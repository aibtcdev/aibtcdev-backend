from lib.models import ProfileResponse, VerificationResponse
from typing import Dict

# =============================================================================
# Profile Operations
# =============================================================================


def verify_session_token(token: str) -> VerificationResponse:
    """Validate if a token is valid and belongs to a user.

    Args:
        token (str): Authentication token

    Returns:
        dict: Dictionary containing 'valid' and 'message' keys
    """
    return services_client.auth.verify_session_token(token)


def get_profile_by_address(address: str) -> ProfileResponse:
    """Get profile information by address.

    Args:
        address (str): User's address

    Returns:
        Dict: Profile data including account_index
    """
    return services_client.database.get_user_profile(address)
