from typing import Any, Dict, Optional

from langchain_core.messages import HumanMessage

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

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process the proposal's financial aspects.

        Args:
            state: The current workflow state

        Returns:
            Dictionary containing financial evaluation results
        """
        proposal_id = state.get("proposal_id", "unknown")
        proposal_content = state.get("proposal_data", "")
        dao_id = state.get("dao_id")
        agent_id = state.get("agent_id")
        profile_id = state.get("profile_id")

        # Initialize token usage tracking in state if not present
        if "token_usage" not in state:
            state["token_usage"] = {}

        # Get DAO financial context from config if available
        dao_financial_context = self.config.get("dao_financial_context", {})
        treasury_balance = dao_financial_context.get("treasury_balance", "unknown")
        monthly_budget = dao_financial_context.get("monthly_budget", "unknown")
        funding_priorities = dao_financial_context.get("funding_priorities", [])
        financial_constraints = dao_financial_context.get("financial_constraints", [])

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
<financial_context_evaluation>
  <current_proposal>
    {proposal_data}
  </current_proposal>
  <dao_financial_context>
    <treasury_balance>{treasury_balance}</treasury_balance>
    <monthly_budget>{monthly_budget}</monthly_budget>
    <funding_priorities>{funding_priorities}</funding_priorities>
    <financial_constraints>{financial_constraints}</financial_constraints>
  </dao_financial_context>
  <task>
    <criteria>
      <criterion weight=\"40\">Cost-effectiveness and value for money</criterion>
      <criterion weight=\"20\">Budget accuracy and detail</criterion>
      <criterion weight=\"20\">Financial risk assessment</criterion>
      <criterion weight=\"20\">Alignment with DAO's financial priorities</criterion>
    </criteria>
    <considerations>
      <consideration>Is the proposal requesting a reasonable amount?</consideration>
      <consideration>Are costs well-justified with clear deliverables?</consideration>
      <consideration>Are there hidden or underestimated costs?</consideration>
      <consideration>Does it align with the DAO's financial priorities?</consideration>
      <consideration>What is the potential ROI (Return on Investment)?</consideration>
      <consideration>Are there financial risks or dependencies?</consideration>
    </considerations>
    <scoring_guide>
      <score range=\"0-20\">Very poor financial justification, high risk, or not aligned with priorities</score>
      <score range=\"21-50\">Significant issues or missing details, questionable value</score>
      <score range=\"51-70\">Adequate but with some concerns or minor risks</score>
      <score range=\"71-90\">Good value, well-justified, low risk, fits priorities</score>
      <score range=\"91-100\">Excellent value, clear ROI, no concerns, highly aligned</score>
    </scoring_guide>
  </task>
  <output_format>
    Provide:
    <score>A number from 0-100</score>
    <flags>List of any critical financial issues or red flags</flags>
    <summary>Brief summary of your financial evaluation</summary>
    Only return a JSON object with these three fields: score, flags (array), and summary.
  </output_format>
</financial_context_evaluation>"""

        # Create prompt with custom injection
        prompt = self.create_prompt_with_custom_injection(
            default_template=default_template,
            input_variables=[
                "proposal_data",
                "treasury_balance",
                "monthly_budget",
                "funding_priorities",
                "financial_constraints",
            ],
            dao_id=dao_id,
            agent_id=agent_id,
            profile_id=profile_id,
            prompt_type="financial_context_evaluation",
        )

        try:
            formatted_prompt_text = prompt.format(
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
