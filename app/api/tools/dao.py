from typing import List, Optional
from uuid import UUID

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
from app.services.ai.simple_workflows import (
    generate_proposal_metadata,
    generate_proposal_recommendation,
)
from app.tools.agent_account_action_proposals import (
    AgentAccountCreateActionProposalTool,
    AgentAccountVetoActionProposalTool,
)
import uuid

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
    tweet_db_ids: List[UUID],
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
        tweet_db_ids: List of tweet database IDs that were processed

    Returns:
        The created proposal or None if creation failed
    """
    try:
        output = tool_result.get("output", "")
        if not output:
            logger.warning("No output in tool result")
            return None

        # Extract transaction ID using shared utility function
        from app.lib.utils import extract_transaction_id_from_tool_result

        tx_id = extract_transaction_id_from_tool_result(
            tool_result,
            fallback_regex_pattern=r"Transaction broadcasted successfully: (0x[a-fA-F0-9]+)",
        )

        if not tx_id:
            logger.warning("Could not extract transaction ID from tool output")
            return None

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

        # Use the already processed Twitter data
        x_url = None
        tweet_id = None

        if tweet_db_ids:
            # Get the first Twitter URL for x_url field (backward compatibility)
            from app.services.processing.twitter_data_service import (
                twitter_data_service,
            )

            twitter_urls = twitter_data_service.extract_twitter_urls(enhanced_message)
            if twitter_urls:
                x_url = twitter_urls[0]
                logger.info(f"Using Twitter URL from proposal: {x_url}")

            # Use the first tweet database ID for the proposal
            tweet_id = tweet_db_ids[0]
            logger.info(
                f"Using {len(tweet_db_ids)} processed tweets, first tweet ID: {tweet_id}"
            )
        else:
            logger.info("No tweet database IDs provided")

        # Lookup airdrop data if airdrop_txid is provided
        airdrop_id = None
        if payload.airdrop_txid:
            try:
                airdrop = backend.get_airdrop_by_tx_hash(payload.airdrop_txid)
                if airdrop:
                    # Check if this airdrop has already been used in a proposal
                    if airdrop.proposal_tx_id:
                        logger.warning(
                            f"Airdrop {airdrop.id} (tx: {payload.airdrop_txid}) has already been used in proposal with tx_id: {airdrop.proposal_tx_id}"
                        )
                        return None

                    airdrop_id = airdrop.id
                    logger.info(
                        f"Found airdrop record {airdrop_id} for tx {payload.airdrop_txid}"
                    )
                else:
                    logger.warning(
                        f"No airdrop found for transaction hash: {payload.airdrop_txid}"
                    )
            except Exception as e:
                logger.error(
                    f"Error looking up airdrop for tx {payload.airdrop_txid}: {str(e)}"
                )
        else:
            logger.info("No airdrop transaction ID provided")

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
            tweet_id=tweet_id,  # Store the linked tweet database ID
            airdrop_id=airdrop_id,  # Store the linked airdrop database ID
        )

        proposal = backend.create_proposal(proposal_content)
        logger.info(f"Created proposal record {proposal.id} for transaction {tx_id}")

        # Update airdrop record with proposal transaction ID if applicable
        if airdrop_id and tx_id:
            try:
                from app.backend.models import AirdropBase

                update_data = AirdropBase(proposal_tx_id=tx_id)
                updated_airdrop = backend.update_airdrop(airdrop_id, update_data)
                if updated_airdrop:
                    logger.info(
                        f"Updated airdrop {airdrop_id} with proposal_tx_id {tx_id}"
                    )
                else:
                    logger.warning(
                        f"Failed to update airdrop {airdrop_id} with proposal_tx_id {tx_id}"
                    )
            except Exception as e:
                logger.error(
                    f"Error updating airdrop {airdrop_id} with proposal_tx_id: {str(e)}"
                )

        return proposal

    except Exception as e:
        logger.error(f"Error creating proposal from tool result: {str(e)}")
        return None


def _validate_payload_fields(payload: ProposeSendMessageRequest) -> None:
    """Validate required payload fields for DAO action proposal.

    Args:
        payload: The request payload to validate.

    Raises:
        HTTPException: If any required field is missing.
    """
    if not payload.agent_account_contract:
        logger.error("Agent account contract is missing from payload")
        raise HTTPException(
            status_code=400,
            detail="Agent account contract is required",
        )

    if not payload.action_proposals_voting_extension:
        logger.error("Action proposals voting extension is missing from payload")
        raise HTTPException(
            status_code=400,
            detail="Action proposals voting extension is required",
        )

    if not payload.action_proposal_contract_to_execute:
        logger.error("Action proposal contract to execute is missing from payload")
        raise HTTPException(
            status_code=400,
            detail="Action proposal contract to execute is required",
        )

    if not payload.dao_token_contract_address:
        logger.error("DAO token contract address is missing from payload")
        raise HTTPException(
            status_code=400,
            detail="DAO token contract address is required",
        )


async def _generate_metadata_for_message(
    message: str, tweet_db_ids: Optional[List] = None
) -> tuple[str, str, list]:
    """Generate metadata (title, summary, tags) for a message.

    Args:
        message: The message to generate metadata for.
        tweet_db_ids: Optional list of tweet database IDs to include in metadata generation.

    Returns:
        Tuple of (title, summary, tags).
    """
    title = ""
    summary = ""
    metadata_tags = []

    try:
        metadata_result = await generate_proposal_metadata(
            proposal_content=message,
            dao_name="",  # Could be enhanced to fetch DAO name if available
            proposal_type="action_proposal",
            tweet_db_ids=tweet_db_ids,
        )

        # Extract the nested metadata from the orchestrator result
        metadata = metadata_result.get("metadata", {})
        title = metadata.get("title", "")
        summary = metadata.get("summary", "")
        metadata_tags = metadata.get("tags", [])

    except Exception as e:
        logger.error(f"Failed to generate title and metadata: {str(e)}")
        # Return empty values if enhancement fails

    return title, summary, metadata_tags


def _get_agent_and_wallet(profile: Profile) -> tuple:
    """Get agent and wallet for a profile.

    Args:
        profile: The user profile.

    Returns:
        Tuple of (agent, wallet).

    Raises:
        HTTPException: If agent or wallet is not found.
    """
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
    return agent, wallet


async def _create_proposal_record_if_successful(
    result: dict,
    payload: ProposeSendMessageRequest,
    enhanced_message: str,
    title: str,
    summary: str,
    metadata_tags: list,
    profile: Profile,
    wallet,
    tweet_db_ids: List[UUID],
) -> None:
    """Create proposal record if tool execution was successful.

    Args:
        result: The tool execution result.
        payload: The original request payload.
        enhanced_message: The enhanced message with metadata.
        title: The generated title.
        summary: The generated summary.
        metadata_tags: The generated metadata tags.
        profile: The user profile.
        wallet: The wallet used for the proposal.
        tweet_db_ids: List of tweet database IDs that were processed.
    """
    if result.get("success") and result.get("output"):
        try:
            await _create_proposal_from_tool_result(
                result,
                payload,
                enhanced_message,
                title,
                summary,
                metadata_tags,
                profile,
                wallet,
                tweet_db_ids,
            )
        except Exception as e:
            logger.error(f"Failed to create proposal record: {str(e)}")
            # Don't fail the entire request if proposal creation fails


def _enhance_message_with_metadata(
    message: str, title: str, metadata_tags: list, airdrop_txid: Optional[str] = None
) -> str:
    """Enhance message with title, tags, and optional airdrop transaction ID using structured format.

    Args:
        message: The original message.
        title: The generated title.
        metadata_tags: The generated tags.
        airdrop_txid: Optional transaction ID of an associated airdrop.

    Returns:
        Enhanced message with metadata.
    """
    enhanced_message = message

    # Add metadata section if we have title, tags, or airdrop_txid
    if title or metadata_tags or airdrop_txid:
        enhanced_message = f"{message}\n\n--- Metadata ---"

        if title:
            enhanced_message += f"\nTitle: {title}"
            logger.info(f"Enhanced message with title: {title}")

        if metadata_tags:
            tags_string = "|".join(metadata_tags)
            enhanced_message += f"\nTags: {tags_string}"
            logger.info(f"Enhanced message with tags: {metadata_tags}")

        if airdrop_txid:
            enhanced_message += f"\nAirdrop Transaction ID: {airdrop_txid}"
            logger.info(f"Enhanced message with airdrop transaction ID: {airdrop_txid}")
    else:
        logger.warning(
            "No title, tags, or airdrop transaction ID generated for the message"
        )

    return enhanced_message


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

        # Get agent and wallet for the profile
        agent, wallet = _get_agent_and_wallet(profile)

        logger.info(
            f"Using wallet {wallet.id} for profile {profile.id} to propose DAO send message action."
        )

        # Validate required payload fields
        _validate_payload_fields(payload)

        # Validate airdrop if provided - check if it's already been used
        if payload.airdrop_txid:
            try:
                airdrop = backend.get_airdrop_by_tx_hash(payload.airdrop_txid)
                if airdrop and airdrop.proposal_tx_id:
                    logger.warning(
                        f"Airdrop transaction {payload.airdrop_txid} has already been used in proposal with tx_id: {airdrop.proposal_tx_id}"
                    )
                    raise HTTPException(
                        status_code=400,
                        detail=f"Airdrop transaction {payload.airdrop_txid} has already been used in another proposal",
                    )
                elif not airdrop:
                    logger.warning(
                        f"Airdrop transaction {payload.airdrop_txid} not found"
                    )
                    raise HTTPException(
                        status_code=404,
                        detail=f"Airdrop transaction {payload.airdrop_txid} not found",
                    )
            except HTTPException:
                raise
            except Exception as e:
                logger.error(
                    f"Error validating airdrop {payload.airdrop_txid}: {str(e)}"
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"Error validating airdrop: {str(e)}",
                )

        # Step 1: Extract Twitter information and save to tweet table
        tweet_db_ids = []
        if payload.message:
            from app.services.processing.twitter_data_service import (
                twitter_data_service,
            )

            tweet_db_ids = await twitter_data_service.process_twitter_urls_from_text(
                payload.message
            )
            logger.info(
                f"Processed {len(tweet_db_ids)} Twitter URLs from message for profile {profile.id}"
            )

        # Step 2: Generate metadata given the message and the tweet_id information
        title, summary, metadata_tags = await _generate_metadata_for_message(
            payload.message, tweet_db_ids
        )

        # Step 3: Enhance message with metadata
        enhanced_message = _enhance_message_with_metadata(
            payload.message, title, metadata_tags, payload.airdrop_txid
        )

        # Step 4: Deploy the information on chain
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

        # Step 5: Create proposal record if tool execution was successful
        await _create_proposal_record_if_successful(
            result,
            payload,
            enhanced_message,
            title,
            summary,
            metadata_tags,
            profile,
            wallet,
            tweet_db_ids,
        )

        return JSONResponse(content=result)

    except HTTPException:
        raise
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
        proposal = backend.get_proposal(uuid.UUID(payload.proposal_id))
        if not proposal:
            logger.error(f"No proposal found for ID: {payload.proposal_id}")
            raise HTTPException(
                status_code=404,
                detail=f"No proposal found for ID: {payload.proposal_id}",
            )

        # Validate required fields before calling _arun
        if not agent.account_contract:
            logger.error(f"Agent account contract is missing for agent ID: {agent_id}")
            raise HTTPException(
                status_code=400,
                detail="Agent account contract is not set",
            )

        if not proposal.proposal_id:
            logger.error(f"Proposal ID is missing for proposal: {payload.proposal_id}")
            raise HTTPException(
                status_code=400,
                detail="Proposal ID is not set in the proposal record",
            )

        if not payload.dao_action_proposal_voting_contract:
            logger.error("DAO action proposal voting contract is missing from payload")
            raise HTTPException(
                status_code=400,
                detail="DAO action proposal voting contract is required",
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
async def generate_proposal_recommendation_api(
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

        # Get the recommendation
        result = await generate_proposal_recommendation(
            dao_id=payload.dao_id,
            focus_area=payload.focus_area,
            specific_needs=payload.specific_needs,
        )

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
