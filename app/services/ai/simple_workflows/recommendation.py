"""Simplified proposal recommendation generation.

This module provides a functional approach to generating proposal recommendations,
converting the complex class-based recommendation agent into a simple async function.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from langchain_core.prompts.chat import ChatPromptTemplate

from app.backend.factory import backend
from app.backend.models import DAO, Proposal, ProposalFilter
from app.lib.logger import configure_logger
from app.services.ai.simple_workflows.llm import invoke_structured
from app.services.ai.simple_workflows.models import ProposalRecommendationOutput
from app.services.ai.simple_workflows.prompts import (
    RECOMMENDATION_SYSTEM_PROMPT,
    RECOMMENDATION_USER_PROMPT_TEMPLATE,
)

logger = configure_logger(__name__)


async def generate_proposal_recommendation(
    dao_id: UUID,
    focus_area: str = "",
    specific_needs: str = "",
    images: Optional[List[Dict[str, Any]]] = None,
    callbacks: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    """Generate a proposal recommendation for a DAO.

    Args:
        dao_id: UUID of the DAO
        focus_area: Focus area for the recommendation
        specific_needs: Specific needs mentioned
        images: List of processed images
        callbacks: Optional callback handlers for streaming

    Returns:
        Dictionary containing the generated recommendation
    """
    logger.info(f"[RecommendationProcessor] Generating recommendation for DAO {dao_id}")

    try:
        # Fetch DAO information
        dao_info = await fetch_dao_info(dao_id)
        if not dao_info:
            logger.error(
                f"[RecommendationProcessor] Could not fetch DAO info for {dao_id}"
            )
            return {
                "error": f"Could not fetch DAO info for {dao_id}",
                "title": "",
                "content": "",
                "rationale": "",
                "priority": "low",
                "estimated_impact": "",
                "suggested_action": "",
            }

        # Fetch recent proposals for context
        recent_proposals = await fetch_dao_proposals(dao_id, limit=10)
        recent_proposals_text = format_proposals_for_context(recent_proposals)

        # Create chat messages
        messages = create_chat_messages(
            dao_name=dao_info.name or "Unknown DAO",
            dao_mission=dao_info.mission or "No mission statement available",
            dao_description=dao_info.description or "No description available",
            recent_proposals=recent_proposals_text,
            focus_area=focus_area,
            specific_needs=specific_needs,
            proposal_images=images or [],
        )

        # Create chat prompt template
        prompt = ChatPromptTemplate.from_messages(messages)

        # Get structured output from the LLM
        result = await invoke_structured(
            messages=prompt,
            output_schema=ProposalRecommendationOutput,
            callbacks=callbacks,
        )

        result_dict = result.model_dump()

        # Add metadata
        result_dict["dao_id"] = str(dao_id)
        result_dict["dao_name"] = dao_info.name or "Unknown DAO"
        result_dict["focus_area"] = focus_area
        result_dict["specific_needs"] = specific_needs
        result_dict["recent_proposals_count"] = len(recent_proposals)
        result_dict["images_processed"] = len(images) if images else 0

        logger.info(
            f"[RecommendationProcessor] Generated recommendation: {result_dict.get('title', 'Unknown')}"
        )
        return result_dict

    except Exception as e:
        logger.error(
            f"[RecommendationProcessor] Error generating proposal recommendation: {str(e)}"
        )
        return {
            "error": str(e),
            "title": "",
            "content": f"Error generating recommendation: {str(e)}",
            "rationale": "",
            "priority": "low",
            "estimated_impact": "",
            "suggested_action": "",
            "dao_id": str(dao_id),
            "dao_name": "Unknown DAO",
            "focus_area": focus_area,
            "specific_needs": specific_needs,
            "recent_proposals_count": 0,
            "images_processed": len(images) if images else 0,
        }


async def fetch_dao_info(dao_id: UUID) -> Optional[DAO]:
    """Fetch DAO information from database.

    Args:
        dao_id: UUID of the DAO

    Returns:
        DAO object or None if not found
    """
    try:
        dao = backend.get_dao(dao_id)
        if dao:
            logger.debug(f"Retrieved DAO info for {dao_id}: {dao.name}")
            return dao
        else:
            logger.warning(f"DAO with ID {dao_id} not found")
            return None
    except Exception as e:
        logger.error(f"Error fetching DAO info for {dao_id}: {str(e)}")
        return None


async def fetch_dao_proposals(dao_id: UUID, limit: int = 50) -> List[Proposal]:
    """Fetch recent proposals for a DAO.

    Args:
        dao_id: UUID of the DAO
        limit: Maximum number of proposals to fetch

    Returns:
        List of recent proposals
    """
    try:
        # Create filter to get proposals for this DAO
        filters = ProposalFilter(dao_id=dao_id)

        # Fetch proposals
        proposals = backend.list_proposals(filters)

        # Sort by creation date (newest first) and limit results
        sorted_proposals = sorted(proposals, key=lambda p: p.created_at, reverse=True)
        limited_proposals = sorted_proposals[:limit]

        logger.debug(
            f"Retrieved {len(limited_proposals)} recent proposals for DAO {dao_id}"
        )
        return limited_proposals
    except Exception as e:
        logger.error(f"Error fetching proposals for DAO {dao_id}: {str(e)}")
        return []


def format_proposals_for_context(proposals: List[Proposal]) -> str:
    """Format proposals for inclusion in the prompt.

    Args:
        proposals: List of proposals

    Returns:
        Formatted text of past proposals
    """
    if not proposals:
        return "<no_proposals>No past proposals available.</no_proposals>"

    formatted_proposals = []
    for i, proposal in enumerate(proposals):
        try:
            # Safely get proposal attributes with proper error handling
            title = getattr(proposal, "title", None) or "Untitled"
            content = getattr(proposal, "content", None) or "No content"
            proposal_type = getattr(proposal, "type", None) or "Unknown"
            status = getattr(proposal, "status", None) or "Unknown"
            passed = getattr(proposal, "passed", None)

            # Safely handle created_at date formatting
            created_at = getattr(proposal, "created_at", None)
            created_str = "Unknown"
            if created_at:
                try:
                    created_str = created_at.strftime("%Y-%m-%d")
                except (AttributeError, ValueError):
                    created_str = str(created_at)

            # Safely convert content to string and limit length
            content_str = str(content)[:500] if content else "No content"

            # Ensure content is treated as plain text and safe for prompt processing
            # Remove any control characters that might cause parsing issues
            content_str = "".join(
                char for char in content_str if ord(char) >= 32 or char in "\n\r\t"
            )

            # Escape curly braces to prevent f-string/format interpretation issues
            content_str = content_str.replace("{", "{{").replace("}", "}}")

            proposal_text = f"""<proposal id="{i + 1}">
  <title>{str(title)[:100]}</title>
  <content>{content_str}</content>
  <type>{str(proposal_type)}</type>
  <status>{str(status)}</status>
  <created>{created_str}</created>
  <passed>{str(passed) if passed is not None else "Unknown"}</passed>
