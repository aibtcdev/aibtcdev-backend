#!/usr/bin/env python3
"""
Simple test script for XTweet retrieval from Supabase backend.

This test demonstrates basic XTweet retrieval functionality using the backend factory.

Usage:
    python test_xtweet_retrieval.py --tweet-id "123e4567-e89b-12d3-a456-426614174000"
    python test_xtweet_retrieval.py --tweet-id "123e4567-e89b-12d3-a456-426614174000" --verbose
"""

import argparse
import asyncio
import json
import os
import sys
from uuid import UUID

# Add the parent directory (root) to the path to import from app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.backend.factory import get_backend
from app.backend.models import XTweet
from app.lib.logger import configure_logger

logger = configure_logger(__name__)


def format_tweet_output(tweet: XTweet, verbose: bool = False) -> None:
    """Format and display tweet information."""
    print("\n✅ XTweet Retrieved Successfully!")
    print("=" * 60)
    print(f"ID: {tweet.id}")
    print(f"Tweet ID: {tweet.tweet_id}")
    print(f"Author Username: {tweet.author_username}")
    print(f"Author Name: {tweet.author_name}")
    print(f"Tweet Type: {tweet.tweet_type}")
    print(f"Is Worthy: {tweet.is_worthy}")
    print(f"Created At: {tweet.created_at}")
    print(f"Created At Twitter: {tweet.created_at_twitter}")

    # Show message content (truncated if too long)
    if tweet.message:
        message = tweet.message
        if len(message) > 200 and not verbose:
            message = message[:200] + "... (use --verbose to see full message)"
        print(f"Message: {message}")

    # Show confidence score and reason if available
    if tweet.confidence_score is not None:
        print(f"Confidence Score: {tweet.confidence_score}")
    if tweet.reason:
        print(f"Reason: {tweet.reason}")

    # Show images if any
    if tweet.images:
        print(f"Images ({len(tweet.images)}):")
        for i, image_url in enumerate(tweet.images, 1):
            print(f"  {i}. {image_url}")

    if verbose:
        print("\n📊 Detailed Information:")
        print(f"Author ID: {tweet.author_id}")
        print(f"Conversation ID: {tweet.conversation_id}")

        # Show public metrics if available
        if tweet.public_metrics:
            print(f"Public Metrics: {json.dumps(tweet.public_metrics, indent=2)}")

        # Show entities if available
        if tweet.entities:
            print(f"Entities: {json.dumps(tweet.entities, indent=2)}")

        # Show attachments if available
        if tweet.attachments:
            print(f"Attachments: {json.dumps(tweet.attachments, indent=2)}")


async def main():
    parser = argparse.ArgumentParser(
        description="Test XTweet retrieval from Supabase backend",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic tweet retrieval
  python test_xtweet_retrieval.py --tweet-id "12345678-1234-5678-9012-123456789abc"
  
  # Verbose output with all details
  python test_xtweet_retrieval.py --tweet-id "12345678-1234-5678-9012-123456789abc" --verbose
        """,
    )

    # Required arguments
    parser.add_argument(
        "--tweet-id",
        type=str,
        required=True,
        help="UUID of the XTweet to retrieve",
    )

    # Optional arguments
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed tweet information including metadata",
    )

    args = parser.parse_args()

    print("🚀 Starting XTweet Retrieval Test")
    print("=" * 60)
    print(f"Tweet ID: {args.tweet_id}")
    print(f"Verbose: {args.verbose}")
    print("=" * 60)

    try:
        # Validate UUID format
        try:
            tweet_uuid = UUID(args.tweet_id)
        except ValueError as e:
            print(f"❌ Error: Invalid UUID format: {e}")
            sys.exit(1)

        # Get backend instance
        print("🔗 Connecting to backend...")
        backend = get_backend()

        # Retrieve the tweet
        print(f"🔍 Retrieving XTweet with ID: {tweet_uuid}")
        tweet = backend.get_x_tweet(tweet_uuid)

        if tweet is None:
            print(f"❌ Error: XTweet with ID {args.tweet_id} not found in database")
            sys.exit(1)

        # Display the tweet information
        format_tweet_output(tweet, args.verbose)

    except Exception as e:
        print(f"❌ Error during XTweet retrieval: {str(e)}")
        logger.error(f"XTweet retrieval failed: {str(e)}", exc_info=True)
        sys.exit(1)

    print("\n🎉 Test completed successfully!")


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
