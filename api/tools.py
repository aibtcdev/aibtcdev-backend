from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field  # Added import for Pydantic models
from starlette.responses import JSONResponse
import httpx  # Added import for async HTTP requests

from api.dependencies import (
    verify_profile_from_token,  # Added verify_profile_from_token
    verify_profile,
)
from backend.factory import backend  # Added backend factory
from backend.models import (  # Added Profile, AgentFilter, Wallet
    UUID,
    AgentFilter,
    ContractStatus,
    Profile,
    Proposal,
    ProposalCreate,
    ProposalType,
    Wallet,
    WalletFilter,
)
from config import config  # Added config import
from lib.logger import configure_logger
from lib.tools import Tool, get_available_tools
from services.ai.workflows.agents.proposal_metadata import (
    ProposalMetadataAgent,
)

# Import the proposal recommendation agent and metadata agent
from services.ai.workflows.agents.proposal_recommendation import (
    ProposalRecommendationAgent,
)
from services.ai.workflows.comprehensive_evaluation import (
    evaluate_proposal_comprehensive,
)
from services.ai.workflows.agents.evaluator import (
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_USER_PROMPT_TEMPLATE,
)
from tools.agent_account_action_proposals import (
    AgentAccountCreateActionProposalTool,  # Added AgentAccountCreateActionProposalTool
)
from tools.dao_ext_action_proposals import (
    VetoActionProposalTool,  # Added VetoActionProposalTool
)
from tools.faktory import (
    FaktoryExecuteBuyTool,  # Added import for Faktory tool
    FaktoryGetSbtcTool,  # Added import for Faktory sBTC faucet tool
)
from tools.wallet import WalletFundMyWalletFaucet  # Added import for wallet faucet tool

# Configure logger
logger = configure_logger(__name__)

# Create the router
router = APIRouter(prefix="/tools", tags=["tools"])

# Initialize tools once at startup
available_tools = get_available_tools()


async def _create_proposal_from_tool_result(
    tool_result: dict,
    payload: "ProposeSendMessageRequest",
    enhanced_message: str,
    title: str,
    summary: str,
    tags: List[str],
    profile: "Profile",
    wallet: "Wallet",
) -> Optional["Proposal"]:
    """Create a proposal record from successful tool execution result.

    Args:
        tool_result: The result from ProposeActionSendMessageTool execution
        payload: The original request payload
        enhanced_message: The enhanced message with title and tags
        title: The generated title for the proposal
        summary: The generated summary for the proposal
        tags: The generated tags for the proposal
        profile: The user's profile
        wallet: The agent's wallet

    Returns:
        The created proposal or None if creation failed
    """
    import re

    try:
        output = tool_result.get("output", "")
        if not output:
            logger.warning("No output in tool result")
            return None

        # Extract transaction ID from the output
        tx_id_match = re.search(
            r"Transaction broadcasted successfully: (0x[a-fA-F0-9]+)", output
        )
        if not tx_id_match:
            logger.warning("Could not extract transaction ID from tool output")
            return None

        tx_id = tx_id_match.group(1)

        # Use the voting contract from the original payload since it's no longer in the output
        voting_contract = payload.action_proposals_voting_extension

        # Find the DAO based on the voting contract or token contract
        # First try to find by the voting contract in extensions
        extensions = backend.list_extensions()
        dao_id = None

        for extension in extensions:
            if extension.contract_principal == voting_contract:
                dao_id = extension.dao_id
                break

        # If not found in extensions, try to find by token contract
        if not dao_id:
            tokens = backend.list_tokens()
            for token in tokens:
                if token.contract_principal == payload.dao_token_contract_address:
                    dao_id = token.dao_id
                    break

        if not dao_id:
            logger.warning(
                f"Could not find DAO for contracts: {voting_contract}, {payload.dao_token_contract_address}"
            )
            return None

        # Get the appropriate wallet address based on network configuration
        creator_address = (
            wallet.mainnet_address
            if config.network.network == "mainnet"
            else wallet.testnet_address
        )

        # Extract Twitter/X URL from the message content
        x_url = None
        # Look for Twitter/X URLs in the enhanced message
        twitter_url_pattern = r'https?://(?:twitter\.com|x\.com)/[^\s]+'
        twitter_match = re.search(twitter_url_pattern, enhanced_message)
        if twitter_match:
            x_url = twitter_match.group(0)
            logger.info(f"Extracted Twitter URL from proposal: {x_url}")

        # Create the proposal record
        proposal_content = ProposalCreate(
            dao_id=dao_id,
            title=title if title else "Action Proposal",
            content=enhanced_message,
            summary=summary,
            tags=tags,
            status=ContractStatus.DRAFT,  # Since transaction was successful
            contract_principal=voting_contract,
            tx_id=tx_id,
            type=ProposalType.ACTION,
            # Additional fields that might be available
            creator=creator_address or "Unknown",
            memo=payload.memo,
            x_url=x_url,  # Store the extracted Twitter URL
        )

        proposal = backend.create_proposal(proposal_content)
        logger.info(f"Created proposal record {proposal.id} for transaction {tx_id}")
        return proposal

    except Exception as e:
        logger.error(f"Error creating proposal from tool result: {str(e)}")
        return None


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
    """Request body for proposing a DAO action to send a message via agent account."""

    agent_account_contract: str = Field(
        ...,
        description="Contract principal of the agent account to use for creating the proposal.",
    )
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