</proposal>"""
            formatted_proposals.append(proposal_text)
        except Exception as e:
            logger.error(f"Error formatting proposal {i}: {str(e)}")
            # Add a fallback proposal entry
            formatted_proposals.append(
                f"""<proposal id="{i + 1}">
  <title>Error loading proposal</title>
  <content>Could not load proposal data: {str(e)}</content>
  <type>Unknown</type>
  <status>Unknown</status>
  <created>Unknown</created>
  <passed>Unknown</passed>
</proposal>"""
            )

    return "\n\n".join(formatted_proposals)


def create_chat_messages(
    dao_name: str,
    dao_mission: str,
    dao_description: str,
    recent_proposals: str,
    focus_area: str,
    specific_needs: str,
    proposal_images: List[Dict[str, Any]] = None,
) -> List:
    """Create chat messages for the proposal recommendation.

    Args:
        dao_name: Name of the DAO
        dao_mission: Mission statement of the DAO
        dao_description: Description of the DAO
        recent_proposals: Formatted recent proposals text
        focus_area: Focus area for the recommendation
        specific_needs: Specific needs mentioned
        proposal_images: List of processed images

    Returns:
        List of chat messages
    """
    # Use the system prompt from the prompts package
    system_content = RECOMMENDATION_SYSTEM_PROMPT

    # Use the user prompt template from the prompts package
    user_content = RECOMMENDATION_USER_PROMPT_TEMPLATE.format(
        dao_name=dao_name,
        dao_mission=dao_mission,
        dao_description=dao_description,
        recent_proposals=recent_proposals,
        focus_area=focus_area
        if focus_area
        else "No specific focus area provided - recommend based on DAO mission and recent proposal patterns",
        specific_needs=specific_needs
        if specific_needs
        else "No specific needs mentioned - identify opportunities based on DAO context",
    )

    messages = [{"role": "system", "content": system_content}]

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
