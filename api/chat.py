import asyncio
import uuid
from api.verify_profile import verify_profile_from_token
from backend.factory import backend
from backend.models import JobCreate, JobFilter, Profile, StepFilter
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from lib.logger import configure_logger
from lib.websocket_manager import manager
from pydantic import BaseModel
from services.chat import process_chat_message, running_jobs
from typing import List
from uuid import UUID

# Configure logger
logger = configure_logger(__name__)

# Create the router
router = APIRouter(prefix="/chat")


def get_thread_history(thread_id: UUID, profile_id: UUID) -> List:
    thread = backend.get_thread(thread_id=thread_id)
    if thread.profile_id != profile_id:
        return []
    jobs = backend.list_jobs(filters=JobFilter(thread_id=thread.id))
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
                    "thread_id": str(thread.id),
                    "type": "user",
                }
            )

            steps = backend.list_steps(filters=StepFilter(job_id=job.id))
            if not steps:
                continue
            for step in steps:
                type = "tool" if step.tool else "step"
                formatted_msg = {
                    "role": step.role,
                    "content": step.content,
                    "created_at": step.created_at.isoformat(),
                    "tool": step.tool,
                    "tool_input": step.tool_input,
                    "tool_output": step.tool_output,
                    "agent_id": str(step.agent_id),
                    "thread_id": str(thread.id),
                    "type": type,
                }
                formatted_history.append(formatted_msg)

        # Sort messages by timestamp
        formatted_history.sort(key=lambda x: x["created_at"])
    return formatted_history


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
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
        generated_session = str(uuid.uuid4())
        await manager.connect_session(websocket, generated_session)
        logger.debug(f"Starting WebSocket connection for session {generated_session}")

        # Keep connection open and handle incoming messages
        try:
            while True:
                # Wait for messages from the client
                data = await websocket.receive_json()

                if data.get("type") == "history":
                    formatted_history = get_thread_history(
                        UUID(data.get("thread_id", None)), profile.id
                    )
                    for message in formatted_history:
                        await manager.send_session_message(message, generated_session)
                elif data.get("type") == "message":
                    agent_id = UUID(data.get("agent_id", None))
                    thread_id = UUID(data.get("thread_id", None))
                    if agent_id == None or thread_id == None:
                        await websocket.accept()
                        await websocket.send_json(
                            {"type": "error", "message": "Agent or Thread not passed"}
                        )
                        await websocket.close()
                        return
                    formatted_history = get_thread_history(thread_id, profile.id)
                    content = data.get("content", "")
                    # Create a new job for this message
                    job = backend.create_job(
                        new_job=JobCreate(
                            thread_id=thread_id,
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
                        "agent_id": agent_id,
                        "task": None,
                    }

                    # Create task
                    task = asyncio.create_task(
                        process_chat_message(
                            job_id=job_id,
                            thread_id=thread_id,
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
                            await manager.send_session_message(
                                result, generated_session
                            )
                    except Exception as e:
                        logger.error(f"Error processing chat message: {str(e)}")
                        await manager.broadcast_session_error(str(e), generated_session)

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for session {generated_session}")
        except Exception as e:
            logger.error(
                f"Error in WebSocket connection for session {generated_session}: {str(e)}"
            )
            await manager.broadcast_session_error(str(e), generated_session)
        finally:
            await manager.disconnect_session(websocket, generated_session)
            logger.debug(
                f"Cleaned up WebSocket connection for session {generated_session}"
            )

    except Exception as e:
        logger.error(
            f"Error setting up WebSocket for session {generated_session}: {str(e)}"
        )
        if not websocket.client_state.disconnected:
            await websocket.close()
