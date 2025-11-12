"""Proposal evaluation with OpenRouter and Grok prompts."""

import httpx
import json

from datetime import datetime
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from uuid import UUID
from urllib.parse import urlparse

from app.backend.factory import backend
from app.backend.models import ContractStatus, ProposalFilter, Proposal
from app.config import config
from app.lib.logger import configure_logger
from app.services.ai.simple_workflows.prompts.evaluation_grok import (
    EVALUATION_GROK_SYSTEM_PROMPT,
    EVALUATION_GROK_USER_PROMPT_TEMPLATE,
)

logger = configure_logger(__name__)

##############################
# Evaluation Input Models   ##
##############################


class DAOInfoForEvaluation(BaseModel):
    """Model representing DAO information for evaluation."""

    dao_id: str
    name: str
    mission: str


class ProposalInfoForEvaluation(BaseModel):
    """Model representing proposal information for evaluation."""

    proposal_number: Optional[int] = None
    title: str
    # content: str # includes metadata/tags
    summary: str
    created_at_timestamp: datetime
    created_at_btc_block: Optional[int] = None
    executable_at_btc_block: Optional[int] = None
    x_url: str
    tx_sender: Optional[str] = None


class TweetPostInfoForEvaluation(BaseModel):
    """Model representing tweet information for evaluation."""

    x_post_id: str
    images: List[str]
    author_name: Optional[str] = None
    author_username: Optional[str] = None
    created_at: str
    public_metrics: Dict[str, int]


class LinkedTweetInformationForEvaluation(BaseModel):
    """Model representing linked tweet information for evaluation."""

    quoted_tweet_id: Optional[str]
    in_reply_to_user_id: Optional[str]
    replied_to_tweet_id: Optional[str]


class TweetAuthorInfoForEvaluation(BaseModel):
    """Model representing tweet author information for evaluation."""

    user_id: str
    name: str
    username: str
    profile_image_url: str
    verified: bool
    verified_type: Optional[str]
    location: Optional[str]


##############################
# Evaluation Output Models  ##
##############################


class EvaluationCategory(BaseModel):
    """Category model for consistent evaluation output."""

    score: int
    reason: str
    evidence: List[str]


class EvaluationOutput(BaseModel):
    """Output model matching expected evaluation JSON structure."""

    current_order: EvaluationCategory
    mission: EvaluationCategory
    value: EvaluationCategory
    values: EvaluationCategory
    originality: EvaluationCategory
    clarity: EvaluationCategory
    safety: EvaluationCategory
    growth: EvaluationCategory
    final_score: int
    confidence: float
    decision: str
    failed: List[str]


###############################
# OpenRouter Helpers         ##
###############################


def get_openrouter_config() -> Dict[str, str]:
    """Get OpenRouter configuration from environment/config.
    Returns:
        Dictionary with OpenRouter configuration
    """
    return {
        "api_key": config.chat_llm.api_key,
        "model": config.chat_llm.default_model or "x-ai/grok-4-fast",
        "base_url": "https://openrouter.ai/api/v1",
        "referer": "https://aibtc.com",
        "title": "AIBTC",
    }


