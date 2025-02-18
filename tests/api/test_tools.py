import pytest
from api.tools import available_tools, router
from fastapi.testclient import TestClient
from lib.tools import Tool
from unittest.mock import patch


@pytest.fixture
def client():
    """Create a test client."""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def mock_tools():
    """Create mock tools for testing."""
    return [
        Tool(
            id="category_tool1",
            name="Tool1",
            description="Test tool 1",
            category="CATEGORY",
            parameters='{"param1": {"description": "Test param", "type": "str"}}',
        ),
        Tool(
            id="category_tool2",
            name="Tool2",
            description="Test tool 2",
            category="CATEGORY",
            parameters='{"param1": {"description": "Test param", "type": "str"}}',
        ),
    ]


def test_get_tools_success(client, mock_tools):
    """Test successful tools endpoint."""
    # Mock the available_tools
    with patch("api.tools.available_tools", mock_tools):
        response = client.get("/tools/available")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(tool["category"] == "CATEGORY" for tool in data)
        assert {tool["name"] for tool in data} == {"Tool1", "Tool2"}


def test_get_tools_error(client):
    """Test error handling in tools endpoint."""
    # Mock available_tools to raise an exception
    with patch("api.tools.available_tools", side_effect=Exception("Test error")):
        response = client.get("/tools/available")

        assert response.status_code == 500
        assert "Failed to serve available tools" in response.json()["detail"]
