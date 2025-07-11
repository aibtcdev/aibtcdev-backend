#!/usr/bin/env python3
"""
Simple CLI test script for proposal evaluation workflow (multi-agent).

This test uses the multi-agent ProposalEvaluationWorkflow that runs multiple
specialized agents (core, financial, historical, social, reasoning) in sequence.

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
from uuid import UUID

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.ai.simple_workflows.evaluation import evaluate_proposal
from app.backend.factory import get_backend


async def main():
    parser = argparse.ArgumentParser(
        description="Test proposal evaluation workflow (multi-agent)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic multi-agent evaluation with proposal data
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
    proposal_content = args.proposal_content
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

    print("🚀 Starting Multi-Agent Proposal Evaluation Test")
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
    print("🧠 Using Multi-Agent ProposalEvaluationWorkflow")
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

        # Run multi-agent evaluation
        print("🔍 Running multi-agent evaluation...")
        result = await evaluate_proposal(
            proposal_id=args.proposal_id,
            proposal_content=proposal_content,
            config=config,
            dao_id=args.dao_id,
            agent_id=args.agent_id,
            profile_id=args.profile_id,
        )

        print("\n✅ Multi-Agent Evaluation Complete!")
        print("=" * 60)

        # Pretty print the result
        if "error" in result:
            print(f"❌ Error: {result['error']}")
        else:
            print("📊 Multi-Agent Evaluation Results:")
            print(
                f"   • Approval: {'✅ APPROVE' if result.get('approve') else '❌ REJECT'}"
            )
            print(f"   • Overall Score: {result.get('overall_score', 0)}")
            print(f"   • Evaluation Type: {result.get('evaluation_type', 'unknown')}")

            # Show reasoning (truncated for readability)
            reasoning = result.get("reasoning", "N/A")
            if len(reasoning) > 500:
                reasoning = reasoning[:500] + "... (truncated)"
            print(f"   • Reasoning: {reasoning}")

            scores = result.get("scores", {})
            if scores:
                print("   • Detailed Scores:")
                for score_type, score_value in scores.items():
                    print(f"     - {score_type.title()}: {score_value}")

            flags = result.get("flags", [])
            if flags:
                print(f"   • Flags: {', '.join(flags[:5])}")  # Show first 5 flags
                if len(flags) > 5:
                    print(f"     ... and {len(flags) - 5} more flags")

            token_usage = result.get("token_usage", {})
            if token_usage:
                print("   • Token Usage:")
                print(f"     - Input: {token_usage.get('input_tokens', 0):,}")
                print(f"     - Output: {token_usage.get('output_tokens', 0):,}")
                print(f"     - Total: {token_usage.get('total_tokens', 0):,}")

            workflow_step = result.get("workflow_step", "unknown")
            completed_steps = result.get("completed_steps", [])
            if workflow_step or completed_steps:
                print("   • Workflow Progress:")
                print(f"     - Current Step: {workflow_step}")
                if completed_steps:
                    print(f"     - Completed Steps: {', '.join(completed_steps)}")

            summaries = result.get("summaries", {})
            if summaries and args.debug_level >= 1:
                print("   • Summaries:")
                for summary_type, summary_text in summaries.items():
                    truncated_summary = (
                        summary_text[:200] + "..."
                        if len(summary_text) > 200
                        else summary_text
                    )
                    print(
                        f"     - {summary_type.replace('_', ' ').title()}: {truncated_summary}"
                    )

        print("\n📄 Full Result JSON:")
        print(json.dumps(result, indent=2, default=str))

    except Exception as e:
        print(f"\n❌ Error during multi-agent evaluation: {str(e)}")
        if args.debug_level >= 1:
            import traceback

            traceback.print_exc()
        sys.exit(1)

    print("\n🎉 Multi-agent evaluation test completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
