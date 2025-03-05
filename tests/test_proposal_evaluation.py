"""Test script for the proposal evaluation workflow."""

import asyncio
import os
import sys
from typing import Dict, Optional

# Add the parent directory to the path so we can import the modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models import UUID
from services.workflows.proposal_evaluation import (
    evaluate_and_vote_on_proposal,
    evaluate_proposal_only,
)


async def test_proposal_evaluation(
    action_proposals_contract: str,
    proposal_id: int,
    dao_name: Optional[str] = None,
    wallet_id: Optional[UUID] = None,
    auto_vote: bool = False,
) -> Dict:
    """Test the proposal evaluation workflow.

    Args:
        action_proposals_contract: The contract ID of the DAO action proposals
        proposal_id: The ID of the proposal to evaluate
        dao_name: Optional name of the DAO for additional context
        wallet_id: Optional wallet ID to use for retrieving proposal data
        auto_vote: Whether to automatically vote based on the evaluation

    Returns:
        Dictionary containing the evaluation results
    """
    print(f"Evaluating proposal {proposal_id} for contract {action_proposals_contract}")

    if auto_vote:
        print("Auto-voting is enabled")
        result = await evaluate_and_vote_on_proposal(
            action_proposals_contract=action_proposals_contract,
            proposal_id=proposal_id,
            dao_name=dao_name,
            wallet_id=wallet_id,
            auto_vote=True,
            confidence_threshold=0.7,
        )
    else:
        print("Evaluation only mode (no voting)")
        result = await evaluate_proposal_only(
            action_proposals_contract=action_proposals_contract,
            proposal_id=proposal_id,
            dao_name=dao_name,
            wallet_id=wallet_id,
        )

    # Print the results
    print("\nEvaluation Results:")
    print(f"Approve: {result['evaluation']['approve']}")
    print(f"Confidence: {result['evaluation']['confidence_score']}")
    print(f"Reasoning: {result['evaluation']['reasoning']}")

    if auto_vote and result.get("auto_voted"):
        print("\nVoting Results:")
        print(f"Auto-voted: {result.get('auto_voted', False)}")
        print(f"Vote Result: {result.get('vote_result', {})}")

    return result


if __name__ == "__main__":
    # Example usage
    # Replace these values with actual contract and proposal IDs
    contract_id = "SP000000000000000000002Q6VF78.dao-action-proposals"
    proposal_id = 1
    dao_name = "Example DAO"

    # Run the test
    asyncio.run(
        test_proposal_evaluation(
            action_proposals_contract=contract_id,
            proposal_id=proposal_id,
            dao_name=dao_name,
            auto_vote=False,  # Set to True to enable auto-voting
        )
    )
