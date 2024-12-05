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
    add_job,
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
router = APIRouter(prefix="/bot")

class TestMessageResponse(BaseModel):
    """Response model for test message endpoint."""
    success: bool
    message: str


@router.post("/telegram/test", response_model=TestMessageResponse)
async def test_telegram_message(
    message: str = Body(default="Test message from API", embed=True),
    profile: ProfileInfo = Depends(verify_profile),
) -> TestMessageResponse:
    """Send a test message to the logged-in user via Telegram bot.
    
    Args:
        message (str): The message to send
        profile (ProfileInfo): The user's profile information
        
    Returns:
        JSONResponse: A JSON response with the result of the operation
        
    Raises:
        HTTPException: If the test message cannot be sent
    """
    try:
        success = await send_message_to_user(profile.id, message)
        if success:
            return TestMessageResponse(success=True, message="Test message sent successfully")
        else:
            return TestMessageResponse(success=False, message="Failed to send message. Make sure your Telegram account is registered.")
    except Exception as e:
        logger.error(f"Error sending test telegram message: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while sending telegram message",
        )
