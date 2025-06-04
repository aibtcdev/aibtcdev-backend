#!/usr/bin/env python3
"""
Example usage of the ProposalSummarizationAgent.

This script demonstrates how to use the ProposalSummarizationAgent to generate
titles and summaries for proposal content.
"""

import asyncio
from typing import Any, Dict

from services.workflows.agents import ProposalSummarizationAgent


async def example_proposal_summarization():
    """Example of using the ProposalSummarizationAgent."""

    # Initialize the agent
    agent = ProposalSummarizationAgent()

    # Example proposal content
    sample_proposal_content = """
    We propose to establish a community treasury management committee consisting of 5 elected members
    who will oversee the allocation and investment of DAO funds. The committee will be responsible for:
    
    1. Reviewing and approving treasury investment strategies
    2. Monitoring portfolio performance and risk metrics  
    3. Reporting quarterly to the DAO membership on financial status
    4. Implementing transparent governance processes for fund allocation
    
    This committee will help professionalize our treasury management while maintaining
    decentralized oversight through community elections every 12 months. The total budget
    requested is 50,000 tokens for operational expenses over the first year.
    
    Expected outcomes:
    - Improved treasury performance through professional management
    - Enhanced transparency and accountability in fund allocation
    - Risk mitigation through diversified investment strategies
    - Quarterly reporting to maintain community trust
    """

    # Prepare the state dictionary with required input
    state: Dict[str, Any] = {
        "proposal_content": sample_proposal_content,
        "dao_name": "Example DAO",
        "proposal_type": "treasury_management",
    }

    print("🤖 Running Proposal Summarization Agent...")
    print(f"📄 Input content length: {len(sample_proposal_content)} characters")
    print()

    # Process the proposal content
    result = await agent.process(state)

    # Display results
    if "error" in result:
        print(f"❌ Error: {result['error']}")
    else:
        print("✅ Generated Title and Summary:")
        print(f"📝 Title: {result['title']}")
        print(f"📋 Summary: {result['summary']}")
        print()
        print("📊 Metadata:")
        print(f"   • Content Length: {result.get('content_length', 'N/A')} characters")
        print(f"   • DAO Name: {result.get('dao_name', 'N/A')}")
        print(f"   • Proposal Type: {result.get('proposal_type', 'N/A')}")

        if "token_usage" in result:
            token_info = result["token_usage"]
            print(f"   • Input Tokens: {token_info.get('input_tokens', 'N/A')}")
            print(f"   • Output Tokens: {token_info.get('output_tokens', 'N/A')}")
            print(f"   • Total Tokens: {token_info.get('total_tokens', 'N/A')}")


async def example_multiple_proposals():
    """Example of processing multiple different types of proposals."""

    agent = ProposalSummarizationAgent()

    proposals = [
        {
            "content": "Proposal to implement a new governance token staking mechanism that rewards long-term holders with increased voting power and yield farming opportunities.",
            "dao_name": "DeFi DAO",
            "type": "tokenomics",
        },
        {
            "content": "We propose to fund a developer grant program with 100,000 tokens to support open-source projects that benefit our ecosystem.",
            "dao_name": "Developer DAO",
            "type": "funding",
        },
        {
            "content": "Motion to update the DAO constitution to include new clauses about member responsibilities and conflict resolution procedures.",
            "dao_name": "Governance DAO",
            "type": "constitutional_amendment",
        },
    ]

    print("🔄 Processing Multiple Proposals...")
    print()

    for i, proposal in enumerate(proposals, 1):
        state = {
            "proposal_content": proposal["content"],
            "dao_name": proposal["dao_name"],
            "proposal_type": proposal["type"],
        }

        result = await agent.process(state)

        print(f"📋 Proposal {i} ({proposal['type']}):")
        if "error" not in result:
            print(f"   Title: {result['title']}")
            print(f"   Summary: {result['summary']}")
        else:
            print(f"   Error: {result['error']}")
        print()


if __name__ == "__main__":
    print("🚀 Proposal Summarization Agent Examples")
    print("=" * 50)
    print()

    # Run the basic example
    asyncio.run(example_proposal_summarization())

    print("\n" + "=" * 50)
    print()

    # Run the multiple proposals example
    asyncio.run(example_multiple_proposals())
