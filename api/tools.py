import datetime
import json
from backend.models import Profile
from fastapi import APIRouter, HTTPException
from lib.logger import configure_logger
from starlette.responses import JSONResponse
from tools.tools_factory import initialize_tools
from typing import Dict, List

# Configure logger
logger = configure_logger(__name__)

# Create the router
router = APIRouter(prefix="/tools")

# Initialize tools for tool endpoint


def get_avaliable_tools() -> List[Dict[str, str]]:
    """Get a list of available tools and their descriptions.

    Returns:
        List[Dict[str, str]]: List of dictionaries containing tool information

    Raises:
        HTTPException: If there's an error initializing or fetching tools
    """
    logger.debug("Fetching available tools")
    try:
        tools_map = initialize_tools(None, None)

        tools_array = []
        for tool_name, tool_instance in tools_map.items():
            schema = tool_instance.args_schema
            if schema:
                # Extract category from tool name (part before first underscore)
                category = tool_name.split("_")[0].upper()

                # Extract tool name from tool instance
                tool_name_parts = tool_instance.name.split("_")[1:]
                tool_name = " ".join(tool_name_parts).title()

                # Create a tool object with required fields
                tool = {
                    "id": tool_instance.name,  # Using tool_name as id for now
                    "name": tool_name,
                    "description": tool_instance.description or "",
                    "category": category,
                    "parameters": json.dumps(
                        {
                            name: {
                                "description": field.description,
                                "type": str(field.annotation),
                            }
                            for name, field in schema.model_fields.items()
                        }
                    ),
                }
                tools_array.append(tool)

        return tools_array
    except Exception as e:
        logger.error(f"Error fetching available tools: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")


avaliable_tools = get_avaliable_tools()


@router.get("/available")
async def get_tools() -> List[Dict[str, str]]:
    """Get a list of available tools and their descriptions.

    Returns:
        List[Dict[str, str]]: List of dictionaries containing tool information

    Raises:
        HTTPException: If there's an error initializing or fetching tools
    """
    logger.debug("Fetching available tools")
    try:
        return JSONResponse(content=avaliable_tools)
    except Exception as e:
        logger.error(f"Error fetching available tools: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")
