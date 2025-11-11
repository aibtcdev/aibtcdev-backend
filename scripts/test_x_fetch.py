"""Test script to fetch X posts for a given username.

Usage:
    python scripts/test_x_fetch.py --username manlike_greg
    python scripts/test_x_fetch.py -u manlike_greg
"""

import asyncio
import argparse
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.ai.simple_workflows.evaluation import fetch_x_posts_for_user
from app.lib.logger import configure_logger

logger = configure_logger(__name__)


async def test_fetch_x_posts(username: str):
    """Test fetching X posts for a username.
    
    Args:
        username: X username (with or without @)
    """
    # Clean username (remove @ if present)
    clean_username = username.lstrip("@")
    
    print(f"\n{'='*80}")
    print(f"Testing X Posts Fetch for @{clean_username}")
    print(f"{'='*80}\n")
    
    try:
        # Fetch posts
        result = await fetch_x_posts_for_user(clean_username)
        
        print("\n" + "="*80)
        print("RESULT:")
        print("="*80)
        print(result)
        
        # Check for errors
        if result and result.get("error"):
            print("\n" + "="*80)
            print("❌ ERROR DETECTED:")
            print("="*80)
            print(result.get("error"))
            
            # Check if it's a rate limit error
            if "rate limit" in result.get("error", "").lower():
                print("\n⚠️  RATE LIMIT HIT - Wait 60 seconds and try again")
            
            return False
        
        print("\n" + "="*80)
        print("RAW RESPONSE:")
        print("="*80)
        print(result.get("raw_response") if result else "None")
        
        print("\n" + "="*80)
        print("STATS:")
        print("="*80)
        if result and result.get("raw_response"):
            raw = result["raw_response"]
            print(f"Length: {len(raw)} chars")
            print(f"'--- POST' count: {raw.count('--- POST')}")
            print(f"Lines: {len(raw.splitlines())}")
            return True
        else:
            print("No response data")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR - Failed to fetch posts for @{clean_username}")
        print(f"Error: {str(e)}\n")
        logger.exception(f"Error fetching X posts for @{clean_username}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test X posts fetching for a given username"
    )
    parser.add_argument(
        "-u", "--username",
        required=True,
        help="X username (with or without @)"
    )
    
    args = parser.parse_args()
    
    # Run the async test
    success = asyncio.run(test_fetch_x_posts(args.username))
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
