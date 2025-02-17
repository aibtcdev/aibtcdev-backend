import pytest
from lib.alex import AlexApi
from lib.logger import configure_logger
from typing import Dict, List
from unittest.mock import Mock, patch

logger = configure_logger(__name__)


@pytest.fixture
def mock_config() -> None:
    """Fixture to mock config values."""
    with patch("config.config") as mock_config:
        mock_config.api.alex_base_url = "https://test-alex-api.com/"
        yield


@pytest.fixture
def alex_api(mock_config: None) -> AlexApi:
    """Fixture providing an AlexApi instance."""
    return AlexApi()


@pytest.fixture
def mock_price_data() -> Dict[str, List[Dict[str, float]]]:
    """Fixture providing mock price history data."""
    return {
        "prices": [
            {"avg_price_usd": 1.0, "block_height": 1000},
            {"avg_price_usd": 2.0, "block_height": 2000},
        ]
    }


@pytest.fixture
def mock_volume_data() -> Dict[str, List[Dict[str, float]]]:
    """Fixture providing mock volume data."""
    return {
        "volume_values": [
            {"volume_24h": 1000.0, "block_height": 1000},
            {"volume_24h": 2000.0, "block_height": 2000},
        ]
    }


def test_initialization(alex_api: AlexApi) -> None:
    """Test AlexApi initialization."""
    assert alex_api.base_url == "https://test-alex-api.com/"
    assert alex_api.limits == 500


@patch("requests.get")
def test_get_success(mock_get: Mock, alex_api: AlexApi) -> None:
    """Test successful GET request."""
    mock_response = Mock()
    mock_response.json.return_value = {"data": "test"}
    mock_get.return_value = mock_response

    result = alex_api._get("test-endpoint")

    assert result == {"data": "test"}
    mock_get.assert_called_once_with(
        "https://test-alex-api.com/test-endpoint",
        headers={"Accept": "application/json"},
        params={},
    )


@patch("requests.get")
def test_get_with_params(mock_get: Mock, alex_api: AlexApi) -> None:
    """Test GET request with parameters."""
    mock_response = Mock()
    mock_response.json.return_value = {"data": "test"}
    mock_get.return_value = mock_response

    params = {"key": "value"}
    result = alex_api._get("test-endpoint", params=params)

    assert result == {"data": "test"}
    mock_get.assert_called_once_with(
        "https://test-alex-api.com/test-endpoint",
        headers={"Accept": "application/json"},
        params=params,
    )


@patch("requests.get")
def test_get_error(mock_get: Mock, alex_api: AlexApi) -> None:
    """Test GET request error handling."""
    mock_get.side_effect = Exception("API Error")

    with pytest.raises(Exception, match="Alex API GET request error: API Error"):
        alex_api._get("test-endpoint")


@patch("requests.get")
def test_get_pairs(mock_get: Mock, alex_api: AlexApi) -> None:
    """Test pairs retrieval."""
    mock_response = Mock()
    mock_response.json.return_value = {"data": ["pair1", "pair2"]}
    mock_get.return_value = mock_response

    result = alex_api.get_pairs()

    assert result == ["pair1", "pair2"]
    mock_get.assert_called_once_with(
        "https://test-alex-api.com/v1/public/pairs",
        headers={"Accept": "application/json"},
        params={},
    )


@patch("requests.get")
def test_get_price_history(
    mock_get: Mock,
    alex_api: AlexApi,
    mock_price_data: Dict[str, List[Dict[str, float]]],
) -> None:
    """Test price history retrieval."""
    mock_response = Mock()
    mock_response.json.return_value = mock_price_data
    mock_get.return_value = mock_response

    result = alex_api.get_price_history("test-token")

    assert len(result) == 2
    assert all(key in result[0] for key in ["price", "block"])
    assert result[0]["price"] == 1.0
    assert result[0]["block"] == 1000
    mock_get.assert_called_once_with(
        "https://test-alex-api.com/v1/price_history/test-token?limit=500",
        headers={"Accept": "application/json"},
        params={},
    )


