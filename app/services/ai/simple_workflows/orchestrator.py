"""Orchestrator for simple workflows.

This module provides the main public API facade for the simplified workflow system,
orchestrating the various processors and providing a clean interface for callers.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID
import traceback

# from app.backend.factory import backend
from app.lib.logger import configure_logger
from app.services.ai.simple_workflows.evaluation_openrouter_v2 import (
    evaluate_proposal_openrouter,
    EvaluationOutput,
)
from app.services.ai.simple_workflows.metadata import (
    generate_proposal_metadata as _generate_metadata,
)
from app.services.ai.simple_workflows.processors import process_media, process_tweets

# from app.services.ai.simple_workflows.prompts.loader import load_prompt
from app.services.ai.simple_workflows.recommendation import (
    generate_proposal_recommendation as _generate_recommendation,
)
from app.services.ai.simple_workflows.streaming import create_streaming_setup

logger = configure_logger(__name__)


async def evaluate_proposal_strict(
    proposal_id: UUID | str,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    reasoning: Optional[bool] = None,
) -> Optional[EvaluationOutput]:
    """Evaluates a proposal using OpenRouter.

    Args:
        proposal_id: Required proposal UUID for evaluation
        model: Optional model override
        temperature: Optional temperature override

    Returns:
        Dictionary containing comprehensive evaluation results or None.
    """

    try:
        evaluation_result = await evaluate_proposal_openrouter(
            proposal_id=proposal_id,
            model=model,
            temperature=temperature,
            reasoning=reasoning,
        )

        if evaluation_result is None:
            logger.error("Evaluation returned None")
            return None

        return evaluation_result

    except Exception as e:
        logger.error(
            "Error during evaluation proposal strict",
            extra={
                "error": str(e),
                "proposal_id": str(proposal_id),
                "traceback": traceback.format_exc(),
            },
        )
        return None


async def evaluate_proposal_comprehensive(
    dao_id: Optional[UUID] = None,
    proposal_id: Optional[UUID] = None,
    model: Optional[str] = None,
    temperature: float = 0.7,
) -> Dict[str, Any]:
    """Evaluate a proposal comprehensively using OpenRouter.

    Args:
        proposal_id: Required proposal UUID for evaluation
        tweet_db_ids: Optional list of additional tweet database IDs (not used in v2)
        custom_system_prompt: Optional custom system prompt (not used in v2)
        custom_user_prompt: Optional custom user prompt (not used in v2)
        streaming: Whether to enable streaming (not supported in v2)
        model: Optional model override (e.g., 'x-ai/grok-4-fast')
        temperature: Generation temperature (default 0.7)

    Returns:
        Dictionary containing comprehensive evaluation results
    """
    proposal_id_str = str(proposal_id) if proposal_id else "unknown"
    logger.info(
        f"[Orchestrator] Starting comprehensive evaluation for proposal {proposal_id_str}"
    )

    if not proposal_id:
        logger.error("[Orchestrator] proposal_id is required for evaluation")
        return {
            "error": "proposal_id is required",
            "evaluation": {
                "current_order": {"score": 0, "reason": "", "evidence": []},
                "mission": {"score": 0, "reason": "", "evidence": []},
                "value": {"score": 0, "reason": "", "evidence": []},
                "values": {"score": 0, "reason": "", "evidence": []},
                "originality": {"score": 0, "reason": "", "evidence": []},
                "clarity": {"score": 0, "reason": "", "evidence": []},
                "safety": {"score": 0, "reason": "", "evidence": []},
                "growth": {"score": 0, "reason": "", "evidence": []},
                "final_score": 0,
                "confidence": 0.0,
                "decision": "REJECT",
                "failed": ["Missing proposal_id"],
            },
            "processing_metadata": {
                "proposal_id": proposal_id_str,
                "dao_id": str(dao_id) if dao_id else None,
                "images_processed": 0,
                "tweet_images_processed": 0,
                "total_images": 0,
                "tweets_processed": 0,
                "tweet_content_length": 0,
                "streaming_enabled": False,
            },
        }

    try:
        # Run evaluation using OpenRouter v2
        logger.debug(f"[Orchestrator:{proposal_id_str}] Running OpenRouter evaluation")
        evaluation_result = await evaluate_proposal_openrouter(
            proposal_id=proposal_id_str,
            model=model,
            temperature=temperature,
        )

        if not evaluation_result:
            logger.error(f"[Orchestrator:{proposal_id_str}] Evaluation returned None")
            return {
                "error": "Evaluation failed",
                "evaluation": {
                    "current_order": {"score": 0, "reason": "", "evidence": []},
                    "mission": {"score": 0, "reason": "", "evidence": []},
                    "value": {"score": 0, "reason": "", "evidence": []},
                    "values": {"score": 0, "reason": "", "evidence": []},
                    "originality": {"score": 0, "reason": "", "evidence": []},
                    "clarity": {"score": 0, "reason": "", "evidence": []},
                    "safety": {"score": 0, "reason": "", "evidence": []},
                    "growth": {"score": 0, "reason": "", "evidence": []},
                    "final_score": 0,
                    "confidence": 0.0,
                    "decision": "REJECT",
                    "failed": ["Evaluation failed"],
                },
                "processing_metadata": {
                    "proposal_id": proposal_id_str,
                    "dao_id": str(dao_id) if dao_id else None,
                    "images_processed": 0,
                    "tweet_images_processed": 0,
                    "total_images": 0,
                    "tweets_processed": 0,
                    "tweet_content_length": 0,
                    "streaming_enabled": False,
                },
            }

        # Convert to dict for response
        result = {
            "evaluation": evaluation_result.model_dump(),
            "processing_metadata": {
                "proposal_id": proposal_id_str,
                "dao_id": str(dao_id) if dao_id else None,
                "images_processed": len(evaluation_result.current_order.evidence)
                if hasattr(evaluation_result.current_order, "evidence")
                else 0,
                "tweet_images_processed": 0,
                "total_images": 0,
                "tweets_processed": 0,
                "tweet_content_length": 0,
                "streaming_enabled": False,
            },
        }

        logger.info(
            f"[Orchestrator] Completed comprehensive evaluation for proposal {proposal_id_str}"
        )
        return result

    except Exception as e:
        logger.error(
            f"[Orchestrator] Error in comprehensive evaluation for proposal {proposal_id_str}: {str(e)}",
            exc_info=True,
        )
        return {
            "error": str(e),
            "evaluation": {
                "current_order": {"score": 0, "reason": "", "evidence": []},
                "mission": {"score": 0, "reason": "", "evidence": []},
                "value": {"score": 0, "reason": "", "evidence": []},
                "values": {"score": 0, "reason": "", "evidence": []},
                "originality": {"score": 0, "reason": "", "evidence": []},
                "clarity": {"score": 0, "reason": "", "evidence": []},
                "safety": {"score": 0, "reason": "", "evidence": []},
                "growth": {"score": 0, "reason": "", "evidence": []},
                "final_score": 0,
                "confidence": 0.0,
                "decision": "REJECT",
                "failed": [f"Critical Error: {str(e)}"],
            },
            "processing_metadata": {
                "proposal_id": proposal_id_str,
                "dao_id": str(dao_id) if dao_id else None,
                "images_processed": 0,
                "tweet_images_processed": 0,
                "total_images": 0,
                "tweets_processed": 0,
                "tweet_content_length": 0,
                "streaming_enabled": False,
            },
        }


async def generate_proposal_metadata(
    proposal_content: str,
    dao_name: str = "",
    proposal_type: str = "",
    tweet_db_ids: Optional[List[UUID]] = None,
    streaming: bool = False,
) -> Dict[str, Any]:
    """Generate metadata for a proposal with image and tweet processing.

    Args:
        proposal_content: The proposal content
        dao_name: Name of the DAO
        proposal_type: Type of the proposal
        tweet_db_ids: Optional list of tweet database IDs to process
        streaming: Whether to enable streaming

    Returns:
        Dictionary containing generated metadata
    """
    logger.info(
        f"[Orchestrator] Generating metadata for proposal (content length: {len(proposal_content)})"
    )

    try:
        # Set up streaming if requested
        callbacks = None
        if streaming:
            callback_handler, queue = create_streaming_setup()
            callbacks = [callback_handler]

        # Step 1: Process images from proposal content
        images = await process_media(proposal_content, "metadata_generation")
        logger.debug(
            f"[Orchestrator] Found {len(images)} images for metadata generation"
        )

        # Step 2: Process tweets if provided
        tweet_content = ""
        tweet_images = []
        if tweet_db_ids:
            logger.debug(
                f"[Orchestrator] Processing {len(tweet_db_ids)} tweets for metadata"
            )
            tweet_content, tweet_images = await process_tweets(
                tweet_db_ids, "metadata_generation"
            )
            logger.debug(
                f"[Orchestrator] Found {len(tweet_images)} tweet images for metadata and {len(tweet_content)} chars of tweet content"
            )

        # Step 3: Combine all images
        all_images = images + tweet_images

        # Step 4: Combine proposal content with tweet content
        # Escape curly braces in proposal content to prevent template parsing issues
        escaped_proposal_content = proposal_content.replace("{", "{{").replace(
            "}", "}}"
        )

        combined_content = escaped_proposal_content
        if tweet_content:
            # Also escape curly braces in tweet content to prevent template parsing issues
            escaped_tweet_content = tweet_content.replace("{", "{{").replace("}", "}}")
            combined_content = f"{escaped_proposal_content}\n\n--- Referenced Tweets ---\n{escaped_tweet_content}"

        # Step 5: Generate metadata
        metadata_result = await _generate_metadata(
            proposal_content=combined_content,
            dao_name=dao_name,
            proposal_type=proposal_type,
            images=all_images,
            callbacks=callbacks,
        )

        # Step 6: Add processing metadata
        result = {
            "metadata": metadata_result,
            "processing_metadata": {
                "images_processed": len(images),
                "tweet_images_processed": len(tweet_images),
                "total_images": len(all_images),
                "tweets_processed": len(tweet_db_ids) if tweet_db_ids else 0,
                "tweet_content_length": len(tweet_content),
                "streaming_enabled": streaming,
            },
        }

        # Add streaming queue if enabled
        if streaming and callbacks:
            result["streaming_queue"] = callbacks[0].queue

        logger.info("[Orchestrator] Completed metadata generation")
        return result

    except Exception as e:
        logger.error(f"[Orchestrator] Error in metadata generation: {str(e)}")
        return {
            "error": str(e),
            "metadata": {
                "error": str(e),
                "title": "",
                "summary": f"Error generating metadata: {str(e)}",
                "tags": [],
            },
            "processing_metadata": {
                "images_processed": 0,
                "tweet_images_processed": 0,
                "total_images": 0,
                "tweets_processed": 0,
                "tweet_content_length": 0,
                "streaming_enabled": streaming,
            },
        }


async def generate_proposal_recommendation(
    dao_id: UUID,
    focus_area: str = "",
    specific_needs: str = "",
    streaming: bool = False,
) -> Dict[str, Any]:
    """Generate a proposal recommendation for a DAO.

    Args:
        dao_id: UUID of the DAO
        focus_area: Focus area for the recommendation
        specific_needs: Specific needs mentioned
        streaming: Whether to enable streaming

    Returns:
        Dictionary containing the generated recommendation
    """
    logger.info(f"[Orchestrator] Generating recommendation for DAO {dao_id}")

    try:
        # Set up streaming if requested
        callbacks = None
        if streaming:
            callback_handler, queue = create_streaming_setup()
            callbacks = [callback_handler]

        # Generate recommendation
        recommendation_result = await _generate_recommendation(
            dao_id=dao_id,
            focus_area=focus_area,
            specific_needs=specific_needs,
            callbacks=callbacks,
        )

        # Add processing metadata
        result = {
            "recommendation": recommendation_result,
            "processing_metadata": {
                "dao_id": str(dao_id),
                "focus_area": focus_area,
                "specific_needs": specific_needs,
                "streaming_enabled": streaming,
            },
        }

        # Add streaming queue if enabled
        if streaming and callbacks:
            result["streaming_queue"] = callbacks[0].queue

        logger.info(
            f"[Orchestrator] Completed recommendation generation for DAO {dao_id}"
        )
        return result

    except Exception as e:
        logger.error(
            f"[Orchestrator] Error in recommendation generation for DAO {dao_id}: {str(e)}"
        )
        return {
            "error": str(e),
            "recommendation": {
                "error": str(e),
                "title": "",
                "content": f"Error generating recommendation: {str(e)}",
                "rationale": "",
                "priority": "low",
                "estimated_impact": "",
                "suggested_action": "",
            },
            "processing_metadata": {
                "dao_id": str(dao_id),
                "focus_area": focus_area,
                "specific_needs": specific_needs,
                "streaming_enabled": streaming,
            },
        }


async def process_proposal_content(
    proposal_content: str,
    tweet_db_ids: Optional[List[UUID]] = None,
    proposal_id: Optional[UUID] = None,
) -> Dict[str, Any]:
    """Process proposal content to extract images and tweets.

    Args:
        proposal_content: The proposal content to process
        tweet_db_ids: Optional list of tweet database IDs to process
        proposal_id: Optional proposal UUID for logging

    Returns:
        Dictionary containing processed content
    """
    proposal_id_str = str(proposal_id) if proposal_id else "unknown"
    logger.info(f"[Orchestrator] Processing content for proposal {proposal_id_str}")

    try:
        # Step 1: Process images from proposal content
        images = await process_media(proposal_content, proposal_id_str)
        logger.debug(f"[Orchestrator:{proposal_id_str}] Found {len(images)} images")

        # Step 2: Process tweets if provided
        tweet_content = ""
        tweet_images = []
        if tweet_db_ids:
            logger.debug(
                f"[Orchestrator:{proposal_id_str}] Processing {len(tweet_db_ids)} tweets"
            )
            tweet_content, tweet_images = await process_tweets(
                tweet_db_ids, proposal_id_str
            )
            logger.debug(
                f"[Orchestrator:{proposal_id_str}] Processed tweets: {len(tweet_content)} chars, {len(tweet_images)} images"
            )

        # Step 3: Combine all images
        all_images = images + tweet_images

        result = {
            "images": images,
            "tweet_content": tweet_content,
            "tweet_images": tweet_images,
            "all_images": all_images,
            "processing_metadata": {
                "proposal_id": proposal_id_str,
                "images_processed": len(images),
                "tweet_images_processed": len(tweet_images),
                "total_images": len(all_images),
                "tweets_processed": len(tweet_db_ids) if tweet_db_ids else 0,
                "tweet_content_length": len(tweet_content),
            },
        }

        logger.info(
            f"[Orchestrator] Completed content processing for proposal {proposal_id_str}"
        )
        return result

    except Exception as e:
        logger.error(
            f"[Orchestrator] Error processing content for proposal {proposal_id_str}: {str(e)}"
        )
        return {
            "error": str(e),
            "images": [],
            "tweet_content": "",
            "tweet_images": [],
            "all_images": [],
            "processing_metadata": {
                "proposal_id": proposal_id_str,
                "images_processed": 0,
                "tweet_images_processed": 0,
                "total_images": 0,
                "tweets_processed": 0,
                "tweet_content_length": 0,
            },
        }


# Convenience functions for backwards compatibility
async def comprehensive_evaluation(
    proposal_content: str,
    dao_id: Optional[UUID] = None,
    proposal_id: Optional[UUID] = None,
    tweet_db_ids: Optional[List[UUID]] = None,
    custom_system_prompt: Optional[str] = None,
    custom_user_prompt: Optional[str] = None,
    streaming: bool = False,
) -> Dict[str, Any]:
    """Alias for evaluate_proposal_comprehensive for backwards compatibility."""
    # return await evaluate_proposal_comprehensive(
    #    proposal_content=proposal_content,
    #    dao_id=dao_id,
    #    proposal_id=proposal_id,
    #    tweet_db_ids=tweet_db_ids,
    #    custom_system_prompt=custom_system_prompt,
    #    custom_user_prompt=custom_user_prompt,
    #    streaming=streaming,
    # )
    return await evaluate_proposal_comprehensive(dao_id=dao_id, proposal_id=proposal_id)


async def metadata_generation(
    proposal_content: str,
    dao_name: str = "",
    proposal_type: str = "",
    tweet_db_ids: Optional[List[UUID]] = None,
    streaming: bool = False,
) -> Dict[str, Any]:
    """Alias for generate_proposal_metadata for backwards compatibility."""
    return await generate_proposal_metadata(
        proposal_content=proposal_content,
        dao_name=dao_name,
        proposal_type=proposal_type,
        tweet_db_ids=tweet_db_ids,
        streaming=streaming,
    )


async def recommendation_generation(
    dao_id: UUID,
    focus_area: str = "",
    specific_needs: str = "",
    streaming: bool = False,
) -> Dict[str, Any]:
    """Alias for generate_proposal_recommendation for backwards compatibility."""
    return await generate_proposal_recommendation(
        dao_id=dao_id,
        focus_area=focus_area,
        specific_needs=specific_needs,
        streaming=streaming,
    )
