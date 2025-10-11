"""Authentication and OAuth handlers for the application."""

from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.lib.logger import configure_logger
from app.services.processing.twitter_data_service import twitter_data_service

logger = configure_logger(__name__)

router = APIRouter()


class XOAuthData(BaseModel):
    """X OAuth data from Supabase Auth."""

    user_id: str
    provider_id: str
    username: str
    email: Optional[str] = None
    name: Optional[str] = None


async def handle_x_oauth_completion(oauth_data: XOAuthData) -> Dict[str, Any]:
    """
    Handle X OAuth completion and sync user data.
    Called automatically after user links their Twitter account.

    Args:
        oauth_data: OAuth data containing user information

    Returns:
        Dictionary with sync results
    """
    try:
        logger.info(f"Processing X OAuth completion for user {oauth_data.user_id}")

        # Extract data from OAuth response
        provider_id = oauth_data.provider_id  # X user ID
        username = oauth_data.username  # X username

        if not username or not provider_id:
            logger.error("Missing username or provider_id in OAuth data")
            raise HTTPException(
                status_code=400, detail="Missing username or provider_id in OAuth data"
            )

        # Automatically sync user data after OAuth link
        user_db_id = await twitter_data_service.sync_user_after_oauth_link(
            username=username,
            provider_id=provider_id,
            supabase_user_id=oauth_data.user_id,
        )

        if user_db_id:
            logger.info(f"Successfully synced X user {username} after OAuth link")
            return {
                "success": True,
                "user_id": str(user_db_id),
                "username": username,
                "message": f"Successfully linked X account @{username}",
            }
        else:
            logger.error(f"Failed to sync X user {username} after OAuth link")
            raise HTTPException(
                status_code=500, detail=f"Failed to sync X user {username}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in X OAuth completion: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error processing X OAuth: {str(e)}"
        )


@router.post("/x-oauth-complete")
async def x_oauth_complete(oauth_data: XOAuthData):
    """
    Endpoint for X OAuth completion.
    This endpoint should be called after successful X OAuth flow.
    """
    return await handle_x_oauth_completion(oauth_data)


@router.post("/link-x-account")
async def link_x_account(user_id: str, username: str, provider_id: str):
    """
    Manually link X account to user profile.
    Alternative endpoint for manual X account linking.
    """
    oauth_data = XOAuthData(user_id=user_id, provider_id=provider_id, username=username)
    return await handle_x_oauth_completion(oauth_data)


@router.get("/x-user-status/{user_id}")
async def get_x_user_status(user_id: str):
    """
    Check if user has linked X account and get their X user data.
    """
    try:
        from app.backend.factory import backend
        from app.backend.models import XUserFilter

        # Check if user has X account linked
        x_users = backend.list_x_users(XUserFilter(supabase_user_id=user_id))

        if x_users:
            user = x_users[0]
            return {
                "linked": True,
                "username": user.username,
                "name": user.name,
                "verified": user.verified,
                "profile_image_url": user.profile_image_url,
                "bitcoin_face_score": user.bitcoin_face_score,
            }
        else:
            return {"linked": False, "message": "No X account linked"}

    except Exception as e:
        logger.error(f"Error checking X user status: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error checking X user status: {str(e)}"
        )
