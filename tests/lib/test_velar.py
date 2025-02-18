import pytest
from lib.logger import configure_logger
from lib.velar import VelarApi
from typing import Dict, List
from unittest.mock import Mock, patch

logger = configure_logger(__name__)


@pytest.fixture
def velar_api() -> VelarApi:
    """Fixture providing a VelarApi instance."""
    return VelarApi()


@pytest.fixture
def mock_pools() -> List[Dict[str, str]]:
    """Fixture providing mock pool data."""
    return [
        {
            "token0Symbol": "TEST",
            "token1Symbol": "STX",
            "poolId": "pool1",
        },
        {
            "token0Symbol": "STX",
            "token1Symbol": "OTHER",
            "poolId": "pool2",
        },
        {
            "token0Symbol": "TEST",
            "token1Symbol": "OTHER",
            "poolId": "pool3",
        },
    ]


@pytest.fixture
def mock_stats_data() -> Dict[str, List[Dict[str, float]]]:
    """Fixture providing mock stats data."""
    return {
        "data": [
            {"datetime": "2024-01-01", "value": 1.0},
            {"datetime": "2024-01-02", "value": 2.0},
        ]
    }


def test_initialization(velar_api: VelarApi) -> None:
    """Test VelarApi initialization."""
    assert velar_api.base_url == "https://gateway.velar.network/"


@patch("requests.get")
def test_get_success(mock_get: Mock, velar_api: VelarApi) -> None:
    """Test successful GET request."""
    mock_response = Mock()
    mock_response.json.return_value = {"data": "test"}
    mock_get.return_value = mock_response

    result = velar_api._get("test-endpoint")

    assert result == {"data": "test"}
    mock_get.assert_called_once_with(
        "https://gateway.velar.network/test-endpoint",
        headers={"Accept": "application/json"},
        params=None,
    )


@patch("requests.get")
def test_get_with_params(mock_get: Mock, velar_api: VelarApi) -> None:
    """Test GET request with parameters."""
    mock_response = Mock()
    mock_response.json.return_value = {"data": "test"}
    mock_get.return_value = mock_response

    params = {"key": "value"}
    result = velar_api._get("test-endpoint", params=params)

    assert result == {"data": "test"}
    mock_get.assert_called_once_with(
        "https://gateway.velar.network/test-endpoint",
        headers={"Accept": "application/json"},
        params=params,
    )


@patch("requests.get")
def test_get_error(mock_get: Mock, velar_api: VelarApi) -> None:
    """Test GET request error handling."""
    mock_get.side_effect = Exception("API Error")

    with pytest.raises(Exception, match="Velar API GET request error: API Error"):
        velar_api._get("test-endpoint")


@patch("requests.get")
def test_get_tokens(mock_get: Mock, velar_api: VelarApi) -> None:
    """Test tokens retrieval."""
    mock_response = Mock()
    mock_response.json.return_value = {"message": ["token1", "token2"]}
    mock_get.return_value = mock_response

    result = velar_api.get_tokens()

    assert result == ["token1", "token2"]
    mock_get.assert_called_once_with(
        "https://gateway.velar.network/swapapp/swap/tokens",
        headers={"Accept": "application/json"},
        params=None,
    )


@patch("requests.get")
def test_get_pools(
    mock_get: Mock, velar_api: VelarApi, mock_pools: List[Dict[str, str]]
) -> None:
    """Test pools retrieval."""
    mock_response = Mock()
    mock_response.json.return_value = {"message": mock_pools}
    mock_get.return_value = mock_response

    result = velar_api.get_pools()

    assert result == mock_pools
    mock_get.assert_called_once_with(
        "https://gateway.velar.network/watcherapp/pool",
        headers={"Accept": "application/json"},
        params=None,
    )


@patch.object(VelarApi, "get_pools")
def test_get_token_pools(
    mock_get_pools: Mock, velar_api: VelarApi, mock_pools: List[Dict[str, str]]
) -> None:
    """Test token pools retrieval."""
    mock_get_pools.return_value = mock_pools

    result = velar_api.get_token_pools("TEST")

    assert len(result) == 2
    assert all(
        pool["token0Symbol"] == "TEST" or pool["token1Symbol"] == "TEST"
        for pool in result
    )


@patch.object(VelarApi, "get_pools")
def test_get_token_stx_pools(
    mock_get_pools: Mock, velar_api: VelarApi, mock_pools: List[Dict[str, str]]
) -> None:
    """Test STX token pools retrieval."""
    mock_get_pools.return_value = mock_pools

    result = velar_api.get_token_stx_pools("TEST")

    assert len(result) == 1
    assert result[0]["poolId"] == "pool1"
    assert "TEST" in [
        result[0]["token0Symbol"],
        result[0]["token1Symbol"],
    ] and "STX" in [result[0]["token0Symbol"], result[0]["token1Symbol"]]


@patch("requests.get")
def test_get_token_price_history(
    mock_get: Mock,
    velar_api: VelarApi,
    mock_stats_data: Dict[str, List[Dict[str, float]]],
) -> None:
    """Test token price history retrieval."""
    mock_response = Mock()
    mock_response.json.return_value = mock_stats_data
    mock_get.return_value = mock_response

    result = velar_api.get_token_price_history("TEST", "week")

    assert result == mock_stats_data
    mock_get.assert_called_once_with(
        "https://gateway.velar.network/watcherapp/stats/TEST/?type=price&interval=week",
        headers={"Accept": "application/json"},
        params=None,
    )


@patch("requests.get")
def test_get_token_stats(mock_get: Mock, velar_api: VelarApi) -> None:
    """Test token stats retrieval."""
    mock_response = Mock()
    mock_response.json.return_value = {"stats": "data"}
    mock_get.return_value = mock_response

    result = velar_api.get_token_stats("TEST")

    assert result == {"stats": "data"}
    mock_get.assert_called_once_with(
        "https://gateway.velar.network/watcherapp/pool/TEST",
        headers={"Accept": "application/json"},
        params=None,
    )


@patch("requests.get")
def test_get_pool_stats_history(mock_get: Mock, velar_api: VelarApi) -> None:
    """Test pool stats history retrieval."""
    mock_response = Mock()
    mock_response.json.return_value = {"stats": "data"}
    mock_get.return_value = mock_response

    result = velar_api.get_pool_stats_history("pool1", "tvl", "week")

    assert result == {"stats": "data"}
    mock_get.assert_called_once_with(
        "https://gateway.velar.network/watcherapp/stats/pool1?type=tvl&interval=week",
        headers={"Accept": "application/json"},
        params=None,
    )


@patch.object(VelarApi, "_get")
def test_get_pool_stats_history_agg(
    mock_get: Mock,
    velar_api: VelarApi,
    mock_stats_data: Dict[str, List[Dict[str, float]]],
) -> None:
    """Test aggregated pool stats history retrieval."""
    mock_get.return_value = mock_stats_data

    result = velar_api.get_pool_stats_history_agg("pool1", "week")

    assert len(result) == 2
    assert all(key in result[0] for key in ["price", "tvl", "volume", "datetime"])
    assert mock_get.call_count == 3  # Called for price, tvl, and volume data


@patch.object(VelarApi, "_get")
def test_get_pool_stats_history_agg_error(mock_get: Mock, velar_api: VelarApi) -> None:
    """Test aggregated pool stats history retrieval error."""
    mock_get.side_effect = Exception("API Error")

    with pytest.raises(
        Exception, match="Token pool stats history retrieval error: API Error"
    ):
        velar_api.get_pool_stats_history_agg("pool1")
