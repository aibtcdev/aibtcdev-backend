from typing import Any, Dict, List, Optional

from langchain_core.prompts.chat import ChatPromptTemplate

from lib.logger import configure_logger
from services.workflows.capability_mixins import BaseCapabilityMixin, PromptCapability
from services.workflows.utils.models import AgentOutput
from services.workflows.utils.state_reducers import update_state_with_agent_result
from services.workflows.utils.token_usage import TokenUsageMixin

logger = configure_logger(__name__)


class SocialContextAgent(BaseCapabilityMixin, TokenUsageMixin, PromptCapability):
    """Social Context Agent evaluates social and community aspects of proposals."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Social Context Agent.

        Args:
            config: Optional configuration dictionary
        """
        BaseCapabilityMixin.__init__(self, config=config, state_key="social_score")
        TokenUsageMixin.__init__(self)
        PromptCapability.__init__(self)
        self.initialize()

    def _create_chat_messages(
        self,
        proposal_data: str,
        community_info: str,
        search_results: str,
        proposal_images: List[Dict[str, Any]] = None,
    ) -> List:
        """Create chat messages for social context evaluation.

        Args:
            proposal_data: The proposal content to evaluate
            community_info: Information about the DAO community
            search_results: External context from web search
            proposal_images: List of processed images

        Returns:
            List of chat messages
        """
        # System message with social evaluation guidelines
        system_content = """You are an expert community analyst specializing in DAO governance and social dynamics. Your role is to evaluate proposals from a community perspective, ensuring they serve the broader membership and align with community values.

You must plan extensively before each evaluation and reflect thoroughly on the social implications. Consider both immediate community impact and long-term social dynamics.

Evaluation Criteria (weighted):
- Community benefit and inclusion (40% weight)
- Alignment with community values and interests (30% weight)
- Potential for community engagement (20% weight)
- Consideration of diverse stakeholders (10% weight)

Key Considerations:
- Will this proposal benefit the broader community or just a few members?
- Is there likely community support or opposition?
- Does it foster inclusivity and participation?
- Does it align with the community's values and interests?
- Could it cause controversy or division?
- Does it consider the needs of diverse stakeholders?

Scoring Guide:
- 0-20: No benefit, misaligned, or divisive
- 21-50: Significant issues or missing details
- 51-70: Adequate but with some concerns or minor risks
- 71-90: Good benefit, aligned, and inclusive
- 91-100: Excellent benefit, highly aligned, and unifying

Output Format:
Provide a JSON object with exactly these fields:
- score: A number from 0-100
- flags: Array of any critical social issues or red flags
- summary: Brief summary of your social evaluation"""

        # User message with specific social context and evaluation request
        user_content = f"""Please evaluate the social and community aspects of the following proposal:

Proposal to Evaluate:
{proposal_data}

Community Information:
{community_info}

External Context:
{search_results}

Based on the evaluation criteria and community context, provide your assessment of how this proposal will impact the community, whether it aligns with community values, and its potential for fostering engagement and inclusion."""

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
        """Process the proposal's social context.

        Args:
            state: The current workflow state

        Returns:
            Dictionary containing social evaluation results
        """
        proposal_id = state.get("proposal_id", "unknown")
        proposal_content = state.get("proposal_data", "")
        state.get("dao_id")
        state.get("agent_id")
        state.get("profile_id")

        # Initialize token usage tracking in state if not present
        if "token_usage" not in state:
            state["token_usage"] = {}

        # Web search is disabled for social context evaluation
        search_results_text = "Web search is disabled for social context evaluation.\n"

        # Get community info from config
        community_context = self.config.get("community_context", {})
        community_size = community_context.get("community_size", "Unknown")
        active_members = community_context.get("active_members", "Unknown")
        governance_participation = community_context.get(
            "governance_participation", "Low"
        )
        recent_sentiment = community_context.get("recent_sentiment", "Neutral")

        community_info = f"""
Community Size: {community_size}
Active Members: {active_members}
Governance Participation: {governance_participation}
Recent Community Sentiment: {recent_sentiment}
"""

        # Get proposal images
        proposal_images = state.get("proposal_images", [])

        try:
            # Create chat messages
            messages = self._create_chat_messages(
                proposal_data=proposal_content,
                community_info=community_info,
                search_results=search_results_text,
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
            state["token_usage"]["social_agent"] = token_usage_data
            result_dict["token_usage"] = token_usage_data
            result_dict["images_processed"] = len(proposal_images)

            # Update state with agent result
            update_state_with_agent_result(state, result_dict, "social")
            return result_dict
        except Exception as e:
            self.logger.error(
                f"[DEBUG:SocialAgent:{proposal_id}] Error in social evaluation: {str(e)}"
            )
            return {
                "score": 50,
                "flags": [f"Error: {str(e)}"],
                "summary": "Social evaluation failed due to error",
                "images_processed": len(proposal_images) if proposal_images else 0,
            }