class VetoActionProposalRequest(BaseModel):
    """Request body for vetoing a DAO action proposal."""

    dao_action_proposal_voting_contract: str = Field(
        ...,
        description="Contract principal where the DAO creates action proposals for voting by DAO members.",
    )
    proposal_id: str = Field(
        ...,
        description="ID of the proposal to veto.",
    )


class FundWalletFaucetRequest(BaseModel):
    """Request body for funding wallet with testnet STX tokens."""

    pass  # No parameters needed as the tool uses wallet_id from initialization


class FundSbtcFaucetRequest(BaseModel):
    """Request body for requesting testnet sBTC from Faktory faucet."""

    pass  # No parameters needed as the tool uses wallet_id from initialization


class ProposalRecommendationRequest(BaseModel):
    """Request body for getting a proposal recommendation."""

    dao_id: UUID = Field(
        ...,
        description="The ID of the DAO to generate a proposal recommendation for.",
    )
    focus_area: Optional[str] = Field(
        default="general improvement",
        description="Specific area of focus for the recommendation (e.g., 'community growth', 'technical development', 'partnerships')",
    )
    specific_needs: Optional[str] = Field(
        default="",
        description="Any specific needs or requirements to consider in the recommendation",
    )
    model_name: Optional[str] = Field(
        default="gpt-4.1",
        description="LLM model to use for generation (e.g., 'gpt-4.1', 'gpt-4o', 'gpt-3.5-turbo')",
    )
    temperature: Optional[float] = Field(
        default=0.1,
        description="Temperature for LLM generation (0.0-2.0). Lower = more focused, Higher = more creative",
        ge=0.0,
        le=2.0,
    )


class ComprehensiveEvaluationRequest(BaseModel):
    """Request body for comprehensive proposal evaluation."""

    proposal_id: str = Field(
        ...,
        description="Unique identifier for the proposal being evaluated.",
    )
    proposal_content: Optional[str] = Field(
        None,
        description="Optional proposal content to override the default proposal content.",
    )
    dao_id: Optional[UUID] = Field(
        None,
        description="Optional DAO ID for context.",
    )
    custom_system_prompt: Optional[str] = Field(
        None,
        description="Optional custom system prompt to override the default evaluation prompt.",
    )
    custom_user_prompt: Optional[str] = Field(
        None,
        description="Optional custom user prompt to override the default evaluation instructions.",
    )
    config: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Optional configuration for the evaluation agent.",
    )


