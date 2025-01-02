from backend.factory import backend
from backend.models import CollectiveCreate, TokenBase, TokenCreate
from lib.logger import configure_logger
from lib.token_assets import TokenAssetError, TokenAssetManager, TokenMetadata
from typing import Dict, Tuple
from uuid import UUID

logger = configure_logger(__name__)


class TokenServiceError(Exception):
    """Base exception for token service operations"""

    def __init__(self, message: str, details: Dict = None):
        super().__init__(message)
        self.details = details or {}


class TokenCreationError(TokenServiceError):
    """Raised when token creation fails"""

    pass


class TokenUpdateError(TokenServiceError):
    """Raised when token update fails"""

    pass


def generate_collective_dependencies(name: str, mission: str, description: str) -> Dict:
    """Generate collective dependencies including database record and metadata.

    Args:
        name: Name of the collective
        mission: Mission of the collective
        description: Description of the collective

    Returns:
        Dict: Collective record as a dictionary
    """
    collective = backend.create_collective(
        CollectiveCreate(name=name, mission=mission, description=description)
    )
    return collective.model_dump()


def generate_token_dependencies(
    name: str,
    symbol: str,
    description: str,
    decimals: str,
    max_supply: str,
) -> Tuple[str, Dict]:
    """Generate token dependencies including database record and metadata.

    Args:
        name: Name of the token
        symbol: Symbol of the token
        description: Description of the token
        decimals: Number of decimals for the token
        max_supply: Maximum supply of the token

    Returns:
        Tuple[str, Dict]: A tuple containing the metadata URL and token record as dict

    Raises:
        TokenServiceError: If there is an error creating token dependencies
    """
    try:
        # Create token metadata
        metadata = TokenMetadata(
            name=name,
            symbol=symbol,
            description=description,
            decimals=decimals,
            max_supply=max_supply,
        )

        # Upload token assets
        assets = TokenAssetManager.upload_token_assets(metadata)

        # Create token record
        new_token = backend.create_token(
            TokenCreate(
                name=name,
                symbol=symbol,
                description=description,
                decimals=decimals,
                max_supply=max_supply,
            )
        )

        return assets["metadata_url"], new_token.model_dump()

    except TokenAssetError as e:
        raise TokenServiceError(
            f"Failed to upload token assets: {str(e)}",
            details=e.details if hasattr(e, "details") else None,
        ) from e
    except Exception as e:
        raise TokenServiceError(
            f"Failed to create token dependencies: {str(e)}"
        ) from e


def bind_token_to_collective(token_id: UUID, collective_id: UUID) -> bool:
    """Bind a token to a collective.

    Args:
        token_id: UUID of the token
        collective_id: UUID of the collective

    Returns:
        bool: True if binding was successful, False otherwise
    """
    return backend.update_token(
        token_id=token_id, update_data=TokenBase(collective_id=collective_id)
    )
