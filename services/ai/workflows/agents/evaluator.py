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
from services.ai.workflows.utils.models import ComprehensiveEvaluationOutput
from services.ai.workflows.utils.token_usage import TokenUsageMixin

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

        # Configuration for thresholds
        self.default_threshold = config.get("approval_threshold", 70)
        self.veto_threshold = config.get("veto_threshold", 30)
        self.consensus_threshold = config.get("consensus_threshold", 10)

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
        proposal_data: str,
        dao_mission: str,
        community_info: str,
        past_proposals: str,
        approval_threshold: int,
        proposal_images: List[Dict[str, Any]] = None,
        dao_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        profile_id: Optional[str] = None,
    ) -> List:
        """Create chat messages for comprehensive evaluation.

        Args:
            proposal_data: The proposal content to evaluate
            dao_mission: The DAO mission statement
            community_info: Information about the DAO community
            past_proposals: Formatted past proposals text
            approval_threshold: The approval threshold for decision making
            proposal_images: List of processed images
            dao_id: Optional DAO ID for custom prompt injection
            agent_id: Optional agent ID for custom prompt injection
            profile_id: Optional profile ID for custom prompt injection

        Returns:
            List of chat messages
        """
        # System message combining all evaluation guidelines
        system_content = f"""You are a comprehensive DAO governance evaluator with expertise across multiple domains: core context analysis, financial evaluation, historical analysis, social dynamics, and strategic reasoning. You will evaluate proposals across all these dimensions in a single comprehensive assessment.

You must plan extensively before each evaluation and reflect thoroughly on all aspects. Consider the proposal holistically while providing detailed analysis for each evaluation dimension.

**Image Evaluation**: If images are attached to this proposal, they are an integral part of the proposal content. You must carefully examine and evaluate any provided images across ALL evaluation dimensions, considering how they support, clarify, or relate to the written proposal. Images may contain diagrams, charts, financial projections, community plans, historical comparisons, mockups, or other visual information that is essential to understanding the full scope and merit of the proposal. Include your analysis of the visual content in ALL relevant evaluation sections.

**EVALUATION FRAMEWORK**

**1. CORE CONTEXT EVALUATION (25% of final decision weight)**
Evaluate against DAO mission and fundamental standards:

Evaluation Criteria (weighted within core):
- Alignment with DAO mission (40% weight)
- Clarity of proposal (20% weight) 
- Feasibility and practicality (20% weight)
- Community benefit (20% weight)

Key Considerations:
- Does this align with the DAO's core mission and values?
- Is the proposal clear and well-structured?
- Is it technically and practically feasible?
- Will it benefit the broader community?

**2. FINANCIAL EVALUATION (25% of final decision weight)**
Evaluate financial aspects and resource allocation:

**Default Financial Context**: 
- If this proposal passes, it will automatically distribute 1000 tokens from the treasury to the proposer
- Beyond this default payout, evaluate any additional financial requests, promises, or money/crypto-related aspects mentioned in the proposal

Evaluation Criteria (weighted within financial):
- Cost-effectiveness and value for money (40% weight)
- Reasonableness of any additional funding requests (25% weight)
- Financial feasibility of promises or commitments (20% weight)
- Overall financial risk assessment (15% weight)

Key Considerations:
- Are any additional funding requests beyond the 1000 tokens reasonable and well-justified?
- Are there any promises or commitments in the proposal that involve money, crypto, or treasury resources?
- What are the financial risks or implications of the proposal?
- Does the proposal represent good value for the default 1000 token investment?
- Are there any hidden financial commitments or ongoing costs?

**3. HISTORICAL CONTEXT EVALUATION (25% of final decision weight)**
Evaluate against DAO historical context and past decisions:

The DAO has a 1000 token payout limit per proposal, and submitters might try to game this by splitting large requests across multiple proposals.

Evaluation Criteria (weighted within historical):
- Is it a duplicate of past proposals? (25% weight)
- Has it addressed issues raised in similar past proposals? (20% weight)
- Shows consistency with past approved proposals? (25% weight)
- Is potentially part of a sequence to exceed limits? (30% weight)

Key Red Flags:
- Exact duplicates of previous proposals
- Similar requesters, recipients, or incremental funding for the same project
- Proposals that contradict previous decisions
- Suspicious sequence patterns attempting to game token limits

**4. SOCIAL CONTEXT EVALUATION (25% of final decision weight)**
Evaluate social and community aspects:

Evaluation Criteria (weighted within social):
- Community benefit and inclusion (40% weight)
- Alignment with community values and interests (30% weight)
- Potential for community engagement (20% weight)
- Consideration of diverse stakeholders (10% weight)

Key Considerations:
- Will this proposal benefit the broader community or just a few members?
- Is there likely community support or opposition?
- Does it foster inclusivity and participation?
- Does it align with the community's values and interests?
- Could it cause controversy or division?
- Does it consider the needs of diverse stakeholders?

**SCORING METHODOLOGY**

For each evaluation dimension, provide scores from 0-100:
- 0-20: Critical issues, not aligned, or harmful
- 21-50: Significant issues or missing details
- 51-70: Adequate but with some concerns or minor risks
- 71-90: Good quality, aligned, and beneficial
- 91-100: Excellent quality, highly aligned, and valuable

**FINAL DECISION FRAMEWORK**

The approval threshold is {approval_threshold}/100.

Final Decision Process:
1. Calculate weighted average of all four dimension scores
2. Assess critical flags that might override the score
3. Determine confidence level based on consensus and evidence quality
4. Make approve/reject decision with comprehensive reasoning

Approval Criteria:
- **Strong Approve** (Score 80+): Clear benefits, minimal risks, strong consensus across dimensions
- **Conditional Approve** (Score 60-79): Net positive with manageable risks or some uncertainty
- **Neutral** (Score 40-59): Unclear net benefit, significant uncertainty, or balanced trade-offs
- **Conditional Reject** (Score 20-39): Net negative or high risk with limited upside
- **Strong Reject** (Score 0-19): Clear harm, fundamental flaws, or critical risks

Veto Conditions (automatic rejection regardless of score):
- Any dimension score below 30 suggests critical issues
- Multiple critical flags indicating legal, security, or ethical violations
- Fundamental misalignment with DAO values or objectives
- Evidence of fraud, manipulation, or malicious intent

**CONFIDENCE ASSESSMENT**

Provide confidence score (0.0-1.0) based on:
- **High Confidence (0.7-1.0)**: Strong consensus across dimensions, clear evidence, minimal uncertainty
- **Medium Confidence (0.4-0.69)**: Some disagreement between dimensions, moderate uncertainty
- **Low Confidence (0.0-0.39)**: High disagreement, significant uncertainty, conflicting evidence

**OUTPUT REQUIREMENTS**

You must provide detailed analysis for each dimension and comprehensive final reasoning. Your response should demonstrate thorough consideration of all evaluation aspects while synthesizing them into a coherent final decision.

Return a JSON object with ALL required fields populated with substantive content."""

        # User message with all context and evaluation request
        user_content = f"""Please conduct a comprehensive evaluation of the following proposal across all dimensions:

**PROPOSAL TO EVALUATE:**
{proposal_data}

**DAO MISSION:**
{dao_mission}

**COMMUNITY INFORMATION:**
{community_info}

**HISTORICAL CONTEXT - PAST DAO PROPOSALS:**
{past_proposals}

**EVALUATION INSTRUCTIONS:**
Analyze this proposal thoroughly across all four evaluation dimensions (Core Context, Financial, Historical Context, Social Context) and provide your comprehensive assessment. Ensure each dimension receives detailed analysis and scoring, then synthesize your findings into a final decision with high-quality reasoning.

Consider all provided context, examine any attached images carefully, and provide substantive analysis that demonstrates deep consideration of the proposal's merits and risks across all evaluation areas."""

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

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process the proposal with comprehensive evaluation.

        Args:
            state: The current workflow state

        Returns:
            Dictionary containing comprehensive evaluation results
        """
        self._initialize_vector_capability()
        proposal_id = state.get("proposal_id", "unknown")
        proposal_content = state.get("proposal_data", "")
        dao_id = state.get("dao_id")
        agent_id = state.get("agent_id")
        profile_id = state.get("profile_id")

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
                proposal_data=proposal_content,
                dao_mission=dao_mission_text,
                community_info=community_info,
                past_proposals=past_proposals_text
                or "<no_proposals>No past proposals available for comparison.</no_proposals>",
                approval_threshold=self.default_threshold,
                proposal_images=proposal_images,
                dao_id=dao_id,
                agent_id=agent_id,
                profile_id=profile_id,
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
            result_dict = result.model_dump()

            # Track token usage
            token_usage_data = self.track_token_usage(str(formatted_prompt), result)
            state["token_usage"]["comprehensive_evaluator"] = token_usage_data
            result_dict["token_usage"] = token_usage_data
            result_dict["images_processed"] = len(proposal_images)

            # Update state with comprehensive result
            # Update individual score fields for compatibility
            state["core_score"] = {"score": result_dict["core_score"]}
            state["financial_score"] = {"score": result_dict["financial_score"]}
            state["historical_score"] = {"score": result_dict["historical_score"]}
            state["social_score"] = {"score": result_dict["social_score"]}
            state["final_score"] = {
                "score": result_dict["final_score"],
                "decision": result_dict["decision"],
                "confidence": result_dict["confidence"],
                "explanation": result_dict["explanation"],
            }

            # Update summaries
            if "summaries" not in state:
                state["summaries"] = {}
            state["summaries"]["core_score"] = result_dict["core_summary"]
            state["summaries"]["financial_score"] = result_dict["financial_summary"]
            state["summaries"]["historical_score"] = result_dict["historical_summary"]
            state["summaries"]["social_score"] = result_dict["social_summary"]

            # Update flags
            state["flags"] = result_dict["all_flags"]

            # Update workflow step
            state["workflow_step"] = "comprehensive_evaluation_complete"
            if "completed_steps" not in state:
                state["completed_steps"] = set()
            state["completed_steps"].add("comprehensive_evaluation")

            self.logger.info(
                f"[DEBUG:ComprehensiveEvaluator:{proposal_id}] Successfully completed comprehensive evaluation"
            )
            self.logger.info(
                f"[DEBUG:ComprehensiveEvaluator:{proposal_id}] Decision: {result_dict.get('decision')}, Final Score: {result_dict.get('final_score')}"
            )

            return result_dict
        except Exception as e:
            self.logger.error(
                f"[DEBUG:ComprehensiveEvaluator:{proposal_id}] Error in comprehensive evaluation: {str(e)}"
            )
            return {
                "core_score": 50,
                "core_flags": [f"Error: {str(e)}"],
                "core_summary": "Core evaluation failed due to error",
                "financial_score": 50,
                "financial_flags": [f"Error: {str(e)}"],
                "financial_summary": "Financial evaluation failed due to error",
                "historical_score": 50,
                "historical_flags": [f"Error: {str(e)}"],
                "historical_summary": "Historical evaluation failed due to error",
                "sequence_analysis": "Could not analyze proposal sequences due to error.",
                "social_score": 50,
                "social_flags": [f"Error: {str(e)}"],
                "social_summary": "Social evaluation failed due to error",
                "final_score": 50,
                "decision": "Reject",
                "confidence": 0.0,
                "explanation": f"Comprehensive evaluation failed due to error: {str(e)}",
                "all_flags": [f"Critical Error: {str(e)}"],
                "images_processed": len(proposal_images) if proposal_images else 0,
            }
