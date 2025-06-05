from typing import Any, Dict, Optional

from langchain.prompts import PromptTemplate
from langchain_core.messages import HumanMessage

from lib.logger import configure_logger
from services.workflows.capability_mixins import BaseCapabilityMixin
from services.workflows.utils.models import ProposalMetadataOutput
from services.workflows.utils.token_usage import TokenUsageMixin

logger = configure_logger(__name__)


class ProposalMetadataAgent(BaseCapabilityMixin, TokenUsageMixin):
    """Agent that generates title, summary, and metadata tags for proposal content."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Proposal Metadata Agent.

        Args:
            config: Optional configuration dictionary
        """
        BaseCapabilityMixin.__init__(self, config=config, state_key="proposal_metadata")
        TokenUsageMixin.__init__(self)
        self.initialize()

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate title, summary, and metadata tags for the given proposal content.

        Args:
            state: The current workflow state containing proposal_content

        Returns:
            Dictionary containing the generated title, summary, tags, and metadata
        """
        proposal_content = state.get("proposal_content")
        if not proposal_content:
            self.logger.error("No proposal_content provided in state")
            return {
                "error": "proposal_content is required",
                "title": "",
                "summary": "",
                "tags": [],
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
    You are an expert at analyzing DAO proposals and generating comprehensive metadata including titles, summaries, and tags. Create content that accurately represents and categorizes the proposal to help with organization and discoverability.
  </reminder>
</system>

<proposal_metadata_task>
  <input_content>
    <proposal_content>{proposal_content}</proposal_content>
    <dao_name>{dao_name}</dao_name>
    <proposal_type>{proposal_type}</proposal_type>
  </input_content>
  
  <task>
    Based on the provided proposal content, generate:
    
    1. A clear, compelling title that captures the main purpose of the proposal
    2. A concise summary (2-3 sentences) that explains what the proposal is about and its key objectives
    3. 3-5 relevant tags that categorize and describe the proposal
    
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
      
      <tag_guidelines>
        <guideline>Generate exactly 3-5 tags (no more, no less)</guideline>
        <guideline>Each tag should be 1-3 words maximum</guideline>
        <guideline>Use lowercase for consistency</guideline>
        <guideline>Focus on the main themes, topics, and purpose of the proposal</guideline>
        <guideline>Include category-based tags (e.g., "governance", "treasury", "technical")</guideline>
        <guideline>Include action-based tags (e.g., "funding", "upgrade", "partnership")</guideline>
        <guideline>Avoid overly generic tags like "proposal" or "dao"</guideline>
        <guideline>Be specific but not too narrow - tags should be useful for filtering</guideline>
        <guideline>Consider the scope and impact of the proposal</guideline>
      </tag_guidelines>
      
      <common_categories>
        <category>governance - for proposals about DAO structure, voting, rules</category>
        <category>treasury - for proposals about financial management, budgets</category>
        <category>technical - for proposals about code, infrastructure, upgrades</category>
        <category>partnerships - for proposals about collaborations, integrations</category>
        <category>community - for proposals about community building, outreach</category>
        <category>security - for proposals about safety, audits, risk management</category>
        <category>tokenomics - for proposals about token mechanics, rewards</category>
        <category>development - for proposals about product development, features</category>
        <category>marketing - for proposals about promotion, brand, awareness</category>
        <category>operations - for proposals about day-to-day functioning</category>
      </common_categories>
    </guidelines>
  </task>
  
  <output_format>
    Provide a JSON object with:
    <title>Generated proposal title (max 100 characters)</title>
    <summary>Brief summary explaining the proposal (2-3 sentences, max 500 characters)</summary>
    <tags>Array of 3-5 relevant tags as strings</tags>
  </output_format>
</proposal_metadata_task>""",
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
                ProposalMetadataOutput
            ).ainvoke([llm_input_message])
            result_dict = result.model_dump()

            # Track token usage
            token_usage_data = self.track_token_usage(formatted_prompt_text, result)
            state["token_usage"]["proposal_metadata_agent"] = token_usage_data
            result_dict["token_usage"] = token_usage_data

            # Add metadata
            result_dict["content_length"] = len(proposal_content)
            result_dict["dao_name"] = dao_name
            result_dict["proposal_type"] = proposal_type
            result_dict["tags_count"] = len(result_dict.get("tags", []))

            self.logger.info(
                f"Generated title, summary, and {len(result_dict.get('tags', []))} tags for proposal: {result_dict.get('title', 'Unknown')}"
            )
            return result_dict

        except Exception as e:
            self.logger.error(f"Error generating proposal metadata: {str(e)}")
            return {
                "error": str(e),
                "title": "",
                "summary": f"Error generating summary: {str(e)}",
                "tags": [],
                "content_length": len(proposal_content) if proposal_content else 0,
                "dao_name": dao_name,
                "proposal_type": proposal_type,
                "tags_count": 0,
            }
