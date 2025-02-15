from backend.factory import backend
from backend.models import (
    QueueMessageCreate,
    XTweetBase,
    XTweetCreate,
    XTweetFilter,
    XUserCreate,
    XUserFilter,
)
from config import config
from lib.logger import configure_logger
from lib.twitter import TwitterService
from pydantic import BaseModel
from services.workflows import analyze_tweet
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


class TwitterConfig(BaseModel):
    """Configuration for Twitter service."""

    consumer_key: str
    consumer_secret: str
    client_id: str
    client_secret: str
    access_token: str
    access_secret: str
    user_id: str
    whitelisted_authors: List[str]
    whitelist_enabled: bool = False


class TweetRepository:
    """Repository for handling tweet storage and retrieval."""

    async def store_tweet(self, tweet_data: TweetData) -> None:
        """Store tweet and author data in the database."""
        try:
            authors = backend.list_x_users(
                filters=XUserFilter(user_id=tweet_data.author_id)
            )
            if authors and len(authors) > 0:
                author = authors[0]
                logger.debug(
                    f"Found existing author {tweet_data.author_id} in database"
                )
            else:
                logger.info(f"Creating new author record for {tweet_data.author_id}")
                author = backend.create_x_user(
                    XUserCreate(user_id=tweet_data.author_id)
                )

            logger.debug(f"Creating tweet record for {tweet_data.tweet_id}")
            backend.create_x_tweet(
                XTweetCreate(
                    author_id=author.id,
                    tweet_id=tweet_data.tweet_id,
                    message=tweet_data.text,
                    conversation_id=tweet_data.conversation_id,
                )
            )
        except Exception as e:
            logger.error(f"Failed to store tweet/author data: {str(e)}", exc_info=True)
            raise

    async def update_tweet_analysis(
        self,
        tweet_id: str,
        is_worthy: bool,
        tweet_type: str,
        confidence_score: float,
        reason: str,
    ) -> None:
        """Update tweet with analysis results."""
        try:
            tweets = backend.list_x_tweets(filters=XTweetFilter(tweet_id=tweet_id))
            if tweets and len(tweets) > 0:
                logger.debug(f"Updating existing tweet record with analysis results")
                backend.update_x_tweet(
                    x_tweet_id=tweets[0].id,
                    update_data=XTweetBase(
                        is_worthy=is_worthy,
                        tweet_type=tweet_type,
                        confidence_score=confidence_score,
                        reason=reason,
                    ),
                )
        except Exception as e:
            logger.error(f"Failed to update tweet analysis: {str(e)}", exc_info=True)
            raise

    async def get_conversation_history(
        self, conversation_id: str, user_id: str
    ) -> List[Dict[str, str]]:
        """Retrieve conversation history for a given conversation ID."""
        try:
            conversation_tweets = backend.list_x_tweets(
                filters=XTweetFilter(conversation_id=conversation_id)
            )
            logger.debug(
                f"Retrieved {len(conversation_tweets)} tweets from conversation {conversation_id}"
            )
            return [
                {
                    "role": "user" if tweet.author_id != user_id else "assistant",
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


class TweetAnalyzer:
    """Handles tweet analysis and processing logic."""

    def __init__(self, tweet_repository: TweetRepository):
        """Initialize with dependencies."""
        self.tweet_repository = tweet_repository

    async def analyze_tweet_content(
        self, tweet_data: TweetData, history: List[Dict[str, str]]
    ) -> Dict:
        """Analyze tweet content and determine if it needs processing."""
        logger.info(
            f"Analyzing tweet {tweet_data.tweet_id} from user {tweet_data.author_id}"
        )
        logger.debug(f"Tweet content: {tweet_data.text}")
        logger.debug(f"Conversation history size: {len(history)} messages")

        filtered_content = "\n".join(
            f"{msg['role']}: {msg['content']}" for msg in history
        )

        try:
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

            await self.tweet_repository.update_tweet_analysis(
                tweet_id=tweet_data.tweet_id,
                is_worthy=analysis_result["is_worthy"],
                tweet_type=analysis_result["tweet_type"],
                confidence_score=analysis_result["confidence_score"],
                reason=analysis_result["reason"],
            )

            return analysis_result
        except Exception as e:
            logger.error(
                f"Analysis failed for tweet {tweet_data.tweet_id}: {str(e)}",
                exc_info=True,
            )
            raise


class TwitterMentionHandler:
    """Handles Twitter mention processing and responses."""

    def __init__(
        self,
        config: TwitterConfig,
        tweet_repository: TweetRepository,
        tweet_analyzer: TweetAnalyzer,
    ):
        """Initialize with dependencies."""
        self.config = config
        self.tweet_repository = tweet_repository
        self.tweet_analyzer = tweet_analyzer
        self.twitter_service = TwitterService(
            consumer_key=config.consumer_key,
            consumer_secret=config.consumer_secret,
            client_id=config.client_id,
            client_secret=config.client_secret,
            access_token=config.access_token,
            access_secret=config.access_secret,
        )

    async def _post_response(
        self, tweet_data: TweetData, response_content: str
    ) -> None:
        """Post a response tweet.

        Args:
            tweet_data: Data about the tweet to respond to
            response_content: Content of the response tweet
        """
        logger.debug(f"Posting response to tweet {tweet_data.tweet_id}")
        await self.twitter_service._ainitialize()
        await self.twitter_service._apost_tweet(
            text=response_content, reply_in_reply_to_tweet_id=tweet_data.tweet_id
        )

    def _is_author_whitelisted(self, author_id: str) -> bool:
        """Check if the author is in the whitelist."""
        logger.debug(f"Checking whitelist status for author {author_id}")
        is_whitelisted = str(author_id) in self.config.whitelisted_authors
        logger.debug(f"Author {author_id} whitelist status: {is_whitelisted}")
        return is_whitelisted

    async def _handle_mention(self, mention) -> None:
        """Process a single mention for analysis."""
        tweet_data = TweetData(
            tweet_id=mention.id,
            author_id=mention.author_id,
            text=mention.text,
            conversation_id=mention.conversation_id,
        )

        logger.debug(
            f"Processing mention - Tweet ID: {tweet_data.tweet_id}, "
            f"Author: {tweet_data.author_id}, Text: {tweet_data.text[:50]}..."
        )

        # Check if tweet exists in our database
        try:
            existing_tweets = backend.list_x_tweets(
                filters=XTweetFilter(tweet_id=tweet_data.tweet_id)
            )
            if existing_tweets and len(existing_tweets) > 0:
                logger.debug(
                    f"Tweet {tweet_data.tweet_id} already exists in database, skipping processing"
                )
                return
        except Exception as e:
            logger.error(
                f"Database error checking tweet {tweet_data.tweet_id}: {str(e)}",
                exc_info=True,
            )
            raise

        await self.tweet_repository.store_tweet(tweet_data)

        try:
            if self.config.whitelist_enabled:
                if self._is_author_whitelisted(tweet_data.author_id):
                    logger.info(
                        f"Processing whitelisted mention {tweet_data.tweet_id} "
                        f"from user {tweet_data.author_id}"
                    )
                    await self._process_mention(tweet_data)
                else:
                    logger.warning(
                        f"Skipping non-whitelisted mention {tweet_data.tweet_id} "
                        f"from user {tweet_data.author_id}"
                    )
            else:
                logger.debug("Whitelist check disabled, processing all mentions")
                await self._process_mention(tweet_data)
        except Exception as e:
            logger.error(
                f"Failed to process mention {tweet_data.tweet_id}: {str(e)}",
                exc_info=True,
            )
            raise

    async def _process_mention(self, tweet_data: TweetData) -> None:
        """Process mention after validation."""
        history = await self.tweet_repository.get_conversation_history(
            tweet_data.conversation_id, self.config.user_id
        )

        analysis_result = await self.tweet_analyzer.analyze_tweet_content(
            tweet_data, history
        )

        if analysis_result["is_worthy"] and analysis_result["tool_request"]:
            logger.info(
                f"Queueing tool request for tweet {tweet_data.tweet_id} - "
                f"Tool: {analysis_result['tool_request'].tool_name}"
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

    async def process_mentions(self) -> None:
        """Process all new mentions for analysis."""
        try:
            logger.info("Starting Twitter mention processing")
            await self.twitter_service._ainitialize()
            mentions = await self.twitter_service.get_mentions_by_user_id(
                self.config.user_id
            )

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


def create_twitter_handler() -> TwitterMentionHandler:
    """Factory function to create TwitterMentionHandler with dependencies."""
    twitter_config = TwitterConfig(
        consumer_key=config.twitter.consumer_key,
        consumer_secret=config.twitter.consumer_secret,
        client_id=config.twitter.client_id,
        client_secret=config.twitter.client_secret,
        access_token=config.twitter.access_token,
        access_secret=config.twitter.access_secret,
        user_id=config.twitter.automated_user_id,
        whitelisted_authors=config.twitter.whitelisted_authors,
        whitelist_enabled=False,
    )

    tweet_repository = TweetRepository()
    tweet_analyzer = TweetAnalyzer(tweet_repository)

    return TwitterMentionHandler(twitter_config, tweet_repository, tweet_analyzer)


# Global handler instance
handler = create_twitter_handler()


async def execute_twitter_job() -> None:
    """Execute the Twitter job to process mentions."""
    try:
        if not handler.config.user_id:
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
