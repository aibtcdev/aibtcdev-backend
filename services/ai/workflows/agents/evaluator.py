from typing import Any, Dict, List, Optional
from uuid import UUID

from langchain_core.prompts.chat import ChatPromptTemplate

from backend.factory import backend
from backend.models import Proposal, ProposalFilter
from lib.logger import configure_logger
from services.ai.workflows.mixins.capability_mixins import (
    BaseCapabilityMixin,
    PromptCapability,
)
from services.ai.workflows.mixins.vector_mixin import VectorRetrievalCapability
from services.ai.workflows.utils.models import (
    ComprehensiveEvaluationOutput,
    ComprehensiveEvaluatorAgentProcessOutput,
    EvaluationCategory,
)
from services.ai.workflows.utils.token_usage import TokenUsageMixin

# Add these constants after the imports, before the class definition

# Default prompts for comprehensive evaluation
DEFAULT_SYSTEM_PROMPT = """You are a comprehensive DAO governance evaluator with expertise across multiple domains. You will evaluate proposals across configurable evaluation categories in a single comprehensive assessment.

**Critical Reasoning Requirements**:
- **Detailed Chain of Thought (CoT)**: For each evaluation category, provide extensive step-by-step reasoning that goes far beyond simple scoring. Explain your analytical process in detail, including:
  * How you interpret specific elements of the proposal
  * What evidence you consider and why it's significant
  * How you weigh competing factors and trade-offs
  * What assumptions you make and their justification
  * How you handle ambiguities or uncertainties
  * Your intermediate conclusions and the logic connecting them
- **Comprehensive Analysis**: Each category evaluation must contain substantive analysis, not just bullet points or brief statements. Provide rich context, detailed reasoning, and nuanced evaluation that demonstrates deep understanding of the proposal's implications.
- **Robust Reflection**: After completing initial analysis, conduct thorough reflection that examines:
  * Alternative interpretations of key proposal elements
  * Potential blind spots or biases in your analysis
  * Cross-category interactions and conflicts
  * Whether your reasoning is internally consistent
  * Areas where additional information would be valuable
- **Transparent Methodology**: Document your reasoning process so thoroughly that another evaluator could understand and verify your conclusions.

**Analysis Depth Requirements**:
You must provide extensive, substantive analysis rather than superficial assessments. Each evaluation section should demonstrate sophisticated reasoning that considers multiple perspectives, potential implications, and contextual factors. Avoid generic statements and focus on proposal-specific insights that show deep analytical thinking.

**Image Evaluation**: If images are attached to this proposal, they are an integral part of the proposal content. You must carefully examine and evaluate any provided images across ALL evaluation categories, considering how they support, clarify, or relate to the written proposal. Images may contain diagrams, charts, financial projections, community plans, historical comparisons, mockups, or other visual information that is essential to understanding the full scope and merit of the proposal. Include your analysis of the visual content in ALL relevant evaluation sections.

**DYNAMIC EVALUATION FRAMEWORK**

You will evaluate the proposal across the following categories with their specified weights:

{evaluation_categories}

**SCORING METHODOLOGY**

For each evaluation category, provide scores from 1-100:
- 1-20: Critical issues, not aligned, or harmful
- 21-50: Significant issues or missing details
- 51-70: Adequate but with some concerns or minor risks
- 71-90: Good quality, aligned, and beneficial
- 91-100: Excellent quality, highly aligned, and valuable

**Detailed Reasoning for Each Category**:
- For each category, provide comprehensive analysis explaining:
  * Specific evidence from the proposal and why it's relevant
  * How this evidence aligns or conflicts with the DAO's goals and values
  * Detailed risk assessment and uncertainty analysis
  * Comparative analysis against past proposals or best practices
  * Consideration of multiple stakeholder perspectives
- Show your complete thought process for arriving at scores, including:
  * Intermediate reasoning for each criterion score
  * How you balanced competing factors
  * What alternatives you considered and why you rejected them
  * Key assumptions and their potential impact on conclusions
- **Limit reasoning to 3 bullet points maximum per category** - make each bullet point comprehensive and substantive

**FINAL DECISION FRAMEWORK**

The final decision will be based on the weighted average of all category scores. Proposals scoring 70 or above will be approved, while those below 70 will be rejected.

Final Decision Process:
1. Calculate the weighted average of all category scores using their specified weights
2. Synthesize findings from all categories, explaining how they interact and reinforce or conflict with each other
3. Provide comprehensive analysis of the proposal's overall merit beyond just numerical scores
4. Assess critical flags and their implications for the DAO's long-term interests
5. Conduct thorough reflection examining alternative interpretations and potential blind spots
6. Determine final overall score that directly maps to approval decision
7. Make approve/reject decision (true/false) based on the score threshold with detailed, substantive reasoning

**Overall Score Calculation**:
- Calculate weighted average using the provided category weights
- Apply any adjustments based on critical flags or exceptional circumstances
- Ensure the final score accurately reflects the proposal's overall merit

**Decision Mapping**:
- **Score 70-100**: APPROVE (decision = true) - Proposal meets or exceeds the approval threshold
- **Score 1-69**: REJECT (decision = false) - Proposal falls below the approval threshold

**Score Guidelines**:
- **90-100**: Exceptional proposal with outstanding merit across all categories
- **80-89**: Excellent proposal with strong benefits and minimal risks
- **70-79**: Good proposal that meets approval threshold with manageable concerns
- **60-69**: Adequate proposal with significant issues preventing approval
- **50-59**: Below average proposal with substantial problems
- **40-49**: Poor proposal with major flaws or misalignment
- **30-39**: Very poor proposal with critical issues
- **1-29**: Unacceptable proposal with fundamental problems

**Veto Conditions** (automatic rejection regardless of calculated score):
- Any category score below 30 indicates critical issues
- Multiple critical flags indicating legal, security, or ethical violations
- Fundamental misalignment with DAO values or objectives
- Evidence of fraud, manipulation, or malicious intent

**Reflection Phase**:
- Re-evaluate each category score and reasoning with fresh perspective
- Consider alternative interpretations of proposal data, images, and contextual information
- Examine potential biases, assumptions, or analytical blind spots
- Assess whether your reasoning is internally consistent across all categories
- Document any adjustments to scores or reasoning with detailed justification
- Verify that the final score accurately reflects the proposal's overall merit and aligns with the approval threshold

**CRITICAL OUTPUT REQUIREMENTS**

Return a JSON object with ALL required fields containing rich, substantive analysis:

**For Each Category**: Provide comprehensive reasoning (maximum 3 bullet points) that includes:
- Specific evidence from the proposal and its significance
- Risk assessment and uncertainty analysis
- Clear explanation of how you reached your conclusions

**For Final Explanation**: Provide comprehensive synthesis (minimum 300-400 words) that includes:
- How findings from all categories interact and inform the overall assessment
- Analysis of the proposal's broader implications for the DAO's future
- Consideration of long-term consequences and strategic alignment
- Discussion of key trade-offs and alternative perspectives considered
- Detailed justification for the final decision beyond score calculations
- Assessment of confidence level with specific reasoning about uncertainties

**Quality Standards**: All text fields must demonstrate sophisticated analysis, avoid generic statements, and provide proposal-specific insights that show deep understanding of the evaluation context."""

