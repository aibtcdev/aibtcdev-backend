"""Functional test script for the proposal evaluation workflow.

This script demonstrates the usage of the proposal evaluation workflow
with real-world scenarios. It's not a unit test but rather a functional
test to see the workflow in action.
"""

import asyncio
from typing import Dict, Optional
from uuid import UUID

from backend.factory import backend
from backend.models import (
    ProposalCreate,
    ProposalType,
    QueueMessageCreate,
    QueueMessageType,
)
from services.workflows.proposal_evaluation import (
    evaluate_and_vote_on_proposal,
    evaluate_proposal_only,
)


async def create_test_proposal(dao_id: UUID) -> UUID:
    """Create a test proposal for evaluation.

    Args:
        dao_id: The ID of the DAO to create the proposal for

    Returns:
        The ID of the created proposal
    """
    # Create test parameters as a JSON object
    parameters = {
        "action": "test_action",
        "amount": 1000,
        "description": "Test proposal for evaluation",
        "recipient": "ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM",
    }

    # Create a test proposal
    proposal_data = ProposalCreate(
        dao_id=dao_id,
        type=ProposalType.ACTION,
        parameters=str(parameters),  # Convert parameters to string
        action="test_action",
        contract_principal="ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM.test-contract",
        creator="ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM",
        created_at_block=1,
        end_block=100,
        start_block=1,
        liquid_tokens="1000",  # Keep as string since that's what the model expects
        proposal_id=1,
    )

    try:
        # # Create some test tweets for the DAO
        # for i in range(3):
        #     tweet_message = {
        #         "text": f"Test tweet {i+1} for proposal evaluation",
        #         "created_at": "2024-03-06T00:00:00Z",
        #     }
        #     backend.create_queue_message(
        #         QueueMessageCreate(
        #             type=QueueMessageType.TWEET,
        #             dao_id=dao_id,
        #             message=tweet_message,
        #             is_processed=True,
        #         )
        #     )
        #     print(f"Created test tweet {i+1} for DAO {dao_id}")

        # Create the proposal
        proposal = backend.create_proposal(proposal_data)
        print(f"Created test proposal with ID: {proposal.id}")
        return proposal.id
    except Exception as e:
        print(f"Failed to create test proposal: {e}")
        raise


async def test_proposal_evaluation_workflow():
    """Test the proposal evaluation workflow with different scenarios."""
    try:
        # # First, let's run the debug workflow to test basic functionality
        # print("Running debug workflow test...")
        # debug_result = await debug_proposal_evaluation_workflow()
        # print(f"Debug workflow test result: {debug_result}")

        # Now let's test with a real proposal
        # First, we need a DAO ID - you would replace this with a real DAO ID
        dao_id = UUID(
            "cffb355f-50c1-4ec5-8e2f-a0e65547c746"
        )  # Replace with real DAO ID

        # Create a test proposal
        proposal_id = await create_test_proposal(dao_id)

        # Test scenarios
        scenarios = [
            {
                "name": "Evaluation Only",
                "auto_vote": False,
                "confidence_threshold": 0.7,
                "description": "Testing proposal evaluation without voting",
            },
            {
                "name": "Auto-vote Enabled",
                "auto_vote": False,  # Fixed: Changed to True for auto-vote scenario
                "confidence_threshold": 0.7,
                "description": "Testing proposal evaluation with auto-voting",
            },
            {
                "name": "Low Confidence Threshold",
                "auto_vote": False,
                "confidence_threshold": 0.3,
                "description": "Testing with lower confidence threshold",
            },
        ]

        # Run each scenario
        for scenario in scenarios:
            print(f"\nRunning scenario: {scenario['name']}")
            print(f"Description: {scenario['description']}")

            try:
                if scenario["auto_vote"]:
                    result = await evaluate_and_vote_on_proposal(
                        proposal_id=proposal_id,
                        auto_vote=scenario["auto_vote"],
                        confidence_threshold=scenario["confidence_threshold"],
                        dao_id=dao_id,
                    )
                else:
                    result = await evaluate_proposal_only(
                        proposal_id=proposal_id,
                        wallet_id=UUID("532fd36b-8a9d-4fdd-82d2-25ddcf007488"),
                    )

                # Print the results
                print("\nEvaluation Results:")
                print(f"Success: {result['success']}")
                if result["success"]:
                    print(f"Approval: {result['evaluation']['approve']}")
                    print(f"Confidence: {result['evaluation']['confidence_score']}")
                    print(f"Reasoning: {result['evaluation']['reasoning']}")
                    print(f"Token Usage: {result['token_usage']}")
                    print(f"Cost: ${result['token_costs']['total_cost']:.4f}")

                    if scenario["auto_vote"]:
                        print(f"Auto-voted: {result['auto_voted']}")
                        if result["vote_result"]:
                            print(f"Vote Result: {result['vote_result']}")
                            if result.get("tx_id"):
                                print(f"Transaction ID: {result['tx_id']}")
                else:
                    print(f"Error: {result.get('error', 'Unknown error')}")

            except Exception as e:
                print(f"Error in scenario {scenario['name']}: {e}")

    except Exception as e:
        print(f"Test failed: {e}")
        raise


if __name__ == "__main__":

    # Run the tests
    asyncio.run(test_proposal_evaluation_workflow())
