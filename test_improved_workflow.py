#!/usr/bin/env python3
"""
Test script for the improved proposal evaluation workflow.

This script tests the enhanced supervisor logic and completion tracking
to ensure we don't have infinite loops with core agent invocations.
"""

import asyncio
import os
import sys
from uuid import uuid4

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.logger import configure_logger
from services.workflows.proposal_evaluation import evaluate_proposal

logger = configure_logger(__name__)


async def test_improved_workflow():
    """Test the improved workflow with better supervision."""
    print("🧪 Testing Improved Proposal Evaluation Workflow")
    print("=" * 60)

    # Test with a simple proposal
    test_proposal_id = str(uuid4())
    test_proposal_data = """
    Proposal: Fund AI Development Initiative
    
    We request 500 tokens to develop advanced AI capabilities for the DAO.
    This will help automate proposal evaluation and improve decision-making.
    
    Timeline: 3 months
    Deliverables:
    - Enhanced AI evaluation system
    - Automated proposal scoring
    - Integration with existing DAO infrastructure
    
    Budget breakdown:
    - Development: 300 tokens
    - Testing: 100 tokens
    - Documentation: 100 tokens
    """

    try:
        print(f"📋 Proposal ID: {test_proposal_id}")
        print(f"📝 Proposal Content: {len(test_proposal_data)} characters")
        print("\n🚀 Starting evaluation...")

        # Configure with debugging enabled
        config = {
            "model_name": "gpt-4.1",
            "debug_level": 2,
            "recursion_limit": 15,  # Lower limit to catch issues faster
        }

        result = await evaluate_proposal(
            proposal_id=test_proposal_id,
            proposal_data=test_proposal_data,
            config=config,
        )

        print("\n✅ Evaluation completed successfully!")
        print("=" * 60)

        # Display results
        print(f"📊 Final Decision: {result.get('approve', 'Unknown')}")
        print(f"🎯 Confidence: {result.get('confidence_score', 0):.2f}")
        print(f"💭 Reasoning: {result.get('reasoning', 'N/A')}")

        # Display scores breakdown
        scores = result.get("scores", {})
        print(f"\n📈 Score Breakdown:")
        for score_type, score_value in scores.items():
            print(f"   • {score_type.title()}: {score_value}")

        # Display workflow tracking info
        print(f"\n🔄 Workflow Info:")
        print(f"   • Final Step: {result.get('workflow_step', 'Unknown')}")
        print(f"   • Completed Steps: {result.get('completed_steps', [])}")

        # Display flags if any
        flags = result.get("flags", [])
        if flags:
            print(f"\n⚠️  Flags:")
            for flag in flags:
                print(f"   • {flag}")

        # Display token usage
        token_usage = result.get("token_usage", {})
        if token_usage:
            print(f"\n� Token Usage:")
            print(f"   • Input: {token_usage.get('input_tokens', 0)}")
            print(f"   • Output: {token_usage.get('output_tokens', 0)}")
            print(f"   • Total: {token_usage.get('total_tokens', 0)}")

        # Check for error indicators
        if "error" in result:
            print(f"\n❌ Error detected: {result['error']}")
            return False

        # Validate that we didn't hit recursion limits
        if any("halted" in flag.lower() for flag in flags):
            print(f"\n⚠️  Workflow was halted - potential infinite loop detected")
            return False

        print(f"\n🎉 Test completed successfully!")
        return True

    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


async def test_edge_cases():
    """Test edge cases that previously caused infinite loops."""
    print("\n🧪 Testing Edge Cases")
    print("=" * 60)

    edge_cases = [
        {
            "name": "Empty Proposal",
            "data": "",
        },
        {
            "name": "Very Short Proposal",
            "data": "Fund 100 tokens for project X.",
        },
        {
            "name": "Proposal with Images",
            "data": "Fund AI project. See details: https://example.com/image.png",
        },
    ]

    all_passed = True

    for i, case in enumerate(edge_cases, 1):
        print(f"\n🔬 Test Case {i}: {case['name']}")
        print("-" * 40)

        try:
            test_id = str(uuid4())
            config = {"recursion_limit": 10}  # Very low limit

            result = await evaluate_proposal(
                proposal_id=test_id,
                proposal_data=case["data"],
                config=config,
            )

            # Check if we completed without errors
            if "error" not in result:
                print(f"   ✅ Passed - Decision: {result.get('approve', 'Unknown')}")
            else:
                print(f"   ⚠️  Completed with error: {result['error']}")
                # Errors are ok for edge cases, as long as we don't infinite loop

        except Exception as e:
            print(f"   ❌ Failed: {str(e)}")
            all_passed = False

    return all_passed


if __name__ == "__main__":

    async def main():
        print("🚀 Starting Improved Workflow Tests")
        print("=" * 80)

        # Test 1: Basic functionality
        test1_passed = await test_improved_workflow()

        # Test 2: Edge cases
        test2_passed = await test_edge_cases()

        print("\n" + "=" * 80)
        print("📊 Test Summary")
        print("=" * 80)
        print(f"✅ Basic Workflow Test: {'PASSED' if test1_passed else 'FAILED'}")
        print(f"✅ Edge Cases Test: {'PASSED' if test2_passed else 'FAILED'}")

        overall_success = test1_passed and test2_passed
        print(
            f"\n🎯 Overall Result: {'ALL TESTS PASSED' if overall_success else 'SOME TESTS FAILED'}"
        )

        if overall_success:
            print("\n🎉 Workflow improvements are working correctly!")
            print("The infinite loop issue should now be resolved.")
        else:
            print("\n⚠️  Some issues remain - check the logs above.")

        return 0 if overall_success else 1

    sys.exit(asyncio.run(main()))
