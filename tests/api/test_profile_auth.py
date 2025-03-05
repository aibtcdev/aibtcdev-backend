from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from api.dependencies import (
    get_profile_from_api_key,
    verify_profile,
    verify_profile_from_token,
)
from backend.models import Profile


@pytest.mark.asyncio
async def test_get_profile_from_api_key_invalid_uuid():
    """Test that invalid UUID format returns None."""
    result = await get_profile_from_api_key("not-a-uuid")
    assert result is None


@pytest.mark.asyncio
async def test_get_profile_from_api_key_no_keys():
    """Test that when no keys are found, None is returned."""
    with patch("api.dependencies.backend") as mock_backend:
        mock_backend.list_keys.return_value = []

        result = await get_profile_from_api_key("123e4567-e89b-12d3-a456-426614174000")

        assert result is None
        mock_backend.list_keys.assert_called_once()


@pytest.mark.asyncio
async def test_get_profile_from_api_key_no_profile_id():
    """Test that when key has no profile_id, None is returned."""
    with patch("api.dependencies.backend") as mock_backend:
        mock_key = MagicMock()
        mock_key.profile_id = None
        mock_backend.list_keys.return_value = [mock_key]

        result = await get_profile_from_api_key("123e4567-e89b-12d3-a456-426614174000")

        assert result is None


@pytest.mark.asyncio
async def test_get_profile_from_api_key_no_profile():
    """Test that when profile is not found, None is returned."""
    with patch("api.dependencies.backend") as mock_backend:
        mock_key = MagicMock()
        mock_key.profile_id = "profile-id"
        mock_backend.list_keys.return_value = [mock_key]
        mock_backend.get_profile.return_value = None

        result = await get_profile_from_api_key("123e4567-e89b-12d3-a456-426614174000")

        assert result is None
        mock_backend.get_profile.assert_called_once_with("profile-id")


@pytest.mark.asyncio
async def test_get_profile_from_api_key_success():
    """Test successful profile retrieval from API key."""
    with patch("api.dependencies.backend") as mock_backend:
        mock_key = MagicMock()
        mock_key.profile_id = "profile-id"
        mock_profile = MagicMock(spec=Profile)

        mock_backend.list_keys.return_value = [mock_key]
        mock_backend.get_profile.return_value = mock_profile

        result = await get_profile_from_api_key("123e4567-e89b-12d3-a456-426614174000")

        assert result == mock_profile
        mock_backend.get_profile.assert_called_once_with("profile-id")


@pytest.mark.asyncio
async def test_verify_profile_with_api_key():
    """Test verify_profile with valid API key."""
    with patch("api.dependencies.get_profile_from_api_key") as mock_get_profile:
        mock_profile = MagicMock(spec=Profile)
        mock_get_profile.return_value = mock_profile

        result = await verify_profile(authorization=None, x_api_key="valid-api-key")

        assert result == mock_profile
        mock_get_profile.assert_called_once_with("valid-api-key")


@pytest.mark.asyncio
async def test_verify_profile_with_invalid_api_key():
    """Test verify_profile with invalid API key raises exception."""
    with patch("api.dependencies.get_profile_from_api_key") as mock_get_profile:
        mock_get_profile.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await verify_profile(authorization=None, x_api_key="invalid-api-key")

        assert exc_info.value.status_code == 401
        assert "Invalid API key" in exc_info.value.detail


@pytest.mark.asyncio
async def test_verify_profile_missing_auth():
    """Test verify_profile with missing authorization raises exception."""
    with pytest.raises(HTTPException) as exc_info:
        await verify_profile(authorization=None, x_api_key=None)

    assert exc_info.value.status_code == 401
    assert "Missing authorization header" in exc_info.value.detail


@pytest.mark.asyncio
async def test_verify_profile_invalid_auth_format():
    """Test verify_profile with invalid authorization format raises exception."""
    with pytest.raises(HTTPException) as exc_info:
        await verify_profile(authorization="InvalidFormat", x_api_key=None)

    assert exc_info.value.status_code == 401
    assert "Invalid authorization format" in exc_info.value.detail


