import uuid
from typing import Optional

from fastapi import Header, HTTPException, Query

from app.backend.factory import backend
from app.backend.models import KeyFilter, Profile, ProfileFilter
from app.config import config
from app.lib.logger import configure_logger

# Configure logger
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
        keys = backend.list_keys(KeyFilter(id=uuid.UUID(api_key), is_enabled=True))
        if not keys:
            logger.error("No enabled API key found")
            return None

        key = keys[0]
        if not key.profile_id:
            logger.error("API key has no associated profile")
            return None

        # Get the associated profile
        profile = backend.get_profile(key.profile_id)
        if not profile:
            logger.error("No profile found for API key")
            return None

        return profile

    except Exception as e:
        logger.error(f"Error verifying API key: {str(e)}", exc_info=True)
        return None


async def verify_profile(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Profile:
    """
    Verify profile from either authorization header or X-API-Key header.

    Authorization header supports Bearer token format: "Bearer <token>"
    X-API-Key header supports direct API key format

    Args:
        authorization: The Authorization header value
        x_api_key: The X-API-Key header value

    Returns:
        Profile: The verified user profile

    Raises:
        HTTPException: If authentication fails
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
    token: Optional[str] = Query(None, description="Bearer token for authentication"),
    key: Optional[str] = Query(None, description="API key for authentication"),
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
                detail="No profile found for the authenticated email. Please ensure your profile is properly set up.",
            )

        return profile_response[0]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Profile verification failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=401, detail="Authorization failed")


async def verify_webhook_auth(authorization: Optional[str] = Header(None)) -> None:
    """
    Verify webhook authentication using Bearer token.

    Args:
        authorization: The Authorization header value

    Raises:
        HTTPException: If authentication fails
    """
    if not authorization:
        logger.error("Missing Authorization header for webhook")
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    if not authorization.startswith("Bearer "):
        logger.error("Invalid Authorization header format for webhook")
        raise HTTPException(
            status_code=401, detail="Invalid Authorization format. Use 'Bearer <token>'"
        )

    token = authorization.split(" ")[1]
    expected_token = (
        config.api.webhook_auth.split(" ")[1]
        if config.api.webhook_auth.startswith("Bearer ")
        else config.api.webhook_auth
    )

    if token != expected_token:
        logger.error("Invalid webhook authentication token")
        raise HTTPException(status_code=401, detail="Invalid authentication token")


async def verify_faktory_access_token(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> None:
    """
    Verify the static API key for the agent lookup endpoint.

    Args:
        x_api_key: The X-API-Key header value

    Raises:
        HTTPException: If authentication fails
    """
    if not x_api_key:
        logger.error("Missing X-API-Key header for agent lookup")
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    if x_api_key != config.api.faktory_access_token:
        logger.error("Invalid agent lookup API key")
        raise HTTPException(status_code=401, detail="Invalid API key")
