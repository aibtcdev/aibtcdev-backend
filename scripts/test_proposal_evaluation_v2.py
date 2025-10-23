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
import multiprocessing as mp
import os
import sys
from datetime import datetime
from typing import List, Dict, Any
from uuid import UUID

# Add the parent directory (root) to the path to import from app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.lib.logger import StructuredFormatter, setup_uvicorn_logging
from app.services.ai.simple_workflows.evaluation import (
    evaluate_proposal,
    fetch_dao_proposals,
    format_proposals_for_context,
    retrieve_from_vector_store,
    create_chat_messages,
)
from app.lib.tokenizer import Trimmer
from app.services.ai.simple_workflows.prompts.loader import load_prompt
from app.services.ai.simple_workflows.processors.twitter import (
    fetch_tweet,
    format_tweet,
    format_tweet_images,
)
from app.services.ai.simple_workflows.processors.airdrop import process_airdrop
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


def evaluate_single_proposal(
    proposal_id: str,
    index: int,
    dao_id: str | None,
    debug_level: int,
    timestamp: str,
    save_output: bool,
    expected_decision: str | None,
    no_vector_store: bool,
    backend,  # Shared backend instance
) -> Dict[str, Any]:
    """Evaluate a single proposal with output redirection."""

    async def inner() -> Dict[str, Any]:
        log_f = None
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        tee_stdout = original_stdout
        tee_stderr = original_stderr
        if save_output:
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

        try:
            proposal_uuid = UUID(proposal_id)

            print(f"📋 Evaluating proposal {index}: {proposal_id}")
            proposal = backend.get_proposal(proposal_uuid)

            if not proposal:
                raise ValueError(f"Proposal {proposal_id} not found")

            proposal_content = proposal.content

            if not proposal_content:
                raise ValueError(f"Proposal {proposal_id} has no content")

            print(f"✅ Found proposal: {proposal.title or 'Untitled'}")

            # Use DAO ID from args or proposal
            effective_dao_id = (
                dao_id or str(proposal.dao_id) if proposal.dao_id else None
            )
            dao_uuid = UUID(effective_dao_id) if effective_dao_id else None

            # Fetch DAO for mission
            dao = backend.get_dao(dao_uuid) if dao_uuid else None
            dao_mission = (
                dao.mission
                if dao and dao.mission
                else "Elevate human potential through AI on Bitcoin"
            )

            # Align community info with backend
            community_info = """
Community Size: Growing
Active Members: Active
Governance Participation: Moderate
Recent Community Sentiment: Positive
"""

            # Fetch and format tweet content
            tweet_content = None
            linked_tweet_images = []
            if hasattr(proposal, "tweet_id") and proposal.tweet_id:
                tweet_data = await fetch_tweet(proposal.tweet_id)
                if tweet_data:
                    tweet_content = format_tweet(tweet_data)
                    linked_tweet_images = format_tweet_images(
                        tweet_data, proposal.tweet_id
                    )

            cleaned_images = [
                {"type": img["type"], "image_url": img["image_url"]}
                for img in linked_tweet_images
            ]

            print(
                f"DEBUG: Passing {len(cleaned_images)} images to evaluate_proposal: {[img['image_url']['url'] for img in cleaned_images]}"
            )

            # Fetch and format airdrop content
            airdrop_content = None
            if hasattr(proposal, "airdrop_id") and proposal.airdrop_id:
                airdrop_content = await process_airdrop(
                    proposal.airdrop_id, proposal_id
                )

            # Aligned past proposals gathering (mimics backend)
            dao_proposals = []
            past_proposals_db_text = ""
            try:
                if dao_uuid:
                    dao_proposals = await fetch_dao_proposals(
                        dao_uuid, exclude_proposal_id=None
                    )
                    # Exclude current for past_proposals
                    past_proposals_list = [
                        p for p in dao_proposals if p.id != proposal_uuid
                    ]
                    past_proposals_db_text = format_proposals_for_context(
                        past_proposals_list
                    )
            except Exception as e:
                print(f"Error fetching DAO proposals: {str(e)}")
                past_proposals_db_text = "<no_proposals>No past proposals available due to error.</no_proposals>"

            # Vector store retrieval (optional)
            past_proposals_vector_text = ""
            if not no_vector_store:
                try:
                    similar_proposals = await retrieve_from_vector_store(
                        query=proposal_content[:1000],
                        collection_name="past_proposals",
                        limit=3,
                    )
                    past_proposals_vector_text = "\n\n".join(
                        [
                            f'<similar_proposal id="{i + 1}">\n{doc.page_content}\n</similar_proposal>'
                            for i, doc in enumerate(similar_proposals)
                        ]
                    )
                except Exception as e:
                    print(f"Error retrieving from vector store: {str(e)}")
                    past_proposals_vector_text = "<no_similar_proposals>No similar past proposals available in vector store.</no_similar_proposals>"

            # Combine like backend
            past_proposals = past_proposals_db_text
            if past_proposals_vector_text:
                past_proposals += (
                    "\n\n" + past_proposals_vector_text
                    if past_proposals
                    else past_proposals_vector_text
                )
            elif not past_proposals:
                past_proposals = (
                    "<no_proposals>No past proposals available.</no_proposals>"
                )

            # Determine proposal number based on descending sort (newest first)
            proposal_number = (
                proposal.proposal_id if proposal.proposal_id is not None else None
            )

            # Determine prompt type
            prompt_type = "evaluation"
            if dao:
                if dao.name == "ELONBTC":
                    prompt_type = "evaluation_elonbtc"
                elif dao.name in ["AIBTC", "AITEST", "AITEST2", "AITEST3", "AITEST4"]:
                    prompt_type = "evaluation_aibtc"

            custom_system_prompt = load_prompt(prompt_type, "system")
            custom_user_prompt = load_prompt(prompt_type, "user_template")

            # Proposal metadata for logging
            proposal_metadata = {
                "title": proposal.title or "Untitled",
                "content": proposal_content,
                "tweet_content": tweet_content,
                "airdrop_content": airdrop_content,
            }

            # Format full_user_prompt for logging using aligned data
            full_user_prompt = custom_user_prompt.format(
                proposal_content=proposal_content,
                dao_mission=dao_mission,
                community_info=community_info,
                past_proposals=past_proposals,
            )

            # Run evaluation, passing fetched content
            result = await evaluate_proposal(
                proposal_content=proposal_content,
                dao_id=dao_uuid,
                proposal_id=proposal_id,
                images=cleaned_images,  # Pass cleaned images
                tweet_content=tweet_content,
                airdrop_content=airdrop_content,
                custom_system_prompt=custom_system_prompt,
                custom_user_prompt=custom_user_prompt,
            )

            print(
                f"DEBUG: Evaluation completed. Images processed in result: {result.images_processed}"
            )

            # Reconstruct full messages for logging
            full_messages = create_chat_messages(
                proposal_content=proposal_content,
                dao_mission=dao_mission,
                community_info=community_info,
                past_proposals=past_proposals,
                proposal_images=linked_tweet_images,
                tweet_content=tweet_content,
                airdrop_content=airdrop_content,
                custom_system_prompt=custom_system_prompt,
                custom_user_prompt=custom_user_prompt,
            )

            # Convert messages to dicts for consistent handling
            full_messages_dict = (
                [
                    msg
                    if isinstance(msg, dict)
                    else (msg.dict() if hasattr(msg, "dict") else msg.to_dict())
                    for msg in full_messages
                ]
                if isinstance(full_messages, list)
                else (
                    full_messages.dict()
                    if hasattr(full_messages, "dict")
                    else full_messages.to_dict()
                )
            )

            trimmer = Trimmer()
            input_tokens = trimmer.count_tokens(full_messages_dict)
            output_tokens = len(
                trimmer.tokenizer.encode(getattr(result, "raw_response", ""))
            )
            computed_token_usage = {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            }

            # Convert to dict
            result_dict = {
                "proposal_id": proposal_id,
                "proposal_number": proposal_number,
                "proposal_metadata": proposal_metadata,
                "full_system_prompt": custom_system_prompt,
                "full_user_prompt": full_user_prompt,
                "full_messages": full_messages_dict,
                "raw_ai_response": getattr(result, "raw_response", "Not available"),
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
                "token_usage": result.token_usage or computed_token_usage,
                "images_processed": result.images_processed,
                "expected_decision": True
                if expected_decision == "true"
                else False
                if expected_decision == "false"
                else None,
            }

            # Save JSON if requested
            if save_output:
                json_filename = (
                    f"evals/{timestamp}_prop{index:02d}_{prop_short_id}_summary.json"
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

    return asyncio.run(inner())


def generate_summary(
    results: List[Dict[str, Any]], timestamp: str, save_output: bool
) -> str:
    """Generate and save a readable summary of all evaluations."""
    summary_lines = [f"Evaluation Summary - {timestamp}", "=" * 60]

    total_proposals = len(results)
    passed = sum(1 for r in results if r.get("decision", False) and "error" not in r)
    failed = total_proposals - passed

    successful_count = sum(1 for r in results if "error" not in r)
    avg_score = sum(r.get("final_score", 0) for r in results if "error" not in r) / max(
        1, successful_count
    )

    # Expected outcomes
    total_with_expected = sum(1 for r in results if r.get("expected_decision") is not None and "error" not in r)
    matched = sum(1 for r in results if r.get("expected_decision") is not None and r.get("decision") == r.get("expected_decision") and "error" not in r)

    summary_lines.extend(
        [
            f"Total Proposals: {total_proposals}",
            f"Passed: {passed} | Rejected/Failed: {failed}",
            f"Average Score: {avg_score:.2f}",
            f"Expected Outcomes: {matched}/{total_with_expected} matched",
            "=" * 60,
        ]
    )

    summary_lines.append("Compact Scores Overview:")
    summary_lines.append("Proposal ID | Score | Decision | Expected | Match | Explanation | Tweet Snippet")
    summary_lines.append("-" * 100)
    for idx, result in enumerate(results, 1):
        prop_id = short_uuid(result["proposal_id"])
        if "error" in result:
            summary_lines.append(
                f"Prop {prop_id} | ERROR | N/A | N/A | N/A | {result['error']} | N/A"
            )
        else:
            decision = "APPROVE" if result["decision"] else "REJECT"
            expected = "APPROVE" if result.get("expected_decision") else ("REJECT" if result.get("expected_decision") is False else "N/A")
            match = "Yes" if result.get("expected_decision") is not None and result["decision"] == result["expected_decision"] else ("No" if result.get("expected_decision") is not None else "N/A")
            expl = result.get("explanation") or "N/A"
            content = result.get("proposal_metadata", {}).get("tweet_content", "")
            tweet_snippet = content and f"{content[:50]}..." or "N/A"
            summary_lines.append(
                f"Prop {prop_id} | {result['final_score']:.2f} | {decision} | {expected} | {match} | {expl} | {tweet_snippet}"
            )
    summary_lines.append("=" * 60)
    summary_lines.append(
        "For full reasoning and categories, see per-proposal JSON files or summary JSON."
    )

    summary_text = "\n".join(summary_lines)
    print(summary_text)

    if save_output:
        summary_txt = f"evals/{timestamp}_summary.txt"
        with open(summary_txt, "w") as f:
            f.write(summary_text)
        summary_json = f"evals/{timestamp}_summary.json"

        json_data = {
            "timestamp": timestamp,
            "overall_stats": {
                "total_proposals": total_proposals,
                "passed": passed,
                "failed": failed,
                "avg_score": avg_score,
                "matched_expected": matched,
                "total_with_expected": total_with_expected,
            },
            "compact_scores": [
                {
                    "proposal_id": r["proposal_id"],
                    "final_score": r.get("final_score"),
                    "decision": r.get("decision"),
                    "expected_decision": r.get("expected_decision"),
                    "match": r.get("expected_decision") is not None and r.get("decision") == r.get("expected_decision"),
                    "explanation": r.get("explanation"),
                    "error": r.get("error"),
                    "tweet_snippet": (
                        content := r.get("proposal_metadata", {}).get(
                            "tweet_content", ""
                        )
                    )
                    and f"{content[:50]}..."
                    or "N/A",
                }
                for r in results
            ],
            "full_results": results,
        }
        with open(summary_json, "w") as f:
            json.dump(json_data, f, indent=2, default=str)
        print(f"✅ Summary saved to {summary_txt} and {summary_json}")

    return summary_text


def main():
    parser = argparse.ArgumentParser(
        description="Test comprehensive proposal evaluation workflow (V2 - Sequential)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single proposal
  python test_proposal_evaluation_v2.py --proposal-id "12345678-1234-5678-9012-123456789abc" --debug-level 2
  
  # Multiple proposals
  python test_proposal_evaluation_v2.py --proposal-id "ID1" --proposal-id "ID2" --save-output
  
  # With DAO ID for all
  python test_proposal_evaluation_v2.py --proposal-id "ID1" --proposal-id "ID2" --dao-id "DAO_ID" --save-output
  
  # With expected decisions (true/false, matching proposal order)
  python test_proposal_evaluation_v2.py --proposal-id "ID1" --expected-decision true --proposal-id "ID2" --expected-decision false
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
        type=str,
        choices=["true", "false"],
        help="Expected decision for the corresponding proposal (true=APPROVE, false=REJECT; must match proposal-id count and order)",
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
        "--no-vector-store",
        action="store_true",
        help="Skip vector store retrieval for past proposals",
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

    print("🚀 Starting Sequential Proposal Evaluation Test V2")
    print("=" * 60)
    print(f"Proposals: {len(args.proposal_id)}")
    print(f"DAO ID: {args.dao_id or 'Auto-detect per proposal'}")
    print(f"Debug Level: {args.debug_level}")
    print(f"Save Output: {args.save_output}")
    print(f"No Vector Store: {args.no_vector_store}")
    print("=" * 60)

    # Create single backend instance
    backend = get_backend()

    args_list = [
        (
            pid,
            idx + 1,
            args.dao_id,
            args.debug_level,
            timestamp,
            args.save_output,
            args.expected_decision[idx] if args.expected_decision else None,
            args.no_vector_store,
            backend,
        )
        for idx, pid in enumerate(args.proposal_id)
    ]

    try:
        results = []
        for arg_tuple in args_list:
            result = evaluate_single_proposal(*arg_tuple)
            results.append(result)

        generate_summary(results, timestamp, args.save_output)

        print("\n🎉 Sequential proposal evaluation test completed successfully!")

        # Generate or update manifest after run if saving output
        if args.save_output:
            from scripts.generate_evals_manifest import generate_manifest

            generate_manifest()
    finally:
        # Clean up backend connections
        backend.sqlalchemy_engine.dispose()
        if backend.vecs_client:
            backend.vecs_client.close()


if __name__ == "__main__":
    main()
