import json
from typing import Any, List, Optional, Protocol

from pydantic import BaseModel, Field

from app.lib.logger import configure_logger
from app.tools.tools_factory import initialize_tools

# Configure logger
logger = configure_logger(__name__)


class ToolParameter(BaseModel):
    """Schema for tool parameter information."""

    description: str
    type: str


class Tool(BaseModel):
    """Schema for tool information."""

    id: str = Field(..., description="Unique identifier for the tool")
    name: str = Field(..., description="Display name of the tool")
    description: str = Field(default="", description="Tool description")
    category: str = Field(..., description="Tool category")
    parameters: str = Field(..., description="JSON string of tool parameters")


class ToolInstance(Protocol):
    args_schema: Any
    name: str
    description: Optional[str]


def extract_tool_info(tool_name: str, tool_instance: ToolInstance) -> Optional[Tool]:
    """Extract tool information from a tool instance.

    Args:
        tool_name: Name of the tool
        tool_instance: Instance of the tool

    Returns:
        Optional[Tool]: Tool information if valid schema exists, None otherwise
    """
    try:
        schema = tool_instance.args_schema
        if not schema:
            logger.debug(f"No schema found for tool: {tool_name}")
            return None

        # Extract category and name
        category = tool_name.split("_")[0].upper()
        tool_name_parts = tool_instance.name.split("_")[1:]
        display_name = " ".join(tool_name_parts).title()

        # Create parameters dictionary
        parameters = {
            name: ToolParameter(
                description=field.description, type=str(field.annotation)
            ).model_dump()
            for name, field in schema.model_fields.items()
        }

        return Tool(
            id=tool_instance.name,
            name=display_name,
            description=tool_instance.description or "",
            category=category,
            parameters=json.dumps(parameters),
        )
    except Exception as e:
        logger.error(f"Error extracting tool info for {tool_name}: {str(e)}")
        return None


def get_available_tools() -> List[Tool]:
    """Get a list of available tools and their descriptions.

    Returns:
        List[Tool]: List of available tools

    Raises:
        Exception: If there's an error initializing or fetching tools
    """
    try:
        tools_map = initialize_tools(None, None)
        tools = []

        for tool_name, tool_instance in tools_map.items():
            tool = extract_tool_info(tool_name, tool_instance)
            if tool:
                tools.append(tool)

        return tools

    except Exception as e:
        logger.error("Failed to fetch available tools", exc_info=e)
        raise
