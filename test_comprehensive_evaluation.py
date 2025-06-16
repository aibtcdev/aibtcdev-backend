#!/usr/bin/env python3
"""
Simple CLI test script for comprehensive proposal evaluation workflow.

This test uses the new ComprehensiveEvaluatorAgent that performs all evaluations
(core, financial, historical, social, and reasoning) in a single LLM pass instead
of the multi-agent workflow.

Usage:
    python test_comprehensive_evaluation.py --proposal-id "123e4567-e89b-12d3-a456-426614174000"
    python test_comprehensive_evaluation.py --proposal-id "123e4567-e89b-12d3-a456-426614174000" --wallet-id "456e7890-e89b-12d3-a456-426614174001" --auto-vote
    python test_comprehensive_evaluation.py --proposal-id "123e4567-e89b-12d3-a456-426614174000" --debug-level 2
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

from services.ai.workflows.comprehensive_evaluation import (
    evaluate_and_vote_on_proposal_comprehensive,
)


def parse_uuid(value: str) -> Optional[UUID]:
    """Parse a UUID string, return None if invalid."""
    try:
        return UUID(value) if value else None
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid UUID format: {value}")


async def main():
    parser = argparse.ArgumentParser(
        description="Test comprehensive proposal evaluation workflow (single-agent)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic comprehensive evaluation (no voting)
  python test_comprehensive_evaluation.py --proposal-id "12345678-1234-5678-9012-123456789abc"
  
  # Comprehensive evaluation with auto-voting
  python test_comprehensive_evaluation.py --proposal-id "12345678-1234-5678-9012-123456789abc" \\
    --wallet-id "87654321-4321-8765-2109-987654321cba" --auto-vote
  
  # Verbose debugging
  python test_comprehensive_evaluation.py --proposal-id "12345678-1234-5678-9012-123456789abc" \\
    --debug-level 2
  
  # Compare with multi-agent workflow
  python test_comprehensive_evaluation.py --proposal-id "12345678-1234-5678-9012-123456789abc" \\
    --compare-with-multi-agent
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

    parser.add_argument(
        "--compare-with-multi-agent",
        action="store_true",
        help="Also run multi-agent evaluation for comparison",
    )

    args = parser.parse_args()

    print("🚀 Starting Comprehensive Proposal Evaluation Test")
    print("=" * 60)
    print(f"Proposal ID: {args.proposal_id}")
    print(f"Wallet ID: {args.wallet_id}")
    print(f"Agent ID: {args.agent_id}")
    print(f"DAO ID: {args.dao_id}")
    print(f"Auto Vote: {args.auto_vote and not args.evaluation_only}")
    print(f"Confidence Threshold: {args.confidence_threshold}")
    print(f"Debug Level: {args.debug_level}")
    print(f"Evaluation Only: {args.evaluation_only}")
    print(f"Compare with Multi-Agent: {args.compare_with_multi_agent}")
    print("=" * 60)
    print("🧠 Using ComprehensiveEvaluatorAgent (Single LLM Pass)")
    print("=" * 60)

    try:
        # Run comprehensive evaluation
        if args.evaluation_only:
            print("🔍 Running comprehensive evaluation only...")
            result = await evaluate_and_vote_on_proposal_comprehensive(
                proposal_id=args.proposal_id,
                wallet_id=args.wallet_id,
                agent_id=args.agent_id,
                dao_id=args.dao_id,
                auto_vote=False,
            )
        else:
            print("🔍 Running comprehensive evaluation with voting option...")
            result = await evaluate_and_vote_on_proposal_comprehensive(
                proposal_id=args.proposal_id,
                wallet_id=args.wallet_id,
                agent_id=args.agent_id,
                auto_vote=args.auto_vote,
                confidence_threshold=args.confidence_threshold,
                dao_id=args.dao_id,
                debug_level=args.debug_level,
            )

        print("\n✅ Comprehensive Evaluation Complete!")
        print("=" * 60)

        # Pretty print the result
        if "error" in result:
            print(f"❌ Error: {result['error']}")
        else:
            evaluation = result.get("evaluation", {})
            vote_result = result.get("vote_result")
            message = result.get("message", "")

            print("📊 Comprehensive Evaluation Results:")
            if evaluation:
                print(
                    f"   • Approval: {'✅ APPROVE' if evaluation.get('approve') else '❌ REJECT'}"
                )
                print(f"   • Confidence: {evaluation.get('confidence_score', 0):.2f}")
                print(
                    f"   • Evaluation Type: {evaluation.get('evaluation_type', 'unknown')}"
                )

                # Show reasoning (truncated for readability)
                reasoning = evaluation.get("reasoning", "N/A")
                if len(reasoning) > 500:
                    reasoning = reasoning[:500] + "... (truncated)"
                print(f"   • Reasoning: {reasoning}")

                scores = evaluation.get("scores", {})
                if scores:
                    print("   • Detailed Scores:")
                    for score_type, score_value in scores.items():
                        print(f"     - {score_type.title()}: {score_value}")

                flags = evaluation.get("flags", [])
                if flags:
                    print(f"   • Flags: {', '.join(flags[:5])}")  # Show first 5 flags
                    if len(flags) > 5:
                        print(f"     ... and {len(flags) - 5} more flags")

                token_usage = evaluation.get("token_usage", {})
                if token_usage:
                    print("   • Token Usage:")
                    print(f"     - Input: {token_usage.get('input_tokens', 0):,}")
                    print(f"     - Output: {token_usage.get('output_tokens', 0):,}")
                    print(f"     - Total: {token_usage.get('total_tokens', 0):,}")

                images_processed = evaluation.get("images_processed", 0)
                if images_processed > 0:
                    print(f"   • Images Processed: {images_processed}")

            if vote_result:
                print("\n🗳️  Voting Results:")
                print(f"   • Status: {vote_result}")
            elif args.auto_vote and not args.evaluation_only:
                print(f"\n🗳️  Voting: {message}")

        # Optional comparison with multi-agent workflow
        if args.compare_with_multi_agent:
            print("\n" + "=" * 60)
            print("🔄 Running Multi-Agent Evaluation for Comparison...")
            print("=" * 60)

            try:
                # Import the original evaluation function
                from services.ai.workflows.proposal_evaluation import (
                    evaluate_and_vote_on_proposal,
                )

                comparison_result = await evaluate_and_vote_on_proposal(
                    proposal_id=args.proposal_id,
                    wallet_id=args.wallet_id,
                    agent_id=args.agent_id,
                    dao_id=args.dao_id,
                    auto_vote=False,  # Don't vote twice
                    debug_level=args.debug_level,
                )

                print("📊 Multi-Agent Evaluation Results:")
                comparison_eval = comparison_result.get("evaluation", {})
                if comparison_eval:
                    print(
                        f"   • Approval: {'✅ APPROVE' if comparison_eval.get('approve') else '❌ REJECT'}"
                    )
                    print(
                        f"   • Confidence: {comparison_eval.get('confidence_score', 0):.2f}"
                    )

                    comp_scores = comparison_eval.get("scores", {})
                    if comp_scores:
                        print("   • Detailed Scores:")
                        for score_type, score_value in comp_scores.items():
                            print(f"     - {score_type.title()}: {score_value}")

                    comp_token_usage = comparison_eval.get("token_usage", {})
                    if comp_token_usage:
                        print("   • Token Usage:")
                        print(
                            f"     - Total: {comp_token_usage.get('total_tokens', 0):,}"
                        )

                # Show comparison summary
                print("\n🔍 Comparison Summary:")
                if evaluation and comparison_eval:
                    comp_decision = "Approve" if evaluation.get("approve") else "Reject"
                    multi_decision = (
                        "Approve" if comparison_eval.get("approve") else "Reject"
                    )
                    decisions_match = comp_decision == multi_decision

                    print(
                        f"   • Decisions Match: {'✅ YES' if decisions_match else '❌ NO'}"
                    )
                    print(f"     - Comprehensive: {comp_decision}")
                    print(f"     - Multi-Agent: {multi_decision}")

                    comp_confidence = evaluation.get("confidence_score", 0)
                    multi_confidence = comparison_eval.get("confidence_score", 0)
                    confidence_diff = abs(comp_confidence - multi_confidence)

                    print(f"   • Confidence Difference: {confidence_diff:.3f}")
                    print(f"     - Comprehensive: {comp_confidence:.3f}")
                    print(f"     - Multi-Agent: {multi_confidence:.3f}")

                    comp_tokens = evaluation.get("token_usage", {}).get(
                        "total_tokens", 0
                    )
                    multi_tokens = comparison_eval.get("token_usage", {}).get(
                        "total_tokens", 0
                    )
                    if comp_tokens > 0 and multi_tokens > 0:
                        token_savings = (
                            (multi_tokens - comp_tokens) / multi_tokens
                        ) * 100
                        print(
                            f"   • Token Efficiency: {token_savings:.1f}% {'savings' if token_savings > 0 else 'increase'}"
                        )
                        print(f"     - Comprehensive: {comp_tokens:,} tokens")
                        print(f"     - Multi-Agent: {multi_tokens:,} tokens")

            except Exception as e:
                print(f"❌ Error running multi-agent comparison: {str(e)}")

        print("\n📄 Full Comprehensive Result JSON:")
        print(json.dumps(result, indent=2, default=str))

    except Exception as e:
        print(f"\n❌ Error during comprehensive evaluation: {str(e)}")
        if args.debug_level >= 1:
            import traceback

            traceback.print_exc()
        sys.exit(1)

    print("\n🎉 Comprehensive evaluation test completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
