from typing import List, Optional
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import JSONResponse

from app.api.dependencies import verify_profile_from_token
from app.api.tools.models import (
    ProposeSendMessageRequest,
    VetoActionProposalRequest,
    ProposalRecommendationRequest,
    ToolResponse,
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

        # Process Twitter URLs using TwitterDataService
        from app.services.processing.twitter_data_service import twitter_data_service

        tweet_db_ids = await twitter_data_service.process_twitter_urls_from_text(
            enhanced_message
        )
        x_url = None
        tweet_id = None

        if tweet_db_ids:
            # Get the first Twitter URL for x_url field (backward compatibility)
            twitter_urls = twitter_data_service.extract_twitter_urls(enhanced_message)
            if twitter_urls:
                x_url = twitter_urls[0]
                logger.info(f"Extracted Twitter URL from proposal: {x_url}")

            # Use the first tweet database ID for the proposal
            tweet_id = tweet_db_ids[0]
            logger.info(
                f"Processed {len(tweet_db_ids)} tweets, using first tweet ID: {tweet_id}"
            )
        else:
            logger.info("No Twitter URLs found or processed in the message")

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
        )

        proposal = backend.create_proposal(proposal_content)
        logger.info(f"Created proposal record {proposal.id} for transaction {tx_id}")
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


