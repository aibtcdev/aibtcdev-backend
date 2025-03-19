"""Proposal evaluation workflow."""

from typing import Dict, Optional, TypedDict

from langchain.prompts import PromptTemplate
from langgraph.graph import END, Graph, StateGraph
from pydantic import BaseModel, Field

from backend.factory import backend
from backend.models import UUID, Profile
from lib.logger import configure_logger
from services.workflows.base import BaseWorkflow
from tools.dao_ext_action_proposals import VoteOnActionProposalTool
from tools.tools_factory import filter_tools_by_names, initialize_tools

logger = configure_logger(__name__)


class ProposalEvaluationOutput(BaseModel):
    """Output model for proposal evaluation."""

    approve: bool = Field(
        description="Whether to approve (true) or reject (false) the proposal"
    )
    confidence_score: float = Field(
        description="The confidence score for the evaluation (0.0-1.0)"
    )
    reasoning: str = Field(description="The reasoning behind the evaluation decision")


class EvaluationState(TypedDict):
    """State for the proposal evaluation flow."""

    action_proposals_contract: str
    action_proposals_voting_extension: str
    proposal_id: int
    proposal_data: Dict
    dao_info: Optional[Dict]
    approve: bool
    confidence_score: float
    reasoning: str
    vote_result: Optional[Dict]
    wallet_id: Optional[UUID]
    confidence_threshold: float
    auto_vote: bool


