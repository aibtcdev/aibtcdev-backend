"""Tests for the DAO webhook service."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from backend.models import ContractStatus
from services.webhooks.dao.handler import DAOHandler
from services.webhooks.dao.models import DAOWebhookPayload, ExtensionData, TokenData
from services.webhooks.dao.parser import DAOParser
from services.webhooks.dao.service import DAOService


@pytest.fixture
def sample_dao_payload():
    """Create a sample DAO webhook payload for testing."""
    return {
        "name": "Test DAO",
        "mission": "Testing mission",
        "description": "A DAO for testing purposes",
        "is_deployed": False,
        "is_broadcasted": False,
        "extensions": [{"type": "test_extension", "status": "DRAFT"}],
        "token": {
            "name": "Test Token",
            "symbol": "TEST",
            "decimals": 6,
            "description": "A token for testing",
        },
    }


def test_dao_parser(sample_dao_payload):
    """Test that the DAO parser correctly parses a valid payload."""
    parser = DAOParser()
    result = parser.parse(sample_dao_payload)

    assert isinstance(result, DAOWebhookPayload)
    assert result.name == "Test DAO"
    assert result.mission == "Testing mission"
    assert result.description == "A DAO for testing purposes"
    assert result.is_deployed is False
    assert result.is_broadcasted is False

    assert len(result.extensions) == 1
    assert result.extensions[0].type == "test_extension"
    assert result.extensions[0].status == ContractStatus.DRAFT

    assert result.token is not None
    assert result.token.name == "Test Token"
    assert result.token.symbol == "TEST"
    assert result.token.decimals == 6
    assert result.token.description == "A token for testing"


@pytest.mark.asyncio
async def test_dao_handler():
    """Test that the DAO handler correctly processes a parsed payload."""
    # Create mock database
    mock_db = MagicMock()
    mock_db.create_dao.return_value = MagicMock(
        id=UUID("00000000-0000-0000-0000-000000000001"), name="Test DAO"
    )
    mock_db.create_extension.return_value = MagicMock(
        id=UUID("00000000-0000-0000-0000-000000000002")
    )
    mock_db.create_token.return_value = MagicMock(
        id=UUID("00000000-0000-0000-0000-000000000003")
    )

    # Create parsed payload
    parsed_data = DAOWebhookPayload(
        name="Test DAO",
        mission="Testing mission",
        description="A DAO for testing purposes",
        extensions=[ExtensionData(type="test_extension", status=ContractStatus.DRAFT)],
        token=TokenData(
            name="Test Token",
            symbol="TEST",
            decimals=6,
            description="A token for testing",
        ),
    )

    # Test handler with mocked database
    with patch("backend.factory.backend", mock_db):
        handler = DAOHandler()
        result = await handler.handle(parsed_data)

        assert result["success"] is True
        assert "Successfully created DAO 'Test DAO'" in result["message"]
        assert result["data"]["dao_id"] == UUID("00000000-0000-0000-0000-000000000001")
        assert result["data"]["extension_ids"] == [
            UUID("00000000-0000-0000-0000-000000000002")
        ]
        assert result["data"]["token_id"] == UUID(
            "00000000-0000-0000-0000-000000000003"
        )

        # Verify database calls
        mock_db.create_dao.assert_called_once()
        mock_db.create_extension.assert_called_once()
        mock_db.create_token.assert_called_once()


@pytest.mark.asyncio
async def test_dao_service(sample_dao_payload):
    """Test that the DAO service correctly coordinates parsing and handling."""
    # Create mock parser and handler
    mock_parser = MagicMock()
    mock_handler = MagicMock()
    mock_handler.handle = AsyncMock()

    # Configure mock returns
    parsed_data = DAOWebhookPayload(**sample_dao_payload)
    mock_parser.parse.return_value = parsed_data
    mock_handler.handle.return_value = {
        "success": True,
        "message": "Successfully created DAO",
        "data": {
            "dao_id": UUID("00000000-0000-0000-0000-000000000001"),
            "extension_ids": [UUID("00000000-0000-0000-0000-000000000002")],
            "token_id": UUID("00000000-0000-0000-0000-000000000003"),
        },
    }

    # Create service with mocked components
    service = DAOService()
    service.parser = mock_parser
    service.handler = mock_handler

    # Test service
    result = await service.process(sample_dao_payload)

    assert result["success"] is True
    assert result["message"] == "Successfully created DAO"
    assert result["data"]["dao_id"] == UUID("00000000-0000-0000-0000-000000000001")

    # Verify component calls
    mock_parser.parse.assert_called_once_with(sample_dao_payload)
    mock_handler.handle.assert_called_once_with(parsed_data)
