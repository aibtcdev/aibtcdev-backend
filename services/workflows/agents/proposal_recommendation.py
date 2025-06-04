from typing import Any, Dict, List, Optional
from uuid import UUID

from langchain.prompts import PromptTemplate
from langchain_core.messages import HumanMessage

from backend.factory import backend
from backend.models import DAO, Proposal, ProposalFilter
from lib.logger import configure_logger
from services.workflows.capability_mixins import BaseCapabilityMixin
from services.workflows.utils.models import ProposalRecommendationOutput
from services.workflows.utils.token_usage import TokenUsageMixin

logger = configure_logger(__name__)


class ProposalRecommendationAgent(BaseCapabilityMixin, TokenUsageMixin):
    """Agent that generates proposal recommendations based on DAO mission and historical context."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Proposal Recommendation Agent.

        Args:
            config: Optional configuration dictionary
        """
        BaseCapabilityMixin.__init__(
            self, config=config, state_key="proposal_recommendation"
        )
        TokenUsageMixin.__init__(self)
        self.initialize()

    async def _fetch_dao_info(self, dao_id: UUID) -> Optional[DAO]:
        """Fetch DAO information from the database.

        Args:
            dao_id: The UUID of the DAO

        Returns:
            DAO object or None if not found
        """
        try:
            dao = backend.get_dao(dao_id)
            if dao:
                self.logger.debug(f"Retrieved DAO info for {dao_id}: {dao.name}")
            else:
                self.logger.warning(f"No DAO found with ID: {dao_id}")
            return dao
        except Exception as e:
            self.logger.error(f"Error fetching DAO info for {dao_id}: {str(e)}")
            return None

    async def _fetch_dao_proposals(
        self, dao_id: UUID, limit: int = 50
    ) -> List[Proposal]:
        """Fetch recent proposals for a specific DAO from the database.

        Args:
            dao_id: The UUID of the DAO
            limit: Maximum number of proposals to fetch

        Returns:
            List of Proposal objects
        """
        try:
            # Create filter to get proposals for this DAO
            filters = ProposalFilter(dao_id=dao_id)

            # Fetch proposals
            proposals = backend.list_proposals(filters)

            # Sort by creation date (newest first) and limit results
            sorted_proposals = sorted(
                proposals, key=lambda p: p.created_at, reverse=True
            )
            limited_proposals = sorted_proposals[:limit]

            self.logger.debug(
                f"Retrieved {len(limited_proposals)} recent proposals for DAO {dao_id}"
            )
            return limited_proposals
        except Exception as e:
            self.logger.error(f"Error fetching proposals for DAO {dao_id}: {str(e)}")
            return []

    def _format_proposals_for_context(self, proposals: List[Proposal]) -> str:
        """Format proposals for inclusion in the prompt.

        Args:
            proposals: List of proposals

        Returns:
            Formatted text of past proposals
        """
        if not proposals:
            return "<no_proposals>No past proposals available.</no_proposals>"

        formatted_proposals = []
        for i, proposal in enumerate(proposals):
            proposal_text = f"""<proposal id="{i+1}">
  <title>{proposal.title or 'Untitled'}</title>
  <content>{proposal.content or 'No content'}</content>
  <type>{proposal.type or 'Unknown'}</type>
  <status>{proposal.status or 'Unknown'}</status>
  <created>{proposal.created_at.strftime('%Y-%m-%d') if proposal.created_at else 'Unknown'}</created>
  <passed>{proposal.passed if proposal.passed is not None else 'Unknown'}</passed>
</proposal>"""
            formatted_proposals.append(proposal_text)

        return "\n\n".join(formatted_proposals)

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a proposal recommendation based on DAO context.

        Args:
            state: The current workflow state containing dao_id

        Returns:
            Dictionary containing the proposal recommendation
        """
        dao_id = state.get("dao_id")
        if not dao_id:
            self.logger.error("No dao_id provided in state")
            return {
                "error": "dao_id is required",
                "title": "",
                "content": "",
                "rationale": "Error: No DAO ID provided",
                "priority": "low",
                "estimated_impact": "None",
            }

        # Initialize token usage tracking in state if not present
        if "token_usage" not in state:
            state["token_usage"] = {}

        # Fetch DAO information
        dao = await self._fetch_dao_info(dao_id)
        if not dao:
            return {
                "error": "DAO not found",
                "title": "",
                "content": "",
                "rationale": f"Error: DAO with ID {dao_id} not found",
                "priority": "low",
                "estimated_impact": "None",
            }

        # Fetch recent proposals for context
        recent_proposals = await self._fetch_dao_proposals(dao_id, limit=8)
        proposals_context = self._format_proposals_for_context(recent_proposals)

        # Get additional context from state if available
        focus_area = state.get("focus_area", "general improvement")
        specific_needs = state.get("specific_needs", "")

        prompt = PromptTemplate(
            input_variables=[
                "dao_name",
                "dao_mission",
                "dao_description",
                "recent_proposals",
                "focus_area",
                "specific_needs",
            ],
            template="""<system>
  <reminder>
    You are an expert DAO governance advisor. Generate a thoughtful proposal recommendation that aligns with the DAO's mission and builds upon past proposals intelligently.
  </reminder>
