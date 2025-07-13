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


@router.get(
    "/",
    response_model=List[Tool],
    summary="Get Available Tools",
    description="Retrieve a list of all available tools in the system with optional category filtering",
    responses={
        200: {
            "description": "List of available tools",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": "faktory_execute_buy",
                            "name": "Execute Faktory Buy",
                            "description": "Execute a buy order on Faktory DEX",
                            "category": "trading",
                            "parameters": {
                                "btc_amount": "string",
                                "dao_token_dex_contract_address": "string",
                                "slippage": "string (optional)",
                            },
                        },
                        {
                            "id": "dao_create_proposal",
                            "name": "Create DAO Proposal",
                            "description": "Create a new DAO action proposal",
                            "category": "dao",
                            "parameters": {
                                "message": "string",
                                "agent_account_contract": "string",
                            },
                        },
                    ]
                }
            },
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {"detail": "Failed to serve available tools"}
                }
            },
        },
    },
)
async def get_tools(
    request: Request,
    category: Optional[str] = Query(
        None,
        description="Filter tools by category (e.g., 'trading', 'dao', 'wallet')",
        example="trading",
    ),
) -> JSONResponse:
    """
    Get a list of available tools and their descriptions.

    This endpoint returns all available tools in the system. Tools can be optionally
    filtered by category to narrow down the results.

    **Categories include:**
    - `trading`: Financial and DEX trading operations
    - `dao`: DAO management and proposal operations
    - `wallet`: Wallet management and funding operations
    - `evaluation`: AI-powered analysis and evaluation
    - `social`: Social media integrations
    - `agent-account`: Agent account management

    **Authentication Required:** Yes (Bearer token or API key)
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


@router.get(
    "/categories",
    response_model=List[str],
    summary="Get Tool Categories",
    description="Retrieve a list of all available tool categories for filtering purposes",
    responses={
        200: {
            "description": "List of unique tool categories",
            "content": {
                "application/json": {
                    "example": [
                        "trading",
                        "dao",
                        "wallet",
                        "evaluation",
                        "social",
                        "agent-account",
                    ]
                }
            },
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {"detail": "Failed to serve tool categories"}
                }
            },
        },
    },
)
async def get_tool_categories() -> JSONResponse:
    """
    Get a list of all available tool categories.

    Returns a sorted list of unique categories that can be used to filter tools
    in the `/tools/` endpoint. This is useful for building category-based UI filters.

    **Authentication Required:** Yes (Bearer token or API key)
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


@router.get(
    "/search",
    response_model=List[Tool],
    summary="Search Tools",
    description="Search for tools by name or description with optional category filtering",
    responses={
        200: {
            "description": "List of tools matching the search criteria",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": "faktory_execute_buy",
                            "name": "Execute Faktory Buy",
                            "description": "Execute a buy order on Faktory DEX",
                            "category": "trading",
                            "parameters": {
                                "btc_amount": "string",
                                "dao_token_dex_contract_address": "string",
                            },
                        }
                    ]
                }
            },
        },
        400: {
            "description": "Bad request - missing query parameter",
            "content": {
                "application/json": {
                    "example": {"detail": "Query parameter is required"}
                }
            },
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {"example": {"detail": "Failed to search tools"}}
            },
        },
    },
)
async def search_tools(
    query: str = Query(
        ...,
        description="Search query to match against tool names and descriptions",
        example="faktory",
        min_length=1,
    ),
    category: Optional[str] = Query(
        None, description="Optional category to filter results by", example="trading"
    ),
) -> JSONResponse:
    """
    Search for tools by name or description.

    This endpoint allows searching for tools based on a text query that matches
    against tool names and descriptions. Results can be optionally filtered by category
    for more targeted searches.

    **Search is case-insensitive** and matches partial strings in:
    - Tool names
    - Tool descriptions
    - Tool IDs

    **Authentication Required:** Yes (Bearer token or API key)
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
