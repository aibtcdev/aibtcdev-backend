from typing import Any, Dict, Optional

from lib.logger import configure_logger
from services.ai.workflows.agents.evaluator import ComprehensiveEvaluatorAgent
from services.ai.workflows.agents.image_processing import ImageProcessingNode
from services.ai.workflows.utils.model_factory import get_default_model_name

logger = configure_logger(__name__)


async def evaluate_proposal_comprehensive(
    proposal_id: str,
    proposal_content: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    dao_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    profile_id: Optional[str] = None,
    custom_system_prompt: Optional[str] = None,
    custom_user_prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """Evaluate a proposal using the ComprehensiveEvaluatorAgent in a single pass.

    Args:
        proposal_id: Unique identifier for the proposal
        proposal_content: Proposal content
        config: Optional configuration for the agent
        dao_id: Optional DAO ID
        agent_id: Optional agent ID
        profile_id: Optional profile ID
        custom_system_prompt: Optional custom system prompt to override default
        custom_user_prompt: Optional custom user prompt to override default

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
            "proposal_content": proposal_content,
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
            "proposal_content": proposal_content,
            "dao_id": dao_id,
            "agent_id": agent_id,
            "profile_id": profile_id,
            "proposal_images": proposal_images,
            "custom_system_prompt": custom_system_prompt,
            "custom_user_prompt": custom_user_prompt,
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

        # Determine approval based on final score and threshold
        approval = final_score >= 70

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

        # Return formatted result
        evaluation_result = {
            "proposal_id": proposal_id,
            "approve": approval,
            "overall_score": final_score,
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
            "overall_score": 0,
            "reasoning": f"Comprehensive evaluation failed due to error: {str(e)}",
            "error": str(e),
            "evaluation_type": "comprehensive_single_pass_error",
        }
