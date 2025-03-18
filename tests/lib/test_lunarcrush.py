from unittest.mock import Mock, patch

import pytest
import requests

from lib.logger import configure_logger
from lib.lunarcrush import LunarCrushApi

logger = configure_logger(__name__)


@pytest.fixture
def mock_response() -> Mock:
    """Fixture providing a mock response."""
    mock = Mock()
    mock.status_code = 200
    mock.json.return_value = {"data": {"test": "value"}}
    return mock


@pytest.fixture
def api() -> LunarCrushApi:
    """Fixture providing a LunarCrushApi instance."""
    return LunarCrushApi()


def test_get_success(api: LunarCrushApi, mock_response: Mock) -> None:
    """Test successful GET request."""
    with patch("requests.get") as mock_get:
        mock_get.return_value = mock_response

        result = api._get("/test-endpoint")
        assert result == {"data": {"test": "value"}}

        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert args[0] == "https://lunarcrush.com/api/v2/test-endpoint"
        assert kwargs["headers"]["Authorization"] == f"Bearer {api.api_key}"


def test_get_with_params(api: LunarCrushApi, mock_response: Mock) -> None:
    """Test GET request with parameters."""
    with patch("requests.get") as mock_get:
        mock_get.return_value = mock_response

        params = {"key": "value"}
        api._get("/test-endpoint", params=params)

        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert kwargs["params"] == params


def test_get_error(api: LunarCrushApi) -> None:
    """Test GET request with error."""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = Exception("API Error")

        with pytest.raises(
            Exception, match="Lunarcrush API GET request error: API Error"
        ):
            api._get("/test-endpoint")


def test_get_token_socials(api: LunarCrushApi, mock_response: Mock) -> None:
    """Test getting token socials."""
    with patch("requests.get") as mock_get:
        mock_get.return_value = mock_response

        result = api.get_token_socials("0x123")
        assert result == {"test": "value"}

        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert args[0] == "https://lunarcrush.com/api/v2/coins/0x123/v1"


def test_get_token_metadata(api: LunarCrushApi, mock_response: Mock) -> None:
    """Test getting token metadata."""
    with patch("requests.get") as mock_get:
        mock_get.return_value = mock_response

        result = api.get_token_metadata("0x123")
        assert result == {"test": "value"}

        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert args[0] == "https://lunarcrush.com/api/v2/coins/0x123/meta/v1"


def test_get_token_social_history(api: LunarCrushApi, mock_response: Mock) -> None:
    """Test getting token social history."""
    with patch("requests.get") as mock_get:
        mock_get.return_value = mock_response

        result = api.get_token_social_history("0x123")
        assert result == {"data": {"test": "value"}}

        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert args[0] == "https://lunarcrush.com/api/v2/coins/0x123/time-series/v1"


def test_search(api: LunarCrushApi, mock_response: Mock) -> None:
    """Test search functionality."""
    with patch("requests.get") as mock_get:
        mock_get.return_value = mock_response

        result = api.search("test_term")
        assert result == {"data": {"test": "value"}}

        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert args[0] == "https://lunarcrush.com/api/v2/searches/search"
        assert kwargs["params"] == {"term": "test_term"}


def test_http_error(api: LunarCrushApi) -> None:
    """Test handling of HTTP errors."""
    with patch("requests.get") as mock_get:
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "404 Client Error"
        )
        mock_get.return_value = mock_response

        with pytest.raises(
            Exception, match="Lunarcrush API GET request error: 404 Client Error"
        ):
            api._get("/test-endpoint")


def test_connection_error(api: LunarCrushApi) -> None:
    """Test handling of connection errors."""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

        with pytest.raises(
            Exception, match="Lunarcrush API GET request error: Connection refused"
        ):
            api._get("/test-endpoint")
