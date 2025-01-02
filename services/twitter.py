import os
from backend.factory import backend
from backend.models import XTweetCreate, XTweetFilter, XUserCreate, Profile
from dotenv import load_dotenv
from lib.logger import configure_logger
from lib.twitter import TwitterService
from services.flow import execute_twitter_stream
from typing import Dict, List, Optional, TypedDict
from uuid import UUID
from datetime import datetime

# Configure logger
logger = configure_logger(__name__)


class UserProfile(TypedDict):
    """Type definition for user profile data."""

    name: str  # User's full name
    age: int  # User's age
    email: str  # User's email address


class TwitterMentionHandler:
    """Handles Twitter mention processing and responses."""

    def __init__(self):
        """Initialize Twitter components and configuration."""
        self.twitter_service = TwitterService(
            consumer_key=os.getenv("AIBTC_TWITTER_CONSUMER_KEY", ""),
            consumer_secret=os.getenv("AIBTC_TWITTER_CONSUMER_SECRET", ""),
            client_id=os.getenv("AIBTC_TWITTER_CLIENT_ID", ""),
            client_secret=os.getenv("AIBTC_TWITTER_CLIENT_SECRET", ""),
            access_token=os.getenv("AIBTC_TWITTER_ACCESS_TOKEN", ""),
            access_secret=os.getenv("AIBTC_TWITTER_ACCESS_SECRET", ""),
        )
        self.user_id = os.getenv("AIBTC_TWITTER_AUTOMATED_USER_ID")
        self.whitelisted_authors = os.getenv("AIBTC_TWITTER_WHITELISTED", "").split(",")
        logger.info(
            f"📋 Initialized with whitelist: {self.whitelisted_authors} (types: {[type(x) for x in self.whitelisted_authors]})"
        )

    async def _handle_mention(self, mention) -> None:
        """Process a single mention and generate response if needed."""
        tweet_id = mention.id or ""
        author_id = mention.author_id or ""
        conversation_id = mention.conversation_id or ""
        text = mention.text or ""

        logger.info("🎯 New mention detected:")
        logger.info(f"  Tweet ID: {tweet_id}")
        logger.info(f"  Author ID: {author_id} (type: {type(author_id)})")
        logger.info(f"  Text: {text}")

        # Check if tweet exists in our database
        existing_tweet = backend.get_x_tweet(tweet_id)
        if existing_tweet:
            logger.debug(f"⏭️  Skipping already processed tweet {tweet_id}")
            return

        # Create or get the X user
        existing_user = backend.get_x_user(author_id)
        if not existing_user:
            logger.info(f"Creating new X user with ID {author_id}")
            backend.create_x_user(XUserCreate(id=author_id))

        tweet_data = {
            "tweet_id": tweet_id,
            "author_id": author_id,
            "text": text,
            "conversation_id": conversation_id,
        }

        try:
            if self._is_author_whitelisted(author_id):
                logger.info(
                    f"Processing whitelisted mention {tweet_id} from user {author_id}"
                )
                await self._generate_and_post_response(tweet_data)
            else:
                logger.debug(
                    f"Skipping non-whitelisted mention {tweet_id} from user {author_id}"
                )
        finally:
            # Always store the tweet and log its processing
            backend.create_x_tweet(
                XTweetCreate(
                    id=tweet_id,
                    author_id=author_id,
                    message=text
                )
            )

    def _is_author_whitelisted(self, author_id: str) -> bool:
        """Check if the author is in the whitelist."""
        logger.info(
            f"🔍 Whitelist check details:"
        )
        logger.info(
            f"  Author ID: {author_id} (type: {type(author_id)})"
        )
        logger.info(
            f"  Whitelist: {self.whitelisted_authors} (types: {[type(x) for x in self.whitelisted_authors]})"
        )
        
        is_whitelisted = str(author_id) in self.whitelisted_authors
        logger.info(
            f"  Result: {'✅ Whitelisted' if is_whitelisted else '❌ Not whitelisted'}"
        )
        return is_whitelisted

    async def _generate_and_post_response(self, tweet_data: Dict) -> None:
        """Generate and post a response to a tweet."""
        history = await self._get_conversation_history(tweet_data)
        response = await self._generate_response(tweet_data, history)

        if response:
            await self._post_response(tweet_data, response)

    async def _get_conversation_history(self, tweet_data: Dict) -> List[Dict]:
        """Retrieve and format conversation history."""
        if not tweet_data["conversation_id"]:
            return []

        # Get all tweets in the conversation thread
        conversation_tweets = backend.list_x_tweets(
            filters=XTweetFilter(conversation_id=tweet_data["conversation_id"])
        )
        return [
            {
                "role": "user" if tweet.author_id != self.user_id else "assistant",
                "content": tweet.message,
            }
            for tweet in conversation_tweets
            if tweet.message
        ]

    async def _generate_response(
        self, tweet_data: Dict, history: List[Dict]
    ) -> Optional[str]:
        """Generate a response using the AI model."""
        logger.info(
            f"Processing tweet {tweet_data['tweet_id']} from user {tweet_data['author_id']}"
        )
        logger.debug(f"Tweet text: {tweet_data['text']}")
        logger.debug(f"Conversation history: {len(history)} messages")

        response_content = None
        profile = Profile(
            id=UUID('00000000-0000-0000-0000-000000000000'),  # Placeholder UUID
            created_at=datetime.now(),
            account_index=0
        )
        async for response in execute_twitter_stream(
            twitter_service=self.twitter_service,
            profile=profile,
            history=history,
            input_str=tweet_data["text"],
            author_id=tweet_data["author_id"]
        ):
            if response["type"] == "result":
                if response.get("content"):
                    logger.info(f"Final Response: {response['content']}")
                    response_content = response["content"]
                elif response.get("reason"):
                    logger.info(f"No response generated. Reason: {response['reason']}")
            elif response["type"] == "step":
                logger.debug(f"Step: {response['content']}")
                if response["result"]:
                    logger.debug(f"Result: {response['result']}")

        return response_content

    async def _post_response(self, tweet_data: Dict, response_content: str) -> None:
        """Post the response to Twitter and store in database."""
        response_tweet = await self.twitter_service.post_tweet(
            text=response_content, reply_in_reply_to_tweet_id=tweet_data["tweet_id"]
        )

        if response_tweet and response_tweet.id:
            # Store the response tweet
            backend.create_x_tweet(
                XTweetCreate(
                    id=response_tweet.id,
                    author_id=self.user_id,
                    message=response_content
                )
            )
            # Log the response
            backend.create_x_tweet(
                XTweetCreate(
                    id=None,
                    author_id=None,
                    message=f"Response to tweet {tweet_data['tweet_id']}"
                )
            )
            logger.info(
                f"Stored bot response in database. Response tweet ID: {response_tweet.id}"
            )

    async def process_mentions(self) -> None:
        """Process all new mentions for the bot user."""
        try:
            logger.info("🔍 Checking for new mentions...")
            
            # Initialize Twitter service and get mentions
            await self.twitter_service.initialize()
            mentions = await self.twitter_service.get_mentions_by_user_id(self.user_id)

            if not mentions:
                logger.info("👻 No new mentions found")
                return

            logger.info(f"📥 Found {len(mentions)} new mentions to process")

            for mention in mentions:
                try:
                    logger.info("-----------------------------------")
                    await self._handle_mention(mention)
                except Exception as e:
                    logger.error(f"❌ Error processing mention {mention.id}: {str(e)}")

            logger.info("✅ Mention processing complete")
            logger.info("===================================")

        except Exception as e:
            logger.error(f"❌ Error processing mentions: {str(e)}")
            raise


# Global handler instance
load_dotenv()
handler = TwitterMentionHandler()


async def execute_twitter_job() -> None:
    """Execute the Twitter job to process mentions."""
    try:
        if not handler.user_id:
            logger.error("AIBTC_TWITTER_AUTOMATED_USER_ID not set")
            return

        logger.info("Starting Twitter mention check")
        await handler.process_mentions()
        logger.info("Completed Twitter mention check")

    except Exception as e:
        logger.error(f"Error in Twitter job: {str(e)}")
        raise
