"""OpenRouter-based proposal evaluation logic using standard models.

This module provides a functional approach to proposal evaluation using OpenRouter
with direct HTTP calls and the standard comprehensive evaluation output model.
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field

from app.backend.factory import backend
from app.backend.models import Proposal, ProposalFilter
from app.config import config
from app.lib.logger import configure_logger
from app.services.ai.simple_workflows.processors.twitter import (
    fetch_tweet,
    format_tweet,
    format_tweet_images,
)
from app.services.ai.simple_workflows.processors.airdrop import (
    process_airdrop,
)

# Import prompts
from app.services.ai.simple_workflows.prompts import (
    EVALUATION_SYSTEM_PROMPT as DEFAULT_SYSTEM_PROMPT,
    EVALUATION_USER_PROMPT_TEMPLATE as DEFAULT_USER_PROMPT_TEMPLATE,
)
from app.services.ai.simple_workflows.models import (
    ComprehensiveEvaluatorAgentProcessOutput,
    ComprehensiveEvaluationOutput,
    EvaluationCategory,
)

logger = configure_logger(__name__)

# ==========================================
# DAO-SPECIFIC EVALUATION MODELS
# ==========================================
# If you have a new DAO with a different response format:
# 1. Add new Pydantic models here matching the LLM's JSON schema
# 2. Create a conversion function to transform to ComprehensiveEvaluatorAgentProcessOutput
# 3. Update the parsing logic in evaluate_proposal_openrouter() to detect and handle the new format
# 4. Use field inspection (e.g., "current_order" in content_dict) to auto-detect which format was returned
# ==========================================

# AIBTC BREW specific models


class Reasons(BaseModel):
    """Nested model for per-category rationales."""

    current_order: str = Field(
        description="2-3 sentence rationale for current_order alignment"
    )
    mission: str = Field(description="2-3 sentence rationale for mission alignment")
    value: str = Field(description="2-3 sentence rationale for value contribution")
    values: str = Field(description="2-3 sentence rationale for values alignment")
    originality: str = Field(description="2-3 sentence rationale for originality")
    clarity: str = Field(description="2-3 sentence rationale for clarity")
    safety: str = Field(description="2-3 sentence rationale for safety")
    growth: str = Field(description="2-3 sentence rationale for growth potential")


class Evidence(BaseModel):
    """Nested model for supporting evidence."""

    value_items: List[str] = Field(
        default_factory=list, description="List of specific value evidence items"
    )


class AIBTCBrewEvaluationOutput(BaseModel):
    """Output model matching the AIBTC BREW prompt's JSON schema."""

    # Category scores (0-100, as per prompt)
    current_order: int = Field(
        ge=0, le=100, description="Current order alignment score"
    )
    mission: int = Field(ge=0, le=100, description="Mission alignment score")
    value: int = Field(ge=0, le=100, description="Value contribution score")
    values: int = Field(ge=0, le=100, description="Values alignment score")
    originality: int = Field(ge=0, le=100, description="Originality score")
    clarity: int = Field(ge=0, le=100, description="Clarity & execution score")
    safety: int = Field(ge=0, le=100, description="Safety & compliance score")
    growth: int = Field(ge=0, le=100, description="Growth potential score")

    # Nested rationales
    reasons: Reasons = Field(description="Per-category rationales")
    evidence: Evidence = Field(description="Supporting evidence")

    # Overall evaluation
    final_score: int = Field(ge=0, le=100, description="Final weighted score")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in evaluation")
    decision: str = Field(description="APPROVE or REJECT")
    failed: List[str] = Field(
        default_factory=list, description="List of failed gates/thresholds with reasons"
    )

    @property
    def is_approved(self) -> bool:
        """Convenience: True if 'APPROVE', False if 'REJECT'."""
        return self.decision == "APPROVE"


