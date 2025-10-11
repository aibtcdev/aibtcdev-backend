#!/usr/bin/env python3
"""
Test script for X OAuth integration.
This script tests the sync_user_after_oauth_link functionality.
"""

import asyncio
import sys
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))

from app.services.processing.twitter_data_service import twitter_data_service
from app.lib.logger import configure_logger

logger = configure_logger(__name__)


async def test_x_oauth_sync():
    """Test the X OAuth sync functionality."""
    try:
        logger.info("Testing X OAuth sync functionality...")

        # Test with a known Twitter user (Elon Musk)
        test_username = "davek_btc"
        test_provider_id = "59159134"  # Elon's Twitter ID
        test_supabase_user_id = "test-user-123"

        logger.info(f"Testing sync for user: {test_username}")

        # Call the sync method
        user_db_id = await twitter_data_service.sync_user_after_oauth_link(
            username=test_username,
            provider_id=test_provider_id,
            supabase_user_id=test_supabase_user_id,
        )

        if user_db_id:
            logger.info(
                f"✅ Successfully synced user {test_username} with DB ID: {user_db_id}"
            )
            return True
        else:
            logger.error(f"❌ Failed to sync user {test_username}")
            return False

    except Exception as e:
        logger.error(f"❌ Error in test: {str(e)}", exc_info=True)
        return False


async def test_auth_endpoint():
    """Test the auth endpoint functionality."""
    try:
        logger.info("Testing auth endpoint...")

        # This would normally be called by your OAuth flow
        from app.api.auth import handle_x_oauth_completion, XOAuthData

        oauth_data = XOAuthData(
            user_id="test-user-456", provider_id="59159134", username="davek_btc"
        )

        result = await handle_x_oauth_completion(oauth_data)

        if result.get("success"):
            logger.info(f"✅ Auth endpoint test successful: {result}")
            return True
        else:
            logger.error(f"❌ Auth endpoint test failed: {result}")
            return False

    except Exception as e:
        logger.error(f"❌ Error in auth endpoint test: {str(e)}", exc_info=True)
        return False


async def main():
    """Run all tests."""
    logger.info("🚀 Starting X OAuth integration tests...")

    # Check if required environment variables are set
    required_vars = [
        "AIBTC_TWITTER_BEARER_TOKEN",
        "HUGGING_FACE_TOKEN",
        "HUGGING_FACE_API_URL",
    ]

    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        logger.error(
            f"❌ Missing required environment variables: {', '.join(missing_vars)}"
        )
        logger.error("Please set these in your .env file or environment")
        return 1

    logger.info("✅ All required environment variables are set")

    # Test 1: Direct sync method
    logger.info("\n📋 Test 1: Direct sync method")
    test1_result = await test_x_oauth_sync()

    # Test 2: Auth endpoint
    logger.info("\n📋 Test 2: Auth endpoint")
    test2_result = await test_auth_endpoint()

    # Summary
    logger.info("\n📊 Test Results:")
    logger.info(f"  Direct sync method: {'✅ PASS' if test1_result else '❌ FAIL'}")
    logger.info(f"  Auth endpoint: {'✅ PASS' if test2_result else '❌ FAIL'}")

    if test1_result and test2_result:
        logger.info("🎉 All tests passed! X OAuth integration is working correctly.")
        return 0
    else:
        logger.error("💥 Some tests failed. Please check the logs above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