@patch("requests.get")
def test_get_all_swaps(mock_get: Mock, alex_api: AlexApi) -> None:
    """Test all swaps retrieval."""
    mock_response = Mock()
    mock_response.json.return_value = {"swaps": ["swap1", "swap2"]}
    mock_get.return_value = mock_response

    result = alex_api.get_all_swaps()

    assert result == {"swaps": ["swap1", "swap2"]}
    mock_get.assert_called_once_with(
        "https://test-alex-api.com/v1/allswaps",
        headers={"Accept": "application/json"},
        params={},
    )


@patch("requests.get")
def test_get_token_pool_volume(
    mock_get: Mock,
    alex_api: AlexApi,
    mock_volume_data: Dict[str, List[Dict[str, float]]],
) -> None:
    """Test pool volume retrieval."""
    mock_response = Mock()
    mock_response.json.return_value = mock_volume_data
    mock_get.return_value = mock_response

    result = alex_api.get_token_pool_volume("test-pool")

    assert len(result) == 2
    assert result[0]["volume_24h"] == 1000.0
    assert result[0]["block_height"] == 1000
    mock_get.assert_called_once_with(
        "https://test-alex-api.com/v1/pool_volume/test-pool?limit=500",
        headers={"Accept": "application/json"},
        params={},
    )


@patch("requests.get")
def test_get_token_pool_agg_history(
    mock_get: Mock,
    alex_api: AlexApi,
    mock_price_data: Dict[str, List[Dict[str, float]]],
    mock_volume_data: Dict[str, List[Dict[str, float]]],
) -> None:
    """Test aggregated history retrieval."""
    mock_response1 = Mock()
    mock_response1.json.return_value = mock_price_data
    mock_response2 = Mock()
    mock_response2.json.return_value = mock_volume_data
    mock_get.side_effect = [mock_response1, mock_response2]

    result = alex_api.get_token_pool_agg_history("test-token", "test-pool")

    assert len(result) == 2
    assert all(key in result[0] for key in ["price", "block", "volume_24h"])
    assert result[0]["price"] == 1.0
    assert result[0]["block"] == 1000
    assert result[0]["volume_24h"] == 1000.0
    assert mock_get.call_count == 2


@patch("requests.get")
def test_get_token_pool_price(mock_get: Mock, alex_api: AlexApi) -> None:
    """Test pool price retrieval."""
    mock_response = Mock()
    mock_response.json.return_value = {"price": 1.5}
    mock_get.return_value = mock_response

    result = alex_api.get_token_pool_price("test-pool")

    assert result == {"price": 1.5}
    mock_get.assert_called_once_with(
        "https://test-alex-api.com/v1/pool_token_price/test-pool?limit=500",
        headers={"Accept": "application/json"},
        params={},
    )


@patch("requests.get")
def test_get_token_tvl(mock_get: Mock, alex_api: AlexApi) -> None:
    """Test TVL retrieval."""
    mock_response = Mock()
    mock_response.json.return_value = {"tvl": 1000000.0}
    mock_get.return_value = mock_response

    result = alex_api.get_token_tvl("test-pool")

    assert result == {"tvl": 1000000.0}
    mock_get.assert_called_once_with(
        "https://test-alex-api.com/v1/stats/tvl/test-pool?limit=500",
        headers={"Accept": "application/json"},
        params={},
    )


@patch("requests.get")
def test_error_handling(mock_get: Mock, alex_api: AlexApi) -> None:
    """Test error handling for all methods."""
    mock_get.side_effect = Exception("API Error")

    with pytest.raises(Exception, match="Failed to get token pairs"):
        alex_api.get_pairs()

    with pytest.raises(Exception, match="Failed to get token price history"):
        alex_api.get_price_history("test-token")

    with pytest.raises(Exception, match="Failed to get all swaps"):
        alex_api.get_all_swaps()

    with pytest.raises(Exception, match="Failed to get pool volume"):
        alex_api.get_token_pool_volume("test-pool")

    with pytest.raises(Exception, match="Failed to get token price history"):
        alex_api.get_token_pool_agg_history("test-token", "test-pool")

    with pytest.raises(Exception, match="Failed to get pool price"):
        alex_api.get_token_pool_price("test-pool")

    with pytest.raises(Exception, match="Failed to get pool volume"):
        alex_api.get_token_tvl("test-pool")
