"""Proposal evaluation workflow."""

import os
from typing import Dict, List, Optional, TypedDict

from langchain.prompts import PromptTemplate
from langgraph.graph import END, Graph, StateGraph
from pydantic import BaseModel, Field

from backend.factory import backend
from backend.models import UUID, Profile
from lib.logger import configure_logger
from services.workflows.base import BaseWorkflow
from tools.dao_ext_action_proposals import GetProposalTool, VoteOnActionProposalTool
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
            You are a DAO proposal evaluator. Your task is to analyze the following proposal and determine whether to vote FOR or AGAINST it.
            
            DAO Information:
            {dao_info}
            
            Proposal Data:
            {proposal_data}
            
            Evaluation Guidelines:
            1. Assess if the proposal aligns with the DAO's mission and values
            2. Evaluate the technical feasibility and risks
            3. Consider the potential impact on the DAO and its members
            4. Analyze the cost-benefit ratio
            5. Check for any security or governance concerns
            
            Evaluation Criteria by Proposal Type:
            
            For Resource Addition Proposals:
            - Assess if the resource provides value to the DAO community
            - Check if the pricing is reasonable for the value provided
            - Verify that the resource description is clear and accurate
            - Consider if the resource aligns with the DAO's mission
            
            For Asset Allowance Proposals:
            - Evaluate the token's reputation, utility, and security
            - Consider potential risks of allowing this asset
            - Assess if the token aligns with the DAO's investment strategy
            - Check for any regulatory concerns
            
            For Message Sending Proposals:
            - Evaluate the content and tone of the message
            - Ensure the message represents the DAO appropriately
            - Check for any potential reputational risks
            
            For Account Holder Changes:
            - Verify the reputation and trustworthiness of the proposed account holder
            - Consider the security implications of the change
            - Assess if proper governance procedures were followed for nomination
            
            For Withdrawal Parameter Changes:
            - Evaluate if the proposed changes maintain appropriate security controls
            - Consider if the changes could lead to potential abuse
            - Assess if the changes align with the DAO's financial strategy
            
            For Resource Toggle Proposals:
            - Consider the reasons for enabling/disabling the resource
            - Evaluate the impact on users who may be using the resource
            - Assess if the change aligns with the DAO's current priorities
            
            General Decision Criteria:
            - Proposals that enhance the DAO's functionality, security, or user experience should generally be approved
            - Proposals that introduce unnecessary risks, high costs with low benefits, or governance issues should be rejected
            - Proposals that modify core parameters should be carefully scrutinized for unintended consequences
            - Proposals that add new resources or assets should be evaluated for their utility and value to the DAO
            
            Output format:
            {{
                "approve": bool,  # true to vote FOR, false to vote AGAINST
                "confidence_score": float,  # between 0.0 and 1.0
                "reasoning": str  # detailed explanation of your decision
            }}
            """,
        )

    def _create_graph(self) -> Graph:
        """Create the evaluation graph."""
        prompt = self._create_prompt()

        # Create evaluation node
        def evaluate_proposal(state: EvaluationState) -> EvaluationState:
            """Evaluate the proposal and determine how to vote."""
            # Format prompt with state
            formatted_prompt = prompt.format(
                proposal_data=state["proposal_data"],
                dao_info=state.get(
                    "dao_info", "No additional DAO information available."
                ),
            )

            # Get evaluation from LLM
            structured_output = self.llm.with_structured_output(
                ProposalEvaluationOutput,
            )
            result = structured_output.invoke(formatted_prompt)

            # Update state
            state["approve"] = result.approve
            state["confidence_score"] = result.confidence_score
            state["reasoning"] = result.reasoning

            return state

        # Create decision node
        def should_vote(state: EvaluationState) -> str:
            """Decide whether to vote based on confidence threshold."""
            if not state["auto_vote"]:
                return "skip_vote"

            if state["confidence_score"] >= state["confidence_threshold"]:
                return "vote"
            else:
                return "skip_vote"

        # Create voting node
        def vote_on_proposal(state: EvaluationState) -> EvaluationState:
            """Vote on the proposal based on the evaluation."""
            # Initialize the VoteOnActionProposalTool
            vote_tool = VoteOnActionProposalTool(wallet_id=state["wallet_id"])

            # Execute the vote
            vote_result = vote_tool._run(
                action_proposals_contract=state["action_proposals_contract"],
                proposal_id=state["proposal_id"],
                vote=state["approve"],
            )

            # Update state with vote result
            state["vote_result"] = vote_result

            return state

        # Create skip voting node
        def skip_voting(state: EvaluationState) -> EvaluationState:
            """Skip voting and just return the evaluation."""
            state["vote_result"] = {
                "success": True,
                "message": "Voting skipped due to confidence threshold or auto_vote setting",
                "data": None,
            }
            return state

        # Create the graph
        workflow = StateGraph(EvaluationState)

        # Add nodes
        workflow.add_node("evaluate", evaluate_proposal)
        workflow.add_node("vote", vote_on_proposal)
        workflow.add_node("skip_vote", skip_voting)

        # Add edges
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
        return all(field in state and state[field] for field in required_fields)


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

    # Filter to only include the tools we need
    required_tools = [
        "dao_action_get_proposal",
        "dao_action_vote_on_proposal",
        "dao_action_get_voting_power",
        "dao_action_get_voting_configuration",
        "database_get_dao_get_by_name",
    ]

    return filter_tools_by_names(required_tools, all_tools)


async def evaluate_and_vote_on_proposal(
    action_proposals_contract: str,
    proposal_id: int,
    dao_name: Optional[str] = None,
    wallet_id: Optional[UUID] = None,
    auto_vote: bool = True,
    confidence_threshold: float = 0.7,
) -> Dict:
    """Evaluate a proposal and automatically vote based on the evaluation.

    Args:
        action_proposals_contract: The contract ID of the DAO action proposals
        proposal_id: The ID of the proposal to evaluate and vote on
        dao_name: Optional name of the DAO for additional context
        wallet_id: Optional wallet ID to use for voting
        auto_vote: Whether to automatically vote based on the evaluation
        confidence_threshold: Minimum confidence score required to auto-vote (0.0-1.0)

    Returns:
        Dictionary containing the evaluation results and voting outcome
    """
    # First, get the proposal data
    get_proposal_tool = GetProposalTool(wallet_id=wallet_id)
    proposal_data = get_proposal_tool._run(
        action_proposals_contract=action_proposals_contract,
        proposal_id=proposal_id,
    )

    if not proposal_data.get("success", False):
        return {
            "success": False,
            "error": f"Failed to retrieve proposal data: {proposal_data.get('error', 'Unknown error')}",
        }

    # Get DAO information if available
    dao_info = None
    if dao_name:
        try:
            # Get DAO information from the database
            dao_info_tool = get_proposal_evaluation_tools().get(
                "database_get_dao_get_by_name"
            )
            if dao_info_tool:
                dao_info_result = dao_info_tool._run(name=dao_name)
                if dao_info_result.get("success", False):
                    dao_info = dao_info_result.get("data", {})
        except Exception as e:
            logger.warning(f"Failed to retrieve DAO information: {str(e)}")

    # Initialize state
    state = {
        "action_proposals_contract": action_proposals_contract,
        "proposal_id": proposal_id,
        "proposal_data": proposal_data.get("data", {}),
        "dao_info": dao_info,
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
    result = await workflow.execute(state)

    return {
        "success": True,
        "evaluation": {
            "approve": result["approve"],
            "confidence_score": result["confidence_score"],
            "reasoning": result["reasoning"],
        },
        "vote_result": result["vote_result"],
        "auto_voted": auto_vote and result["confidence_score"] >= confidence_threshold,
    }


async def evaluate_proposal_only(
    action_proposals_contract: str,
    proposal_id: int,
    dao_name: Optional[str] = None,
    wallet_id: Optional[UUID] = None,
) -> Dict:
    """Evaluate a proposal without voting.

    Args:
        action_proposals_contract: The contract ID of the DAO action proposals
        proposal_id: The ID of the proposal to evaluate
        dao_name: Optional name of the DAO for additional context
        wallet_id: Optional wallet ID to use for retrieving proposal data

    Returns:
        Dictionary containing the evaluation results
    """
    result = await evaluate_and_vote_on_proposal(
        action_proposals_contract=action_proposals_contract,
        proposal_id=proposal_id,
        dao_name=dao_name,
        wallet_id=wallet_id,
        auto_vote=False,
    )

    # Remove vote_result from the response
    if "vote_result" in result:
        del result["vote_result"]
    if "auto_voted" in result:
        del result["auto_voted"]

    return result
