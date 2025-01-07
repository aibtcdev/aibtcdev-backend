import asyncio
from api.verify_profile import verify_profile_from_token
from backend.factory import backend
from backend.models import JobCreate, JobFilter, Profile, StepFilter
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from lib.logger import configure_logger
from lib.websocket_manager import manager
from pydantic import BaseModel
from services.chat import process_chat_message, running_jobs
from uuid import UUID

# Configure logger
logger = configure_logger(__name__)

# Create the router
router = APIRouter(prefix="/chat")


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    thread_id: str = Query(..., description="Thread ID"),
    profile: Profile = Depends(verify_profile_from_token),
):
    """WebSocket endpoint for real-time chat communication.

    Args:
        websocket (WebSocket): The WebSocket connection
        thread_id (str): The ID of the thread
        profile (Profile): The user's profile information

    Raises:
        WebSocketDisconnect: When client disconnects
    """
    try:
        # Verify thread belongs to user
        thread_id_uuid = UUID(thread_id)
        thread = backend.get_thread(thread_id=thread_id_uuid)
        logger.info(f"Received WebSocket connection for thread {thread}")
        jobs = backend.list_jobs(filters=JobFilter(thread_id=thread_id_uuid))
        logger.info(f"Jobs for thread {thread}: {jobs}")

        if not thread:
            await websocket.accept()
            await websocket.send_json({"type": "error", "message": "Thread not found"})
            await websocket.close()
            return

        await manager.connect_thread(websocket, thread_id)
        logger.debug(f"Starting WebSocket connection for thread {thread_id}")
        formatted_history = []
        if jobs:
            for job in jobs:
                logger.info(f"Processing job {job}")
                # Add user input message
                formatted_history.append(
                    {
                        "role": "user",
                        "content": job.input,
                        "created_at": job.created_at.isoformat(),
                    }
                )

                steps = backend.list_steps(filters=StepFilter(job_id=job.id))
                if not steps:
                    continue
                for step in steps:
                    formatted_msg = {
                        "role": step.role,
                        "content": step.content,
                        "created_at": step.created_at.isoformat(),
                        "tool": step.tool,
                        "tool_input": step.tool_input,
                        "tool_output": step.tool_output,
                        "agent_id": str(step.agent_id),
                        "type": "step",
                    }
                    await websocket.send_json(formatted_msg)
                    formatted_history.append(formatted_msg)

            # Sort messages by timestamp
            formatted_history.sort(key=lambda x: x["created_at"])

        # Keep connection open and handle incoming messages
        try:
            while True:
                # Wait for messages from the client
                data = await websocket.receive_json()

                if data.get("role") == "user":
                    agent_id = UUID(data.get("agent_id", None))
                    content = data.get("content", "")
                    # Create a new job for this message
                    job = backend.create_job(
                        new_job=JobCreate(
                            thread_id=thread_id_uuid,
                            profile_id=profile.id,
                            agent_id=agent_id,
                            input=content,
                        )
                    )
                    job_id = job.id
                    output_queue = asyncio.Queue()

                    # Store job info
                    running_jobs[str(job_id)] = {
                        "queue": output_queue,
                        "thread_id": thread_id,
                        "task": None,
                    }

                    # Create task
                    task = asyncio.create_task(
                        process_chat_message(
                            job_id=job_id,
                            thread_id=thread_id_uuid,
                            profile=profile,
                            agent_id=agent_id,
                            input_str=content,
                            history=formatted_history,
                            output_queue=output_queue,
                        )
                    )
                    running_jobs[str(job_id)]["task"] = task

                    # Start streaming results
                    try:
                        while True:
                            result = await output_queue.get()
                            if result is None:
                                break
                            # Add job_started_at if it's a stream message
                            logger.debug(result)
                            if result.get("type") == "stream":
                                result["job_started_at"] = job_started_at
                            await manager.send_thread_message(result, thread_id)
                    except Exception as e:
                        logger.error(f"Error processing chat message: {str(e)}")
                        await manager.broadcast_thread_error(str(e), thread_id)

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for thread {thread_id}")
        except Exception as e:
            logger.error(
                f"Error in WebSocket connection for thread {thread_id}: {str(e)}"
            )
            await manager.broadcast_thread_error(str(e), thread_id)
        finally:
            await manager.disconnect_thread(websocket, thread_id)
            logger.debug(f"Cleaned up WebSocket connection for thread {thread_id}")

    except Exception as e:
        logger.error(f"Error setting up WebSocket for thread {thread_id}: {str(e)}")
        if not websocket.client_state.disconnected:
            await websocket.close()
