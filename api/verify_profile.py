from db.factory import db
from fastapi import Header, HTTPException, Query
from lib.logger import configure_logger
from lib.models import ProfileInfo

# Configure module logger
logger = configure_logger(__name__)


async def verify_profile(authorization: str = Header(...)) -> ProfileInfo:
    """
    Get and verify the account_index from the profile of the requesting user.

    Args:
        authorization (str): Bearer token from request header

    Returns:
        ProfileInfo: Object containing account_index and user ID

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
        # Extract and verify token
        token = authorization.split(" ")[1]
        logger.debug("Processing authorization token")

        identifier = db.verify_session_token(token)
        # Get user from token
        profile_response = db.get_profile(identifier)

        if not profile_response:
            logger.debug("Profile not found in database")
            raise HTTPException(status_code=404, detail="Profile not found")

        account_index = profile_response.get("account_index")
        id = profile_response.get("id")

        if account_index is None:
            logger.debug("Account index missing from profile")
            raise HTTPException(
                status_code=400, detail="No account index found for profile"
            )

        logger.debug(
            f"Successfully verified profile with account_index: {account_index}"
        )
        return ProfileInfo(account_index=account_index, id=id)

    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"Profile verification failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=401, detail="Authorization failed")


async def verify_profile_from_token(
    token: str = Query(..., description="Bearer token for authentication")
) -> ProfileInfo:
    """
    Get and verify the account_index from the profile of the requesting user using a token query parameter.

    Args:
        token (str): Bearer token from query parameter

    Returns:
        ProfileInfo: Object containing account_index and user ID

    Raises:
        HTTPException: For various authentication and profile retrieval failures
    """
    if not token:
        logger.debug("Token query parameter is missing")
        raise HTTPException(status_code=401, detail="Missing token parameter")

    try:
        # Extract and verify token
        identifier = db.verify_session_token(token)
        logger.debug(identifier)
        # Get user from token
        profile_response = db.get_profile(identifier)
        logger.debug(profile_response)
        if not profile_response:
            logger.debug("Profile not found in database")
            raise HTTPException(status_code=404, detail="Profile not found")

        account_index = profile_response.get("account_index")
        id = profile_response.get("id")

        if account_index is None:
            logger.debug("Account index missing from profile")
            raise HTTPException(
                status_code=400, detail="No account index found for profile"
            )

        logger.debug(
            f"Successfully verified profile with account_index: {account_index}"
        )
        return ProfileInfo(account_index=account_index, id=id)

    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"Profile verification failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=401, detail="Authorization failed")
