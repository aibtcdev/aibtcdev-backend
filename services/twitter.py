import os
from db.helpers import (
    add_twitter_log,
    add_twitter_tweet,
    get_author_tweets,
    get_thread_tweets,
    get_twitter_author,
    get_twitter_tweet,
)
from dotenv import load_dotenv
from lib.logger import configure_logger
from lib.twitter import TwitterService
from services.flow import execute_twitter_stream
from typing import Dict, List, Optional, TypedDict

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

    async def _handle_mention(self, mention) -> None:
        """Process a single mention and generate response if needed."""
        tweet_id = mention.id or ""
        author_id = mention.author_id or ""
        conversation_id = mention.conversation_id or ""
        text = mention.text or ""

        # Check if tweet exists in our database
        existing_tweet = get_twitter_tweet(tweet_id)
        if existing_tweet:
            logger.debug(f"Skipping already processed tweet {tweet_id}")
            return

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
            add_twitter_tweet(
                author_id=author_id,
                tweet_id=tweet_id,
                tweet_body=text,
                thread_id=int(conversation_id) if conversation_id else None,
            )
            add_twitter_log(tweet_id=tweet_id, status="processed")

    def _is_author_whitelisted(self, author_id: str) -> bool:
        """Check if the author is in the whitelist."""
        logger.debug(
            f"Checking author {author_id} against whitelist {self.whitelisted_authors}"
        )
        return str(author_id) in self.whitelisted_authors

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
        conversation_tweets = get_thread_tweets(int(tweet_data["conversation_id"]))
        return [
            {
                "role": "user" if tweet.author_id != self.user_id else "assistant",
                "content": tweet.tweet_body,
            }
            for tweet in conversation_tweets
            if tweet.tweet_body
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
        async for response in execute_twitter_stream(
            twitter_service=self.twitter_service,
            account_index="0",
            history=history,
            input_str=tweet_data["text"],
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
            add_twitter_tweet(
                author_id=self.user_id,
                tweet_id=response_tweet.id,
                tweet_body=response_content,
                thread_id=(
                    int(tweet_data["conversation_id"])
                    if tweet_data["conversation_id"]
                    else None
                ),
            )
            # Log the response
            add_twitter_log(
                tweet_id=response_tweet.id,
                status="response_posted",
                message=f"Response to tweet {tweet_data['tweet_id']}",
            )
            logger.info(
                f"Stored bot response in database. Response tweet ID: {response_tweet.id}"
            )

    async def process_mentions(self) -> None:
        """Process all new mentions for the bot user."""
        try:
            await self.twitter_service.initialize()
            mentions = await self.twitter_service.get_mentions_by_user_id(self.user_id)
            if not mentions:
                logger.debug("No mentions found")
                return

            for mention in mentions:
                try:
                    await self._handle_mention(mention)
                except Exception as e:
                    logger.error(f"Error processing mention {mention.id}: {str(e)}")
                    # Log the error
                    add_twitter_log(tweet_id=mention.id, status="error", message=str(e))
                    # Continue processing other mentions even if one fails
                    continue

        except Exception as e:
            logger.error(f"Error processing mentions: {str(e)}")
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
