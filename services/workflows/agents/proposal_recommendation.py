from typing import Any, Dict, List, Optional
from uuid import UUID

from langchain_core.prompts.chat import ChatPromptTemplate

from backend.factory import backend
from backend.models import DAO, Proposal, ProposalFilter
from lib.logger import configure_logger
from services.workflows.mixins.capability_mixins import BaseCapabilityMixin
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
            try:
                # Safely get proposal attributes with proper error handling
                title = getattr(proposal, "title", None) or "Untitled"
                content = getattr(proposal, "content", None) or "No content"
                proposal_type = getattr(proposal, "type", None) or "Unknown"
                status = getattr(proposal, "status", None) or "Unknown"
                passed = getattr(proposal, "passed", None)

                # Safely handle created_at date formatting
                created_at = getattr(proposal, "created_at", None)
                created_str = "Unknown"
                if created_at:
                    try:
                        created_str = created_at.strftime("%Y-%m-%d")
                    except (AttributeError, ValueError):
                        created_str = str(created_at)

                # Safely convert content to string and limit length
                content_str = str(content)[:500] if content else "No content"

                # Ensure content is treated as plain text and safe for prompt processing
                # Remove any control characters that might cause parsing issues
                content_str = "".join(
                    char for char in content_str if ord(char) >= 32 or char in "\n\r\t"
                )

                # Escape curly braces to prevent f-string/format interpretation issues
                content_str = content_str.replace("{", "{{").replace("}", "}}")

                proposal_text = f"""<proposal id="{i + 1}">
  <title>{str(title)[:100]}</title>
  <content>{content_str}</content>
  <type>{str(proposal_type)}</type>
  <status>{str(status)}</status>
  <created>{created_str}</created>
  <passed>{str(passed) if passed is not None else "Unknown"}</passed>
</proposal>"""
                formatted_proposals.append(proposal_text)
            except Exception as e:
                self.logger.error(f"Error formatting proposal {i}: {str(e)}")
                # Add a fallback proposal entry
                formatted_proposals.append(
                    f"""<proposal id="{i + 1}">
  <title>Error loading proposal</title>
  <content>Could not load proposal data: {str(e)}</content>
  <type>Unknown</type>
  <status>Unknown</status>
  <created>Unknown</created>
  <passed>Unknown</passed>
</proposal>"""
                )

        return "\n\n".join(formatted_proposals)

    def _create_chat_messages(
        self,
        dao_name: str,
        dao_mission: str,
        dao_description: str,
        recent_proposals: str,
        focus_area: str,
        specific_needs: str,
        proposal_images: List[Dict[str, Any]] = None,
    ) -> List:
        """Create chat messages for the proposal recommendation.

        Args:
            dao_name: Name of the DAO
            dao_mission: Mission statement of the DAO
            dao_description: Description of the DAO
            recent_proposals: Formatted recent proposals text
            focus_area: Focus area for the recommendation
            specific_needs: Specific needs mentioned
            proposal_images: List of processed images

        Returns:
            List of chat messages
        """
        # System message with guidelines and context
        system_content = """You are an expert DAO governance advisor. Generate a thoughtful proposal recommendation that aligns with the DAO's mission and builds upon past proposals intelligently.

Analysis Criteria:
- Alignment with the DAO's stated mission and values
- Gaps or opportunities not addressed by recent proposals
- Natural progression from successful past proposals
- Practical feasibility and clear deliverables
- Potential positive impact on the DAO community
- Resource requirements and sustainability

Guidelines:
- Avoid duplicating recent proposals unless building meaningfully upon them
- Ensure the proposal is specific and actionable
- Consider both short-term wins and long-term strategic value
- Make sure the proposal scope is reasonable and achievable
- Include clear success metrics where applicable

Output Format:
Provide a JSON object with:
- title: A clear, compelling proposal title (max 100 characters)
- content: Detailed proposal content with specific objectives, deliverables, timeline, and success metrics (max 1800 characters)
- rationale: Explanation of why this proposal is recommended based on the DAO's context
- priority: Priority level: high, medium, or low
- estimated_impact: Expected positive impact on the DAO
- suggested_action: Specific next steps or actions to implement (optional)

IMPORTANT: Use only ASCII characters (characters 0-127) in all fields. Avoid any Unicode characters, emojis, special symbols, or non-ASCII punctuation. Use standard English letters, numbers, and basic punctuation only."""

        # User message with the specific DAO context and request
        user_content = f"""Based on the following DAO information and context, generate a thoughtful recommendation for a new proposal that would benefit the DAO:

DAO Context:
- Name: {dao_name}
- Mission: {dao_mission}
- Description: {dao_description}

Recent Proposals:
{recent_proposals}

Recommendation Request:
- Focus Area: {focus_area}
- Specific Needs: {specific_needs or "No specific needs mentioned"}

Please analyze this information and provide a proposal recommendation that aligns with the DAO's mission, addresses gaps in recent proposals, and offers clear value to the community."""

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
        try:
            recent_proposals = await self._fetch_dao_proposals(dao_id, limit=8)
            proposals_context = self._format_proposals_for_context(recent_proposals)
        except Exception as e:
            self.logger.error(
                f"Error fetching/formatting proposals for DAO {dao_id}: {str(e)}"
            )
            proposals_context = (
                "<no_proposals>No past proposals available due to error.</no_proposals>"
            )

        # Get additional context from state if available
        focus_area = state.get("focus_area", "general improvement")
        specific_needs = state.get("specific_needs", "")
        proposal_images = state.get("proposal_images", [])

        try:
            # Create chat messages
            messages = self._create_chat_messages(
                dao_name=dao.name or "Unknown DAO",
                dao_mission=dao.mission or "Mission not specified",
                dao_description=dao.description or "Description not provided",
                recent_proposals=proposals_context,
                focus_area=focus_area,
                specific_needs=specific_needs,
                proposal_images=proposal_images,
            )

            # Create chat prompt template
            prompt = ChatPromptTemplate.from_messages(messages)
            formatted_prompt = prompt.format()

            # Get structured output from the LLM
            result = await self.llm.with_structured_output(
                ProposalRecommendationOutput
            ).ainvoke(formatted_prompt)
            result_dict = result.model_dump()

            # Track token usage
            token_usage_data = self.track_token_usage(str(formatted_prompt), result)
            state["token_usage"]["proposal_recommendation_agent"] = token_usage_data
            result_dict["token_usage"] = token_usage_data

            # Add metadata
            result_dict["dao_id"] = str(dao_id)
            result_dict["dao_name"] = dao.name
            result_dict["proposals_analyzed"] = len(recent_proposals)
            result_dict["images_processed"] = len(proposal_images)

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
