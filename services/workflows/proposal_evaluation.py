import asyncio
import operator
import uuid
from typing import Annotated, Any, Dict, List, Optional, TypedDict, Union

from langchain.prompts import PromptTemplate
from langgraph.graph import END, StateGraph

from backend.factory import backend
from backend.models import UUID, Profile
from lib.logger import configure_logger
from services.workflows.agents.core_context import CoreContextAgent
from services.workflows.agents.financial_context import FinancialContextAgent
from services.workflows.agents.historical_context import HistoricalContextAgent
from services.workflows.agents.image_processing import ImageProcessingNode
from services.workflows.agents.reasoning import ReasoningAgent
from services.workflows.agents.social_context import SocialContextAgent
from services.workflows.base import BaseWorkflow
from services.workflows.hierarchical_workflows import (
    HierarchicalTeamWorkflow,
    append_list_fn,
)
from services.workflows.utils.state_reducers import (
    merge_dicts,
    no_update_reducer,
    set_once,
)
from tools.dao_ext_action_proposals import VoteOnActionProposalTool
from tools.tools_factory import filter_tools_by_names, initialize_tools

logger = configure_logger(__name__)


class ProposalEvaluationState(TypedDict):
    """Type definition for the proposal evaluation state."""

    proposal_id: Annotated[str, no_update_reducer]
    proposal_data: Annotated[str, no_update_reducer]
    dao_id: Annotated[Optional[str], no_update_reducer]
    agent_id: Annotated[Optional[str], no_update_reducer]
    profile_id: Annotated[Optional[str], no_update_reducer]
    core_score: Annotated[Optional[Dict[str, Any]], set_once]
    historical_score: Annotated[Optional[Dict[str, Any]], set_once]
    financial_score: Annotated[Optional[Dict[str, Any]], set_once]
    social_score: Annotated[Optional[Dict[str, Any]], set_once]
    final_score: Annotated[Optional[Dict[str, Any]], set_once]
    flags: Annotated[List[str], append_list_fn]  # Correctly appends lists
    summaries: Annotated[Dict[str, str], merge_dicts]  # Properly merges dictionaries
    decision: Annotated[Optional[str], set_once]
    halt: Annotated[bool, operator.or_]
    token_usage: Annotated[
        Dict[str, Dict[str, int]], merge_dicts
    ]  # Properly merges dictionaries
    # Improved state tracking
    workflow_step: Annotated[str, lambda x, y: y[-1] if y else x]  # Track current step
    completed_steps: Annotated[
        set[str], lambda x, y: x.union(set(y)) if y else x
    ]  # Track completed steps
    proposal_images: Annotated[Optional[List[Dict]], set_once]


