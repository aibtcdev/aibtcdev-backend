from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field  # Added import for Pydantic models
from starlette.responses import JSONResponse

from api.dependencies import (
    verify_profile_from_token,  # Added verify_profile_from_token
)
from backend.factory import backend  # Added backend factory
from backend.models import UUID, AgentFilter, Profile  # Added Profile, AgentFilter
from lib.logger import configure_logger
from lib.tools import Tool, get_available_tools
from tools.dao_ext_action_proposals import (
    ProposeActionSendMessageTool,  # Added ProposeActionSendMessageTool
)
from tools.faktory import FaktoryExecuteBuyTool  # Added import for Faktory tool

# Configure logger
logger = configure_logger(__name__)

# Create the router
router = APIRouter(prefix="/tools", tags=["tools"])

# Initialize tools once at startup
available_tools = get_available_tools()


class FaktoryBuyTokenRequest(BaseModel):
    """Request body for executing a Faktory buy order."""

    # agent_id: UUID = Field(..., description="The ID of the agent performing the action") # Removed agent_id
    btc_amount: str = Field(
        ...,
        description="Amount of BTC to spend on the purchase in standard units (e.g. 0.0004 = 0.0004 BTC or 40000 sats)",
    )
    dao_token_dex_contract_address: str = Field(
        ..., description="Contract principal where the DAO token is listed"
    )
    slippage: Optional[str] = Field(
        default="15",
        description="Slippage tolerance in basis points (default: 15, which is 0.15%)",
    )


class ProposeSendMessageRequest(BaseModel):
    """Request body for proposing a DAO action to send a message."""

    action_proposals_voting_extension: str = Field(
        ...,
        description="Contract principal where the DAO creates action proposals for voting by DAO members.",
    )
    action_proposal_contract_to_execute: str = Field(
        ...,
        description="Contract principal of the action proposal that executes sending a message.",
    )
    dao_token_contract_address: str = Field(
        ...,
        description="Contract principal of the token used by the DAO for voting.",
    )
    message: str = Field(
        ...,
        description="Message to be sent through the DAO proposal system.",
    )
    memo: Optional[str] = Field(
        None,
        description="Optional memo to include with the proposal.",
    )


@router.get("/available", response_model=List[Tool])
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


@router.post("/faktory/execute_buy")
async def execute_faktory_buy(
    request: Request,
    payload: FaktoryBuyTokenRequest,
    profile: Profile = Depends(verify_profile_from_token),  # Added auth dependency
) -> JSONResponse:
    """Execute a buy order on Faktory DEX.

    This endpoint allows an authenticated user's agent to execute a buy order
    for a specified token using BTC on the Faktory DEX.

    Args:
        request: The FastAPI request object.
        payload: The request body containing btc_amount,
                 dao_token_dex_contract_address, and optional slippage.
        profile: The authenticated user's profile.

    Returns:
        JSONResponse: The result of the buy order execution.

    Raises:
        HTTPException: If there's an error executing the buy order, or if the
                       agent for the profile is not found.
    """
    try:
        logger.info(
            f"Faktory execute buy request received from {request.client.host if request.client else 'unknown'} for profile {profile.id}"
        )

        # Get agent_id from profile_id
        agents = backend.list_agents(AgentFilter(profile_id=profile.id))
        if not agents:
            logger.error(f"No agent found for profile ID: {profile.id}")
            raise HTTPException(
                status_code=404,
                detail=f"No agent found for profile ID: {profile.id}",
            )

        agent = agents[0]  # Assuming the first agent is the one to use
        agent_id = agent.id

        logger.info(
            f"Using agent {agent_id} for profile {profile.id} to execute Faktory buy."
        )

        tool = FaktoryExecuteBuyTool(wallet_id=agent_id)  # Use fetched agent_id
        result = await tool._arun(
            btc_amount=payload.btc_amount,
            dao_token_dex_contract_address=payload.dao_token_dex_contract_address,
            slippage=payload.slippage,
        )

        logger.debug(
            f"Faktory execute buy result for agent {agent_id} (profile {profile.id}): {result}"
        )
        return JSONResponse(content=result)

    except HTTPException as he:
        # Re-raise HTTPExceptions directly
        raise he
    except Exception as e:
        logger.error(
            f"Failed to execute Faktory buy for profile {profile.id}", exc_info=e
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to execute Faktory buy order: {str(e)}",
        )


@router.post("/dao/action_proposals/propose_send_message")
async def propose_dao_action_send_message(
    request: Request,
    payload: ProposeSendMessageRequest,
    profile: Profile = Depends(verify_profile_from_token),
) -> JSONResponse:
    """Propose a DAO action to send a message.

    This endpoint allows an authenticated user's agent to create a proposal
    for sending a message via the DAO's action proposal system.

    Args:
        request: The FastAPI request object.
        payload: The request body containing the proposal details.
        profile: The authenticated user's profile.

    Returns:
        JSONResponse: The result of the proposal creation.

    Raises:
        HTTPException: If there's an error, or if the agent for the profile is not found.
    """
    try:
        logger.info(
            f"DAO propose send message request received from {request.client.host if request.client else 'unknown'} for profile {profile.id}"
        )

        agents = backend.list_agents(AgentFilter(profile_id=profile.id))
        if not agents:
            logger.error(f"No agent found for profile ID: {profile.id}")
            raise HTTPException(
                status_code=404,
                detail=f"No agent found for profile ID: {profile.id}",
            )

        agent = agents[0]
        agent_id = agent.id

        logger.info(
            f"Using agent {agent_id} for profile {profile.id} to propose DAO send message action."
        )

        tool = ProposeActionSendMessageTool(wallet_id=agent_id)
        result = await tool._arun(
            action_proposals_voting_extension=payload.action_proposals_voting_extension,
            action_proposal_contract_to_execute=payload.action_proposal_contract_to_execute,
            dao_token_contract_address=payload.dao_token_contract_address,
            message=payload.message,
            memo=payload.memo,
        )

        logger.debug(
            f"DAO propose send message result for agent {agent_id} (profile {profile.id}): {result}"
        )
        return JSONResponse(content=result)

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(
            f"Failed to propose DAO send message action for profile {profile.id}",
            exc_info=e,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to propose DAO send message action: {str(e)}",
        )
