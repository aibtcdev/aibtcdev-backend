import aiohttp
import pytest
import requests
import time
from lib.hiro import HiroApi, HiroApiError, HiroApiRateLimitError, HiroApiTimeoutError
from lib.logger import configure_logger
from typing import Any, Dict, List
from unittest.mock import Mock, patch

logger = configure_logger(__name__)


@pytest.fixture
def mock_config() -> None:
    """Fixture to mock config values."""
    with patch("config.config") as mock_config:
        mock_config.api.hiro_api_url = "https://test-hiro-api.com/"
        yield


@pytest.fixture
def hiro_api(mock_config: None) -> HiroApi:
    """Fixture providing a HiroApi instance."""
    return HiroApi()


@pytest.fixture
def mock_response() -> Mock:
    """Fixture providing a mock response."""
    mock = Mock()
    mock.status_code = 200
    mock.json.return_value = {"data": "test_value"}
    return mock


def test_initialization(hiro_api: HiroApi) -> None:
    """Test HiroApi initialization."""
    assert hiro_api.base_url == "https://test-hiro-api.com/"
    assert len(hiro_api._request_times) == 0
    assert hiro_api._cache is not None
    assert hiro_api._session is None


def test_rate_limit(hiro_api: HiroApi) -> None:
    """Test rate limiting functionality."""
    # Fill up the request times
    current_time = time.time()
    hiro_api._request_times = [current_time] * (hiro_api.RATE_LIMIT - 1)

    # This request should not trigger rate limiting
    hiro_api._rate_limit()
    assert len(hiro_api._request_times) == hiro_api.RATE_LIMIT

    # This request should trigger rate limiting
    with patch("time.sleep") as mock_sleep:
        hiro_api._rate_limit()
        mock_sleep.assert_called_once()


@patch("requests.get")
def test_get_success(mock_get: Mock, hiro_api: HiroApi, mock_response: Mock) -> None:
    """Test successful GET request."""
    mock_get.return_value = mock_response

    result = hiro_api._get("test-endpoint")

    assert result == {"data": "test_value"}
    mock_get.assert_called_once_with(
        "https://test-hiro-api.com/test-endpoint",
        headers={"Accept": "application/json"},
        params=None,
    )


@patch("requests.get")
def test_get_with_params(
    mock_get: Mock, hiro_api: HiroApi, mock_response: Mock
) -> None:
    """Test GET request with parameters."""
    mock_get.return_value = mock_response

    params = {"key": "value"}
    result = hiro_api._get("test-endpoint", params=params)

    assert result == {"data": "test_value"}
    mock_get.assert_called_once_with(
        "https://test-hiro-api.com/test-endpoint",
        headers={"Accept": "application/json"},
        params=params,
    )


@patch("requests.get")
def test_get_error(mock_get: Mock, hiro_api: HiroApi) -> None:
    """Test GET request error handling."""
    mock_get.side_effect = Exception("API Error")

    with pytest.raises(HiroApiError, match="Unexpected error: API Error"):
        hiro_api._get("test-endpoint")


@patch("requests.get")
def test_get_rate_limit_error(mock_get: Mock, hiro_api: HiroApi) -> None:
    """Test rate limit error handling."""
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
        response=Mock(status_code=429)
    )
    mock_get.return_value = mock_response

    with pytest.raises(HiroApiRateLimitError):
        hiro_api._get("test-endpoint")


@patch("requests.get")
def test_get_retry_on_timeout(mock_get: Mock, hiro_api: HiroApi) -> None:
    """Test retry mechanism on timeout."""
    mock_get.side_effect = [
        requests.exceptions.Timeout(),
        requests.exceptions.Timeout(),
        mock_response,
    ]

    result = hiro_api._get("test-endpoint")
    assert result == {"data": "test_value"}
    assert mock_get.call_count == 3


@patch("requests.get")
def test_get_max_retries_exceeded(mock_get: Mock, hiro_api: HiroApi) -> None:
    """Test max retries exceeded."""
    mock_get.side_effect = requests.exceptions.Timeout()

    with pytest.raises(HiroApiTimeoutError):
        hiro_api._get("test-endpoint")
    assert mock_get.call_count == hiro_api.MAX_RETRIES


@pytest.mark.asyncio
async def test_aget_success(hiro_api: HiroApi) -> None:
    """Test successful async GET request."""
    mock_response = Mock()
    mock_response.json.return_value = {"data": "test_value"}
    mock_response.__aenter__.return_value = mock_response

    with patch.object(aiohttp.ClientSession, "get") as mock_get:
        mock_get.return_value = mock_response
        result = await hiro_api._aget("test-endpoint")
        assert result == {"data": "test_value"}


@pytest.mark.asyncio
async def test_aget_error(hiro_api: HiroApi) -> None:
    """Test async GET request error handling."""
    with patch.object(aiohttp.ClientSession, "get") as mock_get:
        mock_get.side_effect = aiohttp.ClientError()
        with pytest.raises(HiroApiError):
            await hiro_api._aget("test-endpoint")


