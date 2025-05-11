from typing import Any, Dict, Optional

from langchain.prompts import PromptTemplate
from langchain_core.messages import HumanMessage

from lib.logger import configure_logger
from services.workflows.capability_mixins import BaseCapabilityMixin
from services.workflows.utils.models import AgentOutput
from services.workflows.utils.state_reducers import update_state_with_agent_result
from services.workflows.utils.token_usage import TokenUsageMixin
from services.workflows.vector_mixin import VectorRetrievalCapability

logger = configure_logger(__name__)


class CoreContextAgent(BaseCapabilityMixin, VectorRetrievalCapability, TokenUsageMixin):
    """Core Context Agent evaluates proposals against DAO mission and standards."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Core Context Agent.

        Args:
            config: Optional configuration dictionary
        """
        BaseCapabilityMixin.__init__(self, config=config, state_key="core_score")
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
                "Initialized vector retrieval capability for CoreContextAgent"
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

        # Initialize token usage tracking in state if not present
        if "token_usage" not in state:
            state["token_usage"] = {}

        # Retrieve or use provided DAO mission text
        dao_mission_text = self.config.get("dao_mission", "")
        if not dao_mission_text:
            try:
                self.logger.debug(
                    f"[DEBUG:CoreAgent:{proposal_id}] Attempting to retrieve DAO mission"
                )
                dao_mission = await self.retrieve_from_vector_store(
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

        prompt = PromptTemplate(
            input_variables=["proposal_data", "dao_mission"],
            template="""Evaluate the proposal against the DAO's mission and values.

# Context
You are evaluating a proposal for a DAO that focuses on: {dao_mission}

# Proposal Data
{proposal_data}

# Task
Score this proposal from 0-100 based on:
1. Alignment with DAO mission (40%)
2. Clarity of proposal (20%)
3. Feasibility and practicality (20%)
4. Community benefit (20%)

# Output Format
Provide:
- Score (0-100)
- List of any critical issues or red flags
- Brief summary of your evaluation

Only return a JSON object with these three fields: score, flags (array), and summary.""",
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
