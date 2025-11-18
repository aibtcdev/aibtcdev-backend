#!/usr/bin/env python3
"""
Simplified evaluation pipeline using direct OpenRouter HTTP request.

Usage:
    python scripts/test_evaluation_openrouter_v2.py --proposal-id "your-proposal-uuid" --save-output
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
from app.backend.models import ContractStatus, ProposalFilter
from app.config import config
from app.services.ai.simple_workflows.evaluation_openrouter_v2 import evaluate_proposal_openrouter
from app.services.ai.simple_workflows.prompts.evaluation_grok import (
    EVALUATION_GROK_SYSTEM_PROMPT,
    EVALUATION_GROK_USER_PROMPT_TEMPLATE,
)


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


async def test_evaluation(
    proposal_id: str, model: Optional[str] = None, save_output: bool = False
):
    """Test the evaluation function with a proposal ID."""
    try:
        # Convert string to UUID
        proposal_uuid = UUID(proposal_id)

        print("\n" + "=" * 80)
        print(f"Testing OpenRouter evaluation for proposal ID: {proposal_id}")
        if model:
            print(f"Using model from args: {model}")

        evaluation_result = await evaluate_proposal_openrouter(
            proposal_uuid,
            model=model,
            temperature=0.7,
            reasoning=True
        )

        if not evaluation_result:
            print("❌ Evaluation failed")
            return

        print("\n" + "=" * 80)
        print("Evaluation Result:")
        print(json.dumps(evaluation_result, indent=2))

        if save_output:
            output_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "evals",
            )
            os.makedirs(output_dir, exist_ok=True)
            output_filename = f"evaluation_openrouter_{proposal_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            output_path = os.path.join(output_dir, output_filename)

            evaluation_output = evaluation_result["evaluation_output"]
            if hasattr(evaluation_output, "model_dump"):
                evaluation_output_dumped = evaluation_output.model_dump()
            else:
                evaluation_output_dumped = evaluation_output  # already dumped

            output_data = {
                "timestamp": datetime.now().isoformat(),
                "results": [{
                    "proposal_id": proposal_id,
                    "evaluation_output": evaluation_output_dumped,
                    "full_system_prompt": evaluation_result.get("full_system_prompt"),
                    "full_user_prompt": evaluation_result.get("full_user_prompt"),
                    "full_messages": evaluation_result.get("full_messages"),
                    "expected_decision": None  # Set if available
                }]
            }

            with open(output_path, "w") as f:
                json.dump(output_data, f, indent=2)

            print(f"\nSaved evaluation output to: {output_path}")

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
