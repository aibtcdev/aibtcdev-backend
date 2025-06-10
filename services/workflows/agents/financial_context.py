from typing import Any, Dict, List, Optional

from langchain_core.prompts.chat import ChatPromptTemplate

from lib.logger import configure_logger
from services.workflows.capability_mixins import BaseCapabilityMixin, PromptCapability
from services.workflows.utils.models import AgentOutput
from services.workflows.utils.state_reducers import update_state_with_agent_result
from services.workflows.utils.token_usage import TokenUsageMixin

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
        proposal_data: str,
        treasury_balance: str,
        monthly_budget: str,
        funding_priorities: str,
        financial_constraints: str,
        proposal_images: List[Dict[str, Any]] = None,
    ) -> List:
        """Create chat messages for financial context evaluation.

        Args:
            proposal_data: The proposal content to evaluate
            treasury_balance: Current treasury balance
            monthly_budget: Monthly budget information
            funding_priorities: DAO funding priorities
            financial_constraints: Financial constraints to consider
            proposal_images: List of processed images

        Returns:
            List of chat messages
        """
        # System message with financial evaluation guidelines
        system_content = """You are an expert financial analyst specializing in DAO treasury management and proposal evaluation. Your role is to assess the financial aspects of proposals to ensure responsible resource allocation.

You must plan extensively before each evaluation and reflect thoroughly on the financial implications. Consider both immediate costs and long-term financial sustainability.

**Image Evaluation**: If images are attached to this proposal, they are an integral part of the proposal content. You must carefully examine and evaluate any provided images, considering how they support, clarify, or relate to the written proposal. Images may contain budget breakdowns, financial charts, cost projections, timeline diagrams, or other visual information that is essential to understanding the financial aspects and merit of the proposal. Include your analysis of the visual content in your overall financial evaluation.

Evaluation Criteria (weighted):
- Cost-effectiveness and value for money (40% weight)
- Budget accuracy and detail (20% weight)
- Financial risk assessment (20% weight)
- Alignment with DAO's financial priorities (20% weight)

Key Considerations:
- Is the proposal requesting a reasonable amount?
- Are costs well-justified with clear deliverables?
- Are there hidden or underestimated costs?
- Does it align with the DAO's financial priorities?
- What is the potential ROI (Return on Investment)?
- Are there financial risks or dependencies?

Scoring Guide:
- 0-20: Very poor financial justification, high risk, or not aligned with priorities
- 21-50: Significant issues or missing details, questionable value
- 51-70: Adequate but with some concerns or minor risks
- 71-90: Good value, well-justified, low risk, fits priorities
- 91-100: Excellent value, clear ROI, no concerns, highly aligned

Output Format:
Provide a JSON object with exactly these fields:
- score: A number from 0-100
- flags: Array of any critical financial issues or red flags
- summary: Brief summary of your financial evaluation"""

        # User message with specific financial context and evaluation request
        user_content = f"""Please evaluate the financial aspects of the following proposal:

Proposal to Evaluate:
{proposal_data}

DAO Financial Context:
- Treasury Balance: {treasury_balance}
- Monthly Budget: {monthly_budget}
- Funding Priorities: {funding_priorities}
- Financial Constraints: {financial_constraints}

Based on the evaluation criteria and the DAO's current financial situation, provide your assessment of the proposal's financial merit, value for money, and alignment with financial priorities."""

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
        proposal_content = state.get("proposal_data", "")
        state.get("dao_id")
        state.get("agent_id")
        state.get("profile_id")

        # Initialize token usage tracking in state if not present
        if "token_usage" not in state:
            state["token_usage"] = {}

        # Get DAO financial context from config if available
        dao_financial_context = self.config.get("dao_financial_context", {})
        treasury_balance = dao_financial_context.get("treasury_balance", "unknown")
        monthly_budget = dao_financial_context.get("monthly_budget", "unknown")
        funding_priorities = dao_financial_context.get("funding_priorities", [])
        financial_constraints = dao_financial_context.get("financial_constraints", [])

        # Get proposal images
        proposal_images = state.get("proposal_images", [])

        try:
            # Create chat messages
            messages = self._create_chat_messages(
                proposal_data=proposal_content,
                treasury_balance=treasury_balance,
                monthly_budget=monthly_budget,
                funding_priorities=(
                    ", ".join(funding_priorities)
                    if funding_priorities
                    else "Not specified"
                ),
                financial_constraints=(
                    ", ".join(financial_constraints)
                    if financial_constraints
                    else "Not specified"
                ),
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
