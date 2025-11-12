#!/usr/bin/env python3
"""
CLI test script for proposal evaluations using the v3 strict workflow.

This script runs evaluations via evaluate_proposal_strict, collects raw results,
and saves them as JSON for the data viewer. No heavy transformations here—keep it simple.

Usage:
    python test_proposal_evaluation_v3.py --proposal-id "123e4567-e89b-12d3-a456-426614174000"
    python test_proposal_evaluation_v3.py --proposal-id "ID1" --proposal-id "ID2" --save-output
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any
from uuid import UUID

# Add the parent directory (root) to the path to import from app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.lib.logger import StructuredFormatter, setup_uvicorn_logging
from app.services.ai.simple_workflows.orchestrator import evaluate_proposal_strict
from app.backend.factory import get_backend
from scripts.generate_evals_manifest import generate_manifest


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


def reset_logging():
    """Reset logging to a clean state with a handler to original sys.stderr."""
    root_logger = logging.getLogger()
    # Remove all existing handlers to clear any references to Tee/closed files
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    # Add a fresh handler to the current (original) sys.stderr
    clean_handler = logging.StreamHandler(sys.stderr)
    clean_handler.setFormatter(StructuredFormatter())
    clean_handler.setLevel(logging.INFO)
    root_logger.addHandler(clean_handler)
    root_logger.setLevel(clean_handler.level)
    # Propagate changes to other loggers if needed
    for logger_name, logger in logging.Logger.manager.loggerDict.items():
        if isinstance(logger, logging.Logger):
            logger.setLevel(root_logger.level)
            logger.handlers.clear()  # Clear per-logger handlers
            logger.propagate = True
    setup_uvicorn_logging()  # Re-apply any custom setup


def short_uuid(uuid_str: str) -> str:
    """Get first 8 characters of UUID for file naming."""
    return uuid_str[:8]


async def evaluate_single_proposal(
    proposal_id: str,
    index: int,
    args: argparse.Namespace,
    timestamp: str,
    backend,  # Shared backend instance
) -> Dict[str, Any]:
    """Evaluate a single proposal with output redirection."""
    log_f = None
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    tee_stdout = original_stdout
    tee_stderr = original_stderr
    if args.save_output:
        prop_short_id = short_uuid(proposal_id)
        log_filename = f"evals/{timestamp}_prop{index:02d}_{prop_short_id}_log.txt"
        log_f = open(log_filename, "w")
        tee_stdout = Tee(original_stdout, log_f)
        tee_stderr = Tee(original_stderr, log_f)
    sys.stdout = tee_stdout
    sys.stderr = tee_stderr

    # Update logger for this proposal
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    new_handler = logging.StreamHandler(sys.stderr)
    new_handler.setFormatter(StructuredFormatter())
    new_handler.setLevel(logging.DEBUG if args.debug_level >= 2 else logging.INFO)
    root_logger.addHandler(new_handler)
    root_logger.setLevel(new_handler.level)
    setup_uvicorn_logging()
    for logger_name, logger in logging.Logger.manager.loggerDict.items():
        if isinstance(logger, logging.Logger):
            logger.setLevel(root_logger.level)
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)
            logger.propagate = True

    try:
        proposal_uuid = UUID(proposal_id)
        print(f"📋 Evaluating proposal {index}: {proposal_id}")

        result = await evaluate_proposal_strict(
            proposal_id=proposal_uuid,
            model=args.model,
            temperature=args.temperature,
            reasoning=args.reasoning,
        )

        if not result:
            error_msg = f"Evaluation failed for proposal {proposal_id}"
            print(result)
            print(error_msg)
            return {"proposal_id": proposal_id, "error": error_msg}

        # Build minimal result dict with raw EvaluationOutput
        expected_dec = None
        if args.expected_decision and index <= len(args.expected_decision):
            expected_dec = args.expected_decision[
                index - 1
            ].upper()  # "APPROVE" or "REJECT"

        result_dict = {
            "proposal_id": proposal_id,
            "expected_decision": expected_dec,
            "evaluation_output": result.model_dump(),  # Raw as dict
        }

        # Save JSON if requested
        if args.save_output:
            json_filename = (
                f"evals/{timestamp}_prop{index:02d}_{prop_short_id}_raw.json"
            )
            with open(json_filename, "w") as f:
                json.dump(result_dict, f, indent=2, default=str)
            print(f"✅ Results saved to {json_filename} and {log_filename}")

        return result_dict

    except Exception as e:
        error_msg = f"Error evaluating proposal {proposal_id}: {str(e)}"
        print(error_msg)
        return {"proposal_id": proposal_id, "error": error_msg}

    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        if log_f:
            log_f.close()


def generate_summary(
    results: list[Dict[str, Any]], timestamp: str, save_output: bool
) -> None:
    """Generate a simple summary JSON (raw results array, no aggregates)."""
    summary = {
        "timestamp": timestamp,
        "total_proposals": len(results),
        "results": results,  # Raw array of result_dicts
    }

    print(f"Evaluation Summary - {timestamp}")
    print("=" * 60)
    print(f"Total Proposals: {len(results)}")
    print("See summary JSON for raw details.")
    print("=" * 60)

    if save_output:
        summary_json = f"evals/{timestamp}_summary.json"
        with open(summary_json, "w") as f:
            json.dump(summary, f, indent=2, default=str)
        print(f"✅ Summary saved to {summary_json}")


def main():
    parser = argparse.ArgumentParser(
        description="Test proposal evaluation using v3 strict workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single proposal
  python test_proposal_evaluation_v3.py --proposal-id "12345678-1234-5678-9012-123456789abc"
  
  # Multiple with expected decisions
  python test_proposal_evaluation_v3.py --proposal-id "ID1" --expected-decision approve --proposal-id "ID2" --expected-decision reject --save-output
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
        "--expected-decision",
        action="append",
        type=str.lower,
        choices=["approve", "reject"],
        help="Expected decision for the corresponding proposal (must match proposal-id count and order)",
    )

    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model override (e.g., 'x-ai/grok-4-fast')",
    )

    parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="Temperature for evaluation (default: 0.7)",
    )

    parser.add_argument(
        "--reasoning",
        default=True,
        help="Enable reasoning (default: True)",
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
        help="Save outputs to timestamped files in evals/",
    )

    args = parser.parse_args()

    if args.expected_decision and len(args.expected_decision) != len(args.proposal_id):
        print("❌ Number of --expected-decision must match --proposal-id")
        sys.exit(1)

    if not args.proposal_id:
        print("❌ At least one proposal ID is required")
        sys.exit(1)

    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")

    if args.save_output:
        os.makedirs("evals", exist_ok=True)

    print("🚀 Starting Proposal Evaluation Test V3")
    print("=" * 60)
    print(f"Proposals: {len(args.proposal_id)}")
    print(f"Model: {args.model or 'default'}")
    print(f"Temperature: {args.temperature}")
    print(f"Reasoning: {args.reasoning}")
    print(f"Debug Level: {args.debug_level}")
    print(f"Save Output: {args.save_output}")
    print("=" * 60)

    # Create single backend instance
    backend = get_backend()

    results = []
    for index, proposal_id in enumerate(args.proposal_id, 1):
        result = asyncio.run(
            evaluate_single_proposal(proposal_id, index, args, timestamp, backend)
        )
        results.append(result)

    # Reset logging
    reset_logging()

    generate_summary(results, timestamp, args.save_output)

    if args.save_output:
        generate_manifest()

    print("\n🎉 Proposal evaluation test v3 completed!")

    # Clean up backend
    backend.sqlalchemy_engine.dispose()


if __name__ == "__main__":
    main()
