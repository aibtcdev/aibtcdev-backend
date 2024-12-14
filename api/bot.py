from fastapi import APIRouter, Body, HTTPException, Depends
from pydantic import BaseModel
from api.verify_profile import ProfileInfo, verify_profile
from lib.logger import configure_logger
from services.bot import send_message_to_user

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