async def _generate_metadata_for_message(message: str) -> tuple[str, str, list]:
    """Generate metadata (title, summary, tags) for a message.

    Args:
        message: The message to generate metadata for.

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
        )
        title = metadata_result.get("title", "")
        summary = metadata_result.get("summary", "")
        metadata_tags = metadata_result.get("tags", [])

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
            )
        except Exception as e:
            logger.error(f"Failed to create proposal record: {str(e)}")
            # Don't fail the entire request if proposal creation fails


def _enhance_message_with_metadata(
    message: str, title: str, metadata_tags: list
) -> str:
    """Enhance message with title and tags using structured format.

    Args:
        message: The original message.
        title: The generated title.
        metadata_tags: The generated tags.

    Returns:
        Enhanced message with metadata.
    """
    enhanced_message = message

    # Add metadata section if we have title or tags
    if title or metadata_tags:
        enhanced_message = f"{message}\n\n--- Metadata ---"

        if title:
            enhanced_message += f"\nTitle: {title}"
            logger.info(f"Enhanced message with title: {title}")

        if metadata_tags:
            tags_string = "|".join(metadata_tags)
            enhanced_message += f"\nTags: {tags_string}"
            logger.info(f"Enhanced message with tags: {metadata_tags}")
    else:
        logger.warning("No title or tags generated for the message")

    return enhanced_message


@router.post(
    "/action_proposals/propose_send_message",
    response_model=ToolResponse,
    summary="Create DAO Action Proposal",
    description="Submit a new action proposal to the DAO for member voting and governance",
    responses={
        200: {
            "description": "Action proposal created successfully",
            "model": ToolResponse,
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "DAO action proposal created successfully",
                        "data": {
                            "transaction_id": "0x1234567890abcdef",
                            "proposal_id": "12345678-1234-1234-1234-123456789abc",
                            "block_height": 12345,
                            "voting_contract": "SP1234567890ABCDEF.dao-action-proposals-voting",
                            "proposal_title": "Monthly Community Update",
                            "enhanced_message": "This is a proposal message...\n\n--- Metadata ---\nTitle: Monthly Community Update\nTags: community|update|monthly",
                            "metadata_generated": True,
                        },
                        "error": None,
                    }
                }
            },
        },
        400: {
            "description": "Invalid request parameters",
            "content": {
                "application/json": {
                    "example": {"detail": "Agent account contract is required"}
                }
            },
        },
        401: {
            "description": "Authentication failed",
            "content": {
                "application/json": {"example": {"detail": "Invalid bearer token"}}
            },
        },
        404: {
            "description": "Agent or wallet not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "No agent found for profile ID: 12345678-1234-1234-1234-123456789abc"
                    }
                }
            },
        },
        500: {
            "description": "Proposal creation failed",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to propose DAO send message action: Network error"
                    }
                }
            },
        },
    },
    tags=["dao"],
)
async def propose_dao_action_send_message(
    request: Request,
    payload: ProposeSendMessageRequest,
    profile: Profile = Depends(verify_profile_from_token),
) -> JSONResponse:
    """
    Create a new DAO action proposal for sending a message.

    This endpoint allows an authenticated user's agent to create a proposal
    for sending a message via the DAO's action proposal system. The proposal
    will be submitted for member voting and governance approval.

    **Process:**
    1. Validates the user's authentication and retrieves their agent
    2. Finds the agent's associated wallet for transaction signing
    3. Generates AI-enhanced metadata (title, summary, tags) for the proposal
    4. Creates the proposal transaction on the blockchain
    5. Records the proposal in the database for tracking
    6. Returns transaction details and proposal information

    **AI Enhancement Features:**
    - Automatic title generation from proposal content
    - Intelligent summary creation for easy understanding
    - Tag generation for categorization and search
    - Twitter URL extraction and processing
    - Metadata formatting for improved readability

    **DAO Governance Integration:**
    - Submits to the DAO's voting contract for member approval
    - Follows the DAO's governance rules and procedures
    - Tracks proposal status throughout the lifecycle
    - Enables community participation in decision-making

    **Use Cases:**
    - Announcing important DAO updates and decisions
    - Proposing new initiatives or changes
    - Communicating with the broader community
    - Documenting governance decisions and rationale

    **Authentication:** Requires Bearer token or API key authentication.
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

        # Generate metadata for the message
        title, summary, metadata_tags = await _generate_metadata_for_message(
            payload.message
        )

        # Enhance message with metadata
        enhanced_message = _enhance_message_with_metadata(
            payload.message, title, metadata_tags
        )

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
        await _create_proposal_record_if_successful(
            result,
            payload,
            enhanced_message,
            title,
            summary,
            metadata_tags,
            profile,
            wallet,
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


@router.post(
    "/action_proposals/veto_proposal",
    response_model=ToolResponse,
    summary="Veto DAO Action Proposal",
    description="Veto an existing DAO action proposal to prevent its execution",
    responses={
        200: {
            "description": "Proposal veto successful",
            "model": ToolResponse,
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "DAO action proposal vetoed successfully",
                        "data": {
                            "transaction_id": "0x1234567890abcdef",
                            "proposal_id": "12345678-1234-1234-1234-123456789abc",
                            "block_height": 12345,
                            "voting_contract": "SP1234567890ABCDEF.dao-action-proposals-voting",
                            "veto_reason": "Proposal conflicts with DAO governance rules",
                        },
                        "error": None,
                    }
                }
            },
        },
        400: {
            "description": "Invalid request parameters",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "DAO action proposal voting contract is required"
                    }
                }
            },
        },
        401: {
            "description": "Authentication failed",
            "content": {
                "application/json": {"example": {"detail": "Invalid bearer token"}}
            },
        },
        404: {
            "description": "Agent, wallet, or proposal not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "No proposal found for ID: 12345678-1234-1234-1234-123456789abc"
                    }
                }
            },
        },
        500: {
            "description": "Veto operation failed",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to veto DAO action proposal: Transaction failed"
                    }
                }
            },
        },
    },
    tags=["dao"],
)
async def veto_dao_action_proposal(
    request: Request,
    payload: VetoActionProposalRequest,
    profile: Profile = Depends(verify_profile_from_token),
) -> JSONResponse:
    """
    Veto an existing DAO action proposal.

    This endpoint allows an authenticated user's agent to veto an existing
    action proposal in the DAO's action proposal system. Vetoing prevents
    the proposal from being executed even if it has sufficient votes.

    **Process:**
    1. Validates the user's authentication and retrieves their agent
    2. Finds the agent's associated wallet for transaction signing
    3. Looks up the proposal in the database to verify it exists
    4. Executes the veto transaction on the blockchain
    5. Returns transaction details and veto confirmation

    **Veto Authority:**
    - Only authorized agents can veto proposals
    - Veto powers are defined by the DAO's governance rules
    - Typically reserved for emergency situations or rule violations
    - May require specific permissions or roles within the DAO

    **Use Cases:**
    - Preventing execution of harmful or malicious proposals
    - Stopping proposals that violate DAO governance rules
    - Emergency intervention in time-sensitive situations
    - Protecting DAO resources from misuse

    **Governance Impact:**
    - Immediately prevents proposal execution
    - May trigger additional governance procedures
    - Could require justification or community discussion
    - Maintains DAO security and rule compliance

    **Authentication:** Requires Bearer token or API key authentication.
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


@router.post(
    "/proposal_recommendations/generate",
    response_model=ToolResponse,
    summary="Generate AI Proposal Recommendation",
    description="Generate AI-powered proposal recommendations tailored to a specific DAO's needs and mission",
    responses={
        200: {
            "description": "Proposal recommendation generated successfully",
            "model": ToolResponse,
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Proposal recommendation generated successfully",
                        "data": {
                            "recommendation": {
                                "title": "Community Engagement Initiative",
                                "description": "A comprehensive proposal to increase community participation through gamification and rewards",
                                "category": "community growth",
                                "priority": "high",
                                "estimated_impact": "significant",
                                "implementation_timeline": "3-6 months",
                                "resource_requirements": [
                                    "development team",
                                    "marketing budget",
                                    "community managers",
                                ],
                                "success_metrics": [
                                    "active users",
                                    "participation rates",
                                    "community sentiment",
                                ],
                                "risks": [
                                    "user adoption",
                                    "technical complexity",
                                    "resource availability",
                                ],
                                "next_steps": [
                                    "conduct feasibility study",
                                    "gather community feedback",
                                    "prepare detailed proposal",
                                ],
                            },
                            "dao_context": {
                                "dao_name": "ExampleDAO",
                                "focus_area": "community growth",
                                "previous_proposals": 15,
                                "active_members": 500,
                            },
                            "generation_metadata": {
                                "model_used": "x-ai/grok-4",
                                "temperature": 0.1,
                                "generated_at": "2024-01-15T10:30:00Z",
                            },
                        },
                        "error": None,
                    }
                }
            },
        },
        400: {
            "description": "Invalid request parameters",
            "content": {
                "application/json": {"example": {"detail": "Invalid DAO ID format"}}
            },
        },
        401: {
            "description": "Authentication failed",
            "content": {
                "application/json": {"example": {"detail": "Invalid bearer token"}}
            },
        },
        404: {
            "description": "DAO not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "DAO with ID 12345678-1234-1234-1234-123456789abc not found"
                    }
                }
            },
        },
        500: {
            "description": "Recommendation generation failed",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to generate proposal recommendation: AI service unavailable"
                    }
                }
            },
        },
    },
    tags=["dao"],
)
async def generate_proposal_recommendation_api(
    request: Request,
    payload: ProposalRecommendationRequest,
    profile: Profile = Depends(verify_profile_from_token),
) -> JSONResponse:
    """
    Generate AI-powered proposal recommendations for a DAO.

    This endpoint provides intelligent proposal suggestions based on the DAO's
    mission, previous proposals, and current needs. It uses advanced AI to
    analyze the DAO's context and generate actionable recommendations.

    **AI Analysis Process:**
    1. Analyzes the DAO's mission and governance structure
    2. Reviews previous proposals and outcomes
    3. Considers the specified focus area and needs
    4. Generates tailored recommendations with implementation details
    5. Provides risk assessment and success metrics

    **Recommendation Categories:**
    - **Community Growth:** Engagement, onboarding, retention strategies
    - **Technical Development:** Platform improvements, new features
    - **Partnerships:** Strategic alliances, collaboration opportunities
    - **Financial Management:** Treasury optimization, funding strategies
    - **Governance:** Process improvements, rule changes

    **Generated Content:**
    - Detailed proposal title and description
    - Implementation timeline and resource requirements
    - Success metrics and key performance indicators
    - Risk assessment and mitigation strategies
    - Next steps and action items

    **Customization Options:**
    - Focus area specification for targeted recommendations
    - Specific needs input for context-aware suggestions
    - Model selection for different AI capabilities
    - Temperature control for creativity vs. precision

    **Use Cases:**
    - Discovering new opportunities for DAO improvement
    - Overcoming proposal writer's block
    - Ensuring comprehensive coverage of important topics
    - Generating ideas for community engagement

    **Authentication:** Requires Bearer token or API key authentication.
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
