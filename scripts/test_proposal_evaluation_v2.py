#!/usr/bin/env python3
"""
Enhanced CLI test script for comprehensive proposal evaluations (V2).

This version supports evaluating multiple proposals concurrently,
with per-proposal logging and JSON outputs, plus a consolidated summary.

Usage:
    python test_proposal_evaluation_v2.py --proposal-id "123e4567-e89b-12d3-a456-426614174000" --debug-level 2
    python test_proposal_evaluation_v2.py --proposal-id "ID1" --proposal-id "ID2" --max-concurrent 3 --save-output
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import List, Dict, Any
from uuid import UUID

# Add the parent directory (root) to the path to import from app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.lib.logger import StructuredFormatter, setup_uvicorn_logging
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


def short_uuid(uuid_str: str) -> str:
    """Get first 8 characters of UUID for file naming."""
    return uuid_str[:8]


async def evaluate_single_proposal(
    proposal_id: str,
    index: int,
    dao_id: str | None,
    debug_level: int,
    timestamp: str,
    save_output: bool,
    semaphore: asyncio.Semaphore,
    original_stdout,
    original_stderr,
) -> Dict[str, Any]:
    """Evaluate a single proposal with output redirection."""
    async with semaphore:
        try:
            proposal_uuid = UUID(proposal_id)

            # Setup per-proposal output if saving
            if save_output:
                prop_short_id = short_uuid(proposal_id)
                log_filename = f"{timestamp}_prop{index:02d}_{prop_short_id}_log.txt"
                log_f = open(log_filename, "w")
                sys.stdout = Tee(original_stdout, log_f)
                sys.stderr = Tee(original_stderr, log_f)

                # Update logger for this proposal
                root_logger = logging.getLogger()
                for handler in root_logger.handlers[:]:
                    root_logger.removeHandler(handler)
                new_handler = logging.StreamHandler(sys.stderr)
                new_handler.setFormatter(StructuredFormatter())
                new_handler.setLevel(logging.DEBUG if debug_level >= 2 else logging.INFO)
                root_logger.addHandler(new_handler)
                root_logger.setLevel(new_handler.level)
                setup_uvicorn_logging()
                for logger_name, logger in logging.Logger.manager.loggerDict.items():
                    if isinstance(logger, logging.Logger):
                        logger.setLevel(root_logger.level)
                        for handler in logger.handlers[:]:
                            logger.removeHandler(handler)
                        logger.propagate = True

            print(f"📋 Evaluating proposal {index}: {proposal_id}")
            backend = get_backend()
            proposal = backend.get_proposal(proposal_uuid)

            if not proposal:
                raise ValueError(f"Proposal {proposal_id} not found")

            if not proposal.content:
                raise ValueError(f"Proposal {proposal_id} has no content")

            proposal_content = proposal.content
            print(f"✅ Found proposal: {proposal.title or 'Untitled'}")

            # Use DAO ID from args or proposal
            effective_dao_id = dao_id or str(proposal.dao_id) if proposal.dao_id else None
            dao_uuid = UUID(effective_dao_id) if effective_dao_id else None

            # Determine prompt type
            prompt_type = "evaluation"
            if dao_uuid:
                dao = backend.get_dao(dao_uuid)
                if dao:
                    if dao.name == "ELONBTC":
                        prompt_type = "evaluation_elonbtc"
                    elif dao.name in ["AIBTC", "AITEST", "AITEST2", "AITEST3", "AITEST4"]:
                        prompt_type = "evaluation_aibtc"

            custom_system_prompt = load_prompt(prompt_type, "system")
            custom_user_prompt = load_prompt(prompt_type, "user_template")

            # Run evaluation
            result = await evaluate_proposal(
                proposal_content=proposal_content,
                dao_id=dao_uuid,
                proposal_id=proposal_id,
                custom_system_prompt=custom_system_prompt,
                custom_user_prompt=custom_user_prompt,
            )

            # Convert to dict
            result_dict = {
                "proposal_id": proposal_id,
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

            # Save JSON if requested
            if save_output:
                json_filename = f"{timestamp}_prop{index:02d}_{prop_short_id}_summary.json"
                with open(json_filename, "w") as f:
                    json.dump(result_dict, f, indent=2, default=str)
                print(f"✅ Results saved to {json_filename} and {log_filename}")
                log_f.close()

            # Restore original outputs
            sys.stdout = original_stdout
            sys.stderr = original_stderr

            return result_dict

        except Exception as e:
            error_msg = f"Error evaluating proposal {proposal_id}: {str(e)}"
            print(error_msg)
            if save_output:
                log_f.close()
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            return {"proposal_id": proposal_id, "error": error_msg}


def generate_summary(results: List[Dict[str, Any]], timestamp: str, save_output: bool) -> str:
    """Generate and save a readable summary of all evaluations."""
    summary_lines = [f"Evaluation Summary - {timestamp}", "=" * 60]

    total_proposals = len(results)
    passed = sum(1 for r in results if r.get("decision", False) and "error" not in r)
    failed = total_proposals - passed
    avg_score = sum(r.get("final_score", 0) for r in results if "error" not in r) / max(1, passed + failed - sum(1 for r in results if "error" in r))

    summary_lines.extend([
        f"Total Proposals: {total_proposals}",
        f"Passed: {passed} | Rejected/Failed: {failed}",
        f"Average Score: {avg_score:.2f}",
        "=" * 60,
    ])

    # Collect successful results for examples
    successful_results = [r for r in results if "error" not in r]
    sorted_results = sorted(successful_results, key=lambda x: x.get("final_score", 0), reverse=True)

    # Good examples: top 3 highest scores
    good_examples = sorted_results[:3]
    summary_lines.append("Good Examples (Top Scores):")
    for ex in good_examples:
        summary_lines.append(f"  Proposal {ex['proposal_id']}: Score {ex['final_score']} - {ex['summary'][:100]}...")
    summary_lines.append("")

    # Bad examples: bottom 3 lowest scores
    bad_examples = sorted_results[-3:] if len(sorted_results) >= 3 else sorted_results[::-1][:3]
    summary_lines.append("Bad Examples (Low Scores):")
    for ex in bad_examples:
        summary_lines.append(f"  Proposal {ex['proposal_id']}: Score {ex['final_score']} - {ex['summary'][:100]}...")
    summary_lines.append("=" * 60)

    for idx, result in enumerate(results, 1):
        if "error" in result:
            summary_lines.append(f"Proposal {idx} ({result['proposal_id']}): ERROR - {result['error']}")
        else:
            summary_lines.append(f"Proposal {idx} ({result['proposal_id']}):")
            summary_lines.append(f"  Decision: {'APPROVE' if result['decision'] else 'REJECT'}")
            summary_lines.append(f"  Final Score: {result['final_score']}")
            summary_lines.append("  Categories:")
            for cat in result["categories"]:
                summary_lines.append(f"    - {cat['category']}: {cat['score']} (Weight: {cat['weight']:.1%})")
                if cat["reasoning"]:
                    summary_lines.append(f"      Reasoning: {'; '.join(cat['reasoning'][:2])}...")
            summary_lines.append(f"  Explanation: {result['explanation'][:200]}..." if result['explanation'] else "  Explanation: N/A")
            summary_lines.append(f"  Flags: {', '.join(result['flags'][:5])}" if result['flags'] else "  Flags: None")
            summary_lines.append(f"  Token Usage: {result['token_usage'].get('total_tokens', 0):,}")
        summary_lines.append("-" * 60)

    summary_text = "\n".join(summary_lines)
    print(summary_text)

    if save_output:
        summary_txt = f"{timestamp}_summary.txt"
        with open(summary_txt, "w") as f:
            f.write(summary_text)
        summary_json = f"{timestamp}_summary.json"

        # Prepare JSON with good/bad examples
        json_data = {
            "timestamp": timestamp,
            "overall_stats": {
                "total_proposals": total_proposals,
                "passed": passed,
                "failed": failed,
                "avg_score": avg_score,
            },
            "good_examples": [
                {
                    "proposal_id": ex["proposal_id"],
                    "score": ex["final_score"],
                    "summary": ex["summary"],
                    "explanation": ex["explanation"],
                }
                for ex in good_examples
            ],
            "bad_examples": [
                {
                    "proposal_id": ex["proposal_id"],
                    "score": ex["final_score"],
                    "summary": ex["summary"],
                    "explanation": ex["explanation"],
                }
                for ex in bad_examples
            ],
            "results": results,
        }
        with open(summary_json, "w") as f:
            json.dump(json_data, f, indent=2, default=str)
        print(f"✅ Summary saved to {summary_txt} and {summary_json}")

    return summary_text


async def main():
    parser = argparse.ArgumentParser(
        description="Test comprehensive proposal evaluation workflow (V2 - Multi-proposal)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single proposal
  python test_proposal_evaluation_v2.py --proposal-id "12345678-1234-5678-9012-123456789abc" --debug-level 2
  
  # Multiple proposals
  python test_proposal_evaluation_v2.py --proposal-id "ID1" --proposal-id "ID2" --max-concurrent 3 --save-output
  
  # With DAO ID for all
  python test_proposal_evaluation_v2.py --proposal-id "ID1" --proposal-id "ID2" --dao-id "DAO_ID" --save-output
        """,
    )

    parser.add_argument(
        "--proposal-id",
        action="append",
        type=str,
        required=True,
        help="ID of the proposal to evaluate (can be specified multiple times)",
    )

    parser.add_argument(
        "--dao-id",
        type=str,
        help="ID of the DAO (applies to all proposals if provided)",
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
        help="Save outputs to timestamped files",
    )

    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=5,
        help="Maximum concurrent evaluations (default: 5)",
    )

    args = parser.parse_args()

    if not args.proposal_id:
        print("❌ At least one proposal ID is required")
        sys.exit(1)

    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")

    original_stdout = sys.stdout
    original_stderr = sys.stderr

    print("🚀 Starting Multi-Proposal Evaluation Test V2")
    print("=" * 60)
    print(f"Proposals: {len(args.proposal_id)}")
    print(f"DAO ID: {args.dao_id or 'Auto-detect per proposal'}")
    print(f"Debug Level: {args.debug_level}")
    print(f"Max Concurrent: {args.max_concurrent}")
    print(f"Save Output: {args.save_output}")
    print("=" * 60)

    semaphore = asyncio.Semaphore(args.max_concurrent)

    tasks = [
        evaluate_single_proposal(
            pid,
            idx + 1,
            args.dao_id,
            args.debug_level,
            timestamp,
            args.save_output,
            semaphore,
            original_stdout,
            original_stderr,
        )
        for idx, pid in enumerate(args.proposal_id)
    ]

    results = await asyncio.gather(*tasks)

    generate_summary(results, timestamp, args.save_output)

    print("\n🎉 Multi-proposal evaluation test completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
