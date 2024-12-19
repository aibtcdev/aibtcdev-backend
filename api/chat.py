import asyncio
import datetime
import json
import uuid
from api.verify_profile import ProfileInfo, verify_profile_from_token
from db.helpers import get_conversation_history, get_detailed_conversation
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from lib.logger import configure_logger
from lib.websocket_manager import manager
from pydantic import BaseModel
from services.chat import process_chat_message, running_jobs
from typing import Any, Dict, List, Optional

# Configure logger
logger = configure_logger(__name__)

# Create the router
router = APIRouter(prefix="/chat")


class ChatMessage(BaseModel):
    """Model for chat messages."""

    content: str
    role: str
    name: Optional[str] = None
    function_call: Optional[Dict[str, Any]] = None
    timestamp: datetime.datetime = datetime.datetime.now()

    class Config:
        arbitrary_types_allowed = True


class ChatHistoryResponse(BaseModel):
    """Response model for chat history."""

    messages: List[ChatMessage]
    has_more: bool

    class Config:
        arbitrary_types_allowed = True


class ChatJobResponse(BaseModel):
    """Response model for chat job creation."""

    job_id: str
    status: str = "created"


class ConversationResponse(BaseModel):
    """Response model for a single conversation."""

    id: str
    created_at: datetime.datetime
    profile_id: str
    name: Optional[str]

    class Config:
        arbitrary_types_allowed = True


class ConversationsResponse(BaseModel):
    """Response model for multiple conversations."""

    conversations: List[ConversationResponse]

    class Config:
        arbitrary_types_allowed = True


@router.websocket("/conversation/{conversation_id}/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    conversation_id: str,
    profile: ProfileInfo = Depends(verify_profile_from_token),
):
    """WebSocket endpoint for real-time chat communication.

    Args:
        websocket (WebSocket): The WebSocket connection
        conversation_id (str): The ID of the conversation
        profile (ProfileInfo): The user's profile information

    Raises:
        WebSocketDisconnect: When client disconnects
    """
    try:
        # Verify conversation belongs to user
        conversation = get_detailed_conversation(conversation_id)

        if not conversation:
            await websocket.accept()
            await websocket.send_json(
                {"type": "error", "message": "Conversation not found"}
            )
            await websocket.close()
            return

        await manager.connect_conversation(websocket, conversation_id)
        logger.debug(
            f"Starting WebSocket connection for conversation {conversation_id}"
        )

        # Send conversation history using the jobs from detailed conversation
        if conversation.get("jobs"):
            # Format history messages according to frontend expectations
            formatted_history = []
            for job in conversation["jobs"]:
                if job.get("messages"):
                    for msg in job["messages"]:
                        if isinstance(msg, str):
                            msg = json.loads(msg)

                        # Skip step messages with empty thoughts
                        if msg.get("type") == "step" and (
                            not msg.get("thought") or msg.get("thought").strip() == ""
                        ):
                            continue

                        formatted_msg = {
                            "role": msg.get("role"),
                            "type": msg.get("type"),
                            "content": msg.get("content", ""),
                            "timestamp": msg.get("timestamp")
                            or msg.get("created_at")
                            or msg.get("job_started_at")
                            or datetime.datetime.now().isoformat(),
                            "tool": msg.get("tool"),
                            "tool_input": msg.get("tool_input", None),
                            "result": msg.get("result", None),
                            "thought": msg.get("thought", None),
                        }
                        formatted_history.append(formatted_msg)

            # Sort messages by timestamp
            formatted_history.sort(key=lambda x: x["timestamp"])

            # Send formatted history
            await websocket.send_json(
                {"type": "history", "messages": formatted_history}
            )

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
                            "job_started_at": job_started_at,
                        },
                        conversation_id,
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
                            await manager.send_conversation_message(
                                result, conversation_id
                            )
                    except Exception as e:
                        logger.error(f"Error processing chat message: {str(e)}")
                        await manager.broadcast_conversation_error(
                            str(e), conversation_id
                        )

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for conversation {conversation_id}")
        except Exception as e:
            logger.error(
                f"Error in WebSocket connection for conversation {conversation_id}: {str(e)}"
            )
            await manager.broadcast_conversation_error(str(e), conversation_id)
        finally:
            await manager.disconnect_conversation(websocket, conversation_id)
            logger.debug(
                f"Cleaned up WebSocket connection for conversation {conversation_id}"
            )

    except Exception as e:
        logger.error(
            f"Error setting up WebSocket for conversation {conversation_id}: {str(e)}"
        )
        if not websocket.client_state.disconnected:
            await websocket.close()