DEFAULT_USER_PROMPT_TEMPLATE = """Please conduct a comprehensive evaluation of the following proposal across all specified categories, providing extensive detailed reasoning as specified in the guidelines:

**PROPOSAL TO EVALUATE:**
{proposal_content}

**DAO MISSION:**
{dao_mission}

**COMMUNITY INFORMATION:**
{community_info}

**HISTORICAL CONTEXT - PAST DAO PROPOSALS:**
{past_proposals}

**EVALUATION CATEGORIES:**
{evaluation_categories}

**DETAILED EVALUATION INSTRUCTIONS:**

Perform thorough analysis across all specified evaluation categories with the following requirements:

1. **Comprehensive Category Analysis**: For each category, provide extensive reasoning that goes far beyond simple scoring. Include detailed examination of specific proposal elements, evidence analysis, risk assessment, stakeholder considerations, and comparative context.

2. **Rich Chain of Thought**: Document your complete analytical process for each category, showing how you interpret evidence, weigh competing factors, handle uncertainties, and arrive at conclusions. Avoid superficial assessments and demonstrate sophisticated reasoning.

3. **Concise but Substantive Reasoning**: Each category reasoning must be limited to 3 bullet points maximum, but each bullet point should be comprehensive and contain substantive analysis that provides deep insights into the proposal's implications for that evaluation area.

4. **Thorough Reflection**: Conduct detailed reflection examining alternative interpretations, potential biases, cross-category interactions, and areas of uncertainty. Document any adjustments to your reasoning with full justification.

5. **Comprehensive Final Assessment**: Provide a detailed final explanation (300-400 words minimum) that synthesizes findings across all categories, discusses broader implications for the DAO, considers long-term consequences, and provides substantive justification for your decision beyond mere score calculations.

**Critical Requirements:**
- Examine any attached images thoroughly and integrate visual analysis across all relevant evaluation sections
- Provide proposal-specific insights rather than generic statements
- Demonstrate deep understanding of the evaluation context and DAO dynamics
- Ensure all reasoning is transparent, detailed, and reproducible
- Focus on comprehensive analysis rather than brief summaries
- **Limit each category reasoning to exactly 3 bullet points, but make each bullet point rich and substantive**"""