def convert_aibtc_brew_to_standard_format(
    aibtc_result: AIBTCBrewEvaluationOutput,
    images_processed: int = 0,
    token_usage: Dict[str, Any] = None,
) -> ComprehensiveEvaluatorAgentProcessOutput:
    """Convert AIBTC BREW result to standard evaluation format."""
    if token_usage is None:
        token_usage = {}

    # Convert AIBTC BREW categories to standard format
    categories = [
        EvaluationCategory(
            category="Current Order Alignment",
            score=aibtc_result.current_order,
            weight=0.2,  # 20% as per AIBTC BREW
            reasoning=[aibtc_result.reasons.current_order],
        ),
        EvaluationCategory(
            category="Mission Alignment",
            score=aibtc_result.mission,
            weight=0.2,  # 20% as per AIBTC BREW
            reasoning=[aibtc_result.reasons.mission],
        ),
        EvaluationCategory(
            category="Value Contribution",
            score=aibtc_result.value,
            weight=0.2,  # 20% as per AIBTC BREW
            reasoning=[aibtc_result.reasons.value],
        ),
        EvaluationCategory(
            category="Values Alignment",
            score=aibtc_result.values,
            weight=0.1,  # 10% as per AIBTC BREW
            reasoning=[aibtc_result.reasons.values],
        ),
        EvaluationCategory(
            category="Originality",
            score=aibtc_result.originality,
            weight=0.1,  # 10% as per AIBTC BREW
            reasoning=[aibtc_result.reasons.originality],
        ),
        EvaluationCategory(
            category="Clarity & Execution",
            score=aibtc_result.clarity,
            weight=0.1,  # 10% as per AIBTC BREW
            reasoning=[aibtc_result.reasons.clarity],
        ),
        EvaluationCategory(
            category="Safety & Compliance",
            score=aibtc_result.safety,
            weight=0.1,  # 10% as per AIBTC BREW
            reasoning=[aibtc_result.reasons.safety],
        ),
        EvaluationCategory(
            category="Growth Potential",
            score=aibtc_result.growth,
            weight=0.1,  # 10% as per AIBTC BREW
            reasoning=[aibtc_result.reasons.growth],
        ),
    ]

    # Build comprehensive explanation from all reasoning
    explanation_parts = []
    for category in categories:
        explanation_parts.append(f"**{category.category}**: {category.reasoning[0]}")

    # Add evidence if available
    if aibtc_result.evidence.value_items:
        explanation_parts.append(
            f"**Evidence**: {', '.join(aibtc_result.evidence.value_items)}"
        )

    explanation = "\n\n".join(explanation_parts)

    # Create summary
    summary = f"Proposal evaluated with final score of {aibtc_result.final_score}/100. Decision: {aibtc_result.decision}. Confidence: {aibtc_result.confidence:.2f}"
    if aibtc_result.failed:
        summary += f" Failed gates: {', '.join(aibtc_result.failed)}"

    return ComprehensiveEvaluatorAgentProcessOutput(
        categories=categories,
        final_score=aibtc_result.final_score,
        decision=aibtc_result.is_approved,
        explanation=explanation,
        flags=aibtc_result.failed,
        summary=summary,
        token_usage=token_usage,
        images_processed=images_processed,
    )


def get_openrouter_config() -> Dict[str, str]:
    """Get OpenRouter configuration from environment."""
    api_key = os.getenv("AIBTC_CHAT_API_KEY") or getattr(
        config, "AIBTC_CHAT_API_KEY", None
    )
    if not api_key:
        raise ValueError("AIBTC_CHAT_API_KEY not found in configuration")

    base_url = (
        os.getenv("AIBTC_CHAT_API_BASE")
        or getattr(config, "AIBTC_CHAT_API_BASE", None)
        or "https://openrouter.ai/api/v1"
    )
    default_model = (
        os.getenv("AIBTC_CHAT_DEFAULT_MODEL")
        or getattr(config, "AIBTC_CHAT_DEFAULT_MODEL", None)
        or "x-ai/grok-4-fast"
    )

    return {"api_key": api_key, "base_url": base_url, "default_model": default_model}


