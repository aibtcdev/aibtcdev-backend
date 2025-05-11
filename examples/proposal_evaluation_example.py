"""Functional test script for the proposal evaluation workflow.

This script demonstrates the usage of the proposal evaluation workflow
with real-world scenarios. It's not a unit test but rather a functional
test to see the workflow in action.
"""

import asyncio
import binascii
import os
import sys
from uuid import UUID

# Add the project root to Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from backend.factory import backend
from backend.models import (
    ProposalCreate,
    ProposalType,
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
    # parameters = "I Publius.btc will do a $FACES airdrop to as many bitcoin faces holders as possible. I will report back with a confirmation message and proof. Give me a shot."
    parameters = """

Proposal Title: $FACES Airdrop to Bitcoin Faces Holders with Transparent Execution and Community Engagement

Proposer: Publius.btc

Proposal Data:
I, Publius.btc, propose to execute a $FACES airdrop to Bitcoin Faces holders to boost community engagement and reward active participants in the DAO. Due to a limit of 1,000 tokens per proposal, this will be 1 of 10 proposals, each distributing up to 1,000 $FACES tokens. The airdrop will distribute a total of 10,000 $FACES tokens to eligible holders, with a clear execution plan, transparent verification, and measurable outcomes. The proposal aligns with the DAO's mission to promote community activity and token utility. Below are the details:

Objective: Distribute $FACES tokens to Bitcoin Faces holders to incentivize participation, increase governance engagement, and strengthen community ties.
Eligibility Criteria:
Holders of Bitcoin Faces NFTs as of a snapshot date (to be set 7 days after proposal approval).
Minimum holding: 1 Bitcoin Faces NFT.
Exclusion: Wallets flagged for suspicious activity (e.g., wash trading) based on on-chain analysis.
Execution Plan:
Snapshot: Conduct a blockchain snapshot of Bitcoin Faces holders on the specified date, using a third-party tool (e.g., Etherscan or equivalent for Bitcoin-based assets).
Distribution: Distribute 10 $FACES per eligible wallet, up to a total of 1,000 tokens per proposal, via a smart contract to ensure transparency and immutability. This proposal is part of a series of 10 proposals to reach the full 10,000 token distribution.
Timeline:
Day 1–7: Proposal approval and snapshot preparation.
Day 8: Snapshot execution.
Day 9–14: Smart contract deployment and testing.
Day 15: Airdrop distribution.
Day 20: Post-airdrop report published.
Budget and Funding:
Total Cost: 1,000 $FACES tokens for this proposal (valued at $0.10 per token based on current market price, totaling $100). The full airdrop campaign will total 10,000 tokens across 10 proposals.
Additional Costs: $500 for smart contract development, auditing, and gas fees, to be funded from the DAO treasury.
Funding Request: 1,000 $FACES tokens + $500 in stablecoins (e.g., USDC) from the DAO treasury for this proposal.
Cost Justification: The airdrop is cost-effective, targeting active holders to maximize engagement with minimal token dilution. The $500 covers secure execution to mitigate risks.
Verification and Transparency:
Publish the snapshot data and eligible wallet list on the DAO's governance forum.
Share the smart contract address and transaction hashes on-chain for public verification.
Provide a detailed post-airdrop report within 5 days of distribution, including the number of wallets reached, tokens distributed, and community feedback.
Community Benefit:
Inclusivity: All Bitcoin Faces holders are eligible, ensuring broad participation.
Engagement: The airdrop will encourage holders to participate in governance and DAO activities, addressing low governance participation.
Stakeholder Consideration: The plan includes outreach to diverse community segments via the DAO's social channels (e.g., Discord, X) to ensure awareness and feedback.
Alignment with DAO Priorities:
Promotes token utility and community engagement, core to the DAO's mission.
Supports financial prudence by capping costs and providing ROI through increased governance participation (measurable via voting turnout post-airdrop).
Risk Mitigation:
Financial Risk: Limited to 1,000 $FACES and $500 for this proposal, with no ongoing costs. The full campaign is capped at 10,000 tokens and $5,000 across all proposals.
Execution Risk: Smart contract audit to prevent vulnerabilities.
Inclusion Risk: Transparent eligibility criteria to avoid disputes.
Deliverables and ROI:
Deliverables: Snapshot data, smart contract, airdrop distribution, and post-airdrop report.
ROI: Expected 10% increase in governance participation (based on similar airdrop campaigns) and enhanced community sentiment, measurable via forum activity and X posts.
Addressing Past Concerns:
Unlike previous proposals, this includes a detailed execution plan, budget, and verification process.
Responds to feedback on inclusion by defining clear eligibility and outreach strategies.
Aligns with financial priorities by justifying costs and capping token usage.
Commitment:
I will execute the airdrop as outlined, provide regular updates on the DAO's governance forum, and deliver a comprehensive report with proof of distribution. If the proposal is approved, I will collaborate with the DAO's technical and community teams to ensure success.
"""

    # # Convert parameters to JSON string and then hex encode it
    # parameters_hex = "0x" + binascii.hexlify(parameters.encode("utf-8")).decode("utf-8")

    # Create a test proposal
    proposal_data = ProposalCreate(
        dao_id=dao_id,
        type=ProposalType.ACTION,
        parameters=parameters,  # Use hex encoded parameters
        action="send_message",
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

        # Use a consistent test wallet ID
        test_wallet_id = UUID("532fd36b-8a9d-4fdd-82d2-25ddcf007488")

        # Test scenarios
        scenarios = [
            {
                "name": "Evaluation Only",
                "auto_vote": False,
                "confidence_threshold": 0.7,
                "description": "Testing proposal evaluation without voting",
            },
            # {
            #     "name": "Auto-vote Enabled",
            #     "auto_vote": True,  # Corrected: Changed to True for auto-vote scenario
            #     "confidence_threshold": 0.7,
            #     "description": "Testing proposal evaluation with auto-voting",
            # },
            # {
            #     "name": "Low Confidence Threshold",
            #     "auto_vote": False,
            #     "confidence_threshold": 0.3,
            #     "description": "Testing with lower confidence threshold",
            # },
        ]

        # Run each scenario
        for scenario in scenarios:
            print(f"\nRunning scenario: {scenario['name']}")
            print(f"Description: {scenario['description']}")

            try:
                if scenario["auto_vote"]:
                    result = await evaluate_and_vote_on_proposal(
                        proposal_id=proposal_id,
                        wallet_id=test_wallet_id,  # Add wallet_id for auto-vote scenarios
                        auto_vote=scenario["auto_vote"],
                        confidence_threshold=scenario["confidence_threshold"],
                        dao_id=dao_id,
                    )
                else:
                    result = await evaluate_proposal_only(
                        proposal_id=proposal_id,
                        wallet_id=test_wallet_id,  # Use the same consistent wallet ID
                    )

                # Print the results
                print("\nEvaluation Results:")
                print(f"Approval: {result['evaluation'].get('approve', False)}")
                print(f"Confidence: {result['evaluation'].get('confidence_score', 0)}")
                print(
                    f"Reasoning: {result['evaluation'].get('reasoning', 'No reasoning provided')}"
                )

                if "token_usage" in result.get("evaluation", {}):
                    print(f"Total Token Usage: {result['evaluation']['token_usage']}")

                if scenario["auto_vote"]:
                    print(f"Auto-voted: {result.get('auto_voted', False)}")
                    if result.get("vote_result"):
                        print(f"Vote Result: {result['vote_result']}")
                        if result.get("tx_id"):
                            print(f"Transaction ID: {result['tx_id']}")
            except Exception as e:
                print(f"Error in scenario {scenario['name']}: {e}")

    except Exception as e:
        print(f"Test failed: {e}")
        raise


if __name__ == "__main__":

    # Run the tests
    asyncio.run(test_proposal_evaluation_workflow())
