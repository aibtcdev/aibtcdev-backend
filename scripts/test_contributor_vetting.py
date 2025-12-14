#!/usr/bin/env python3
"""
CLI test script for contributor vetting using custom LLM prompts.

This script fetches unique contributors (via proposal.creator) from a DAO's past proposals,
evaluates each for future contribution eligibility (allow/block), and saves raw JSON results.

Usage:
    python test_contributor_vetting.py --dao-name "MyDAO" --dry-run
    python test_contributor_vetting.py --dao-name "MyDAO" --save-output
    python test_contributor_vetting.py --dao-name "MyDAO" --max-contributors 20 --model "x-ai/grok-beta"
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any, List, Optional, Literal

# Add the parent directory (root) to the path to import from app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.lib.logger import StructuredFormatter, setup_uvicorn_logging
from app.backend.factory import get_backend
from app.backend.models import ProposalFilter, DAO, DAOFilter, Proposal
from app.config import config
import httpx
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Any, Dict, List
from urllib.parse import urlparse

from scripts.generate_vettings_manifest import generate_manifest


# Custom Pydantic model for structured LLM output
class ContributorVettingOutput(BaseModel):
    contributor_id: str = Field(
        description="Unique contributor identifier (e.g., creator address/username)"
    )
    x_handle: Optional[str] = Field(
        default=None,
        description="Primary X/Twitter handle extracted from contributor's proposals"
    )
    decision: Literal["allow", "block"] = Field(
        description="Final decision: allow or block future contributions"
    )
    confidence_score: float = Field(
        description="Confidence in decision (0.0-1.0)", ge=0.0, le=1.0
    )
    reasoning: str = Field(
        description="Detailed reasoning with evidence from past proposals (200-400 words)"
    )
    proposal_count: int = Field(
        description="Number of past proposals by this contributor"
    )
    notable_proposals: Optional[List[str]] = Field(
        default=[], description="List of key proposal titles/IDs"
    )


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


def safe_int_votes(value: Any, default: int = 0) -> int:
    """Safely convert value to int, handling None/non-numeric cases."""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def format_proposals_for_context(proposals: List[Dict[str, Any]]) -> str:
    """Format proposals for context in evaluation prompt (adapted from evaluation_openrouter_v2.py)."""
    if not proposals:
        return "None Found."

    # Sort by created_at descending (newest first)
    def get_created_at(p: Dict[str, Any]):
        created_at = p.get("created_at")
        if created_at:
            try:
                # Handle ISO format
                if isinstance(created_at, str):
                    return datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except ValueError:
                pass
        return datetime.min

    sorted_proposals = sorted(proposals, key=get_created_at, reverse=True)

    formatted_proposals = []
    for proposal in sorted_proposals:
        # Extract basic info
        proposal_id = str(proposal.get("proposal_id") or proposal.get("id", ""))[:8]  # Short ID
        title = proposal.get("title", "Untitled")

        # Extract x_handle from x_url
        x_url = proposal.get("x_url", "")
        x_handle = "unknown"
        if x_url:
            try:
                parsed_path = urlparse(x_url).path.split("/")
                if len(parsed_path) > 1:
                    x_handle = parsed_path[1]
            except (AttributeError, IndexError):
                pass

        # Get creation info
        created_at_btc = proposal.get("created_btc")
        created_at_timestamp = proposal.get("created_at")

        created_str = "unknown"
        if created_at_timestamp:
            try:
                if isinstance(created_at_timestamp, str):
                    created_str = created_at_timestamp[:10]
                else:
                    created_str = str(created_at_timestamp)[:10]
            except (AttributeError, ValueError):
                created_str = str(created_at_timestamp)

        if created_at_btc and created_at_timestamp:
            created_at = f"BTC Block {created_at_btc} (at {created_str})"
        elif created_at_btc:
            created_at = f"BTC Block {created_at_btc}"
        elif created_at_timestamp:
            created_at = created_str
        else:
            created_at = "unknown"

        # Get status
        proposal_status = proposal.get("status")
        passed = proposal.get("passed", False)
        concluded = proposal.get("concluded_by") is not None
        yes_votes = safe_int_votes(proposal.get("votes_for", 0))
        no_votes = safe_int_votes(proposal.get("votes_against", 0))

        if (
            proposal_status
            and isinstance(proposal_status, str)
            and proposal_status == "FAILED"
        ):
            proposal_passed = "n/a (failed tx)"
        elif passed:
            proposal_passed = "yes"
        elif concluded:
            proposal_passed = "no"
        else:
            proposal_passed = "pending"

        # handle special case of no votes
        if concluded and (yes_votes + no_votes == 0):
            proposal_passed = "n/a (no votes)"

        # Get content
        content = proposal.get("summary") or proposal.get("content", "")
        content_preview = content[:500] + "..." if len(content) > 500 else content

        formatted_proposal = f"""\n- #{proposal_id} by @{x_handle} Created: {created_at} Passed: {proposal_passed} Title: {title} Summary: {content_preview}"""

        formatted_proposals.append(formatted_proposal)

    return "\n".join(formatted_proposals)


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

