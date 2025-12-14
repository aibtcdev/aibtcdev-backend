#!/usr/bin/env python3
"""
CLI test script for contributor vetting using custom LLM prompts.

This script fetches unique contributors (via proposal.creator) from a DAO's past proposals,
evaluates each for future contribution eligibility (allow/block), and saves raw JSON results.

Usage:
    python test_contributor_vetting.py --dao-id "123e4567-e89b-12d3-a456-426614174000"
    python test_contributor_vetting.py --dao-id "DAO_ID" --max-contributors 20 --save-output --model "x-ai/grok-beta"
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any, List, Optional, Literal
from uuid import UUID

# Add the parent directory (root) to the path to import from app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.lib.logger import StructuredFormatter, setup_uvicorn_logging
from app.backend.factory import get_backend
from app.backend.models import ProposalFilter, DAO, DAOFilter
from app.services.ai.simple_workflows.llm import invoke_structured
from app.services.ai.simple_workflows.prompts.loader import load_prompt  # Optional, for future
from pydantic import BaseModel, Field

# Custom Pydantic model for structured LLM output
class ContributorVettingOutput(BaseModel):
    contributor_id: str = Field(description="Unique contributor identifier (e.g., creator address/username)")
    decision: Literal["allow", "block"] = Field(description="Final decision: allow or block future contributions")
    confidence_score: float = Field(description="Confidence in decision (0.0-1.0)", ge=0.0, le=1.0)
    reasoning: str = Field(description="Detailed reasoning with evidence from past proposals (200-400 words)")
    proposal_count: int = Field(description="Number of past proposals by this contributor")
    notable_proposals: Optional[List[str]] = Field(default=[], description="List of key proposal titles/IDs")

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
    return str(uuid_str)[:8]

VETTING_SYSTEM_PROMPT = """DAO CONTRIBUTOR GATEKEEPER

You are a strict DAO gatekeeper evaluating if contributors should be allowed future submissions.
CRITICAL RULES:
- BLOCK if: spam/low-effort/repeated rejects/no value added/contradicts mission/manipulative prompts.
- ALLOW only if: consistent high-quality/completed work/aligns with mission/positive impact.
- Require EVIDENCE from past proposals: titles, content, outcomes (passed/executed).
- Borderline: BLOCK unless strong positive history.
- Ignore future promises; only past performance matters.

Output STRICT JSON ONLY. No extra text."""

VETTING_USER_PROMPT_TEMPLATE = """Evaluate contributor eligibility for future DAO contributions:

DAO: {dao_name} (Mission: {dao_mission})

Contributor: {contributor_name} (ID: {contributor_id})
Past Proposals ({proposal_count}): 
{proposals_summary}