class ProposalEvaluationWorkflow(BaseWorkflow[ProposalEvaluationState]):
    """Main workflow for evaluating DAO proposals using a hierarchical team."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the proposal evaluation workflow.

        Args:
            config: Optional configuration dictionary
        """
        super().__init__()
        self.config = config or {}
        self.hierarchical_workflow = HierarchicalTeamWorkflow(
            name="ProposalEvaluation",
            config={
                "state_type": ProposalEvaluationState,
                "recursion_limit": self.config.get(
                    "recursion_limit", 15
                ),  # Reduced limit
            },
        )

        # Initialize agents
        image_processor_agent = ImageProcessingNode(config=self.config)
        core_agent = CoreContextAgent(self.config)
        historical_agent = HistoricalContextAgent(self.config)
        financial_agent = FinancialContextAgent(self.config)
        social_agent = SocialContextAgent(self.config)
        reasoning_agent = ReasoningAgent(self.config)

        # Add agents to the workflow
        self.hierarchical_workflow.add_sub_workflow(
            "image_processor", image_processor_agent
        )
        self.hierarchical_workflow.add_sub_workflow("core_agent", core_agent)
        self.hierarchical_workflow.add_sub_workflow(
            "historical_agent", historical_agent
        )
        self.hierarchical_workflow.add_sub_workflow("financial_agent", financial_agent)
        self.hierarchical_workflow.add_sub_workflow("social_agent", social_agent)
        self.hierarchical_workflow.add_sub_workflow("reasoning_agent", reasoning_agent)

        # Set entry point and other workflow properties
        self.hierarchical_workflow.set_entry_point("image_processor")
        self.hierarchical_workflow.set_supervisor_logic(self._supervisor_logic)
        self.hierarchical_workflow.set_halt_condition(self._halt_condition)
        self.required_fields = ["proposal_id", "proposal_data"]

    def _supervisor_logic(
        self, state: ProposalEvaluationState
    ) -> Union[str, List[str]]:
        """Determine which agent(s) to run next based on current state.

        Improved logic to prevent infinite loops and unnecessary re-executions.

        Args:
            state: Current workflow state

        Returns:
            String or list of strings identifying next agent(s) to run
        """
        # Initialize workflow tracking
        if "workflow_step" not in state:
            state["workflow_step"] = "start"
        if "completed_steps" not in state:
            state["completed_steps"] = set()

        proposal_id = state.get("proposal_id", "unknown")
        completed_steps = state.get("completed_steps", set())

        logger.info(
            f"[DEBUG:SupervisorLogic:{proposal_id}] Current step: {state.get('workflow_step')}, "
            f"Completed: {completed_steps}"
        )

        # Step 1: Image processing (required first step)
        if "proposal_images" not in state and "image_processor" not in completed_steps:
            logger.debug(
                f"[DEBUG:SupervisorLogic:{proposal_id}] Starting image processing"
            )
            state["workflow_step"] = "image_processing"
            return "image_processor"

        # Step 2: Core context evaluation (required after images)
        if "core_score" not in state and "core_agent" not in completed_steps:
            # Ensure images are processed first
            if "proposal_images" not in state:
                logger.warning(
                    f"[DEBUG:SupervisorLogic:{proposal_id}] Images not processed, but core agent requested"
                )
                state["proposal_images"] = []  # Set empty images to proceed

            logger.debug(
                f"[DEBUG:SupervisorLogic:{proposal_id}] Starting core evaluation"
            )
            state["workflow_step"] = "core_evaluation"
            return "core_agent"

        # Step 3: Parallel evaluation of specialized agents
        specialized_agents = ["historical_agent", "financial_agent", "social_agent"]
        specialized_scores = ["historical_score", "financial_score", "social_score"]

        # Check if core evaluation is complete
        if "core_score" in state:
            # Find which specialized agents haven't completed yet
            pending_agents = []
            for agent, score_key in zip(specialized_agents, specialized_scores):
                if score_key not in state and agent not in completed_steps:
                    pending_agents.append(agent)

            if pending_agents:
                logger.debug(
                    f"[DEBUG:SupervisorLogic:{proposal_id}] Running specialized agents: {pending_agents}"
                )
                state["workflow_step"] = "specialized_evaluation"
                # Return all pending agents for parallel execution
                return pending_agents

        # Step 4: Final reasoning (only after all evaluations are complete)
        all_scores_present = all(
            score_key in state for score_key in ["core_score"] + specialized_scores
        )

        if (
            all_scores_present
            and "final_score" not in state
            and "reasoning_agent" not in completed_steps
        ):
            logger.debug(
                f"[DEBUG:SupervisorLogic:{proposal_id}] Starting final reasoning"
            )
            state["workflow_step"] = "final_reasoning"
            return "reasoning_agent"

        # Step 5: Workflow complete
        if "final_score" in state:
            logger.info(f"[DEBUG:SupervisorLogic:{proposal_id}] Workflow complete")
            state["workflow_step"] = "complete"
            return END

        # Error state - should not reach here
        logger.error(
            f"[DEBUG:SupervisorLogic:{proposal_id}] Unexpected state - "
            f"core_score: {'core_score' in state}, "
            f"specialized scores: {[key in state for key in specialized_scores]}, "
            f"final_score: {'final_score' in state}, "
            f"completed_steps: {completed_steps}"
        )

        # Force completion if we're in an unexpected state
        return END

    def _halt_condition(self, state: ProposalEvaluationState) -> bool:
        """Determine if the workflow should halt early.

        Improved halt condition with better error detection.

        Args:
            state: Current workflow state

        Returns:
            True if workflow should halt, False otherwise
        """
        proposal_id = state.get("proposal_id", "unknown")

        # Halt if explicitly set
        if state.get("halt", False):
            logger.info(
                f"[DEBUG:HaltCondition:{proposal_id}] Halting due to explicit halt flag"
            )
            return True

        # Check for circular dependencies or infinite loops
        workflow_step = state.get("workflow_step", "start")
        completed_steps = state.get("completed_steps", set())

        # Define the expected workflow sequence
        expected_sequence = [
            "image_processing",
            "core_evaluation",
            "specialized_evaluation",
            "final_reasoning",
            "complete",
        ]

        # If we've been on the same step too long, something is wrong
        if hasattr(state, "_step_attempts"):
            state["_step_attempts"][workflow_step] = (
                state["_step_attempts"].get(workflow_step, 0) + 1
            )
            if state["_step_attempts"][workflow_step] > 3:
                logger.error(
                    f"[DEBUG:HaltCondition:{proposal_id}] Too many attempts on step {workflow_step}"
                )
                state["flags"] = state.get("flags", []) + [
                    f"Workflow halted: Too many attempts on step {workflow_step}"
                ]
                return True
        else:
            state["_step_attempts"] = {workflow_step: 1}

        # Check for agent completion tracking
        required_agents = {
            "image_processor",
            "core_agent",
            "historical_agent",
            "financial_agent",
            "social_agent",
            "reasoning_agent",
        }

        # If we have all required scores but final score is missing and reasoning agent hasn't run
        if (
            all(
                key in state
                for key in [
                    "core_score",
                    "historical_score",
                    "financial_score",
                    "social_score",
                ]
            )
            and "final_score" not in state
            and "reasoning_agent" in completed_steps
        ):
            logger.error(
                f"[DEBUG:HaltCondition:{proposal_id}] Reasoning agent completed but no final score"
            )
            state["flags"] = state.get("flags", []) + [
                "Workflow halted: Reasoning agent failed to produce final score"
            ]
            return True

        return False

    def _create_graph(self) -> StateGraph:
        """Create the workflow graph.

        Returns:
            The constructed state graph
        """
        return self.hierarchical_workflow.build_graph()

    def _validate_state(self, state: ProposalEvaluationState) -> bool:
        """Validate that the state contains required fields.

        Args:
            state: Current workflow state

        Returns:
            True if state is valid, False otherwise
        """
        for field in self.required_fields:
            if field not in state:
                self.logger.error(
                    f"[ProposalEvaluation] Missing required field: {field}"
                )
                return False
        return True


