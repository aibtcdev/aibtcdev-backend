from typing import Any, Dict, List, Optional

from langchain.prompts import PromptTemplate
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

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

        # Initialize token usage tracking in state if not present
        if "token_usage" not in state:
            state["token_usage"] = {}

        # Retrieve similar past proposals if possible
        past_proposals_text = ""
        try:
            self.logger.debug(
                f"[DEBUG:HistoricalAgent:{proposal_id}] Retrieving similar past proposals"
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
            past_proposals_text = "\n\n".join(
                [
                    f"Past Proposal {i+1}:\n{doc.page_content}"
                    for i, doc in enumerate(similar_proposals)
                ]
            )
        except Exception as e:
            self.logger.error(
                f"[DEBUG:HistoricalAgent:{proposal_id}] Error retrieving similar proposals: {str(e)}"
            )
            past_proposals_text = "No similar past proposals available."

        prompt = PromptTemplate(
            input_variables=["proposal_data", "past_proposals"],
            template="""Evaluate this proposal in the context of the DAO's past decisions and similar proposals.

# Current Proposal
{proposal_data}

# Similar Past Proposals
{past_proposals}

# Task
Evaluate whether this proposal:
1. Is a duplicate of past proposals (40%)
2. Has addressed issues raised in similar past proposals (30%)
3. Shows consistency with past approved proposals (30%)

Score this proposal from 0-100 based on the criteria above.
- 0-20: Exact duplicate or contradicts previous decisions
- 21-50: Significant overlap without addressing past concerns
- 51-70: Similar to past proposals but with improvements
- 71-90: Builds well on past work with few concerns
- 91-100: Unique proposal or excellent improvement on past proposals

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
                past_proposals=past_proposals_text
                or "No past proposals available for comparison.",
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
            }
