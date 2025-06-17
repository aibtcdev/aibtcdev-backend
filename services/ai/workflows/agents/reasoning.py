import asyncio
from typing import Any, Dict, Optional

from langchain_core.prompts.chat import ChatPromptTemplate
from langgraph.graph import StateGraph

from lib.logger import configure_logger
from services.ai.workflows.utils.model_factory import (
    create_chat_openai,
    create_reasoning_llm,
)
from services.ai.workflows.chat import StreamingCallbackHandler
from services.ai.workflows.mixins.capability_mixins import (
    BaseCapabilityMixin,
    PromptCapability,
)
from services.ai.workflows.mixins.planning_mixin import PlanningCapability
from services.ai.workflows.utils.models import FinalOutput
from services.ai.workflows.utils.state_reducers import update_state_with_agent_result
from services.ai.workflows.utils.token_usage import TokenUsageMixin

logger = configure_logger(__name__)


class ReasoningAgent(
    BaseCapabilityMixin, PlanningCapability, TokenUsageMixin, PromptCapability
):
    """Reasoning Agent that makes the final evaluation decision based on other agents' inputs."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Reasoning Agent.

        Args:
            config: Optional configuration dictionary
        """
        BaseCapabilityMixin.__init__(self, config=config, state_key="final_score")
        TokenUsageMixin.__init__(self)
        PromptCapability.__init__(self)

        # Create a dummy queue for the StreamingCallbackHandler
        self.dummy_queue = asyncio.Queue()
        # Create callback handler and planning_llm for PlanningCapability
        # These won't be used since we don't actually use the planning functionality
        self.dummy_callback = StreamingCallbackHandler(queue=self.dummy_queue)
        self.dummy_llm = create_chat_openai()

        # Pass the required arguments to PlanningCapability.__init__
        PlanningCapability.__init__(
            self, callback_handler=self.dummy_callback, planning_llm=self.dummy_llm
        )

        self.initialize()
        self._initialize_planning_capability()

        # Configuration for thresholds
        self.default_threshold = config.get("approval_threshold", 70)
        self.veto_threshold = config.get("veto_threshold", 30)
        self.consensus_threshold = config.get("consensus_threshold", 10)
        self.confidence_adjustment = config.get("confidence_adjustment", 0.15)
        self.llm = create_reasoning_llm()  # Uses o3-mini by default for reasoning

    def _initialize_planning_capability(self):
        """Initialize the planning capability if not already initialized."""
        if not hasattr(self, "planning"):
            # We don't actually use the planning method, just create a dummy placeholder
            self.planning = lambda *args, **kwargs: None
            self.logger.info("Initialized dummy planning capability for ReasoningAgent")

    def integrate_with_graph(self, graph: StateGraph, **kwargs) -> None:
        """Hook to integrate with a particular graph."""
        pass

    def _create_chat_messages(
        self,
        agent_evaluations: str,
        approval_threshold: int,
        dao_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        profile_id: Optional[str] = None,
    ) -> list:
        """Create chat messages for reasoning evaluation.

        Args:
            agent_evaluations: Formatted string of all agent evaluations
            approval_threshold: The approval threshold for decision making
            dao_id: Optional DAO ID for custom prompt injection
            agent_id: Optional agent ID for custom prompt injection
            profile_id: Optional profile ID for custom prompt injection

        Returns:
            List of chat messages
        """
        # System message with evaluation guidelines
        system_content = (
            """<system>
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
<reasoning_evaluation>
  
  <analytical_framework>
    <step_1_individual_analysis>
      For each agent evaluation:
      - Assess the quality and depth of the reasoning provided
      - Identify specific evidence cited or lack thereof
      - Evaluate if the score aligns with the reasoning given
      - Note any potential biases or blind spots in the analysis
      - Consider the agent's domain expertise relevance to this proposal
    </step_1_individual_analysis>
    
    <step_2_cross_agent_analysis>
      - Identify areas where agents agree and disagree
      - Look for complementary insights that reinforce each other
      - Spot contradictory findings that need resolution
      - Assess if disagreements stem from different perspectives or actual conflicts
      - Determine which agent insights are most reliable for this specific proposal type
    </step_2_cross_agent_analysis>
    
    <step_3_pattern_recognition>
      - Analyze score distribution patterns (consensus, polarization, outliers)
      - Identify common themes across agent summaries
      - Look for correlation between different evaluation dimensions
      - Assess if the proposal has consistent strengths/weaknesses across domains
      - Consider if any single dimension should be weighted more heavily
    </step_3_pattern_recognition>
    
    <step_4_flag_assessment>
      - Categorize flags by severity (critical, moderate, minor)
      - Assess if flags are substantiated by agent reasoning
      - Determine if flags represent deal-breakers or manageable risks
      - Consider if multiple minor flags compound into major concerns
      - Evaluate if any flags contradict positive agent assessments
    </step_4_flag_assessment>
    
    <step_5_contextual_weighting>
      - Consider the proposal type and what dimensions matter most
      - Assess if certain agent perspectives are more relevant than others
      - Weigh immediate vs. long-term implications highlighted by agents
      - Consider the DAO's specific context and priorities
      - Factor in any time-sensitive or strategic considerations mentioned
    </step_5_contextual_weighting>
  </analytical_framework>
  
      <decision_guidelines>
    <threshold>The default threshold for approval is """
            + str(approval_threshold)
            + """/100</threshold>
    
    <scoring_principles>
      - Scores should reflect the overall risk-adjusted potential of the proposal
      - Higher scores require strong positive evidence from multiple dimensions
      - Lower scores should be justified by significant risks or poor reasoning
      - Consider both the ceiling (best case) and floor (worst case) outcomes
    </scoring_principles>
    
    <approval_criteria>
      <strong_approve>Score 80+: Clear benefits, minimal risks, strong consensus</strong_approve>
      <conditional_approve>Score 60-79: Net positive with manageable risks or some uncertainty</conditional_approve>
      <neutral>Score 40-59: Unclear net benefit, significant uncertainty, or balanced trade-offs</neutral>
      <conditional_reject>Score 20-39: Net negative or high risk with limited upside</conditional_reject>
      <strong_reject>Score 0-19: Clear harm, fundamental flaws, or critical risks</strong_reject>
    </approval_criteria>
    
    <veto_conditions>
      - Any agent score below 30 suggests critical issues requiring explanation
      - Multiple flags indicating legal, security, or ethical violations
      - Fundamental misalignment with DAO values or objectives
      - Evidence of fraud, manipulation, or malicious intent
    </veto_conditions>
    
    <scoring_methodology>
      You must provide a final overall score (0-100) that directly maps to the approval decision:
      
      <score_calculation>
        - Start with the weighted average of reliable agent scores
        - Adjust based on flag severity and cross-agent insights
        - Apply contextual weighting based on proposal type and DAO priorities
        - Ensure the final score accurately reflects the proposal's overall merit
      </score_calculation>
      
      <score_adjustment_factors>
        - Strong consensus among agents (minimal adjustments needed)
        - Detailed, evidence-based reasoning from multiple agents (higher confidence in scores)
        - Clear alignment between different evaluation dimensions (scores are reliable)
        - Conflicting evidence or contradictory assessments (may require score adjustments)
        - Critical flags or red flags (may require significant score reductions)
        - Missing critical information (may require score reductions due to uncertainty)
      </score_adjustment_factors>
      
      <threshold_alignment>
        The approval threshold is 70/100. Ensure your final score reflects:
        - Score 70-100: APPROVE - Proposal meets or exceeds the approval threshold
        - Score 0-69: REJECT - Proposal falls below the approval threshold
      </threshold_alignment>
    </scoring_methodology>
  </decision_guidelines>
  
  <reasoning_process>
    <analysis>
      1. **Individual Agent Assessment**: Evaluate each agent's reasoning quality and reliability
      2. **Cross-Agent Synthesis**: Identify patterns, agreements, and meaningful disagreements
      3. **Risk-Benefit Analysis**: Weigh potential upsides against identified risks and concerns
      4. **Contextual Evaluation**: Consider DAO-specific factors and proposal relevance
      5. **Confidence Assessment**: Determine how certain you are about your evaluation based on the factors above
    </analysis>
    
    <decision_logic>
      - Start with the weighted average of reliable agent scores
      - Adjust based on flag severity and cross-agent insights
      - Consider confidence level in final score precision
      - Ensure decision threshold accounts for uncertainty
      - Provide specific, actionable reasoning for stakeholders
    </decision_logic>
  </reasoning_process>
  
  <output_requirements>
    <score>
      - Provide a final overall score from 0-100
      - Justify how you arrived at this specific score
      - Explain any adjustments made to the base average
      - Ensure the score accurately reflects the proposal's merit relative to the 70-point threshold
    </score>
    
    <decision>
      - State clearly "Approve" or "Reject"
      - Ensure decision aligns with score and 70-point threshold
      - Score 70+ = Approve, Score <70 = Reject
    </decision>
    
    <explanation>
      Your explanation should be comprehensive and structured, providing stakeholders with a complete understanding of your reasoning process. Include the following elements in a detailed narrative:

      **Agent Analysis Summary (200-300 words)**:
      - Provide a detailed assessment of each agent's evaluation quality and key insights
      - Explain which agent perspectives were most valuable and why
      - Identify any agent evaluations that were particularly strong or weak in their reasoning
      - Discuss how different agent specializations contributed to the overall assessment
      - Note any gaps in agent coverage or areas where more analysis would be beneficial

      **Cross-Agent Synthesis (150-250 words)**:
      - Analyze patterns of agreement and disagreement between agents
      - Explain whether disagreements represent different valid perspectives or actual conflicts
      - Discuss how complementary insights from different agents reinforced or contradicted each other
      - Identify which agent insights proved most reliable for this specific proposal type
      - Address any surprising correlations or lack thereof between evaluation dimensions

      **Risk-Benefit Analysis (200-300 words)**:
      - Provide a detailed breakdown of identified benefits and their likelihood/magnitude
      - Thoroughly assess risks, their probability, and potential impact
      - Explain your risk tolerance assessment for this particular proposal
      - Discuss both short-term and long-term implications highlighted by the agents
      - Address any trade-offs between different benefits or between benefits and risks

      **Flag Impact Assessment (100-200 words)**:
      - Categorize each flag by severity and explain your reasoning
      - Discuss whether flags represent deal-breakers, manageable risks, or minor concerns
      - Explain how multiple flags might compound or offset each other
      - Address any contradictions between positive agent assessments and negative flags
      - Provide context on whether flags are unusual for this type of proposal

      **Decision Rationale (150-250 words)**:
      - Explain your specific scoring methodology and how you arrived at the final number
      - Justify any significant adjustments made to the simple average of agent scores
      - Discuss how the score translates to your approve/reject decision relative to the 70-point threshold
      - Address whether this is a clear-cut decision or a borderline case
      - Explain how uncertainty and disagreement between agents were factored into the final score

      **Score Justification (100-150 words)**:
      - Provide specific reasoning for your final score
      - Identify the main factors that influenced your scoring decision
      - Discuss what additional information might have changed the score
      - Explain how disagreement between agents affected your scoring
      - Address whether the proposal type or complexity contributed to scoring challenges

      **Contextual Considerations (100-200 words)**:
      - Discuss any DAO-specific factors that influenced your assessment
      - Address timing considerations or strategic implications mentioned by agents
      - Explain how this proposal fits within the broader context of DAO objectives
      - Consider resource allocation implications and opportunity costs
      - Address any precedent-setting aspects of this decision

      **Actionable Recommendations (if applicable, 100-200 words)**:
      - For rejected proposals: Provide specific, actionable feedback for improvement
      - For approved proposals: Highlight key success factors to monitor during implementation
      - Suggest risk mitigation strategies based on identified concerns
      - Recommend additional due diligence or safeguards if needed
      - Propose metrics or milestones for tracking proposal success

      **Final Summary (50-100 words)**:
      - Conclude with a clear, concise statement of your decision and primary reasoning
      - Highlight the 2-3 most critical factors that drove your decision
      - Provide a forward-looking statement about expected outcomes

      The total explanation should be comprehensive (approximately 1000-1500 words) and demonstrate thorough consideration of all available information while remaining clear and actionable for stakeholders.
    </explanation>
  </output_requirements>
  
  <final_instruction>
    Think step-by-step through this analytical framework. Don't just average scores - synthesize insights, weigh evidence quality, and provide a thoughtful evaluation that helps stakeholders understand both the decision and the reasoning behind it. Your analysis should demonstrate deep consideration of all available information.
    
    Ensure your final score accurately reflects the proposal's merit and aligns with the 70-point approval threshold. Score 70 or above means approval, below 70 means rejection.
    
    Return only a JSON object with exactly these three fields: score, decision, and explanation.
  </final_instruction>
</reasoning_evaluation>"""
        )

        # User message with evaluation request
        user_content = f"""Please evaluate the following agent assessments and make your final decision:

<agent_evaluations>
{agent_evaluations}
</agent_evaluations>

Based on the analytical framework and decision guidelines provided in the system instructions, please provide your comprehensive evaluation."""

        # Apply custom prompt injection if enabled
        if dao_id or agent_id or profile_id:
            try:
                custom_prompt_template = self.create_chat_prompt_with_custom_injection(
                    default_system_message=system_content,
                    default_user_message=user_content,
                    dao_id=dao_id,
                    agent_id=agent_id,
                    profile_id=profile_id,
                    prompt_type="reasoning_evaluation",
                )
                # Return the ChatPromptTemplate directly - it will be handled in the process method
                return custom_prompt_template
            except Exception as e:
                self.logger.warning(
                    f"Custom prompt injection failed, using default: {e}"
                )

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]

        return messages

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process all agent scores and make a final decision.

        Args:
            state: The current workflow state with all agent results

        Returns:
            Dictionary containing the final evaluation decision
        """
        self._initialize_planning_capability()
        proposal_id = state.get("proposal_id", "unknown")
        dao_id = state.get("dao_id")
        agent_id = state.get("agent_id")
        profile_id = state.get("profile_id")

        # Add diagnostic logging
        self.logger.info(
            f"[DEBUG:ReasoningAgent:{proposal_id}] Starting reasoning agent process"
        )
        self.logger.info(
            f"[DEBUG:ReasoningAgent:{proposal_id}] State keys: {list(state.keys())}"
        )

        # Initialize token usage tracking in state if not present
        if "token_usage" not in state:
            state["token_usage"] = {}

        # Helper function to safely get scores
        def safe_get_score(value, default=0):
            if isinstance(value, dict) and "score" in value:
                return value["score"]
            return default

        # Get individual scores
        core_score = safe_get_score(state.get("core_score"), 0)
        historical_score = safe_get_score(state.get("historical_score"), 0)
        financial_score = safe_get_score(state.get("financial_score"), 0)
        social_score = safe_get_score(state.get("social_score"), 0)

        # Get agent summaries
        core_summary = state.get("summaries", {}).get(
            "core_score", "No core context evaluation available."
        )
        historical_summary = state.get("summaries", {}).get(
            "historical_score", "No historical context evaluation available."
        )
        financial_summary = state.get("summaries", {}).get(
            "financial_score", "No financial evaluation available."
        )
        social_summary = state.get("summaries", {}).get(
            "social_score", "No social context evaluation available."
        )

        # Get flags
        flags = state.get("flags", [])
        flags_text = (
            "\n".join([f"- {flag}" for flag in flags])
            if flags
            else "No flags identified."
        )

        # Calculate score statistics
        scores = [
            ("Core", core_score),
            ("Historical", historical_score),
            ("Financial", financial_score),
            ("Social", social_score),
        ]
        valid_scores = [score for _, score in scores if score > 0]

        if not valid_scores:
            self.logger.error(
                f"[DEBUG:ReasoningAgent:{proposal_id}] No valid scores found!"
            )
            return {
                "score": 0,
                "decision": "Reject",
                "confidence": 0.0,
                "explanation": "Unable to evaluate due to missing agent scores.",
                "flags": ["Critical: No valid evaluation scores available."],
            }

        # Calculate metrics
        avg_score = sum(valid_scores) / len(valid_scores)
        min_score = min(valid_scores)
        max_score = max(valid_scores)
        score_range = max_score - min_score

        # Detect if any agent has a veto-level score
        has_veto = any(score <= self.veto_threshold for score in valid_scores)

        # Check for consensus or disagreement
        has_consensus = score_range <= self.consensus_threshold
        has_disagreement = score_range >= 30

        # Format agent evaluations for prompt
        agent_evaluations = f"""