@pytest.mark.asyncio
async def test_close_session(hiro_api: HiroApi) -> None:
    """Test closing async session."""
    # Create a session
    await hiro_api._aget("test-endpoint")
    assert hiro_api._session is not None

    # Close the session
    await hiro_api.close()
    assert hiro_api._session is None


def test_cached_methods(hiro_api: HiroApi) -> None:
    """Test that caching works for decorated methods."""
    with patch.object(HiroApi, "_get") as mock_get:
        mock_get.return_value = {"data": "test_value"}

        # First call should hit the API
        result1 = hiro_api.get_token_holders("test-token")
        assert result1 == {"data": "test_value"}
        assert mock_get.call_count == 1

        # Second call should use cache
        result2 = hiro_api.get_token_holders("test-token")
        assert result2 == {"data": "test_value"}
        assert mock_get.call_count == 1


# Token holder related tests
@patch("requests.get")
def test_get_token_holders(
    mock_get: Mock, hiro_api: HiroApi, mock_response: Mock
) -> None:
    """Test token holders retrieval."""
    mock_get.return_value = mock_response

    result = hiro_api.get_token_holders("test-token")

    assert result == {"data": "test_value"}
    mock_get.assert_called_once_with(
        f"{hiro_api.base_url}{hiro_api.ENDPOINTS['tokens']}/ft/test-token/holders",
        headers={"Accept": "application/json"},
        params=None,
    )


@patch("requests.get")
def test_get_address_balance(
    mock_get: Mock, hiro_api: HiroApi, mock_response: Mock
) -> None:
    """Test address balance retrieval."""
    mock_get.return_value = mock_response

    result = hiro_api.get_address_balance("test-address")

    assert result == {"data": "test_value"}
    mock_get.assert_called_once_with(
        f"{hiro_api.base_url}{hiro_api.ENDPOINTS['addresses']}/test-address/balances",
        headers={"Accept": "application/json"},
        params=None,
    )


# Transaction related tests
@patch("requests.get")
def test_get_transaction(
    mock_get: Mock, hiro_api: HiroApi, mock_response: Mock
) -> None:
    """Test transaction retrieval."""
    mock_get.return_value = mock_response

    result = hiro_api.get_transaction("test-tx")

    assert result == {"data": "test_value"}
    mock_get.assert_called_once_with(
        "https://test-hiro-api.com//extended/v1/tx/test-tx",
        headers={"Accept": "application/json"},
        params=None,
    )


@patch("requests.get")
def test_get_raw_transaction(
    mock_get: Mock, hiro_api: HiroApi, mock_response: Mock
) -> None:
    """Test raw transaction retrieval."""
    mock_get.return_value = mock_response

    result = hiro_api.get_raw_transaction("test-tx")

    assert result == {"data": "test_value"}
    mock_get.assert_called_once_with(
        "https://test-hiro-api.com//extended/v1/tx/test-tx/raw",
        headers={"Accept": "application/json"},
        params=None,
    )


# Block related tests
@patch("requests.get")
def test_get_blocks(mock_get: Mock, hiro_api: HiroApi, mock_response: Mock) -> None:
    """Test blocks retrieval."""
    mock_get.return_value = mock_response

    result = hiro_api.get_blocks()

    assert result == {"data": "test_value"}
    mock_get.assert_called_once_with(
        "https://test-hiro-api.com//extended/v1/block",
        headers={"Accept": "application/json"},
        params=None,
    )


@patch("requests.get")
def test_get_block_by_height(
    mock_get: Mock, hiro_api: HiroApi, mock_response: Mock
) -> None:
    """Test block retrieval by height."""
    mock_get.return_value = mock_response

    result = hiro_api.get_block_by_height(12345)

    assert result == {"data": "test_value"}
    mock_get.assert_called_once_with(
        "https://test-hiro-api.com//extended/v1/block/by_height/12345",
        headers={"Accept": "application/json"},
        params=None,
    )


# Address related tests
@patch("requests.get")
def test_get_address_stx_balance(
    mock_get: Mock, hiro_api: HiroApi, mock_response: Mock
) -> None:
    """Test STX balance retrieval."""
    mock_get.return_value = mock_response

    result = hiro_api.get_address_stx_balance("test-principal")

    assert result == {"data": "test_value"}
    mock_get.assert_called_once_with(
        "https://test-hiro-api.com//extended/v1/address/test-principal/stx",
        headers={"Accept": "application/json"},
        params=None,
    )


@patch("requests.get")
def test_get_address_transactions(
    mock_get: Mock, hiro_api: HiroApi, mock_response: Mock
) -> None:
    """Test address transactions retrieval."""
    mock_get.return_value = mock_response

    result = hiro_api.get_address_transactions("test-principal")

    assert result == {"data": "test_value"}
    mock_get.assert_called_once_with(
        "https://test-hiro-api.com//extended/v1/address/test-principal/transactions",
        headers={"Accept": "application/json"},
        params=None,
    )


