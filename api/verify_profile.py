from fastapi import Header, HTTPException, Query
from db.helpers import get_user_from_token, get_profile_by_email
from lib.logger import configure_logger
from cachetools import TTLCache
from lib.models import ProfileInfo

# Configure module logger
logger = configure_logger(__name__)

# Cache for profile data (5 minutes TTL)
cache = TTLCache(maxsize=100, ttl=300)

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
        
        # Get user from token
        user = get_user_from_token(token)
        email = user.user.email
        
        # Check cache first
        if email in cache:
            logger.debug(f"Cache hit for email: {email}")
            account_index = cache[email]
        else:
            logger.debug(f"Cache miss for email: {email}")
            # Fetch profile from database
            profile_response = get_profile_by_email(email)

            if not profile_response.data:
                logger.debug("Profile not found in database")
                raise HTTPException(status_code=404, detail="Profile not found")

            account_index = profile_response.data.get("account_index")
            if account_index is None:
                logger.debug("Account index missing from profile")
                raise HTTPException(
                    status_code=400, detail="No account index found for profile"
                )

            # Update cache
            cache[email] = account_index
            logger.debug(f"Cached account_index for email: {email}")

        logger.debug(f"Successfully verified profile with account_index: {account_index}")
        return ProfileInfo(account_index=account_index, id=user.user.id)

    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"Profile verification failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=401, detail="Authorization failed")


async def verify_profile_from_token(token: str = Query(..., description="Bearer token for authentication")) -> ProfileInfo:
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
        raise HTTPException(
            status_code=401, detail="Missing token parameter"
        )

    try:
        # Get user from token
        logger.debug("Processing token from query parameter")
        user = get_user_from_token(token)
        email = user.user.email
        
        # Check cache first
        if email in cache:
            logger.debug(f"Cache hit for email: {email}")
            account_index = cache[email]
        else:
            logger.debug(f"Cache miss for email: {email}")
            # Fetch profile from database
            profile_response = get_profile_by_email(email)

            if not profile_response.data:
                logger.debug("Profile not found in database")
                raise HTTPException(status_code=404, detail="Profile not found")

            account_index = profile_response.data.get("account_index")
            if account_index is None:
                logger.debug("Account index missing from profile")
                raise HTTPException(
                    status_code=400, detail="No account index found for profile"
                )

            # Update cache
            cache[email] = account_index
            logger.debug(f"Cached account_index for email: {email}")

        logger.debug(f"Successfully verified profile with account_index: {account_index}")
        return ProfileInfo(account_index=account_index, id=user.user.id)

    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"Profile verification failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=401, detail="Authorization failed")
