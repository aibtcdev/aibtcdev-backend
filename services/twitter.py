import os
from backend.factory import backend
from backend.models import XTweetCreate, XTweetFilter, XUserCreate, XUserFilter
from dotenv import load_dotenv
from lib.logger import configure_logger
from lib.twitter import TwitterService
from services.flow import execute_twitter_stream
from typing import Dict, List, Optional, TypedDict

logger = configure_logger(__name__)


class UserProfile(TypedDict):
    """Type definition for user profile data."""

    name: str
    age: int
    email: str


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
        try:
            existing_tweets = backend.list_x_tweets(
                filters=XTweetFilter(tweet_id=tweet_id)
            )
            if existing_tweets and len(existing_tweets) > 0:
                logger.debug(f"Skipping already processed tweet {tweet_id}")
                return
        except Exception as e:
            logger.error(f"Error checking tweet {tweet_id} in database: {str(e)}")

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
            authors = backend.list_x_users(filters=XUserFilter(user_id=author_id))
            if authors and len(authors) > 0:
                author = authors[0]
                backend.create_x_tweet(
                    XTweetCreate(
                        author_id=author.id,
                        tweet_id=tweet_id,
                        message=text,
                        conversation_id=conversation_id,
                    )
                )
            else:
                author = backend.create_x_user(
                    XUserCreate(
                        user_id=author_id,
                    )
                )
                backend.create_x_tweet(
                    XTweetCreate(
                        author_id=author.id,
                        tweet_id=tweet_id,
                        message=text,
                        conversation_id=conversation_id,
                    )
                )

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

        # Get all tweets in the conversation
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
        async for response in execute_twitter_stream(
            twitter_service=self.twitter_service,
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
        response_tweet = await self.twitter_service._apost_tweet(
            text=response_content, reply_in_reply_to_tweet_id=tweet_data["tweet_id"]
        )

        if response_tweet and response_tweet.id:
            # Store the response tweet
            backend.create_x_tweet(
                XTweetCreate(
                    tweet_id=response_tweet.id,
                    message=response_content,
                    conversation_id=tweet_data["conversation_id"],
                )
            )
            logger.info(
                f"Stored bot response in database. Response tweet ID: {response_tweet.id}"
            )

    async def process_mentions(self) -> None:
        """Process all new mentions for the bot user."""
        try:
            await self.twitter_service._ainitialize()
            mentions = await self.twitter_service.get_mentions_by_user_id(self.user_id)
            if not mentions:
                logger.debug("No mentions found")
                return

            for mention in mentions:
                try:
                    await self._handle_mention(mention)
                except Exception as e:
                    logger.error(f"Error processing mention {mention.id}: {str(e)}")
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
