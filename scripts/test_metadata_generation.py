#!/usr/bin/env python3
"""
Simple CLI test script for proposal metadata generation.

This test uses the simplified metadata generation workflow that creates
title, summary, and tags for proposal content.

Usage:
    python test_metadata_generation.py --proposal-id "123e4567-e89b-12d3-a456-426614174000" --proposal-data "Some proposal content"
    python test_metadata_generation.py --proposal-id "123e4567-e89b-12d3-a456-426614174000" --proposal-data "Proposal content" --debug-level 2
    python test_metadata_generation.py --proposal-id "123e4567-e89b-12d3-a456-426614174000" --debug-level 2  # Lookup from database
"""

import argparse
import asyncio
import json
import os
import sys
from uuid import UUID

# Add the parent directory (root) to the path to import from app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.ai.simple_workflows.metadata import generate_proposal_metadata
from app.backend.factory import get_backend


async def main():
    parser = argparse.ArgumentParser(
        description="Test proposal metadata generation workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic metadata generation with proposal data
  python test_metadata_generation.py --proposal-id "12345678-1234-5678-9012-123456789abc" \\
    --proposal-data "Proposal to fund development of new feature"
  
  # Lookup proposal from database
  python test_metadata_generation.py --proposal-id "12345678-1234-5678-9012-123456789abc" \\
    --debug-level 2
  
  # With DAO context
  python test_metadata_generation.py --proposal-id "12345678-1234-5678-9012-123456789abc" \\
    --proposal-data "Proposal content" --dao-name "AIBTC" --proposal-type "funding" --debug-level 2
        """,
    )

    # Required arguments
    parser.add_argument(
        "--proposal-id",
        type=str,
        required=True,
        help="ID of the proposal to generate metadata for",
    )

    parser.add_argument(
        "--proposal-data",
        type=str,
        required=False,
        help="Content/data of the proposal (optional - will lookup from database if not provided)",
    )

    # Optional arguments
    parser.add_argument(
        "--dao-name",
        type=str,
        help="Name of the DAO",
    )

    parser.add_argument(
        "--proposal-type",
        type=str,
        help="Type of the proposal (e.g., funding, governance, technical)",
    )

    parser.add_argument(
        "--debug-level",
        type=int,
        choices=[0, 1, 2],
        default=0,
        help="Debug level: 0=normal, 1=verbose, 2=very verbose (default: 0)",
    )

    args = parser.parse_args()

    # If proposal_content is not provided, look it up from the database
    proposal_content = args.proposal_data
    dao_name = args.dao_name or ""
    proposal_type = args.proposal_type or ""

    if not proposal_content:
        print("📋 No proposal data provided, looking up from database...")
        try:
            backend = get_backend()
            proposal_uuid = UUID(args.proposal_id)
            proposal = backend.get_proposal(proposal_uuid)

            if not proposal:
                print(
                    f"❌ Error: Proposal with ID {args.proposal_id} not found in database"
                )
                sys.exit(1)

            if not proposal.content:
                print(f"❌ Error: Proposal {args.proposal_id} has no content")
                sys.exit(1)

            proposal_content = proposal.content
            print(f"✅ Found proposal in database: {proposal.title or 'Untitled'}")

            # Get DAO name if not provided and available in proposal
            if not dao_name and proposal.dao_id:
                try:
                    dao = backend.get_dao(proposal.dao_id)
                    if dao and dao.name:
                        dao_name = dao.name
                        print(f"✅ Using DAO name from database: {dao_name}")
                except Exception as e:
                    if args.debug_level >= 1:
                        print(f"⚠️  Could not retrieve DAO name: {e}")

            # Get proposal type if available
            if not proposal_type and hasattr(proposal, "proposal_type"):
                proposal_type = proposal.proposal_type or ""

        except ValueError as e:
            print(f"❌ Error: Invalid proposal ID format: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error looking up proposal: {e}")
            if args.debug_level >= 1:
                import traceback

                traceback.print_exc()
            sys.exit(1)

    print("🚀 Starting Proposal Metadata Generation Test")
    print("=" * 60)
    print(f"Proposal ID: {args.proposal_id}")
    print(
        f"Proposal Data: {proposal_content[:100]}{'...' if len(proposal_content) > 100 else ''}"
    )
    print(f"DAO Name: {dao_name or '(not specified)'}")
    print(f"Proposal Type: {proposal_type or '(not specified)'}")
    print(f"Debug Level: {args.debug_level}")
    print("=" * 60)

    try:
        # Generate metadata
        print("🔍 Generating metadata...")
        result = await generate_proposal_metadata(
            proposal_content=proposal_content,
            dao_name=dao_name,
            proposal_type=proposal_type,
            images=None,  # TODO: Support image processing if needed
            callbacks=None,
        )

        print("\n✅ Metadata Generation Complete!")
        print("=" * 60)

        # Check for errors
        if "error" in result and result["error"]:
            print(f"❌ Error during generation: {result['error']}")
            if args.debug_level >= 1:
                print("\n📄 Full Result JSON:")
                print(json.dumps(result, indent=2, default=str))
            sys.exit(1)

        # Pretty print the result
        print("📊 Generated Metadata:")
        print(f"   • Title: {result.get('title', 'N/A')}")
        print(f"   • Summary: {result.get('summary', 'N/A')}")
        print(f"   • Tags: {', '.join(result.get('tags', []))}")
        print(f"   • Tags Count: {result.get('tags_count', 0)}")
        print(f"   • Content Length: {result.get('content_length', 0)} characters")
        print(f"   • Images Processed: {result.get('images_processed', 0)}")

        # Show additional details in debug mode
        if args.debug_level >= 1:
            print("\n📋 Additional Details:")
            print(f"   • DAO Name: {result.get('dao_name', 'N/A')}")
            print(f"   • Proposal Type: {result.get('proposal_type', 'N/A')}")

        # Show full JSON in verbose debug mode
        if args.debug_level >= 2:
            print("\n📄 Full Result JSON:")
            print(json.dumps(result, indent=2, default=str))

        # Validate the output
        print("\n🔍 Validation:")
        validation_passed = True

        if not result.get("title"):
            print("   ❌ Title is empty")
            validation_passed = False
        elif len(result.get("title", "")) > 100:
            print(f"   ⚠️  Title exceeds 100 characters: {len(result['title'])}")
            validation_passed = False
        else:
            print(f"   ✅ Title is valid ({len(result.get('title', ''))} characters)")

        if not result.get("summary"):
            print("   ❌ Summary is empty")
            validation_passed = False
        elif len(result.get("summary", "")) > 500:
            print(f"   ⚠️  Summary exceeds 500 characters: {len(result['summary'])}")
            validation_passed = False
        else:
            print(
                f"   ✅ Summary is valid ({len(result.get('summary', ''))} characters)"
            )

        tags = result.get("tags", [])
        if not tags:
            print("   ❌ No tags generated")
            validation_passed = False
        elif len(tags) < 3:
            print(f"   ⚠️  Fewer than 3 tags: {len(tags)}")
            validation_passed = False
        elif len(tags) > 5:
            print(f"   ⚠️  More than 5 tags: {len(tags)}")
            validation_passed = False
        else:
            print(f"   ✅ Tags are valid ({len(tags)} tags)")

        if validation_passed:
            print("\n🎉 All validations passed!")
        else:
            print("\n⚠️  Some validations failed")

    except Exception as e:
        print(f"\n❌ Error during metadata generation: {str(e)}")
        if args.debug_level >= 1:
            import traceback

            traceback.print_exc()
        sys.exit(1)

    print("\n🎉 Metadata generation test completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
