import asyncio
import uuid
from backend.factory import backend
from backend.models import UUID, JobCreate, Profile
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from lib.logger import configure_logger
from lib.verify_profile import verify_profile_from_token
from lib.websocket_manager import manager
from services.chat import (
    get_job_history,
    get_thread_history,
    process_chat_message,
    running_jobs,
)
from typing import Any, Dict, Literal, Optional, TypedDict

# Configure logger
logger = configure_logger(__name__)

# Create the router
router = APIRouter(prefix="/chat")


class WebSocketBaseMessage(TypedDict):
    type: str


class WebSocketHistoryMessage(WebSocketBaseMessage):
    type: Literal["history"]
    thread_id: str


class WebSocketChatMessage(WebSocketBaseMessage):
    type: Literal["message"]
    thread_id: str
    agent_id: Optional[str]
    content: str


class WebSocketErrorMessage(TypedDict):
    type: Literal["error"]
    message: str


class JobInfo(TypedDict):
    queue: asyncio.Queue
    thread_id: UUID
    agent_id: Optional[UUID]
    task: Optional[asyncio.Task]


WebSocketMessage = WebSocketHistoryMessage | WebSocketChatMessage
WebSocketResponse = Dict[str, Any]  # Type for response messages


async def handle_history_message(
    message: WebSocketHistoryMessage, profile_id: UUID, session: str
) -> None:
    """Handle history type messages.

    Args:
        message: The history request message
        profile_id: The ID of the requesting profile
        session: The WebSocket session ID
    """
    formatted_history = get_thread_history(UUID(message["thread_id"]), profile_id)
    for history_msg in formatted_history:
        await manager.send_session_message(history_msg, session)


async def handle_chat_message(
    message: WebSocketChatMessage,
    profile: Profile,
    session: str,
) -> None:
    """Handle chat type messages.

    Args:
        message: The chat message
        profile: The user's profile
        session: The WebSocket session ID

    Raises:
        HTTPException: If thread_id is invalid
    """
    thread_id = UUID(message["thread_id"])
    if not thread_id:
        raise HTTPException(status_code=400, detail="Thread ID is required")

    agent_id = UUID(message["agent_id"]) if message.get("agent_id") else None
    formatted_history = get_job_history(thread_id, profile.id)

    # Create and setup job
    job = backend.create_job(
        new_job=JobCreate(
            thread_id=thread_id,
            profile_id=profile.id,
            agent_id=agent_id,
            input=message["content"],
        )
    )

    output_queue: asyncio.Queue[Optional[WebSocketResponse]] = asyncio.Queue()

    # Store job info
    running_jobs[str(job.id)] = JobInfo(
        queue=output_queue,
        thread_id=thread_id,
        agent_id=agent_id,
        task=None,
    )

    # Create and store task
    task = asyncio.create_task(
        process_chat_message(
            job_id=job.id,
            thread_id=thread_id,
            profile=profile,
            agent_id=agent_id,
            input_str=message["content"],
            history=formatted_history,
            output_queue=output_queue,
        )
    )
    running_jobs[str(job.id)]["task"] = task

    # Process results
    try:
        while True:
            result = await output_queue.get()
            if result is None:
                break
            await manager.send_session_message(result, session)
    except Exception as e:
        logger.error(f"Error processing chat message: {str(e)}")
        await manager.broadcast_session_error(str(e), session)


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    profile: Profile = Depends(verify_profile_from_token),
):
    """WebSocket endpoint for real-time chat communication.

    Args:
        websocket (WebSocket): The WebSocket connection
        profile (Profile): The user's profile information

    Raises:
        WebSocketDisconnect: When client disconnects
    """
    generated_session = str(uuid.uuid4())

    try:
        await manager.connect_session(websocket, generated_session)
        logger.debug(f"Starting WebSocket connection for session {generated_session}")

        while True:
            try:
                data: WebSocketMessage = await websocket.receive_json()

                if data["type"] == "history":
                    await handle_history_message(data, profile.id, generated_session)
                elif data["type"] == "message":
                    await handle_chat_message(data, profile, generated_session)
                else:
                    raise HTTPException(
                        status_code=400, detail=f"Unknown message type: {data['type']}"
                    )

            except WebSocketDisconnect:
                break
            except HTTPException as he:
                await manager.send_session_message(
                    WebSocketErrorMessage(type="error", message=he.detail),
                    generated_session,
                )
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
                await manager.broadcast_session_error(str(e), generated_session)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {generated_session}")
    except Exception as e:
        logger.error(f"WebSocket error for session {generated_session}: {str(e)}")
    finally:
        await manager.disconnect_session(websocket, generated_session)
        logger.debug(f"Cleaned up WebSocket connection for session {generated_session}")
