from typing import Any, Dict, List, Optional
from uuid import UUID

from langchain_core.messages import HumanMessage
from langchain_core.prompts.chat import ChatPromptTemplate

from backend.factory import backend
from backend.models import Proposal, ProposalFilter
from lib.logger import configure_logger
from services.workflows.capability_mixins import BaseCapabilityMixin, PromptCapability
from services.workflows.utils.models import AgentOutput
from services.workflows.utils.state_reducers import update_state_with_agent_result
from services.workflows.utils.token_usage import TokenUsageMixin
from services.workflows.vector_mixin import VectorRetrievalCapability

logger = configure_logger(__name__)


class HistoricalContextAgent(
    BaseCapabilityMixin, VectorRetrievalCapability, TokenUsageMixin, PromptCapability
):
    """Historical Context Agent evaluates proposals against DAO historical context and past decisions."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Historical Context Agent.

        Args:
            config: Optional configuration dictionary
        """
        BaseCapabilityMixin.__init__(self, config=config, state_key="historical_score")
        VectorRetrievalCapability.__init__(self)
        TokenUsageMixin.__init__(self)
        PromptCapability.__init__(self)
        self.initialize()
        self._initialize_vector_capability()

    def _initialize_vector_capability(self):
        """Initialize the vector retrieval capability if not already initialized."""
        if not hasattr(self, "retrieve_from_vector_store"):
            self.retrieve_from_vector_store = (
                VectorRetrievalCapability.retrieve_from_vector_store.__get__(
                    self, self.__class__
                )
            )
            self.logger.info(
                "Initialized vector retrieval capability for HistoricalContextAgent"
            )

    async def _fetch_dao_proposals(self, dao_id: UUID) -> List[Proposal]:
        """Fetch all proposals for a specific DAO from Supabase.

        Args:
            dao_id: The UUID of the DAO

        Returns:
            List of Proposal objects
        """
        try:
            # Create filter to get all proposals for this DAO
            filters = ProposalFilter(dao_id=dao_id)

            # Fetch proposals
            proposals = backend.list_proposals(filters)
            self.logger.debug(f"Retrieved {len(proposals)} proposals for DAO {dao_id}")
            return proposals
        except Exception as e:
            self.logger.error(f"Error fetching proposals for DAO {dao_id}: {str(e)}")
            return []

    def _format_proposals_for_context(self, proposals: List[Proposal]) -> str:
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
            # Use safe sorting with error handling
            sorted_proposals = []
            for proposal in proposals:
                try:
                    created_at = getattr(proposal, "created_at", None)
                    if created_at:
                        sorted_proposals.append((proposal, created_at))
                    else:
                        sorted_proposals.append((proposal, None))
                except Exception as e:
                    self.logger.warning(
                        f"Error accessing created_at for proposal: {str(e)}"
                    )
                    sorted_proposals.append((proposal, None))

            # Sort by created_at, handling None values
            sorted_proposals.sort(
                key=lambda x: x[1] if x[1] is not None else 0, reverse=True
            )
        except Exception as e:
            self.logger.error(f"Error sorting proposals: {str(e)}")
            sorted_proposals = [(proposal, None) for proposal in proposals]

        # Format individual proposals with all relevant details
        formatted_proposals = []
        for i, (proposal, _) in enumerate(
            sorted_proposals[:8]
        ):  # Limit to first 8 for context
            try:
                # Safely get proposal attributes with proper error handling
                title = getattr(proposal, "title", None) or "Untitled"
                content = getattr(proposal, "content", None) or "No content"
                status = getattr(proposal, "status", None) or "Unknown"
                proposal_type = getattr(proposal, "type", None) or "Unknown"
                passed = getattr(proposal, "passed", None)
                action = getattr(proposal, "action", None) or "None"

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

                proposal_text = (
                    f'<proposal id="{i + 1}">\n'
                    f"  <title>{str(title)[:100]}</title>\n"
                    f"  <content>{content_str}</content>\n"
                    f"  <status>{str(status)}</status>\n"
                    f"  <type>{str(proposal_type)}</type>\n"
                    f"  <created_at>{created_str}</created_at>\n"
                    f"  <passed>{str(passed) if passed is not None else 'False'}</passed>\n"
                    f"  <action>{str(action)}</action>\n"
                    f"</proposal>"
                )

                formatted_proposals.append(proposal_text)
            except Exception as e:
                self.logger.error(f"Error formatting proposal {i}: {str(e)}")
                # Add a fallback proposal entry
                formatted_proposals.append(
                    f'<proposal id="{i + 1}">\n'
                    f"  <title>Error loading proposal</title>\n"
                    f"  <content>Could not load proposal data: {str(e)}</content>\n"
                    f"  <status>Unknown</status>\n"
                    f"  <type>Unknown</type>\n"
                    f"  <created_at>Unknown</created_at>\n"
                    f"  <passed>Unknown</passed>\n"
                    f"  <action>None</action>\n"
                    f"</proposal>"
                )

        return (
            "\n\n".join(formatted_proposals)
            if formatted_proposals
            else "<no_proposals>No past proposals available.</no_proposals>"
        )

    def _create_chat_messages(
        self,
        proposal_data: str,
        past_proposals: str,
        proposal_images: List[Dict[str, Any]] = None,
    ) -> List:
        """Create chat messages for historical context evaluation.

        Args:
            proposal_data: The current proposal content to evaluate
            past_proposals: Formatted past proposals text
            proposal_images: List of processed images

        Returns:
            List of chat messages
        """
        # System message with historical evaluation guidelines
        system_content = """You are an expert DAO governance historian specializing in proposal analysis and pattern recognition. Your role is to evaluate new proposals against historical context to identify duplicates, sequences, and potential gaming attempts.

You must plan extensively before each evaluation and reflect thoroughly on historical patterns. The DAO has a 1000 token payout limit per proposal, and submitters might try to game this by splitting large requests across multiple proposals.

Evaluation Process:
1. First, analyze proposals to identify sequences or relationships:
   - Look for proposals with similar titles, themes, or goals
   - Identify proposals that might be parts of a multi-stage initiative
   - Detect potential attempts to circumvent the 1000 token limit by splitting requests
   - Consider chronological relationships between proposals

2. Then evaluate the current proposal based on:
   - Is it a duplicate of past proposals? (25% weight)
   - Has it addressed issues raised in similar past proposals? (20% weight)
   - Shows consistency with past approved proposals? (25% weight)
   - Is potentially part of a sequence to exceed limits? (30% weight)

Key Red Flags:
- Exact duplicates of previous proposals
- Similar requesters, recipients, or incremental funding for the same project
- Proposals that contradict previous decisions
- Suspicious sequence patterns attempting to game token limits

Scoring Guide:
- 0-20: Exact duplicate, contradicts previous decisions, or appears to be gaming token limits
- 21-50: Significant overlap without addressing past concerns or suspicious sequence pattern
- 51-70: Similar to past proposals but with improvements and reasonable sequence relationship
- 71-90: Builds well on past work with few concerns and transparent relationships
- 91-100: Unique proposal or excellent improvement with clear, legitimate purpose

Output Format:
Provide a JSON object with exactly these fields:
- score: A number from 0-100
- flags: Array of any critical issues or red flags
- summary: Brief summary of your evaluation
- sequence_analysis: Identify any proposal sequences and explain relationships"""

        # User message with specific historical context and evaluation request
        user_content = f"""Please evaluate the following proposal against the DAO's historical context and past proposals:

Current Proposal to Evaluate:
{proposal_data}

Past DAO Proposals:
{past_proposals}

Analyze this proposal for duplicates, sequences, and potential gaming attempts. Pay special attention to whether this might be part of a sequence of proposals designed to exceed the 1000 token payout limit. Provide your assessment based on the evaluation criteria."""

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

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process the proposal against historical context.

        Args:
            state: The current workflow state

        Returns:
            Dictionary containing evaluation results
        """
        self._initialize_vector_capability()
        proposal_id = state.get("proposal_id", "unknown")
        proposal_content = state.get("proposal_data", "")

        # Ensure proposal content is safely handled as plain text
        if proposal_content:
            # Convert to string and ensure it's treated as plain text
            proposal_content = str(proposal_content)
            # Remove any null bytes or other control characters that might cause parsing issues
            proposal_content = "".join(
                char for char in proposal_content if ord(char) >= 32 or char in "\n\r\t"
            )
            # Escape curly braces to prevent f-string/format interpretation issues
            proposal_content = proposal_content.replace("{", "{{").replace("}", "}}")
        dao_id = state.get("dao_id")
        agent_id = state.get("agent_id")
        profile_id = state.get("profile_id")

        # Initialize token usage tracking in state if not present
        if "token_usage" not in state:
            state["token_usage"] = {}

        # Retrieve all proposals for this DAO from Supabase
        dao_proposals = []
        past_proposals_db_text = ""
        try:
            if dao_id:
                dao_proposals = await self._fetch_dao_proposals(dao_id)
                past_proposals_db_text = self._format_proposals_for_context(
                    dao_proposals
                )
        except Exception as e:
            self.logger.error(
                f"[DEBUG:HistoricalAgent:{proposal_id}] Error fetching/formatting DAO proposals: {str(e)}"
            )
            past_proposals_db_text = (
                "<no_proposals>No past proposals available due to error.</no_proposals>"
            )

        # Retrieve similar past proposals from vector store if possible
        past_proposals_vector_text = ""
        try:
            self.logger.debug(
                f"[DEBUG:HistoricalAgent:{proposal_id}] Retrieving similar past proposals from vector store"
            )
            similar_proposals = await self.retrieve_from_vector_store(
                query=proposal_content[
                    :1000
                ],  # Use first 1000 chars of proposal as query
                collection_name=self.config.get(
                    "proposals_collection", "past_proposals"
                ),
                limit=3,
            )
            past_proposals_vector_text = "\n\n".join(
                [
                    f'<similar_proposal id="{i + 1}">\n{doc.page_content}\n</similar_proposal>'
                    for i, doc in enumerate(similar_proposals)
                ]
            )
        except Exception as e:
            self.logger.error(
                f"[DEBUG:HistoricalAgent:{proposal_id}] Error retrieving similar proposals from vector store: {str(e)}"
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

        # Get proposal images
        proposal_images = state.get("proposal_images", [])

        try:
            # Create chat messages
            messages = self._create_chat_messages(
                proposal_data=proposal_content,
                past_proposals=past_proposals_text
                or "<no_proposals>No past proposals available for comparison.</no_proposals>",
                proposal_images=proposal_images,
            )

            # Create chat prompt template
            prompt = ChatPromptTemplate.from_messages(messages)
            formatted_prompt = prompt.format()

            # Get structured output from the LLM
            result = await self.llm.with_structured_output(AgentOutput).ainvoke(
                formatted_prompt
            )
            result_dict = result.model_dump()

            # Track token usage
            token_usage_data = self.track_token_usage(str(formatted_prompt), result)
            state["token_usage"]["historical_agent"] = token_usage_data
            result_dict["token_usage"] = token_usage_data
            result_dict["images_processed"] = len(proposal_images)

            # Update state with agent result
            update_state_with_agent_result(state, result_dict, "historical")
            return result_dict
        except Exception as e:
            self.logger.error(
                f"[DEBUG:HistoricalAgent:{proposal_id}] Error in historical evaluation: {str(e)}"
            )
            return {
                "score": 50,
                "flags": [f"Error: {str(e)}"],
                "summary": "Historical evaluation failed due to error",
                "sequence_analysis": "Could not analyze potential proposal sequences due to error.",
                "images_processed": len(proposal_images) if proposal_images else 0,
            }
