from dataclasses import dataclass
from typing import Dict, Tuple
from uuid import UUID

from backend.factory import backend
from backend.models import DAO, DAOCreate, Token, TokenBase, TokenCreate
from lib.logger import configure_logger
from lib.token_assets import TokenAssetError, TokenAssetManager, TokenMetadata

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


@dataclass
class DAORequest:
    """Data class for DAO creation request"""

    name: str
    mission: str
    description: str
    wallet_id: UUID

    def to_dao_create(self) -> DAOCreate:
        """Convert to DAOCreate model"""
        return DAOCreate(
            name=self.name,
            mission=self.mission,
            description=self.description,
            wallet_id=self.wallet_id,
        )


@dataclass
class TokenRequest:
    """Data class for token creation request"""

    name: str
    symbol: str
    description: str
    decimals: int
    max_supply: str

    def to_token_create(self) -> TokenCreate:
        """Convert to TokenCreate model"""
        return TokenCreate(
            name=self.name,
            symbol=self.symbol,
            description=self.description,
            decimals=self.decimals,
            max_supply=self.max_supply,
            status="DRAFT",
        )

    def to_token_metadata(self) -> TokenMetadata:
        """Convert to TokenMetadata"""
        return TokenMetadata(
            name=self.name,
            symbol=self.symbol,
            description=self.description,
            decimals=self.decimals,
            max_supply=self.max_supply,
        )


class DAOService:
    """Service class for DAO-related operations"""

    @staticmethod
    def create_dao(request: DAORequest) -> DAO:
        """Create a new DAO with the given parameters

        Args:
            request: The DAO creation request

        Returns:
            DAO: The created DAO record

        Raises:
            TokenServiceError: If DAO creation fails
        """
        logger.debug(f"Creating dao with request: {request}")
        try:
            dao = backend.create_dao(request.to_dao_create())
            logger.debug(f"Created dao: {dao}")
            return dao
        except Exception as e:
            logger.error(f"Failed to create dao: {str(e)}", exc_info=True)
            raise TokenServiceError(f"Failed to create dao: {str(e)}")


class TokenService:
    """Service class for token-related operations"""

    def __init__(self):
        self.backend = backend

    def create_token(self, request: TokenRequest) -> Tuple[str, Token]:
        """Create a new token with the given parameters

        Args:
            request: The token creation request

        Returns:
            Tuple[str, Token]: Token metadata URL and token details

        Raises:
            TokenCreationError: If token creation fails
            TokenAssetError: If asset generation fails
            TokenUpdateError: If token update fails
        """
        logger.debug(f"Creating token with request: {request}")
        try:
            # Create initial token record
            new_token = self.backend.create_token(request.to_token_create())
            logger.debug(f"Created initial token: {new_token}")

            # Generate and store assets
            asset_manager = TokenAssetManager(new_token.id)
            metadata = request.to_token_metadata()

            logger.debug("Generating token assets...")
            assets = asset_manager.generate_all_assets(metadata)
            logger.debug(f"Generated assets: {assets}")

            # Update token record with asset URLs
            token_update = TokenBase(
                uri=assets["metadata_url"],
                image_url=assets["image_url"],
            )
            logger.debug(f"Updating token with: {token_update}")

            update_result = self.backend.update_token(
                token_id=new_token.id, update_data=token_update
            )

            if not update_result:
                raise TokenUpdateError(
                    "Failed to update token record with asset URLs",
                    {"token_id": new_token.id, "assets": assets},
                )

            logger.debug(f"Final token data: {update_result}")
            return assets["metadata_url"], update_result

        except TokenAssetError:
            logger.error("Failed to generate token assets", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error during token creation: {e}", exc_info=True)
            raise TokenCreationError(
                f"Unexpected error during token creation: {str(e)}",
                {"original_error": str(e)},
            ) from e

    def bind_token_to_dao(self, token_id: UUID, dao_id: UUID) -> bool:
        """Bind a token to a DAO

        Args:
            token_id: ID of the token to bind
            dao_id: ID of the DAO to bind to

        Returns:
            bool: True if binding was successful, False otherwise
        """
        logger.debug(f"Binding token {token_id} to DAO {dao_id}")
        try:
            token_update = TokenBase(dao_id=dao_id)
            logger.debug(f"Token update data: {token_update}")

            result = self.backend.update_token(
                token_id=token_id, update_data=token_update
            )
            logger.debug(f"Bind result: {result}")
            return result
        except Exception as e:
            logger.error(f"Failed to bind token to DAO: {str(e)}", exc_info=True)
            return False


# Facade functions for backward compatibility
def generate_dao_dependencies(
    name: str, mission: str, description: str, wallet_id: UUID
) -> DAO:
    """Generate dao dependencies including database record and metadata."""
    request = DAORequest(
        name=name, mission=mission, description=description, wallet_id=wallet_id
    )
    return DAOService.create_dao(request)


def generate_token_dependencies(
    token_name: str,
    token_symbol: str,
    token_description: str,
    token_decimals: int,
    token_max_supply: str,
) -> Tuple[str, Token]:
    """Generate token dependencies including database record, image, and metadata."""
    request = TokenRequest(
        name=token_name,
        symbol=token_symbol,
        description=token_description,
        decimals=token_decimals,
        max_supply=token_max_supply,
    )
    return TokenService().create_token(request)


def bind_token_to_dao(token_id: UUID, dao_id: UUID) -> bool:
    """Bind a token to a DAO."""
    return TokenService().bind_token_to_dao(token_id, dao_id)
