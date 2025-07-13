#!/usr/bin/env python3
"""
Simple CLI test script for comprehensive proposal evaluation workflow.

This test uses the ComprehensiveEvaluatorAgent that performs all evaluations
(core, financial, historical, social, and reasoning) in a single LLM pass.

Usage:
    python scripts/test_comprehensive_evaluation.py --proposal-id "123e4567-e89b-12d3-a456-426614174000" --proposal-data "Some proposal content"
    python scripts/test_comprehensive_evaluation.py --proposal-id "123e4567-e89b-12d3-a456-426614174000" --proposal-data "Proposal content" --debug-level 2
    python scripts/test_comprehensive_evaluation.py --proposal-id "123e4567-e89b-12d3-a456-426614174000" --debug-level 2  # Lookup from database
"""

import argparse
import asyncio
import json
import os
import sys
from uuid import UUID

# Add the parent directory (project root) to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.ai.simple_workflows import evaluate_proposal_comprehensive
from app.backend.factory import get_backend


async def main():
    parser = argparse.ArgumentParser(
        description="Test comprehensive proposal evaluation workflow (single-agent)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic comprehensive evaluation with proposal data
  python scripts/test_comprehensive_evaluation.py --proposal-id "12345678-1234-5678-9012-123456789abc" \\
    --proposal-data "Proposal to fund development of new feature"
  
  # Lookup proposal from database
  python scripts/test_comprehensive_evaluation.py --proposal-id "12345678-1234-5678-9012-123456789abc" \\
    --debug-level 2
  
  # Verbose debugging
  python scripts/test_comprehensive_evaluation.py --proposal-id "12345678-1234-5678-9012-123456789abc" \\
    --proposal-data "Proposal content" --debug-level 2
        """,
    )

    # Required arguments
    parser.add_argument(
        "--proposal-id",
        type=str,
        required=True,
        help="ID of the proposal to evaluate",
    )

    parser.add_argument(
        "--proposal-data",
        type=str,
        required=False,
        help="Content/data of the proposal to evaluate (optional - will lookup from database if not provided)",
    )

    # Optional arguments
    parser.add_argument(
        "--agent-id",
        type=str,
        help="ID of the agent",
    )

    parser.add_argument(
        "--dao-id",
        type=str,
        help="ID of the DAO",
    )

    parser.add_argument(
        "--profile-id",
        type=str,
        help="ID of the profile",
    )

    parser.add_argument(
        "--debug-level",
        type=int,
        choices=[0, 1, 2],
        default=0,
        help="Debug level: 0=normal, 1=verbose, 2=very verbose (default: 0)",
    )

    parser.add_argument(
        "--model-name",
        type=str,
        help="Override the default model name for evaluation",
    )

    args = parser.parse_args()

    # If proposal_content is not provided, look it up from the database
    proposal_content = args.proposal_data
    if not proposal_content:
        print("📋 No proposal data provided, looking up from database...")
        try:
            backend = get_backend()
            proposal_uuid = UUID(args.proposal_id)
            proposal = backend.get_proposal(proposal_uuid)

            if not proposal:
                print(
                    f"❌ Error: Proposal with ID {args.proposal_id} not found in database"
                )
                sys.exit(1)

            if not proposal.content:
                print(f"❌ Error: Proposal {args.proposal_id} has no content")
                sys.exit(1)

            proposal_content = proposal.content
            print(f"✅ Found proposal in database: {proposal.title or 'Untitled'}")

            # Update DAO ID if not provided and available in proposal
            if not args.dao_id and proposal.dao_id:
                args.dao_id = str(proposal.dao_id)
                print(f"✅ Using DAO ID from proposal: {args.dao_id}")

        except ValueError as e:
            print(f"❌ Error: Invalid proposal ID format: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error looking up proposal: {e}")
            sys.exit(1)

    print("🚀 Starting Comprehensive Proposal Evaluation Test")
    print("=" * 60)
    print(f"Proposal ID: {args.proposal_id}")
    print(
        f"Proposal Data: {proposal_content[:100]}{'...' if len(proposal_content) > 100 else ''}"
    )
    print(f"Agent ID: {args.agent_id}")
    print(f"DAO ID: {args.dao_id}")
    print(f"Profile ID: {args.profile_id}")
    print(f"Debug Level: {args.debug_level}")
    print(f"Model Name: {args.model_name}")
    print("=" * 60)
    print("🧠 Using ComprehensiveEvaluatorAgent (Single LLM Pass)")
    print("=" * 60)

    try:
        # Set up config
        config = {
            "debug_level": args.debug_level,
        }

        if args.model_name:
            config["model_name"] = args.model_name

        if args.debug_level >= 1:
            # For verbose debugging, customize agent settings
            config["approval_threshold"] = 70
            config["veto_threshold"] = 30
            config["consensus_threshold"] = 10

        # Run comprehensive evaluation
        print("🔍 Running comprehensive evaluation...")
        result = await evaluate_proposal_comprehensive(
            proposal_content=proposal_content,
            dao_id=UUID(args.dao_id) if args.dao_id else None,
            proposal_id=args.proposal_id,
            streaming=False,
        )

        print("\n✅ Comprehensive Evaluation Complete!")
        print("=" * 60)

        # Pretty print the result
        if "error" in result:
            print(f"❌ Error: {result['error']}")
        else:
            evaluation = result.get("evaluation", {})
            print("📊 Comprehensive Evaluation Results:")
            print(
                f"   • Approval: {'✅ APPROVE' if evaluation.get('decision') else '❌ REJECT'}"
            )
            print(f"   • Overall Score: {evaluation.get('final_score', 0)}")
            print("   • Evaluation Type: comprehensive")

            # Show reasoning (truncated for readability)
            reasoning = evaluation.get("explanation", "N/A")
            if len(reasoning) > 500:
                reasoning = reasoning[:500] + "... (truncated)"
            print(f"   • Reasoning: {reasoning}")

            # Show category scores
            categories = evaluation.get("categories", [])
            if categories:
                print("   • Category Scores:")
                for category in categories:
                    print(
                        f"     - {category.get('category', 'Unknown')}: {category.get('score', 0)} (weight: {category.get('weight', 0)})"
                    )

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

            # Show summary
            summary = evaluation.get("summary", "")
            if summary and args.debug_level >= 1:
                print("   • Summary:")
                truncated_summary = (
                    summary[:200] + "..." if len(summary) > 200 else summary
                )
                print(f"     {truncated_summary}")

            # Show detailed category reasoning if verbose
            if categories and args.debug_level >= 2:
                print("   • Detailed Category Reasoning:")
                for category in categories:
                    print(f"     - {category.get('category', 'Unknown')}:")
                    for reason in category.get("reasoning", []):
                        truncated_reason = (
                            reason[:150] + "..." if len(reason) > 150 else reason
                        )
                        print(f"       * {truncated_reason}")

        print("\n📄 Full Result JSON:")
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
