from typing import Any, Dict, Optional

from langchain.prompts import PromptTemplate
from langchain_core.messages import HumanMessage

from lib.logger import configure_logger
from services.workflows.capability_mixins import BaseCapabilityMixin, PromptCapability
from services.workflows.utils.models import AgentOutput
from services.workflows.utils.state_reducers import update_state_with_agent_result
from services.workflows.utils.token_usage import TokenUsageMixin
from services.workflows.vector_mixin import VectorRetrievalCapability

logger = configure_logger(__name__)


class CoreContextAgent(
    BaseCapabilityMixin, VectorRetrievalCapability, TokenUsageMixin, PromptCapability
):
    """Core Context Agent evaluates proposals against DAO mission and standards."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Core Context Agent.

        Args:
            config: Optional configuration dictionary
        """
        BaseCapabilityMixin.__init__(self, config=config, state_key="core_score")
        VectorRetrievalCapability.__init__(self)
        TokenUsageMixin.__init__(self)
        PromptCapability.__init__(self)
        self.initialize()
        self._initialize_vector_capability()

    def _initialize_vector_capability(self):
        """Initialize the vector retrieval capability if not already initialized."""
        if not hasattr(self, "hybrid_retrieve"):
            self.hybrid_retrieve = VectorRetrievalCapability.hybrid_retrieve.__get__(
                self, self.__class__
            )
            self.logger.info(
                "Initialized hybrid retrieval capability for CoreContextAgent"
            )

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process the proposal against core DAO context.

        Args:
            state: The current workflow state

        Returns:
            Dictionary containing evaluation results
        """
        self._initialize_vector_capability()
        proposal_id = state.get("proposal_id", "unknown")
        proposal_content = state.get("proposal_data", "")
        dao_id = state.get("dao_id")
        agent_id = state.get("agent_id")
        profile_id = state.get("profile_id")

        # Initialize token usage tracking in state if not present
        if "token_usage" not in state:
            state["token_usage"] = {}

        # Retrieve or use provided DAO mission text
        dao_mission_text = self.config.get("dao_mission", "")
        if not dao_mission_text:
            try:
                self.logger.debug(
                    f"[DEBUG:CoreAgent:{proposal_id}] Attempting to retrieve DAO mission using hybrid search"
                )
                dao_mission = await self.hybrid_retrieve(
                    query="DAO mission statement and values",
                    collection_name=self.config.get(
                        "mission_collection", "dao_documents"
                    ),
                    limit=3,
                )
                dao_mission_text = "\n".join([doc.page_content for doc in dao_mission])
            except Exception as e:
                self.logger.error(
                    f"[DEBUG:CoreAgent:{proposal_id}] Error retrieving DAO mission: {str(e)}"
                )
                dao_mission_text = "Elevate human potential through AI on Bitcoin"

        # Default prompt template
        default_template = """<system>
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
<core_context_evaluation>
  <dao_mission>
    {dao_mission}
  </dao_mission>
  <proposal_data>
    {proposal_data}
  </proposal_data>
  <task>
    <criteria>
      <criterion weight=\"40\">Alignment with DAO mission</criterion>
      <criterion weight=\"20\">Clarity of proposal</criterion>
      <criterion weight=\"20\">Feasibility and practicality</criterion>
      <criterion weight=\"20\">Community benefit</criterion>
    </criteria>
    <scoring_guide>
      <score range=\"0-20\">Not aligned, unclear, impractical, or no community benefit</score>
      <score range=\"21-50\">Significant issues or missing details</score>
      <score range=\"51-70\">Adequate but with some concerns or minor risks</score>
      <score range=\"71-90\">Good alignment, clear, practical, and beneficial</score>
      <score range=\"91-100\">Excellent alignment, clarity, feasibility, and community value</score>
    </scoring_guide>
  </task>
  <output_format>
    Provide:
    <score>A number from 0-100</score>
    <flags>List of any critical issues or red flags</flags>
    <summary>Brief summary of your evaluation</summary>
    Only return a JSON object with these three fields: score, flags (array), and summary.
  </output_format>
</core_context_evaluation>"""

        # Create prompt with custom injection
        prompt = self.create_prompt_with_custom_injection(
            default_template=default_template,
            input_variables=["proposal_data", "dao_mission"],
            dao_id=dao_id,
            agent_id=agent_id,
            profile_id=profile_id,
            prompt_type="core_context_evaluation",
        )

        try:
            formatted_prompt_text = prompt.format(
                proposal_data=proposal_content,
                dao_mission=dao_mission_text
                or "Elevate human potential through AI on Bitcoin",
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
            state["token_usage"]["core_agent"] = token_usage_data
            result_dict["token_usage"] = token_usage_data

            # Update state with agent result
            update_state_with_agent_result(state, result_dict, "core")
            return result_dict
        except Exception as e:
            self.logger.error(
                f"[DEBUG:CoreAgent:{proposal_id}] Error in core evaluation: {str(e)}"
            )
            return {
                "score": 50,
                "flags": [f"Error: {str(e)}"],
                "summary": "Evaluation failed due to error",
            }
