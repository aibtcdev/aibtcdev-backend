import json
from unittest.mock import Mock, patch

import pytest

from lib.tools import Tool, extract_tool_info, get_available_tools


class MockToolInstance:
    def __init__(self, name: str, description: str, schema: Mock = None):
        self.name = name
        self.description = description
        self.args_schema = schema


class MockSchemaField:
    def __init__(self, description: str, annotation: str):
        self.description = description
        self.annotation = annotation


def test_extract_tool_info_valid():
    """Test extracting tool info with valid input."""
    # Setup mock schema
    mock_schema = Mock()
    mock_schema.model_fields = {
        "param1": MockSchemaField("Test param", "str"),
        "param2": MockSchemaField("Another param", "int"),
    }

    # Create mock tool instance
    tool_instance = MockToolInstance(
        name="category_test_tool",
        description="Test description",
        schema=mock_schema,
    )

    # Extract tool info
    result = extract_tool_info("category_test_tool", tool_instance)

    # Verify result
    assert result is not None
    assert result.id == "category_test_tool"
    assert result.name == "Test Tool"
    assert result.description == "Test description"
    assert result.category == "CATEGORY"

    # Verify parameters
    params = json.loads(result.parameters)
    assert len(params) == 2
    assert params["param1"]["type"] == "str"
    assert params["param2"]["type"] == "int"


def test_extract_tool_info_no_schema():
    """Test extracting tool info with no schema."""
    tool_instance = MockToolInstance(
        name="test_tool",
        description="Test description",
        schema=None,
    )

    result = extract_tool_info("test_tool", tool_instance)
    assert result is None


def test_extract_tool_info_error_handling():
    """Test error handling in extract_tool_info."""
    # Create a tool instance that will raise an exception
    tool_instance = Mock()
    tool_instance.args_schema = Mock(side_effect=Exception("Test error"))

    result = extract_tool_info("test_tool", tool_instance)
    assert result is None


@patch("lib.tools.initialize_tools")
def test_get_available_tools_success(mock_initialize_tools):
    """Test successfully getting available tools."""
    # Setup mock schema
    mock_schema = Mock()
    mock_schema.model_fields = {
        "param1": MockSchemaField("Test param", "str"),
    }

    # Setup mock tools
    mock_tools = {
        "category_tool1": MockToolInstance(
            name="category_tool1",
            description="Tool 1",
            schema=mock_schema,
        ),
        "category_tool2": MockToolInstance(
            name="category_tool2",
            description="Tool 2",
            schema=mock_schema,
        ),
    }

    # Configure mock
    mock_initialize_tools.return_value = mock_tools

    # Get tools
    result = get_available_tools()

    # Verify results
    assert len(result) == 2
    assert all(isinstance(tool, Tool) for tool in result)
    assert {tool.name for tool in result} == {"Tool1", "Tool2"}


@patch("lib.tools.initialize_tools")
def test_get_available_tools_error(mock_initialize_tools):
    """Test error handling in get_available_tools."""
    # Configure mock to raise an exception
    mock_initialize_tools.side_effect = Exception("Test error")

    # Verify exception is raised
    with pytest.raises(Exception):
        get_available_tools()
