"""Simplified proposal metadata generation.

This module provides a functional approach to generating proposal metadata,
converting the complex class-based metadata agent into a simple async function.
"""

from typing import Any, Dict, List, Optional

import json

from app.config import config
from app.lib.logger import configure_logger
from app.services.ai.simple_workflows.evaluation_openrouter_v2 import call_openrouter

from app.lib.utils import estimate_usage_cost
from app.services.ai.simple_workflows.models import ProposalMetadataOutput
from app.services.ai.simple_workflows.prompts.metadata import (
    METADATA_SYSTEM_PROMPT,
    METADATA_USER_PROMPT_TEMPLATE,
)

logger = configure_logger(__name__)


async def generate_proposal_metadata(
    proposal_content: str,
    dao_name: str = "",
    proposal_type: str = "",
    proposal_media: Optional[List[Dict[str, Any]]] = None,
    callbacks: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    """Generate title, summary, and metadata tags for proposal content.

    Args:
        proposal_content: Content of the proposal
        dao_name: Name of the DAO
        proposal_type: Type of the proposal
        images: List of processed images
        callbacks: Optional callback handlers for streaming

    Returns:
        Dictionary containing the generated title, summary, tags, and metadata
    """
    if not proposal_content:
        logger.error("No proposal_content provided")
        return {
            "error": "proposal_content is required",
            "title": "",
            "summary": "",
            "tags": [],
        }

    logger.info(
        f"[MetadataProcessor] Generating metadata for proposal content (length: {len(proposal_content)})"
    )

    try:
        # Create chat messages
        messages = create_chat_messages(
            proposal_content=proposal_content,
            dao_name=dao_name,
            proposal_type=proposal_type,
            proposal_media=proposal_media or [],
        )

        # Call OpenRouter
        openrouter_response = await call_openrouter(
            messages=messages,
            model=None,
            temperature=0.0,
            reasoning=False,
            tools=None,
        )

        # ouput full response (debugging)
        # logger.info(
        #    f"[MetadataProcessor] OpenRouter response: {openrouter_response.get('choices', [])[0]}"
        # )

        # Parse usage information
        usage = openrouter_response.get("usage", {})
        logger.debug(f"OpenRouter usage for metadata: {usage}")

        usage_input_tokens = usage.get("prompt_tokens") if usage else None
        usage_output_tokens = usage.get("completion_tokens") if usage else None
        model_used = openrouter_response.get("model", config.chat_llm.default_model)
        usage_est_cost = None
        if usage_input_tokens is not None and usage_output_tokens is not None:
            usage_est_cost = estimate_usage_cost(
                usage_input_tokens,
                usage_output_tokens,
                model_used,
            )
        usage_data = {
            "usage_input_tokens": str(usage_input_tokens),
            "usage_output_tokens": str(usage_output_tokens),
            "usage_est_cost": str(usage_est_cost),
        }

        # Parse first choice for requested json
        choices = openrouter_response.get("choices", [])
        if not choices:
            logger.error("No choices in OpenRouter response")
            raise ValueError("No choices in response")

        first_choice = choices[0]
        choice_message = first_choice.get("message")
        if not choice_message or not isinstance(choice_message.get("content"), str):
            logger.error("Invalid message content in response")
            raise ValueError("Invalid message content")

        try:
            # load the json
            metadata_json = json.loads(choice_message["content"])
            # validate with pydantic
            result = ProposalMetadataOutput(**metadata_json)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            raise ValueError(f"Invalid JSON: {e}")
        except ValueError as e:
            logger.error(f"Pydantic validation error: {e}")
            raise ValueError(f"Validation error: {e}")

        result_dict = result.model_dump()

        # Add metadata and usage
        result_dict["content_length"] = len(proposal_content)
        result_dict["dao_name"] = dao_name
        result_dict["proposal_type"] = proposal_type
        result_dict["tags_count"] = len(result_dict.get("tags", []))
        result_dict["media_processed"] = len(proposal_media) if proposal_media else 0
        result_dict.update(usage_data)

        logger.info(
            f"[MetadataProcessor] Generated title, summary, and {len(result_dict.get('tags', []))} tags for proposal: {result_dict.get('title', 'Unknown')}"
        )
        return result_dict

    except Exception as e:
        logger.error(
            f"[MetadataProcessor] Error generating proposal metadata: {str(e)}"
        )
        logger.debug("[MetadataProcessor] Error details:", exc_info=True)
        return {
            "error": str(e),
            "title": "",
            "summary": f"Error generating summary: {str(e)}",
            "tags": [],
            "content_length": len(proposal_content) if proposal_content else 0,
            "dao_name": dao_name,
            "proposal_type": proposal_type,
            "tags_count": 0,
            "media_processed": len(proposal_media) if proposal_media else 0,
        }


def create_chat_messages(
    proposal_content: str,
    dao_name: str,
    proposal_type: str,
    proposal_media: List[Dict[str, Any]] = None,
) -> List:
    """Create chat messages for proposal metadata generation.

    Args:
        proposal_content: Content of the proposal
        dao_name: Name of the DAO
        proposal_type: Type of the proposal
        proposal_images: List of processed images

    Returns:
        List of chat messages
    """
    # Use the system prompt from the prompts package
    system_content = METADATA_SYSTEM_PROMPT

    # Use the user prompt template from the prompts package
    user_content = METADATA_USER_PROMPT_TEMPLATE.format(
        proposal_content=proposal_content,
        dao_name=dao_name or "the DAO",
        proposal_type=proposal_type or "general proposal",
    )

    messages = [{"role": "system", "content": system_content}]

    # Create user message content - start with text
    user_message_content = [{"type": "text", "text": user_content}]

    # Add media if available
    if proposal_media:
        for item in proposal_media:
            item_type = item.get("type")
            if item_type in ("image_url", "video_url"):
                # Add detail parameter if not present
                item_with_detail = item.copy()
                url_key = "image_url" if item_type == "image_url" else "video_url"
                if "detail" not in item_with_detail.get(url_key, {}):
                    item_with_detail[url_key]["detail"] = "auto"
                user_message_content.append(item_with_detail)

    # Add the user message
    messages.append({"role": "user", "content": user_message_content})

    return messages