</system>
<proposal_recommendation_task>
  <dao_context>
    <name>{dao_name}</name>
    <mission>{dao_mission}</mission>
    <description>{dao_description}</description>
  </dao_context>
  
  <recent_proposals>
    {recent_proposals}
  </recent_proposals>
  
  <recommendation_request>
    <focus_area>{focus_area}</focus_area>
    <specific_needs>{specific_needs}</specific_needs>
  </recommendation_request>
  
  <task>
    Based on the DAO's mission, description, and recent proposal history, generate a thoughtful recommendation for a new proposal that would benefit the DAO. Consider:
    
    <analysis_criteria>
      <criterion>Alignment with the DAO's stated mission and values</criterion>
      <criterion>Gaps or opportunities not addressed by recent proposals</criterion>
      <criterion>Natural progression from successful past proposals</criterion>
      <criterion>Practical feasibility and clear deliverables</criterion>
      <criterion>Potential positive impact on the DAO community</criterion>
      <criterion>Resource requirements and sustainability</criterion>
    </analysis_criteria>
    
    <guidelines>
      <guideline>Avoid duplicating recent proposals unless building meaningfully upon them</guideline>
      <guideline>Ensure the proposal is specific and actionable</guideline>
      <guideline>Consider both short-term wins and long-term strategic value</guideline>
      <guideline>Make sure the proposal scope is reasonable and achievable</guideline>
      <guideline>Include clear success metrics where applicable</guideline>
    </guidelines>
  </task>
  
  <output_format>
    Provide a JSON object with:
    <title>A clear, compelling proposal title (max 100 characters)</title>
    <content>Detailed proposal content with specific objectives, deliverables, timeline, and success metrics (max 2048 characters)</content>
    <rationale>Explanation of why this proposal is recommended based on the DAO's context</rationale>
    <priority>Priority level: high, medium, or low</priority>
    <estimated_impact>Expected positive impact on the DAO</estimated_impact>
    <suggested_action>Specific next steps or actions to implement (optional)</suggested_action>
  </output_format>
</proposal_recommendation_task>""",
        )

        try:
            formatted_prompt_text = prompt.format(
                dao_name=dao.name or "Unknown DAO",
                dao_mission=dao.mission or "Mission not specified",
                dao_description=dao.description or "Description not provided",
                recent_proposals=proposals_context,
                focus_area=focus_area,
                specific_needs=specific_needs or "No specific needs mentioned",
            )

            llm_input_message = HumanMessage(content=formatted_prompt_text)

            # Get structured output from the LLM
            result = await self.llm.with_structured_output(
                ProposalRecommendationOutput
            ).ainvoke([llm_input_message])
            result_dict = result.model_dump()

            # Track token usage
            token_usage_data = self.track_token_usage(formatted_prompt_text, result)
            state["token_usage"]["proposal_recommendation_agent"] = token_usage_data
            result_dict["token_usage"] = token_usage_data

            # Add metadata
            result_dict["dao_id"] = str(dao_id)
            result_dict["dao_name"] = dao.name
            result_dict["proposals_analyzed"] = len(recent_proposals)

            self.logger.info(
                f"Generated proposal recommendation for DAO {dao_id}: {result_dict.get('title', 'Unknown')}"
            )
            return result_dict

        except Exception as e:
            self.logger.error(
                f"Error generating proposal recommendation for DAO {dao_id}: {str(e)}"
            )
            return {
                "error": str(e),
                "title": "",
                "content": "",
                "rationale": f"Error generating recommendation: {str(e)}",
                "priority": "low",
                "estimated_impact": "None",
                "dao_id": str(dao_id),
                "dao_name": dao.name if dao else "Unknown",
            }
