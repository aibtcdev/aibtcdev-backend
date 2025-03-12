import asyncio
import uuid
from typing import Any, Dict, Literal, Optional, TypedDict, Union, cast

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from api.dependencies import verify_profile_from_token
from backend.factory import backend
from backend.models import UUID, JobCreate, Profile
from lib.logger import configure_logger
from lib.websocket_manager import manager
from services.chat import (
    get_job_history,
    get_thread_history,
    process_chat_message,
    running_jobs,
)

# Configure logger
logger = configure_logger(__name__)

# Create the router
router = APIRouter(prefix="/chat")


class WebSocketBaseMessage(TypedDict):
    """Base type for all WebSocket messages."""

    type: str


class WebSocketHistoryMessage(WebSocketBaseMessage):
    """Message type for requesting chat history."""

    type: Literal["history"]
    thread_id: str


class WebSocketChatMessage(WebSocketBaseMessage):
    """Message type for sending chat messages."""

    type: Literal["message"]
    thread_id: str
    agent_id: Optional[str]
    content: str


class WebSocketErrorMessage(TypedDict):
    """Message type for error responses."""

    type: Literal["error"]
    message: str


class JobInfo(TypedDict):
    """Information about a running job."""

    queue: asyncio.Queue
    thread_id: UUID
    agent_id: Optional[UUID]
    task: Optional[asyncio.Task]


# Type aliases for better readability
WebSocketMessage = Union[WebSocketHistoryMessage, WebSocketChatMessage]
WebSocketResponse = Dict[str, Any]  # Type for response messages


async def handle_history_message(
    message: WebSocketHistoryMessage, profile_id: UUID, session: str
) -> None:
    """Handle history type messages by retrieving and sending thread history.

    Args:
        message: The history request message containing thread_id
        profile_id: The ID of the requesting profile
        session: The WebSocket session ID
    """
    try:
        thread_id = UUID(message["thread_id"])
        formatted_history = get_thread_history(thread_id, profile_id)

        for history_msg in formatted_history:
            await manager.send_session_message(history_msg, session)

    except ValueError as e:
        logger.error(f"Invalid thread ID format: {e}")
        await manager.broadcast_session_error("Invalid thread ID format", session)
    except Exception as e:
        logger.error(f"Error retrieving history: {str(e)}")
        await manager.broadcast_session_error(
            f"Error retrieving history: {str(e)}", session
        )


async def handle_chat_message(
    message: WebSocketChatMessage,
    profile: Profile,
    session: str,
) -> None:
    """Handle chat type messages by processing and responding to them.

    Args:
        message: The chat message containing thread_id, agent_id, and content
        profile: The user's profile
        session: The WebSocket session ID

    Raises:
        HTTPException: If thread_id is invalid or missing
    """
    try:
        # Validate thread_id
        thread_id = UUID(message["thread_id"])
        if not thread_id:
            raise HTTPException(status_code=400, detail="Thread ID is required")

        # Parse agent_id if provided
        agent_id = UUID(message["agent_id"]) if message.get("agent_id") else None

        # Get job history
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

        # Create output queue for job results
        output_queue: asyncio.Queue[Optional[WebSocketResponse]] = asyncio.Queue()

        # Store job info
        job_id_str = str(job.id)
        running_jobs[job_id_str] = JobInfo(
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
        running_jobs[job_id_str]["task"] = task

        # Process results
        try:
            while True:
                result = await output_queue.get()
                if result is None:
                    break
                await manager.send_session_message(result, session)
        except Exception as e:
            logger.error(f"Error processing chat message results: {str(e)}")
            await manager.broadcast_session_error(str(e), session)

    except ValueError as e:
        logger.error(f"Invalid UUID format: {e}")
        await manager.broadcast_session_error("Invalid UUID format", session)
    except HTTPException as he:
        logger.error(f"HTTP exception: {he.detail}")
        await manager.broadcast_session_error(he.detail, session)
    except Exception as e:
        logger.error(f"Error processing chat message: {str(e)}")
        await manager.broadcast_session_error(str(e), session)


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    profile: Profile = Depends(verify_profile_from_token),
) -> None:
    """WebSocket endpoint for real-time chat communication.

    This endpoint handles WebSocket connections for chat functionality,
    including message processing and error handling.

    Args:
        websocket: The WebSocket connection
        profile: The user's profile information

    Raises:
        WebSocketDisconnect: When client disconnects
    """
    # Generate unique session ID
    generated_session = str(uuid.uuid4())
    logger.info(f"New WebSocket connection request for user {profile.id}")

    # Flag to track if the WebSocket has been accepted
    connection_accepted = False

    try:
        # Connect the session
        await websocket.accept()
        await manager.connect_session(websocket, generated_session)
        connection_accepted = True
        logger.debug(
            f"WebSocket connection established for session {generated_session}"
        )

        # Main message processing loop
        while True:
            try:
                # Receive and parse message
                data = await websocket.receive_json()
                message = cast(WebSocketMessage, data)

                # Process based on message type
                if message["type"] == "history":
                    await handle_history_message(
                        cast(WebSocketHistoryMessage, message),
                        profile.id,
                        generated_session,
                    )
                elif message["type"] == "message":
                    await handle_chat_message(
                        cast(WebSocketChatMessage, message), profile, generated_session
                    )
                else:
                    error_msg = f"Unknown message type: {message['type']}"
                    logger.warning(error_msg)
                    await manager.send_session_message(
                        WebSocketErrorMessage(type="error", message=error_msg),
                        generated_session,
                    )

            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for session {generated_session}")
                break
            except HTTPException as he:
                logger.error(f"HTTP exception in message processing: {he.detail}")
                if connection_accepted:
                    await manager.send_session_message(
                        WebSocketErrorMessage(type="error", message=he.detail),
                        generated_session,
                    )
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
                if connection_accepted:
                    await manager.broadcast_session_error(str(e), generated_session)

    except WebSocketDisconnect:
        logger.info(
            f"WebSocket disconnected during setup for session {generated_session}"
        )
    except Exception as e:
        logger.error(f"WebSocket error for session {generated_session}: {str(e)}")
    finally:
        # Clean up connection only if it was accepted
        if connection_accepted:
            await manager.disconnect_session(websocket, generated_session)
            logger.debug(
                f"Cleaned up WebSocket connection for session {generated_session}"
            )
