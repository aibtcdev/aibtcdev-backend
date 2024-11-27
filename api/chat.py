import asyncio
import datetime
import json
import uuid
from fastapi import APIRouter, Body, HTTPException, Depends, Query, WebSocket, WebSocketDisconnect
from api.verify_profile import ProfileInfo, verify_profile, verify_profile_from_token
from db.helpers import (
    add_conversation,
    add_job,
    delete_conversation,
    get_conversations,
    get_detailed_conversation,
    get_latest_conversation,
    get_conversation_history,
)
from db.client import supabase
from fastapi.responses import JSONResponse
from services.crews import execute_chat_stream
from lib.logger import configure_logger
from lib.websocket_manager import manager
import functools
from concurrent.futures import ThreadPoolExecutor

# Configure logger
logger = configure_logger(__name__)

# Create a thread pool executor for running sync functions
thread_pool = ThreadPoolExecutor()

router = APIRouter(prefix="/chat")
running_jobs = {}

@router.post("/")
async def trigger_chat(
    input_str: str = Body(...),
    conversation_id: str = Query(...),
    profile: ProfileInfo = Depends(verify_profile),
):
    # Generate a unique task ID
    job_id = str(uuid.uuid4())
    logger.info(f"Starting new chat job {job_id} for conversation {conversation_id}")
    
    output_queue = asyncio.Queue()
    results_array = []

    # Add initial user message
    results_array.append(
        json.dumps({
            "role": "user",
            "type": "user",
            "content": input_str,
            "timestamp": datetime.datetime.now().isoformat()
        })
    )

    async def task_wrapper():
        try:
            # Get detailed conversation history to help provide context
            logger.debug(f"Fetching conversation history for {conversation_id}")
            history = get_conversation_history(conversation_id)

            # Run the actual crew stream task, yielding output to the queue
            logger.debug(f"Starting chat stream for job {job_id}")
            job_started_at = datetime.datetime.now().isoformat()
            
            async for result in execute_chat_stream(
                str(profile.account_index), history, input_str
            ):
                # Add to the output queue for WebSocket streaming
                stream_message = {
                    "type": "stream",
                    "stream_type": result.get("type", "result"),  # step, task, or result
                    "content": result.get("content", ""),
                    "timestamp": datetime.datetime.now().isoformat(),
                    "job_started_at": job_started_at,
                    "role": "assistant"
                }
                await output_queue.put(stream_message)

                # Build object in memory for later storage in db
                result_with_timestamp = {
                    **result,
                    "timestamp": datetime.datetime.now().isoformat(),
                }
                results_array.append(json.dumps(result_with_timestamp))
            await output_queue.put(None)  # Signal completion
            logger.info(f"Chat stream completed for job {job_id}")
        except Exception as e:
            logger.error(f"Error in chat stream for job {job_id}: {str(e)}")
            raise
        finally:
            logger.debug(f"Saving chat results for job {job_id}")
            # Get the final result from the last message
            final_result = json.loads(results_array[-1]) if results_array else None
            final_result_content = final_result.get("content", "") if final_result else ""
            
            add_job(
                profile_id=profile.id,
                conversation_id=conversation_id,
                crew_id=None,  # Default crew ID for chat specialist
                input_data=input_str,
                tokens=final_result.get("tokens", 0) if final_result else 0,
                result=final_result_content,
                messages=results_array
            )
            running_jobs.pop(job_id, None)
            logger.debug(f"Cleaned up job {job_id}")

    task = asyncio.create_task(task_wrapper())
    running_jobs[job_id] = {
        "task": task,
        "queue": output_queue,
        "profile": profile,
        "timestamp": datetime.datetime.now().isoformat(),
    }

    logger.info(f"Chat job {job_id} initialized and running")
    return JSONResponse(content={"job_id": job_id})


@router.websocket("/conversation/{conversation_id}/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    conversation_id: str,
    profile: ProfileInfo = Depends(verify_profile_from_token)
):
    try:
        # Verify conversation belongs to user
        conversation = get_detailed_conversation(conversation_id)
        
        if not conversation:
            await websocket.accept()
            await websocket.send_json({"type": "error", "message": "Conversation not found"})
            await websocket.close()
            return

        await manager.connect_conversation(websocket, conversation_id)
        logger.debug(f"Starting WebSocket connection for conversation {conversation_id}")

        # Keep connection open and handle incoming messages
        try:
            while True:
                # Wait for messages from the client
                data = await websocket.receive_json()
                
                if data.get("type") == "chat_message":
                    # Create a new job for this message
                    job_id = str(uuid.uuid4())
                    output_queue = asyncio.Queue()
                    
                    # Store job info
                    running_jobs[job_id] = {
                        "queue": output_queue,
                        "conversation_id": conversation_id,
                        "task": None,
                    }

                    # Get conversation history
                    history = get_conversation_history(conversation_id)
                    
                    # Create task
                    task = asyncio.create_task(
                        process_chat_message(
                            job_id=job_id,
                            conversation_id=conversation_id,
                            profile=profile,
                            input_str=data.get("message", ""),
                            history=history,
                            output_queue=output_queue,
                        )
                    )
                    running_jobs[job_id]["task"] = task

                    # Send job started message
                    job_started_at = datetime.datetime.now().isoformat()
                    await manager.send_conversation_message(
                        {
                            "type": "job_started",
                            "job_id": job_id,
                            "job_started_at": job_started_at
                        },
                        conversation_id
                    )

                    # Start streaming results
                    try:
                        while True:
                            result = await output_queue.get()
                            if result is None:
                                break
                            # Add job_started_at if it's a stream message
                            if result.get("type") == "stream":
                                result["job_started_at"] = job_started_at
                            await manager.send_conversation_message(result, conversation_id)
                    except Exception as e:
                        logger.error(f"Error processing chat message: {str(e)}")
                        await manager.broadcast_conversation_error(str(e), conversation_id)

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for conversation {conversation_id}")
        except Exception as e:
            logger.error(f"Error in WebSocket connection for conversation {conversation_id}: {str(e)}")
            await manager.broadcast_conversation_error(str(e), conversation_id)
        finally:
            await manager.disconnect_conversation(websocket, conversation_id)
            logger.debug(f"Cleaned up WebSocket connection for conversation {conversation_id}")

    except Exception as e:
        logger.error(f"Error setting up WebSocket for conversation {conversation_id}: {str(e)}")
        if not websocket.client_state.disconnected:
            await websocket.close()

