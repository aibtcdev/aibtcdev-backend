"""Simplified proposal evaluation logic.

This module provides a functional approach to proposal evaluation, converting
the complex class-based evaluator into a simple async function.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from langchain_core.documents import Document
from langchain_core.prompts.chat import ChatPromptTemplate
from langchain_openai import OpenAIEmbeddings

from app.backend.factory import backend
from app.backend.models import Proposal, ProposalFilter
from app.config import config
from app.lib.logger import configure_logger
from app.services.ai.simple_workflows.llm import invoke_structured
from app.services.ai.simple_workflows.models import (
    ComprehensiveEvaluatorAgentProcessOutput,
    ComprehensiveEvaluationOutput,
)
from app.services.ai.simple_workflows.processors.twitter import (
    fetch_tweet,
    format_tweet,
    format_tweet_images,
)
from app.services.ai.simple_workflows.processors.airdrop import (
    process_airdrop,
)

logger = configure_logger(__name__)

# Import prompts from the prompts package
from app.services.ai.simple_workflows.prompts import (
    EVALUATION_SYSTEM_PROMPT as DEFAULT_SYSTEM_PROMPT,
    EVALUATION_USER_PROMPT_TEMPLATE as DEFAULT_USER_PROMPT_TEMPLATE,
)


def create_embedding_model() -> OpenAIEmbeddings:
    """Create an OpenAI embeddings model using the configured settings.

    Returns:
        Configured OpenAIEmbeddings instance
    """
    embedding_config = {
        "model": config.embedding.default_model,
    }

    # Add base_url if configured
    if config.embedding.api_base:
        embedding_config["base_url"] = config.embedding.api_base

    # Add api_key if configured
    if config.embedding.api_key:
        embedding_config["api_key"] = config.embedding.api_key

    logger.debug(
        f"Creating OpenAI embeddings with model: {config.embedding.default_model}"
    )
    return OpenAIEmbeddings(**embedding_config)


async def fetch_dao_proposals(
    dao_id: UUID, exclude_proposal_id: Optional[str] = None
) -> List[Proposal]:
    """Fetch all proposals for a specific DAO from database, excluding the current proposal.

    Args:
        dao_id: The UUID of the DAO
        exclude_proposal_id: Optional proposal ID to exclude from results

    Returns:
        List of Proposal objects (excluding the current proposal if specified)
    """
    try:
        # Create filter to get all proposals for this DAO
        filters = ProposalFilter(dao_id=dao_id)

        # Fetch proposals
        proposals = backend.list_proposals(filters)

        # Filter out the current proposal if specified
        if exclude_proposal_id:
            proposals = [p for p in proposals if str(p.id) != exclude_proposal_id]
            logger.debug(
                f"Excluded current proposal {exclude_proposal_id} from historical context"
            )

        logger.debug(
            f"Retrieved {len(proposals)} proposals for DAO {dao_id} (excluding current)"
        )
        return proposals
    except Exception as e:
        logger.error(f"Error fetching proposals for DAO {dao_id}: {str(e)}")
        return []


def format_proposals_for_context(proposals: List[Proposal]) -> str:
    """Format proposals for inclusion in the prompt.

    Args:
        proposals: List of all proposals

    Returns:
        Formatted text of past proposals
    """
    if not proposals:
        return "<no_proposals>No past proposals available.</no_proposals>"

    try:
        # Sort proposals by creation date (newest first to prioritize recent history)
        sorted_proposals = []
        for proposal in proposals:
            try:
                created_at = getattr(proposal, "created_at", None)
                if created_at:
                    sorted_proposals.append((proposal, created_at))
                else:
                    sorted_proposals.append((proposal, None))
            except Exception as e:
                logger.warning(f"Error accessing created_at for proposal: {str(e)}")
                sorted_proposals.append((proposal, None))

        # Sort by created_at, handling None values
        sorted_proposals.sort(
            key=lambda x: x[1] if x[1] is not None else 0, reverse=True
        )
    except Exception as e:
        logger.error(f"Error sorting proposals: {str(e)}")
        sorted_proposals = [(proposal, None) for proposal in proposals]

    # Format individual proposals with all relevant details
    formatted_proposals = []
    for i, (proposal, _) in enumerate(
        sorted_proposals[:8]
    ):  # Limit to first 8 for context
        try:
            # Safely get proposal attributes with proper error handling
            title = getattr(proposal, "title", None) or "Untitled"
            summary = (
                getattr(proposal, "summary", None)
                or getattr(proposal, "content", None)
                or "No summary"
            )
            status = getattr(proposal, "status", None) or "Unknown"
            proposal_type = getattr(proposal, "type", None) or "Unknown"
            passed = getattr(proposal, "passed", None)
            action = getattr(proposal, "action", None) or "None"
            creator = getattr(proposal, "creator", None) or "Unknown"
            tags = getattr(proposal, "tags", None) or []
            executed = getattr(proposal, "executed", None)
            votes_for = getattr(proposal, "votes_for", None) or 0
            votes_against = getattr(proposal, "votes_against", None) or 0
            met_quorum = getattr(proposal, "met_quorum", None)
            met_threshold = getattr(proposal, "met_threshold", None)

            # Safely handle created_at date formatting
            created_at = getattr(proposal, "created_at", None)
            created_str = "Unknown"
            if created_at:
                try:
                    created_str = created_at.strftime("%Y-%m-%d")
                except (AttributeError, ValueError):
                    created_str = str(created_at)

            # Safely convert summary to string and limit length
            summary_str = str(summary)[:500] if summary else "No summary"

            # Ensure summary is treated as plain text and safe for prompt processing
            summary_str = "".join(
                char for char in summary_str if ord(char) >= 32 or char in "\n\r\t"
            )

            # Escape curly braces to prevent f-string/format interpretation issues
            summary_str = summary_str.replace("{", "{{").replace("}", "}}")

            # Format tags as a comma-separated string
            tags_str = (
                ", ".join(str(tag) for tag in (tags if isinstance(tags, list) else []))
                if tags
                else "None"
            )

            proposal_text = (
                f'<proposal id="{i + 1}">\n'
                f"  <title>{str(title)[:100]}</title>\n"
                f"  <summary>{summary_str}</summary>\n"
                f"  <creator>{str(creator)}</creator>\n"
                f"  <status>{str(status)}</status>\n"
                f"  <type>{str(proposal_type)}</type>\n"
                f"  <created_at>{created_str}</created_at>\n"
                f"  <passed>{str(passed) if passed is not None else 'False'}</passed>\n"
                f"  <executed>{str(executed) if executed is not None else 'False'}</executed>\n"
                f"  <votes_for>{str(votes_for)}</votes_for>\n"
                f"  <votes_against>{str(votes_against)}</votes_against>\n"
                f"  <met_quorum>{str(met_quorum) if met_quorum is not None else 'Unknown'}</met_quorum>\n"
                f"  <met_threshold>{str(met_threshold) if met_threshold is not None else 'Unknown'}</met_threshold>\n"
                f"  <tags>{tags_str}</tags>\n"
                f"  <action>{str(action)}</action>\n"
                f"</proposal>"
            )

            formatted_proposals.append(proposal_text)
        except Exception as e:
            logger.error(f"Error formatting proposal {i}: {str(e)}")
            # Add a fallback proposal entry
            formatted_proposals.append(
                f'<proposal id="{i + 1}">\n'
                f"  <title>Error loading proposal</title>\n"
                f"  <summary>Could not load proposal data: {str(e)}</summary>\n"
                f"  <creator>Unknown</creator>\n"
                f"  <status>Unknown</status>\n"
                f"  <type>Unknown</type>\n"
                f"  <created_at>Unknown</created_at>\n"
                f"  <passed>Unknown</passed>\n"
                f"  <executed>Unknown</executed>\n"
                f"  <votes_for>0</votes_for>\n"
                f"  <votes_against>0</votes_against>\n"
                f"  <met_quorum>Unknown</met_quorum>\n"
                f"  <met_threshold>Unknown</met_threshold>\n"
                f"  <tags>None</tags>\n"
                f"  <action>None</action>\n"
                f"</proposal>"
            )

    return (
        "\n\n".join(formatted_proposals)
        if formatted_proposals
        else "<no_proposals>No past proposals available.</no_proposals>"
    )


def format_proposals_for_context_v2(proposals: List[Proposal], limit: int = 50) -> str:
    if not proposals:
        return "<no_proposals>No past proposals available.</no_proposals>"

    # Filter to only DEPLOYED or FAILED status
    filtered_proposals = [
        p for p in proposals
        if getattr(p, "status", None) in ["DEPLOYED", "FAILED"]
    ]
    if not filtered_proposals:
        return "<no_proposals>No qualifying past proposals (DEPLOYED or FAILED) available.</no_proposals>"

    # Sort by created_at descending (newest first)
    sorted_proposals = sorted(
        filtered_proposals,
        key=lambda p: p.created_at if p.created_at else 0,
        reverse=True
    )

    formatted = []
    for i, proposal in enumerate(sorted_proposals[:limit]):
        try:
            title = str(getattr(proposal, "title", "Untitled"))[:100]
            summary = str(getattr(proposal, "summary", getattr(proposal, "content", "No summary")))[:250]
            summary = "".join(char for char in summary if ord(char) >= 32 or char in "\n\r\t")  # Remove control chars
            summary = summary.replace("{", "{{").replace("}", "}}")  # Escape braces
            if len(summary) == 250: summary += "..."
            
            creator = str(getattr(proposal, "creator", "Unknown"))
            passed = str(getattr(proposal, "passed", False)).upper()  # "TRUE" or "FALSE"
            tags = ", ".join(str(tag) for tag in getattr(proposal, "tags", []) or []) or "None"
            x_url = str(getattr(proposal, "x_url", "None"))
            
            prop_text = (
                f"- Proposal {i+1}\n"
                f"  Title: {title}\n"
                f"  Summary: {summary}\n"
                f"  Creator: {creator}\n"
                f"  Passed: {passed}\n"
                f"  Tags: {tags}\n"
                f"  X_URL: {x_url}"
            )
            formatted.append(prop_text)
        except Exception as e:
            formatted.append(f"- Proposal {i+1}: Error loading data ({str(e)})")
    
    return "\n\n".join(formatted) if formatted else "<no_proposals>No past proposals available.</no_proposals>"


async def retrieve_from_vector_store(
    query: str,
    collection_name: str = "past_proposals",
    limit: int = 3,
    embeddings: Optional[OpenAIEmbeddings] = None,
) -> List[Document]:
    """Retrieve relevant documents from vector store.

    Args:
        query: The query to search for
        collection_name: Name of the vector collection
        limit: Number of documents to retrieve
        embeddings: Optional embeddings model

    Returns:
        List of retrieved documents
    """
    try:
        if embeddings is None:
            embeddings = create_embedding_model()

        vector_results = await backend.query_vectors(
            collection_name=collection_name,
            query_text=query,
            limit=limit,
            embeddings=embeddings,
        )

        documents = [
            Document(
                page_content=doc.get("page_content", ""),
                metadata={
                    **doc.get("metadata", {}),
                    "collection_source": collection_name,
                },
            )
            for doc in vector_results
        ]

        logger.debug(f"Retrieved {len(documents)} documents from vector store")
        return documents
    except Exception as e:
        logger.error(f"Vector store retrieval failed: {str(e)}")
        return []


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
) -> List:
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

    # Use custom user prompt or default, format with data
    if custom_user_prompt:
        # Format custom user prompt with the same data
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
            if ord(char) >= 32 or char in "\n\r\t"
        )
        # Escape curly braces to prevent f-string/format interpretation issues
        escaped_tweet_content = escaped_tweet_content.replace("{", "{{").replace(
            "}", "}}"
        )

        messages.append(
            {
                "role": "user",
                "content": f"Referenced tweets in this proposal:\n\n{escaped_tweet_content}",
            }
        )
        logger.debug(
            f"Added escaped tweet content to messages: {escaped_tweet_content[:100]}..."
        )

    # Add airdrop content as separate user message if available
    if airdrop_content and airdrop_content.strip():
        # Safely escape airdrop content to prevent JSON/format issues
        escaped_airdrop_content = str(airdrop_content)
        # Remove or replace control characters (keep common whitespace)
        escaped_airdrop_content = "".join(
            char
            for char in escaped_airdrop_content
            if ord(char) >= 32 or char in "\n\r\t"
        )
        # Escape curly braces to prevent f-string/format interpretation issues
        escaped_airdrop_content = escaped_airdrop_content.replace("{", "{{").replace(
            "}", "}}"
        )

        messages.append(
            {
                "role": "user",
                "content": f"Associated airdrop data for this proposal:\n\n{escaped_airdrop_content}",
            }
        )
        logger.debug(
            f"Added escaped airdrop content to messages: {escaped_airdrop_content[:100]}..."
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


async def evaluate_proposal(
    proposal_content: str,
    dao_id: Optional[UUID] = None,
    proposal_id: Optional[UUID] = None,
    images: Optional[List[Dict[str, Any]]] = None,
    tweet_content: Optional[str] = None,
    airdrop_content: Optional[str] = None,
    custom_system_prompt: Optional[str] = None,
    custom_user_prompt: Optional[str] = None,
    callbacks: Optional[List[Any]] = None,
) -> ComprehensiveEvaluatorAgentProcessOutput:
    """Evaluate a proposal comprehensively.

    Args:
        proposal_content: The proposal content to evaluate
        dao_id: Optional DAO ID for context
        proposal_id: Optional proposal UUID for fetching linked tweet content
        images: Optional list of processed images
        tweet_content: Optional tweet content (will be fetched from DB if proposal_id provided)
        airdrop_content: Optional airdrop content (will be fetched from DB if proposal_id provided)
        custom_system_prompt: Optional custom system prompt
        custom_user_prompt: Optional custom user prompt
        callbacks: Optional callback handlers for streaming

    Returns:
        Comprehensive evaluation output
    """
    proposal_id_str = str(proposal_id) if proposal_id else "unknown"
    logger.info(
        f"[EvaluationProcessor:{proposal_id_str}] Starting comprehensive evaluation"
    )

    # Fetch tweet content from the proposal's linked tweet if available
    linked_tweet_images = []
    if proposal_id and not tweet_content:
        try:
            logger.debug(
                f"[EvaluationProcessor:{proposal_id_str}] Fetching proposal to get linked tweet content"
            )
            proposal = backend.get_proposal(proposal_id)
            if proposal and proposal.tweet_id:
                logger.debug(
                    f"[EvaluationProcessor:{proposal_id_str}] Found linked tweet_id: {proposal.tweet_id}"
                )
                # Use twitter processor to fetch and format tweet content
                tweet_data = await fetch_tweet(proposal.tweet_id)
                if tweet_data:
                    # Format tweet content using twitter processor
                    tweet_content = format_tweet(tweet_data)
                    logger.debug(
                        f"[EvaluationProcessor:{proposal_id_str}] Retrieved and formatted tweet content: {tweet_content}"
                    )

                    # Also extract any images from the linked tweet
                    linked_tweet_images = format_tweet_images(
                        tweet_data, proposal.tweet_id
                    )
                    if linked_tweet_images:
                        logger.debug(
                            f"[EvaluationProcessor:{proposal_id_str}] Found {len(linked_tweet_images)} images in linked tweet"
                        )
                else:
                    logger.warning(
                        f"[EvaluationProcessor:{proposal_id_str}] Could not fetch tweet data for tweet_id: {proposal.tweet_id}"
                    )
            else:
                logger.debug(
                    f"[EvaluationProcessor:{proposal_id_str}] No linked tweet found for proposal"
                )
        except Exception as e:
            logger.error(
                f"[EvaluationProcessor:{proposal_id_str}] Error fetching linked tweet content: {str(e)}"
            )

    # Fetch airdrop content from the proposal's linked airdrop if available and not provided
    if proposal_id and not airdrop_content:
        try:
            logger.debug(
                f"[EvaluationProcessor:{proposal_id_str}] Fetching proposal to get linked airdrop content"
            )
            # Check if we already have the proposal from above
            if "proposal" not in locals() or not proposal:
                proposal = backend.get_proposal(proposal_id)

            if proposal and proposal.airdrop_id:
                logger.debug(
                    f"[EvaluationProcessor:{proposal_id_str}] Found linked airdrop_id: {proposal.airdrop_id}"
                )
                # Use airdrop processor to fetch and format airdrop content
                airdrop_content = await process_airdrop(
                    proposal.airdrop_id, proposal_id_str
                )
                if airdrop_content:
                    logger.info(
                        f"[EvaluationProcessor:{proposal_id_str}] Retrieved and formatted airdrop content"
                    )
                else:
                    logger.warning(
                        f"[EvaluationProcessor:{proposal_id_str}] Could not fetch airdrop data for airdrop_id: {proposal.airdrop_id}"
                    )
            else:
                logger.debug(
                    f"[EvaluationProcessor:{proposal_id_str}] No linked airdrop found for proposal"
                )
        except Exception as e:
            logger.error(
                f"[EvaluationProcessor:{proposal_id_str}] Error fetching linked airdrop content: {str(e)}"
            )

    # Ensure proposal content is safely handled as plain text
    if proposal_content:
        proposal_content = str(proposal_content)
        proposal_content = "".join(
            char for char in proposal_content if ord(char) >= 32 or char in "\n\r\t"
        )
        proposal_content = proposal_content.replace("{", "{{").replace("}", "}}")

    # Get DAO mission from database using dao_id
    dao_mission_text = "Elevate human potential through AI on Bitcoin"  # Default
    if dao_id:
        try:
            logger.debug(
                f"[EvaluationProcessor:{proposal_id_str}] Retrieving DAO mission from database for dao_id: {dao_id}"
            )
            dao = backend.get_dao(dao_id)
            if dao and dao.mission:
                dao_mission_text = dao.mission
                logger.debug(
                    f"[EvaluationProcessor:{proposal_id_str}] Retrieved DAO mission: {dao_mission_text[:100]}..."
                )
            else:
                logger.warning(
                    f"[EvaluationProcessor:{proposal_id_str}] No DAO found or no mission field for dao_id: {dao_id}"
                )
        except Exception as e:
            logger.error(
                f"[EvaluationProcessor:{proposal_id_str}] Error retrieving DAO from database: {str(e)}"
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
            f"[EvaluationProcessor:{proposal_id_str}] Error fetching/formatting DAO proposals: {str(e)}"
        )
        past_proposals_db_text = (
            "<no_proposals>No past proposals available due to error.</no_proposals>"
        )

    # Retrieve similar past proposals from vector store if possible
    past_proposals_vector_text = ""
    try:
        logger.debug(
            f"[EvaluationProcessor:{proposal_id_str}] Retrieving similar past proposals from vector store"
        )
        similar_proposals = await retrieve_from_vector_store(
            query=proposal_content[:1000],  # Use first 1000 chars of proposal as query
            collection_name="past_proposals",
            limit=3,
        )
        past_proposals_vector_text = "\n\n".join(
            [
                f'<similar_proposal id="{i + 1}">\n{doc.page_content}\n</similar_proposal>'
                for i, doc in enumerate(similar_proposals)
            ]
        )
    except Exception as e:
        logger.error(
            f"[EvaluationProcessor:{proposal_id_str}] Error retrieving similar proposals from vector store: {str(e)}"
        )
        past_proposals_vector_text = "<no_similar_proposals>No similar past proposals available in vector store.</no_similar_proposals>"

    # Combine both sources of past proposals
    past_proposals_text = past_proposals_db_text
    if past_proposals_vector_text:
        past_proposals_text += (
            "\n\n" + past_proposals_vector_text
            if past_proposals_text
            else past_proposals_vector_text
        )

    try:
        # Combine all images (proposal images + linked tweet images)
        all_proposal_images = (images or []) + linked_tweet_images

        # Create chat messages
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

        # Create chat prompt template
        prompt = ChatPromptTemplate.from_messages(messages)

        # Get structured output from the LLM
        try:
            result = await invoke_structured(
                messages=prompt,
                output_schema=ComprehensiveEvaluationOutput,
                callbacks=callbacks,
            )
        except Exception as e:
            # If we get a streaming/parsing error, try to handle it
            error_msg = str(e)
            if (
                "Expected list delta entry to have an `index` key" in error_msg
                or "reasoning.text" in error_msg
            ):
                logger.warning(
                    f"[EvaluationProcessor:{proposal_id_str}] Grok reasoning token error, retrying with basic invocation: {error_msg}"
                )
                # This would require a fallback implementation
                raise e
            else:
                # Re-raise non-Grok related errors
                raise e

        logger.info(
            f"[EvaluationProcessor:{proposal_id_str}] Successfully completed comprehensive evaluation"
        )
        logger.info(
            f"[EvaluationProcessor:{proposal_id_str}] Decision: {'Approve' if result.decision else 'Reject'}, Final Score: {result.final_score}"
        )

        # Return the typed model
        return ComprehensiveEvaluatorAgentProcessOutput(
            categories=result.categories,
            final_score=result.final_score,
            decision=result.decision,
            explanation=result.explanation,
            flags=result.flags,
            summary=result.summary,
            token_usage={},  # Token usage tracking would need to be implemented
            images_processed=len(all_proposal_images),
        )
    except Exception as e:
        logger.error(
            f"[EvaluationProcessor:{proposal_id_str}] Error in comprehensive evaluation: {str(e)}"
        )
        # Calculate total images processed (including any linked tweet images that were fetched)
        total_images = len(images) if images else 0
        try:
            total_images += len(linked_tweet_images)
        except NameError:
            # linked_tweet_images might not be defined if error occurred early
            pass

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
