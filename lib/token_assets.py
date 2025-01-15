import json
from backend.factory import backend
from dataclasses import dataclass
from lib.images import generate_token_image
from lib.logger import configure_logger
from typing import Dict, Optional

logger = configure_logger(__name__)


class TokenAssetError(Exception):
    """Base exception for token asset operations"""

    pass


class ImageGenerationError(TokenAssetError):
    """Raised when image generation fails"""

    pass


class StorageError(TokenAssetError):
    """Raised when file storage operations fail"""

    pass


@dataclass
class TokenMetadata:
    name: str
    symbol: str
    description: str
    decimals: int
    max_supply: str
    image_url: Optional[str] = None
    uri: Optional[str] = None


class TokenAssetManager:
    # Default configuration
    DEFAULT_EXTERNAL_URL = "https://aibtc.dev/"
    DEFAULT_SIP_VERSION = 10

    def __init__(self, token_id: str):
        self.token_id = token_id

    def generate_and_store_image(self, metadata: TokenMetadata) -> str:
        """Generate and store token image, return public URL

        Raises:
            ImageGenerationError: If image generation fails
            StorageError: If image storage fails
        """
        try:
            image_bytes = generate_token_image(
                name=metadata.name,
                symbol=metadata.symbol,
                description=metadata.description,
            )

            if not isinstance(image_bytes, bytes):
                raise ImageGenerationError(
                    f"Invalid image data type for token {self.token_id}: got {type(image_bytes)}"
                )

            return backend.upload_file(f"{self.token_id}.png", image_bytes)

        except Exception as e:
            if isinstance(e, ImageGenerationError):
                raise  # Re-raise ImageGenerationError as is
            elif isinstance(e, StorageError):
                raise  # Re-raise StorageError as is
            else:
                raise StorageError(
                    f"Failed to store image for token {self.token_id}: {str(e)}"
                ) from e

    def generate_and_store_metadata(self, metadata: TokenMetadata) -> str:
        """Generate and store token metadata JSON, return public URL

        Raises:
            StorageError: If metadata storage fails
        """
        json_data = {
            "sip": self.DEFAULT_SIP_VERSION,
            "name": metadata.name,
            "description": metadata.description,
            "image": metadata.image_url,
            "properties": {
                "decimals": metadata.decimals,
                "external_url": self.DEFAULT_EXTERNAL_URL,
            },
        }

        try:
            return backend.upload_file(
                f"{self.token_id}.json", json.dumps(json_data).encode("utf-8")
            )
        except Exception as e:
            raise StorageError(
                f"Failed to store metadata for token {self.token_id}: {str(e)}"
            ) from e

    def generate_all_assets(self, metadata: TokenMetadata) -> Dict[str, str]:
        """Generate and store all token assets, return URLs

        Raises:
            TokenAssetError: If any asset generation or storage operation fails
        """
        try:
            logger.debug(f"Generating assets for token {self.token_id}")

            # Generate and store image first
            image_url = self.generate_and_store_image(metadata)
            metadata.image_url = image_url
            logger.debug(f"Generated image URL: {image_url}")

            # Generate and store metadata
            metadata_url = self.generate_and_store_metadata(metadata)
            logger.debug(f"Generated metadata URL: {metadata_url}")

            return {"image_url": image_url, "metadata_url": metadata_url}
        except Exception as e:
            logger.error(
                f"Failed to generate assets for token {self.token_id}: {str(e)}"
            )
            raise TokenAssetError(
                f"Asset generation failed for token {self.token_id}"
            ) from e
