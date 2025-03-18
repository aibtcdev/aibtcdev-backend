from unittest.mock import patch

import pytest
from fastapi import HTTPException

from api.dependencies import verify_webhook_auth


@pytest.mark.asyncio
async def test_verify_webhook_auth_missing_header():
    """Test authentication fails when Authorization header is missing."""
    with pytest.raises(HTTPException) as exc_info:
        await verify_webhook_auth(authorization=None)

    assert exc_info.value.status_code == 401
    assert "Missing Authorization header" in exc_info.value.detail


@pytest.mark.asyncio
async def test_verify_webhook_auth_invalid_format():
    """Test authentication fails when Authorization header has invalid format."""
    with pytest.raises(HTTPException) as exc_info:
        await verify_webhook_auth(authorization="InvalidFormat")

    assert exc_info.value.status_code == 401
    assert "Invalid Authorization format" in exc_info.value.detail


@pytest.mark.asyncio
async def test_verify_webhook_auth_invalid_token():
    """Test authentication fails when token is invalid."""
    with patch("api.dependencies.config") as mock_config:
        mock_config.api.webhook_auth = "Bearer correct-token"

        with pytest.raises(HTTPException) as exc_info:
            await verify_webhook_auth(authorization="Bearer wrong-token")

        assert exc_info.value.status_code == 401
        assert "Invalid authentication token" in exc_info.value.detail


@pytest.mark.asyncio
async def test_verify_webhook_auth_success():
    """Test authentication succeeds with valid token."""
    with patch("api.dependencies.config") as mock_config:
        mock_config.api.webhook_auth = "Bearer correct-token"

        # Should not raise an exception
        result = await verify_webhook_auth(authorization="Bearer correct-token")

        assert result is None  # Function returns None on success


@pytest.mark.asyncio
async def test_verify_webhook_auth_with_raw_token():
    """Test authentication with raw token in config."""
    with patch("api.dependencies.config") as mock_config:
        # Config has token without Bearer prefix
        mock_config.api.webhook_auth = "correct-token"

        # Should not raise an exception
        result = await verify_webhook_auth(authorization="Bearer correct-token")

        assert result is None  # Function returns None on success