class ProposalEvaluationWorkflow(BaseWorkflow[EvaluationState]):
    """Workflow for evaluating DAO proposals and voting automatically."""

    def _create_prompt(self) -> PromptTemplate:
        """Create the evaluation prompt template."""
        return PromptTemplate(
            input_variables=["proposal_data", "dao_info"],
            template="""
            You are a DAO proposal evaluator. Your task is to analyze the following action proposal and determine whether to vote FOR or AGAINST it based on its parameters and purpose.

            DAO Information:
            {dao_info}

            Note: The AIBTC Charter below represents high-level guiding principles for the AIBTC platform and AI agent operations, not the specific DAO's own charter.

            AIBTC Charter
            1. Mission: Elevate human potential through Autonomous Intelligence on Bitcoin.
            2. Core Values:
            • Curiosity | Truth Maximizing | Humanity's Best Interests
            • Transparency | Resilience | Collaboration
            3. Guardrails:
            • Decentralized Governance
            • Smart Contracts to enforce accountability
            4. Amendments:
            • Allowed only if they uphold the mission/values and pass a governance vote

            Proposal Data:
            {proposal_data}

            # Action Proposal Types and Guidelines

            Action proposals are predefined operations that can be executed with specific voting requirements (66% approval threshold, 15% quorum). Each action is implemented as a smart contract that executes specific functionality through the DAO's extensions.

            Focus on the "action" field in the proposal data to identify the proposal type, and the "parameters" field (a hexadecimal string starting with "0x") which contains the encoded content.

            ## Available Action Types:

            ### Payment/Invoice Management
            * **Add Resource** (`aibtc-action-add-resource`): Creates new payable resource in the payments system. Sets resource name, description, price, and URL.
            * **Toggle Resource** (`aibtc-action-toggle-resource-by-name`): Enables or disables a payment resource.

            ### Treasury Management
            * **Allow Asset** (`aibtc-action-allow-asset`): Adds FT or NFT to treasury allowlist. Enables deposits and withdrawals of the asset.

            ### Messaging
            * **Send Message** (`aibtc-action-send-message`): Posts verified DAO message on-chain. Message includes DAO verification flag. Limited to 1MB size.

            ### Timed Vault Configuration
            * **Set Account Holder** (`aibtc-action-set-account-holder`): Designates authorized withdrawal address.
            * **Set Withdrawal Amount** (`aibtc-action-set-withdrawal-amount`): Updates permitted withdrawal size (0–100 STX).
            * **Set Withdrawal Period** (`aibtc-action-set-withdrawal-period`): Sets time between allowed withdrawals (6–1,008 blocks).

            ## Evaluation Guidelines:

            1. Identify the action type from the proposal data
            2. Evaluate the parameters based on the action type
            3. Consider the DAO's mission and values (in addition to the overarching AIBTC Charter)
            4. Assess potential security or financial risks
            5. Decide whether to vote FOR or AGAINST the proposal

            ### Specific Guidelines by Action Type:

            * **For messaging actions**: Ensure the message is appropriate, aligned with DAO values, and doesn't contain harmful content.
            * **For treasury actions**: Verify the asset is legitimate and appropriate for the DAO to interact with.
            * **For payment actions**: Confirm the resource details are complete and pricing is reasonable.
            * **For timed vault configuration**: Ensure parameters are within acceptable ranges and the account holder is trustworthy.

            When in doubt about technical parameters, lean toward approving proposals that come from trusted creators and follow established patterns.

            Output format:

            {{
            "approve": bool,  # true to vote FOR, false to vote AGAINST the proposal
            "confidence_score": float,  # between 0.0 and 1.0
            "reasoning": str  # detailed explanation of your decision
            }}
            """,
        )

    def _create_graph(self) -> Graph:
        """Create the evaluation graph."""
        prompt = self._create_prompt()

        # Create evaluation node
        async def evaluate_proposal(state: EvaluationState) -> EvaluationState:
            """Evaluate the proposal and determine how to vote."""
            try:
                # Get proposal data from state
                proposal_data = state["proposal_data"]

                # Ensure we have parameters
                if not proposal_data.get("parameters"):
                    raise ValueError("No parameters found in proposal data")

                # Format prompt with state
                self.logger.debug("Formatting evaluation prompt...")
                formatted_prompt = prompt.format(
                    proposal_data=proposal_data,
                    dao_info=state.get(
                        "dao_info", "No additional DAO information available."
                    ),
                )

                # Get evaluation from LLM
                self.logger.debug("Invoking LLM for evaluation...")
                structured_output = self.llm.with_structured_output(
                    ProposalEvaluationOutput,
                )
                result = structured_output.invoke(formatted_prompt)
                self.logger.debug(f"LLM evaluation result: {result}")

                # Update state
                state["approve"] = result.approve
                state["confidence_score"] = result.confidence_score
                state["reasoning"] = result.reasoning
                self.logger.info(
                    f"Evaluation complete: approve={result.approve}, confidence={result.confidence_score}"
                )

                return state
            except Exception as e:
                self.logger.error(
                    f"Error in evaluate_proposal: {str(e)}", exc_info=True
                )
                state["approve"] = False
                state["confidence_score"] = 0.0
                state["reasoning"] = f"Error during evaluation: {str(e)}"
                return state

        # Create decision node
        async def should_vote(state: EvaluationState) -> str:
            """Decide whether to vote based on confidence threshold."""
            try:
                self.logger.debug(
                    f"Deciding whether to vote: auto_vote={state['auto_vote']}, confidence={state['confidence_score']}, threshold={state['confidence_threshold']}"
                )

                if not state["auto_vote"]:
                    self.logger.info("Auto-vote is disabled, skipping vote")
                    return "skip_vote"

                if state["confidence_score"] >= state["confidence_threshold"]:
                    self.logger.info(
                        f"Confidence score {state['confidence_score']} meets threshold {state['confidence_threshold']}, proceeding to vote"
                    )
                    return "vote"
                else:
                    self.logger.info(
                        f"Confidence score {state['confidence_score']} below threshold {state['confidence_threshold']}, skipping vote"
                    )
                    return "skip_vote"
            except Exception as e:
                self.logger.error(f"Error in should_vote: {str(e)}", exc_info=True)
                return "skip_vote"

        # Create voting node
        async def vote_on_proposal(state: EvaluationState) -> EvaluationState:
            """Vote on the proposal based on the evaluation."""
            try:
                # Initialize the VoteOnActionProposalTool
                self.logger.debug(
                    f"Preparing to vote on proposal {state['proposal_id']}, vote={state['approve']}"
                )
                vote_tool = VoteOnActionProposalTool(wallet_id=state["wallet_id"])

                # Execute the vote
                self.logger.debug("Executing vote...")
                vote_result = await vote_tool._arun(
                    action_proposals_voting_extension=state[
                        "action_proposals_contract"
                    ],
                    proposal_id=state["proposal_id"],
                    vote=state["approve"],
                )
                self.logger.debug(f"Vote result: {vote_result}")

                # Update state with vote result
                state["vote_result"] = vote_result
                self.logger.info(f"Vote complete: {vote_result.get('success', False)}")

                return state
            except Exception as e:
                self.logger.error(f"Error in vote_on_proposal: {str(e)}", exc_info=True)
                state["vote_result"] = {
                    "success": False,
                    "error": f"Error during voting: {str(e)}",
                }
                return state

        # Create skip voting node
        async def skip_voting(state: EvaluationState) -> EvaluationState:
            """Skip voting and just return the evaluation."""
            try:
                self.logger.debug("Skipping voting step")
                state["vote_result"] = {
                    "success": True,
                    "message": "Voting skipped due to confidence threshold or auto_vote setting",
                    "data": None,
                }
                self.logger.info("Vote skipped as requested")
                return state
            except Exception as e:
                self.logger.error(f"Error in skip_voting: {str(e)}", exc_info=True)
                state["vote_result"] = {
                    "success": True,
                    "message": f"Voting skipped (with error: {str(e)})",
                    "data": None,
                }
                return state

        # Create the graph
        workflow = StateGraph(EvaluationState)

        # Add nodes
        workflow.add_node("evaluate", evaluate_proposal)
        workflow.add_node("vote", vote_on_proposal)
        workflow.add_node("skip_vote", skip_voting)

        # Set up the conditional branching
        workflow.set_entry_point("evaluate")
        workflow.add_conditional_edges(
            "evaluate",
            should_vote,
            {
                "vote": "vote",
                "skip_vote": "skip_vote",
            },
        )
        workflow.add_edge("vote", END)
        workflow.add_edge("skip_vote", END)

        return workflow.compile()

    def _validate_state(self, state: EvaluationState) -> bool:
        """Validate the workflow state."""
        required_fields = ["action_proposals_contract", "proposal_id", "proposal_data"]

        # Log the state for debugging
        self.logger.debug(f"Validating state: {state}")

        # Check all fields and log problems
        for field in required_fields:
            if field not in state:
                self.logger.error(f"Missing required field: {field}")
                return False
            elif not state[field]:
                self.logger.error(f"Empty required field: {field}")
                return False

        # Ensure proposal_data has parameters
        if not state["proposal_data"].get("parameters"):
            self.logger.error("No parameters field in proposal_data")
            return False

        return True