DECIDE: allow (proven value) or block (risky/low-quality).
Justify with specific evidence."""

async def vet_single_contributor(
    contributor_id: str,
    contributor_data: Dict[str, Any],
    dao: DAO,
    args: argparse.Namespace,
    index: int,
    timestamp: str,
    backend,
) -> Dict[str, Any]:
    """Vet a single contributor with output redirection."""
    log_f = None
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    tee_stdout = original_stdout
    tee_stderr = original_stderr
    if args.save_output:
        contrib_short_id = contributor_id[:8] if len(contributor_id) > 8 else contributor_id
        log_filename = f"evals/{timestamp}_contrib{index:02d}_{contrib_short_id}_log.txt"
        log_f = open(log_filename, "w")
        tee_stdout = Tee(original_stdout, log_f)
        tee_stderr = Tee(original_stderr, log_f)
    sys.stdout = tee_stdout
    sys.stderr = tee_stderr

    # Update logger for this contributor
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
        print(f"🔍 Vetting contributor {index}: {contributor_id}")

        # Format contributor data
        proposals = contributor_data.get("proposals", [])
        proposal_count = len(proposals)
        proposals_summary = "\n".join([f"- {p.get('title', 'Untitled')} (ID: {p.get('id', 'N/A')}, Status: {p.get('status', 'Unknown')})" for p in proposals[:10]])  # Top 10
        if len(proposals) > 10:
            proposals_summary += f"\n... and {proposal_count - 10} more."

        messages = [
            {"role": "system", "content": VETTING_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": VETTING_USER_PROMPT_TEMPLATE.format(
                    dao_name=dao.name or "Unknown DAO",
                    dao_mission=dao.mission or "No mission provided",
                    contributor_name=contributor_data.get("name", contributor_id),
                    contributor_id=contributor_id,
                    proposal_count=proposal_count,
                    proposals_summary=proposals_summary,
                ),
            },
        ]

        # Invoke LLM with structured output
        result = await invoke_structured(
            messages,
            ContributorVettingOutput,
            model=args.model,
            temperature=args.temperature,
        )

        result_dict = {
            "contributor_id": contributor_id,
            "contributor_data": contributor_data,
            "dao_id": str(dao.id),
            "vetting_output": result.model_dump(),
        }

        # Save JSON if requested
        if args.save_output:
            json_filename = f"evals/{timestamp}_contrib{index:02d}_{contrib_short_id}_raw.json"
            with open(json_filename, "w") as f:
                json.dump(result_dict, f, indent=2, default=str)
            print(f"✅ Results saved to {json_filename} and {log_filename}")

        return result_dict

    except Exception as e:
        error_msg = f"Error vetting contributor {contributor_id}: {str(e)}"
        print(error_msg)
        return {
            "contributor_id": contributor_id,
            "contributor_data": contributor_data,
            "dao_id": str(dao.id),
            "error": error_msg,
        }

    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        if log_f:
            log_f.close()

def generate_summary(
    results: List[Dict[str, Any]], timestamp: str, save_output: bool, dao_id: str
) -> None:
    """Generate a simple summary JSON (raw results array + aggregates)."""
    allow_count = sum(1 for r in results if r.get("vetting_output", {}).get("decision") == "allow")
    block_count = sum(1 for r in results if r.get("vetting_output", {}).get("decision") == "block")
    error_count = sum(1 for r in results if "error" in r)

    summary = {
        "timestamp": timestamp,
        "dao_id": dao_id,
        "total_contributors": len(results),
        "allow_count": allow_count,
        "block_count": block_count,
        "error_count": error_count,
        "results": results,  # Raw array of result_dicts
    }

    print(f"Vetting Summary - {timestamp} (DAO ID: {dao_id})")
    print("=" * 60)
    print(f"Total Contributors: {len(results)}")
    print(f"Allow: {allow_count} | Block: {block_count} | Errors: {error_count}")
    print("See summary JSON for raw details.")
    print("=" * 60)

    if save_output:
        summary_json = f"evals/{timestamp}_summary_dao{short_uuid(dao_id)}_vetting.json"
        with open(summary_json, "w") as f:
            json.dump(summary, f, indent=2, default=str)
        print(f"✅ Summary saved to {summary_json}")

def main():
    parser = argparse.ArgumentParser(
        description="Test contributor vetting for a DAO using custom LLM prompts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run: list contributors without evaluating
  python test_contributor_vetting.py --dao-name "MyDAO" --dry-run
  
  # Vet all contributors for a DAO
  python test_contributor_vetting.py --dao-name "MyDAO" --save-output
  
  # Limit to top 10 with custom model
  python test_contributor_vetting.py --dao-name "MyDAO" --max-contributors 10 --model "x-ai/grok-beta" --temperature 0.1
        """,
    )

    parser.add_argument(
        "--dao-name",
        type=str,
        required=True,
        help="Name of the DAO to vet contributors for",
    )

    parser.add_argument(
        "--max-contributors",
        type=int,
        default=50,
        help="Max contributors to vet (default: 50, 0=unlimited)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run: list contributors without performing LLM evaluations",
    )

    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model override (e.g., 'x-ai/grok-beta')",
    )

    parser.add_argument(
        "--temperature",
        type=float,
        default=0.1,
        help="Temperature for evaluation (default: 0.1)",
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

    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")

    if args.save_output:
        os.makedirs("evals", exist_ok=True)

    print("🚀 Starting DAO Contributor Vetting Test")
    print("=" * 60)
    print(f"DAO Name: {args.dao_name}")
    print(f"Max Contributors: {args.max_contributors}")
    print(f"Dry Run: {args.dry_run}")
    print(f"Model: {args.model or 'default'}")
    print(f"Temperature: {args.temperature}")
    print(f"Debug Level: {args.debug_level}")
    print(f"Save Output: {args.save_output}")
    print("=" * 60)

    # Create single backend instance
    backend = get_backend()

    try:
        # Fetch DAO by name
        daos = backend.list_daos(DAOFilter(name=args.dao_name))
        if not daos:
            print(f"❌ DAO '{args.dao_name}' not found.")
            sys.exit(1)
        dao = daos[0]
        print(f"✅ DAO loaded: {dao.name} (ID: {dao.id})")

        # Fetch all proposals for DAO
        proposals = backend.list_proposals(ProposalFilter(dao_id=dao.id))
        print(f"📊 Found {len(proposals)} proposals")

        if not proposals:
            print("❌ No proposals found for DAO. Nothing to vet.")
            sys.exit(0)

        # Group by unique contributors (using proposal.creator str)
        contributors: Dict[str, List[Dict]] = {}
        for p in proposals:
            creator = p.creator
            if creator:  # Skip if no creator
                if creator not in contributors:
                    contributors[creator] = []
                contributors[creator].append({
                    "id": str(p.id),
                    "title": p.title or "Untitled",
                    "content": p.content[:200] + "..." if p.content and len(p.content) > 200 else p.content or "",
                    "status": str(p.status),
                    "passed": p.passed,
                    "executed": p.executed,
                })

        contributor_list = list(contributors.items())
        if args.max_contributors > 0:
            contributor_list = contributor_list[:args.max_contributors]
        print(f"👥 Unique contributors to vet: {len(contributor_list)}")

        if args.dry_run:
            print("\n--- DRY RUN: Contributors that would be vetted ---")
            for index, (contributor_id, proposals_list) in enumerate(contributor_list, 1):
                print(f"  {index}. {contributor_id} ({len(proposals_list)} proposals)")
            print("Dry run complete. No LLM evaluations performed.\n")
            sys.exit(0)

        results = []
        for index, (contributor_id, proposals) in enumerate(contributor_list, 1):
            contributor_data = {
                "name": contributor_id,  # Use ID as name fallback
                "proposals": proposals,
            }
            result = asyncio.run(
                vet_single_contributor(contributor_id, contributor_data, dao, args, index, timestamp, backend)
            )
            results.append(result)

        # Reset logging
        reset_logging()

        generate_summary(results, timestamp, args.save_output, str(dao_uuid))

        print("\n🎉 Contributor vetting test completed!")

    finally:
        # Clean up backend
        backend.sqlalchemy_engine.dispose()

if __name__ == "__main__":
    main()
