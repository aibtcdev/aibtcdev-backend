from typing import Any, Dict, List, Optional

from langchain.prompts import PromptTemplate
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from lib.logger import configure_logger
from services.workflows.capability_mixins import BaseCapabilityMixin
from services.workflows.utils.models import AgentOutput
from services.workflows.utils.state_reducers import update_state_with_agent_result
from services.workflows.utils.token_usage import TokenUsageMixin

logger = configure_logger(__name__)


class FinancialContextAgent(BaseCapabilityMixin, TokenUsageMixin):
    """Financial Context Agent evaluates financial aspects of proposals."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Financial Context Agent.

        Args:
            config: Optional configuration dictionary
        """
        BaseCapabilityMixin.__init__(self, config=config, state_key="financial_score")
        TokenUsageMixin.__init__(self)
        self.initialize()

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process the proposal's financial aspects.

        Args:
            state: The current workflow state

        Returns:
            Dictionary containing financial evaluation results
        """
        proposal_id = state.get("proposal_id", "unknown")
        proposal_content = state.get("proposal_data", "")

        # Initialize token usage tracking in state if not present
        if "token_usage" not in state:
            state["token_usage"] = {}

        # Get DAO financial context from config if available
        dao_financial_context = self.config.get("dao_financial_context", {})
        treasury_balance = dao_financial_context.get("treasury_balance", "unknown")
        monthly_budget = dao_financial_context.get("monthly_budget", "unknown")
        funding_priorities = dao_financial_context.get("funding_priorities", [])
        financial_constraints = dao_financial_context.get("financial_constraints", [])

        # Format financial context for the prompt
        financial_context_text = f"""
Treasury Balance: {treasury_balance}
Monthly Budget: {monthly_budget}
Funding Priorities: {', '.join(funding_priorities) if funding_priorities else 'Not specified'}
Financial Constraints: {', '.join(financial_constraints) if financial_constraints else 'Not specified'}
"""

        prompt = PromptTemplate(
            input_variables=["proposal_data", "financial_context"],
            template="""Evaluate the financial aspects of this proposal for the DAO.

# Proposal
{proposal_data}

# DAO Financial Context
{financial_context}

# Task
Score this proposal from 0-100 based on:
1. Cost-effectiveness and value for money (40%)
2. Budget accuracy and detail (20%)
3. Financial risk assessment (20%)
4. Alignment with DAO's financial priorities (20%)

When analyzing, consider:
- Is the proposal requesting a reasonable amount?
- Are costs well-justified with clear deliverables?
- Are there hidden or underestimated costs?
- Does it align with the DAO's financial priorities?
- What is the potential ROI (Return on Investment)?
- Are there financial risks or dependencies?

# Output Format
Provide:
- Score (0-100)
- List of any critical financial issues or red flags
- Brief summary of your financial evaluation

Only return a JSON object with these three fields: score, flags (array), and summary.""",
        )

        try:
            formatted_prompt_text = prompt.format(
                proposal_data=proposal_content,
                financial_context=financial_context_text,
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
            state["token_usage"]["financial_agent"] = token_usage_data
            result_dict["token_usage"] = token_usage_data

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
            }
