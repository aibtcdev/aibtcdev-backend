#!/usr/bin/env python3
"""
Test script for OpenRouter evaluation (evaluation_openrouter_v1.py)

Usage:
    python scripts/test_evaluation_openrouter_v1.py --proposal-id "your-proposal-uuid"
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from uuid import UUID

# Add the parent directory to the path to import from app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.backend.factory import backend
from app.services.ai.simple_workflows.evaluation_openrouter_v1 import (
    evaluate_proposal_openrouter,
)
from app.services.ai.simple_workflows.models import (
    ComprehensiveEvaluatorAgentProcessOutput,
)
from app.services.ai.simple_workflows.prompts.loader import load_prompt


def pretty_print_result(result: ComprehensiveEvaluatorAgentProcessOutput):
    """Pretty print the evaluation result."""
    print("\n" + "=" * 80)
    print("OPENROUTER EVALUATION RESULT")
    print("=" * 80)

    print(f"Decision: {'✅ APPROVED' if result.decision else '❌ REJECTED'}")
    print(f"Final Score: {result.final_score}/100")
    print(f"Images Processed: {result.images_processed}")

    if result.flags:
        print(f"Flags: {', '.join(result.flags)}")

    print(f"\nSummary: {result.summary}")

    print(f"\nExplanation:\n{result.explanation}")

    if result.categories:
        print("\nCategory Scores:")
        for category in result.categories:
            print(
                f"  • {category.category}: {category.score}/100 (Weight: {category.weight:.1%})"
            )
            for reasoning in category.reasoning:
                print(f"    {reasoning}")

    if result.token_usage:
        print(f"\nToken Usage: {result.token_usage}")

    print("\n" + "=" * 80)


async def test_evaluation(
    proposal_id: str, model: str = None, save_output: bool = False
):
    """Test the evaluation function with a proposal ID."""
    try:
        # Generate timestamp for file naming
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prop_short_id = proposal_id[:8]
        # Convert string to UUID
        proposal_uuid = UUID(proposal_id)

        print(f"Testing OpenRouter evaluation for proposal ID: {proposal_id}")
        if model:
            print(f"Using model: {model}")

        # Get the proposal from the backend to extract content
        proposal = backend.get_proposal(proposal_uuid)
        if not proposal:
            print(f"❌ Proposal {proposal_id} not found in database")
            return

        print(f"Found proposal: {proposal.title}")

        # Extract proposal content (this might vary based on your Proposal model)
        proposal_content = (
            getattr(proposal, "content", "")
            or getattr(proposal, "summary", "")
            or proposal.title
        )

        if not proposal_content:
            print("❌ No content found in proposal")
            return

        print(f"Proposal content preview: {proposal_content[:200]}...")

        # Fetch and process tweet content and images
        linked_tweet_images = []
        tweet_content = None
        if hasattr(proposal, "tweet_id") and proposal.tweet_id:
            try:
                from app.services.ai.simple_workflows.processors.twitter import (
                    fetch_tweet,
                    format_tweet,
                    format_tweet_images,
                )

                print(f"📷 Fetching tweet content and images from: {proposal.tweet_id}")
                tweet_data = await fetch_tweet(proposal.tweet_id)
                if tweet_data:
                    # Get formatted tweet content
                    tweet_content = format_tweet(tweet_data)
                    print(
                        f"📝 Retrieved tweet content: {len(tweet_content)} characters"
                    )

                    # Get tweet images
                    linked_tweet_images = format_tweet_images(
                        tweet_data, proposal.tweet_id
                    )
                    print(f"📷 Found {len(linked_tweet_images)} images in tweet")
                    for i, img in enumerate(linked_tweet_images):
                        print(
                            f"  Image {i + 1}: {img.get('image_url', {}).get('url', 'No URL')}"
                        )
                else:
                    print("❌ Could not fetch tweet data")
            except Exception as e:
                print(f"⚠️ Error fetching tweet content/images: {e}")

        # Clean images for evaluation (remove extra metadata)
        cleaned_images = [
            {"type": img["type"], "image_url": img["image_url"]}
            for img in linked_tweet_images
        ]

        print(f"📷 Passing {len(cleaned_images)} cleaned images to evaluation")

        # Fetch airdrop content if available
        airdrop_content = None
        if hasattr(proposal, "airdrop_id") and proposal.airdrop_id:
            try:
                from app.services.ai.simple_workflows.processors.airdrop import (
                    process_airdrop,
                )

                print(f"🪂 Fetching airdrop content from: {proposal.airdrop_id}")
                airdrop_content = await process_airdrop(
                    proposal.airdrop_id, proposal_uuid
                )
                if airdrop_content:
                    print(
                        f"🪂 Retrieved airdrop content: {len(airdrop_content)} characters"
                    )
                else:
                    print("❌ Could not fetch airdrop data")
            except Exception as e:
                print(f"⚠️ Error fetching airdrop content: {e}")

        # Determine prompt type based on DAO
        custom_system_prompt = None
        custom_user_prompt = None

        if hasattr(proposal, "dao_id") and proposal.dao_id:
            try:
                dao = backend.get_dao(proposal.dao_id)
                if dao and hasattr(dao, "name"):
                    print(f"DAO: {dao.name}")

                    # Load custom prompts based on DAO name
                    if dao.name in ["AIBTC", "AIBTC-BREW"]:
                        prompt_type = "evaluation_aibtc_brew"
                        print(f"Loading custom prompts for {prompt_type}")

                        custom_system_prompt = load_prompt(prompt_type, "system")
                        custom_user_prompt = load_prompt(prompt_type, "user_template")

                        if custom_system_prompt:
                            print("✅ Loaded custom AIBTC BREW system prompt")
                        else:
                            print("❌ Failed to load AIBTC BREW system prompt")
                        if custom_user_prompt:
                            print("✅ Loaded custom AIBTC BREW user prompt")
                        else:
                            print("❌ Failed to load AIBTC BREW user prompt")
                    else:
                        print("Using default evaluation prompts")
            except Exception as e:
                print(f"⚠️ Error loading DAO info: {e}")

        # Get DAO mission and community info for message reconstruction
        dao_mission = ""
        community_info = """
