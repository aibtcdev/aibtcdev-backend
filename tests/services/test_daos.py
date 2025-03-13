import uuid
from unittest.mock import patch

import pytest

from backend.models import DAO, Token
from services.daos import (
    DAORequest,
    DAOService,
    TokenCreationError,
    TokenRequest,
    TokenService,
    TokenServiceError,
    TokenUpdateError,
)


@pytest.fixture
def mock_backend():
    with patch("services.daos.backend") as mock:
        yield mock


@pytest.fixture
def dao_request():
    return DAORequest(
        name="Test DAO",
        mission="Test Mission",
        description="Test Description",
        wallet_id=uuid.uuid4(),
    )


@pytest.fixture
def token_request():
    return TokenRequest(
        name="Test Token",
        symbol="TEST",
        description="Test Token Description",
        decimals=6,
        max_supply="1000000000",
    )


class TestDAORequest:
    def test_to_dao_create(self, dao_request):
        dao_create = dao_request.to_dao_create()
        assert dao_create.name == dao_request.name
        assert dao_create.mission == dao_request.mission
        assert dao_create.description == dao_request.description
        assert dao_create.wallet_id == dao_request.wallet_id


class TestTokenRequest:
    def test_to_token_create(self, token_request):
        token_create = token_request.to_token_create()
        assert token_create.name == token_request.name
        assert token_create.symbol == token_request.symbol
        assert token_create.description == token_request.description
        assert token_create.decimals == token_request.decimals
        assert token_create.max_supply == token_request.max_supply
        assert token_create.status == "DRAFT"

    def test_to_token_metadata(self, token_request):
        metadata = token_request.to_token_metadata()
        assert metadata.name == token_request.name
        assert metadata.symbol == token_request.symbol
        assert metadata.description == token_request.description
        assert metadata.decimals == token_request.decimals
        assert metadata.max_supply == token_request.max_supply


class TestDAOService:
    def test_create_dao_success(self, mock_backend, dao_request):
        expected_dao = DAO(
            id=uuid.uuid4(),
            name=dao_request.name,
            mission=dao_request.mission,
            description=dao_request.description,
            wallet_id=dao_request.wallet_id,
        )
        mock_backend.create_dao.return_value = expected_dao

        result = DAOService.create_dao(dao_request)
        assert result == expected_dao
        mock_backend.create_dao.assert_called_once_with(dao_request.to_dao_create())

    def test_create_dao_failure(self, mock_backend, dao_request):
        mock_backend.create_dao.side_effect = Exception("Database error")

        with pytest.raises(TokenServiceError) as exc_info:
            DAOService.create_dao(dao_request)

        assert "Failed to create dao" in str(exc_info.value)


class TestTokenService:
    @pytest.fixture
    def token_service(self):
        return TokenService()

    @pytest.fixture
    def mock_asset_manager(self):
        with patch("services.daos.TokenAssetManager") as mock:
            instance = mock.return_value
            instance.generate_all_assets.return_value = {
                "metadata_url": "http://example.com/metadata",
                "image_url": "http://example.com/image",
            }
            yield instance

    def test_create_token_success(
        self, token_service, mock_backend, mock_asset_manager, token_request
    ):
        # Mock token creation
        created_token = Token(
            id=uuid.uuid4(),
            name=token_request.name,
            symbol=token_request.symbol,
            description=token_request.description,
            decimals=token_request.decimals,
            max_supply=token_request.max_supply,
            status="DRAFT",
        )
        mock_backend.create_token.return_value = created_token

        # Mock token update
        updated_token = Token(
            id=created_token.id,
            name=created_token.name,
            symbol=created_token.symbol,
            description=created_token.description,
            decimals=created_token.decimals,
            max_supply=created_token.max_supply,
            status="DRAFT",
            uri="http://example.com/metadata",
            image_url="http://example.com/image",
        )
        mock_backend.update_token.return_value = updated_token

        metadata_url, result = token_service.create_token(token_request)

        assert metadata_url == "http://example.com/metadata"
        assert result == updated_token
        mock_backend.create_token.assert_called_once_with(
            token_request.to_token_create()
        )
        mock_asset_manager.generate_all_assets.assert_called_once()

    def test_create_token_asset_generation_failure(
        self, token_service, mock_backend, mock_asset_manager, token_request
    ):
        created_token = Token(
            id=uuid.uuid4(),
            name=token_request.name,
            symbol=token_request.symbol,
            description=token_request.description,
            decimals=token_request.decimals,
            max_supply=token_request.max_supply,
            status="DRAFT",
        )
        mock_backend.create_token.return_value = created_token
        mock_asset_manager.generate_all_assets.side_effect = Exception(
            "Asset generation failed"
        )

        with pytest.raises(TokenCreationError) as exc_info:
            token_service.create_token(token_request)

        assert "Unexpected error during token creation" in str(exc_info.value)

    def test_create_token_update_failure(
        self, token_service, mock_backend, mock_asset_manager, token_request
    ):
        created_token = Token(
            id=uuid.uuid4(),
            name=token_request.name,
            symbol=token_request.symbol,
            description=token_request.description,
            decimals=token_request.decimals,
            max_supply=token_request.max_supply,
            status="DRAFT",
        )
        mock_backend.create_token.return_value = created_token
        mock_backend.update_token.return_value = None

        with pytest.raises(TokenUpdateError) as exc_info:
            token_service.create_token(token_request)

        assert "Failed to update token record with asset URLs" in str(exc_info.value)

    def test_bind_token_to_dao_success(self, token_service, mock_backend):
        token_id = uuid.uuid4()
        dao_id = uuid.uuid4()
        mock_backend.update_token.return_value = True

        result = token_service.bind_token_to_dao(token_id, dao_id)

        assert result is True
        mock_backend.update_token.assert_called_once()

    def test_bind_token_to_dao_failure(self, token_service, mock_backend):
        token_id = uuid.uuid4()
        dao_id = uuid.uuid4()
        mock_backend.update_token.side_effect = Exception("Update failed")

        result = token_service.bind_token_to_dao(token_id, dao_id)

        assert result is False
