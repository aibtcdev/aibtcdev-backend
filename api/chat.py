import asyncio
import uuid
from typing import Any, Dict, Literal, Optional, TypedDict, Union, cast

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from api.dependencies import verify_profile_from_token
from backend.factory import backend
from backend.models import UUID, JobCreate, Profile
from lib.logger import configure_logger
from services.chat import (
    get_job_history,
    get_thread_history,
    process_chat_message,
    running_jobs,
)
from services.websocket import websocket_manager

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
    connection_active: bool


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
            await websocket_manager.send_message(history_msg, session)

    except ValueError as e:
        logger.error(f"Invalid thread ID format: {e}")
        await websocket_manager.send_error("Invalid thread ID format", session)
    except Exception as e:
        logger.error(f"Error retrieving history: {str(e)}")
        await websocket_manager.send_error(
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
    """
    job_id = None
    job_id_str = None

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
        job_id = job.id
        job_id_str = str(job_id)

        # Create output queue for job results
        output_queue: asyncio.Queue[Optional[WebSocketResponse]] = asyncio.Queue()

        # Store job info
        running_jobs[job_id_str] = JobInfo(
            queue=output_queue,
            thread_id=thread_id,
            agent_id=agent_id,
            task=None,
            connection_active=True,
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
        message_count = 0
        try:
            while True:
                try:
                    # Use timeout to avoid blocking forever if there's an issue
                    result = await asyncio.wait_for(output_queue.get(), timeout=1.0)

                    # None signals end of processing
                    if result is None:
                        logger.debug(
                            f"Received end of processing signal for job {job_id_str}"
                        )
                        break

                    message_count += 1

                    # Check if job is still marked active
                    job_active = job_id_str in running_jobs and running_jobs[
                        job_id_str
                    ].get("connection_active", False)

                    if job_active:
                        try:
                            # Try to send the message
                            await websocket_manager.send_message(result, session)
                        except Exception as e:
                            logger.debug(
                                f"Error sending message, marking job {job_id_str} as disconnected: {e}"
                            )
                            if job_id_str in running_jobs:
                                running_jobs[job_id_str]["connection_active"] = False
                    else:
                        logger.debug(
                            f"Job {job_id_str} marked inactive, processing without sending messages"
                        )

                except asyncio.TimeoutError:
                    # Check if the job still exists
                    if job_id_str not in running_jobs:
                        logger.debug(f"Job {job_id_str} no longer exists, exiting loop")
                        break
                    continue

            logger.info(
                f"Successfully processed {message_count} messages for job {job_id_str}"
            )

        except Exception as e:
            logger.error(
                f"Error processing chat message results for job {job_id_str}: {str(e)}"
            )
            # Only try to send error if we think connection is still active
            if job_id_str in running_jobs and running_jobs[job_id_str].get(
                "connection_active", False
            ):
                try:
                    await websocket_manager.send_error(str(e), session)
                except Exception:
                    # If this fails, client is definitely disconnected
                    if job_id_str in running_jobs:
                        running_jobs[job_id_str]["connection_active"] = False
                    logger.debug(
                        f"Failed to send error message, connection marked inactive for job {job_id_str}"
                    )

    except ValueError as e:
        logger.error(f"Invalid UUID format: {e}")
        await websocket_manager.send_error("Invalid UUID format", session)
    except HTTPException as he:
        logger.error(f"HTTP exception: {he.detail}")
        await websocket_manager.send_error(he.detail, session)
    except Exception as e:
        logger.error(f"Error processing chat message: {str(e)}")
        await websocket_manager.send_error(str(e), session)
    finally:
        # Make sure job is cleaned up properly, regardless of errors
        if job_id_str and job_id_str in running_jobs:
            logger.debug(
                f"Cleaning up job {job_id_str} in handle_chat_message finally block"
            )
            task = running_jobs[job_id_str].get("task")
            if task and not task.done() and not task.cancelled():
                logger.debug(f"Ensuring task for job {job_id_str} completes")
                # Don't cancel the task - let it complete to save results in the database


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
    """
    # Generate unique session ID
    session_id = str(uuid.uuid4())
    logger.info(f"New WebSocket connection request for user {profile.id}")

    # Flag to track if the WebSocket has been accepted
    connection_accepted = False

    try:
        # Connect the session with a timeout to prevent hanging
        try:
            await asyncio.wait_for(websocket.accept(), timeout=2.0)
            connection_accepted = True
            logger.debug(f"WebSocket accepted for session {session_id}")
        except asyncio.TimeoutError:
            logger.error(f"Timeout accepting WebSocket for session {session_id}")
            return
        except Exception as e:
            logger.error(f"Error accepting WebSocket: {type(e).__name__}: {str(e)}")
            return

        # Register with WebSocket manager
        try:
            await asyncio.wait_for(
                websocket_manager.connect(websocket, session_id), timeout=2.0
            )
            logger.debug(f"WebSocket connection established for session {session_id}")
        except Exception as e:
            logger.error(f"Error registering WebSocket: {type(e).__name__}: {str(e)}")
            # Continue anyway, we'll handle disconnections gracefully

        # Main message processing loop
        while True:
            try:
                # Receive and parse message with a reasonable timeout
                try:
                    data = await asyncio.wait_for(
                        websocket.receive_json(), timeout=60.0
                    )
                    message = cast(WebSocketMessage, data)
                except asyncio.TimeoutError:
                    # Check if client is still connected (periodic ping)
                    try:
                        # Send a lightweight ping message to check connection
                        ping_payload = {"type": "ping"}
                        await asyncio.wait_for(
                            websocket.send_json(ping_payload), timeout=1.0
                        )
                        continue  # Connection still alive, continue waiting for messages
                    except Exception:
                        # Connection dead, break the loop
                        logger.debug(
                            f"Ping failed for session {session_id}, client likely disconnected"
                        )
                        break

                # Process based on message type
                if message["type"] == "history":
                    await handle_history_message(
                        cast(WebSocketHistoryMessage, message),
                        profile.id,
                        session_id,
                    )
                elif message["type"] == "message":
                    await handle_chat_message(
                        cast(WebSocketChatMessage, message), profile, session_id
                    )
                else:
                    error_msg = f"Unknown message type: {message['type']}"
                    logger.warning(error_msg)
                    await websocket_manager.send_error(error_msg, session_id)

            except WebSocketDisconnect:
                # Normal client disconnect - break out of the loop
                logger.info(f"WebSocket disconnected for session {session_id}")
                break
            except Exception as e:
                # For other errors, log and try to continue if possible
                error_str = str(e)
                logger.error(f"Error processing message: {error_str}")

                # If we see the "accept" error, the connection is broken
                if "accept" in error_str.lower():
                    logger.error(
                        "WebSocket connection is broken (accept error), breaking loop"
                    )
                    break

                # Try to send error message, but don't crash if it fails
                try:
                    await asyncio.wait_for(
                        websocket_manager.send_error(error_str, session_id),
                        timeout=1.0,
                    )
                except Exception:
                    # If sending the error fails, client is likely disconnected
                    logger.debug(
                        f"Failed to send error message to session {session_id}"
                    )
                    break

    except WebSocketDisconnect:
        # Client disconnected during setup
        logger.info(f"WebSocket disconnected during setup for session {session_id}")
    except Exception as e:
        # Unexpected error during setup
        logger.error(
            f"WebSocket error for session {session_id}: {type(e).__name__}: {str(e)}"
        )
    finally:
        # Always clean up, even if there was an error
        if connection_accepted:
            try:
                # Ensure all jobs for this session are marked as disconnected
                from services.chat import mark_jobs_disconnected_for_session

                await asyncio.wait_for(
                    mark_jobs_disconnected_for_session(session_id), timeout=2.0
                )

                # Disconnect from WebSocket manager
                await asyncio.wait_for(
                    websocket_manager.disconnect(websocket, session_id), timeout=2.0
                )
                logger.debug(
                    f"Cleaned up WebSocket connection for session {session_id}"
                )
            except Exception as e:
                logger.error(
                    f"Error during WebSocket cleanup: {type(e).__name__}: {str(e)}"
                )
