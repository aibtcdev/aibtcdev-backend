from typing import Any, Dict, Optional
from uuid import UUID

from backend.factory import backend
from backend.models import Profile
from lib.logger import configure_logger
from services.ai.workflows.agents.evaluator import ComprehensiveEvaluatorAgent
from services.ai.workflows.agents.image_processing import ImageProcessingNode
from services.ai.workflows.utils.model_factory import get_default_model_name
from tools.dao_ext_action_proposals import VoteOnActionProposalTool
from tools.tools_factory import filter_tools_by_names, initialize_tools

logger = configure_logger(__name__)


async def evaluate_proposal_comprehensive(
    proposal_id: str,
    proposal_data: str,
    config: Optional[Dict[str, Any]] = None,
    dao_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    profile_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Evaluate a proposal using the ComprehensiveEvaluatorAgent in a single pass.

    Args:
        proposal_id: Unique identifier for the proposal
        proposal_data: Proposal content
        config: Optional configuration for the agent
        dao_id: Optional DAO ID
        agent_id: Optional agent ID
        profile_id: Optional profile ID

    Returns:
        Dictionary containing evaluation results
    """
    # Set up configuration with defaults if not provided
    if config is None:
        config = {}

    # Use model name from config or default
    model_name = config.get("model_name", get_default_model_name())

    try:
        logger.info(
            f"Starting comprehensive proposal evaluation for proposal {proposal_id}"
        )

        # Step 1: Process images first (if any)
        logger.debug(f"[DEBUG:ComprehensiveEval:{proposal_id}] Processing images")
        image_processor = ImageProcessingNode(config=config)
        initial_state = {
            "proposal_id": proposal_id,
            "proposal_data": proposal_data,
            "dao_id": dao_id,
            "agent_id": agent_id,
            "profile_id": profile_id,
        }

        # Process images - the result is a list of processed image dictionaries
        proposal_images = await image_processor.process(initial_state)

        # The ImageProcessingNode also updates the state automatically via BaseCapabilityMixin
        # but we use the direct return value for clarity and immediate access

        logger.debug(
            f"[DEBUG:ComprehensiveEval:{proposal_id}] Processed {len(proposal_images)} images"
        )

        # Step 2: Run comprehensive evaluation
        logger.debug(
            f"[DEBUG:ComprehensiveEval:{proposal_id}] Starting comprehensive evaluation"
        )

        # Create the comprehensive evaluator
        evaluator = ComprehensiveEvaluatorAgent(config)

        # Create state for the evaluator
        evaluator_state = {
            "proposal_id": proposal_id,
            "proposal_data": proposal_data,
            "dao_id": dao_id,
            "agent_id": agent_id,
            "profile_id": profile_id,
            "proposal_images": proposal_images,
            "flags": [],
            "summaries": {},
            "token_usage": {},
        }

        # Run the comprehensive evaluation
        result = await evaluator.process(evaluator_state)

        logger.info(
            f"[DEBUG:ComprehensiveEval:{proposal_id}] Evaluation complete, result keys: {list(result.keys())}"
        )

        # Extract results from the comprehensive evaluation
        # The comprehensive evaluator returns all scores in the result
        core_score = result.get("core_score", 0)
        historical_score = result.get("historical_score", 0)
        financial_score = result.get("financial_score", 0)
        social_score = result.get("social_score", 0)
        final_score = result.get("final_score", 0)

        # Get decision and explanation
        final_decision = result.get("decision", "Undecided")
        final_explanation = result.get("explanation", "No explanation provided.")
        confidence = result.get("confidence", 0.7)

        # Determine approval
        approval = final_decision.lower() == "approve"

        # Get token usage (single agent usage)
        token_usage_data = result.get("token_usage", {})
        total_token_usage = {
            "input_tokens": token_usage_data.get("input_tokens", 0),
            "output_tokens": token_usage_data.get("output_tokens", 0),
            "total_tokens": token_usage_data.get("total_tokens", 0),
        }

        # Get summaries and flags
        summaries = {
            "core_score": result.get("core_summary", "No core summary available."),
            "financial_score": result.get(
                "financial_summary", "No financial summary available."
            ),
            "historical_score": result.get(
                "historical_summary", "No historical summary available."
            ),
            "social_score": result.get(
                "social_summary", "No social summary available."
            ),
        }

        flags = result.get("all_flags", [])

        # Return formatted result (compatible with existing format)
        evaluation_result = {
            "proposal_id": proposal_id,
            "approve": approval,
            "confidence_score": confidence,
            "reasoning": final_explanation,
            "scores": {
                "core": core_score,
                "historical": historical_score,
                "financial": financial_score,
                "social": social_score,
                "final": final_score,
            },
            "flags": flags,
            "summaries": summaries,
            "token_usage": total_token_usage,
            "model_name": model_name,
            "workflow_step": "comprehensive_evaluation_complete",
            "images_processed": len(proposal_images),
            "evaluation_type": "comprehensive_single_pass",
        }

        logger.info(
            f"Completed comprehensive proposal evaluation for proposal {proposal_id}: {final_decision}"
        )
        return evaluation_result

    except Exception as e:
        logger.error(f"Error in comprehensive proposal evaluation: {str(e)}")
        return {
            "proposal_id": proposal_id,
            "approve": False,
            "confidence_score": 0.1,
            "reasoning": f"Comprehensive evaluation failed due to error: {str(e)}",
            "error": str(e),
            "evaluation_type": "comprehensive_single_pass_error",
        }


def get_proposal_evaluation_tools(
    profile: Optional[Profile] = None, agent_id: Optional[UUID] = None
):
    """Get tools for proposal evaluation.

    Args:
        profile: Optional user profile
        agent_id: Optional agent ID

    Returns:
        List of available tools
    """
    tool_names = ["vote_on_action_proposal"]
    tools = initialize_tools(profile, agent_id)
    return filter_tools_by_names(tools, tool_names)


async def evaluate_and_vote_on_proposal_comprehensive(
    proposal_id: UUID,
    wallet_id: Optional[UUID] = None,
    agent_id: Optional[UUID] = None,
    auto_vote: bool = True,
    confidence_threshold: float = 0.7,
    dao_id: Optional[UUID] = None,
    debug_level: int = 0,  # 0=normal, 1=verbose, 2=very verbose
) -> Dict:
    """Evaluate a proposal using comprehensive evaluator and optionally vote on it.

    Args:
        proposal_id: Proposal ID
        wallet_id: Optional wallet ID
        agent_id: Optional agent ID
        auto_vote: Whether to automatically vote based on evaluation
        confidence_threshold: Confidence threshold for auto-voting
        dao_id: Optional DAO ID
        debug_level: Debug level (0=normal, 1=verbose, 2=very verbose)

    Returns:
        Evaluation and voting results
    """
    # Get proposal details
    logger.info(f"Retrieving proposal details for {proposal_id}")

    try:
        proposal = backend.get_proposal(proposal_id=proposal_id)

        if not proposal:
            logger.error(f"Proposal {proposal_id} not found")
            return {"error": f"Proposal {proposal_id} not found"}

        # Set up config based on debug level
        config = {
            "debug_level": debug_level,
        }

        if debug_level >= 1:
            # For verbose debugging, customize agent settings
            config["approval_threshold"] = 70
            config["veto_threshold"] = 30
            config["consensus_threshold"] = 10

        # Extract context for personalized evaluation
        evaluation_dao_id = str(proposal.dao_id) if proposal.dao_id else None
        evaluation_agent_id = str(agent_id) if agent_id else None

        # Get profile_id from wallet if available
        evaluation_profile_id = None
        if wallet_id:
            wallet = backend.get_wallet(wallet_id)
            if wallet and wallet.profile_id:
                evaluation_profile_id = str(wallet.profile_id)

        # Evaluate the proposal using comprehensive evaluator
        logger.info(f"Starting comprehensive evaluation of proposal {proposal_id}")
        evaluation_result = await evaluate_proposal_comprehensive(
            proposal_id=str(proposal_id),
            proposal_data=proposal.content,
            config=config,
            dao_id=evaluation_dao_id,
            agent_id=evaluation_agent_id,
            profile_id=evaluation_profile_id,
        )

        # Check if auto voting is enabled
        if auto_vote:
            if "error" in evaluation_result:
                logger.error(
                    f"Skipping voting due to evaluation error: {evaluation_result['error']}"
                )
                return {
                    "evaluation": evaluation_result,
                    "vote_result": None,
                    "message": "Skipped voting due to evaluation error",
                }

            # Check if the confidence score meets the threshold
            confidence_score = evaluation_result.get("confidence_score", 0)

            if confidence_score >= confidence_threshold:
                # Get the vote decision
                approve = evaluation_result.get("approve", False)
                vote_direction = "for" if approve else "against"

                logger.info(
                    f"Auto-voting {vote_direction} proposal {proposal_id} with confidence {confidence_score}"
                )

                # Get the profile by finding the wallet first
                profile = None
                if wallet_id:
                    wallet = backend.get_wallet(wallet_id)
                    if wallet and wallet.profile_id:
                        profile = backend.get_profile(wallet.profile_id)
                elif agent_id:
                    # Try to find wallet by agent_id
                    from backend.models import WalletFilter

                    wallets = backend.list_wallets(WalletFilter(agent_id=agent_id))
                    if wallets and wallets[0].profile_id:
                        profile = backend.get_profile(wallets[0].profile_id)
                tools = get_proposal_evaluation_tools(profile, agent_id)
                vote_tool = next(
                    (t for t in tools if isinstance(t, VoteOnActionProposalTool)), None
                )

                if vote_tool:
                    try:
                        # Execute the vote
                        vote_result = await vote_tool.execute(
                            proposal_id=str(proposal_id),
                            vote=vote_direction,
                            wallet_id=str(wallet_id) if wallet_id else None,
                            dao_id=str(dao_id) if dao_id else None,
                        )

                        logger.info(f"Vote result: {vote_result}")

                        return {
                            "evaluation": evaluation_result,
                            "vote_result": vote_result,
                            "message": f"Voted {vote_direction} with confidence {confidence_score:.2f}",
                        }
                    except Exception as e:
                        logger.error(f"Error voting on proposal: {str(e)}")
                        return {
                            "evaluation": evaluation_result,
                            "vote_result": None,
                            "error": f"Error voting on proposal: {str(e)}",
                        }
                else:
                    logger.error("Vote tool not available")
                    return {
                        "evaluation": evaluation_result,
                        "vote_result": None,
                        "error": "Vote tool not available",
                    }
            else:
                logger.info(
                    f"Skipping auto-vote due to low confidence: {confidence_score} < {confidence_threshold}"
                )
                return {
                    "evaluation": evaluation_result,
                    "vote_result": None,
                    "message": f"Skipped voting due to low confidence: {confidence_score:.2f} < {confidence_threshold}",
                }
        else:
            logger.info("Auto-voting disabled, returning evaluation only")
            return {
                "evaluation": evaluation_result,
                "vote_result": None,
                "message": "Auto-voting disabled",
            }

    except Exception as e:
        logger.error(f"Error in evaluate_and_vote_on_proposal_comprehensive: {str(e)}")
        return {"error": f"Failed to evaluate proposal: {str(e)}"}
