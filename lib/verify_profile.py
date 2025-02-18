import uuid
from backend.factory import backend
from backend.models import KeyFilter, Profile, ProfileFilter
from fastapi import Header, HTTPException, Query
from lib.logger import configure_logger
from typing import Optional

# Configure module logger
logger = configure_logger(__name__)


async def get_profile_from_api_key(api_key: str) -> Optional[Profile]:
    """
    Verify an API key and return the associated profile if valid.

    Args:
        api_key (str): The API key to verify

    Returns:
        Optional[Profile]: The associated profile if the key is valid, None otherwise
    """
    try:
        # Try to parse as UUID to validate format
        try:
            uuid.UUID(api_key)
        except ValueError:
            return None

        # List all enabled keys that match this key ID
        keys = backend.list_keys(KeyFilter(id=api_key, is_enabled=True))
        if not keys:
            logger.error(f"No enabled API key found")
            return None

        key = keys[0]
        if not key.profile_id:
            logger.error(f"API key has no associated profile")
            return None

        # Get the associated profile
        profile = backend.get_profile(key.profile_id)
        if not profile:
            logger.error(f"No profile found for API key")
            return None

        return profile

    except Exception as e:
        logger.error(f"Error verifying API key: {str(e)}", exc_info=True)
        return None


async def verify_profile(
    authorization: str = Header(None),
    x_api_key: str = Header(None, alias="X-API-Key"),
) -> Profile:
    """
    Verify profile from either authorization header or X-API-Key header.

    Authorization header supports Bearer token format: "Bearer <token>"
    X-API-Key header supports direct API key format
    """
    # Check for API Key authentication first
    if x_api_key:
        profile = await get_profile_from_api_key(x_api_key)
        if profile:
            return profile
        logger.error("Invalid API key")
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Fall back to Bearer token authentication
    if not authorization:
        logger.error("Authorization header is missing")
        raise HTTPException(status_code=401, detail="Missing authorization header")

    if not authorization.startswith("Bearer "):
        logger.error("Invalid authorization header format")
        raise HTTPException(
            status_code=401, detail="Invalid authorization format. Use 'Bearer <token>'"
        )

    try:
        token = authorization.split(" ")[1]
        identifier = backend.verify_session_token(token)
        if not identifier:
            logger.error("Invalid bearer token")
            raise HTTPException(status_code=401, detail="Invalid bearer token")

        profile_response = backend.list_profiles(ProfileFilter(email=identifier))
        if not profile_response:
            logger.error("Profile not found in database")
            raise HTTPException(status_code=404, detail="Profile not found")

        return profile_response[0]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Profile verification failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=401, detail="Authorization failed")


async def verify_profile_from_token(
    token: str = Query(None, description="Bearer token for authentication"),
    key: str = Query(None, description="API key for authentication"),
) -> Profile:
    """
    Get and verify the profile of the requesting user using either a token or key parameter.

    Args:
        token (str): Bearer token for authentication
        key (str): API key for authentication

    Returns:
        Profile: Object

    Raises:
        HTTPException: For various authentication and profile retrieval failures
    """
    # Check for API Key authentication first
    if key:
        profile = await get_profile_from_api_key(key)
        if profile:
            return profile
        logger.error("Invalid API key")
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Fall back to Bearer token authentication
    if not token:
        logger.error("Token parameter is missing")
        raise HTTPException(status_code=401, detail="Missing token parameter")

    try:
        identifier = backend.verify_session_token(token)
        if not identifier:
            logger.error("Invalid or expired token")
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        profile_response = backend.list_profiles(ProfileFilter(email=identifier))
        if not profile_response:
            logger.error(f"No profile found for email: {identifier}")
            raise HTTPException(
                status_code=404,
                detail=f"No profile found for the authenticated email. Please ensure your profile is properly set up.",
            )

        return profile_response[0]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Profile verification failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=401, detail="Authorization failed")
