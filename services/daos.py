from db.factory import db
from lib.logger import configure_logger
from lib.token_assets import TokenAssetError, TokenAssetManager, TokenMetadata
from typing import Dict, Tuple

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
    """

    return db.add_collective(name, mission, description)


def generate_token_dependencies(
    token_name: str,
    token_symbol: str,
    token_description: str,
    token_decimals: int,
    token_max_supply: str,
) -> Tuple[str, Dict]:
    """Generate token dependencies including database record, image, and metadata.

    Args:
        token_name: Name of the token
        token_symbol: Symbol of the token
        token_description: Description of the token
        token_decimals: Number of decimals for the token
        token_max_supply: Maximum supply of the token

    Returns:
        Tuple[str, Dict]: Token metadata URL and token details

    Raises:
        TokenCreationError: If token record creation fails
        TokenAssetError: If asset generation fails
        TokenUpdateError: If token update fails
    """
    try:
        # Create initial token record
        new_token = db.add_token(
            name=token_name,
            symbol=token_symbol,
            description=token_description,
            decimals=token_decimals,
            max_supply=token_max_supply,
        )
        token_id = new_token["id"]
        logger.debug(f"Created token record with ID: {token_id}")

        # Create metadata object
        metadata = TokenMetadata(
            name=token_name,
            symbol=token_symbol,
            description=token_description,
            decimals=token_decimals,
            max_supply=token_max_supply,
        )

        # Generate and store assets
        asset_manager = TokenAssetManager(token_id)
        try:
            assets = asset_manager.generate_all_assets(metadata)

            # Update token record with asset URLs
            if not db.update_token(
                token_id,
                {"uri": assets["metadata_url"], "image_url": assets["image_url"]},
            ):
                raise TokenUpdateError(
                    "Failed to update token record with asset URLs",
                    {"token_id": token_id, "assets": assets},
                )

            ## there is no update method to the new_token object need to merge dictionary
            metadata.uri = assets["metadata_url"]
            metadata.image_url = assets["image_url"]
            final_token = {
                **new_token,
                "uri": assets["metadata_url"],
                "image_url": assets["image_url"],
            }

            return assets["metadata_url"], final_token

        except TokenAssetError as e:
            raise TokenCreationError(
                f"Failed to generate token assets: {str(e)}",
                {
                    "token_id": token_id,
                    "original_error": str(e),
                    "token_data": new_token,
                },
            ) from e

    except Exception as e:
        raise TokenCreationError(
            f"Unexpected error during token creation: {str(e)}",
            {"original_error": str(e)},
        ) from e


def bind_token_to_collective(token_id: str, collective_id: str):
    return db.update_token(token_id, {"collective_id": collective_id})
