#!/usr/bin/env python3
"""
Test script for OpenRouter evaluation (evaluation_openrouter_v1.py)

Usage:
    python scripts/test_evaluation_openrouter_v1.py --proposal-id "your-proposal-uuid"
"""

import argparse
import asyncio
import httpx
import json
import os
import sys
from datetime import datetime
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse
from uuid import UUID

# Add the parent directory to the path to import from app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.backend.factory import backend
from app.backend.models import ContractStatus, ProposalFilter, Proposal
from app.config import config
from app.services.ai.simple_workflows.evaluation_openrouter_v1 import (
    format_proposals_for_context_v2,
)
from app.services.ai.simple_workflows.prompts.loader import load_prompt


def get_openrouter_config() -> Dict[str, str]:
    """Get OpenRouter configuration from environment/config.
    Returns:
        Dictionary with OpenRouter configuration
    """
    return {
        "api_key": config.chat_llm.api_key,
        "model": config.chat_llm.default_model or "x-ai/grok-4-fast",
        "base_url": "https://openrouter.ai/api/v1",
        "referer": "https://aibtc.com",
        "title": "AIBTC",
    }


async def call_openrouter(
    messages: List[Dict[str, Any]],
    model: Optional[str] = None,
    temperature: float = 0.0,
    tools: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Make a direct HTTP call to OpenRouter API.

    Args:
        messages: List of chat messages
        model: Optional model override
        temperature: Temperature for generation
        tools: Optional tools for the model

    Returns:
        Response from OpenRouter API
    """
    config_data = get_openrouter_config()

    payload = {
        "model": model or config_data["model"],
        "messages": messages,
        "temperature": temperature,
    }

    if tools:
        payload["tools"] = tools

    headers = {
        "Authorization": f"Bearer {config_data['api_key']}",
        "HTTP-Referer": config_data["referer"],
        "X-Title": config_data["title"],
        "Content-Type": "application/json",
    }

    print(f"Making OpenRouter API call to model: {payload['model']}")

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{config_data['base_url']}/chat/completions", json=payload, headers=headers
        )
        response.raise_for_status()
        return response.json()


def print_proposal(proposal: Proposal):
    created_at = proposal.created_at.strftime("%Y-%m-%d %H:%M:%S")
    status = proposal.status
    title = proposal.title[:50] if isinstance(proposal.title, str) else proposal.title

    print(f"  {created_at} {status} {title}")


async def test_evaluation(
    proposal_id: str, model: Optional[str] = None, save_output: bool = False
):
    """Test the evaluation function with a proposal ID."""
    try:
        # Generate timestamp for file naming
        # timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # prop_short_id = proposal_id[:8]

        # Convert string to UUID
        proposal_uuid = UUID(proposal_id)

        print("\n" + "=" * 80)
        print(f"Testing OpenRouter evaluation for proposal ID: {proposal_id}")
        if model:
            print(f"Using model from args: {model}")

        # get the proposal from the backend
        proposal = backend.get_proposal(proposal_uuid)
        if not proposal:
            print(f"❌ Proposal {proposal_id} not found in database")
            return

        print(f"Found proposal: {proposal_id}")

        # extract proposal into a consistent object
        proposal_info_for_evaluation = {
            "proposal_number": proposal.proposal_id,
            "title": proposal.title,
            # "content": proposal.content,  # includes metadata/tags
            "summary": proposal.summary,  # just post and ref link
            "created_at_timestamp": proposal.created_at,
            "created_at_btc_block": proposal.created_btc,
            "executable_at_btc_block": proposal.exec_start,
            "x_url": proposal.x_url,
            # "tweet_id": proposal.tweet_id, # used internally
            # "tags": proposal.tags, # noise at this point?
            "tx_sender": proposal.tx_sender,
        }

        for key, value in proposal_info_for_evaluation.items():
            print(f"  {key}: {value[:80] if isinstance(value, str) else value}")

        # fetch dao info from proposal info
        print("\n" + "=" * 80)
        dao = None
        dao_info_for_evaluation = None
        if proposal.dao_id:
            dao = backend.get_dao(proposal.dao_id)

        if not dao:
            print(f"❌ DAO {proposal.dao_id} not found for proposal {proposal_id}")
            return

        print(f"Found related DAO: {dao.name} (ID: {dao.id})")

        dao_info_for_evaluation = {
            "dao_id": dao.id,
            "name": dao.name,
            "mission": dao.mission,
        }

        for key, value in dao_info_for_evaluation.items():
            print(f"  {key}: {value[:80] if isinstance(value, str) else value}")

        # fetch tweet info from DB
        print("\n" + "=" * 80)
        tweet_info_for_evaluation = None

        if proposal.tweet_id:
            tweet_content = backend.get_x_tweet(proposal.tweet_id)
            print(f"Fetched tweet info for tweet ID: {proposal.tweet_id}")
        else:
            tweet_content = None
            print("No tweet ID associated with this proposal")

        if tweet_content:
            tweet_info_for_evaluation = {
                # "message": tweet_content.message, # already in summary
                # "author_id": tweet_content.author_id, # local to our DB
                "x_post_id": tweet_content.tweet_id,
                # "conversation_id": tweet_content.conversation_id,  # verify used?
                "images": tweet_content.images,
                "author_name": tweet_content.author_name,
                "author_username": tweet_content.author_username,
                "created_at": tweet_content.created_at_twitter,
                "public_metrics": tweet_content.public_metrics,
                # "entities": tweet_content.entities,
                # "attachments": tweet_content.attachments,
                "quoted_tweet_id": tweet_content.quoted_tweet_id,
                "in_reply_to_user_id": tweet_content.in_reply_to_user_id,
                "replied_to_tweet_id": tweet_content.replied_to_tweet_id,
            }

        for key, value in (tweet_info_for_evaluation or {}).items():
            print(f"  {key}: {value[:100] if isinstance(value, str) else value}")

        # fetch tweet author info from db (if present)
        print("\n" + "=" * 80)
        tweet_author_info_for_evaluation = None

        if tweet_content and tweet_content.author_id:
            tweet_author_id = tweet_content.author_id
            tweet_author_content = backend.get_x_user(tweet_author_id)
            print(f"Fetched tweet author info for user ID: {tweet_author_id}")

            if tweet_author_content:
                tweet_author_info_for_evaluation = {
                    "user_id": tweet_author_content.user_id,
                    "name": tweet_author_content.name,
                    "username": tweet_author_content.username,
                    "description": tweet_author_content.description,
                    "verified": tweet_author_content.verified,
                    "verified_type": tweet_author_content.verified_type,
                    "location": tweet_author_content.location,
                }

                for key, value in tweet_author_info_for_evaluation.items():
                    print(
                        f"  {key}: {value[:100] if isinstance(value, str) else value}"
                    )
            else:
                print("❌ Could not fetch tweet author content")

        # fetch quoted tweet from db (if present)
        print("\n" + "=" * 80)
        quote_tweet_info_for_evaluation = None

        if tweet_content and tweet_content.quoted_tweet_db_id:
            quoted_tweet_id = tweet_content.quoted_tweet_db_id
            quoted_tweet_content = backend.get_x_tweet(quoted_tweet_id)
            print(f"Fetched quoted tweet info for tweet ID: {quoted_tweet_id}")

            if quoted_tweet_content:
                quote_tweet_info_for_evaluation = {
                    "x_post_id": quoted_tweet_content.tweet_id,
                    # "conversation_id": quoted_tweet_content.conversation_id,
                    "images": quoted_tweet_content.images,
                    "author_name": quoted_tweet_content.author_name,
                    "author_username": quoted_tweet_content.author_username,
                    "created_at": quoted_tweet_content.created_at_twitter,
                    "public_metrics": quoted_tweet_content.public_metrics,
                }

                for key, value in quote_tweet_info_for_evaluation.items():
                    print(
                        f"  {key}: {value[:100] if isinstance(value, str) else value}"
                    )
            else:
                print("❌ Could not fetch quoted tweet content")
        else:
            print("No quoted tweet associated with this tweet")

        # fetch replied-to tweet from db (if present)
        print("\n" + "=" * 80)
        reply_tweet_info_for_evaluation = None

        if tweet_content and tweet_content.replied_to_tweet_db_id:
            replied_to_tweet_id = tweet_content.replied_to_tweet_db_id
            replied_to_tweet_content = backend.get_x_tweet(replied_to_tweet_id)
            print(f"Fetched replied-to tweet info for tweet ID: {replied_to_tweet_id}")

            if replied_to_tweet_content:
                reply_tweet_info_for_evaluation = {
                    "x_post_id": replied_to_tweet_content.tweet_id,
                    # "conversation_id": replied_to_tweet_content.conversation_id,
                    "images": replied_to_tweet_content.images,
                    "author_name": replied_to_tweet_content.author_name,
                    "author_username": replied_to_tweet_content.author_username,
                    "created_at": replied_to_tweet_content.created_at_twitter,
                    "public_metrics": replied_to_tweet_content.public_metrics,
                }

                for key, value in reply_tweet_info_for_evaluation.items():
                    print(
                        f"  {key}: {value[:100] if isinstance(value, str) else value}"
                    )
            else:
                print("❌ Could not fetch replied-to tweet content")
        else:
            print("No replied-to tweet associated with this tweet")

        # fetch past proposals for context
        print("\n" + "=" * 80)
        dao_past_proposals_categorized = None
        dao_past_proposals_stats_for_evaluation = None
        dao_draft_proposals_for_evaluation = None
        dao_deployed_proposals_for_evaluation = None

        # get all proposals for the dao
        dao_proposals = backend.list_proposals(ProposalFilter(dao_id=proposal.dao_id))
        # exclude the current proposal
        dao_proposals = [p for p in dao_proposals if p.id != proposal.id]
        print(
            f"Fetched {len(dao_proposals)} past proposals for DAO ID: {proposal.dao_id}"
        )

        # print all proposals
        # for p in dao_proposals:
        #    print(
        #        f"  Proposal ID: {p.id}, Title: {p.title[:50] if isinstance(p.title, str) else p.title}..."
        #   )
        # print(p)

        # match past proposals by same tx_sender
        user_past_proposals_for_evaluation = None
        if proposal.tx_sender:
            user_past_proposals = [
                p for p in dao_proposals if p.tx_sender == proposal.tx_sender
            ]
            user_past_proposals_for_evaluation = format_proposals_for_context_v2(
                user_past_proposals
            )
            print("\n" + "=" * 80)
            print(
                f"Found {len(user_past_proposals)} past proposals by same sender:\n{proposal.tx_sender}"
            )
            # for p in user_past_proposals:
            #    print_proposal(p)

        # remove tx-sender matched proposals from dao proposals
        # if not present then default to full object
        dao_past_proposals = [
            p
            for p in dao_proposals
            if user_past_proposals and p not in user_past_proposals
        ]

        sorted_dao_past_proposals = sorted(
            dao_past_proposals,
            key=lambda p: getattr(p, "created_at", datetime.min),
            reverse=True,
        )

        dao_past_proposals_categorized = {
            "ALL": sorted_dao_past_proposals,
            ContractStatus.DRAFT: [
                p for p in sorted_dao_past_proposals if p.status == ContractStatus.DRAFT
            ],
            ContractStatus.PENDING: [
                p
                for p in sorted_dao_past_proposals
                if p.status == ContractStatus.PENDING
            ],
            ContractStatus.DEPLOYED: [
                p
                for p in sorted_dao_past_proposals
                if p.status == ContractStatus.DEPLOYED
            ],
            ContractStatus.FAILED: [
                p
                for p in sorted_dao_past_proposals
                if p.status == ContractStatus.FAILED
            ],
        }

        dao_past_proposals_stats_for_evaluation = {
            "ALL": len(sorted_dao_past_proposals),
            ContractStatus.DRAFT: len(
                dao_past_proposals_categorized[ContractStatus.DRAFT]
            ),
            ContractStatus.PENDING: len(
                dao_past_proposals_categorized[ContractStatus.PENDING]
            ),
            ContractStatus.DEPLOYED: len(
                dao_past_proposals_categorized[ContractStatus.DEPLOYED]
            ),
            ContractStatus.FAILED: len(
                dao_past_proposals_categorized[ContractStatus.FAILED]
            ),
        }

        print("Stats:", dao_past_proposals_stats_for_evaluation)

        # limit to last 20
        dao_draft_proposals = dao_past_proposals_categorized[ContractStatus.DRAFT][:20]

        dao_draft_proposals_for_evaluation = format_proposals_for_context_v2(
            dao_draft_proposals
        )

        print("\n" + "=" * 80)
        print(
            f"Using {len(dao_draft_proposals)} DAO draft proposals for evaluation context"
        )

        # for p in dao_draft_proposals:
        #    print_proposal(p)

        # limit to last 100
        dao_deployed_proposals = dao_past_proposals_categorized[
            ContractStatus.DEPLOYED
        ][:100]

        dao_deployed_proposals_for_evaluation = format_proposals_for_context_v2(
            dao_deployed_proposals
        )

        print("\n" + "=" * 80)
        print(
            f"Using {len(dao_deployed_proposals)} DAO deployed proposals for evaluation context"
        )
        # for p in dao_deployed_proposals:
        #    print_proposal(p)

        # add images in format so grok will read them
        # this should be appended to user chat object
        print("\n" + "=" * 80)
        images_for_evaluation = []

        if tweet_content and tweet_content.images:
            for img_url in tweet_content.images:
                # Basic validation of URL
                parsed_url = urlparse(img_url)
                if parsed_url.scheme in ["http", "https"]:
                    images_for_evaluation.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": img_url, "detail": "auto"},
                        }
                    )
                else:
                    print(f"❌ Invalid image URL skipped: {img_url}")

        print(f"Prepared {len(images_for_evaluation)} images for AI evaluation")

        # determine prompt type based on DAO
        print("\n" + "=" * 80)
        system_prompt = load_prompt("evaluation_grok", "system")
        user_prompt = load_prompt("evaluation_grok", "user_template")

        # fail if not found
        if not system_prompt or not user_prompt:
            print("❌ Could not load prompts for evaluation")
            return

        # list of dict with str keys and values that are either str or list of dicts
        # say that 10 times fast (using it based on format in Full LLM Messages in Eval))
        messages: list[dict[str, str | list[dict[str, str]]]] = []

        system_content = system_prompt

        messages = [{"role": "system", "content": system_content}]

        formatted_user_content = user_prompt.format(
            dao_info_for_evaluation=dao_info_for_evaluation,
            proposal_content_for_evaluation=proposal_info_for_evaluation,
            tweet_info_for_evaluation=tweet_info_for_evaluation,
            tweet_author_info_for_evaluation=tweet_author_info_for_evaluation,
            quote_tweet_info_for_evaluation=quote_tweet_info_for_evaluation,
            reply_tweet_info_for_evaluation=reply_tweet_info_for_evaluation,
            dao_past_proposals_stats_for_evaluation=dao_past_proposals_stats_for_evaluation,
            user_past_proposals_for_evaluation=user_past_proposals_for_evaluation,
            dao_draft_proposals_for_evaluation=dao_draft_proposals_for_evaluation,
            dao_deployed_proposals_for_evaluation=dao_deployed_proposals_for_evaluation,
        )

        user_content = [{"type": "text", "text": formatted_user_content}]

        if len(images_for_evaluation) > 0:
            for image in images_for_evaluation:
                user_content.append(image)

        messages.append({"role": "user", "content": user_content})

        print("\n" + "=" * 80)
        print("Final formatted messages to be sent to LLM:")
        print(messages)

        # NEXT STEP: call OpenRouter with this data, see if it processes
        # then we work backwards to how we want to implement it in the other areas
        # also add these headers to any OpenRouter methods:
        # 'default_headers': {'HTTP-Referer': 'https://aibtc.com', 'X-Title': 'AIBTC'}

        x_ai_tools = [{"type": "web_search"}, {"type": "x_search"}]

        openrouter_response = await call_openrouter(
            messages=messages, model=model or None, temperature=0.7, tools=x_ai_tools
        )

        print("\n" + "=" * 80)
        print("OpenRouter Full API Response:")
        print(openrouter_response)

        print("\n" + "=" * 80)
        print("OpenRouter Response Breakdown:")

        response_id = openrouter_response.get("id")
        response_provider = openrouter_response.get("provider")
        response_model = openrouter_response.get("model")
        response_usage = openrouter_response.get("usage")
        response_usage_total_tokens = (
            response_usage.get("total_tokens") if response_usage else None
        )

        print(f"Response ID: {response_id}")
        print(f"Response Provider: {response_provider}")
        print(f"Response Model: {response_model}")
        print(f"Response Usage: {response_usage_total_tokens} total tokens")

        response_choices = openrouter_response.get("choices", [])

        if len(response_choices) == 0:
            print("❌ No choices returned in OpenRouter response")
            return

        if len(response_choices) > 1:
            print(
                f"⚠️ Multiple choices returned ({len(response_choices)}), using the first one."
            )

        first_choice = response_choices[0]

        choice_finish_reason = first_choice.get("finish_reason")
        choice_native_finish_reason = first_choice.get("native_finish_reason")

        print(f"Choice Finish Reason: {choice_finish_reason}")
        print(f"Choice Native Finish Reason: {choice_native_finish_reason}")

        print("\n" + "=" * 80)
        print("Parsing JSON from message content")

        choice_message = first_choice.get("message")
        if not choice_message:
            print("❌ No message found in the first choice")
            return

        if not isinstance(choice_message, dict):
            print("❌ Choice message is not a dictionary")

        choice_message_role = choice_message.get("role")
        choice_message_content = choice_message.get("content")
        choice_message_refusal = choice_message.get("refusal")
        choice_message_reasoning = choice_message.get("reasoning")
        choice_message_reasoning_details = choice_message.get("reasoning_details")

        if (
            choice_message_reasoning_details
            and len(choice_message_reasoning_details) > 1
        ):
            print(
                f"⚠️ Multiple reasoning details returned ({len(choice_message_reasoning_details)}), using the first one."
            )

        choice_annotations = choice_message.get("annotations")

        print(f"Choice Message Role: {choice_message_role}")
        print(f"Choice Message Refusal: {choice_message_refusal}")
        print(f"Choice Message Reasoning: {choice_message_reasoning}")
        print(
            f"Choice Annotations: {len(choice_annotations) if choice_annotations else 0}"
        )
        choice_annotations_urls = []
        if choice_annotations:
            for annotation in choice_annotations:
                if annotation.get("type") == "url_citation":
                    url_citation = annotation.get("url_citation")
                    if url_citation:
                        url = url_citation.get("url")
                        if url:
                            choice_annotations_urls.append(url)
                else:
                    print(f"Unknown annotation type: {annotation.get('type')}")

        if len(choice_annotations_urls) > 0:
            print("  URLs cited in annotations:")
            for url in choice_annotations_urls:
                print(f"    {url}")

        if not choice_message_content:
            print("❌ No content found in the choice message")

        if not isinstance(choice_message_content, str):
            print("❌ Choice message content is not a string")

        try:
            choice_message_json = json.loads(choice_message_content)
            print("\n" + "=" * 80)
            print("Successfully parsed JSON from message content")
            print(json.dumps(choice_message_json, indent=2))

            if save_output:
                # save to file
                output_dir = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "evals",
                )
                os.makedirs(output_dir, exist_ok=True)
                output_filename = f"evaluation_openrouter_{proposal_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                output_path = os.path.join(output_dir, output_filename)

                with open(output_path, "w") as f:
                    json.dump(choice_message_json, f, indent=2)

                print(f"\nSaved evaluation output to: {output_path}")
        except json.JSONDecodeError as e:
            print(f"❌ JSON decoding error: {e}")
            return

        return

    except ValueError as e:
        print(f"❌ Invalid UUID format: {e}")
    except Exception as e:
        print(f"❌ Error during evaluation: {e}")
        import traceback

        traceback.print_exc()


def main():
    """Main function to handle command line arguments."""
    parser = argparse.ArgumentParser(description="Test OpenRouter evaluation")
    parser.add_argument(
        "--proposal-id", required=True, help="UUID of the proposal to evaluate"
    )
    parser.add_argument(
        "--model",
        help="Optional model to use (e.g., 'x-ai/grok-4', 'anthropic/claude-3.5-sonnet')",
    )
    parser.add_argument(
        "--save-output",
        action="store_true",
        help="Save detailed evaluation results to JSON file in evals/ directory",
    )

    args = parser.parse_args()

    # Run the async test
    asyncio.run(test_evaluation(args.proposal_id, args.model, args.save_output))


if __name__ == "__main__":
    main()
