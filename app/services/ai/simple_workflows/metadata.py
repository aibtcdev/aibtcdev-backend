"""Simplified proposal metadata generation.

This module provides a functional approach to generating proposal metadata,
converting the complex class-based metadata agent into a simple async function.
"""

from typing import Any, Dict, List, Optional

from langchain_core.prompts.chat import ChatPromptTemplate

from app.lib.logger import configure_logger
from app.services.ai.simple_workflows.llm import invoke_structured
from app.services.ai.simple_workflows.models import ProposalMetadataOutput
from app.services.ai.simple_workflows.prompts import (
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

        # Create chat prompt template
        prompt = ChatPromptTemplate.from_messages(messages)

        # Get structured output from the LLM
        # Try json_mode first as it's more compatible with various models
        try:
            logger.debug(
                "[MetadataProcessor] Attempting structured output with json_mode"
            )
            result = await invoke_structured(
                messages=prompt,
                output_schema=ProposalMetadataOutput,
                model="anthropic/claude-haiku-4.5",
                method="json_mode",
                include_raw=True,
                callbacks=callbacks,
            )
            logger.debug(
                f"[MetadataProcessor] Structured output result type: {type(result)}"
            )

            # Handle include_raw response
            if isinstance(result, dict) and "parsed" in result:
                logger.debug(
                    "[MetadataProcessor] Extracting parsed result from raw response"
                )
                result = result["parsed"]
                if result is None:
                    logger.warning(
                        "[MetadataProcessor] Model returned None for parsed result (possible refusal)"
                    )
                    raise ValueError("Model refused to generate structured output")
        except Exception as json_mode_error:
            logger.warning(
                f"[MetadataProcessor] json_mode failed: {str(json_mode_error)}, trying function_calling"
            )
            # Fallback to function_calling method
            try:
                result = await invoke_structured(
                    messages=prompt,
                    output_schema=ProposalMetadataOutput,
                    model="anthropic/claude-haiku-4.5",
                    method="function_calling",
                    include_raw=True,
                    callbacks=callbacks,
                )
                # Handle include_raw response
                if isinstance(result, dict) and "parsed" in result:
                    result = result["parsed"]
                    if result is None:
                        logger.warning(
                            "[MetadataProcessor] Model returned None for parsed result (possible refusal)"
                        )
                        raise ValueError("Model refused to generate structured output")
            except Exception as function_error:
                logger.error(
                    f"[MetadataProcessor] Both methods failed. json_mode: {str(json_mode_error)}, function_calling: {str(function_error)}"
                )
                raise

        result_dict = result.model_dump()

        # Add metadata
        result_dict["content_length"] = len(proposal_content)
        result_dict["dao_name"] = dao_name
        result_dict["proposal_type"] = proposal_type
        result_dict["tags_count"] = len(result_dict.get("tags", []))
        result_dict["media_processed"] = len(proposal_media) if proposal_media else 0

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
