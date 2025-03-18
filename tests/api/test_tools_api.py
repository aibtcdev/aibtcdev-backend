import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.tools import router
from lib.tools import Tool


# Create a test client
@pytest.fixture
def client():
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# Mock tools for testing
@pytest.fixture
def mock_tools():
    return [
        Tool(
            id="test_get_data",
            name="Get Data",
            description="Test tool for getting data",
            category="TEST",
            parameters=json.dumps(
                {
                    "param1": {"description": "Test parameter 1", "type": "str"},
                    "param2": {"description": "Test parameter 2", "type": "int"},
                }
            ),
        ),
        Tool(
            id="wallet_get_balance",
            name="Get Balance",
            description="Get wallet balance",
            category="WALLET",
            parameters=json.dumps(
                {"wallet_id": {"description": "Wallet ID", "type": "UUID"}}
            ),
        ),
        Tool(
            id="dao_get_info",
            name="Get Info",
            description="Get DAO information",
            category="DAO",
            parameters=json.dumps(
                {"dao_id": {"description": "DAO ID", "type": "UUID"}}
            ),
        ),
    ]


@pytest.mark.asyncio
async def test_get_tools(client, mock_tools):
    """Test the /tools/available endpoint."""
    # Mock the available_tools
    with patch("api.tools.available_tools", mock_tools):
        response = client.get("/tools/available")

        # Check response status
        assert response.status_code == 200

        # Check response content
        tools = response.json()
        assert len(tools) == 3
        assert tools[0]["id"] == "test_get_data"
        assert tools[1]["id"] == "wallet_get_balance"
        assert tools[2]["id"] == "dao_get_info"


@pytest.mark.asyncio
async def test_get_tools_with_category_filter(client, mock_tools):
    """Test the /tools/available endpoint with category filter."""
    # Mock the available_tools
    with patch("api.tools.available_tools", mock_tools):
        response = client.get("/tools/available?category=WALLET")

        # Check response status
        assert response.status_code == 200

        # Check response content
        tools = response.json()
        assert len(tools) == 1
        assert tools[0]["id"] == "wallet_get_balance"
        assert tools[0]["category"] == "WALLET"


@pytest.mark.asyncio
async def test_get_tools_with_nonexistent_category(client, mock_tools):
    """Test the /tools/available endpoint with a category that doesn't exist."""
    # Mock the available_tools
    with patch("api.tools.available_tools", mock_tools):
        response = client.get("/tools/available?category=NONEXISTENT")

        # Check response status
        assert response.status_code == 200

        # Check response content
        tools = response.json()
        assert len(tools) == 0


@pytest.mark.asyncio
async def test_get_tool_categories(client, mock_tools):
    """Test the /tools/categories endpoint."""
    # Mock the available_tools
    with patch("api.tools.available_tools", mock_tools):
        response = client.get("/tools/categories")

        # Check response status
        assert response.status_code == 200

        # Check response content
        categories = response.json()
        assert len(categories) == 3
        assert "TEST" in categories
        assert "WALLET" in categories
        assert "DAO" in categories


@pytest.mark.asyncio
async def test_search_tools(client, mock_tools):
    """Test the /tools/search endpoint."""
    # Mock the available_tools
    with patch("api.tools.available_tools", mock_tools):
        response = client.get("/tools/search?query=balance")

        # Check response status
        assert response.status_code == 200

        # Check response content
        tools = response.json()
        assert len(tools) == 1
        assert tools[0]["id"] == "wallet_get_balance"


@pytest.mark.asyncio
async def test_search_tools_with_category(client, mock_tools):
    """Test the /tools/search endpoint with category filter."""
    # Mock the available_tools
    with patch("api.tools.available_tools", mock_tools):
        response = client.get("/tools/search?query=get&category=DAO")

        # Check response status
        assert response.status_code == 200

        # Check response content
        tools = response.json()
        assert len(tools) == 1
        assert tools[0]["id"] == "dao_get_info"


@pytest.mark.asyncio
async def test_search_tools_no_results(client, mock_tools):
    """Test the /tools/search endpoint with no matching results."""
    # Mock the available_tools
    with patch("api.tools.available_tools", mock_tools):
        response = client.get("/tools/search?query=nonexistent")

        # Check response status
        assert response.status_code == 200

        # Check response content
        tools = response.json()
        assert len(tools) == 0


@pytest.mark.asyncio
async def test_search_tools_missing_query(client, mock_tools):
    """Test the /tools/search endpoint with missing query parameter."""
    # Mock the available_tools
    with patch("api.tools.available_tools", mock_tools):
        response = client.get("/tools/search")

        # Check response status
        assert response.status_code == 422  # Unprocessable Entity


@pytest.mark.asyncio
async def test_get_tools_error_handling(client):
    """Test error handling in the /tools/available endpoint."""
    # Mock get_available_tools to raise an exception
    with patch("api.tools.available_tools", side_effect=Exception("Test error")):
        response = client.get("/tools/available")

        # Check response status
        assert response.status_code == 500

        # Check error message
        error = response.json()
        assert "detail" in error
        assert "Failed to serve available tools" in error["detail"]


@pytest.mark.asyncio
async def test_get_tool_categories_error_handling(client):
    """Test error handling in the /tools/categories endpoint."""
    # Mock available_tools to raise an exception when accessed
    with patch("api.tools.available_tools", side_effect=Exception("Test error")):
        response = client.get("/tools/categories")

        # Check response status
        assert response.status_code == 500

        # Check error message
        error = response.json()
        assert "detail" in error
        assert "Failed to serve tool categories" in error["detail"]


@pytest.mark.asyncio
async def test_search_tools_error_handling(client):
    """Test error handling in the /tools/search endpoint."""
    # Mock available_tools to raise an exception when accessed
    with patch("api.tools.available_tools", side_effect=Exception("Test error")):
        response = client.get("/tools/search?query=test")

        # Check response status
        assert response.status_code == 500

        # Check error message
        error = response.json()
        assert "detail" in error
        assert "Failed to search tools" in error["detail"]