async def call_openrouter(
    messages: List[Dict[str, Any]],
    model: Optional[str] = None,
    temperature: float = 0.0,
    tools: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Make a direct HTTP call to OpenRouter API.

    Args:
        messages: List of chat messages
        model: Optional model override
        temperature: Temperature for generation
        tools: Optional tools for the model

    Returns:
        Response from OpenRouter API
    """
    config_data = get_openrouter_config()

    payload = {
        "model": model or config_data["model"],
        "messages": messages,
        "temperature": temperature,
    }

    if tools:
        payload["tools"] = tools

    headers = {
        "Authorization": f"Bearer {config_data['api_key']}",
        "HTTP-Referer": config_data["referer"],
        "X-Title": config_data["title"],
        "Content-Type": "application/json",
    }

    print(f"Making OpenRouter API call to model: {payload['model']}")

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{config_data['base_url']}/chat/completions", json=payload, headers=headers
        )
        response.raise_for_status()
        return response.json()


###############################
# Evaluation Helpers         ##
###############################


def _format_proposals_for_context(proposals: List[Proposal]) -> str:
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
            proposal_passed = "pending"

        # Get content
        content = getattr(proposal, "summary", "") or getattr(proposal, "content", "")
        content_preview = content[:500] + "..." if len(content) > 500 else content

        formatted_proposal = f"""\n- #{proposal_id or "n/a"} by @{x_handle} Created: {created_at} Passed: {proposal_passed} Title: {title} Summary: {content_preview}"""

        formatted_proposals.append(formatted_proposal)

    return "\n".join(formatted_proposals)


def _fetch_and_format_dao_info(dao_id: str) -> Optional[DAOInfoForEvaluation]:
    """Fetch and format DAO information for evaluation."""
    dao = backend.get_dao(dao_id)
    if not dao:
        logger.error(f"DAO {dao_id} not found")
        return None
    return DAOInfoForEvaluation(
        dao_id=str(dao.id),
        name=dao.name,
        mission=dao.mission,
    )


def _fetch_and_format_proposal_info(proposal: Proposal) -> ProposalInfoForEvaluation:
    """Fetch and format proposal information for evaluation."""
    return ProposalInfoForEvaluation(
        proposal_number=proposal.proposal_id,
        title=proposal.title,
        summary=proposal.summary,
        created_at_timestamp=proposal.created_at,
        created_at_btc_block=proposal.created_btc,
        executable_at_btc_block=proposal.exec_start,
        x_url=proposal.x_url,
        tx_sender=proposal.tx_sender,
    )


def _fetch_and_format_tweet_info(
    proposal: Proposal,
) -> Optional[TweetPostInfoForEvaluation]:
    """Fetch and format tweet information for evaluation."""
    if not proposal.tweet_id:
        return None
    tweet_content = backend.get_x_tweet(proposal.tweet_id)
    if not tweet_content:
        return None
    return TweetPostInfoForEvaluation(
        x_post_id=str(tweet_content.tweet_id),
        images=tweet_content.images or [],
        author_name=tweet_content.author_name or "",
        author_username=tweet_content.author_username or "",
        created_at=tweet_content.created_at_twitter
        if tweet_content.created_at_twitter
        else "",
        public_metrics=dict(tweet_content.public_metrics)
        if tweet_content.public_metrics
        else {},
    )


def _fetch_and_format_tweet_author_info(
    proposal: Proposal,
) -> Optional[TweetAuthorInfoForEvaluation]:
    """Fetch and format tweet author information for evaluation."""
    tweet_content = (
        backend.get_x_tweet(proposal.tweet_id) if proposal.tweet_id else None
    )
    if not tweet_content or not tweet_content.author_id:
        return None
    author_content = backend.get_x_user(tweet_content.author_id)
    if not author_content:
        return None
    return TweetAuthorInfoForEvaluation(
        user_id=str(author_content.user_id),
        name=author_content.name,
        username=author_content.username,
        profile_image_url=author_content.profile_image_url or "",
        verified=author_content.verified,
        verified_type=author_content.verified_type,
        location=author_content.location,
    )


def _fetch_and_format_linked_tweet_info(
    proposal: Proposal, link_type: str
) -> Optional[TweetPostInfoForEvaluation]:
    """Fetch and format quoted or replied-to tweet information for evaluation."""
    tweet_content = (
        backend.get_x_tweet(proposal.tweet_id) if proposal.tweet_id else None
    )
    if not tweet_content:
        return None

    linked_tweet_db_id = None
    if link_type == "quoted" and tweet_content.quoted_tweet_db_id:
        linked_tweet_db_id = tweet_content.quoted_tweet_db_id
    elif link_type == "replied_to" and tweet_content.replied_to_tweet_db_id:
        linked_tweet_db_id = tweet_content.replied_to_tweet_db_id
    else:
        return None

    linked_tweet_content = backend.get_x_tweet(linked_tweet_db_id)
    if not linked_tweet_content:
        return None
    return TweetPostInfoForEvaluation(
        x_post_id=str(linked_tweet_content.tweet_id),
        images=linked_tweet_content.images or [],
        author_name=linked_tweet_content.author_name or "",
        author_username=linked_tweet_content.author_username or "",
        created_at=linked_tweet_content.created_at_twitter
        if linked_tweet_content.created_at_twitter
        else "",
        public_metrics=dict(linked_tweet_content.public_metrics)
        if linked_tweet_content.public_metrics
        else {},
    )


def _fetch_past_proposals_context(
    proposal: Proposal,
) -> tuple[Optional[str], Dict[str, int], Optional[str], Optional[str]]:
    """Fetch and format past proposals for evaluation context."""
    dao_proposals = backend.list_proposals(ProposalFilter(dao_id=proposal.dao_id))
    dao_proposals = [p for p in dao_proposals if p.id != proposal.id]

    # User past proposals
    user_past_proposals_for_evaluation = None
    if proposal.tx_sender:
        user_past_proposals = [
            p for p in dao_proposals if p.tx_sender == proposal.tx_sender
        ]
        user_past_proposals_for_evaluation = _format_proposals_for_context(
            user_past_proposals
        )

    # DAO past proposals
    dao_past_proposals = [
        p for p in dao_proposals if user_past_proposals and p not in user_past_proposals
    ] or dao_proposals
    sorted_dao_past_proposals = sorted(
        dao_past_proposals,
        key=lambda p: getattr(p, "created_at", datetime.min),
        reverse=True,
    )

    dao_past_proposals_categorized = {
        "ALL": sorted_dao_past_proposals,
        "DRAFT": [
            p for p in sorted_dao_past_proposals if p.status == ContractStatus.DRAFT
        ],
        "PENDING": [
            p for p in sorted_dao_past_proposals if p.status == ContractStatus.PENDING
        ],
        "DEPLOYED": [
            p for p in sorted_dao_past_proposals if p.status == ContractStatus.DEPLOYED
        ],
        "FAILED": [
            p for p in sorted_dao_past_proposals if p.status == ContractStatus.FAILED
        ],
    }

    dao_past_proposals_stats_for_evaluation = {
        "ALL": len(sorted_dao_past_proposals),
        "DRAFT": len(dao_past_proposals_categorized["DRAFT"]),
        "PENDING": len(dao_past_proposals_categorized["PENDING"]),
        "DEPLOYED": len(dao_past_proposals_categorized["DEPLOYED"]),
        "FAILED": len(dao_past_proposals_categorized["FAILED"]),
    }

    # Limit drafts to last 20
    dao_draft_proposals = dao_past_proposals_categorized["DRAFT"][:20]
    dao_draft_proposals_for_evaluation = _format_proposals_for_context(
        dao_draft_proposals
    )

    # Limit deployed to last 100
    dao_deployed_proposals = dao_past_proposals_categorized["DEPLOYED"][:100]
    dao_deployed_proposals_for_evaluation = _format_proposals_for_context(
        dao_deployed_proposals
    )

    return (
        user_past_proposals_for_evaluation,
        dao_past_proposals_stats_for_evaluation,
        dao_draft_proposals_for_evaluation,
        dao_deployed_proposals_for_evaluation,
    )


def _prepare_images_for_evaluation(tweet_images: List[str]) -> List[Dict[str, Any]]:
    """Prepare images for evaluation context."""
    images = []
    for img_url in tweet_images:
        parsed_url = urlparse(img_url)
        if parsed_url.scheme in ["http", "https"]:
            images.append(
                {
                    "type": "image_url",
                    "image_url": {"url": img_url, "detail": "auto"},
                }
            )
    return images


###############################
## Main Evaluation Function  ##
###############################


async def evaluate_proposal_openrouter(
    proposal_id: str | UUID,
    model: Optional[str] = None,
    temperature: float = 0.7,
) -> Optional[EvaluationOutput]:
    """
    Evaluate a proposal using OpenRouter and Grok prompts.

    Args:
        proposal_id: UUID of the proposal to evaluate.
        model: Optional model override (e.g., 'x-ai/grok-4').
        temperature: Generation temperature.

    Returns:
        Parsed EvaluationOutput or None if evaluation fails.
    """
    try:
        # parse the uuid
        if isinstance(proposal_id, str):
            proposal_uuid = UUID(proposal_id)
        elif isinstance(proposal_id, UUID):
            proposal_uuid = proposal_id
        else:
            logger.error(f"Invalid proposal_id type: {type(proposal_id)}")
            return None
        # get the proposal from backend
        proposal = backend.get_proposal(proposal_uuid)
        if not proposal:
            logger.error(f"Proposal {proposal_id} not found")
            return None

        logger.info(f"Starting evaluation for proposal ID: {proposal_id}")

        # fetch and format inputs using Pydantic models
        dao_info = _fetch_and_format_dao_info(str(proposal.dao_id))
        if not dao_info:
            logger.error(f"DAO not found for proposal {proposal_id}")
            return None

        proposal_info = _fetch_and_format_proposal_info(proposal)
        tweet_info = _fetch_and_format_tweet_info(proposal)
        tweet_author_info = _fetch_and_format_tweet_author_info(proposal)
        quote_tweet_info = _fetch_and_format_linked_tweet_info(proposal, "quoted")
        reply_tweet_info = _fetch_and_format_linked_tweet_info(proposal, "replied_to")

        # fetch past proposals context
        (
            user_past_proposals_for_evaluation,
            dao_past_proposals_stats_for_evaluation,
            dao_draft_proposals_for_evaluation,
            dao_deployed_proposals_for_evaluation,
        ) = _fetch_past_proposals_context(proposal)

        formatted_info_collection = [
            proposal_info,
            tweet_info,
            tweet_author_info,
            quote_tweet_info,
            reply_tweet_info,
            user_past_proposals_for_evaluation,
            dao_past_proposals_stats_for_evaluation,
            dao_draft_proposals_for_evaluation,
            dao_deployed_proposals_for_evaluation,
        ]

        # check and log any missing data
        missing_info_fields = [
            type(info).__name__ for info in formatted_info_collection if info is None
        ]
        if missing_info_fields:
            logger.warning(
                f"Some information missing for proposal {proposal_id}",
                extra={missing_info_fields},
            )

        # Prepare images
        images_for_evaluation = _prepare_images_for_evaluation(
            [] if not tweet_info else tweet_info.images
        )

        # Load prompts
        system_prompt = EVALUATION_GROK_SYSTEM_PROMPT
        user_prompt = EVALUATION_GROK_USER_PROMPT_TEMPLATE
        if not system_prompt or not user_prompt:
            logger.error("Could not load evaluation prompts")
            return None

        # format messages starting with system message
        messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]

        # fill in user prompt with collected info
        formatted_user_content = user_prompt.format(
            dao_info_for_evaluation=dao_info.model_dump_json(),
            proposal_content_for_evaluation=proposal_info.model_dump_json(),
            tweet_info_for_evaluation=tweet_info.model_dump_json()
            if tweet_info
            else None,
            tweet_author_info_for_evaluation=tweet_author_info.model_dump_json()
            if tweet_author_info
            else None,
            quote_tweet_info_for_evaluation=quote_tweet_info.model_dump_json()
            if quote_tweet_info
            else None,
            reply_tweet_info_for_evaluation=reply_tweet_info.model_dump_json()
            if reply_tweet_info
            else None,
            dao_past_proposals_stats_for_evaluation=json.dumps(
                dao_past_proposals_stats_for_evaluation
            ),
            user_past_proposals_for_evaluation=user_past_proposals_for_evaluation or "",
            dao_draft_proposals_for_evaluation=dao_draft_proposals_for_evaluation or "",
            dao_deployed_proposals_for_evaluation=dao_deployed_proposals_for_evaluation
            or "",
        )

        # build user content with text and images
        user_content = [{"type": "text", "text": formatted_user_content}]
        user_content.extend(images_for_evaluation)

        # add user message alongside system message
        messages.append({"role": "user", "content": user_content})

        # call openrouter passing x tools and message
        x_ai_tools = [{"type": "web_search"}, {"type": "x_search"}]
        openrouter_response = await call_openrouter(
            messages=messages,
            model=model,
            temperature=temperature,
            tools=x_ai_tools,
        )

        # Parse response
        choices = openrouter_response.get("choices", [])
        if not choices:
            logger.error("No choices in OpenRouter response")
            return None

        first_choice = choices[0]
        choice_message = first_choice.get("message")
        if not choice_message or not isinstance(choice_message.get("content"), str):
            logger.error("Invalid message content in response")
            return None

        try:
            evaluation_json = json.loads(choice_message["content"])
            evaluation_output = EvaluationOutput(**evaluation_json)
            logger.info(f"Successfully evaluated proposal {proposal_id}")

            return evaluation_output

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return None
        except ValueError as e:
            logger.error(f"Pydantic validation error: {e}")
            return None

    except Exception as e:
        logger.error(f"Error during evaluation of proposal {proposal_id}: {e}")
        return None
