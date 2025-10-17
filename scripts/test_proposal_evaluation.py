#!/usr/bin/env python3
"""
Simple CLI test script for comprehensive proposal evaluation.

This test uses the comprehensive proposal evaluation workflow that analyzes
proposals using a single comprehensive agent with multiple evaluation criteria.

Usage:
    python test_proposal_evaluation.py --proposal-id "123e4567-e89b-12d3-a456-426614174000" --proposal-data "Some proposal content"
    python test_proposal_evaluation.py --proposal-id "123e4567-e89b-12d3-a456-426614174000" --proposal-data "Proposal content" --debug-level 2
    python test_proposal_evaluation.py --proposal-id "123e4567-e89b-12d3-a456-426614174000" --debug-level 2  # Lookup from database
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from uuid import UUID

# Add the parent directory (root) to the path to import from app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.ai.simple_workflows.evaluation import evaluate_proposal
from app.services.ai.simple_workflows.prompts.loader import load_prompt
from app.backend.factory import get_backend


class Tee(object):
    def __init__(self, *files):
        self.files = files

    def write(self, data):
        for f in self.files:
            f.write(data)
            f.flush()

    def flush(self):
        for f in self.files:
            f.flush()


async def main():
    parser = argparse.ArgumentParser(
        description="Test comprehensive proposal evaluation workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic comprehensive evaluation with proposal data
  python test_proposal_evaluation.py --proposal-id "12345678-1234-5678-9012-123456789abc" \\
    --proposal-data "Proposal to fund development of new feature"
  
  # Lookup proposal from database
  python test_proposal_evaluation.py --proposal-id "12345678-1234-5678-9012-123456789abc" \\
    --debug-level 2
  
  # Verbose debugging
  python test_proposal_evaluation.py --proposal-id "12345678-1234-5678-9012-123456789abc" \\
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
        "--dao-id",
        type=str,
        help="ID of the DAO",
    )

    parser.add_argument(
        "--debug-level",
        type=int,
        choices=[0, 1, 2],
        default=0,
        help="Debug level: 0=normal, 1=verbose, 2=very verbose (default: 0)",
    )

    parser.add_argument(
        "--save-output",
        action="store_true",
        help="Save output to timestamped JSON and TXT files",
    )

    args = parser.parse_args()

    if args.save_output:
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        json_filename = f"proposal_evaluation_output_{timestamp}.json"
        log_filename = f"proposal_evaluation_full_{timestamp}.txt"
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        log_f = open(log_filename, 'w')
        sys.stdout = Tee(original_stdout, log_f)
        sys.stderr = Tee(original_stderr, log_f)

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
    print(f"DAO ID: {args.dao_id}")
    print(f"Debug Level: {args.debug_level}")
    print("=" * 60)

    try:
        # Convert dao_id to UUID if provided
        dao_uuid = None
        if args.dao_id:
            try:
                dao_uuid = UUID(args.dao_id)
            except ValueError as e:
                print(f"❌ Warning: Invalid DAO ID format: {e}")

        # Determine prompt type based on DAO name
        prompt_type = "evaluation"  # Default
        custom_system_prompt = None
        custom_user_prompt = None

        if dao_uuid:
            backend = get_backend()
            dao = backend.get_dao(dao_uuid)
            if dao:
                if dao.name == "ELONBTC":
                    prompt_type = "evaluation_elonbtc"
                    print(f"🎯 Using ELONBTC-specific prompts for DAO {dao.name}")
                elif dao.name in ["AIBTC", "AITEST", "AITEST2", "AITEST3", "AITEST4"]:
                    prompt_type = "evaluation_aibtc"
                    print(f"🎯 Using AIBTC-specific prompts for DAO {dao.name}")
                else:
                    print(f"📝 Using general prompts for DAO {dao.name}")
            else:
                print("📝 Using general prompts (DAO not found)")
        else:
            print("📝 Using general prompts (no DAO ID provided)")

        # Load prompts based on determined type
        custom_system_prompt = load_prompt(prompt_type, "system")
        custom_user_prompt = load_prompt(prompt_type, "user_template")

        # Run comprehensive evaluation
        print("🔍 Running comprehensive evaluation...")
        result = await evaluate_proposal(
            proposal_content=proposal_content,
            dao_id=dao_uuid,
            proposal_id=args.proposal_id,
            custom_system_prompt=custom_system_prompt,
            custom_user_prompt=custom_user_prompt,
        )

        print("\n✅ Comprehensive Evaluation Complete!")
        print("=" * 60)

        # Pretty print the result
        print("📊 Comprehensive Evaluation Results:")
        print(f"   • Decision: {'✅ APPROVE' if result.decision else '❌ REJECT'}")
        print(f"   • Final Score: {result.final_score}")

        # Show explanation (truncated for readability)
        explanation = result.explanation or "N/A"
        if len(explanation) > 500:
            explanation = explanation[:500] + "... (truncated)"
        print(f"   • Explanation: {explanation}")

        # Show summary
        summary = result.summary or "N/A"
        if len(summary) > 300:
            summary = summary[:300] + "... (truncated)"
        print(f"   • Summary: {summary}")

        # Show category scores
        if result.categories:
            print("   • Category Scores:")
            for category in result.categories:
                if hasattr(category, "category") and hasattr(category, "score"):
                    print(f"     - {category.category}: {category.score}")
                    if hasattr(category, "weight"):
                        print(f"       Weight: {category.weight:.1%}")
                    if hasattr(category, "reasoning") and category.reasoning:
                        print(
                            f"       Reasoning: {'; '.join(category.reasoning[:2])}"
                        )  # Show first 2 points

        # Show flags
        if result.flags:
            print(f"   • Flags: {', '.join(result.flags[:5])}")  # Show first 5 flags
            if len(result.flags) > 5:
                print(f"     ... and {len(result.flags) - 5} more flags")

        # Show token usage
        if result.token_usage:
            print("   • Token Usage:")
            print(f"     - Input: {result.token_usage.get('input_tokens', 0):,}")
            print(f"     - Output: {result.token_usage.get('output_tokens', 0):,}")
            print(f"     - Total: {result.token_usage.get('total_tokens', 0):,}")

        # Show images processed
        if result.images_processed > 0:
            print(f"   • Images Processed: {result.images_processed}")

        print("\n📄 Full Result JSON:")
        # Convert result to dictionary for JSON serialization
        result_dict = {
            "decision": result.decision,
            "final_score": result.final_score,
            "explanation": result.explanation,
            "summary": result.summary,
            "categories": [
                {
                    "category": getattr(cat, "category", "Unknown"),
                    "score": getattr(cat, "score", 0),
                    "weight": getattr(cat, "weight", 0.0),
                    "reasoning": getattr(cat, "reasoning", []),
                }
                for cat in (result.categories or [])
            ],
            "flags": result.flags or [],
            "token_usage": result.token_usage or {},
            "images_processed": result.images_processed,
        }
        print(json.dumps(result_dict, indent=2, default=str))

        if args.save_output:
            with open(json_filename, 'w') as f:
                json.dump(result_dict, f, indent=2, default=str)
            print(f"✅ Results saved to {json_filename}")
            print(f"✅ Full output captured in {log_filename}")

    except Exception as e:
        print(f"\n❌ Error during comprehensive evaluation: {str(e)}")
        if args.debug_level >= 1:
            import traceback

            traceback.print_exc()
        sys.exit(1)

    print("\n🎉 Comprehensive evaluation test completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
