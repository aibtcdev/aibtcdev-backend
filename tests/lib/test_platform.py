import pytest
from lib.logger import configure_logger
from lib.platform import PlatformApi
from typing import Any, Dict
from unittest.mock import Mock, patch

logger = configure_logger(__name__)


@pytest.fixture
def mock_config() -> None:
    """Fixture to mock config values."""
    with patch("config.config") as mock_config:
        mock_config.api.hiro_api_key = "test_api_key"
        mock_config.api.webhook_url = "https://test-webhook.com"
        mock_config.api.webhook_auth = "test_auth"
        yield


@pytest.fixture
def api(mock_config: None) -> PlatformApi:
    """Fixture providing a PlatformApi instance."""
    return PlatformApi()


def test_init_missing_api_key() -> None:
    """Test initialization with missing API key."""
    with patch("config.config") as mock_config:
        mock_config.api.hiro_api_key = None
        with pytest.raises(
            ValueError, match="HIRO_API_KEY environment variable is required"
        ):
            PlatformApi()


def test_generate_contract_deployment_predicate(api: PlatformApi) -> None:
    """Test contract deployment predicate generation."""
    predicate = api.generate_contract_deployment_predicate(
        txid="test_txid",
        start_block=1000,
        network="testnet",
        name="test_hook",
        end_block=2000,
        expire_after_occurrence=2,
        webhook_url="https://custom-webhook.com",
        webhook_auth="custom_auth",
    )

    assert predicate["name"] == "test_hook"
    assert predicate["chain"] == "stacks"
    assert predicate["version"] == 1

    network_config = predicate["networks"]["testnet"]
    assert network_config["if_this"]["scope"] == "txid"
    assert network_config["if_this"]["equals"] == "test_txid"
    assert network_config["start_block"] == 1000
    assert network_config["end_block"] == 2000
    assert network_config["expire_after_occurrence"] == 2
    assert (
        network_config["then_that"]["http_post"]["url"] == "https://custom-webhook.com"
    )
    assert (
        network_config["then_that"]["http_post"]["authorization_header"]
        == "custom_auth"
    )


def test_generate_contract_deployment_predicate_defaults(api: PlatformApi) -> None:
    """Test contract deployment predicate generation with default values."""
    predicate = api.generate_contract_deployment_predicate("test_txid")

    assert predicate["name"] == "test"
    network_config = predicate["networks"]["testnet"]
    assert network_config["start_block"] == 75996
    assert network_config["end_block"] is None
    assert network_config["expire_after_occurrence"] == 1
    assert network_config["then_that"]["http_post"]["url"] == api.webhook_url
    assert (
        network_config["then_that"]["http_post"]["authorization_header"]
        == api.webhook_auth
    )


def test_create_contract_deployment_hook(api: PlatformApi) -> None:
    """Test contract deployment hook creation."""
    with patch.object(api, "create_chainhook") as mock_create_chainhook:
        mock_create_chainhook.return_value = {"status": "success"}

        result = api.create_contract_deployment_hook("test_txid", name="test_hook")
        assert result == {"status": "success"}

        # Verify the predicate was generated correctly
        mock_create_chainhook.assert_called_once()
        predicate = mock_create_chainhook.call_args[0][0]
        assert predicate["name"] == "test_hook"
        assert predicate["networks"]["testnet"]["if_this"]["equals"] == "test_txid"


def test_create_chainhook(api: PlatformApi) -> None:
    """Test chainhook creation."""
    mock_response = Mock()
    mock_response.json.return_value = {"status": "success"}

    with patch("requests.post") as mock_post:
        mock_post.return_value = mock_response

        predicate = {"test": "predicate"}
        result = api.create_chainhook(predicate)

        assert result == {"status": "success"}
        mock_post.assert_called_once_with(
            f"{api.base_url}/v1/ext/{api.api_key}/chainhooks",
            headers={"Content-Type": "application/json"},
            json=predicate,
        )


def test_create_chainhook_error(api: PlatformApi) -> None:
    """Test chainhook creation error handling."""
    with patch("requests.post") as mock_post:
        mock_post.side_effect = Exception("API Error")

        with pytest.raises(Exception, match="Hiro API POST request error: API Error"):
            api.create_chainhook({"test": "predicate"})


def test_generate_dao_x_linkage(api: PlatformApi) -> None:
    """Test DAO X linkage predicate generation."""
    predicate = api.generate_dao_x_linkage(
        contract_identifier="test.contract",
        method="test_method",
        start_block=2000,
        network="mainnet",
        name="test_dao",
        end_block=3000,
        webhook_url="https://custom-webhook.com",
        webhook_auth="custom_auth",
    )

    assert predicate["name"] == "test_dao"
    assert predicate["chain"] == "stacks"
    assert predicate["version"] == 1

    network_config = predicate["networks"]["mainnet"]
    assert network_config["if_this"]["scope"] == "contract_call"
    assert network_config["if_this"]["method"] == "test_method"
    assert network_config["if_this"]["contract_identifier"] == "test.contract"
    assert network_config["start_block"] == 2000
    assert network_config["end_block"] == 3000
    assert (
        network_config["then_that"]["http_post"]["url"] == "https://custom-webhook.com"
    )
    assert (
        network_config["then_that"]["http_post"]["authorization_header"]
        == "custom_auth"
    )


def test_generate_dao_x_linkage_defaults(api: PlatformApi) -> None:
    """Test DAO X linkage predicate generation with default values."""
    predicate = api.generate_dao_x_linkage("test.contract")

    assert predicate["name"] == "getMessage"
    network_config = predicate["networks"]["mainnet"]
    assert network_config["if_this"]["method"] == "send"
    assert network_config["start_block"] == 601924
    assert network_config["end_block"] is None
    assert network_config["then_that"]["http_post"]["url"] == api.webhook_url
    assert (
        network_config["then_that"]["http_post"]["authorization_header"]
        == api.webhook_auth
    )


def test_create_dao_x_linkage_hook(api: PlatformApi) -> None:
    """Test DAO X linkage hook creation."""
    with patch.object(api, "create_chainhook") as mock_create_chainhook:
        mock_create_chainhook.return_value = {"status": "success"}

        result = api.create_dao_x_linkage_hook(
            "test.contract", "test_method", name="test_dao"
        )
        assert result == {"status": "success"}

        # Verify the predicate was generated correctly
        mock_create_chainhook.assert_called_once()
        predicate = mock_create_chainhook.call_args[0][0]
        assert predicate["name"] == "test_dao"
        assert (
            predicate["networks"]["mainnet"]["if_this"]["contract_identifier"]
            == "test.contract"
        )
        assert predicate["networks"]["mainnet"]["if_this"]["method"] == "test_method"
