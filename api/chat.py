import asyncio
import datetime
from api.verify_profile import verify_profile_from_token
from backend.factory import backend
from backend.models import JobCreate, JobFilter, Profile, StepFilter
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from lib.logger import configure_logger
from lib.websocket_manager import manager
from pydantic import BaseModel
from services.chat import process_chat_message, running_jobs
from typing import Any, Dict, List, Optional
from uuid import UUID

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
    profile: Profile = Depends(verify_profile_from_token),
):
    """WebSocket endpoint for real-time chat communication.

    Args:
        websocket (WebSocket): The WebSocket connection
        conversation_id (str): The ID of the conversation
        profile (Profile): The user's profile information

    Raises:
        WebSocketDisconnect: When client disconnects
    """
    try:
        # Verify conversation belongs to user
        conversation_id_uuid = UUID(conversation_id)
        conversation = backend.get_conversation(convo_id=conversation_id_uuid)
        logger.info(f"Received WebSocket connection for conversation {conversation}")
        jobs = backend.list_jobs(
            filters=JobFilter(conversation_id=conversation_id_uuid)
        )
        logger.info(f"Jobs for conversation {conversation}: {jobs}")

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
        formatted_history = []
        # Send conversation history using the jobs from detailed conversation
        if jobs:
            # Format history messages according to frontend expectations
            for job in jobs:
                logger.info(f"Processing job {job}")
                # Add user input message
                formatted_history.append(
                    {
                        "role": "user",
                        "content": job.input,
                        "timestamp": job.created_at.isoformat(),
                    }
                )

                steps = backend.list_steps(filters=StepFilter(job_id=job.id))
                if not steps:
                    continue
                for step in steps:
                    formatted_msg = {
                        "role": step.role,
                        "content": step.content,
                        "timestamp": step.created_at.isoformat(),
                        "tool": step.tool,
                        "tool_input": step.tool_input,
                        "tool_output": step.tool_output,
                        "thought": step.thought,
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

                    agent_id = UUID(data.get("agent_id", None))
                    message = data.get("message", "")
                    # Create a new job for this message
                    job = backend.create_job(
                        new_job=JobCreate(
                            conversation_id=conversation_id_uuid,
                            profile_id=profile.id,
                            agent_id=agent_id,
                            input=message,
                        )
                    )
                    job_id = job.id
                    output_queue = asyncio.Queue()

                    # Store job info
                    running_jobs[str(job_id)] = {
                        "queue": output_queue,
                        "conversation_id": conversation_id,
                        "task": None,
                    }

                    # Create task
                    task = asyncio.create_task(
                        process_chat_message(
                            job_id=job_id,
                            conversation_id=conversation_id_uuid,
                            profile=profile,
                            agent_id=agent_id,
                            input_str=message,
                            history=formatted_history,
                            output_queue=output_queue,
                        )
                    )
                    running_jobs[str(job_id)]["task"] = task

                    # Send job started message
                    job_started_at = datetime.datetime.now().isoformat()
                    await manager.send_conversation_message(
                        {
                            "type": "job_started",
                            "job_id": str(job_id),
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
                            logger.debug(result)
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
