from typing import Any, Dict, List, Optional

from langchain_core.prompts.chat import ChatPromptTemplate

from app.lib.logger import configure_logger
from app.services.ai.workflows.mixins.capability_mixins import (
    BaseCapabilityMixin,
    PromptCapability,
)
from app.services.ai.workflows.utils.models import AgentOutput
from app.services.ai.workflows.utils.state_reducers import (
    update_state_with_agent_result,
)
from app.services.ai.workflows.utils.token_usage import TokenUsageMixin

logger = configure_logger(__name__)


class FinancialContextAgent(BaseCapabilityMixin, TokenUsageMixin, PromptCapability):
    """Financial Context Agent evaluates financial aspects of proposals."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Financial Context Agent.

        Args:
            config: Optional configuration dictionary
        """
        BaseCapabilityMixin.__init__(self, config=config, state_key="financial_score")
        TokenUsageMixin.__init__(self)
        PromptCapability.__init__(self)
        self.initialize()

    def _create_chat_messages(
        self,
        proposal_content: str,
        proposal_images: List[Dict[str, Any]] = None,
    ) -> List:
        """Create chat messages for financial context evaluation.

        Args:
            proposal_content: The proposal content to evaluate
            proposal_images: List of processed images

        Returns:
            List of chat messages
        """
        # System message with financial evaluation guidelines
        system_content = """You are an expert financial analyst specializing in DAO treasury management and proposal evaluation. Your role is to assess the financial aspects of proposals to ensure responsible resource allocation.

You must plan extensively before each evaluation and reflect thoroughly on the financial implications. Consider both immediate costs and long-term financial sustainability.

**Image Evaluation**: If images are attached to this proposal, they are an integral part of the proposal content. You must carefully examine and evaluate any provided images, considering how they support, clarify, or relate to the written proposal. Images may contain budget breakdowns, financial charts, cost projections, timeline diagrams, or other visual information that is essential to understanding the financial aspects and merit of the proposal. Include your analysis of the visual content in your overall financial evaluation.

**Default Financial Context**: 
- If this proposal passes, it will automatically distribute 1000 tokens from the treasury to the proposer
- Beyond this default payout, evaluate any additional financial requests, promises, or money/crypto-related aspects mentioned in the proposal

Evaluation Criteria (weighted):
- Cost-effectiveness and value for money (40% weight)
- Reasonableness of any additional funding requests (25% weight)
- Financial feasibility of promises or commitments (20% weight)
- Overall financial risk assessment (15% weight)

Key Considerations:
- Are any additional funding requests beyond the 1000 tokens reasonable and well-justified?
- Are there any promises or commitments in the proposal that involve money, crypto, or treasury resources?
- What are the financial risks or implications of the proposal?
- Are costs (if any) clearly itemized and realistic?
- Does the proposal represent good value for the default 1000 token investment?
- Are there any hidden financial commitments or ongoing costs?

Scoring Guide:
- 0-20: Very poor financial value, unreasonable requests, or high financial risk
- 21-50: Significant financial concerns, unclear costs, or questionable value
- 51-70: Adequate financial merit with some minor concerns
- 71-90: Good financial value, reasonable requests, clear justification
- 91-100: Excellent financial merit, outstanding value, no financial concerns

Output Format:
Provide a JSON object with exactly these fields:
- score: A number from 0-100
- flags: Array of any critical financial issues or red flags
- summary: Brief summary of your financial evaluation"""

        # User message with evaluation request
        user_content = f"""Please evaluate the financial aspects of the following proposal:

**Important Context**: This proposal, if passed, will automatically receive 1000 tokens from the treasury. Your evaluation should focus on:
1. Whether the proposal provides good value for these 1000 tokens
2. Any additional funding requests beyond the 1000 tokens
3. Any financial commitments, promises, or money/crypto-related aspects mentioned in the proposal
4. Overall financial risk and feasibility

Proposal to Evaluate:
{proposal_content}

Based on the evaluation criteria, provide your assessment of the proposal's financial merit, focusing on the value provided for the 1000 token investment and any additional financial aspects."""

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
        """Process the proposal's financial aspects.

        Args:
            state: The current workflow state

        Returns:
            Dictionary containing financial evaluation results
        """
        proposal_id = state.get("proposal_id", "unknown")
        proposal_content = state.get("proposal_content", "")
        state.get("dao_id")
        state.get("agent_id")
        state.get("profile_id")

        # Initialize token usage tracking in state if not present
        if "token_usage" not in state:
            state["token_usage"] = {}

        # Get proposal images
        proposal_images = state.get("proposal_images", [])

        try:
            # Create chat messages
            messages = self._create_chat_messages(
                proposal_content=proposal_content,
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
            state["token_usage"]["financial_agent"] = token_usage_data
            result_dict["token_usage"] = token_usage_data
            result_dict["images_processed"] = len(proposal_images)

            # Update state with agent result
            update_state_with_agent_result(state, result_dict, "financial")
            return result_dict
        except Exception as e:
            self.logger.error(
                f"[DEBUG:FinancialAgent:{proposal_id}] Error in financial evaluation: {str(e)}"
            )
            return {
                "score": 50,
                "flags": [f"Error: {str(e)}"],
                "summary": "Financial evaluation failed due to error",
                "images_processed": len(proposal_images) if proposal_images else 0,
            }
