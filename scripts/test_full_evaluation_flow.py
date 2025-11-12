#!/usr/bin/env python3
"""Test the full evaluation flow including DB updates.

This script runs the complete evaluation process:
1. Fetches proposal from DB
2. Runs AI evaluation
3. Creates vote record in DB
4. Verifies all DB updates

Usage:
    python scripts/test_full_evaluation_flow.py --proposal-id <proposal_id> [--wallet-id <wallet_id>]

Example:
    python scripts/test_full_evaluation_flow.py --proposal-id f72482e0-a588-456a-a62b-acde7de03acd
    python scripts/test_full_evaluation_flow.py --proposal-id f72482e0-a588-456a-a62b-acde7de03acd --wallet-id a727521b-ee04-43a2-81e9-4d1130393bf9
"""

import argparse
import asyncio
import sys
from uuid import UUID

from app.backend.factory import backend
from app.backend.models import VoteCreate, VoteFilter
from app.lib.logger import configure_logger
from app.services.ai.simple_workflows.orchestrator import (
    evaluate_proposal_comprehensive,
)

logger = configure_logger(__name__)


async def test_full_evaluation_flow(proposal_id: str, wallet_id: str = None):
    """Test the complete evaluation flow with DB updates.

    Args:
        proposal_id: UUID of the proposal to evaluate
        wallet_id: Optional wallet ID to use for the evaluation
    """
    print("=" * 80)
    print("FULL EVALUATION FLOW TEST")
    print("=" * 80)

    # Step 1: Fetch proposal from DB
    print("\n[1/7] Fetching proposal from database...")
    try:
        proposal = backend.get_proposal(UUID(proposal_id))
        if not proposal:
            print(f"L ERROR: Proposal {proposal_id} not found in database")
            return False

        print(" Found proposal:")
        print(f"    ID: {proposal.id}")
        print(f"    Title: {proposal.title or 'Untitled'}")
        print(f"    DAO ID: {proposal.dao_id}")
        print(f"    Transaction: {proposal.tx_id}")
        print(
            f"    Content: {proposal.content[:150] if proposal.content else 'No content'}..."
        )
    except Exception as e:
        print(f"L ERROR fetching proposal: {e}")
        return False

    # Step 2: Get DAO information
    print("\n[2/7] Fetching DAO information...")
    try:
        dao = backend.get_dao(proposal.dao_id)
        if not dao:
            print(f"L ERROR: DAO {proposal.dao_id} not found")
            return False

        print(" Found DAO:")
        print(f"    Name: {dao.name}")
        print(f"    ID: {dao.id}")
    except Exception as e:
        print(f"L ERROR fetching DAO: {e}")
        return False

    # Step 3: Get or determine wallet
    print("\n[3/7] Getting wallet information...")
    if not wallet_id:
        print("    No wallet ID provided, looking for DAO agent wallet...")
        try:
            agents = backend.list_agents()
            dao_agent = next((a for a in agents if a.dao_id == proposal.dao_id), None)

            if dao_agent and dao_agent.wallet_id:
                wallet_id = str(dao_agent.wallet_id)
                print(f" Found agent wallet: {wallet_id}")
            else:
                print("L ERROR: No agent wallet found for this DAO")
                print("    Please provide a wallet_id parameter")
                return False
        except Exception as e:
            print(f"L ERROR finding wallet: {e}")
            return False
    else:
        print(f"    Using provided wallet ID: {wallet_id}")

    try:
        wallet = backend.get_wallet(UUID(wallet_id))
        if not wallet:
            print(f"L ERROR: Wallet {wallet_id} not found")
            return False

        print(" Wallet details:")
        print(f"    ID: {wallet.id}")
        print(f"    Agent ID: {wallet.agent_id}")
        print(f"    Profile ID: {wallet.profile_id}")
    except Exception as e:
        print(f"L ERROR fetching wallet: {e}")
        return False

    # Step 4: Check for existing evaluations
    print("\n[4/7] Checking for existing evaluations...")
    try:
        vote_filter = VoteFilter(
            proposal_id=UUID(proposal_id), wallet_id=UUID(wallet_id)
        )
        existing_votes = backend.list_votes(filters=vote_filter)

        if existing_votes:
            print(
                f"�  WARNING: Found {len(existing_votes)} existing vote(s) for this proposal/wallet:"
            )
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

            user_input = input("\n    Continue and create another vote? (y/N): ")
            if user_input.lower() != "y":
                print("    Aborted by user.")
                return False
        else:
            print(" No existing evaluations found")
    except Exception as e:
        print(f"L ERROR checking existing votes: {e}")
        return False

    # Step 5: Run AI evaluation
    print("\n[5/7] Running AI evaluation...")
    print("    This may take 30-60 seconds...")
    try:
        evaluation = await evaluate_proposal_comprehensive(
            proposal_content="",  # Fetched from DB
            dao_id=proposal.dao_id,
            proposal_id=proposal.id,
            streaming=False,
        )

        evaluation_data = evaluation.get("evaluation", {})
        decision_str = evaluation_data.get("decision", "REJECT")
        approval = decision_str == "APPROVE"
        final_score = evaluation_data.get("final_score", 0)
        confidence = evaluation_data.get("confidence", 0.0)

        print(" Evaluation completed:")
        print(f"    Decision: {decision_str}")
        print(f"    Score: {final_score}/100")
        print(f"    Confidence: {confidence:.2%}")

        # Show category scores
        categories = ["mission", "value", "originality", "clarity", "safety", "growth"]
        print("    Category scores:")
        for cat in categories:
            cat_data = evaluation_data.get(cat, {})
            if isinstance(cat_data, dict):
                score = cat_data.get("score", "N/A")
                reason = cat_data.get("reason", "")[:60]
                print(f"      - {cat.capitalize()}: {score} | {reason}...")

        # Show failed gates
        failed_gates = evaluation_data.get("failed", [])
        if failed_gates:
            print(f"    Failed gates: {', '.join(failed_gates)}")

    except Exception as e:
        print(f"L ERROR during evaluation: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Step 6: Create vote record in DB
    print("\n[6/7] Creating vote record in database...")
    try:
        # Build reasoning from category reasons
        categories_data = {
            "mission": evaluation_data.get("mission", {}),
            "value": evaluation_data.get("value", {}),
            "originality": evaluation_data.get("originality", {}),
            "clarity": evaluation_data.get("clarity", {}),
            "safety": evaluation_data.get("safety", {}),
            "growth": evaluation_data.get("growth", {}),
        }

        reasoning_parts = []
        for cat_name, cat_data in categories_data.items():
            if isinstance(cat_data, dict) and cat_data.get("reason"):
                reasoning_parts.append(f"{cat_name.title()}: {cat_data.get('reason')}")

        reasoning = (
            "\n\n".join(reasoning_parts) if reasoning_parts else "No reasoning provided"
        )

        if failed_gates:
            reasoning += f"\n\nFailed Gates: {', '.join(failed_gates)}"

        # Convert v2 categories to evaluation_scores format
        evaluation_scores = {
            "categories": [
                {
                    "category": cat_name,
                    "score": cat_data.get("score", 0),
                    "weight": 0,
                    "reasoning": cat_data.get("reason", ""),
                    "evidence": cat_data.get("evidence", []),
                }
                for cat_name, cat_data in categories_data.items()
                if isinstance(cat_data, dict)
            ],
            "final_score": final_score,
            "confidence": confidence,
            "decision": decision_str,
        }

        vote_data = VoteCreate(
            wallet_id=UUID(wallet_id),
            dao_id=proposal.dao_id,
            agent_id=wallet.agent_id if wallet else None,
            proposal_id=UUID(proposal_id),
            answer=approval,
            reasoning=reasoning,
            confidence=confidence,
            prompt="",  # Not available in v2
            cost=0.0,  # Not tracked in v2
            model="x-ai/grok-4-fast",
            profile_id=wallet.profile_id if wallet else None,
            evaluation_score=evaluation_scores,
            flags=failed_gates,
            evaluation=evaluation_data,
        )

        vote = backend.create_vote(vote_data)
        if not vote:
            print("L ERROR: Failed to create vote record")
            return False

        print(" Vote record created:")
        print(f"    Vote ID: {vote.id}")
        print(f"    Decision: {'APPROVE' if vote.answer else 'REJECT'}")
        print(f"    Score: {final_score}")

    except Exception as e:
        print(f"L ERROR creating vote record: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Step 7: Verify DB updates
    print("\n[7/7] Verifying database updates...")
    try:
        # Fetch the vote we just created
        created_vote = backend.get_vote(vote.id)
        if not created_vote:
            print("L ERROR: Could not fetch created vote from DB")
            return False

        print(" Vote verified in database:")
        print(f"    Vote ID: {created_vote.id}")
        print(f"    Proposal ID: {created_vote.proposal_id}")
        print(f"    Wallet ID: {created_vote.wallet_id}")
        print(f"    Answer: {created_vote.answer}")
        print(
            f"    Score: {created_vote.evaluation_score.get('final_score') if created_vote.evaluation_score else 'N/A'}"
        )
        print(f"    Confidence: {created_vote.confidence}")
        print(f"    Created at: {created_vote.created_at}")

        # Check all votes for this proposal
        all_votes_filter = VoteFilter(proposal_id=UUID(proposal_id))
        all_votes = backend.list_votes(filters=all_votes_filter)
        print(f"\n Total votes for this proposal: {len(all_votes)}")

    except Exception as e:
        print(f"L ERROR verifying DB updates: {e}")
        return False

    # Summary
    print("\n" + "=" * 80)
    print(" EVALUATION FLOW COMPLETED SUCCESSFULLY!")
    print("=" * 80)
    print("\nSummary:")
    print(f"  Proposal: {proposal.title or proposal_id}")
    print(f"  DAO: {dao.name}")
    print(f"  Decision: {decision_str}")
    print(f"  Score: {final_score}/100")
    print(f"  Confidence: {confidence:.2%}")
    print(f"  Vote ID: {vote.id}")
    print("\nYou can view this vote at:")
    print(f"  Database: votes table, ID = {vote.id}")
    print("=" * 80)

    return True


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test the full evaluation flow including DB updates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic evaluation (auto-finds agent wallet)
  python scripts/test_full_evaluation_flow.py --proposal-id f72482e0-a588-456a-a62b-acde7de03acd

  # With specific wallet
  python scripts/test_full_evaluation_flow.py --proposal-id f72482e0-a588-456a-a62b-acde7de03acd --wallet-id a727521b-ee04-43a2-81e9-4d1130393bf9
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
        required=False,
        help="UUID of the wallet to use for evaluation (optional - will auto-find agent wallet if not provided)",
    )

    args = parser.parse_args()

    success = await test_full_evaluation_flow(args.proposal_id, args.wallet_id)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
