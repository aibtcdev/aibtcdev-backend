import json
from typing import Dict
from unittest.mock import Mock, patch

import pytest

from lib.logger import configure_logger
from lib.token_assets import (
    ImageGenerationError,
    StorageError,
    TokenAssetError,
    TokenAssetManager,
    TokenMetadata,
)

logger = configure_logger(__name__)


@pytest.fixture
def token_metadata() -> TokenMetadata:
    """Fixture providing sample token metadata."""
    return TokenMetadata(
        name="Test Token",
        symbol="TEST",
        description="A test token for unit testing",
        decimals=8,
        max_supply="21000000",
    )


@pytest.fixture
def token_manager() -> TokenAssetManager:
    """Fixture providing a TokenAssetManager instance."""
    return TokenAssetManager("test-token-123")


@pytest.fixture
def mock_image_bytes() -> bytes:
    """Fixture providing mock image bytes."""
    return b"fake-image-data"


def test_token_metadata_initialization(token_metadata: TokenMetadata) -> None:
    """Test TokenMetadata initialization."""
    assert token_metadata.name == "Test Token"
    assert token_metadata.symbol == "TEST"
    assert token_metadata.description == "A test token for unit testing"
    assert token_metadata.decimals == 8
    assert token_metadata.max_supply == "21000000"
    assert token_metadata.image_url is None
    assert token_metadata.uri is None


def test_token_asset_manager_initialization(token_manager: TokenAssetManager) -> None:
    """Test TokenAssetManager initialization."""
    assert token_manager.token_id == "test-token-123"
    assert token_manager.DEFAULT_EXTERNAL_URL == "https://aibtc.dev/"
    assert token_manager.DEFAULT_SIP_VERSION == 10


@patch("lib.images.generate_token_image")
@patch("backend.factory.backend.upload_file")
def test_generate_and_store_image_success(
    mock_upload: Mock,
    mock_generate: Mock,
    token_manager: TokenAssetManager,
    token_metadata: TokenMetadata,
    mock_image_bytes: bytes,
) -> None:
    """Test successful image generation and storage."""
    mock_generate.return_value = mock_image_bytes
    mock_upload.return_value = "https://example.com/image.png"

    result = token_manager.generate_and_store_image(token_metadata)

    assert result == "https://example.com/image.png"
    mock_generate.assert_called_once_with(
        name=token_metadata.name,
        symbol=token_metadata.symbol,
        description=token_metadata.description,
    )
    mock_upload.assert_called_once_with("test-token-123.png", mock_image_bytes)


@patch("lib.images.generate_token_image")
def test_generate_and_store_image_invalid_data(
    mock_generate: Mock,
    token_manager: TokenAssetManager,
    token_metadata: TokenMetadata,
) -> None:
    """Test image generation with invalid data type."""
    mock_generate.return_value = "invalid-data-type"

    with pytest.raises(ImageGenerationError, match="Invalid image data type"):
        token_manager.generate_and_store_image(token_metadata)


@patch("lib.images.generate_token_image")
def test_generate_and_store_image_generation_error(
    mock_generate: Mock,
    token_manager: TokenAssetManager,
    token_metadata: TokenMetadata,
) -> None:
    """Test image generation error."""
    mock_generate.side_effect = ImageGenerationError("Generation failed")

    with pytest.raises(ImageGenerationError, match="Generation failed"):
        token_manager.generate_and_store_image(token_metadata)


@patch("lib.images.generate_token_image")
@patch("backend.factory.backend.upload_file")
def test_generate_and_store_image_storage_error(
    mock_upload: Mock,
    mock_generate: Mock,
    token_manager: TokenAssetManager,
    token_metadata: TokenMetadata,
    mock_image_bytes: bytes,
) -> None:
    """Test image storage error."""
    mock_generate.return_value = mock_image_bytes
    mock_upload.side_effect = StorageError("Storage failed")

    with pytest.raises(StorageError, match="Storage failed"):
        token_manager.generate_and_store_image(token_metadata)


@patch("backend.factory.backend.upload_file")
def test_generate_and_store_metadata_success(
    mock_upload: Mock,
    token_manager: TokenAssetManager,
    token_metadata: TokenMetadata,
) -> None:
    """Test successful metadata generation and storage."""
    token_metadata.image_url = "https://example.com/image.png"
    mock_upload.return_value = "https://example.com/metadata.json"

    result = token_manager.generate_and_store_metadata(token_metadata)

    assert result == "https://example.com/metadata.json"
    mock_upload.assert_called_once()

    # Verify JSON content
    args = mock_upload.call_args[0]
    assert args[0] == "test-token-123.json"
    json_data = json.loads(args[1].decode("utf-8"))
    assert json_data["name"] == token_metadata.name
    assert json_data["description"] == token_metadata.description
    assert json_data["image"] == token_metadata.image_url
    assert json_data["properties"]["decimals"] == token_metadata.decimals
    assert json_data["properties"]["external_url"] == token_manager.DEFAULT_EXTERNAL_URL
    assert json_data["sip"] == token_manager.DEFAULT_SIP_VERSION


@patch("backend.factory.backend.upload_file")
def test_generate_and_store_metadata_storage_error(
    mock_upload: Mock,
    token_manager: TokenAssetManager,
    token_metadata: TokenMetadata,
) -> None:
    """Test metadata storage error."""
    mock_upload.side_effect = Exception("Upload failed")

    with pytest.raises(StorageError, match="Failed to store metadata"):
        token_manager.generate_and_store_metadata(token_metadata)


@patch.object(TokenAssetManager, "generate_and_store_image")
@patch.object(TokenAssetManager, "generate_and_store_metadata")
def test_generate_all_assets_success(
    mock_metadata: Mock,
    mock_image: Mock,
    token_manager: TokenAssetManager,
    token_metadata: TokenMetadata,
) -> None:
    """Test successful generation of all assets."""
    mock_image.return_value = "https://example.com/image.png"
    mock_metadata.return_value = "https://example.com/metadata.json"

    result = token_manager.generate_all_assets(token_metadata)

    assert result == {
        "image_url": "https://example.com/image.png",
        "metadata_url": "https://example.com/metadata.json",
    }
    mock_image.assert_called_once_with(token_metadata)
    mock_metadata.assert_called_once_with(token_metadata)
    assert token_metadata.image_url == "https://example.com/image.png"


@patch.object(TokenAssetManager, "generate_and_store_image")
def test_generate_all_assets_image_error(
    mock_image: Mock,
    token_manager: TokenAssetManager,
    token_metadata: TokenMetadata,
) -> None:
    """Test asset generation with image error."""
    mock_image.side_effect = ImageGenerationError("Image generation failed")

    with pytest.raises(TokenAssetError, match="Asset generation failed"):
        token_manager.generate_all_assets(token_metadata)


@patch.object(TokenAssetManager, "generate_and_store_image")
@patch.object(TokenAssetManager, "generate_and_store_metadata")
def test_generate_all_assets_metadata_error(
    mock_metadata: Mock,
    mock_image: Mock,
    token_manager: TokenAssetManager,
    token_metadata: TokenMetadata,
) -> None:
    """Test asset generation with metadata error."""
    mock_image.return_value = "https://example.com/image.png"
    mock_metadata.side_effect = StorageError("Metadata storage failed")

    with pytest.raises(TokenAssetError, match="Asset generation failed"):
        token_manager.generate_all_assets(token_metadata)
