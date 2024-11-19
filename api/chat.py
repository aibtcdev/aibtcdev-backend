import asyncio
import datetime
import json
import uuid
from fastapi import APIRouter, Body, HTTPException, Depends, Query
from api.verify_profile import ProfileInfo, verify_profile
from db.helpers import (
    add_conversation,
    add_job,
    delete_conversation,
    get_conversations,
    get_detailed_conversation,
    get_latest_conversation,
)
from db.supabase_client import supabase
from fastapi.responses import JSONResponse, StreamingResponse
from services.crew_services import execute_chat_stream

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
    output_queue = asyncio.Queue()
    results_array = []

    results_array.append(
        json.dumps(
            {
                "role": "user",
                "type": "user",
                "content": input_str,
                "timestamp": datetime.datetime.now().isoformat(),
            }
        )
    )

    async def task_wrapper():
        try:
            # Get detailed conversation history to help provide context
            history = get_detailed_conversation(conversation_id)

            # Run the actual crew stream task, yielding output to the queue
            async for result in execute_chat_stream(
                str(profile.account_index), history, input_str
            ):
                # Add to the output queue for SSE streaming
                await output_queue.put(result)

                # Build object in memory for later storage in db
                # Add some extra metadata
                result["timestamp"] = datetime.datetime.now().isoformat()
                results_array.append(json.dumps(result))
            await output_queue.put(None)  # Signal completion
        finally:
            add_job(
                profile.id,
                conversation_id,
                None,
                input_str,
                "",
                results_array,
            )
            running_jobs.pop(job_id, None)

    task = asyncio.create_task(task_wrapper())
    running_jobs[job_id] = {
        "task": task,
        "queue": output_queue,
        "profile": profile,
        "timestamp": datetime.datetime.now().isoformat(),
    }

    # Return the task ID immediately
    return JSONResponse(content={"job_id": job_id})


@router.get("/{job_id}/stream")
async def sse_streaming(job_id: str):
    task_info = running_jobs.get(job_id)
    if not task_info:
        # Send a custom 404 error message as an SSE event
        async def not_found_event_generator():
            error_message = json.dumps({"type": "error", "message": "Task not found"})
            yield f"event: error\ndata: {error_message}\n\n"
            return  # Close the generator after sending the error

        return StreamingResponse(
            not_found_event_generator(), media_type="text/event-stream"
        )

    output_queue = task_info["queue"]

    async def event_generator():
        try:
            while True:
                # Retrieve data from the queue
                result = await output_queue.get()
                if result is None:  # Task completed
                    break
                # Yield the result as JSON for SSE
                json_result = json.dumps(result)
                yield f"data: {json_result}\n\n"
        except Exception as e:
            # Send any runtime error as an SSE error event
            error_message = json.dumps(
                {"type": "error", "message": f"Execution error: {str(e)}"}
            )
            yield f"event: error\ndata: {error_message}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
        },
    )


@router.post("/conversations")
async def create_conversation(
    profile: ProfileInfo = Depends(verify_profile),
):
    try:
        new_conversation = add_conversation(profile)
        if new_conversation.data:
            return JSONResponse(content=new_conversation.data[0])
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create new conversation: {str(e)}",
            )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create new conversations: {str(e)}"
        )


@router.get("/conversations")
async def get_conversations(
    profile: ProfileInfo = Depends(verify_profile),
):
    try:
        conversations = get_conversations(profile)
        if conversations:
            return JSONResponse(content=conversations)
        else:
            new_conversation = add_conversation(profile)
            if new_conversation.data:
                return JSONResponse(content=new_conversation.data[0])
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to create new conversation: {str(e)}",
                )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get conversations: {str(e)}"
        )


@router.get("/conversations/latest")
async def api_get_latest_conversation(
    profile: ProfileInfo = Depends(verify_profile),
):
    try:
        conversations = get_latest_conversation(profile)
        if conversations:
            return JSONResponse(content=conversations)
        else:
            new_conversation = add_conversation(profile)
            if new_conversation.data:
                return JSONResponse(content=new_conversation.data[0])
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to create new conversation: {str(e)}",
                )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get conversations: {str(e)}"
        )


@router.get("/conversations/{conversation_id}")
async def get_conversation_details(
    conversation_id: str,
    profile: ProfileInfo = Depends(verify_profile),
):
    try:
        # Retrieve existing conversation for the user if it exists
        response = get_detailed_conversation(conversation_id)
        return JSONResponse(content=response)

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete history: {str(e)}"
        )


# need a endpoint to reset the history
@router.delete("/conversations/{conversation_id}")
async def delete_history(
    conversation_id: str,
    profile: ProfileInfo = Depends(verify_profile),
):
    try:
        # Retrieve existing conversation for the user if it exists
        delete_conversation(profile, conversation_id)
        return JSONResponse(content={"status": "History deleted successfully"})

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete history: {str(e)}"
        )
