from typing import Any, Dict, List, Optional

from langchain.prompts import PromptTemplate
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from lib.logger import configure_logger
from services.workflows.capability_mixins import BaseCapabilityMixin
from services.workflows.utils.models import AgentOutput
from services.workflows.utils.state_reducers import update_state_with_agent_result
from services.workflows.utils.token_usage import TokenUsageMixin
from services.workflows.web_search_mixin import WebSearchCapability

logger = configure_logger(__name__)


class SocialContextAgent(BaseCapabilityMixin, WebSearchCapability, TokenUsageMixin):
    """Social Context Agent evaluates social and community aspects of proposals."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Social Context Agent.

        Args:
            config: Optional configuration dictionary
        """
        BaseCapabilityMixin.__init__(self, config=config, state_key="social_score")
        WebSearchCapability.__init__(self)
        TokenUsageMixin.__init__(self)
        self.initialize()
        self._initialize_web_search_capability()

    def _initialize_web_search_capability(self):
        """Initialize the web search capability if not already initialized."""
        if not hasattr(self, "web_search"):
            self.web_search = WebSearchCapability.web_search.__get__(
                self, self.__class__
            )
            self.logger.info("Initialized web search capability for SocialContextAgent")

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process the proposal's social context.

        Args:
            state: The current workflow state

        Returns:
            Dictionary containing social evaluation results
        """
        self._initialize_web_search_capability()
        proposal_id = state.get("proposal_id", "unknown")
        proposal_content = state.get("proposal_data", "")

        # Initialize token usage tracking in state if not present
        if "token_usage" not in state:
            state["token_usage"] = {}

        # Extract key concepts for web search
        search_results = []
        try:
            # First try to identify key search terms
            key_concepts_prompt = PromptTemplate(
                input_variables=["proposal"],
                template="""Extract 2-3 key topics from this proposal that would benefit from external information:

{proposal}

Return only the key topics as a comma-separated list. Be specific and concise.
""",
            )

            key_concepts_result = await self.llm.ainvoke(
                key_concepts_prompt.format(proposal=proposal_content[:1500])
            )

            # Use these concepts for web search
            key_concepts = key_concepts_result.content.strip()
            self.logger.info(
                f"[DEBUG:SocialAgent:{proposal_id}] Extracted key concepts: {key_concepts}"
            )

            if key_concepts:
                dao_name = self.config.get("dao_name", "DAO")
                search_query = (
                    f"{key_concepts} {dao_name} bitcoin community perspective"
                )
                self.logger.info(
                    f"[DEBUG:SocialAgent:{proposal_id}] Searching: {search_query}"
                )

                search_results, token_usage = await self.web_search(
                    query=search_query,
                    num_results=3,
                )
        except Exception as e:
            self.logger.error(
                f"[DEBUG:SocialAgent:{proposal_id}] Error in web search: {str(e)}"
            )
            search_results = []

        # Format search results for inclusion in the prompt
        search_results_text = ""
        if search_results:
            search_results_text = "Web search results relevant to this proposal:\n\n"
            for i, doc in enumerate(search_results):
                page_content = doc.get("page_content", "No content available")
                source_urls = doc.get("metadata", {}).get("source_urls", [])

                if source_urls:
                    for j, source in enumerate(source_urls):
                        search_results_text += (
                            f"Source {i+1}.{j+1}: {source.get('title', 'Unknown')}\n"
                        )
                        search_results_text += f"URL: {source.get('url', 'Unknown')}\n"

                search_results_text += f"Summary: {page_content[:300]}...\n\n"
        else:
            search_results_text = "No relevant web search results available.\n"

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

        prompt = PromptTemplate(
            input_variables=["proposal_data", "search_results", "community_info"],
            template="""<system>
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
<social_context_evaluation>
  <proposal_data>
    {proposal_data}
  </proposal_data>
  <community_info>
    {community_info}
  </community_info>
  <external_context>
    {search_results}
  </external_context>
  <task>
    <criteria>
      <criterion weight=\"40\">Community benefit and inclusion</criterion>
      <criterion weight=\"30\">Alignment with community values and interests</criterion>
      <criterion weight=\"20\">Potential for community engagement</criterion>
      <criterion weight=\"10\">Consideration of diverse stakeholders</criterion>
    </criteria>
    <considerations>
      <consideration>Will this proposal benefit the broader community or just a few members?</consideration>
      <consideration>Is there likely community support or opposition?</consideration>
      <consideration>Does it foster inclusivity and participation?</consideration>
      <consideration>Does it align with the community's values and interests?</consideration>
      <consideration>Could it cause controversy or division?</consideration>
      <consideration>Does it consider the needs of diverse stakeholders?</consideration>
    </considerations>
    <scoring_guide>
      <score range=\"0-20\">No benefit, misaligned, or divisive</score>
      <score range=\"21-50\">Significant issues or missing details</score>
      <score range=\"51-70\">Adequate but with some concerns or minor risks</score>
      <score range=\"71-90\">Good benefit, aligned, and inclusive</score>
      <score range=\"91-100\">Excellent benefit, highly aligned, and unifying</score>
    </scoring_guide>
  </task>
  <output_format>
    Provide:
    <score>A number from 0-100</score>
    <flags>List of any critical social issues or red flags</flags>
    <summary>Brief summary of your social evaluation</summary>
    Only return a JSON object with these three fields: score, flags (array), and summary.
  </output_format>
</social_context_evaluation>""",
        )

        try:
            formatted_prompt_text = prompt.format(
                proposal_data=proposal_content,
                search_results=search_results_text,
                community_info=community_info,
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
            state["token_usage"]["social_agent"] = token_usage_data
            result_dict["token_usage"] = token_usage_data

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
            }
