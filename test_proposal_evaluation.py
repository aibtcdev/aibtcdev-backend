#!/usr/bin/env python3
"""
Simple CLI test script for proposal evaluation workflow.

Usage:
    python test_proposal_evaluation.py --proposal-id "123e4567-e89b-12d3-a456-426614174000"
    python test_proposal_evaluation.py --proposal-id "123e4567-e89b-12d3-a456-426614174000" --wallet-id "456e7890-e89b-12d3-a456-426614174001" --auto-vote
    python test_proposal_evaluation.py --proposal-id "123e4567-e89b-12d3-a456-426614174000" --debug-level 2
"""

import argparse
import asyncio
import json

# Add the project root to Python path
import os
import sys
from typing import Optional
from uuid import UUID

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.workflows.proposal_evaluation import (
    evaluate_and_vote_on_proposal,
    evaluate_proposal_only,
)


def parse_uuid(value: str) -> Optional[UUID]:
    """Parse a UUID string, return None if invalid."""
    try:
        return UUID(value) if value else None
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid UUID format: {value}")


async def main():
    parser = argparse.ArgumentParser(
        description="Test proposal evaluation workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic evaluation (no voting)
  python test_proposal_evaluation.py --proposal-id "12345678-1234-5678-9012-123456789abc"
  
  # Evaluation with auto-voting
  python test_proposal_evaluation.py --proposal-id "12345678-1234-5678-9012-123456789abc" \\
    --wallet-id "87654321-4321-8765-2109-987654321cba" --auto-vote
  
  # Verbose debugging
  python test_proposal_evaluation.py --proposal-id "12345678-1234-5678-9012-123456789abc" \\
    --debug-level 2
        """,
    )

    # Required arguments
    parser.add_argument(
        "--proposal-id",
        type=parse_uuid,
        required=True,
        help="UUID of the proposal to evaluate",
    )

    # Optional arguments
    parser.add_argument(
        "--wallet-id",
        type=parse_uuid,
        help="UUID of the wallet (required for voting)",
    )

    parser.add_argument(
        "--agent-id",
        type=parse_uuid,
        help="UUID of the agent",
    )

    parser.add_argument(
        "--dao-id",
        type=parse_uuid,
        help="UUID of the DAO",
    )

    parser.add_argument(
        "--auto-vote",
        action="store_true",
        help="Enable automatic voting based on evaluation",
    )

    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.7,
        help="Confidence threshold for auto-voting (default: 0.7)",
    )

    parser.add_argument(
        "--debug-level",
        type=int,
        choices=[0, 1, 2],
        default=0,
        help="Debug level: 0=normal, 1=verbose, 2=very verbose (default: 0)",
    )

    parser.add_argument(
        "--evaluation-only",
        action="store_true",
        help="Only evaluate, never vote (overrides --auto-vote)",
    )

    args = parser.parse_args()

    print("🚀 Starting Proposal Evaluation Test")
    print("=" * 50)
    print(f"Proposal ID: {args.proposal_id}")
    print(f"Wallet ID: {args.wallet_id}")
    print(f"Agent ID: {args.agent_id}")
    print(f"DAO ID: {args.dao_id}")
    print(f"Auto Vote: {args.auto_vote and not args.evaluation_only}")
    print(f"Confidence Threshold: {args.confidence_threshold}")
    print(f"Debug Level: {args.debug_level}")
    print(f"Evaluation Only: {args.evaluation_only}")
    print("=" * 50)

    try:
        if args.evaluation_only:
            print("🔍 Running evaluation only...")
            result = await evaluate_proposal_only(
                proposal_id=args.proposal_id,
                wallet_id=args.wallet_id,
                agent_id=args.agent_id,
                dao_id=args.dao_id,
            )
        else:
            print("🔍 Running evaluation with voting option...")
            result = await evaluate_and_vote_on_proposal(
                proposal_id=args.proposal_id,
                wallet_id=args.wallet_id,
                agent_id=args.agent_id,
                auto_vote=args.auto_vote,
                confidence_threshold=args.confidence_threshold,
                dao_id=args.dao_id,
                debug_level=args.debug_level,
            )

        print("\n✅ Evaluation Complete!")
        print("=" * 50)

        # Pretty print the result
        if "error" in result:
            print(f"❌ Error: {result['error']}")
        else:
            evaluation = result.get("evaluation", {})
            vote_result = result.get("vote_result")
            message = result.get("message", "")

            print(f"📊 Evaluation Results:")
            if evaluation:
                print(
                    f"   • Approval: {'✅ APPROVE' if evaluation.get('approve') else '❌ REJECT'}"
                )
                print(f"   • Confidence: {evaluation.get('confidence_score', 0):.2f}")
                print(f"   • Reasoning: {evaluation.get('reasoning', 'N/A')}")

                scores = evaluation.get("scores", {})
                if scores:
                    print(f"   • Detailed Scores:")
                    for score_type, score_value in scores.items():
                        print(f"     - {score_type.title()}: {score_value}")

                flags = evaluation.get("flags", [])
                if flags:
                    print(f"   • Flags: {', '.join(flags)}")

                token_usage = evaluation.get("token_usage", {})
                if token_usage:
                    print(f"   • Token Usage:")
                    print(f"     - Input: {token_usage.get('input_tokens', 0)}")
                    print(f"     - Output: {token_usage.get('output_tokens', 0)}")
                    print(f"     - Total: {token_usage.get('total_tokens', 0)}")

            if vote_result:
                print(f"\n🗳️  Voting Results:")
                print(f"   • Status: {vote_result}")
            elif args.auto_vote and not args.evaluation_only:
                print(f"\n🗳️  Voting: {message}")

        print("\n📄 Full Result JSON:")
        print(json.dumps(result, indent=2, default=str))

    except Exception as e:
        print(f"\n❌ Error during evaluation: {str(e)}")
        if args.debug_level >= 1:
            import traceback

            traceback.print_exc()
        sys.exit(1)

    print("\n🎉 Test completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
