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
            template="""Evaluate the social impact and community aspects of this proposal.

# Proposal
{proposal_data}

# Community Information
{community_info}

# External Context
{search_results}

# Task
Score this proposal from 0-100 based on:
1. Community benefit and inclusion (40%)
2. Alignment with community values and interests (30%)
3. Potential for community engagement (20%)
4. Consideration of diverse stakeholders (10%)

When analyzing, consider:
- Will this proposal benefit the broader community or just a few members?
- Is there likely community support or opposition?
- Does it foster inclusivity and participation?
- Does it align with the community's values and interests?
- Could it cause controversy or division?
- Does it consider the needs of diverse stakeholders?

# Output Format
Provide:
- Score (0-100)
- List of any critical social issues or red flags
- Brief summary of your social evaluation

Only return a JSON object with these three fields: score, flags (array), and summary.""",
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
