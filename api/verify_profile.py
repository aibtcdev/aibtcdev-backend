from backend.factory import backend
from backend.models import Profile, ProfileFilter
from fastapi import Header, HTTPException, Query
from lib.logger import configure_logger

# Configure module logger
logger = configure_logger(__name__)


async def verify_profile(authorization: str = Header(...)) -> Profile:
    """
    Get and verify the account_index from the profile of the requesting user.

    Args:
        authorization (str): Bearer token from request header

    Returns:
        Profile: Object containing account_index and user ID

    Raises:
        HTTPException: For various authentication and profile retrieval failures
    """
    # Validate authorization header
    if not authorization or not authorization.startswith("Bearer "):
        logger.debug("Authorization header is missing or invalid")
        raise HTTPException(
            status_code=401, detail="Missing or invalid authorization header"
        )

    try:
        token = authorization.split(" ")[1]
        logger.debug("Processing authorization token")

        identifier = backend.verify_session_token(token)
        profile_response = backend.list_profiles(ProfileFilter(email=identifier))
        if not profile_response:
            logger.debug("Profile not found in database")
            raise HTTPException(status_code=404, detail="Profile not found")

        profile = profile_response[0]
        account_index = profile.account_index
        id = profile.id

        if account_index is None:
            logger.debug("Account index missing from profile")
            raise HTTPException(
                status_code=400, detail="No account index found for profile"
            )

        logger.debug(
            f"Successfully verified profile with account_index: {account_index}"
        )
        return profile

    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"Profile verification failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=401, detail="Authorization failed")


async def verify_profile_from_token(
    token: str = Query(..., description="Bearer token for authentication")
) -> Profile:
    """
    Get and verify the account_index from the profile of the requesting user using a token query parameter.

    Args:
        token (str): Bearer token from query parameter

    Returns:
        Profile: Object containing account_index and user ID

    Raises:
        HTTPException: For various authentication and profile retrieval failures
    """
    if not token:
        logger.debug("Token query parameter is missing")
        raise HTTPException(status_code=401, detail="Missing token parameter")

    try:
        identifier = backend.verify_session_token(token)
        profile_response = backend.list_profiles(ProfileFilter(email=identifier))
        if not profile_response:
            logger.debug("Profile not found in database")
            raise HTTPException(status_code=404, detail="Profile not found")

        profile = profile_response[0]
        account_index = profile.account_index

        if account_index is None:
            logger.debug("Account index missing from profile")
            raise HTTPException(
                status_code=400, detail="No account index found for profile"
            )

        logger.debug(
            f"Successfully verified profile with account_index: {account_index}"
        )
        return profile

    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"Profile verification failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=401, detail="Authorization failed")