async def process_chat_message(
    job_id: str,
    conversation_id: str,
    profile: ProfileInfo,
    input_str: str,
    history: list,
    output_queue: asyncio.Queue
):
    try:
        results = []
        logger.debug(f"Starting chat stream for job {job_id}")
        
        # Add initial user message
        results.append({
            "role": "user",
            "type": "user",
            "content": input_str,
            "timestamp": datetime.datetime.now().isoformat()
        })
        
        async for result in execute_chat_stream(
            str(profile.account_index), history, input_str
        ):
            # Add to the output queue for WebSocket streaming
            stream_message = {
                "type": "stream",
                "stream_type": result.get("type", "result"),  # step, task, or result
                "content": result.get("content", ""),
                "tool": result.get("tool", None),
                "tool_input": result.get("tool_input", None),
                "result": result.get("result", None),
                "thought": result.get("thought", None),
                "timestamp": datetime.datetime.now().isoformat(),
                "job_started_at": datetime.datetime.now().isoformat(),
                "role": "assistant"
            }
            await output_queue.put(stream_message)

            # Build object in memory for later storage in db
            result_with_timestamp = {
                **result,
                "timestamp": datetime.datetime.now().isoformat(),
            }
            results.append(result_with_timestamp)

        # Store results in database
        # Get the final result from the last message
        final_result = results[-1] if results else None
        final_result_content = final_result.get("content", "") if final_result else ""
        
        add_job(
            profile_id=profile.id,
            conversation_id=conversation_id,
            crew_id=None,  # Default crew ID for chat specialist
            input_data=input_str,
            tokens=final_result.get("tokens", 0) if final_result else 0,
            result=final_result_content,
            messages=[json.dumps(r) for r in results]
        )
        logger.info(f"Chat job {job_id} completed and stored")

    except Exception as e:
        logger.error(f"Error in chat stream for job {job_id}: {str(e)}")
        raise
    finally:
        # Signal completion
        await output_queue.put(None)
        if job_id in running_jobs:
            del running_jobs[job_id]

@router.post("/conversations")
async def create_conversation(
    profile: ProfileInfo = Depends(verify_profile),
):
    try:
        logger.debug(f"Creating new conversation for profile {profile.id}")
        new_conversation = add_conversation(profile)
        if new_conversation:
            logger.info(f"Created conversation {new_conversation['id']} for profile {profile.id}")
            return JSONResponse(content=new_conversation)
        else:
            raise HTTPException(
                status_code=500, detail="Failed to create conversation"
            )
    except Exception as e:
        logger.error(f"Failed to create conversation for profile {profile.id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create conversation: {str(e)}"
        )

@router.get("/conversations")
async def get_conversations_endpoint(
    profile: ProfileInfo = Depends(verify_profile),
):
    try:
        logger.debug(f"Fetching conversations for profile {profile.id}")
        conversations = get_conversations(profile)
        logger.info(f"Retrieved {len(conversations)} conversations for profile {profile.id}")
        return conversations
    except Exception as e:
        logger.error(f"Failed to fetch conversations for profile {profile.id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch conversations: {str(e)}"
        )

@router.get("/conversations/latest")
async def api_get_latest_conversation(
    profile: ProfileInfo = Depends(verify_profile),
):
    try:
        logger.debug(f"Fetching latest conversation for profile {profile.id}")
        conversations = get_latest_conversation(profile)
        if conversations:
            logger.info(f"Retrieved latest conversation {conversations['id']} for profile {profile.id}")
            return conversations
        logger.info(f"No conversations found for profile {profile.id}")
        new_conversation = add_conversation(profile)
        if new_conversation:
            logger.info(f"Created conversation {new_conversation['id']} for profile {profile.id}")
            return JSONResponse(content=new_conversation)
        else:
            raise HTTPException(
                status_code=500, detail="Failed to create conversation"
            )
    except Exception as e:
        logger.error(f"Failed to fetch latest conversation for profile {profile.id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch latest conversation: {str(e)}"
        )

@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    profile: ProfileInfo = Depends(verify_profile),
):
    try:
        logger.debug(f"Fetching details for conversation {conversation_id}")
        response = get_detailed_conversation(conversation_id)
        logger.info(f"Retrieved details for conversation {conversation_id}")
        return JSONResponse(content=response)

    except Exception as e:
        logger.error(f"Failed to fetch conversation details for {conversation_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch conversation details: {str(e)}",
        )

@router.delete("/conversations/{conversation_id}")
async def delete_conversation_endpoint(
    conversation_id: str,
    profile: ProfileInfo = Depends(verify_profile),
):
    try:
        logger.debug(f"Deleting conversation {conversation_id}")
        delete_conversation(profile, conversation_id)
        logger.info(f"Successfully deleted conversation {conversation_id}")
        return JSONResponse(content={"status": "History deleted successfully"})

    except Exception as e:
        logger.error(f"Failed to delete conversation {conversation_id}: {str(e)}")