Community Size: Growing
Active Members: Active
Governance Participation: Moderate
Recent Community Sentiment: Positive
"""

        if hasattr(proposal, "dao_id") and proposal.dao_id:
            try:
                dao_obj = backend.get_dao(proposal.dao_id)
                if dao_obj and hasattr(dao_obj, "mission"):
                    dao_mission = dao_obj.mission
            except Exception as e:
                print(f"⚠️ Error fetching DAO mission: {e}")

        # Get past proposals for context (fetch from backend like original)
        past_proposals = (
            "<no_proposals>No past proposals available for comparison.</no_proposals>"
        )
        if hasattr(proposal, "dao_id") and proposal.dao_id:
            try:
                from app.services.ai.simple_workflows.evaluation import (
                    fetch_dao_proposals,
                    format_proposals_for_context_v2,
                )

                dao_proposals = await fetch_dao_proposals(
                    proposal.dao_id, exclude_proposal_id=proposal_id
                )
                past_proposals = format_proposals_for_context_v2(dao_proposals)
                print(f"📋 Retrieved {len(dao_proposals)} past proposals for context")
            except Exception as e:
                print(f"⚠️ Error fetching past proposals: {e}")

        # Reconstruct the full messages that would be sent to the LLM
        from app.services.ai.simple_workflows.evaluation_openrouter_v1 import (
            create_chat_messages,
        )

        full_messages = create_chat_messages(
            proposal_content=proposal_content,
            dao_mission=dao_mission,
            community_info=community_info,
            past_proposals=past_proposals,
            proposal_images=cleaned_images,
            tweet_content=tweet_content,  # Pass the fetched tweet content
            airdrop_content=airdrop_content,  # Pass the fetched airdrop content
            custom_system_prompt=custom_system_prompt,
            custom_user_prompt=custom_user_prompt,
        )

        # Run the evaluation
        print("\n🔄 Running OpenRouter evaluation...")
        result = await evaluate_proposal_openrouter(
            proposal_content=proposal_content,
            dao_id=proposal.dao_id if hasattr(proposal, "dao_id") else None,
            proposal_id=proposal_uuid,
            images=cleaned_images,  # Pass the cleaned images
            custom_system_prompt=custom_system_prompt,
            custom_user_prompt=custom_user_prompt,
            model=model,
        )

        print(f"📷 Images processed in result: {result.images_processed}")

        # Proposal number
        proposal_number = proposal.proposal_id

        # Create detailed result dictionary like the original test script
        proposal_metadata = {
            "title": getattr(proposal, "title", "Unknown"),
            "content": proposal_content,  # Full content, not just preview
            "tweet_content": tweet_content,  # Add tweet content to metadata
            "airdrop_content": airdrop_content,  # Add airdrop content to metadata
        }

        # Extract the actual prompts from the messages
        system_message = next(
            (msg for msg in full_messages if msg["role"] == "system"), {}
        )
        # user_messages = [msg for msg in full_messages if msg["role"] == "user"]

        # Format the user prompt template with actual data (like the original does)
        if custom_user_prompt:
            # Check if this is AIBTC BREW prompt (which has different format requirements)
            if "AIBTC protocol" in custom_user_prompt:
                # AIBTC BREW template only expects dao_mission and past_proposals
                formatted_user_prompt = custom_user_prompt.format(
                    dao_mission=dao_mission,
                    past_proposals=past_proposals,
                )
            else:
                # Other custom prompts use the full format
                formatted_user_prompt = custom_user_prompt.format(
                    proposal_content=proposal_content,
                    dao_mission=dao_mission,
                    community_info=community_info,
                    past_proposals=past_proposals,
                )
        else:
            formatted_user_prompt = "Default user prompt template was used"

        # Convert messages to dict format for JSON serialization
        full_messages_dict = []
        for msg in full_messages:
            if isinstance(msg.get("content"), list):
                # Handle multimodal content
                content_dict = []
                for item in msg["content"]:
                    if isinstance(item, dict):
                        content_dict.append(item)
                    else:
                        content_dict.append({"type": "text", "text": str(item)})
                full_messages_dict.append(
                    {"role": msg["role"], "content": content_dict}
                )
            else:
                full_messages_dict.append(
                    {"role": msg["role"], "content": msg["content"]}
                )

        # Calculate token usage (simplified version)
        raw_response = result.token_usage.get("raw_response", "Not available")
        token_usage = {
            "input_tokens": len(str(full_messages_dict)) // 4,  # Rough approximation
            "output_tokens": len(raw_response) // 4
            if raw_response != "Not available"
            else 0,
            "total_tokens": (len(str(full_messages_dict)) + len(raw_response)) // 4
            if raw_response != "Not available"
            else len(str(full_messages_dict)) // 4,
        }

        result_dict = {
            "proposal_id": proposal_id,
            "proposal_number": proposal_number,
            "proposal_metadata": proposal_metadata,
            "full_system_prompt": system_message.get(
                "content", "No system prompt found"
            ),
            "full_user_prompt": formatted_user_prompt,
            "full_messages": full_messages_dict,
            "raw_ai_response": raw_response,
            "decision": result.decision,
            "final_score": result.final_score,
            "explanation": result.explanation,
            "summary": result.summary,
            "categories": [
                {
                    "category": cat.category,
                    "score": cat.score,
                    "weight": cat.weight,
                    "reasoning": cat.reasoning,
                }
                for cat in result.categories
            ],
            "flags": result.flags,
            "token_usage": token_usage,
            "images_processed": result.images_processed,
            "expected_decision": None,  # Add expected_decision field
        }

        # Save detailed output if requested
        if save_output:
            # Ensure evals directory exists
            os.makedirs("evals", exist_ok=True)

            # Save JSON summary
            json_filename = (
                f"evals/{timestamp}_prop01_{prop_short_id}_summary_openrouter.json"
            )
            with open(json_filename, "w") as f:
                json.dump(result_dict, f, indent=2, default=str)

            print(f"✅ Detailed results saved to {json_filename}")

        # Pretty print the result
        pretty_print_result(result)

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
