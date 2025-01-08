import os
import pytest
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from lib.twitter import TwitterService
from lib.logger import configure_logger

# Configure logger
logger = configure_logger(__name__)

# Load environment variables
load_dotenv()

@pytest.fixture
def twitter_service():
    """Create a TwitterService instance with credentials from env vars."""
    service = TwitterService(
        consumer_key=os.getenv("AIBTC_TWITTER_CONSUMER_KEY", ""),
        consumer_secret=os.getenv("AIBTC_TWITTER_CONSUMER_SECRET", ""),
        client_id=os.getenv("AIBTC_TWITTER_CLIENT_ID", ""),
        client_secret=os.getenv("AIBTC_TWITTER_CLIENT_SECRET", ""),
        access_token=os.getenv("AIBTC_TWITTER_ACCESS_TOKEN", ""),
        access_secret=os.getenv("AIBTC_TWITTER_ACCESS_SECRET", ""),
    )
    return service

def test_environment_variables():
    """Test that all required Twitter environment variables are set."""
    required_vars = [
        "AIBTC_TWITTER_CONSUMER_KEY",
        "AIBTC_TWITTER_CONSUMER_SECRET",
        "AIBTC_TWITTER_CLIENT_ID",
        "AIBTC_TWITTER_CLIENT_SECRET",
        "AIBTC_TWITTER_ACCESS_TOKEN",
        "AIBTC_TWITTER_ACCESS_SECRET",
        "AIBTC_TWITTER_AUTOMATED_USER_ID",
        "AIBTC_TWITTER_WHITELISTED"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    assert not missing_vars, f"Missing required environment variables: {', '.join(missing_vars)}"

@pytest.mark.asyncio
async def test_twitter_initialization(twitter_service):
    """Test that the Twitter client can be initialized."""
    try:
        await twitter_service.initialize()
        assert twitter_service.client is not None, "Twitter client should be initialized"
    except Exception as e:
        pytest.fail(f"Failed to initialize Twitter client: {str(e)}")

@pytest.mark.asyncio
async def test_get_bot_profile(twitter_service):
    """Test that we can fetch the bot's profile."""
    await twitter_service.initialize()
    try:
        # Try by username first
        user = await twitter_service.get_user_by_username("aibtcdevagent")
        if user is None:
            # Fall back to ID if username fails
            bot_id = os.getenv("AIBTC_TWITTER_AUTOMATED_USER_ID")
            user = await twitter_service.get_user_by_id(bot_id)
        
        assert user is not None, "Could not fetch bot profile"
        logger.info(f"Successfully fetched bot profile: @{user.username}")
    except Exception as e:
        pytest.fail(f"Failed to fetch bot profile: {str(e)}")

@pytest.mark.asyncio
async def test_get_mentions(twitter_service):
    """Test that we can fetch mentions."""
    await twitter_service.initialize()
    bot_id = os.getenv("AIBTC_TWITTER_AUTOMATED_USER_ID")
    try:
        mentions = await twitter_service.get_mentions_by_user_id(bot_id, max_results=10)
        assert mentions is not None, "Mentions should not be None"
        logger.info(f"Successfully fetched {len(mentions)} mentions")
    except Exception as e:
        pytest.fail(f"Failed to fetch mentions: {str(e)}")

@pytest.mark.asyncio
async def test_post_and_delete_tweet(twitter_service):
    """Test that we can post and delete a tweet."""
    await twitter_service.initialize()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    test_text = f"🧪 This is a test tweet from the AIBTC Twitter API test suite at {timestamp}. It will be deleted shortly. 🔄"
    
    try:
        # Post tweet
        tweet = await twitter_service.post_tweet(text=test_text)
        assert tweet is not None, "Tweet should be created successfully"
        assert tweet.id is not None, "Tweet should have an ID"
        logger.info(f"Successfully posted test tweet with ID: {tweet.id}")
        
        # Delete tweet
        deleted = await twitter_service.delete_tweet(tweet.id)
        assert deleted is True, "Tweet should be deleted successfully"
        logger.info("Successfully deleted test tweet")
    except Exception as e:
        pytest.fail(f"Failed to post/delete tweet: {str(e)}")

@pytest.mark.asyncio
async def test_post_reply_to_tweet(twitter_service):
    """Test that we can post a reply to an existing tweet."""
    await twitter_service.initialize()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        # First post an initial tweet
        initial_text = f"🧪 Initial test tweet for reply testing at {timestamp}. Will be deleted shortly. 🔄"
        initial_tweet = await twitter_service.post_tweet(text=initial_text)
        assert initial_tweet is not None, "Initial tweet should be created successfully"
        assert initial_tweet.id is not None, "Initial tweet should have an ID"
        logger.info(f"Posted initial test tweet with ID: {initial_tweet.id}")
        
        # Now try to post a reply
        reply_text = f"🧪 This is a reply to the test tweet at {timestamp}. Will be deleted shortly. ↩️"
        reply_tweet = await twitter_service.post_tweet(
            text=reply_text,
            reply_in_reply_to_tweet_id=initial_tweet.id
        )
        assert reply_tweet is not None, "Reply tweet should be created successfully"
        assert reply_tweet.id is not None, "Reply tweet should have an ID"
        logger.info(f"Successfully posted reply tweet with ID: {reply_tweet.id}")
        
        # Clean up - delete both tweets
        for tweet_id in [reply_tweet.id, initial_tweet.id]:
            deleted = await twitter_service.delete_tweet(tweet_id)
            assert deleted is True, f"Tweet {tweet_id} should be deleted successfully"
            logger.info(f"Deleted tweet {tweet_id}")
            
    except Exception as e:
        pytest.fail(f"Failed to post/reply/delete tweets: {str(e)}")

@pytest.mark.asyncio
async def test_reply_to_other_user_tweet(twitter_service):
    """Test that we can reply to tweets from other users."""
    await twitter_service.initialize()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        # Get a tweet from hx2ai account
        twitter_handle = "hx2ai"  # Target account
        user = await twitter_service.get_user_by_username(twitter_handle)
        assert user is not None, f"Could not find user @{twitter_handle}"
        logger.info(f"Found user @{twitter_handle} with ID: {user.id}")
        
        # Get their recent tweets
        tweets = await twitter_service.get_user_tweets(user.id, max_results=5)
        assert tweets and len(tweets) > 0, f"No tweets found for @{twitter_handle}"
        target_tweet = tweets[0]  # Get the most recent tweet
        logger.info(f"Found tweet to reply to: {target_tweet.id}")
        logger.info(f"Tweet text: {target_tweet.text[:100]}...")
        
        # Try to post a reply
        reply_text = f"🧪 This is an automated test reply from AIBTC at {timestamp}. Will be deleted shortly. ↩️ #test"
        reply_tweet = await twitter_service.post_tweet(
            text=reply_text,
            reply_in_reply_to_tweet_id=target_tweet.id
        )
        assert reply_tweet is not None, "Reply tweet should be created successfully"
        assert reply_tweet.id is not None, "Reply tweet should have an ID"
        logger.info(f"Successfully posted reply tweet with ID: {reply_tweet.id}")
        
        # Clean up - delete our reply
        deleted = await twitter_service.delete_tweet(reply_tweet.id)
        assert deleted is True, "Reply tweet should be deleted successfully"
        logger.info(f"Deleted reply tweet {reply_tweet.id}")
            
    except Exception as e:
        pytest.fail(f"Failed to reply to other user's tweet: {str(e)}")

@pytest.mark.asyncio
async def test_whitelist_validation():
    """Test that whitelisted user IDs are valid."""
    whitelist = os.getenv("AIBTC_TWITTER_WHITELISTED", "").split(",")
    assert len(whitelist) > 0, "Whitelist should not be empty"
    
    # Check that all IDs are non-empty strings
    invalid_ids = [id for id in whitelist if not id.strip()]
    assert not invalid_ids, f"Found invalid whitelist IDs: {invalid_ids}"
    
    logger.info(f"Validated {len(whitelist)} whitelisted user IDs")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
