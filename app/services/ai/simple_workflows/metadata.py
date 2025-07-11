"""Simplified proposal metadata generation.

This module provides a functional approach to generating proposal metadata,
converting the complex class-based metadata agent into a simple async function.
"""

from typing import Any, Dict, List, Optional

from langchain_core.prompts.chat import ChatPromptTemplate

from app.lib.logger import configure_logger
from app.services.ai.simple_workflows.llm import invoke_structured
from app.services.ai.simple_workflows.models import ProposalMetadataOutput

logger = configure_logger(__name__)


async def generate_proposal_metadata(
    proposal_content: str,
    dao_name: str = "",
    proposal_type: str = "",
    images: Optional[List[Dict[str, Any]]] = None,
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
            proposal_images=images or [],
        )

        # Create chat prompt template
        prompt = ChatPromptTemplate.from_messages(messages)

        # Get structured output from the LLM
        result = await invoke_structured(
            messages=prompt,
            output_schema=ProposalMetadataOutput,
            callbacks=callbacks,
        )

        result_dict = result.model_dump()

        # Add metadata
        result_dict["content_length"] = len(proposal_content)
        result_dict["dao_name"] = dao_name
        result_dict["proposal_type"] = proposal_type
        result_dict["tags_count"] = len(result_dict.get("tags", []))
        result_dict["images_processed"] = len(images) if images else 0

        logger.info(
            f"[MetadataProcessor] Generated title, summary, and {len(result_dict.get('tags', []))} tags for proposal: {result_dict.get('title', 'Unknown')}"
        )
        return result_dict

    except Exception as e:
        logger.error(
            f"[MetadataProcessor] Error generating proposal metadata: {str(e)}"
        )
        return {
            "error": str(e),
            "title": "",
            "summary": f"Error generating summary: {str(e)}",
            "tags": [],
            "content_length": len(proposal_content) if proposal_content else 0,
            "dao_name": dao_name,
            "proposal_type": proposal_type,
            "tags_count": 0,
            "images_processed": len(images) if images else 0,
        }


def create_chat_messages(
    proposal_content: str,
    dao_name: str,
    proposal_type: str,
    proposal_images: List[Dict[str, Any]] = None,
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
    # System message with guidelines
    system_content = """You are an expert at analyzing DAO proposals and generating comprehensive metadata including titles, summaries, and tags. Create content that accurately represents and categorizes the proposal to help with organization and discoverability.

**Image Evaluation**: If images are attached to this proposal, they are an integral part of the proposal content. You must carefully examine and evaluate any provided images, considering how they support, clarify, or enhance the written proposal. Images may contain diagrams, charts, screenshots, mockups, wireframes, or other visual information that provides crucial context for understanding the proposal's scope, objectives, and implementation details. Include insights from the visual content when generating the title, summary, and tags.

Title Guidelines:
- Keep the title under 100 characters
- Make it descriptive and action-oriented
- Avoid jargon or overly technical language
- Capture the main benefit or outcome
- Include the DAO name if it adds context and clarity

Summary Guidelines:
- Keep the summary under 500 characters (2-3 sentences)
- Explain what the proposal does and why it matters
- Include key objectives or outcomes
- Use clear, accessible language
- Highlight the main benefit to the DAO community

Tag Guidelines:
- Generate exactly 3-5 tags (no more, no less)
- Each tag should be 1-3 words maximum
- Use lowercase for consistency
- Focus on the main themes, topics, and purpose of the proposal
- Include category-based tags (e.g., "governance", "treasury", "technical")
- Include action-based tags (e.g., "funding", "upgrade", "partnership")
- Avoid overly generic tags like "proposal" or "dao"
- Be specific but not too narrow - tags should be useful for filtering
- Consider the scope and impact of the proposal

Common Categories:
- governance: for proposals about DAO structure, voting, rules
- treasury: for proposals about financial management, budgets
- technical: for proposals about code, infrastructure, upgrades
- partnerships: for proposals about collaborations, integrations
- community: for proposals about community building, outreach
- security: for proposals about safety, audits, risk management
- tokenomics: for proposals about token mechanics, rewards
- development: for proposals about product development, features
- marketing: for proposals about promotion, brand, awareness
- operations: for proposals about day-to-day functioning

Output Format:
Provide a JSON object with:
- title: Generated proposal title (max 100 characters)
- summary: Brief summary explaining the proposal (2-3 sentences, max 500 characters)
- tags: Array of 3-5 relevant tags as strings"""

    # User message with proposal content and context
    user_content = f"""Please analyze the following proposal content and generate a title, summary, and tags:

Proposal Content:
{proposal_content}

DAO Name: {dao_name or "the DAO"}
Proposal Type: {proposal_type or "general proposal"}

Based on this information, generate appropriate metadata for this proposal."""

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
