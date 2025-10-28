"""Orchestrator for simple workflows.

This module provides the main public API facade for the simplified workflow system,
orchestrating the various processors and providing a clean interface for callers.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from app.backend.factory import backend
from app.lib.logger import configure_logger
from app.services.ai.simple_workflows.evaluation import evaluate_proposal
from app.services.ai.simple_workflows.metadata import (
    generate_proposal_metadata as _generate_metadata,
)
from app.services.ai.simple_workflows.processors import process_images, process_tweets
from app.services.ai.simple_workflows.prompts.loader import load_prompt
from app.services.ai.simple_workflows.recommendation import (
    generate_proposal_recommendation as _generate_recommendation,
)
from app.services.ai.simple_workflows.streaming import create_streaming_setup

logger = configure_logger(__name__)


async def evaluate_proposal_comprehensive(
    proposal_content: str,
    dao_id: Optional[UUID] = None,
    proposal_id: Optional[UUID] = None,
    tweet_db_ids: Optional[List[UUID]] = None,
    custom_system_prompt: Optional[str] = None,
    custom_user_prompt: Optional[str] = None,
    streaming: bool = False,
) -> Dict[str, Any]:
    """Evaluate a proposal comprehensively with all context processing.

    Args:
        proposal_content: The proposal content to evaluate
        dao_id: Optional DAO ID for context
        proposal_id: Optional proposal UUID (will fetch linked tweet content automatically)
        tweet_db_ids: Optional list of additional tweet database IDs to process
        custom_system_prompt: Optional custom system prompt
        custom_user_prompt: Optional custom user prompt
        streaming: Whether to enable streaming

    Returns:
        Dictionary containing comprehensive evaluation results
    """
    proposal_id_str = str(proposal_id) if proposal_id else "unknown"
    logger.info(
        f"[Orchestrator] Starting comprehensive evaluation for proposal {proposal_id_str}"
    )

    try:
        # Set up streaming if requested
        callbacks = None
        if streaming:
            callback_handler, queue = create_streaming_setup()
            callbacks = [callback_handler]

        # Step 1: Process images from proposal content
        logger.debug(f"[Orchestrator:{proposal_id_str}] Processing images")
        images = await process_images(proposal_content, proposal_id_str)
        logger.debug(f"[Orchestrator:{proposal_id_str}] Found {len(images)} images")

        # Step 2: Process tweets if provided (additional tweets beyond proposal's linked tweet)
        tweet_content = ""
        tweet_images = []
        if tweet_db_ids:
            logger.debug(
                f"[Orchestrator:{proposal_id_str}] Processing {len(tweet_db_ids)} additional tweets"
            )
            tweet_content, tweet_images = await process_tweets(
                tweet_db_ids, proposal_id_str
            )
            logger.debug(
                f"[Orchestrator:{proposal_id_str}] Processed additional tweets: {len(tweet_content)} chars, {len(tweet_images)} images"
            )

        # Step 3: Combine all images
        all_images = images + tweet_images

        # Determine prompt type based on DAO name
        prompt_type = "evaluation"  # Default
        if dao_id:
            dao = backend.get_dao(dao_id)
            if dao:
                if dao.name == "AIBTC-BREW":
                    prompt_type = "evaluation_aibtc_brew"
                    logger.info(
                        f"[Orchestrator:{proposal_id_str}] Using AIBTC-BREW-specific prompts for DAO {dao.name}"
                    )
                elif dao.name == "ELONBTC":
                    prompt_type = "evaluation_elonbtc"
                    logger.info(
                        f"[Orchestrator:{proposal_id_str}] Using ELONBTC-specific prompts for DAO {dao.name}"
                    )
                elif dao.name in ["AIBTC", "AITEST", "AITEST2", "AITEST3", "AITEST4"]:
                    prompt_type = "evaluation_aibtc"
                    logger.info(
                        f"[Orchestrator:{proposal_id_str}] Using AIBTC-specific prompts for DAO {dao.name}"
                    )
                else:
                    logger.debug(
                        f"[Orchestrator:{proposal_id_str}] Using general prompts for DAO {dao.name}"
                    )
            else:
                logger.debug(
                    f"[Orchestrator:{proposal_id_str}] Using general prompts for DAO unknown"
                )

        # Load prompts if not provided
        if custom_system_prompt is None:
            custom_system_prompt = load_prompt(prompt_type, "system")
        if custom_user_prompt is None:
            custom_user_prompt = load_prompt(prompt_type, "user_template")

        # Step 4: Run comprehensive evaluation
        logger.debug(
            f"[Orchestrator:{proposal_id_str}] Running comprehensive evaluation"
        )
        evaluation_result = await evaluate_proposal(
            proposal_content=proposal_content,
            dao_id=dao_id,
            proposal_id=proposal_id,
            images=all_images,
            tweet_content=tweet_content,
            airdrop_content=None,  # Let evaluate_proposal fetch it automatically if needed
            custom_system_prompt=custom_system_prompt,
            custom_user_prompt=custom_user_prompt,
            callbacks=callbacks,
        )

        # Step 5: Add processing metadata
        result = {
            "evaluation": evaluation_result.model_dump()
            if hasattr(evaluation_result, "model_dump")
            else evaluation_result,
            "processing_metadata": {
                "proposal_id": proposal_id_str,
                "dao_id": str(dao_id) if dao_id else None,
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

        logger.info(
            f"[Orchestrator] Completed comprehensive evaluation for proposal {proposal_id_str}"
        )
        return result

    except Exception as e:
        logger.error(
            f"[Orchestrator] Error in comprehensive evaluation for proposal {proposal_id_str}: {str(e)}"
        )
        return {
            "error": str(e),
            "evaluation": {
                "categories": [],
                "final_score": 0,
                "decision": False,
                "explanation": f"Evaluation failed: {str(e)}",
                "flags": [f"Critical Error: {str(e)}"],
                "summary": "Evaluation failed due to error",
                "token_usage": {},
                "images_processed": 0,
            },
            "processing_metadata": {
                "proposal_id": proposal_id_str,
                "dao_id": str(dao_id) if dao_id else None,
                "images_processed": 0,
                "tweet_images_processed": 0,
                "total_images": 0,
                "tweets_processed": 0,
                "tweet_content_length": 0,
                "streaming_enabled": streaming,
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
        images = await process_images(proposal_content, "metadata_generation")
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
        images = await process_images(proposal_content, proposal_id_str)
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
    return await evaluate_proposal_comprehensive(
        proposal_content=proposal_content,
        dao_id=dao_id,
        proposal_id=proposal_id,
        tweet_db_ids=tweet_db_ids,
        custom_system_prompt=custom_system_prompt,
        custom_user_prompt=custom_user_prompt,
        streaming=streaming,
    )


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
