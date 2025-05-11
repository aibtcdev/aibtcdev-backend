import asyncio
from typing import Any, Dict, List, Optional

from langchain.prompts import PromptTemplate
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph
from pydantic import BaseModel, Field

from lib.logger import configure_logger
from services.workflows.capability_mixins import BaseCapabilityMixin
from services.workflows.chat import StreamingCallbackHandler
from services.workflows.planning_mixin import PlanningCapability
from services.workflows.utils.models import FinalOutput
from services.workflows.utils.state_reducers import update_state_with_agent_result
from services.workflows.utils.token_usage import TokenUsageMixin

logger = configure_logger(__name__)


class FinalOutput(BaseModel):
    """Schema for final decision output."""

    score: int = Field(..., description="Final score between 0-100")
    decision: str = Field(..., description="Approve or Reject")
    explanation: str = Field(..., description="Reasoning for the decision")


class ReasoningAgent(BaseCapabilityMixin, PlanningCapability, TokenUsageMixin):
    """Reasoning Agent that makes the final evaluation decision based on other agents' inputs."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Reasoning Agent.

        Args:
            config: Optional configuration dictionary
        """
        BaseCapabilityMixin.__init__(self, config=config, state_key="final_score")
        TokenUsageMixin.__init__(self)

        # Create a dummy queue for the StreamingCallbackHandler
        self.dummy_queue = asyncio.Queue()
        # Create callback handler and planning_llm for PlanningCapability
        # These won't be used since we don't actually use the planning functionality
        self.dummy_callback = StreamingCallbackHandler(queue=self.dummy_queue)
        self.dummy_llm = ChatOpenAI()

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

    def _initialize_planning_capability(self):
        """Initialize the planning capability if not already initialized."""
        if not hasattr(self, "planning"):
            # We don't actually use the planning method, just create a dummy placeholder
            self.planning = lambda *args, **kwargs: None
            self.logger.info("Initialized dummy planning capability for ReasoningAgent")

    def integrate_with_graph(self, graph: StateGraph, **kwargs) -> None:
        """Hook to integrate with a particular graph."""
        pass

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process all agent scores and make a final decision.

        Args:
            state: The current workflow state with all agent results

        Returns:
            Dictionary containing the final evaluation decision
        """
        self._initialize_planning_capability()
        proposal_id = state.get("proposal_id", "unknown")

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

        prompt = PromptTemplate(
            input_variables=["agent_evaluations", "approval_threshold"],
            template="""Analyze the specialized agent evaluations and make a final decision on this proposal.

# Agent Evaluations
{agent_evaluations}

# Decision Guidelines
- The default threshold for approval is {approval_threshold}/100
- A proposal with any agent score below 30 should typically be rejected
- A proposal with high consensus (small range between scores) increases confidence
- A proposal with high disagreement (large range between scores) decreases confidence
- Consider the reasoning behind each agent's score, not just the numerical value
- Critical flags should be weighted heavily in your decision

# Task
1. Analyze the evaluations from all agents
2. Consider the significance of any critical flags
3. Weigh the relative importance of different evaluation dimensions
4. Make a final decision (Approve or Reject) with a final score
5. Provide clear reasoning for your decision

# Output Format
Your response should be a JSON object with:
- score: A final score from 0-100
- decision: Either "Approve" or "Reject"
- explanation: Your reasoning for the decision

Return only the JSON object with these three fields.""",
        )

        try:
            formatted_prompt_text = prompt.format(
                agent_evaluations=agent_evaluations,
                approval_threshold=self.default_threshold,
            )

            llm_input_message = HumanMessage(content=formatted_prompt_text)

            # Get structured output from the LLM
            result = await self.llm.with_structured_output(FinalOutput).ainvoke(
                [llm_input_message]
            )
            result_dict = result.model_dump()

            # Track token usage
            token_usage_data = self.track_token_usage(formatted_prompt_text, result)
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
            }

            # Calculate confidence based on consensus/disagreement
            confidence = 0.7  # Base confidence
            if has_consensus:
                confidence += self.confidence_adjustment
            if has_disagreement:
                confidence -= self.confidence_adjustment
            if has_veto:
                confidence -= 0.3

            result_dict["confidence"] = max(
                0.1, min(1.0, confidence)
            )  # Clamp to [0.1, 1.0]

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
                "score": 50,
                "decision": "Reject",
                "explanation": f"Evaluation failed due to error: {str(e)}",
                "flags": [f"Error: {str(e)}"],
            }