def get_proposal_evaluation_tools(
    profile: Optional[Profile] = None, agent_id: Optional[UUID] = None
):
    """Get the tools needed for proposal evaluation.

    Args:
        profile: Optional user profile
        agent_id: Optional agent ID

    Returns:
        Dictionary of filtered tools for proposal evaluation
    """
    # Initialize all tools
    all_tools = initialize_tools(profile=profile, agent_id=agent_id)

    # Log all available tools for debugging
    logger.debug(f"All available tools: {', '.join(all_tools.keys())}")

    # Filter to only include the tools we need
    required_tools = [
        "dao_action_get_proposal",
        "dao_action_vote_on_proposal",
        "dao_action_get_voting_power",
        "dao_action_get_voting_configuration",
        "database_get_dao_get_by_name",  # Try old name
        "dao_search",  # Try new name
    ]

    filtered_tools = filter_tools_by_names(required_tools, all_tools)
    logger.debug(f"Filtered tools: {', '.join(filtered_tools.keys())}")

    return filtered_tools


async def evaluate_and_vote_on_proposal(
    proposal_id: UUID,
    dao_name: Optional[str] = None,
    wallet_id: Optional[UUID] = None,
    auto_vote: bool = True,
    confidence_threshold: float = 0.7,
) -> Dict:
    """Evaluate a proposal and automatically vote based on the evaluation.

    Args:
        proposal_id: The ID of the proposal to evaluate and vote on
        dao_name: Optional name of the DAO for additional context
        wallet_id: Optional wallet ID to use for voting
        auto_vote: Whether to automatically vote based on the evaluation
        confidence_threshold: Minimum confidence score required to auto-vote (0.0-1.0)

    Returns:
        Dictionary containing the evaluation results and voting outcome
    """
    logger.info(f"Starting proposal evaluation for proposal {proposal_id}")

    try:
        # Get proposal data directly from the database
        proposal_data = backend.get_proposal(proposal_id)
        if not proposal_data:
            error_msg = f"Proposal {proposal_id} not found in database"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        # Convert proposal data to dictionary and ensure parameters exist
        proposal_dict = {
            "proposal_id": proposal_data.proposal_id,
            "parameters": proposal_data.parameters,
            "action": proposal_data.action,
            "caller": proposal_data.caller,
            "contract_principal": proposal_data.contract_principal,
            "creator": proposal_data.creator,
            "created_at_block": proposal_data.created_at_block,
            "end_block": proposal_data.end_block,
            "start_block": proposal_data.start_block,
            "liquid_tokens": proposal_data.liquid_tokens,
        }

        if not proposal_dict.get("parameters"):
            error_msg = "No parameters found in proposal data"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        # Get DAO info
        dao_info = backend.get_dao(proposal_data.dao_id)
        if not dao_info:
            error_msg = f"DAO with ID {proposal_data.dao_id} not found"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        # Initialize state
        state = {
            "action_proposals_contract": proposal_dict["contract_principal"],
            "action_proposals_voting_extension": proposal_dict["action"],
            "proposal_id": proposal_dict["proposal_id"],
            "proposal_data": proposal_dict,
            "dao_info": dao_info or {},
            "approve": False,
            "confidence_score": 0.0,
            "reasoning": "",
            "vote_result": None,
            "wallet_id": wallet_id,
            "confidence_threshold": confidence_threshold,
            "auto_vote": auto_vote,
        }

        # Create and run workflow
        workflow = ProposalEvaluationWorkflow()
        if not workflow._validate_state(state):
            return {
                "success": False,
                "error": "Invalid workflow state",
            }

        result = await workflow.execute(state)

        # Extract transaction ID from vote result if available
        tx_id = None
        if result.get("vote_result") and result["vote_result"].get("output"):
            # Try to extract tx_id from the output
            output = result["vote_result"]["output"]
            if "txid:" in output.lower():
                # Extract the transaction ID from the output
                for line in output.split("\n"):
                    if "txid:" in line.lower():
                        parts = line.split(":")
                        if len(parts) > 1:
                            tx_id = parts[1].strip()
                            break

        return {
            "success": True,
            "evaluation": {
                "approve": result["approve"],
                "confidence_score": result["confidence_score"],
                "reasoning": result["reasoning"],
            },
            "vote_result": result["vote_result"],
            "auto_voted": auto_vote
            and result["confidence_score"] >= confidence_threshold,
            "tx_id": tx_id,
        }
    except Exception as e:
        logger.error(f"Error in evaluate_and_vote_on_proposal: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
        }