# Token related tests
@patch("requests.get")
def test_get_nft_holdings(
    mock_get: Mock, hiro_api: HiroApi, mock_response: Mock
) -> None:
    """Test NFT holdings retrieval."""
    mock_get.return_value = mock_response
    params = {"limit": 20, "offset": 0}

    result = hiro_api.get_nft_holdings(**params)

    assert result == {"data": "test_value"}
    mock_get.assert_called_once_with(
        "https://test-hiro-api.com//extended/v1/tokens/nft/holdings",
        headers={"Accept": "application/json"},
        params=params,
    )


# Contract related tests
@patch("requests.get")
def test_get_contract_by_id(
    mock_get: Mock, hiro_api: HiroApi, mock_response: Mock
) -> None:
    """Test contract retrieval by ID."""
    mock_get.return_value = mock_response

    result = hiro_api.get_contract_by_id("test-contract")

    assert result == {"data": "test_value"}
    mock_get.assert_called_once_with(
        "https://test-hiro-api.com//extended/v1/contract/test-contract",
        headers={"Accept": "application/json"},
        params=None,
    )


@patch("requests.get")
def test_get_contract_events(
    mock_get: Mock, hiro_api: HiroApi, mock_response: Mock
) -> None:
    """Test contract events retrieval."""
    mock_get.return_value = mock_response

    result = hiro_api.get_contract_events("test-contract")

    assert result == {"data": "test_value"}
    mock_get.assert_called_once_with(
        "https://test-hiro-api.com//extended/v1/contract/test-contract/events",
        headers={"Accept": "application/json"},
        params=None,
    )


# Utility endpoint tests
@patch("requests.get")
def test_get_stx_supply(mock_get: Mock, hiro_api: HiroApi, mock_response: Mock) -> None:
    """Test STX supply retrieval."""
    mock_get.return_value = mock_response

    result = hiro_api.get_stx_supply()

    assert result == {"data": "test_value"}
    mock_get.assert_called_once_with(
        "https://test-hiro-api.com//extended/v1/stx_supply",
        headers={"Accept": "application/json"},
        params=None,
    )


@patch("requests.get")
def test_get_stx_price(mock_get: Mock, hiro_api: HiroApi) -> None:
    """Test STX price retrieval."""
    mock_response = Mock()
    mock_response.json.return_value = {"price": 1.23}
    mock_get.return_value = mock_response

    result = hiro_api.get_stx_price()

    assert result == 1.23
    mock_get.assert_called_once_with(
        "https://explorer.hiro.so/stxPrice", params={"blockBurnTime": "current"}
    )


@patch("requests.get")
def test_get_current_block_height(mock_get: Mock, hiro_api: HiroApi) -> None:
    """Test current block height retrieval."""
    mock_response = Mock()
    mock_response.json.return_value = {"results": [{"height": 12345}]}
    mock_get.return_value = mock_response

    result = hiro_api.get_current_block_height()

    assert result == 12345
    mock_get.assert_called_once_with(
        "https://test-hiro-api.com//extended/v2/blocks",
        headers={"Accept": "application/json"},
        params={"limit": 1, "offset": 0},
    )


@patch("requests.get")
def test_search(mock_get: Mock, hiro_api: HiroApi, mock_response: Mock) -> None:
    """Test search functionality."""
    mock_get.return_value = mock_response

    result = hiro_api.search("test-query")

    assert result == {"data": "test_value"}
    mock_get.assert_called_once_with(
        "https://test-hiro-api.com//extended/v1/search/test-query",
        headers={"Accept": "application/json"},
        params=None,
    )


# Error handling tests
@patch("requests.get")
def test_stx_price_error(mock_get: Mock, hiro_api: HiroApi) -> None:
    """Test STX price error handling."""
    mock_get.side_effect = Exception("API Error")

    with pytest.raises(Exception, match="Failed to get STX price: API Error"):
        hiro_api.get_stx_price()


@patch("requests.get")
def test_current_block_height_error(mock_get: Mock, hiro_api: HiroApi) -> None:
    """Test current block height error handling."""
    mock_get.side_effect = Exception("API Error")

    with pytest.raises(
        Exception, match="Failed to get current block height: API Error"
    ):
        hiro_api.get_current_block_height()


@pytest.mark.asyncio
async def test_async_methods(hiro_api: HiroApi) -> None:
    """Test async versions of methods."""
    mock_response = Mock()
    mock_response.json.return_value = {"data": "test_value"}
    mock_response.__aenter__.return_value = mock_response

    with patch.object(aiohttp.ClientSession, "get") as mock_get:
        mock_get.return_value = mock_response

        # Test async token holders
        result = await hiro_api.aget_token_holders("test-token")
        assert result == {"data": "test_value"}

        # Test async address balance
        result = await hiro_api.aget_address_balance("test-address")
        assert result == {"data": "test_value"}