logger = configure_logger(__name__)


class ComprehensiveEvaluatorAgent(
    BaseCapabilityMixin, VectorRetrievalCapability, TokenUsageMixin, PromptCapability
):
    """Comprehensive Evaluator Agent that performs all evaluations in a single LLM pass."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Comprehensive Evaluator Agent.

        Args:
            config: Optional configuration dictionary
        """
        BaseCapabilityMixin.__init__(
            self, config=config, state_key="comprehensive_evaluation"
        )
        VectorRetrievalCapability.__init__(self)
        TokenUsageMixin.__init__(self)
        PromptCapability.__init__(self)
        self.initialize()
        self._initialize_vector_capability()

    def _initialize_vector_capability(self):
        """Initialize the vector retrieval capability if not already initialized."""
        if not hasattr(self, "retrieve_from_vector_store"):
            self.retrieve_from_vector_store = (
                VectorRetrievalCapability.retrieve_from_vector_store.__get__(
                    self, self.__class__
                )
            )
            self.logger.info(
                "Initialized vector retrieval capability for ComprehensiveEvaluatorAgent"
            )

    async def _fetch_dao_proposals(
        self, dao_id: UUID, exclude_proposal_id: Optional[str] = None
    ) -> List[Proposal]:
        """Fetch all proposals for a specific DAO from Supabase, excluding the current proposal.

        Args:
            dao_id: The UUID of the DAO
            exclude_proposal_id: Optional proposal ID to exclude from results

        Returns:
            List of Proposal objects (excluding the current proposal if specified)
        """
        try:
            # Create filter to get all proposals for this DAO
            filters = ProposalFilter(dao_id=dao_id)

            # Fetch proposals
            proposals = backend.list_proposals(filters)

            # Filter out the current proposal if specified
            if exclude_proposal_id:
                proposals = [p for p in proposals if str(p.id) != exclude_proposal_id]
                self.logger.debug(
                    f"Excluded current proposal {exclude_proposal_id} from historical context"
                )

            self.logger.debug(
                f"Retrieved {len(proposals)} proposals for DAO {dao_id} (excluding current)"
            )
            return proposals
        except Exception as e:
            self.logger.error(f"Error fetching proposals for DAO {dao_id}: {str(e)}")
            return []

    def _format_proposals_for_context(self, proposals: List[Proposal]) -> str:
        """Format proposals for inclusion in the prompt.

        Args:
            proposals: List of all proposals

        Returns:
            Formatted text of past proposals
        """
        if not proposals:
            return "<no_proposals>No past proposals available.</no_proposals>"

        try:
            # Sort proposals by creation date (newest first to prioritize recent history)
            sorted_proposals = []
            for proposal in proposals:
                try:
                    created_at = getattr(proposal, "created_at", None)
                    if created_at:
                        sorted_proposals.append((proposal, created_at))
                    else:
                        sorted_proposals.append((proposal, None))
                except Exception as e:
                    self.logger.warning(
                        f"Error accessing created_at for proposal: {str(e)}"
                    )
                    sorted_proposals.append((proposal, None))

            # Sort by created_at, handling None values
            sorted_proposals.sort(
                key=lambda x: x[1] if x[1] is not None else 0, reverse=True
            )
        except Exception as e:
            self.logger.error(f"Error sorting proposals: {str(e)}")
            sorted_proposals = [(proposal, None) for proposal in proposals]

        # Format individual proposals with all relevant details
        formatted_proposals = []
        for i, (proposal, _) in enumerate(
            sorted_proposals[:8]
        ):  # Limit to first 8 for context
            try:
                # Safely get proposal attributes with proper error handling
                title = getattr(proposal, "title", None) or "Untitled"
                summary = (
                    getattr(proposal, "summary", None)
                    or getattr(proposal, "content", None)
                    or "No summary"
                )
                status = getattr(proposal, "status", None) or "Unknown"
                proposal_type = getattr(proposal, "type", None) or "Unknown"
                passed = getattr(proposal, "passed", None)
                action = getattr(proposal, "action", None) or "None"
                creator = getattr(proposal, "creator", None) or "Unknown"
                tags = getattr(proposal, "tags", None) or []
                executed = getattr(proposal, "executed", None)
                votes_for = getattr(proposal, "votes_for", None) or 0
                votes_against = getattr(proposal, "votes_against", None) or 0
                met_quorum = getattr(proposal, "met_quorum", None)
                met_threshold = getattr(proposal, "met_threshold", None)

                # Safely handle created_at date formatting
                created_at = getattr(proposal, "created_at", None)
                created_str = "Unknown"
                if created_at:
                    try:
                        created_str = created_at.strftime("%Y-%m-%d")
                    except (AttributeError, ValueError):
                        created_str = str(created_at)

                # Safely convert summary to string and limit length
                summary_str = str(summary)[:500] if summary else "No summary"

                # Ensure summary is treated as plain text and safe for prompt processing
                summary_str = "".join(
                    char for char in summary_str if ord(char) >= 32 or char in "\n\r\t"
                )

                # Escape curly braces to prevent f-string/format interpretation issues
                summary_str = summary_str.replace("{", "{{").replace("}", "}}")

                # Format tags as a comma-separated string
                tags_str = (
                    ", ".join(
                        str(tag) for tag in (tags if isinstance(tags, list) else [])
                    )
                    if tags
                    else "None"
                )

                proposal_text = (
                    f'<proposal id="{i + 1}">\n'
                    f"  <title>{str(title)[:100]}</title>\n"
                    f"  <summary>{summary_str}</summary>\n"
                    f"  <creator>{str(creator)}</creator>\n"
                    f"  <status>{str(status)}</status>\n"
                    f"  <type>{str(proposal_type)}</type>\n"
                    f"  <created_at>{created_str}</created_at>\n"
                    f"  <passed>{str(passed) if passed is not None else 'False'}</passed>\n"
                    f"  <executed>{str(executed) if executed is not None else 'False'}</executed>\n"
                    f"  <votes_for>{str(votes_for)}</votes_for>\n"
                    f"  <votes_against>{str(votes_against)}</votes_against>\n"
                    f"  <met_quorum>{str(met_quorum) if met_quorum is not None else 'Unknown'}</met_quorum>\n"
                    f"  <met_threshold>{str(met_threshold) if met_threshold is not None else 'Unknown'}</met_threshold>\n"
                    f"  <tags>{tags_str}</tags>\n"
                    f"  <action>{str(action)}</action>\n"
                    f"</proposal>"
                )

                formatted_proposals.append(proposal_text)
            except Exception as e:
                self.logger.error(f"Error formatting proposal {i}: {str(e)}")
                # Add a fallback proposal entry
                formatted_proposals.append(
                    f'<proposal id="{i + 1}">\n'
                    f"  <title>Error loading proposal</title>\n"
                    f"  <summary>Could not load proposal data: {str(e)}</summary>\n"
                    f"  <creator>Unknown</creator>\n"
                    f"  <status>Unknown</status>\n"
                    f"  <type>Unknown</type>\n"
                    f"  <created_at>Unknown</created_at>\n"
                    f"  <passed>Unknown</passed>\n"
                    f"  <executed>Unknown</executed>\n"
                    f"  <votes_for>0</votes_for>\n"
                    f"  <votes_against>0</votes_against>\n"
                    f"  <met_quorum>Unknown</met_quorum>\n"
                    f"  <met_threshold>Unknown</met_threshold>\n"
                    f"  <tags>None</tags>\n"
                    f"  <action>None</action>\n"
                    f"</proposal>"
                )

        return (
            "\n\n".join(formatted_proposals)
            if formatted_proposals
            else "<no_proposals>No past proposals available.</no_proposals>"
        )

    def _create_chat_messages(
        self,
        proposal_content: str,
        dao_mission: str,
        community_info: str,
        past_proposals: str,
        evaluation_categories: List[Dict[str, Any]],
        proposal_images: List[Dict[str, Any]] = None,
        dao_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        profile_id: Optional[str] = None,
        custom_system_prompt: Optional[str] = None,
        custom_user_prompt: Optional[str] = None,
    ) -> List:
        """Create chat messages for comprehensive evaluation with dynamic categories.

        Args:
            proposal_content: The proposal content to evaluate
            dao_mission: The DAO mission statement
            community_info: Information about the DAO community
            past_proposals: Formatted past proposals text
            evaluation_categories: List of evaluation categories with names, weights, and descriptions
            proposal_images: List of processed images
            dao_id: Optional DAO ID for custom prompt injection
            agent_id: Optional agent ID for custom prompt injection
            profile_id: Optional profile ID for custom prompt injection
            custom_system_prompt: Optional custom system prompt to override default
            custom_user_prompt: Optional custom user prompt to override default

        Returns:
            List of chat messages
        """
        # Format evaluation categories for prompt
        categories_text = ""
        for i, category in enumerate(evaluation_categories, 1):
            name = category.get("name", f"Category {i}")
            weight = category.get("weight", 0.25)
            description = category.get("description", "No description provided")

            categories_text += f"""
**{i}. {name.upper()} EVALUATION ({weight * 100:.0f}% of final decision weight)**
{description}

"""

        # Use custom system prompt or default, format with categories
        if custom_system_prompt:
            system_content = custom_system_prompt.format(
                evaluation_categories=categories_text.strip()
            )
        else:
            system_content = DEFAULT_SYSTEM_PROMPT.format(
                evaluation_categories=categories_text.strip()
            )

        # Use custom user prompt or default, format with data
        if custom_user_prompt:
            # Format custom user prompt with the same data
            user_content = custom_user_prompt.format(
                proposal_content=proposal_content,
                dao_mission=dao_mission,
                community_info=community_info,
                past_proposals=past_proposals,
                evaluation_categories=categories_text.strip(),
            )
        else:
            user_content = DEFAULT_USER_PROMPT_TEMPLATE.format(
                proposal_content=proposal_content,
                dao_mission=dao_mission,
                community_info=community_info,
                past_proposals=past_proposals,
                evaluation_categories=categories_text.strip(),
            )

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

        # Apply custom prompt injection if enabled
        if dao_id or agent_id or profile_id:
            try:
                custom_prompt_template = self.create_chat_prompt_with_custom_injection(
                    default_system_message=system_content,
                    default_user_message=user_content,
                    dao_id=dao_id,
                    agent_id=agent_id,
                    profile_id=profile_id,
                    prompt_type="comprehensive_evaluation",
                )
                # Return the ChatPromptTemplate directly
                return custom_prompt_template
            except Exception as e:
                self.logger.warning(
                    f"Custom prompt injection failed, using default: {e}"
                )

        return messages

    async def process(
        self, state: Dict[str, Any]
    ) -> ComprehensiveEvaluatorAgentProcessOutput:
        """Process the proposal with comprehensive evaluation.

        Args:
            state: The current workflow state containing proposal data and optional custom prompts

        Returns:
            Dictionary containing comprehensive evaluation results
        """
        self._initialize_vector_capability()
        proposal_id = state.get("proposal_id", "unknown")
        proposal_content = state.get("proposal_content", "")
        dao_id = state.get("dao_id")
        agent_id = state.get("agent_id")
        profile_id = state.get("profile_id")
        custom_system_prompt = state.get("custom_system_prompt")
        custom_user_prompt = state.get("custom_user_prompt")

        # Ensure proposal content is safely handled as plain text
        if proposal_content:
            proposal_content = str(proposal_content)
            proposal_content = "".join(
                char for char in proposal_content if ord(char) >= 32 or char in "\n\r\t"
            )
            proposal_content = proposal_content.replace("{", "{{").replace("}", "}}")

        # Initialize token usage tracking in state if not present
        if "token_usage" not in state:
            state["token_usage"] = {}

        # Get evaluation categories from config or use defaults
        evaluation_categories = state.get("evaluation_categories") or self.config.get(
            "evaluation_categories",
            [
                {
                    "name": "Core Context",
                    "weight": 0.25,
                    "description": """Evaluate against DAO mission and fundamental standards:

Key Considerations:
- Does this align with the DAO's core mission and values?
- Is the proposal clear and well-structured?
- Is it technically and practically feasible?
- Will it benefit the broader community?""",
                },
                {
                    "name": "Financial",
                    "weight": 0.25,
                    "description": """Evaluate financial aspects and resource allocation:

**Default Financial Context**: 
- If this proposal passes, it will automatically distribute 1000 tokens from the treasury to the proposer
- Beyond this default payout, evaluate any additional financial requests, promises, or money/crypto-related aspects mentioned in the proposal

Key Considerations:
- Are any additional funding requests beyond the 1000 tokens reasonable and well-justified?
- Are there any promises or commitments in the proposal that involve money, crypto, or treasury resources?
- What are the financial risks or implications of the proposal?
- Does the proposal represent good value for the default 1000 token investment?""",
                },
                {
                    "name": "Historical Context",
                    "weight": 0.25,
                    "description": """Evaluate against DAO historical context and past decisions:

The DAO has a 1000 token payout limit per proposal, and submitters might try to game this by splitting large requests across multiple proposals.

Key Red Flags:
- Exact duplicates of previous proposals
- Similar requesters, recipients, or incremental funding for the same project
- Proposals that contradict previous decisions
- Suspicious sequence patterns attempting to game token limits""",
                },
                {
                    "name": "Social Context",
                    "weight": 0.25,
                    "description": """Evaluate social and community aspects:

Key Considerations:
- Will this proposal benefit the broader community or just a few members?
- Is there likely community support or opposition?
- Does it foster inclusivity and participation?
- Does it align with the community's values and interests?
- Could it cause controversy or division?
- Does it consider the needs of diverse stakeholders?""",
                },
            ],
        )

        # Get DAO mission from database using dao_id
        dao_mission_text = self.config.get("dao_mission", "")
        if not dao_mission_text and dao_id:
            try:
                self.logger.debug(
                    f"[DEBUG:ComprehensiveEvaluator:{proposal_id}] Attempting to retrieve DAO mission from database for dao_id: {dao_id}"
                )
                dao = backend.get_dao(dao_id)
                if dao and dao.mission:
                    dao_mission_text = dao.mission
                    self.logger.debug(
                        f"[DEBUG:ComprehensiveEvaluator:{proposal_id}] Retrieved DAO mission: {dao_mission_text[:100]}..."
                    )
                else:
                    self.logger.warning(
                        f"[DEBUG:ComprehensiveEvaluator:{proposal_id}] No DAO found or no mission field for dao_id: {dao_id}"
                    )
                    dao_mission_text = "Elevate human potential through AI on Bitcoin"
            except Exception as e:
                self.logger.error(
                    f"[DEBUG:ComprehensiveEvaluator:{proposal_id}] Error retrieving DAO from database: {str(e)}"
                )
                dao_mission_text = "Elevate human potential through AI on Bitcoin"

        # Fallback to default mission if still empty
        if not dao_mission_text:
            dao_mission_text = "Elevate human potential through AI on Bitcoin"

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

        # Retrieve all proposals for this DAO from Supabase (excluding current proposal)
        dao_proposals = []
        past_proposals_db_text = ""
        try:
            if dao_id:
                dao_proposals = await self._fetch_dao_proposals(
                    dao_id, exclude_proposal_id=proposal_id
                )
                past_proposals_db_text = self._format_proposals_for_context(
                    dao_proposals
                )
        except Exception as e:
            self.logger.error(
                f"[DEBUG:ComprehensiveEvaluator:{proposal_id}] Error fetching/formatting DAO proposals: {str(e)}"
            )
            past_proposals_db_text = (
                "<no_proposals>No past proposals available due to error.</no_proposals>"
            )

        # Retrieve similar past proposals from vector store if possible
        past_proposals_vector_text = ""
        try:
            self.logger.debug(
                f"[DEBUG:ComprehensiveEvaluator:{proposal_id}] Retrieving similar past proposals from vector store"
            )
            similar_proposals = await self.retrieve_from_vector_store(
                query=proposal_content[
                    :1000
                ],  # Use first 1000 chars of proposal as query
                collection_name=self.config.get(
                    "proposals_collection", "past_proposals"
                ),
                limit=3,
            )
            past_proposals_vector_text = "\n\n".join(
                [
                    f'<similar_proposal id="{i + 1}">\n{doc.page_content}\n</similar_proposal>'
                    for i, doc in enumerate(similar_proposals)
                ]
            )
        except Exception as e:
            self.logger.error(
                f"[DEBUG:ComprehensiveEvaluator:{proposal_id}] Error retrieving similar proposals from vector store: {str(e)}"
            )
            past_proposals_vector_text = "<no_similar_proposals>No similar past proposals available in vector store.</no_similar_proposals>"

        # Combine both sources of past proposals
        past_proposals_text = past_proposals_db_text
        if past_proposals_vector_text:
            past_proposals_text += (
                "\n\n" + past_proposals_vector_text
                if past_proposals_text
                else past_proposals_vector_text
            )

        # Get proposal images
        proposal_images = state.get("proposal_images", [])

        try:
            # Create chat messages or get custom prompt template
            messages_or_template = self._create_chat_messages(
                proposal_content=proposal_content,
                dao_mission=dao_mission_text,
                community_info=community_info,
                past_proposals=past_proposals_text
                or "<no_proposals>No past proposals available for comparison.</no_proposals>",
                evaluation_categories=evaluation_categories,
                proposal_images=proposal_images,
                dao_id=dao_id,
                agent_id=agent_id,
                profile_id=profile_id,
                custom_system_prompt=custom_system_prompt,
                custom_user_prompt=custom_user_prompt,
            )

            # Handle both cases: list of messages or ChatPromptTemplate
            if isinstance(messages_or_template, ChatPromptTemplate):
                # Custom prompt injection returned a ChatPromptTemplate
                prompt = messages_or_template
                formatted_prompt = prompt.format()
            else:
                # Default case: list of messages
                prompt = ChatPromptTemplate.from_messages(messages_or_template)
                formatted_prompt = prompt.format()

            # Get structured output from the LLM
            result = await self.llm.with_structured_output(
                ComprehensiveEvaluationOutput
            ).ainvoke(formatted_prompt)

            # Track token usage
            token_usage_data = self.track_token_usage(str(formatted_prompt), result)
            state["token_usage"]["comprehensive_evaluator"] = token_usage_data

            # Update state with comprehensive result for backward compatibility
            # Create backward compatibility fields for legacy code
            if result.categories:
                for category_result in result.categories:
                    category_name = category_result.category
                    category_key = category_name.lower().replace(" ", "_")

                    # Update individual score fields for compatibility
                    state[f"{category_key}_score"] = {"score": category_result.score}

                    # Update summaries
                    if "summaries" not in state:
                        state["summaries"] = {}
                    state["summaries"][f"{category_key}_score"] = " ".join(
                        category_result.reasoning
                    )

            # Set final score and decision
            state["final_score"] = {
                "score": result.final_score,
                "decision": result.decision,
                "explanation": result.explanation,
            }

            # Update flags
            state["flags"] = result.flags

            # Update workflow step
            state["workflow_step"] = "comprehensive_evaluation_complete"
            if "completed_steps" not in state:
                state["completed_steps"] = set()
            state["completed_steps"].add("comprehensive_evaluation")

            self.logger.info(
                f"[DEBUG:ComprehensiveEvaluator:{proposal_id}] Successfully completed comprehensive evaluation"
            )
            self.logger.info(
                f"[DEBUG:ComprehensiveEvaluator:{proposal_id}] Decision: {'Approve' if result.decision else 'Reject'}, Final Score: {result.final_score}"
            )

            # Return the typed model
            return ComprehensiveEvaluatorAgentProcessOutput(
                categories=result.categories,
                final_score=result.final_score,
                decision=result.decision,
                explanation=result.explanation,
                flags=result.flags,
                summary=result.summary,
                token_usage=token_usage_data,
                images_processed=len(proposal_images),
            )
        except Exception as e:
            self.logger.error(
                f"[DEBUG:ComprehensiveEvaluator:{proposal_id}] Error in comprehensive evaluation: {str(e)}"
            )
            return ComprehensiveEvaluatorAgentProcessOutput(
                categories=[
                    EvaluationCategory(
                        category=cat["name"],
                        score=50,
                        weight=cat["weight"],
                        reasoning=[f"Error: {str(e)}"],
                    )
                    for cat in evaluation_categories
                ],
                final_score=30,
                decision=False,
                explanation=f"Comprehensive evaluation failed due to error: {str(e)}",
                flags=[f"Critical Error: {str(e)}"],
                summary="Evaluation failed due to error",
                token_usage={},
                images_processed=len(proposal_images) if proposal_images else 0,
            )