async def evaluate_proposal(
    proposal_id: str,
    proposal_data: str,
    config: Optional[Dict[str, Any]] = None,
    dao_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    profile_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Evaluate a proposal using the ProposalEvaluationWorkflow.

    Args:
        proposal_id: Unique identifier for the proposal
        proposal_data: Proposal content
        config: Optional configuration for the workflow

    Returns:
        Dictionary containing evaluation results
    """
    # Set up configuration with defaults if not provided
    if config is None:
        config = {}

    # Use model name from config or default
    model_name = config.get("model_name", "gpt-4.1")

    workflow = ProposalEvaluationWorkflow(config)

    # Create initial state with improved tracking
    initial_state = {
        "proposal_id": proposal_id,
        "proposal_data": proposal_data,
        "dao_id": dao_id,
        "agent_id": agent_id,
        "profile_id": profile_id,
        "flags": [],
        "summaries": {},
        "token_usage": {},
        "halt": False,
        "workflow_step": "start",
        "completed_steps": set(),
    }

    # Run workflow
    try:
        logger.info(f"Starting proposal evaluation for proposal {proposal_id}")
        result = await workflow.execute(initial_state)

        logger.info(
            f"[DEBUG:EXTRACT] Workflow execution complete, result keys: {list(result.keys())}"
        )
        logger.info(f"[DEBUG:EXTRACT] final_score in result: {'final_score' in result}")
        if "final_score" in result:
            logger.info(
                f"[DEBUG:EXTRACT] final_score type: {type(result['final_score'])}"
            )
            logger.info(f"[DEBUG:EXTRACT] final_score content: {result['final_score']}")

        # Extract results
        def safe_extract_score(value, default=0):
            """Safely extract a score from a potentially complex structure."""
            if isinstance(value, dict) and "score" in value:
                return value["score"]
            return default

        # Get all scores for reporting
        core_score = safe_extract_score(result.get("core_score"))
        historical_score = safe_extract_score(result.get("historical_score"))
        financial_score = safe_extract_score(result.get("financial_score"))
        social_score = safe_extract_score(result.get("social_score"))
        final_score = safe_extract_score(result.get("final_score"))

        # Get decision
        final_decision = "Undecided"
        final_explanation = "No final decision was reached."

        if isinstance(result.get("final_score"), dict):
            final_decision = result["final_score"].get("decision", "Undecided")
            final_explanation = result["final_score"].get(
                "explanation", "No explanation provided."
            )

        # Determine approval and confidence
        approval = final_decision.lower() == "approve"
        confidence = 0.7  # Default confidence

        if (
            isinstance(result.get("final_score"), dict)
            and "confidence" in result["final_score"]
        ):
            confidence = result["final_score"]["confidence"]

        # Compile token usage
        token_usage = result.get("token_usage", {})
        total_token_usage = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }

        for agent_usage in token_usage.values():
            total_token_usage["input_tokens"] += agent_usage.get("input_tokens", 0)
            total_token_usage["output_tokens"] += agent_usage.get("output_tokens", 0)
            total_token_usage["total_tokens"] += agent_usage.get("total_tokens", 0)

        # Return formatted result
        evaluation_result = {
            "proposal_id": proposal_id,
            "approve": approval,
            "confidence_score": confidence,
            "reasoning": final_explanation,
            "scores": {
                "core": core_score,
                "historical": historical_score,
                "financial": financial_score,
                "social": social_score,
                "final": final_score,
            },
            "flags": result.get("flags", []),
            "summaries": result.get("summaries", {}),
            "token_usage": total_token_usage,
            "model_name": model_name,
            "workflow_step": result.get("workflow_step", "unknown"),
            "completed_steps": list(result.get("completed_steps", set())),
        }

        logger.info(
            f"Completed proposal evaluation for proposal {proposal_id}: {final_decision}"
        )
        return evaluation_result

    except Exception as e:
        logger.error(f"Error in proposal evaluation: {str(e)}")
        return {
            "proposal_id": proposal_id,
            "approve": False,
            "confidence_score": 0.1,
            "reasoning": f"Evaluation failed due to error: {str(e)}",
            "error": str(e),
        }


def get_proposal_evaluation_tools(
    profile: Optional[Profile] = None, agent_id: Optional[UUID] = None
):
    """Get tools for proposal evaluation.

    Args:
        profile: Optional user profile
        agent_id: Optional agent ID

    Returns:
        List of available tools
    """
    tool_names = ["vote_on_action_proposal"]
    tools = initialize_tools(profile, agent_id)
    return filter_tools_by_names(tools, tool_names)


async def evaluate_and_vote_on_proposal(
    proposal_id: UUID,
    wallet_id: Optional[UUID] = None,
    agent_id: Optional[UUID] = None,
    auto_vote: bool = True,
    confidence_threshold: float = 0.7,
    dao_id: Optional[UUID] = None,
    debug_level: int = 0,  # 0=normal, 1=verbose, 2=very verbose
) -> Dict:
    """Evaluate a proposal and optionally vote on it.

    Args:
        proposal_id: Proposal ID
        wallet_id: Optional wallet ID
        agent_id: Optional agent ID
        auto_vote: Whether to automatically vote based on evaluation
        confidence_threshold: Confidence threshold for auto-voting
        dao_id: Optional DAO ID
        debug_level: Debug level (0=normal, 1=verbose, 2=very verbose)

    Returns:
        Evaluation and voting results
    """
    # Get proposal details
    logger.info(f"Retrieving proposal details for {proposal_id}")

    try:
        proposal = backend.get_proposal(proposal_id=proposal_id)

        if not proposal:
            logger.error(f"Proposal {proposal_id} not found")
            return {"error": f"Proposal {proposal_id} not found"}

        # Set up config based on debug level
        config = {
            "debug_level": debug_level,
        }

        if debug_level >= 1:
            # For verbose debugging, customize agent settings
            config["approval_threshold"] = 70
            config["veto_threshold"] = 30
            config["consensus_threshold"] = 10

        # Extract context for personalized evaluation
        evaluation_dao_id = str(proposal.dao_id) if proposal.dao_id else None
        evaluation_agent_id = str(agent_id) if agent_id else None

        # Get profile_id from wallet if available
        evaluation_profile_id = None
        if wallet_id:
            wallet = backend.get_wallet(wallet_id)
            if wallet and wallet.profile_id:
                evaluation_profile_id = str(wallet.profile_id)

        # Evaluate the proposal
        logger.info(f"Starting evaluation of proposal {proposal_id}")
        evaluation_result = await evaluate_proposal(
            proposal_id=str(proposal_id),
            proposal_data=proposal.content,
            config=config,
            dao_id=evaluation_dao_id,
            agent_id=evaluation_agent_id,
            profile_id=evaluation_profile_id,
        )

        # Check if auto voting is enabled
        if auto_vote:
            if "error" in evaluation_result:
                logger.error(
                    f"Skipping voting due to evaluation error: {evaluation_result['error']}"
                )
                return {
                    "evaluation": evaluation_result,
                    "vote_result": None,
                    "message": "Skipped voting due to evaluation error",
                }

            # Check if the confidence score meets the threshold
            confidence_score = evaluation_result.get("confidence_score", 0)

            if confidence_score >= confidence_threshold:
                # Get the vote decision
                approve = evaluation_result.get("approve", False)
                vote_direction = "for" if approve else "against"

                logger.info(
                    f"Auto-voting {vote_direction} proposal {proposal_id} with confidence {confidence_score}"
                )

                # Get the profile by finding the wallet first
                profile = None
                if wallet_id:
                    wallet = backend.get_wallet(wallet_id)
                    if wallet and wallet.profile_id:
                        profile = backend.get_profile(wallet.profile_id)
                elif agent_id:
                    # Try to find wallet by agent_id
                    from backend.models import WalletFilter

                    wallets = backend.list_wallets(WalletFilter(agent_id=agent_id))
                    if wallets and wallets[0].profile_id:
                        profile = backend.get_profile(wallets[0].profile_id)
                tools = get_proposal_evaluation_tools(profile, agent_id)
                vote_tool = next(
                    (t for t in tools if isinstance(t, VoteOnActionProposalTool)), None
                )

                if vote_tool:
                    try:
                        # Execute the vote
                        vote_result = await vote_tool.execute(
                            proposal_id=str(proposal_id),
                            vote=vote_direction,
                            wallet_id=str(wallet_id) if wallet_id else None,
                            dao_id=str(dao_id) if dao_id else None,
                        )

                        logger.info(f"Vote result: {vote_result}")

                        return {
                            "evaluation": evaluation_result,
                            "vote_result": vote_result,
                            "message": f"Voted {vote_direction} with confidence {confidence_score:.2f}",
                        }
                    except Exception as e:
                        logger.error(f"Error voting on proposal: {str(e)}")
                        return {
                            "evaluation": evaluation_result,
                            "vote_result": None,
                            "error": f"Error voting on proposal: {str(e)}",
                        }
                else:
                    logger.error("Vote tool not available")
                    return {
                        "evaluation": evaluation_result,
                        "vote_result": None,
                        "error": "Vote tool not available",
                    }
            else:
                logger.info(
                    f"Skipping auto-vote due to low confidence: {confidence_score} < {confidence_threshold}"
                )
                return {
                    "evaluation": evaluation_result,
                    "vote_result": None,
                    "message": f"Skipped voting due to low confidence: {confidence_score:.2f} < {confidence_threshold}",
                }
        else:
            logger.info(f"Auto-voting disabled, returning evaluation only")
            return {
                "evaluation": evaluation_result,
                "vote_result": None,
                "message": "Auto-voting disabled",
            }

    except Exception as e:
        logger.error(f"Error in evaluate_and_vote_on_proposal: {str(e)}")
        return {"error": f"Failed to evaluate proposal: {str(e)}"}


async def evaluate_proposal_only(
    proposal_id: UUID,
    wallet_id: Optional[UUID] = None,
    agent_id: Optional[UUID] = None,
    dao_id: Optional[UUID] = None,
) -> Dict:
    """Evaluate a proposal without voting.

    Args:
        proposal_id: Proposal ID
        wallet_id: Optional wallet ID
        agent_id: Optional agent ID
        dao_id: Optional DAO ID

    Returns:
        Evaluation results
    """
    # Delegate to evaluate_and_vote_on_proposal with auto_vote=False
    return await evaluate_and_vote_on_proposal(
        proposal_id=proposal_id,
        wallet_id=wallet_id,
        agent_id=agent_id,
        auto_vote=False,
        dao_id=dao_id,
    )