Your output MUST follow this EXACT structure:

{{
    "contributor_id": "<contributor identifier>",
    "x_handle": "<primary X handle or null>",
    "decision": "<allow|block>",
    "confidence_score": <float 0.0-1.0>,
    "reasoning": "<detailed reasoning with evidence from past proposals (200-400 words)>",
    "proposal_count": <int number of past proposals>,
    "notable_proposals": ["<list of key proposal numbers/titles>"]
}}

GUIDELINES
- Use only the specified JSON format; no extra fields or text."""

VETTING_USER_PROMPT_TEMPLATE = """Evaluate contributor eligibility for future DAO contributions:

DAO INFO: includes DAO name and mission
{dao_info_for_evaluation}

CONTRIBUTOR ID: {contributor_id}

CONTRIBUTOR'S PAST PROPOSALS: includes all past proposals submitted by this contributor for this DAO
{user_past_proposals_for_evaluation}

Output the evaluation as a JSON object, strictly following the system guidelines."""


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
        contrib_short_id = (
            contributor_id[:8] if len(contributor_id) > 8 else contributor_id
        )
        log_filename = (
            f"evals/{timestamp}_contrib{index:02d}_{contrib_short_id}_log.txt"
        )
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

        # Format contributor data using production-style helpers
        proposals = contributor_data.get("proposals", [])
        proposal_count = len(proposals)
        user_past_proposals_for_evaluation = format_proposals_for_context(proposals)

        dao_info = {
            "dao_id": str(dao.id),
            "name": dao.name or "unknown",
            "mission": dao.mission or "unknown",
        }
        dao_info_for_evaluation = json.dumps(dao_info, default=str)

        messages = [
            {"role": "system", "content": VETTING_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": VETTING_USER_PROMPT_TEMPLATE.format(
                    dao_info_for_evaluation=dao_info_for_evaluation,
                    contributor_id=contributor_id,
                    user_past_proposals_for_evaluation=user_past_proposals_for_evaluation,
                ),
            },
        ]

        user_prompt_filled = messages[1]["content"]

        # Call OpenRouter directly with structured JSON parsing (mirrors evaluation_openrouter_v2.py)
        openrouter_response = await call_openrouter_structured(
            messages,
            ContributorVettingOutput,
            model=args.model,
            temperature=args.temperature,
        )

        serializable_proposals = [p for p in proposals]  # Already dicts from model_dump()
        result_dict = {
            "contributor_id": contributor_id,
            "contributor_data": {
                "name": contributor_id,
                "proposal_count": proposal_count,
                "proposals": serializable_proposals,
            },
            "dao_id": str(dao.id),
            "user_prompt_filled": user_prompt_filled,
            "vetting_output": openrouter_response.model_dump(),
            "usage": getattr(openrouter_response, "usage", None),
        }

        # Save JSON if requested
        if args.save_output:
            json_filename = (
                f"evals/{timestamp}_contrib{index:02d}_{contrib_short_id}_raw.json"
            )
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
            "user_prompt_filled": None,
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
    allow_count = sum(
        1 for r in results if r.get("vetting_output", {}).get("decision") == "allow"
    )
    block_count = sum(
        1 for r in results if r.get("vetting_output", {}).get("decision") == "block"
    )
    error_count = sum(1 for r in results if "error" in r)

    summary = {
        "timestamp": timestamp,
        "dao_id": dao_id,
        "system_prompt": VETTING_SYSTEM_PROMPT,
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

        # Group by unique contributors (using proposal.creator str), full history with model_dump for serialization
        contributors: Dict[str, List[Dict[str, Any]]] = {}
        for p in proposals:
            creator = p.creator
            if creator:  # Skip if no creator
                if creator not in contributors:
                    contributors[creator] = []
                contributors[creator].append(p.model_dump())

        # Sort contributors by number of proposals descending (most active first)
        contributor_list = sorted(contributors.items(), key=lambda x: len(x[1]), reverse=True)
        if args.max_contributors > 0:
            contributor_list = contributor_list[:args.max_contributors]
        print(f"👥 Unique contributors to vet: {len(contributor_list)} (sorted by activity)")

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
                "proposals": proposals,  # Full history dicts
            }
            result = asyncio.run(
                vet_single_contributor(
                    contributor_id,
                    contributor_data,
                    dao,
                    args,
                    index,
                    timestamp,
                    backend,
                )
            )
            results.append(result)

        # Reset logging
        reset_logging()

        generate_summary(results, timestamp, args.save_output, str(dao.id))

        generate_manifest()

        print("\n🎉 Contributor vetting test completed!")

    finally:
        # Clean up backend
        backend.sqlalchemy_engine.dispose()


async def call_openrouter_structured(
    messages: List[Dict[str, Any]],
    output_model: type[BaseModel],
    model: Optional[str] = None,
    temperature: Optional[float] = None,
) -> ContributorVettingOutput:
    """Direct OpenRouter API call with JSON parsing and Pydantic validation (adapted from evaluation_openrouter_v2.py)."""
    config_data = {
        "api_key": config.chat_llm.api_key,
        "model": model or config.chat_llm.default_model,
        "temperature": temperature or config.chat_llm.default_temperature,
        "base_url": config.chat_llm.api_base,
    }

    payload = {
        "messages": messages,
        "model": config_data["model"],
        "temperature": config_data["temperature"],
    }

    headers = {
        "Authorization": f"Bearer {config_data['api_key']}",
        "HTTP-Referer": "https://aibtc.com",
        "X-Title": "AIBTC",
        "Content-Type": "application/json",
    }

    print(
        f"📡 Calling OpenRouter: {config_data['model']} (temp={config_data['temperature']:.1f})"
    )

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{config_data['base_url']}/chat/completions",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()

    data = response.json()
    choices = data.get("choices", [])
    if not choices:
        raise ValueError("No choices in OpenRouter response")

    choice_message = choices[0].get("message")
    if not choice_message or not isinstance(choice_message.get("content"), str):
        raise ValueError("Invalid message content in response")

    try:
        # Parse strict JSON from content
        evaluation_json = json.loads(choice_message["content"])

        # Extract usage
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("completion_tokens")
        usage_info = (
            {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
            if input_tokens is not None and output_tokens is not None
            else None
        )

        # Validate with Pydantic + add usage
        result = output_model(**evaluation_json)
        if usage_info:
            # Monkey-patch usage to model instance (for summary/export)
            object.__setattr__(result, "usage", usage_info)

        print(
            f"✅ OpenRouter success: {result.decision} (conf: {result.confidence_score:.2f})"
        )
        return result

    except json.JSONDecodeError as e:
        print(
            f"❌ JSON decode error: {e}\nRaw content: {choice_message['content'][:500]}..."
        )
        raise
    except ValueError as e:
        print(f"❌ Pydantic validation error: {e}")
        raise


if __name__ == "__main__":
    main()
