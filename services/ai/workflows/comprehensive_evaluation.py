from typing import Any, Dict, Optional

from lib.logger import configure_logger
from services.ai.workflows.agents.evaluator import ComprehensiveEvaluatorAgent
from services.ai.workflows.agents.image_processing import ImageProcessingNode
from services.ai.workflows.agents.twitter_processing import TwitterProcessingNode
from services.ai.workflows.utils.models import ComprehensiveEvaluatorAgentProcessOutput

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
) -> ComprehensiveEvaluatorAgentProcessOutput:
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
        ComprehensiveEvaluatorAgentProcessOutput containing evaluation results
    """
    # Set up configuration with defaults if not provided
    if config is None:
        config = {}

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

        # Step 2: Process Twitter content (if any)
        logger.debug(
            f"[DEBUG:ComprehensiveEval:{proposal_id}] Processing Twitter content"
        )
        twitter_processor = TwitterProcessingNode(config=config)

        # Process Twitter URLs and get tweet content
        tweet_content = await twitter_processor.process(initial_state)

        # Get tweet images from state (TwitterProcessingNode updates the state)
        tweet_images = initial_state.get("tweet_images", [])

        # Combine proposal images and tweet images
        all_proposal_images = proposal_images + tweet_images

        logger.debug(
            f"[DEBUG:ComprehensiveEval:{proposal_id}] Processed Twitter content, found {len(tweet_images)} tweet images"
        )

        # Step 3: Run comprehensive evaluation
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
            "proposal_images": all_proposal_images,
            "tweet_content": tweet_content,
            "custom_system_prompt": custom_system_prompt,
            "custom_user_prompt": custom_user_prompt,
            "flags": [],
            "summaries": {},
            "token_usage": {},
        }

        # Run the comprehensive evaluation
        result: ComprehensiveEvaluatorAgentProcessOutput = await evaluator.process(
            evaluator_state
        )

        logger.info(
            f"[DEBUG:ComprehensiveEval:{proposal_id}] Evaluation complete, returning typed result"
        )

        logger.info(
            f"Completed comprehensive proposal evaluation for proposal {proposal_id}: {'Approved' if result.decision else 'Rejected'}"
        )
        return result

    except Exception as e:
        logger.error(f"Error in comprehensive proposal evaluation: {str(e)}")
        # Return a ComprehensiveEvaluatorAgentProcessOutput with error data
        from services.ai.workflows.utils.models import EvaluationCategory

        return ComprehensiveEvaluatorAgentProcessOutput(
            categories=[
                EvaluationCategory(
                    category="Error",
                    score=0,
                    weight=1.0,
                    reasoning=[
                        f"Comprehensive evaluation failed due to error: {str(e)}"
                    ],
                )
            ],
            final_score=0,
            decision=False,
            explanation=f"Comprehensive evaluation failed due to error: {str(e)}",
            flags=[f"Critical Error: {str(e)}"],
            summary="Evaluation failed due to error",
            token_usage={},
            images_processed=0,
        )
