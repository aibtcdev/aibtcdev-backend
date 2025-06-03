#!/usr/bin/env python3
"""
Example usage of the ProposalRecommendationAgent

This example demonstrates how to use the ProposalRecommendationAgent to generate
proposal recommendations for a DAO based on its mission and previous proposals.
"""

import asyncio
from uuid import UUID

from services.workflows.agents.proposal_recommendation import (
    ProposalRecommendationAgent,
)


async def example_proposal_recommendation():
    """Example showing how to generate a proposal recommendation."""

    # Example DAO ID (replace with actual DAO ID from your database)
    dao_id = UUID("12345678-1234-5678-9abc-123456789abc")

    # Initialize the agent
    agent = ProposalRecommendationAgent(config={})

    # Prepare the state with required parameters
    state = {
        "dao_id": dao_id,
        "focus_area": "community growth",  # Optional: specify focus area
        "specific_needs": "We need to increase engagement and onboard new members",  # Optional
    }

    # Generate the recommendation
    try:
        result = await agent.process(state)

        # Print the results
        print("=== Proposal Recommendation ===")
        print(f"DAO: {result.get('dao_name', 'Unknown')}")
        print(f"Title: {result.get('title', 'N/A')}")
        print(f"Priority: {result.get('priority', 'N/A')}")
        print(f"Estimated Impact: {result.get('estimated_impact', 'N/A')}")
        print("\nContent:")
        print(result.get("content", "N/A"))
        print("\nRationale:")
        print(result.get("rationale", "N/A"))

        if result.get("suggested_action"):
            print("\nSuggested Action:")
            print(result.get("suggested_action"))

        # Token usage information
        if "token_usage" in result:
            token_info = result["token_usage"]
            print(f"\nToken Usage: {token_info}")

    except Exception as e:
        print(f"Error generating recommendation: {e}")


async def example_api_usage():
    """Example showing how the API endpoint would be used (conceptual)."""

    # This is how you would call the API endpoint using requests or httpx

    api_payload = {
        "dao_id": "12345678-1234-5678-9abc-123456789abc",
        "focus_area": "technical development",
        "specific_needs": "Improve smart contract security and add new features",
    }

    # Headers would include authentication token
    headers = {
        "Authorization": "Bearer YOUR_TOKEN_HERE",
        "Content-Type": "application/json",
    }

    endpoint = "http://localhost:8000/tools/dao/proposal_recommendations/generate"

    print("=== API Usage Example ===")
    print(f"POST {endpoint}")
    print(f"Headers: {headers}")
    print(f"Payload: {api_payload}")
    print("\nThis would return a JSON response with the proposal recommendation.")


if __name__ == "__main__":
    print("Proposal Recommendation Agent Examples")
    print("=" * 50)

    # Run the direct agent usage example
    asyncio.run(example_proposal_recommendation())

    print("\n" + "=" * 50)

    # Show the API usage example (conceptual)
    asyncio.run(example_api_usage())
