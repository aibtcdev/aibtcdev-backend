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
    core_agent_invocations: Annotated[int, operator.add]
    supervisor_invocations: Annotated[int, operator.add]
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
                "recursion_limit": self.config.get("recursion_limit", 20),
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

        Args:
            state: Current workflow state

        Returns:
            String or list of strings identifying next agent(s) to run
        """
        # Initialize core agent invocations counter if not present
        if "core_agent_invocations" not in state:
            state["core_agent_invocations"] = 0

            # Initialize supervisor invocations counter if not present
        if "supervisor_invocations" not in state:
            state["supervisor_invocations"] = 0

        # Only increment supervisor invocations counter if we're stuck on image processing
        if "proposal_images" not in state:
            state["supervisor_invocations"] += 1

        # Debug counter behavior
        logger.debug(
            f"[DEBUG:CoreCounter] Current invocations count: {state.get('core_agent_invocations', 0)}"
        )
        logger.debug(
            f"[DEBUG:SupervisorCounter] Current supervisor invocations: {state.get('supervisor_invocations', 0)}"
        )

        # Check if state has images processed
        # If proposal_images key doesn't exist, we need to process images
        # If it exists (even if it's an empty list), we consider images processed
        if "proposal_images" not in state:
            logger.debug("[DEBUG:SupervisorLogic] Need to process images first")
            logger.debug(f"[DEBUG:SupervisorLogic] State keys: {list(state.keys())}")
            return "image_processor"
        else:
            logger.debug(
                f"[DEBUG:SupervisorLogic] Images already processed: {state.get('proposal_images')}"
            )
            logger.debug(
                f"[DEBUG:SupervisorLogic] proposal_images type: {type(state.get('proposal_images'))}"
            )

        # Check if core context evaluation is done
        if "core_score" not in state:
            logger.debug("[DEBUG:SupervisorLogic] Need core context evaluation")
            old_count = state.get("core_agent_invocations", 0)
            state["core_agent_invocations"] = old_count + 1
            logger.debug(
                f"[DEBUG:CoreCounter] Incremented invocations: {old_count} -> {state['core_agent_invocations']}"
            )
            return "core_agent"

        # Run specialized agents in parallel if they haven't run yet
        agents_to_run = []

        if "historical_score" not in state:
            agents_to_run.append("historical_agent")

        if "financial_score" not in state:
            agents_to_run.append("financial_agent")

        if "social_score" not in state:
            agents_to_run.append("social_agent")

        if agents_to_run:
            logger.debug(
                f"[DEBUG:SupervisorLogic] Running specialized agents: {agents_to_run}"
            )
            return agents_to_run

        # If all specialized agents have run, run the reasoning agent for final decision
        if "final_score" not in state:
            logger.debug(
                "[DEBUG:SupervisorLogic] All specialized agents done, running reasoning agent"
            )
            logger.info(
                f"[DEBUG:DIAGNOSIS] About to run reasoning_agent, state keys: {list(state.keys())}"
            )
            return "reasoning_agent"

        # If reasoning agent has run, we're done
        logger.debug("[DEBUG:SupervisorLogic] Workflow complete")

        # Add diagnosis logging
        logger.info(
            f"[DEBUG:DIAGNOSIS] Workflow complete, final_score type: {type(state.get('final_score'))}"
        )
        logger.info(
            f"[DEBUG:DIAGNOSIS] Final score contents: {state.get('final_score')}"
        )

        # Log the entire state and final reasoning as JSON
        import json

        logger.info(f"[DEBUG:FinalState] {json.dumps(state, default=str, indent=2)}")

        return END

    def _halt_condition(self, state: ProposalEvaluationState) -> bool:
        """Determine if the workflow should halt early.

        Args:
            state: Current workflow state

        Returns:
            True if workflow should halt, False otherwise
        """
        # Halt if explicitly set
        if state.get("halt", False):
            logger.info("[DEBUG:HaltCondition] Halting due to explicit halt flag")
            return True

        # Halt if we've run the core agent too many times (prevent loops)
        core_agent_invocations = state.get("core_agent_invocations", 0)
        max_core_invocations = 50
        if core_agent_invocations > max_core_invocations:
            logger.warning(
                f"[DEBUG:HaltCondition] Halting due to too many core agent invocations: {core_agent_invocations}"
            )
            state["flags"] = state.get("flags", []) + [
                f"Workflow halted: Too many core agent invocations ({core_agent_invocations})"
            ]
            return True

        # Add halt condition only for truly stuck scenarios
        supervisor_invocations = state.get("supervisor_invocations", 0)
        max_supervisor_invocations = (
            100  # Very high limit, only for true infinite loops
        )

        # Only halt if we're clearly in an infinite loop (very high count with no progress)
        if (
            supervisor_invocations > max_supervisor_invocations
            and "proposal_images" not in state
        ):
            logger.warning(
                f"[DEBUG:HaltCondition] Halting due to infinite loop in image processing: {supervisor_invocations} invocations"
            )
            # Force set proposal_images to empty list to allow workflow to continue
            state["proposal_images"] = []
            state["flags"] = state.get("flags", []) + [
                f"Workflow recovered from image processing loop ({supervisor_invocations} invocations)"
            ]
            # Don't halt, just fix the state and continue
            return False

        # Don't halt by default
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

    # Create initial state
    initial_state = {
        "proposal_id": proposal_id,
        "proposal_data": proposal_data,
        "dao_id": dao_id,
        "agent_id": agent_id,
        "profile_id": profile_id,
        "flags": [],
        "summaries": {},
        "token_usage": {},
        "core_agent_invocations": 0,
        "supervisor_invocations": 0,
        "halt": False,
    }

    # Run workflow
    try:
        logger.info(f"Starting proposal evaluation for proposal {proposal_id}")
        result = await workflow.execute(initial_state)

        # Add diagnostic logging
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
