#!/usr/bin/env python3
"""
Test script for debugging the analyze_bitcoin_face function
"""

import os
import sys
from dotenv import load_dotenv

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))

# Load environment variables
load_dotenv()

from app.services.processing.twitter_data_service import analyze_bitcoin_face
from app.config import config
from app.lib.logger import configure_logger

logger = configure_logger(__name__)


def test_bitcoin_face_analysis():
    """Test the analyze_bitcoin_face function with a sample image."""

    print("=== Bitcoin Face Analysis Test ===")

    # Print configuration
    print(f"HuggingFace API URL: {config.huggingface.api_url}")
    print(f"HuggingFace Token present: {bool(config.huggingface.token)}")
    if config.huggingface.token:
        print(f"HuggingFace Token (first 10 chars): {config.huggingface.token[:10]}...")

    # Test with a sample Twitter profile image URL
    # This is a sample Bitcoin-related profile image
    test_image_url = "https://pbs.twimg.com/profile_images/1234567890/sample_normal.jpg"

    print(f"\nTesting with image URL: {test_image_url}")

    # Test the function
    result = analyze_bitcoin_face(test_image_url)

    print(f"\nResult: {result}")

    if "error" in result:
        print(f"\n❌ Error detected: {result['error']}")

        # Check common issues
        if "token not found" in result["error"]:
            print("\n🔧 Fix: Set the HUGGING_FACE environment variable")
            print("   export HUGGING_FACE='your_huggingface_token_here'")

        elif "API not available" in result["error"]:
            print("\n🔧 Fix: Check if the HuggingFace API endpoint is accessible")
            print(f"   Try accessing: {config.huggingface.api_url}")

        elif "timeout" in result["error"]:
            print("\n🔧 Fix: The API might be slow or the model is cold starting")
            print("   Try again in a few minutes")

    else:
        print("\n✅ Success! Analysis completed")
        if isinstance(result, dict):
            for key, value in result.items():
                print(f"   {key}: {value}")


if __name__ == "__main__":
    test_bitcoin_face_analysis()
