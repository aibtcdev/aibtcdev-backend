from typing import List, Optional
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import JSONResponse

from app.api.dependencies import verify_profile_from_token
from app.api.tools.models import (
    ProposeSendMessageRequest,
    VetoActionProposalRequest,
    ProposalRecommendationRequest,
)
from app.backend.factory import backend
from app.backend.models import (
    AgentFilter,
    ContractStatus,
    Profile,
    Proposal,
    ProposalCreate,
    ProposalType,
    Wallet,
    WalletFilter,
)
from app.config import config
from app.lib.logger import configure_logger
from app.services.ai.workflows.agents.proposal_metadata import ProposalMetadataAgent
from app.services.ai.workflows.agents.proposal_recommendation import (
    ProposalRecommendationAgent,
)
from app.tools.agent_account_action_proposals import (
    AgentAccountCreateActionProposalTool,
    AgentAccountVetoActionProposalTool,
)

# Configure logger
logger = configure_logger(__name__)

# Create the router
router = APIRouter()


async def _create_proposal_from_tool_result(
    tool_result: dict,
    payload: ProposeSendMessageRequest,
    enhanced_message: str,
    title: str,
    summary: str,
    tags: List[str],
    profile: Profile,
    wallet: Wallet,
) -> Optional[Proposal]:
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
        twitter_url_pattern = r"https?://(?:twitter\.com|x\.com)/[^\s]+"
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


@router.post("/action_proposals/propose_send_message")
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


@router.post("/action_proposals/veto_proposal")
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

        tool = AgentAccountVetoActionProposalTool(wallet_id=wallet.id)
        result = await tool._arun(
            agent_account_contract=agent.account_contract,
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


@router.post("/proposal_recommendations/generate")
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
