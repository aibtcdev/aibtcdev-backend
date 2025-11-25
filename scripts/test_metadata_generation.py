#!/usr/bin/env python3
"""
CLI test script for proposal metadata generation using orchestrator (simulates backend tasks).

This test mirrors test_proposal_evaluation_v3.py: fetches from DB, processes tweets/media via orchestrator,
saves outputs, resets logging. Ensures media (videos/images from X posts) is detected/processed.

Usage:
    python test_metadata_generation.py --proposal-id "123e4567-e89b-12d3-a456-426614174000"
    python test_metadata_generation.py --proposal-id "ID1" --proposal-id "ID2" --save-output --debug-level 2
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
from app.services.ai.simple_workflows.orchestrator import generate_proposal_metadata
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


async def generate_metadata_single_proposal(
    proposal_id: str,
    index: int,
    args: argparse.Namespace,
    timestamp: str,
    backend,  # Shared backend instance
) -> Dict[str, Any]:
    """Generate metadata for a single proposal with output redirection (simulates backend)."""
    log_f = None
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    tee_stdout = original_stdout
    tee_stderr = original_stderr
    if args.save_output:
        prop_short_id = short_uuid(proposal_id)
        log_filename = f"metadata/{timestamp}_prop{index:02d}_{prop_short_id}_log.txt"
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
        print(f"📋 Generating metadata for proposal {index}: {proposal_id}")

        # Fetch proposal (simulates backend task)
        proposal = backend.get_proposal(proposal_uuid)
        if not proposal:
            error_msg = f"Proposal {proposal_id} not found"
            print(error_msg)
            return {"proposal_id": proposal_id, "error": error_msg}

        # Extract tweet_db_ids (key for media processing!)
        tweet_db_ids = [proposal.tweet_id] if proposal.tweet_id else None

        # Fetch DAO for context
        dao_name = ""
        if proposal.dao_id:
            dao = backend.get_dao(proposal.dao_id)
            if dao and dao.name:
                dao_name = dao.name

        # Simulate backend: proposal.content + tweet_db_ids → full media/tweet processing
        result = await generate_proposal_metadata(
            proposal_content=proposal.content or "",
            dao_name=dao_name,
            proposal_type=getattr(proposal, "proposal_type", ""),
            tweet_db_ids=tweet_db_ids,
            streaming=False,  # No streaming in test
        )

        if "error" in result and result["error"]:
            error_msg = f"Metadata generation failed: {result['error']}"
            print(error_msg)
            return {"proposal_id": proposal_id, "error": error_msg}

        # Build result dict
        result_dict = {
            "proposal_id": proposal_id,
            "dao_name": dao_name,
            "tweet_db_ids": [str(tid) for tid in tweet_db_ids] if tweet_db_ids else [],
            "processing_metadata": result.get("processing_metadata", {}),
            "metadata": result.get("metadata", {}),
        }

        # Save JSON if requested
        if args.save_output:
            json_filename = (
                f"metadata/{timestamp}_prop{index:02d}_{prop_short_id}_raw.json"
            )
            with open(json_filename, "w") as f:
                json.dump(result_dict, f, indent=2, default=str)
            print(f"✅ Results saved to {json_filename} and {log_filename}")

        return result_dict

    except Exception as e:
        error_msg = f"Error generating metadata for {proposal_id}: {str(e)}"
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
    """Generate summary JSON with raw results."""
    summary = {
        "timestamp": timestamp,
        "total_proposals": len(results),
        "results": results,
    }

    print(f"Metadata Summary - {timestamp}")
    print("=" * 60)
    print(f"Total Proposals: {len(results)}")
    total_media = sum(
        r.get("processing_metadata", {}).get("total_media", 0) for r in results
    )
    print(f"Total Media Processed: {total_media}")
    print("See summary JSON for details.")
    print("=" * 60)

    if save_output:
        summary_json = f"metadata/{timestamp}_summary.json"
        with open(summary_json, "w") as f:
            json.dump(summary, f, indent=2, default=str)
        print(f"✅ Summary saved to {summary_json}")


def main():
    parser = argparse.ArgumentParser(
        description="Test proposal metadata generation via orchestrator (simulates backend)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single proposal (auto-fetches content/tweets/media from DB)
  python test_metadata_generation.py --proposal-id "12345678-1234-5678-9012-123456789abc"
  
  # Multiple proposals
  python test_metadata_generation.py --proposal-id "ID1" --proposal-id "ID2" --save-output --debug-level 2
        """,
    )

    parser.add_argument(
        "--proposal-id",
        action="append",
        type=str,
        required=True,
        help="Proposal ID(s) to process (multiple allowed)",
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
        help="Save raw JSON + logs to metadata/ (timestamped)",
    )

    args = parser.parse_args()

    if not args.proposal_id:
        print("❌ At least one --proposal-id required")
        sys.exit(1)

    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")

    if args.save_output:
        os.makedirs("metadata", exist_ok=True)

    print("🚀 Starting Metadata Generation Test (Backend Simulation)")
    print("=" * 60)
    print(f"Proposals: {len(args.proposal_id)}")
    print(f"Debug Level: {args.debug_level}")
    print(f"Save Output: {args.save_output}")
    print("=" * 60)

    # Create single backend instance
    backend = get_backend()

    results = []
    for index, proposal_id in enumerate(args.proposal_id, 1):
        result = asyncio.run(
            generate_metadata_single_proposal(
                proposal_id, index, args, timestamp, backend
            )
        )
        results.append(result)

    # Reset logging
    reset_logging()

    generate_summary(results, timestamp, args.save_output)

    print("\n🎉 Metadata generation test completed (backend simulation)!")

    # Clean up backend
    backend.sqlalchemy_engine.dispose()


if __name__ == "__main__":
    main()
