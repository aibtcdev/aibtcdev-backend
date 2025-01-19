import asyncio
import logging
from lib.logger import configure_logger
from services.runner import execute_runner_job
from services.tweet_analysis import analyze_tweet

logger = configure_logger(__name__)
logging.getLogger().setLevel(logging.INFO)


async def test_tweet_analysis():
    """Test the tweet analysis functionality."""
    # Test tweet with DAO deployment request
    test_tweet = """
    Hey @aibtcdevagent, I want to create a DAO called "GamersUnite" with the symbol "GAME". 
    It's going to be a DAO for gamers to collaborate on blockchain gaming projects.
    Initial supply should be 1000000 GAME tokens with 6 decimals.
    Our mission is to bridge traditional gaming with blockchain technology.
    """

    logger.info("Testing tweet analysis...")
    result = await analyze_tweet(test_tweet, "")
    logger.info(f"Analysis result: {result}")

    if result["is_worthy"] and result["tool_request"]:
        logger.info("Tweet analysis passed, message sent to queue")

        # Now test the runner
        logger.info("Testing runner...")
        await execute_runner_job()
    else:
        logger.info(f"Tweet not worthy or no tool request. Reason: {result['reason']}")


async def main():
    """Run the test suite."""
    try:
        await test_tweet_analysis()
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
