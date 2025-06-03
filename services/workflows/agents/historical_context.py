from typing import Any, Dict, List, Optional
from uuid import UUID

from langchain.prompts import PromptTemplate
from langchain_core.messages import HumanMessage

from backend.factory import backend
from backend.models import Proposal, ProposalFilter
from lib.logger import configure_logger
from services.workflows.capability_mixins import BaseCapabilityMixin
from services.workflows.utils.models import AgentOutput
from services.workflows.utils.state_reducers import update_state_with_agent_result
from services.workflows.utils.token_usage import TokenUsageMixin
from services.workflows.vector_mixin import VectorRetrievalCapability

logger = configure_logger(__name__)


class HistoricalContextAgent(
    BaseCapabilityMixin, VectorRetrievalCapability, TokenUsageMixin
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
        # Sort proposals by creation date (newest first to prioritize recent history)
        sorted_proposals = sorted(proposals, key=lambda p: p.created_at, reverse=True)

        # Format individual proposals with all relevant details
        past_proposals_text = (
            "\n\n".join(
                [
                    f'<proposal id="{i+1}">\n'
                    f"  <title>{proposal.title or 'Untitled'}</title>\n"
                    f"  <content>{proposal.content or 'No content'}</content>\n"
                    f"  <status>{proposal.status or 'Unknown'}</status>\n"
                    f"  <type>{proposal.type or 'Unknown'}</type>\n"
                    f"  <created_at>{proposal.created_at.strftime('%Y-%m-%d') if proposal.created_at else 'Unknown'}</created_at>\n"
                    f"  <passed>{proposal.passed or False}</passed>\n"
                    f"  <action>{proposal.action or 'None'}</action>\n"
                    f"</proposal>"
                    for i, proposal in enumerate(
                        sorted_proposals[:8]
                    )  # Limit to first 8 for context
                ]
            )
            if proposals
            else "<no_proposals>No past proposals available.</no_proposals>"
        )

        return past_proposals_text

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
        dao_id = state.get("dao_id")

        # Initialize token usage tracking in state if not present
        if "token_usage" not in state:
            state["token_usage"] = {}

        # Retrieve all proposals for this DAO from Supabase
        dao_proposals = []
        if dao_id:
            dao_proposals = await self._fetch_dao_proposals(dao_id)

        # Format database proposals for context
        past_proposals_db_text = ""
        if dao_proposals:
            past_proposals_db_text = self._format_proposals_for_context(dao_proposals)

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
                    f'<similar_proposal id="{i+1}">\n{doc.page_content}\n</similar_proposal>'
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

        prompt = PromptTemplate(
            input_variables=["proposal_data", "past_proposals"],
            template="""<system>
  <reminder>
    You are an agent - please keep going until the user's query is completely resolved, before ending your turn and yielding back to the user. Only terminate your turn when you are sure that the problem is solved.
  </reminder>
  <reminder>
    If you are not sure about file content or codebase structure pertaining to the user's request, use your tools to read files and gather the relevant information: do NOT guess or make up an answer.
  </reminder>
  <reminder>
    You MUST plan extensively before each function call, and reflect extensively on the outcomes of the previous function calls. DO NOT do this entire process by making function calls only, as this can impair your ability to solve the problem and think insightfully.
  </reminder>
</system>
<historical_context_evaluation>
  <current_proposal>
    {proposal_data}
  </current_proposal>
  <past_dao_proposals>
    {past_proposals}
  </past_dao_proposals>
  <task>
    <sequence_analysis>
      First, analyze the proposals to identify any sequences or relationships between them:
      <criteria>
        <criterion>Look for proposals with similar titles, themes, or goals</criterion>
        <criterion>Identify proposals that might be parts of a multi-stage initiative</criterion>
        <criterion>Detect proposals that might be attempting to circumvent the 1000 token payout limit per proposal by splitting a large request into multiple smaller proposals</criterion>
        <criterion>Consider chronological relationships between proposals</criterion>
      </criteria>
    </sequence_analysis>
    <proposal_evaluation>
      Then, evaluate whether this proposal:
      <criteria>
        <criterion weight=\"25\">Is a duplicate of past proposals</criterion>
        <criterion weight=\"20\">Has addressed issues raised in similar past proposals</criterion>
        <criterion weight=\"25\">Shows consistency with past approved proposals</criterion>
        <criterion weight=\"30\">Is potentially part of a sequence of proposals to exceed limits
          <details>
            <detail>The DAO has a 1000 token payout limit per proposal</detail>
            <detail>Submitters might split large requests across multiple proposals to get around this limit</detail>
            <detail>Look for patterns like similar requesters, recipients, or incremental funding for the same project</detail>
          </details>
        </criterion>
      </criteria>
    </proposal_evaluation>
    <scoring_guide>
      Score this proposal from 0-100 based on the criteria above.
      <score range=\"0-20\">Exact duplicate, contradicts previous decisions, or appears to be gaming token limits</score>
      <score range=\"21-50\">Significant overlap without addressing past concerns or suspicious sequence pattern</score>
      <score range=\"51-70\">Similar to past proposals but with improvements and reasonable sequence relationship (if any)</score>
      <score range=\"71-90\">Builds well on past work with few concerns and transparent relationships to other proposals</score>
      <score range=\"91-100\">Unique proposal or excellent improvement on past proposals with clear, legitimate purpose</score>
    </scoring_guide>
  </task>
  <output_format>
    Provide:
    <score>A number from 0-100</score>
    <flags>List of any critical issues or red flags</flags>
    <summary>Brief summary of your evaluation</summary>
    <sequence_analysis>Identify any proposal sequences and explain how this proposal might relate to others</sequence_analysis>
    Only return a JSON object with these four fields: score, flags (array), summary, and sequence_analysis.
  </output_format>
</historical_context_evaluation>""",
        )

        try:
            formatted_prompt_text = prompt.format(
                proposal_data=proposal_content,
                past_proposals=past_proposals_text
                or "<no_proposals>No past proposals available for comparison.</no_proposals>",
            )
            message_content_list = [{"type": "text", "text": formatted_prompt_text}]

            # Add any proposal images to the message
            proposal_images = state.get("proposal_images", [])
            if proposal_images:
                message_content_list.extend(proposal_images)

            llm_input_message = HumanMessage(content=message_content_list)

            # Get structured output from the LLM
            result = await self.llm.with_structured_output(AgentOutput).ainvoke(
                [llm_input_message]
            )
            result_dict = result.model_dump()

            # Track token usage
            token_usage_data = self.track_token_usage(formatted_prompt_text, result)
            state["token_usage"]["historical_agent"] = token_usage_data
            result_dict["token_usage"] = token_usage_data

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
            }
