#!/usr/bin/env python3
"""Test script for Network School post evaluator.

Usage:
    python test_network_school_eval.py <username>

Example:
    python test_network_school_eval.py balajis
"""

import asyncio
import sys
import json
from app.services.ai.simple_workflows.network_school_evaluator import (
    evaluate_user_posts,
)
from app.lib.logger import configure_logger

logger = configure_logger(__name__)


def format_result(result):
    """Format the evaluation result for display."""
    output = []
    output.append("=" * 80)
    output.append(f"Network School Evaluation for @{result.username}")
    output.append("=" * 80)
    output.append(f"\nTotal posts analyzed: {result.total_posts_analyzed}")

    # Display usage statistics if available
    if result.usage_input_tokens or result.usage_output_tokens:
        output.append("\nUsage Statistics:")
        if result.usage_input_tokens:
            output.append(f"  Input tokens: {result.usage_input_tokens:,}")
        if result.usage_output_tokens:
            output.append(f"  Output tokens: {result.usage_output_tokens:,}")
        if result.usage_est_cost:
            output.append(f"  Estimated cost: {result.usage_est_cost}")

    # Display citations and search queries
    if result.citations or result.search_queries:
        output.append("\nSearch Information:")
        if result.search_queries:
            output.append(f"  Search queries used: {len(result.search_queries)}")
            for i, query in enumerate(result.search_queries[:5], 1):
                output.append(f"    {i}. {query}")
        if result.citations:
            output.append(f"  Sources cited: {len(result.citations)}")
            for i, citation in enumerate(result.citations[:10], 1):
                output.append(f"    {i}. {citation}")

    output.append("")

    if not result.top_posts:
        output.append("No posts found or evaluated.")
        return "\n".join(output)

    output.append(f"Top {len(result.top_posts)} Posts:\n")

    for i, post in enumerate(result.top_posts, 1):
        output.append(f"{'─' * 80}")
        output.append(f"#{i} - Score: {post.score}/100")
        output.append(f"Recommended Payout: {post.recommended_payout}")
        output.append(f"URL: {post.post_url}")
        output.append(f"\nReason: {post.reason}")
        output.append("")

    output.append("=" * 80)
    return "\n".join(output)


async def main():
    """Main test function."""
    if len(sys.argv) < 3:
        print("Usage: python test_network_school_eval.py <username> <prompt_file>")
        print(
            "Example: python test_network_school_eval.py balajis evaluation_prompt.txt"
        )
        print("\nThe prompt file must include {username} placeholder")
        sys.exit(1)

    username = sys.argv[1]
    prompt_file = sys.argv[2]

    # Load the evaluation prompt
    try:
        with open(prompt_file, "r") as f:
            evaluation_prompt = f.read()
        logger.info(f"Loaded evaluation prompt from {prompt_file}")
    except FileNotFoundError:
        logger.error(f"Prompt file not found: {prompt_file}")
        sys.exit(1)

    # Validate prompt has {username} placeholder
    if "{username}" not in evaluation_prompt:
        logger.error("Prompt must contain {username} placeholder")
        sys.exit(1)

    logger.info(f"Testing Network School evaluator with @{username}")

    try:
        # Run evaluation with prompt from file
        result = await evaluate_user_posts(
            username, evaluation_prompt=evaluation_prompt
        )

        # Display formatted result
        print("\n" + format_result(result))

        # Save evaluation result JSON
        output_file = f"network_school_eval_{username}.json"
        result_dict = result.model_dump()

        # Extract and save raw OpenRouter response separately
        raw_response = result_dict.pop("raw_openrouter_response", None)

        with open(output_file, "w") as f:
            json.dump(result_dict, f, indent=2)

        print(f"\n✅ Evaluation results saved to: {output_file}")

        # Save raw OpenRouter response to separate file
        if raw_response:
            raw_output_file = f"network_school_eval_{username}_raw_openrouter.json"
            with open(raw_output_file, "w") as f:
                json.dump(raw_response, f, indent=2, default=str)
            print(f"✅ Raw OpenRouter response saved to: {raw_output_file}")

        # Print citations summary if available
        if result.citations:
            print(f"\n📚 Found {len(result.citations)} citations (tweet sources)")
            print("Check the logs above for full citation details!")
        if result.search_queries:
            print(f"🔍 Used {len(result.search_queries)} search queries")

    except Exception as e:
        logger.error(f"Error during evaluation: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
