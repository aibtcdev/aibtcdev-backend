import os
from backend.factory import backend
from backend.models import (
    QueueMessageCreate,
    XTweetBase,
    XTweetCreate,
    XTweetFilter,
    XUserCreate,
    XUserFilter,
)
from dotenv import load_dotenv
from lib.logger import configure_logger
from lib.twitter import TwitterService
from pydantic import BaseModel
from services.tweet_analysis import analyze_tweet
from typing import Dict, List, Optional, TypedDict

logger = configure_logger(__name__)


class UserProfile(TypedDict):
    """Type definition for user profile data."""

    name: str
    age: int
    email: str


class TweetData(BaseModel):
    """Pydantic model for tweet data."""

    tweet_id: Optional[str] = None
    author_id: Optional[str] = None
    text: Optional[str] = None
    conversation_id: Optional[str] = None


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
        self.whitelist_enabled = False

    async def _handle_mention(self, mention) -> None:
        """Process a single mention for analysis."""
        tweet_id = mention.id or ""
        author_id = mention.author_id or ""
        conversation_id = mention.conversation_id or ""
        text = mention.text or ""

        logger.debug(
            f"Processing mention - Tweet ID: {tweet_id}, Author: {author_id}, Text: {text[:50]}..."
        )

        # Check if tweet exists in our database
        try:
            existing_tweets = backend.list_x_tweets(
                filters=XTweetFilter(tweet_id=tweet_id)
            )
            if existing_tweets and len(existing_tweets) > 0:
                logger.debug(
                    f"Tweet {tweet_id} already exists in database, skipping processing"
                )
                return

        except Exception as e:
            logger.error(
                f"Database error checking tweet {tweet_id}: {str(e)}", exc_info=True
            )
            raise

        tweet_data = TweetData(
            tweet_id=tweet_id,
            author_id=author_id,
            text=text,
            conversation_id=conversation_id,
        )

        # Store tweet and author data
        try:
            authors = backend.list_x_users(filters=XUserFilter(user_id=author_id))
            if authors and len(authors) > 0:
                author = authors[0]
                logger.debug(f"Found existing author {author_id} in database")
            else:
                logger.info(f"Creating new author record for {author_id}")
                author = backend.create_x_user(XUserCreate(user_id=author_id))

            logger.debug(f"Creating tweet record for {tweet_id}")
            backend.create_x_tweet(
                XTweetCreate(
                    author_id=author.id,
                    tweet_id=tweet_id,
                    message=text,
                    conversation_id=conversation_id,
                )
            )
        except Exception as e:
            logger.error(f"Failed to store tweet/author data: {str(e)}", exc_info=True)
            raise

        try:
            if self.whitelist_enabled:
                if self._is_author_whitelisted(author_id):
                    logger.info(
                        f"Processing whitelisted mention {tweet_id} from user {author_id}"
                    )
                    await self._analyze_tweet(tweet_data)
                else:
                    logger.warning(
                        f"Skipping non-whitelisted mention {tweet_id} from user {author_id}"
                    )
            else:
                logger.debug("Whitelist check disabled, processing all mentions")
                await self._analyze_tweet(tweet_data)
        except Exception as e:
            logger.error(
                f"Failed to analyze mention {tweet_id}: {str(e)}", exc_info=True
            )
            raise

    def _is_author_whitelisted(self, author_id: str) -> bool:
        """Check if the author is in the whitelist."""
        logger.debug(f"Checking whitelist status for author {author_id}")
        is_whitelisted = str(author_id) in self.whitelisted_authors
        logger.debug(f"Author {author_id} whitelist status: {is_whitelisted}")
        return is_whitelisted

    async def _analyze_tweet(self, tweet_data: TweetData) -> None:
        """Analyze tweet and queue if needed."""
        logger.debug(f"Starting tweet analysis for {tweet_data.tweet_id}")
        history = []
        await self._run_analysis(tweet_data, history)

    async def _run_analysis(self, tweet_data: TweetData, history: List[Dict]) -> None:
        """Run analysis on tweet and queue tool requests if needed."""
        logger.info(
            f"Analyzing tweet {tweet_data.tweet_id} from user {tweet_data.author_id}"
        )
        logger.debug(f"Tweet content: {tweet_data.text}")
        logger.debug(f"Conversation history size: {len(history)} messages")

        # Convert history to filtered content
        filtered_content = "\n".join(
            f"{msg['role']}: {msg['content']}" for msg in history
        )

        try:
            # Analyze tweet
            analysis_result = await analyze_tweet(
                tweet_text=tweet_data.text,
                filtered_content=filtered_content,
            )

            logger.info(
                f"Analysis complete for {tweet_data.tweet_id} - "
                f"Worthy: {analysis_result['is_worthy']}, "
                f"Type: {analysis_result['tweet_type']}, "
                f"Confidence: {analysis_result['confidence_score']}"
            )
            logger.debug(f"Analysis reason: {analysis_result['reason']}")

            tweets = backend.list_x_tweets(
                filters=XTweetFilter(tweet_id=tweet_data.tweet_id)
            )
            if tweets and len(tweets) > 0:
                logger.debug(f"Updating existing tweet record with analysis results")
                backend.update_x_tweet(
                    x_tweet_id=tweets[0].id,
                    update_data=XTweetBase(
                        is_worthy=analysis_result["is_worthy"],
                        tweet_type=analysis_result["tweet_type"],
                        confidence_score=analysis_result["confidence_score"],
                        reason=analysis_result["reason"],
                    ),
                )

            # If worthy and tool request, send to queue
            if analysis_result["is_worthy"] and analysis_result["tool_request"]:
                logger.info(
                    f"Queueing tool request for tweet {tweet_data.tweet_id} - "
                    f"Type: {analysis_result['tool_request'].type}"
                )
                backend.create_queue_message(
                    new_queue_message=QueueMessageCreate(
                        type="daos",
                        tweet_id=tweet_data.tweet_id,
                        conversation_id=tweet_data.conversation_id,
                        message=analysis_result["tool_request"].model_dump(),
                    )
                )
            elif analysis_result["is_worthy"]:
                logger.debug(
                    f"Tweet {tweet_data.tweet_id} worthy but no tool request present"
                )
            else:
                logger.debug(f"Tweet {tweet_data.tweet_id} not worthy of processing")

        except Exception as e:
            logger.error(
                f"Analysis failed for tweet {tweet_data.tweet_id}: {str(e)}",
                exc_info=True,
            )
            raise

    async def _get_conversation_history(self, tweet_data: TweetData) -> List[Dict]:
        """Retrieve and format conversation history."""
        if not tweet_data.conversation_id:
            logger.debug("No conversation ID present, returning empty history")
            return []

        try:
            # Get all tweets in the conversation
            conversation_tweets = backend.list_x_tweets(
                filters=XTweetFilter(conversation_id=tweet_data.conversation_id)
            )
            logger.debug(
                f"Retrieved {len(conversation_tweets)} tweets from conversation {tweet_data.conversation_id}"
            )
            return [
                {
                    "role": "user" if tweet.author_id != self.user_id else "assistant",
                    "content": tweet.message,
                }
                for tweet in conversation_tweets
                if tweet.message
            ]
        except Exception as e:
            logger.error(
                f"Failed to retrieve conversation history: {str(e)}", exc_info=True
            )
            raise

    async def _post_response(
        self, tweet_data: TweetData, response_content: str
    ) -> None:
        """Post the response to Twitter and store in database."""
        logger.info(f"Posting response to tweet {tweet_data.tweet_id}")
        logger.debug(f"Response content: {response_content[:100]}...")

        try:
            self.twitter_service.initialize()
            response_tweet = await self.twitter_service._apost_tweet(
                text=response_content, reply_in_reply_to_tweet_id=tweet_data.tweet_id
            )

            if response_tweet and response_tweet.id:
                logger.info(f"Successfully posted response tweet {response_tweet.id}")
                # Store the response tweet
                backend.create_x_tweet(
                    XTweetCreate(
                        tweet_id=response_tweet.id,
                        message=response_content,
                        conversation_id=tweet_data.conversation_id,
                    )
                )
                logger.debug(f"Stored response tweet {response_tweet.id} in database")
            else:
                logger.warning("Failed to get response tweet ID from Twitter API")

        except Exception as e:
            logger.error(
                f"Failed to post response to tweet {tweet_data.tweet_id}: {str(e)}",
                exc_info=True,
            )
            raise

    async def process_mentions(self) -> None:
        """Process all new mentions for analysis."""
        try:
            logger.info("Starting Twitter mention processing")
            await self.twitter_service._ainitialize()
            mentions = await self.twitter_service.get_mentions_by_user_id(self.user_id)

            if not mentions:
                logger.info("No new mentions found to process")
                return

            logger.info(f"Found {len(mentions)} mentions to process")
            for mention in mentions:
                try:
                    logger.debug(f"Processing mention {mention.id}")
                    await self._handle_mention(mention)
                except Exception as e:
                    logger.error(
                        f"Failed to process mention {mention.id}: {str(e)}",
                        exc_info=True,
                    )
                    continue

        except Exception as e:
            logger.error("Twitter mention processing failed: {str(e)}", exc_info=True)
            raise


# Global handler instance
load_dotenv()
handler = TwitterMentionHandler()


async def execute_twitter_job() -> None:
    """Execute the Twitter job to process mentions."""
    try:
        if not handler.user_id:
            logger.error(
                "Cannot execute Twitter job: AIBTC_TWITTER_AUTOMATED_USER_ID not set"
            )
            return

        logger.info("Starting Twitter mention check job")
        await handler.process_mentions()
        logger.info("Successfully completed Twitter mention check job")

    except Exception as e:
        logger.error(f"Twitter job execution failed: {str(e)}", exc_info=True)
        raise