Core Context Evaluation:
Score: {core_score}/100
Summary: {core_summary}

Historical Context Evaluation:
Score: {historical_score}/100
Summary: {historical_summary}

Financial Evaluation:
Score: {financial_score}/100
Summary: {financial_summary}

Social Context Evaluation:
Score: {social_score}/100
Summary: {social_summary}

Flags Identified:
{flags_text}

Score Statistics:
- Average Score: {avg_score:.2f}
- Minimum Score: {min_score}
- Maximum Score: {max_score}
- Score Range: {score_range}
"""

        try:
            # Create chat messages or get custom prompt template
            messages_or_template = self._create_chat_messages(
                agent_evaluations=agent_evaluations,
                approval_threshold=self.default_threshold,
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
            result = await self.llm.with_structured_output(FinalOutput).ainvoke(
                formatted_prompt
            )
            result_dict = result.model_dump()

            # Track token usage
            token_usage_data = self.track_token_usage(str(formatted_prompt), result)
            state["token_usage"]["reasoning_agent"] = token_usage_data
            result_dict["token_usage"] = token_usage_data

            # Add calculated metrics to result for transparency
            result_dict["metrics"] = {
                "avg_score": avg_score,
                "min_score": min_score,
                "max_score": max_score,
                "score_range": score_range,
                "has_veto": has_veto,
                "has_consensus": has_consensus,
                "has_disagreement": has_disagreement,
                "score_validity": len(valid_scores) / 4.0,
                "flag_count": len(flags),
                "agent_scores": {
                    "core": core_score,
                    "historical": historical_score,
                    "financial": financial_score,
                    "social": social_score,
                },
            }

            # Score and decision are now provided by the LLM in the structured output
            # The LLM ensures score aligns with the 70-point approval threshold

            # Add flags to the result
            result_dict["flags"] = flags

            # Update state with agent result
            update_state_with_agent_result(state, result_dict, "final")

            # Add final diagnostic logging
            self.logger.info(
                f"[DEBUG:ReasoningAgent:{proposal_id}] Successfully completed reasoning"
            )
            self.logger.info(
                f"[DEBUG:ReasoningAgent:{proposal_id}] Returning result with decision: {result_dict.get('decision')}"
            )
            self.logger.info(
                f"[DEBUG:ReasoningAgent:{proposal_id}] Updated state now has keys: {list(state.keys())}"
            )
            if "final_score" in state:
                self.logger.info(
                    f"[DEBUG:ReasoningAgent:{proposal_id}] final_score type: {type(state.get('final_score'))}"
                )

            return result_dict
        except Exception as e:
            self.logger.error(
                f"[DEBUG:ReasoningAgent:{proposal_id}] Error in reasoning: {str(e)}"
            )
            return {
                "score": 30,  # Below threshold, ensuring rejection
                "decision": "Reject",
                "explanation": f"Evaluation failed due to error: {str(e)}",
                "flags": [f"Error: {str(e)}"],
            }