async def call_openrouter(
    messages: List[Dict[str, Any]],
    model: Optional[str] = None,
    temperature: float = 0.0,
) -> Dict[str, Any]:
    """Call OpenRouter API directly with HTTP requests."""
    openrouter_config = get_openrouter_config()

    # Use provided model or default
    model_name = model or openrouter_config["default_model"]

    headers = {
        "Authorization": f"Bearer {openrouter_config['api_key']}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
    }

    logger.debug(f"Making OpenRouter API call to model: {model_name}")

    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(
            f"{openrouter_config['base_url']}/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        return response.json()


async def fetch_dao_proposals(dao_id: UUID, exclude_proposal_id: str) -> List[Proposal]:
    """Fetch proposals for a DAO, excluding the current proposal."""
    logger.debug(
        f"Excluded current proposal {exclude_proposal_id} from historical context"
    )

    # Get all proposals for this DAO
    proposal_filter = ProposalFilter(dao_id=dao_id)
    all_proposals = backend.get_proposals(proposal_filter)

    # Exclude the current proposal
    filtered_proposals = [
        p for p in all_proposals if str(p.proposal_id) != exclude_proposal_id
    ]

    logger.debug(
        f"Retrieved {len(filtered_proposals)} proposals for DAO {dao_id} (excluding current)"
    )
    return filtered_proposals


def format_proposals_for_context_v2(proposals: List[Proposal]) -> str:
    """Format proposals for context in evaluation prompt."""
    if not proposals:
        return (
            "<no_proposals>No past proposals available for comparison.</no_proposals>"
        )

    # Sort by created_at descending (newest first)
    sorted_proposals = sorted(
        proposals,
        key=lambda p: getattr(p, "created_at", datetime.min),
        reverse=True,
    )

    formatted_proposals = []
    for proposal in sorted_proposals:
        # Extract basic info
        proposal_id = str(proposal.proposal_id)[:8]  # Short ID
        title = getattr(proposal, "title", "Untitled")

        # Extract x_handle from x_url using urlparse
        x_url = getattr(proposal, "x_url", None)
        x_handle = "unknown"
        if x_url:
            try:
                parsed_path = urlparse(x_url).path.split("/")
                if len(parsed_path) > 1:
                    x_handle = parsed_path[1]
            except (AttributeError, IndexError):
                pass  # Fallback to "unknown"

        # Get creation info
        created_at_btc = getattr(proposal, "created_at_btc", None)
        created_at_timestamp = getattr(proposal, "created_at", None)

        # Safely handle created_at date formatting
        created_str = "unknown"
        if created_at_timestamp:
            try:
                created_str = created_at_timestamp.strftime("%Y-%m-%d")
            except (AttributeError, ValueError):
                created_str = str(created_at_timestamp)

        if created_at_btc and created_at_timestamp:
            created_at = f"BTC Block {created_at_btc} (at {created_str})"
        elif created_at_btc:
            created_at = f"BTC Block {created_at_btc}"
        elif created_at_timestamp:
            created_at = created_str
        else:
            created_at = "unknown"

        # Get status
        passed = getattr(proposal, "passed", False)
        concluded = getattr(proposal, "concluded_by", None) is not None
        proposal_status = getattr(proposal, "status", None)

        if (
            proposal_status
            and hasattr(proposal_status, "value")
            and proposal_status.value == "FAILED"
        ):
            proposal_passed = "n/a (failed tx)"
        elif passed:
            proposal_passed = "yes"
        elif concluded:
            proposal_passed = "no"
        else:
            proposal_passed = "pending review"

        # Get content
        content = getattr(proposal, "content", "") or getattr(proposal, "summary", "")
        content_preview = content[:200] + "..." if len(content) > 200 else content

        # Get tags
        tags = getattr(proposal, "tags", [])
        tags_str = ", ".join(tags) if tags else "no tags"

        # Get reference
        reference = getattr(proposal, "reference", None)

        formatted_proposal = f"""- #{proposal_id} by @{x_handle}
  Created: {created_at}
  Passed: {proposal_passed}
  Title: {title}
  Tags: {tags_str}
  Summary: {content_preview}"""

        if reference:
            formatted_proposal += f"\n\nReference: {reference}"

        formatted_proposals.append(formatted_proposal)

    return "\n\n\n".join(formatted_proposals)


def create_chat_messages(
    proposal_content: str,
    dao_mission: str,
    community_info: str,
    past_proposals: str,
    proposal_images: List[Dict[str, Any]] = None,
    tweet_content: Optional[str] = None,
    airdrop_content: Optional[str] = None,
    custom_system_prompt: Optional[str] = None,
    custom_user_prompt: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Create chat messages for comprehensive evaluation.

    Args:
        proposal_content: The proposal content to evaluate
        dao_mission: The DAO mission statement
        community_info: Information about the DAO community
        past_proposals: Formatted past proposals text
        proposal_images: List of processed images
        tweet_content: Optional tweet content from linked tweets
        airdrop_content: Optional airdrop content from linked airdrop
        custom_system_prompt: Optional custom system prompt to override default
        custom_user_prompt: Optional custom user prompt to override default

    Returns:
        List of chat messages
    """
    # Use custom system prompt or default
    if custom_system_prompt:
        system_content = custom_system_prompt
    else:
        system_content = DEFAULT_SYSTEM_PROMPT

    # Use custom user prompt or default, format with appropriate data
    if custom_user_prompt:
        # Check if this is AIBTC BREW prompt (which has different format requirements)
        if "AIBTC protocol" in custom_user_prompt:
            # AIBTC BREW template only expects dao_mission and past_proposals
            user_content = custom_user_prompt.format(
                dao_mission=dao_mission,
                past_proposals=past_proposals,
            )
        else:
            # Other custom prompts use the full format
            user_content = custom_user_prompt.format(
                proposal_content=proposal_content,
                dao_mission=dao_mission,
                community_info=community_info,
                past_proposals=past_proposals,
            )
    else:
        user_content = DEFAULT_USER_PROMPT_TEMPLATE.format(
            proposal_content=proposal_content,
            dao_mission=dao_mission,
            community_info=community_info,
            past_proposals=past_proposals,
        )

    messages = [{"role": "system", "content": system_content}]

    # Add tweet content as separate user message if available
    if tweet_content and tweet_content.strip():
        # Safely escape tweet content to prevent JSON/format issues
        escaped_tweet_content = str(tweet_content)
        # Remove or replace control characters (keep common whitespace)
        escaped_tweet_content = "".join(
            char
            for char in escaped_tweet_content
            if char.isprintable() or char in ["\n", "\r", "\t"]
        )

        logger.debug(
            f"Added escaped tweet content to messages: {escaped_tweet_content[:100]}..."
        )
        messages.append(
            {
                "role": "user",
                "content": f"Referenced tweets in this proposal:\n\n{escaped_tweet_content}",
            }
        )

    # Add airdrop content as separate user message if available
    if airdrop_content and airdrop_content.strip():
        messages.append(
            {
                "role": "user",
                "content": f"Referenced airdrop in this proposal:\n\n{airdrop_content}",
            }
        )

    # Create user message content - start with text
    user_message_content = [{"type": "text", "text": user_content}]

    # Add images if available
    if proposal_images:
        for image in proposal_images:
            if image.get("type") == "image_url":
                # Add detail parameter if not present
                image_with_detail = image.copy()
                if "detail" not in image_with_detail.get("image_url", {}):
                    image_with_detail["image_url"]["detail"] = "auto"
                user_message_content.append(image_with_detail)

    # Add the user message
    messages.append({"role": "user", "content": user_message_content})

    return messages


async def evaluate_proposal_openrouter(
    proposal_content: str,
    dao_id: Optional[UUID] = None,
    proposal_id: Optional[UUID] = None,
    images: Optional[List[Dict[str, Any]]] = None,
    tweet_content: Optional[str] = None,
    airdrop_content: Optional[str] = None,
    custom_system_prompt: Optional[str] = None,
    custom_user_prompt: Optional[str] = None,
    model: Optional[str] = None,
    callbacks: Optional[List[Any]] = None,
) -> ComprehensiveEvaluatorAgentProcessOutput:
    """Evaluate a proposal comprehensively using OpenRouter with dynamic prompts.

    Args:
        proposal_content: The proposal content to evaluate
        dao_id: Optional DAO ID for context
        proposal_id: Optional proposal UUID for fetching linked tweet content
        images: Optional list of processed images
        tweet_content: Optional tweet content (will be fetched from DB if proposal_id provided)
        airdrop_content: Optional airdrop content (will be fetched from DB if proposal_id provided)
        custom_system_prompt: Optional custom system prompt
        custom_user_prompt: Optional custom user prompt
        model: Optional model name to use (defaults to configured model)
        callbacks: Optional callback handlers for streaming

    Returns:
        Comprehensive evaluation output
    """
    proposal_id_str = str(proposal_id) if proposal_id else "unknown"
    logger.info(
        f"[EvaluationProcessorOpenRouter:{proposal_id_str}] Starting comprehensive evaluation with OpenRouter"
    )
    dao_mission_text = "<no_mission>No DAO mission available.</no_mission>"
    linked_tweet_images: List[Dict[str, Any]] = []

    # Fetch DAO mission from database
    if dao_id:
        try:
            dao = backend.get_dao(dao_id)
            if dao and dao.mission:
                dao_mission_text = dao.mission
                logger.debug(
                    f"[EvaluationProcessorOpenRouter:{proposal_id_str}] Retrieved DAO mission: {dao_mission_text[:100]}..."
                )
            else:
                logger.warning(
                    f"[EvaluationProcessorOpenRouter:{proposal_id_str}] No DAO found or no mission field for dao_id: {dao_id}"
                )
        except Exception as e:
            logger.error(
                f"[EvaluationProcessorOpenRouter:{proposal_id_str}] Error retrieving DAO from database: {str(e)}"
            )

    # Fetch tweet content from the proposal's linked tweet if available
    if proposal_id and not tweet_content:
        try:
            logger.debug(
                f"[EvaluationProcessorOpenRouter:{proposal_id_str}] Fetching proposal to get linked tweet content"
            )
            proposal = backend.get_proposal(proposal_id)
            if proposal and hasattr(proposal, "tweet_id") and proposal.tweet_id:
                logger.debug(
                    f"[EvaluationProcessorOpenRouter:{proposal_id_str}] Found linked tweet_id: {proposal.tweet_id}"
                )
                tweet_data = await fetch_tweet(proposal.tweet_id)
                if tweet_data:
                    tweet_content = format_tweet(tweet_data)
                    logger.debug(
                        f"[EvaluationProcessorOpenRouter:{proposal_id_str}] Retrieved and formatted tweet content: {tweet_content}"
                    )

                    # Also extract any images from the linked tweet
                    linked_tweet_images = format_tweet_images(
                        tweet_data, proposal.tweet_id
                    )
                    if linked_tweet_images:
                        logger.debug(
                            f"[EvaluationProcessorOpenRouter:{proposal_id_str}] Found {len(linked_tweet_images)} images in linked tweet"
                        )
                else:
                    logger.warning(
                        f"[EvaluationProcessorOpenRouter:{proposal_id_str}] Could not retrieve tweet data for tweet_id: {proposal.tweet_id}"
                    )
            else:
                logger.debug(
                    f"[EvaluationProcessorOpenRouter:{proposal_id_str}] No linked tweet found for proposal"
                )
        except Exception as e:
            logger.error(
                f"[EvaluationProcessorOpenRouter:{proposal_id_str}] Error fetching linked tweet content: {str(e)}"
            )

    # Fetch airdrop content from the proposal's linked airdrop if available
    if proposal_id and not airdrop_content:
        try:
            logger.debug(
                f"[EvaluationProcessorOpenRouter:{proposal_id_str}] Fetching proposal to get linked airdrop content"
            )
            proposal = backend.get_proposal(proposal_id)
            if proposal and hasattr(proposal, "airdrop_id") and proposal.airdrop_id:
                logger.debug(
                    f"[EvaluationProcessorOpenRouter:{proposal_id_str}] Found linked airdrop_id: {proposal.airdrop_id}"
                )
                airdrop_content = await process_airdrop(
                    proposal.airdrop_id, proposal_id
                )
                if airdrop_content:
                    logger.debug(
                        f"[EvaluationProcessorOpenRouter:{proposal_id_str}] Retrieved and processed airdrop content"
                    )
                else:
                    logger.warning(
                        f"[EvaluationProcessorOpenRouter:{proposal_id_str}] Could not process airdrop for airdrop_id: {proposal.airdrop_id}"
                    )
            else:
                logger.debug(
                    f"[EvaluationProcessorOpenRouter:{proposal_id_str}] No linked airdrop found for proposal"
                )
        except Exception as e:
            logger.error(
                f"[EvaluationProcessorOpenRouter:{proposal_id_str}] Error fetching linked airdrop content: {str(e)}"
            )

    # Get community info (simplified version)
    community_info = """
Community Size: Growing
Active Members: Active
Governance Participation: Moderate
Recent Community Sentiment: Positive
"""

    # Retrieve all proposals for this DAO from database (excluding current proposal)
    dao_proposals = []
    past_proposals_db_text = ""
    try:
        if dao_id:
            dao_proposals = await fetch_dao_proposals(
                dao_id, exclude_proposal_id=proposal_id_str
            )
            past_proposals_db_text = format_proposals_for_context_v2(dao_proposals)
    except Exception as e:
        logger.error(
            f"[EvaluationProcessorOpenRouter:{proposal_id_str}] Error fetching/formatting DAO proposals: {str(e)}"
        )
        past_proposals_db_text = (
            "<no_proposals>No past proposals available due to error.</no_proposals>"
        )

    # Use only database proposals (no vector store)
    past_proposals_text = past_proposals_db_text

    try:
        # Combine all images (proposal images + linked tweet images)
        all_proposal_images = (images or []) + linked_tweet_images

        # Create chat messages with dynamic prompts
        messages = create_chat_messages(
            proposal_content=proposal_content,
            dao_mission=dao_mission_text,
            community_info=community_info,
            past_proposals=past_proposals_text
            or "<no_proposals>No past proposals available for comparison.</no_proposals>",
            proposal_images=all_proposal_images,
            tweet_content=tweet_content,
            airdrop_content=airdrop_content,
            custom_system_prompt=custom_system_prompt,
            custom_user_prompt=custom_user_prompt,
        )

        # Get structured output from OpenRouter API
        try:
            # Call OpenRouter directly
            response = await call_openrouter(
                messages=messages,
                model=model,
                temperature=0.0,
            )

            # Extract the content from the response
            content = response["choices"][0]["message"]["content"].strip()

            # Log the raw response for debugging
            logger.debug(
                f"[EvaluationProcessorOpenRouter:{proposal_id_str}] Raw LLM response: {content[:500]}..."
            )

            # Parse the JSON response into AIBTC BREW model first
            try:
                content_dict = json.loads(content)
                logger.debug(
                    f"[EvaluationProcessorOpenRouter:{proposal_id_str}] Parsed JSON keys: {list(content_dict.keys())}"
                )

                # Check if this is AIBTC BREW format (has individual category scores)
                if "current_order" in content_dict and "mission" in content_dict:
                    logger.debug(
                        f"[EvaluationProcessorOpenRouter:{proposal_id_str}] Detected AIBTC BREW format, using conversion"
                    )
                    aibtc_result = AIBTCBrewEvaluationOutput(**content_dict)
                    # Convert to standard format
                    result = convert_aibtc_brew_to_standard_format(
                        aibtc_result,
                        images_processed=len(all_proposal_images),
                        token_usage={"raw_response": content},
                    )
                else:
                    logger.debug(
                        f"[EvaluationProcessorOpenRouter:{proposal_id_str}] Detected standard format, using directly"
                    )
                    standard_result = ComprehensiveEvaluationOutput(**content_dict)
                    result = ComprehensiveEvaluatorAgentProcessOutput(
                        categories=standard_result.categories,
                        final_score=standard_result.final_score,
                        decision=standard_result.decision,
                        explanation=standard_result.explanation,
                        flags=standard_result.flags,
                        summary=standard_result.summary,
                        token_usage={"raw_response": content},
                        images_processed=len(all_proposal_images),
                    )
            except json.JSONDecodeError as e:
                logger.error(
                    f"[EvaluationProcessorOpenRouter:{proposal_id_str}] JSON decode error: {e}"
                )
                logger.error(
                    f"[EvaluationProcessorOpenRouter:{proposal_id_str}] Raw content: {content}"
                )
                raise e
            except Exception as e:
                logger.error(
                    f"[EvaluationProcessorOpenRouter:{proposal_id_str}] Pydantic validation error: {e}"
                )
                logger.error(
                    f"[EvaluationProcessorOpenRouter:{proposal_id_str}] Content dict: {content_dict}"
                )
                raise e
        except Exception as e:
            # If we get a streaming/parsing error, try to handle it
            error_msg = str(e)
            if (
                "Expected list delta entry to have an `index` key" in error_msg
                or "reasoning.text" in error_msg
            ):
                logger.warning(
                    f"[EvaluationProcessorOpenRouter:{proposal_id_str}] Grok reasoning token error, retrying with basic invocation: {error_msg}"
                )
                # This would require a fallback implementation
                raise e
            else:
                # Re-raise non-Grok related errors
                raise e

        logger.info(
            f"[EvaluationProcessorOpenRouter:{proposal_id_str}] Successfully completed comprehensive evaluation"
        )
        logger.info(
            f"[EvaluationProcessorOpenRouter:{proposal_id_str}] Decision: {result.decision}, Final Score: {result.final_score}"
        )

        # Return the result (already converted if needed)
        return result
    except Exception as e:
        logger.error(
            f"[EvaluationProcessorOpenRouter:{proposal_id_str}] Error in comprehensive evaluation: {str(e)}"
        )
        # Calculate total images processed (including any linked tweet images that were fetched)
        total_images = len(images) if images else 0
        try:
            total_images += len(linked_tweet_images)
        except NameError:
            pass  # linked_tweet_images might not be defined if an error occurred earlier
        return ComprehensiveEvaluatorAgentProcessOutput(
            categories=[],
            final_score=30,
            decision=False,
            explanation=f"Comprehensive evaluation failed due to error: {str(e)}",
            flags=[f"Critical Error: {str(e)}"],
            summary="Evaluation failed due to error",
            token_usage={},
            images_processed=total_images,
        )
