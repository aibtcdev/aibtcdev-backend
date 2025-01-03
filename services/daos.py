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
        # Create token record first to get the ID
        new_token = backend.create_token(
            TokenCreate(
                name=name,
                symbol=symbol,
                description=description,
                decimals=decimals,
                max_supply=max_supply,
            )
        )
        
        # Create metadata object
        metadata = TokenMetadata(
            name=name,
            symbol=symbol,
            description=description,
            decimals=decimals,
            max_supply=max_supply,
        )

        # Create asset manager instance with token ID
        asset_manager = TokenAssetManager(new_token.id)
        
        # Generate and upload assets
        try:
            assets = asset_manager.generate_all_assets(metadata)
            
            # Update token with asset URLs
            token_updates = TokenBase(
                uri=assets["metadata_url"],
                image_url=assets["image_url"]
            )
            if not backend.update_token(new_token.id, token_updates):
                raise TokenServiceError(
                    "Failed to update token with asset URLs",
                    {"token_id": new_token.id, "assets": assets}
                )

            # Return metadata URL and token record as dict
            token_dict = new_token.model_dump()
            return assets["metadata_url"], {
                **token_dict,
                "uri": assets["metadata_url"],
                "image_url": assets["image_url"]
            }

        except TokenAssetError as e:
            raise TokenServiceError(
                f"Failed to generate token assets: {str(e)}",
                {
                    "token_id": new_token.id,
                    "original_error": str(e),
                    "token_data": new_token.model_dump()
                }
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
