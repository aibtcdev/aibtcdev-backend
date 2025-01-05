from backend.factory import backend
from backend.models import Collective, CollectiveCreate, Token, TokenBase, TokenCreate
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


def generate_collective_dependencies(
    name: str, mission: str, description: str
) -> Collective:
    """Generate collective dependencies including database record and metadata.

    Args:
        name: Name of the collective
        mission: Mission of the collective
        description: Description of the collective
    """
    logger.debug(
        f"Creating collective with name={name}, mission={mission}, description={description}"
    )
    try:
        collective = backend.create_collective(
            CollectiveCreate(name=name, mission=mission, description=description)
        )
        logger.debug(f"Created collective type: {type(collective)}")
        logger.debug(f"Created collective content: {collective}")

        return collective
    except Exception as e:
        logger.error(f"Failed to create collective: {str(e)}", exc_info=True)
        raise


def generate_token_dependencies(
    token_name: str,
    token_symbol: str,
    token_description: str,
    token_decimals: int,
    token_max_supply: str,
) -> Tuple[str, Token]:
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
        logger.debug(
            f"Creating token with name={token_name}, symbol={token_symbol}, "
            f"description={token_description}, decimals={token_decimals}, "
            f"max_supply={token_max_supply}"
        )
        # Create initial token record
        token_create = TokenCreate(
            name=token_name,
            symbol=token_symbol,
            description=token_description,
            decimals=token_decimals,
            max_supply=token_max_supply,
        )
        logger.debug(f"TokenCreate object: {token_create}")

        new_token = backend.create_token(new_token=token_create)
        logger.debug(f"Created token type: {type(new_token)}")
        logger.debug(f"Created token content: {new_token}")

        token_id = new_token.id
        logger.debug(f"Created token record with ID: {token_id}")

        # Create metadata object
        metadata = TokenMetadata(
            name=token_name,
            symbol=token_symbol,
            description=token_description,
            decimals=token_decimals,
            max_supply=token_max_supply,
        )
        logger.debug(f"Created TokenMetadata: {metadata}")

        # Generate and store assets
        asset_manager = TokenAssetManager(token_id)
        try:
            logger.debug("Generating token assets...")
            assets = asset_manager.generate_all_assets(metadata)
            logger.debug(f"Generated assets: {assets}")

            # Update token record with asset URLs
            token_update = TokenBase(
                uri=assets["metadata_url"],
                image_url=assets["image_url"],
            )
            logger.debug(f"Updating token with: {token_update}")

            update_result = backend.update_token(
                token_id=token_id, update_data=token_update
            )
            logger.debug(f"Token update result: {update_result}")

            if not update_result:
                raise TokenUpdateError(
                    "Failed to update token record with asset URLs",
                    {"token_id": token_id, "assets": assets},
                )

            logger.debug(f"Final token data content: {update_result}")

            return assets["metadata_url"], update_result

        except TokenAssetError as e:
            logger.error(f"Failed to generate token assets: {e}", exc_info=True)
            logger.error(f"Token ID: {token_id}")
            logger.error(f"Metadata: {metadata}")
            raise

    except Exception as e:
        logger.error(f"Unexpected error during token creation: {e}", exc_info=True)
        raise TokenCreationError(
            f"Unexpected error during token creation: {str(e)}",
            {"original_error": str(e)},
        ) from e


def bind_token_to_collective(token_id: UUID, collective_id: UUID):
    """Bind a token to a collective.

    Args:
        token_id: ID of the token to bind
        collective_id: ID of the collective to bind to

    Returns:
        bool: True if binding was successful, False otherwise
    """
    logger.debug(f"Binding token {token_id} to collective {collective_id}")
    try:
        token_update = TokenBase(collective_id=collective_id)
        logger.debug(f"Token update data: {token_update}")

        result = backend.update_token(token_id=token_id, update_data=token_update)
        logger.debug(f"Bind result: {result}")
        return result
    except Exception as e:
        logger.error(f"Failed to bind token to collective: {str(e)}", exc_info=True)
        return False
