#!/usr/bin/env python3
"""Test the full DAO proposal evaluation task flow.

This script creates a queue message and runs the actual dao_proposal_evaluation task,
which handles the complete flow including DB updates.

Usage:
    python -m scripts.test_evaluation_task --proposal-id <proposal_id> --wallet-id <wallet_id>

Example:
    python -m scripts.test_evaluation_task --proposal-id f72482e0-a588-456a-a62b-acde7de03acd --wallet-id fa4345cc-333e-4d1f-8070-a393a7ed33f6
"""

import argparse
import asyncio
import sys
from uuid import UUID

from app.backend.factory import backend
from app.backend.models import (
    QueueMessageCreate,
    QueueMessageType,
    VoteFilter,
)
from app.lib.logger import configure_logger
from app.services.infrastructure.job_management.tasks.dao_proposal_evaluation import (
    DAOProposalEvaluationTask,
)
from app.services.infrastructure.job_management.base import (
    JobContext,
    JobType,
    RunnerConfig,
)

logger = configure_logger(__name__)


async def test_evaluation_task(proposal_id: str, wallet_id: str):
    """Test the complete evaluation task flow.

    Args:
        proposal_id: UUID of the proposal to evaluate
        wallet_id: UUID of the wallet to use for evaluation
    """
    print("=" * 80)
    print("DAO PROPOSAL EVALUATION TASK TEST")
    print("=" * 80)

    # Step 1: Verify proposal exists
    print("\n[1/5] Verifying proposal exists...")
    try:
        proposal = backend.get_proposal(UUID(proposal_id))
        if not proposal:
            print(f"ERROR: Proposal {proposal_id} not found")
            return False

        print("Found proposal:")
        print(f"    ID: {proposal.id}")
        print(f"    Title: {proposal.title or 'Untitled'}")
        print(f"    DAO ID: {proposal.dao_id}")
    except Exception as e:
        print(f"ERROR verifying proposal: {e}")
        return False

    # Step 2: Verify wallet exists
    print("\n[2/5] Verifying wallet exists...")
    try:
        wallet = backend.get_wallet(UUID(wallet_id))
        if not wallet:
            print(f"ERROR: Wallet {wallet_id} not found")
            return False

        print("Found wallet:")
        print(f"    ID: {wallet.id}")
        print(f"    Agent ID: {wallet.agent_id}")
        print(f"    Profile ID: {wallet.profile_id}")
    except Exception as e:
        print(f"ERROR verifying wallet: {e}")
        return False

    # Step 3: Check for existing evaluations
    print("\n[3/5] Checking for existing evaluations...")
    try:
        vote_filter = VoteFilter(
            proposal_id=UUID(proposal_id), wallet_id=UUID(wallet_id)
        )
        existing_votes = backend.list_votes(filters=vote_filter)

        if existing_votes:
            print(f"WARNING: Found {len(existing_votes)} existing vote(s):")
            for vote in existing_votes:
                decision = "APPROVE" if vote.answer else "REJECT"
                score = (
                    vote.evaluation_score.get("final_score")
                    if vote.evaluation_score
                    else "N/A"
                )
                print(
                    f"    - Vote ID: {vote.id} | Decision: {decision} | Score: {score}"
                )

            user_input = input("\n    Continue anyway? (y/N): ")
            if user_input.lower() != "y":
                print("    Aborted by user.")
                return False
        else:
            print("No existing evaluations found")
    except Exception as e:
        print(f"ERROR checking votes: {e}")
        return False

    # Step 4: Create queue message for evaluation
    print("\n[4/5] Creating queue message for evaluation task...")
    try:
        queue_type = QueueMessageType.get_or_create("dao_proposal_evaluation")

        message_data = QueueMessageCreate(
            type=queue_type,
            wallet_id=UUID(wallet_id),
            dao_id=proposal.dao_id,
            message={
                "proposal_id": str(proposal_id),
            },
        )

        queue_message = backend.create_queue_message(message_data)
        if not queue_message:
            print("ERROR: Failed to create queue message")
            return False

        print("Created queue message:")
        print(f"    Message ID: {queue_message.id}")
        print(f"    Type: {queue_message.type}")
        print(f"    Wallet ID: {queue_message.wallet_id}")
        print(f"    DAO ID: {queue_message.dao_id}")
    except Exception as e:
        print(f"ERROR creating queue message: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Step 5: Run the evaluation task
    print("\n[5/5] Running DAO proposal evaluation task...")
    print("    This may take 30-60 seconds...")
    try:
        task = DAOProposalEvaluationTask()

        # Create proper JobContext
        job_type = JobType.get_or_create("dao_proposal_evaluation")
        config = RunnerConfig(max_retries=3)
        context = JobContext(
            job_type=job_type, config=config, execution_id="test-execution"
        )

        results = await task._execute_impl(context)

        if not results:
            print("ERROR: Task returned no results")
            return False

        result = results[0]
        print("\nTask completed:")
        print(f"    Success: {result.success}")
        print(f"    Message: {result.message}")
        print(f"    Proposals processed: {result.proposals_processed}")
        print(f"    Proposals evaluated: {result.proposals_evaluated}")

        if result.errors:
            print(f"    Errors: {len(result.errors)}")
            for error in result.errors[:3]:
                print(f"      - {error}")

    except Exception as e:
        print(f"ERROR running task: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Step 6: Verify the vote was created
    print("\n[6/6] Verifying vote was created...")
    try:
        vote_filter = VoteFilter(
            proposal_id=UUID(proposal_id), wallet_id=UUID(wallet_id)
        )
        votes = backend.list_votes(filters=vote_filter)

        if not votes:
            print("ERROR: No votes found after evaluation")
            return False

        # Get the most recent vote
        latest_vote = sorted(votes, key=lambda v: v.created_at, reverse=True)[0]

        print("Vote record verified:")
        print(f"    Vote ID: {latest_vote.id}")
        print(f"    Decision: {'APPROVE' if latest_vote.answer else 'REJECT'}")
        print(
            f"    Score: {latest_vote.evaluation_score.get('final_score') if latest_vote.evaluation_score else 'N/A'}"
        )
        print(f"    Confidence: {latest_vote.confidence}")
        print(f"    Created at: {latest_vote.created_at}")

    except Exception as e:
        print(f"ERROR verifying vote: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Summary
    print("\n" + "=" * 80)
    print("EVALUATION TASK COMPLETED SUCCESSFULLY!")
    print("=" * 80)
    print("\nSummary:")
    print(f"  Proposal: {proposal.title or proposal_id}")
    print(f"  Decision: {'APPROVE' if latest_vote.answer else 'REJECT'}")
    print(
        f"  Score: {latest_vote.evaluation_score.get('final_score') if latest_vote.evaluation_score else 'N/A'}/100"
    )
    print(f"  Vote ID: {latest_vote.id}")
    print("\nThe vote was created by the actual dao_proposal_evaluation task!")
    print("=" * 80)

    return True


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test the full DAO proposal evaluation task",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m scripts.test_evaluation_task --proposal-id f72482e0-a588-456a-a62b-acde7de03acd --wallet-id fa4345cc-333e-4d1f-8070-a393a7ed33f6
        """,
    )

    parser.add_argument(
        "--proposal-id",
        type=str,
        required=True,
        help="UUID of the proposal to evaluate",
    )

    parser.add_argument(
        "--wallet-id",
        type=str,
        required=True,
        help="UUID of the wallet to use for evaluation",
    )

    args = parser.parse_args()

    success = await test_evaluation_task(args.proposal_id, args.wallet_id)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
