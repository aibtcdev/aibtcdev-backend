from typing import Any, Dict, List, Optional

from langchain_core.prompts.chat import ChatPromptTemplate

from backend.factory import backend
from lib.logger import configure_logger
from services.ai.workflows.mixins.capability_mixins import (
    BaseCapabilityMixin,
    PromptCapability,
)
from services.ai.workflows.mixins.vector_mixin import VectorRetrievalCapability
from services.ai.workflows.utils.models import AgentOutput
from services.ai.workflows.utils.state_reducers import update_state_with_agent_result
from services.ai.workflows.utils.token_usage import TokenUsageMixin

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
        if not hasattr(self, "retrieve_from_vector_store"):
            self.retrieve_from_vector_store = (
                VectorRetrievalCapability.retrieve_from_vector_store.__get__(
                    self, self.__class__
                )
            )
            self.logger.info(
                "Initialized vector retrieval capability for CoreContextAgent"
            )

    def _create_chat_messages(
        self,
        proposal_data: str,
        dao_mission: str,
        proposal_images: List[Dict[str, Any]] = None,
    ) -> List:
        """Create chat messages for core context evaluation.

        Args:
            proposal_data: The proposal content to evaluate
            dao_mission: The DAO mission statement
            proposal_images: List of processed images

        Returns:
            List of chat messages
        """
        # System message with evaluation guidelines
        system_content = """You are an expert DAO governance evaluator specializing in core context analysis. Your role is to evaluate proposals against the DAO's mission and fundamental standards.

You must plan extensively before each evaluation, and reflect thoroughly on the alignment between the proposal and DAO mission. Do not rush through this process - take time to analyze thoroughly.

**Image Evaluation**: If images are attached to this proposal, they are an integral part of the proposal content. You must carefully examine and evaluate any provided images, considering how they support, clarify, or relate to the written proposal. Images may contain diagrams, charts, screenshots, mockups, or other visual information that is essential to understanding the full scope and merit of the proposal. Include your analysis of the visual content in your overall evaluation.

Evaluation Criteria (weighted):
- Alignment with DAO mission (40% weight)
- Clarity of proposal (20% weight) 
- Feasibility and practicality (20% weight)
- Community benefit (20% weight)

Scoring Guide:
- 0-20: Not aligned, unclear, impractical, or no community benefit
- 21-50: Significant issues or missing details
- 51-70: Adequate but with some concerns or minor risks
- 71-90: Good alignment, clear, practical, and beneficial
- 91-100: Excellent alignment, clarity, feasibility, and community value

Output Format:
Provide a JSON object with exactly these fields:
- score: A number from 0-100
- flags: Array of any critical issues or red flags
- summary: Brief summary of your evaluation"""

        # User message with specific evaluation request
        user_content = f"""Please evaluate the following proposal against the DAO's core mission and standards:

DAO Mission:
{dao_mission}

Proposal to Evaluate:
{proposal_data}

Based on the evaluation criteria and scoring guide, provide your assessment of how well this proposal aligns with the DAO's mission and meets the core standards for clarity, feasibility, and community benefit."""

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
        state.get("agent_id")
        state.get("profile_id")

        # Initialize token usage tracking in state if not present
        if "token_usage" not in state:
            state["token_usage"] = {}

        # Get DAO mission from database using dao_id
        dao_mission_text = self.config.get("dao_mission", "")
        if not dao_mission_text and dao_id:
            try:
                self.logger.debug(
                    f"[DEBUG:CoreAgent:{proposal_id}] Attempting to retrieve DAO mission from database for dao_id: {dao_id}"
                )
                dao = backend.get_dao(dao_id)
                if dao and dao.mission:
                    dao_mission_text = dao.mission
                    self.logger.debug(
                        f"[DEBUG:CoreAgent:{proposal_id}] Retrieved DAO mission: {dao_mission_text[:100]}..."
                    )
                else:
                    self.logger.warning(
                        f"[DEBUG:CoreAgent:{proposal_id}] No DAO found or no mission field for dao_id: {dao_id}"
                    )
                    dao_mission_text = "Elevate human potential through AI on Bitcoin"
            except Exception as e:
                self.logger.error(
                    f"[DEBUG:CoreAgent:{proposal_id}] Error retrieving DAO from database: {str(e)}"
                )
                dao_mission_text = "Elevate human potential through AI on Bitcoin"

        # Fallback to default mission if still empty
        if not dao_mission_text:
            dao_mission_text = "Elevate human potential through AI on Bitcoin"

        # Get proposal images
        proposal_images = state.get("proposal_images", [])

        try:
            # Create chat messages
            messages = self._create_chat_messages(
                proposal_data=proposal_content,
                dao_mission=dao_mission_text,
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
            state["token_usage"]["core_agent"] = token_usage_data
            result_dict["token_usage"] = token_usage_data
            result_dict["images_processed"] = len(proposal_images)

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
                "images_processed": len(proposal_images) if proposal_images else 0,
            }