async def evaluate_proposal_only(
    proposal_id: UUID,
    dao_name: Optional[str] = None,
    wallet_id: Optional[UUID] = None,
) -> Dict:
    """Evaluate a proposal without voting.

    Args:
        action_proposals_contract: The contract ID of the DAO action proposals
        action_proposals_voting_extension: The contract ID of the DAO action proposals voting extension
        proposal_id: The ID of the proposal to evaluate
        dao_name: Optional name of the DAO for additional context
        wallet_id: Optional wallet ID to use for retrieving proposal data

    Returns:
        Dictionary containing the evaluation results
    """
    result = await evaluate_and_vote_on_proposal(
        proposal_id=proposal_id,
        dao_name=dao_name,
        wallet_id=wallet_id,
        auto_vote=True,
    )

    # Remove vote_result from the response
    if "vote_result" in result:
        del result["vote_result"]
    if "auto_voted" in result:
        del result["auto_voted"]

    return result


async def debug_proposal_evaluation_workflow():
    """Debug function to test the workflow with a mock state."""
    logger.setLevel("DEBUG")

    # Create a mock state with valid required fields
    mock_state = {
        "action_proposals_contract": "test-contract",
        "action_proposals_voting_extension": "test-voting-extension",
        "proposal_id": 1,
        "proposal_data": {"title": "Test Proposal", "description": "Test Description"},
        "dao_info": {"name": "Test DAO"},
        "approve": False,
        "confidence_score": 0.0,
        "reasoning": "",
        "vote_result": None,
        "wallet_id": None,
        "confidence_threshold": 0.7,
        "auto_vote": False,
    }

    # Create the workflow and validate the state
    workflow = ProposalEvaluationWorkflow()
    is_valid = workflow._validate_state(mock_state)
    logger.info(f"Mock state validation result: {is_valid}")

    # Try to execute with the mock state
    if is_valid:
        try:
            result = await workflow.execute(mock_state)
            logger.info(f"Workflow execution result: {result}")
        except Exception as e:
            logger.error(f"Workflow execution failed: {str(e)}", exc_info=True)

    return is_valid
