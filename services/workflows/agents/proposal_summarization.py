from typing import Any, Dict, Optional

from langchain.prompts import PromptTemplate
from langchain_core.messages import HumanMessage

from lib.logger import configure_logger
from services.workflows.capability_mixins import BaseCapabilityMixin
from services.workflows.utils.models import ProposalSummarizationOutput
from services.workflows.utils.token_usage import TokenUsageMixin

logger = configure_logger(__name__)


class ProposalSummarizationAgent(BaseCapabilityMixin, TokenUsageMixin):
    """Agent that generates titles and summaries for proposal content."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Proposal Summarization Agent.

        Args:
            config: Optional configuration dictionary
        """
        BaseCapabilityMixin.__init__(
            self, config=config, state_key="proposal_summarization"
        )
        TokenUsageMixin.__init__(self)
        self.initialize()

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a title and summary for the given proposal content.

        Args:
            state: The current workflow state containing proposal_content

        Returns:
            Dictionary containing the generated title and summary
        """
        proposal_content = state.get("proposal_content")
        if not proposal_content:
            self.logger.error("No proposal_content provided in state")
            return {
                "error": "proposal_content is required",
                "title": "",
                "summary": "",
            }

        # Initialize token usage tracking in state if not present
        if "token_usage" not in state:
            state["token_usage"] = {}

        # Get additional context from state if available
        dao_name = state.get("dao_name", "")
        proposal_type = state.get("proposal_type", "")

        prompt = PromptTemplate(
            input_variables=[
                "proposal_content",
                "dao_name",
                "proposal_type",
            ],
            template="""<system>
  <reminder>
    You are an expert at creating clear, concise titles and summaries for DAO proposals. Generate a compelling title and brief summary that captures the essence of the proposal content.
  </reminder>
</system>

<proposal_summarization_task>
  <input_content>
    <proposal_content>{proposal_content}</proposal_content>
    <dao_name>{dao_name}</dao_name>
    <proposal_type>{proposal_type}</proposal_type>
  </input_content>
  
  <task>
    Based on the provided proposal content, generate:
    
    1. A clear, compelling title that captures the main purpose of the proposal
    2. A concise summary (2-3 sentences) that explains what the proposal is about and its key objectives
    
    <guidelines>
      <title_guidelines>
        <guideline>Keep the title under 100 characters</guideline>
        <guideline>Make it descriptive and action-oriented</guideline>
        <guideline>Avoid jargon or overly technical language</guideline>
        <guideline>Capture the main benefit or outcome</guideline>
        <guideline>Include the DAO name if it adds context and clarity</guideline>
      </title_guidelines>
      
      <summary_guidelines>
        <guideline>Keep the summary under 500 characters (2-3 sentences)</guideline>
        <guideline>Explain what the proposal does and why it matters</guideline>
        <guideline>Include key objectives or outcomes</guideline>
        <guideline>Use clear, accessible language</guideline>
        <guideline>Highlight the main benefit to the DAO community</guideline>
      </summary_guidelines>
    </guidelines>
  </task>
  
  <output_format>
    Provide a JSON object with:
    <title>Generated proposal title (max 100 characters)</title>
    <summary>Brief summary explaining the proposal (2-3 sentences, max 500 characters)</summary>
  </output_format>
</proposal_summarization_task>""",
        )

        try:
            formatted_prompt_text = prompt.format(
                proposal_content=proposal_content,
                dao_name=dao_name or "the DAO",
                proposal_type=proposal_type or "general proposal",
            )

            llm_input_message = HumanMessage(content=formatted_prompt_text)

            # Get structured output from the LLM
            result = await self.llm.with_structured_output(
                ProposalSummarizationOutput
            ).ainvoke([llm_input_message])
            result_dict = result.model_dump()

            # Track token usage
            token_usage_data = self.track_token_usage(formatted_prompt_text, result)
            state["token_usage"]["proposal_summarization_agent"] = token_usage_data
            result_dict["token_usage"] = token_usage_data

            # Add metadata
            result_dict["content_length"] = len(proposal_content)
            result_dict["dao_name"] = dao_name
            result_dict["proposal_type"] = proposal_type

            self.logger.info(
                f"Generated title and summary for proposal: {result_dict.get('title', 'Unknown')}"
            )
            return result_dict

        except Exception as e:
            self.logger.error(f"Error generating proposal title and summary: {str(e)}")
            return {
                "error": str(e),
                "title": "",
                "summary": f"Error generating summary: {str(e)}",
                "content_length": len(proposal_content) if proposal_content else 0,
                "dao_name": dao_name,
                "proposal_type": proposal_type,
            }