@pytest.mark.asyncio
async def test_verify_profile_invalid_token():
    """Test verify_profile with invalid token raises exception."""
    with patch("api.dependencies.backend") as mock_backend:
        mock_backend.verify_session_token.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await verify_profile(authorization="Bearer invalid-token", x_api_key=None)

        assert exc_info.value.status_code == 401
        assert "Invalid bearer token" in exc_info.value.detail


@pytest.mark.asyncio
async def test_verify_profile_no_profile():
    """Test verify_profile with valid token but no profile raises exception."""
    with patch("api.dependencies.backend") as mock_backend:
        mock_backend.verify_session_token.return_value = "user@example.com"
        mock_backend.list_profiles.return_value = []

        with pytest.raises(HTTPException) as exc_info:
            await verify_profile(authorization="Bearer valid-token", x_api_key=None)

        assert exc_info.value.status_code == 404
        assert "Profile not found" in exc_info.value.detail


@pytest.mark.asyncio
async def test_verify_profile_success():
    """Test verify_profile with valid token and profile."""
    with patch("api.dependencies.backend") as mock_backend:
        mock_profile = MagicMock(spec=Profile)
        mock_backend.verify_session_token.return_value = "user@example.com"
        mock_backend.list_profiles.return_value = [mock_profile]

        result = await verify_profile(
            authorization="Bearer valid-token", x_api_key=None
        )

        assert result == mock_profile


@pytest.mark.asyncio
async def test_verify_profile_from_token_with_key():
    """Test verify_profile_from_token with valid API key."""
    with patch("api.dependencies.get_profile_from_api_key") as mock_get_profile:
        mock_profile = MagicMock(spec=Profile)
        mock_get_profile.return_value = mock_profile

        result = await verify_profile_from_token(token=None, key="valid-api-key")

        assert result == mock_profile
        mock_get_profile.assert_called_once_with("valid-api-key")


@pytest.mark.asyncio
async def test_verify_profile_from_token_with_invalid_key():
    """Test verify_profile_from_token with invalid API key raises exception."""
    with patch("api.dependencies.get_profile_from_api_key") as mock_get_profile:
        mock_get_profile.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await verify_profile_from_token(token=None, key="invalid-api-key")

        assert exc_info.value.status_code == 401
        assert "Invalid API key" in exc_info.value.detail


@pytest.mark.asyncio
async def test_verify_profile_from_token_missing_token():
    """Test verify_profile_from_token with missing token raises exception."""
    with pytest.raises(HTTPException) as exc_info:
        await verify_profile_from_token(token=None, key=None)

    assert exc_info.value.status_code == 401
    assert "Missing token parameter" in exc_info.value.detail


@pytest.mark.asyncio
async def test_verify_profile_from_token_invalid_token():
    """Test verify_profile_from_token with invalid token raises exception."""
    with patch("api.dependencies.backend") as mock_backend:
        mock_backend.verify_session_token.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await verify_profile_from_token(token="invalid-token", key=None)

        assert exc_info.value.status_code == 401
        assert "Invalid or expired token" in exc_info.value.detail


@pytest.mark.asyncio
async def test_verify_profile_from_token_no_profile():
    """Test verify_profile_from_token with valid token but no profile raises exception."""
    with patch("api.dependencies.backend") as mock_backend:
        mock_backend.verify_session_token.return_value = "user@example.com"
        mock_backend.list_profiles.return_value = []

        with pytest.raises(HTTPException) as exc_info:
            await verify_profile_from_token(token="valid-token", key=None)

        assert exc_info.value.status_code == 404
        assert "No profile found for the authenticated email" in exc_info.value.detail


@pytest.mark.asyncio
async def test_verify_profile_from_token_success():
    """Test verify_profile_from_token with valid token and profile."""
    with patch("api.dependencies.backend") as mock_backend:
        mock_profile = MagicMock(spec=Profile)
        mock_backend.verify_session_token.return_value = "user@example.com"
        mock_backend.list_profiles.return_value = [mock_profile]

        result = await verify_profile_from_token(token="valid-token", key=None)

        assert result == mock_profile
