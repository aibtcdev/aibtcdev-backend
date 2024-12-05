import asyncio
import datetime
import json
import uuid
from fastapi import APIRouter, Body, HTTPException, Depends, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from api.verify_profile import ProfileInfo, verify_profile, verify_profile_from_token
from db.helpers import (
    add_conversation,
    delete_conversation,
    get_conversations,
    get_detailed_conversation,
    get_latest_conversation,
    get_conversation_history,
)
from lib.logger import configure_logger
from services.bot import send_message_to_user
from lib.websocket_manager import manager
from services.chat import process_chat_message, running_jobs

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
    profile: ProfileInfo = Depends(verify_profile_from_token)
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
            await websocket.send_json({"type": "error", "message": "Conversation not found"})
            await websocket.close()
            return

        await manager.connect_conversation(websocket, conversation_id)
        logger.debug(f"Starting WebSocket connection for conversation {conversation_id}")

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
                        if msg.get("type") == "step" and (not msg.get("thought") or msg.get("thought").strip() == ""):
                            continue

                        formatted_msg = {
                            "role": msg.get("role"),
                            "type": msg.get("type"),
                            "content": msg.get("content", ""),
                            "timestamp": msg.get("timestamp") or msg.get("created_at") or msg.get("job_started_at") or datetime.datetime.now().isoformat(),
                            "tool": msg.get("tool"),
                            "tool_input": msg.get("tool_input", None),
                            "result": msg.get("result", None),
                            "thought": msg.get("thought", None)
                        }
                        formatted_history.append(formatted_msg)

            # Sort messages by timestamp
            formatted_history.sort(key=lambda x: x["timestamp"])
            
            # Send formatted history
            await websocket.send_json({
                "type": "history",
                "messages": formatted_history
            })

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

@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    profile: ProfileInfo = Depends(verify_profile),
) -> ConversationResponse:
    """Create a new conversation.
    
    Args:
        profile (ProfileInfo): The user's profile information
        
    Returns:
        JSONResponse: A JSON response with the new conversation
        
    Raises:
        HTTPException: If the conversation cannot be created
    """
    try:
        logger.debug(f"Creating new conversation for profile {profile.id}")
        new_conversation = add_conversation(profile)
        if new_conversation:
            logger.info(f"Created conversation {new_conversation['id']} for profile {profile.id}")
            return ConversationResponse(**new_conversation)
        else:
            raise HTTPException(
                status_code=500, detail="Failed to create conversation"
            )
    except Exception as e:
        logger.error(f"Failed to create conversation for profile {profile.id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create conversation: {str(e)}",
        )

@router.get("/conversations", response_model=ConversationsResponse)
async def get_conversations_endpoint(
    profile: ProfileInfo = Depends(verify_profile),
) -> ConversationsResponse:
    """Get conversations for the logged-in user.
    
    Args:
        profile (ProfileInfo): The user's profile information
        
    Returns:
        list: A list of conversations
        
    Raises:
        HTTPException: If the conversations cannot be retrieved
    """
    try:
        logger.debug(f"Fetching conversations for profile {profile.id}")
        conversations = get_conversations(profile)
        logger.info(f"Retrieved {len(conversations)} conversations for profile {profile.id}")
        return ConversationsResponse(conversations=[ConversationResponse(**c) for c in conversations])
    except Exception as e:
        logger.error(f"Failed to fetch conversations for profile {profile.id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch conversations: {str(e)}",
        )

@router.get("/conversations/latest", response_model=ConversationResponse)
async def api_get_latest_conversation(
    profile: ProfileInfo = Depends(verify_profile),
) -> ConversationResponse:
    """Get the latest conversation for the logged-in user.
    
    Args:
        profile (ProfileInfo): The user's profile information
        
    Returns:
        JSONResponse: A JSON response with the latest conversation
        
    Raises:
        HTTPException: If the latest conversation cannot be retrieved
    """
    try:
        logger.debug(f"Fetching latest conversation for profile {profile.id}")
        conversations = get_latest_conversation(profile)
        if conversations:
            logger.info(f"Retrieved latest conversation {conversations['id']} for profile {profile.id}")
            logger.debug(conversations)
            return ConversationResponse(**conversations)
        logger.info(f"No conversations found for profile {profile.id}")
        new_conversation = add_conversation(profile)
        if new_conversation:
            logger.info(f"Created conversation {new_conversation['id']} for profile {profile.id}")
            return ConversationResponse(**new_conversation)
        else:
            raise HTTPException(
                status_code=500, detail="Failed to create conversation"
            )
    except Exception as e:
        logger.error(f"Failed to fetch latest conversation for profile {profile.id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch latest conversation: {str(e)}",
        )

@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    profile: ProfileInfo = Depends(verify_profile),
) -> ConversationResponse:
    """Get a conversation by ID.
    
    Args:
        conversation_id (str): The ID of the conversation
        profile (ProfileInfo): The user's profile information
        
    Returns:
        JSONResponse: A JSON response with the conversation
        
    Raises:
        HTTPException: If the conversation cannot be retrieved
    """
    try:
        logger.debug(f"Fetching details for conversation {conversation_id}")
        response = get_detailed_conversation(conversation_id)
        logger.info(f"Retrieved details for conversation {conversation_id}")
        return ConversationResponse(**response)

    except Exception as e:
        logger.error(f"Failed to fetch conversation details for {conversation_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch conversation details: {str(e)}",
        )

@router.delete("/conversations/{conversation_id}", response_model=Dict[str, str])
async def delete_conversation_endpoint(
    conversation_id: str,
    profile: ProfileInfo = Depends(verify_profile),
) -> Dict[str, str]:
    """Delete a conversation by ID.
    
    Args:
        conversation_id (str): The ID of the conversation
        profile (ProfileInfo): The user's profile information
        
    Returns:
        JSONResponse: A JSON response with the result of the operation
        
    Raises:
        HTTPException: If the conversation cannot be deleted
    """
    try:
        logger.debug(f"Deleting conversation {conversation_id}")
        delete_conversation(profile, conversation_id)
        logger.info(f"Successfully deleted conversation {conversation_id}")
        return {"status": "History deleted successfully"}

    except Exception as e:
        logger.error(f"Failed to delete conversation {conversation_id}: {str(e)}")
