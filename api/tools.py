from fastapi import APIRouter, HTTPException
from lib.logger import configure_logger
from lib.tools import Tool, get_available_tools
from starlette.responses import JSONResponse
from typing import List

# Configure logger
logger = configure_logger(__name__)

# Create the router
router = APIRouter(prefix="/tools")

# Initialize tools once at startup
available_tools = get_available_tools()


@router.get("/available", response_model=List[Tool])
async def get_tools() -> JSONResponse:
    """Get a list of available tools and their descriptions.

    Returns:
        JSONResponse: List of available tools

    Raises:
        HTTPException: If there's an error serving the tools
    """
    try:
        return JSONResponse(content=[tool.model_dump() for tool in available_tools])
    except Exception as e:
        logger.error("Failed to serve available tools", exc_info=e)
        raise HTTPException(
            status_code=500, detail=f"Failed to serve available tools: {str(e)}"
        )