class DefaultPromptsResponse(BaseModel):
    """Response body for default evaluation prompts."""

    system_prompt: str = Field(
        ...,
        description="The default system prompt used for comprehensive evaluation.",
    )
    user_prompt_template: str = Field(
        ...,
        description="The default user prompt template used for comprehensive evaluation.",
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

        # get wallet id from agent
        wallets = backend.list_wallets(WalletFilter(agent_id=agent_id))
        if not wallets:
            logger.error(f"No wallet found for agent ID: {agent_id}")
            raise HTTPException(
                status_code=404,
                detail=f"No wallet found for agent ID: {agent_id}",
            )

        wallet = wallets[0]  # Get the first wallet for this agent

        logger.info(
            f"Using agent {agent_id} for profile {profile.id} to execute Faktory buy."
        )

        tool = FaktoryExecuteBuyTool(wallet_id=wallet.id)  # Use fetched agent_id
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

        # get wallet id from agent
        wallets = backend.list_wallets(WalletFilter(agent_id=agent_id))
        if not wallets:
            logger.error(f"No wallet found for agent ID: {agent_id}")
            raise HTTPException(
                status_code=404,
                detail=f"No wallet found for agent ID: {agent_id}",
            )

        wallet = wallets[0]  # Get the first wallet for this agent

        logger.info(
            f"Using wallet {wallet.id} for profile {profile.id} to propose DAO send message action."
        )

        # Generate title, summary, and tags for the message before sending
        try:
            metadata_agent = ProposalMetadataAgent()
            metadata_state = {
                "proposal_content": payload.message,
                "dao_name": "",  # Could be enhanced to fetch DAO name if available
                "proposal_type": "action_proposal",
            }

            metadata_result = await metadata_agent.process(metadata_state)
            title = metadata_result.get("title", "")
            summary = metadata_result.get("summary", "")
            metadata_tags = metadata_result.get("tags", [])

            # Enhance message with title and tags using structured format
            enhanced_message = payload.message

            # Add metadata section if we have title or tags
            if title or metadata_tags:
                enhanced_message = f"{payload.message}\n\n--- Metadata ---"

                if title:
                    enhanced_message += f"\nTitle: {title}"
                    logger.info(f"Enhanced message with title: {title}")

                if metadata_tags:
                    tags_string = "|".join(metadata_tags)
                    enhanced_message += f"\nTags: {tags_string}"
                    logger.info(f"Enhanced message with tags: {metadata_tags}")
            else:
                logger.warning("No title or tags generated for the message")

        except Exception as e:
            logger.error(f"Failed to generate title and metadata: {str(e)}")
            # Continue with original message if enhancement fails
            enhanced_message = payload.message

        tool = AgentAccountCreateActionProposalTool(wallet_id=wallet.id)
        result = await tool._arun(
            agent_account_contract=payload.agent_account_contract,
            dao_action_proposal_voting_contract=payload.action_proposals_voting_extension,
            action_contract_to_execute=payload.action_proposal_contract_to_execute,
            dao_token_contract=payload.dao_token_contract_address,
            message_to_send=enhanced_message,
            memo=payload.memo,
        )

        logger.debug(
            f"DAO propose send message result for wallet {wallet.id} (profile {profile.id}): {result}"
        )

        # Create proposal record if tool execution was successful
        if result.get("success") and result.get("output"):
            try:
                await _create_proposal_from_tool_result(
                    result,
                    payload,
                    enhanced_message,
                    title if "title" in locals() else "",
                    summary if "summary" in locals() else "",
                    metadata_tags if "metadata_tags" in locals() else [],
                    profile,
                    wallet,
                )
            except Exception as e:
                logger.error(f"Failed to create proposal record: {str(e)}")
                # Don't fail the entire request if proposal creation fails

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


@router.post("/dao/action_proposals/veto_proposal")
async def veto_dao_action_proposal(
    request: Request,
    payload: VetoActionProposalRequest,
    profile: Profile = Depends(verify_profile_from_token),
) -> JSONResponse:
    """Veto a DAO action proposal.

    This endpoint allows an authenticated user's agent to veto an existing
    action proposal in the DAO's action proposal system.

    Args:
        request: The FastAPI request object.
        payload: The request body containing the proposal details to veto.
        profile: The authenticated user's profile.

    Returns:
        JSONResponse: The result of the veto operation.

    Raises:
        HTTPException: If there's an error, or if the agent for the profile is not found.
    """
    try:
        logger.info(
            f"DAO veto action proposal request received from {request.client.host if request.client else 'unknown'} for profile {profile.id}"
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

        # get wallet id from agent
        wallets = backend.list_wallets(WalletFilter(agent_id=agent_id))
        if not wallets:
            logger.error(f"No wallet found for agent ID: {agent_id}")
            raise HTTPException(
                status_code=404,
                detail=f"No wallet found for agent ID: {agent_id}",
            )

        wallet = wallets[0]  # Get the first wallet for this agent

        logger.info(
            f"Using wallet {wallet.id} for profile {profile.id} to veto DAO action proposal {payload.proposal_id}."
        )

        # get proposal from id
        proposal = backend.get_proposal(payload.proposal_id)
        if not proposal:
            logger.error(f"No proposal found for ID: {payload.proposal_id}")
            raise HTTPException(
                status_code=404,
                detail=f"No proposal found for ID: {payload.proposal_id}",
            )

        tool = VetoActionProposalTool(wallet_id=wallet.id)
        result = await tool._arun(
            dao_action_proposal_voting_contract=payload.dao_action_proposal_voting_contract,
            proposal_id=proposal.proposal_id,
        )

        logger.debug(
            f"DAO veto action proposal result for wallet {wallet.id} (profile {profile.id}): {result}"
        )
        return JSONResponse(content=result)

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(
            f"Failed to veto DAO action proposal for profile {profile.id}",
            exc_info=e,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to veto DAO action proposal: {str(e)}",
        )


@router.post("/dao/proposal_recommendations/generate")
async def generate_proposal_recommendation(
    request: Request,
    payload: ProposalRecommendationRequest,
    profile: Profile = Depends(verify_profile_from_token),
) -> JSONResponse:
    """Generate a proposal recommendation for a DAO.

    This endpoint allows an authenticated user to get AI-generated proposal
    recommendations based on the DAO's mission, description, and previous proposals.

    Args:
        request: The FastAPI request object.
        payload: The request body containing dao_id and optional parameters.
        profile: The authenticated user's profile.

    Returns:
        JSONResponse: The generated proposal recommendation.

    Raises:
        HTTPException: If there's an error, or if the DAO is not found.
    """
    try:
        logger.info(
            f"Proposal recommendation request received from {request.client.host if request.client else 'unknown'} for profile {profile.id} and DAO {payload.dao_id}"
        )

        # Verify that the DAO exists
        dao = backend.get_dao(payload.dao_id)
        if not dao:
            logger.error(f"DAO with ID {payload.dao_id} not found")
            raise HTTPException(
                status_code=404,
                detail=f"DAO with ID {payload.dao_id} not found",
            )

        logger.info(
            f"Generating proposal recommendation for DAO {dao.name} (ID: {payload.dao_id})"
        )

        # Create the proposal recommendation agent with model configuration
        config = {
            "model_name": "gpt-4.1",  # Use model from request or default
            "temperature": 0.9,  # Use temperature from request or default
            "streaming": True,  # Enable streaming responses
            "callbacks": [],  # Optional callback handlers
        }
        agent = ProposalRecommendationAgent(config=config)

        # Prepare state for the agent
        state = {
            "dao_id": payload.dao_id,
            "focus_area": payload.focus_area,
            "specific_needs": payload.specific_needs,
        }

        # Get the recommendation
        result = await agent.process(state)

        logger.debug(
            f"Proposal recommendation result for DAO {payload.dao_id}: {result.get('title', 'Unknown')}"
        )
        return JSONResponse(content=result)

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(
            f"Failed to generate proposal recommendation for DAO {payload.dao_id}",
            exc_info=e,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate proposal recommendation: {str(e)}",
        )


@router.post("/wallet/fund_testnet_faucet")
async def fund_wallet_with_testnet_faucet(
    request: Request,
    payload: FundWalletFaucetRequest,
    profile: Profile = Depends(verify_profile_from_token),
) -> JSONResponse:
    """Fund wallet with testnet STX tokens using the faucet.

    This endpoint allows an authenticated user's agent to request testnet STX tokens
    from the Stacks testnet faucet. This operation only works on testnet.

    Args:
        request: The FastAPI request object.
        payload: The request body (empty as no parameters are needed).
        profile: The authenticated user's profile.

    Returns:
        JSONResponse: The result of the faucet funding operation.

    Raises:
        HTTPException: If there's an error, or if the agent/wallet for the profile is not found.
    """
    try:
        logger.info(
            f"Wallet testnet faucet request received from {request.client.host if request.client else 'unknown'} for profile {profile.id}"
        )

        # Get agent from profile
        agents = backend.list_agents(AgentFilter(profile_id=profile.id))
        if not agents:
            logger.error(f"No agent found for profile ID: {profile.id}")
            raise HTTPException(
                status_code=404,
                detail=f"No agent found for profile ID: {profile.id}",
            )

        agent = agents[0]
        agent_id = agent.id

        # Get wallet from agent
        wallets = backend.list_wallets(WalletFilter(agent_id=agent_id))
        if not wallets:
            logger.error(f"No wallet found for agent ID: {agent_id}")
            raise HTTPException(
                status_code=404,
                detail=f"No wallet found for agent ID: {agent_id}",
            )

        wallet = wallets[0]  # Get the first wallet for this agent

        logger.info(
            f"Using wallet {wallet.id} for profile {profile.id} to fund with testnet faucet."
        )

        # Initialize and execute the wallet faucet tool
        tool = WalletFundMyWalletFaucet(wallet_id=wallet.id)
        result = await tool._arun()

        logger.debug(
            f"Wallet testnet faucet result for wallet {wallet.id} (profile {profile.id}): {result}"
        )
        return JSONResponse(content=result)

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(
            f"Failed to fund wallet with testnet faucet for profile {profile.id}",
            exc_info=e,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fund wallet with testnet faucet: {str(e)}",
        )


@router.post("/faktory/fund_testnet_sbtc")
async def fund_with_testnet_sbtc_faucet(
    request: Request,
    payload: FundSbtcFaucetRequest,
    profile: Profile = Depends(verify_profile_from_token),
) -> JSONResponse:
    """Request testnet sBTC from the Faktory faucet.

    This endpoint allows an authenticated user's agent to request testnet sBTC tokens
    from the Faktory faucet. This operation only works on testnet.

    Args:
        request: The FastAPI request object.
        payload: The request body (empty as no parameters are needed).
        profile: The authenticated user's profile.

    Returns:
        JSONResponse: The result of the sBTC faucet request operation.

    Raises:
        HTTPException: If there's an error, or if the agent/wallet for the profile is not found.
    """
    try:
        logger.info(
            f"Faktory testnet sBTC faucet request received from {request.client.host if request.client else 'unknown'} for profile {profile.id}"
        )

        # Get agent from profile
        agents = backend.list_agents(AgentFilter(profile_id=profile.id))
        if not agents:
            logger.error(f"No agent found for profile ID: {profile.id}")
            raise HTTPException(
                status_code=404,
                detail=f"No agent found for profile ID: {profile.id}",
            )

        agent = agents[0]
        agent_id = agent.id

        # Get wallet from agent
        wallets = backend.list_wallets(WalletFilter(agent_id=agent_id))
        if not wallets:
            logger.error(f"No wallet found for agent ID: {agent_id}")
            raise HTTPException(
                status_code=404,
                detail=f"No wallet found for agent ID: {agent_id}",
            )

        wallet = wallets[0]  # Get the first wallet for this agent

        logger.info(
            f"Using wallet {wallet.id} for profile {profile.id} to request testnet sBTC from Faktory faucet."
        )

        # Initialize and execute the Faktory sBTC faucet tool
        tool = FaktoryGetSbtcTool(wallet_id=wallet.id)
        result = await tool._arun()

        logger.debug(
            f"Faktory testnet sBTC faucet result for wallet {wallet.id} (profile {profile.id}): {result}"
        )
        return JSONResponse(content=result)

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(
            f"Failed to request testnet sBTC from Faktory faucet for profile {profile.id}",
            exc_info=e,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to request testnet sBTC from Faktory faucet: {str(e)}",
        )


@router.get("/twitter/oembed")
async def get_twitter_embed(
    request: Request,
    url: str = Query(..., description="Twitter/X.com URL to embed"),
    media_max_width: Optional[int] = Query(560, description="Maximum width for media"),
    hide_thread: Optional[bool] = Query(False, description="Hide thread"),
) -> JSONResponse:
    """Proxy endpoint for Twitter oembed API.

    This endpoint acts as a proxy to Twitter's oembed API to avoid CORS issues
    when embedding tweets in web applications.

    Args:
        request: The FastAPI request object.
        url: The Twitter/X.com URL to embed.
        media_max_width: Maximum width for embedded media (default: 560).
        hide_thread: Whether to hide the thread (default: False).

    Returns:
        JSONResponse: The oembed data from Twitter or error details.

    Raises:
        HTTPException: If there's an error with the request or Twitter API.
    """
    try:
        logger.info(
            f"Twitter oembed request received from {request.client.host if request.client else 'unknown'} for URL: {url}"
        )

        # Validate the URL format
        if not url.startswith(("https://x.com/", "https://twitter.com/")):
            logger.warning(f"Invalid Twitter URL provided: {url}")
            raise HTTPException(
                status_code=400,
                detail="Invalid Twitter URL. URL must start with https://x.com/ or https://twitter.com/",
            )

        # Make async request to Twitter oembed API
        async with httpx.AsyncClient() as client:
            oembed_url = "https://publish.twitter.com/oembed"
            params = {
                "url": url,
                "media_max_width": media_max_width,
                "partner": "",
                "hide_thread": hide_thread,
            }

            logger.debug(f"Making request to Twitter oembed API with params: {params}")

            response = await client.get(oembed_url, params=params, timeout=10.0)

            if response.status_code == 200:
                logger.info(f"Successfully retrieved oembed data for URL: {url}")
                return JSONResponse(content=response.json())
            elif response.status_code == 404:
                logger.warning(f"Twitter post not found for URL: {url}")
                raise HTTPException(status_code=404, detail="Twitter post not found")
            else:
                logger.error(f"Twitter API error {response.status_code} for URL: {url}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Twitter API error: {response.status_code}",
                )

    except httpx.TimeoutException:
        logger.error(f"Request timeout for Twitter URL: {url}")
        raise HTTPException(status_code=408, detail="Request to Twitter API timed out")
    except httpx.RequestError as e:
        logger.error(f"Request failed for Twitter URL {url}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to connect to Twitter API: {str(e)}"
        )
    except HTTPException as he:
        # Re-raise HTTPExceptions directly
        raise he
    except Exception as e:
        logger.error(f"Unexpected error for Twitter URL {url}: {str(e)}", exc_info=e)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/evaluation/default_prompts", response_model=DefaultPromptsResponse)
async def get_default_evaluation_prompts(
    request: Request,
    profile: Profile = Depends(verify_profile),
) -> JSONResponse:
    """Get the default system and user prompts for comprehensive evaluation.

    This endpoint returns the default prompts used by the comprehensive
    evaluation system. These can be used as templates for custom evaluation
    prompts in the frontend.

    Args:
        request: The FastAPI request object.
        profile: The authenticated user's profile.

    Returns:
        JSONResponse: The default system and user prompt templates.

    Raises:
        HTTPException: If there's an error retrieving the prompts.
    """
    try:
        logger.info(
            f"Default evaluation prompts request received from {request.client.host if request.client else 'unknown'} for profile {profile.id}"
        )

        # Return the default prompts
        response_data = {
            "system_prompt": DEFAULT_SYSTEM_PROMPT,
            "user_prompt_template": DEFAULT_USER_PROMPT_TEMPLATE,
        }

        logger.debug(f"Returning default evaluation prompts for profile {profile.id}")
        return JSONResponse(content=response_data)

    except Exception as e:
        logger.error(
            f"Failed to retrieve default evaluation prompts for profile {profile.id}",
            exc_info=e,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve default evaluation prompts: {str(e)}",
        )


@router.post("/evaluation/comprehensive")
async def run_comprehensive_evaluation(
    request: Request,
    payload: ComprehensiveEvaluationRequest,
    profile: Profile = Depends(verify_profile),
) -> JSONResponse:
    """Run comprehensive evaluation on a proposal with optional custom prompts.

    This endpoint allows an authenticated user to run the comprehensive
    evaluation workflow on a proposal, with optional custom system and user
    prompts to override the defaults.

    Args:
        request: The FastAPI request object.
        payload: The request body containing proposal data and optional custom prompts.
        profile: The authenticated user's profile.

    Returns:
        JSONResponse: The comprehensive evaluation results.

    Raises:
        HTTPException: If there's an error during evaluation.
    """
    try:
        logger.info(
            f"Comprehensive evaluation request received from {request.client.host if request.client else 'unknown'} for profile {profile.id}"
        )

        # Get agent from profile for context
        agents = backend.list_agents(AgentFilter(profile_id=profile.id))
        agent_id = None
        if agents:
            agent_id = str(agents[0].id)

        # Look up the proposal to get its content
        proposal = backend.get_proposal(payload.proposal_id)
        if not proposal:
            logger.error(f"Proposal with ID {payload.proposal_id} not found")
            raise HTTPException(
                status_code=404,
                detail=f"Proposal with ID {payload.proposal_id} not found",
            )

        proposal_content = payload.proposal_content or proposal.content or ""

        logger.info(
            f"Starting comprehensive evaluation for proposal {payload.proposal_id} with agent {agent_id}"
        )

        # Run the comprehensive evaluation
        result = await evaluate_proposal_comprehensive(
            proposal_id=payload.proposal_id,
            proposal_content=proposal_content,
            config=payload.config,
            dao_id=str(payload.dao_id) if payload.dao_id else None,
            agent_id=agent_id,
            profile_id=str(profile.id),
            custom_system_prompt=payload.custom_system_prompt,
            custom_user_prompt=payload.custom_user_prompt,
        )

        logger.debug(
            f"Comprehensive evaluation completed for proposal {payload.proposal_id}: {'Approved' if result.decision else 'Rejected'}"
        )
        return JSONResponse(content=result.model_dump())

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(
            f"Failed to run comprehensive evaluation for profile {profile.id}",
            exc_info=e,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to run comprehensive evaluation: {str(e)}",
        )
