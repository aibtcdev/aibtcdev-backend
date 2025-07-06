from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from starlette.responses import JSONResponse

from app.lib.logger import configure_logger
from app.lib.tools import Tool, get_available_tools

# Configure logger
logger = configure_logger(__name__)

# Create the router
router = APIRouter()

# Initialize tools once at startup
available_tools = get_available_tools()


@router.get("/", response_model=List[Tool])
async def get_tools(
    request: Request,
    category: Optional[str] = Query(None, description="Filter tools by category"),
) -> JSONResponse:
    """Get a list of available tools and their descriptions.

    This endpoint returns all available tools in the system. Tools can be optionally
    filtered by category.

    Args:
        request: The FastAPI request object
        category: Optional category to filter tools by

    Returns:
        JSONResponse: List of available tools matching the criteria

    Raises:
        HTTPException: If there's an error serving the tools
    """
    try:
        # Log the request
        logger.info(
            f"Tools request received from {request.client.host if request.client else 'unknown'}"
        )

        # Filter by category if provided
        if category:
            filtered_tools = [
                tool
                for tool in available_tools
                if tool.category.upper() == category.upper()
            ]
            logger.debug(
                f"Filtered tools by category '{category}', found {len(filtered_tools)} tools"
            )
            return JSONResponse(content=[tool.model_dump() for tool in filtered_tools])

        # Return all tools
        logger.debug(f"Returning all {len(available_tools)} available tools")
        return JSONResponse(content=[tool.model_dump() for tool in available_tools])
    except Exception as e:
        logger.error("Failed to serve available tools", exc_info=e)
        raise HTTPException(
            status_code=500, detail=f"Failed to serve available tools: {str(e)}"
        )


@router.get("/categories", response_model=List[str])
async def get_tool_categories() -> JSONResponse:
    """Get a list of all available tool categories.

    Returns:
        JSONResponse: List of unique tool categories

    Raises:
        HTTPException: If there's an error serving the categories
    """
    try:
        # Extract unique categories
        categories = sorted(list(set(tool.category for tool in available_tools)))
        logger.debug(f"Returning {len(categories)} tool categories")
        return JSONResponse(content=categories)
    except Exception as e:
        logger.error("Failed to serve tool categories", exc_info=e)
        raise HTTPException(
            status_code=500, detail=f"Failed to serve tool categories: {str(e)}"
        )


@router.get("/search", response_model=List[Tool])
async def search_tools(
    query: str = Query(..., description="Search query for tool name or description"),
    category: Optional[str] = Query(None, description="Filter by category"),
) -> JSONResponse:
    """Search for tools by name or description.

    This endpoint allows searching for tools based on a text query that matches
    against tool names and descriptions. Results can be optionally filtered by category.

    Args:
        query: Search query to match against tool names and descriptions
        category: Optional category to filter results by

    Returns:
        JSONResponse: List of tools matching the search criteria

    Raises:
        HTTPException: If there's an error processing the search
    """
    try:
        # Convert query to lowercase for case-insensitive matching
        query = query.lower()
        logger.debug(f"Searching tools with query: '{query}', category: '{category}'")

        # Filter tools by query and category
        filtered_tools = []
        for tool in available_tools:
            # Check if tool matches the query
            if (
                query in tool.name.lower()
                or query in tool.description.lower()
                or query in tool.id.lower()
            ):
                # If category is specified, check if tool belongs to that category
                if category and tool.category.upper() != category.upper():
                    continue

                filtered_tools.append(tool)

        logger.debug(f"Found {len(filtered_tools)} tools matching search criteria")
        return JSONResponse(content=[tool.model_dump() for tool in filtered_tools])
    except Exception as e:
        logger.error(f"Failed to search tools with query '{query}'", exc_info=e)
        raise HTTPException(status_code=500, detail=f"Failed to search tools: {str(e)}")
