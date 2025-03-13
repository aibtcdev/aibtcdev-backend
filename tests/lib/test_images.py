from unittest.mock import Mock, patch

import pytest

from lib.images import ImageGenerationError, generate_image, generate_token_image
from lib.logger import configure_logger

logger = configure_logger(__name__)


@pytest.fixture
def mock_openai_response() -> Mock:
    """Fixture providing a mock OpenAI response."""
    mock_data = Mock()
    mock_data.url = "https://fake-image-url.com/image.png"
    mock_response = Mock()
    mock_response.data = [mock_data]
    return mock_response


@pytest.fixture
def mock_requests_response() -> Mock:
    """Fixture providing a mock requests response."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b"fake-image-content"
    return mock_response


def test_generate_image_success(mock_openai_response: Mock) -> None:
    """Test successful image generation."""
    with patch("openai.OpenAI") as mock_client:
        mock_instance = Mock()
        mock_instance.images.generate.return_value = mock_openai_response
        mock_client.return_value = mock_instance

        result = generate_image("test prompt")
        assert result == "https://fake-image-url.com/image.png"

        mock_instance.images.generate.assert_called_once_with(
            model="dall-e-3", quality="hd", prompt="test prompt", n=1, size="1024x1024"
        )


def test_generate_image_no_response() -> None:
    """Test image generation with no response."""
    with patch("openai.OpenAI") as mock_client:
        mock_instance = Mock()
        mock_instance.images.generate.return_value = Mock(data=[])
        mock_client.return_value = mock_instance

        with pytest.raises(
            ImageGenerationError, match="No response from image generation service"
        ):
            generate_image("test prompt")


def test_generate_image_api_error() -> None:
    """Test image generation with API error."""
    with patch("openai.OpenAI") as mock_client:
        mock_instance = Mock()
        mock_instance.images.generate.side_effect = Exception("API Error")
        mock_client.return_value = mock_instance

        with pytest.raises(
            ImageGenerationError, match="Failed to generate image: API Error"
        ):
            generate_image("test prompt")


def test_generate_token_image_success(
    mock_openai_response: Mock, mock_requests_response: Mock
) -> None:
    """Test successful token image generation."""
    with patch("openai.OpenAI") as mock_client, patch("requests.get") as mock_get:
        mock_instance = Mock()
        mock_instance.images.generate.return_value = mock_openai_response
        mock_client.return_value = mock_instance
        mock_get.return_value = mock_requests_response

        result = generate_token_image("Test Token", "TT", "A test token")
        assert result == b"fake-image-content"


def test_generate_token_image_download_error(mock_openai_response: Mock) -> None:
    """Test token image generation with download error."""
    with patch("openai.OpenAI") as mock_client, patch("requests.get") as mock_get:
        mock_instance = Mock()
        mock_instance.images.generate.return_value = mock_openai_response
        mock_client.return_value = mock_instance

        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        with pytest.raises(
            ImageGenerationError, match="Failed to download image: HTTP 404"
        ):
            generate_token_image("Test Token", "TT", "A test token")


def test_generate_token_image_empty_content(mock_openai_response: Mock) -> None:
    """Test token image generation with empty content."""
    with patch("openai.OpenAI") as mock_client, patch("requests.get") as mock_get:
        mock_instance = Mock()
        mock_instance.images.generate.return_value = mock_openai_response
        mock_client.return_value = mock_instance

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b""
        mock_get.return_value = mock_response

        with pytest.raises(ImageGenerationError, match="Downloaded image is empty"):
            generate_token_image("Test Token", "TT", "A test token")


def test_generate_token_image_unexpected_error(mock_openai_response: Mock) -> None:
    """Test token image generation with unexpected error."""
    with patch("openai.OpenAI") as mock_client, patch("requests.get") as mock_get:
        mock_instance = Mock()
        mock_instance.images.generate.return_value = mock_openai_response
        mock_client.return_value = mock_instance

        mock_get.side_effect = Exception("Unexpected error")

        with pytest.raises(
            ImageGenerationError, match="Unexpected error generating token image"
        ):
            generate_token_image("Test Token", "TT", "A test token")
