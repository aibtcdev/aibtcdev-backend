"""Enhanced Tweet Task using the new job queue system."""

from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID


from app.backend.factory import backend
from app.backend.models import (
    JobCooldownCreate,
    QueueMessage,
    QueueMessageBase,
    QueueMessageFilter,
    QueueMessageType,
    XCredsFilter,
)
from app.config import config
from app.lib.logger import configure_logger
from app.lib.utils import extract_image_urls, split_text_into_chunks
from app.services.communication.twitter_service import TwitterService
from app.services.infrastructure.job_management.base import (
    BaseTask,
    JobContext,
    RunnerConfig,
    RunnerResult,
)
from app.services.infrastructure.job_management.decorators import JobPriority, job
import re
import random
import tweepy
from datetime import datetime, timedelta, timezone

logger = configure_logger(__name__)


@dataclass
class TweetProcessingResult(RunnerResult):
    """Result of tweet processing operation."""

    tweet_id: Optional[str] = None
    dao_id: Optional[UUID] = None
    tweets_sent: int = 0
    chunks_processed: int = 0


@job(
    job_type="tweet",
    name="Tweet Processor",
    description="Processes and sends tweets for DAOs with automatic retry and error handling",
    interval_seconds=30,  # Reduced frequency from 5s to 30s
    priority=JobPriority.NORMAL,  # Changed from HIGH to NORMAL to not dominate queue
    max_retries=3,
    retry_delay_seconds=60,
    timeout_seconds=300,
    max_concurrent=2,  # Increased from 1 to 2 to allow parallel processing
    requires_twitter=True,
    batch_size=5,
    enable_dead_letter_queue=True,
)
class TweetTask(BaseTask[TweetProcessingResult]):
    """Enhanced task for sending tweets with improved error handling and monitoring."""

    def __init__(self, config: Optional[RunnerConfig] = None):
        super().__init__(config)
        self._pending_messages: Optional[List[QueueMessage]] = None
        self._twitter_services: dict[UUID, TwitterService] = {}

    async def _get_twitter_service(self, dao_id: UUID) -> Optional[TwitterService]:
        """Get or create Twitter service for a DAO with caching."""
        if dao_id in self._twitter_services:
            return self._twitter_services[dao_id]

        try:
            # Get Twitter credentials for the DAO
            creds = backend.list_x_creds(filters=XCredsFilter(dao_id=dao_id))
            if not creds:
                logger.error(f"No Twitter credentials found for DAO {dao_id}")
                return None

            # Initialize Twitter service with the credentials
            twitter_service = TwitterService(
                consumer_key=creds[0].consumer_key,
                consumer_secret=creds[0].consumer_secret,
                client_id=creds[0].client_id,
                client_secret=creds[0].client_secret,
                access_token=creds[0].access_token,
                access_secret=creds[0].access_secret,
                bearer_token=creds[0].bearer_token,
            )
            await twitter_service._ainitialize()

            # Cache the service
            self._twitter_services[dao_id] = twitter_service
            logger.debug(f"Initialized and cached Twitter service for DAO {dao_id}")
            return twitter_service

        except Exception as e:
            logger.error(
                f"Error initializing Twitter service for DAO {dao_id}: {str(e)}",
                exc_info=True,
            )
            return None

    async def _initialize_twitter_service(self, dao_id: UUID) -> bool:
        """Initialize Twitter service with credentials from app.config."""
        try:
            # Check if Twitter is enabled in config
            if not config.twitter.enabled:
                logger.error("Twitter service is disabled in configuration")
                return False

            # Validate that required Twitter credentials are configured
            if not all(
                [
                    config.twitter.consumer_key,
                    config.twitter.consumer_secret,
                    config.twitter.client_id,
                    config.twitter.client_secret,
                    config.twitter.access_token,
                    config.twitter.access_secret,
                ]
            ):
                logger.error("Missing required Twitter credentials in configuration")
                return False

            # Initialize Twitter service with credentials from app.config
            self.twitter_service = TwitterService(
                consumer_key=config.twitter.consumer_key,
                consumer_secret=config.twitter.consumer_secret,
                client_id=config.twitter.client_id,
                client_secret=config.twitter.client_secret,
                access_token=config.twitter.access_token,
                access_secret=config.twitter.access_secret,
            )
            await self.twitter_service._ainitialize()
            logger.debug(f"Initialized Twitter service for DAO {dao_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Twitter service: {str(e)}")
            return False

    async def _validate_config(self, context: JobContext) -> bool:
        """Validate task configuration."""
        # Enhanced validation with timeout check
        if context.timeout_seconds and context.timeout_seconds < 60:
            logger.warning("Tweet task timeout should be at least 60 seconds")
            return False
        return True

    async def _validate_resources(self, context: JobContext) -> bool:
        """Validate resource availability."""
        try:
            # Validate Twitter configuration
            if not config.twitter.enabled:
                logger.debug("Twitter service is disabled")
                return False

            if not all(
                [
                    config.twitter.consumer_key,
                    config.twitter.consumer_secret,
                    config.twitter.client_id,
                    config.twitter.client_secret,
                    config.twitter.access_token,
                    config.twitter.access_secret,
                ]
            ):
                logger.error("Missing required Twitter credentials in configuration")
                return False

            return True
        except Exception as e:
            logger.error(f"Backend not available: {str(e)}")
            return False

    async def _validate_prerequisites(self, context: JobContext) -> bool:
        """Validate task prerequisites."""
        try:
            # Cache pending messages for later use
            self._pending_messages = backend.list_queue_messages(
                filters=QueueMessageFilter(
                    type=QueueMessageType.get_or_create("tweet"), is_processed=False
                )
            )
            logger.debug(
                f"Found {len(self._pending_messages)} unprocessed tweet messages"
            )

            # Log some details about the messages for debugging
            if self._pending_messages:
                for idx, msg in enumerate(self._pending_messages[:3]):  # Log first 3
                    logger.debug(
                        f"Tweet message {idx + 1}: ID={msg.id}, DAO={msg.dao_id}, "
                        f"Message type={type(msg.message)}, Content preview: {str(msg.message)[:100]}"
                    )

            return True
        except Exception as e:
            logger.error(f"Error loading pending tweets: {str(e)}", exc_info=True)
            self._pending_messages = None
            return False

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate task-specific conditions."""
        if not self._pending_messages:
            logger.debug("No pending tweet messages found - skipping execution")
            return False

        # Validate each message before processing
        valid_messages = []
        invalid_count = 0

        for message in self._pending_messages:
            if await self._is_message_valid(message):
                valid_messages.append(message)
            else:
                invalid_count += 1

        self._pending_messages = valid_messages

        logger.info(
            f"Tweet validation complete: {len(valid_messages)} valid, {invalid_count} invalid messages"
        )

        if valid_messages:
            logger.debug(f"Found {len(valid_messages)} valid tweet messages")
            return True

        logger.warning(
            f"No valid tweet messages to process (found {invalid_count} invalid messages)"
        )
        return False

    async def _is_message_valid(self, message: QueueMessage) -> bool:
        """Check if a message is valid for processing with new 'posts' format."""
        try:
            if not message.message:
                logger.debug(
                    f"Tweet message {message.id} invalid: message field is empty"
                )
                return False

            if not message.dao_id:
                logger.debug(f"Tweet message {message.id} invalid: dao_id is missing")
                return False

            if not isinstance(message.message, dict):
                logger.debug(
                    f"Tweet message {message.id} invalid: message field is not a dict, got {type(message.message)}"
                )
                return False

            # Check for posts field in new format
            if "posts" not in message.message:
                logger.debug(
                    f"Tweet message {message.id} invalid: 'posts' key not found. Keys: {list(message.message.keys())}"
                )
                return False

            posts = message.message["posts"]
            if not posts:
                logger.debug(
                    f"Tweet message {message.id} invalid: posts array is None or empty"
                )
                return False

            if not isinstance(posts, list):
                logger.debug(
                    f"Tweet message {message.id} invalid: posts is not a list, got {type(posts)}"
                )
                return False

            # Validate each post
            for i, post in enumerate(posts):
                if not isinstance(post, str):
                    logger.debug(
                        f"Tweet message {message.id} invalid: post {i} is not a string, got {type(post)}"
                    )
                    return False
                if not post.strip():
                    logger.debug(
                        f"Tweet message {message.id} invalid: post {i} is empty or whitespace"
                    )
                    return False

            logger.debug(f"Tweet message {message.id} is valid with {len(posts)} posts")
            return True

        except Exception as e:
            logger.debug(f"Tweet message {message.id} validation error: {str(e)}")
            return False

    async def _process_tweet_message(
        self, message: QueueMessage
    ) -> TweetProcessingResult:
        """Process a single tweet message with the new 'posts' format.

        Expected format:
        {
            "posts": ["post1", "post2", "post3", ...]
        }

        Each post will be validated to ensure it's ≤280 characters, splitting longer posts
        without breaking words. Posts are sent as a threaded sequence.
        """
        try:
            # Validate message structure first
            if not message.message or not isinstance(message.message, dict):
                logger.warning(
                    f"Tweet message {message.id} has invalid message structure"
                )
                return TweetProcessingResult(
                    success=False,
                    message="Tweet message structure is invalid",
                    dao_id=message.dao_id,
                )

            # Get Twitter service for this DAO
            twitter_service = await self._get_twitter_service(message.dao_id)
            if not twitter_service:
                return TweetProcessingResult(
                    success=False,
                    message=f"Failed to get Twitter service for DAO: {message.dao_id}",
                    dao_id=message.dao_id,
                )

            # Get posts array from new format
            if "posts" not in message.message:
                logger.warning(f"Tweet message {message.id} missing 'posts' field")
                return TweetProcessingResult(
                    success=False,
                    message="Tweet message missing 'posts' field",
                    dao_id=message.dao_id,
                )

            posts = message.message["posts"]
            if not isinstance(posts, list) or not posts:
                logger.warning(f"Tweet message {message.id} has invalid posts array")
                return TweetProcessingResult(
                    success=False,
                    message="Tweet message has invalid posts array",
                    dao_id=message.dao_id,
                )

            logger.info(
                f"Processing tweet message for DAO {message.dao_id} with {len(posts)} posts"
            )

            # Validate and split posts to ensure ≤280 characters
            processed_posts = []
            for i, post in enumerate(posts):
                if len(post) <= 280:
                    processed_posts.append(post)
                    logger.debug(
                        f"Post {i + 1} is within 280 character limit ({len(post)} chars)"
                    )
                else:
                    # Split post into chunks without breaking words
                    chunks = split_text_into_chunks(post, limit=280)
                    processed_posts.extend(chunks)
                    logger.info(
                        f"Post {i + 1} exceeded 280 chars ({len(post)} chars), split into {len(chunks)} chunks"
                    )

            logger.info(
                f"After validation/splitting: {len(processed_posts)} posts ready to send"
            )

            return await self._process_posts(message, twitter_service, processed_posts)

        except Exception as e:
            logger.error(
                f"Error processing tweet message {message.id}: {str(e)}", exc_info=True
            )
            return TweetProcessingResult(
                success=False,
                message=f"Error sending tweet: {str(e)}",
                error=e,
                tweet_id=getattr(message, "tweet_id", None),
                dao_id=message.dao_id,
            )

    async def _process_posts(
        self, message: QueueMessage, twitter_service: TwitterService, posts: List[str]
    ) -> TweetProcessingResult:
        """Process posts in the new format with automatic threading."""
        previous_tweet_id = (
            None  # Start with no previous tweet - first post creates new thread
        )
        tweets_sent = 0

        logger.info(f"Processing {len(posts)} posts for DAO {message.dao_id}")

        # Debug: Log all post content to identify duplicates
        for i, post in enumerate(posts):
            logger.debug(f"Post {i + 1} content: '{post}'")

        for index, post in enumerate(posts):
            try:
                # Check for image URLs in the post
                image_urls = extract_image_urls(post)
                image_url = image_urls[0] if image_urls else None

                if image_url:
                    # Remove image URL from text
                    post = re.sub(re.escape(image_url), "", post).strip()
                    post = re.sub(r"\s+", " ", post)

                # Post the tweet
                if index == 0:
                    # First post - create new thread (no reply_id)
                    if image_url:
                        tweet_response = await twitter_service.post_tweet_with_media(
                            image_url=image_url,
                            text=post,
                            reply_id=None,  # No reply for first post
                        )
                    else:
                        tweet_response = await twitter_service._apost_tweet(
                            text=post,
                            reply_in_reply_to_tweet_id=None,  # No reply for first post
                        )
                else:
                    # Subsequent posts - reply to previous tweet to continue thread
                    if image_url:
                        tweet_response = await twitter_service.post_tweet_with_media(
                            image_url=image_url,
                            text=post,
                            reply_id=previous_tweet_id,
                        )
                    else:
                        tweet_response = await twitter_service._apost_tweet(
                            text=post,
                            reply_in_reply_to_tweet_id=previous_tweet_id,
                        )
                logger.debug(f"Tweet response: {tweet_response}")

                if tweet_response and tweet_response.data:
                    tweets_sent += 1
                    previous_tweet_id = tweet_response.data["id"]
                    if index == 0:
                        logger.info(
                            f"Successfully created new thread with tweet {tweet_response.data['id']}"
                            f"{f' - {post[:50]}...' if len(post) > 50 else f' - {post}'}"
                        )
                    else:
                        logger.info(
                            f"Successfully posted thread reply {index + 1}/{len(posts)}: {tweet_response.data['id']}"
                            f"{f' - {post[:50]}...' if len(post) > 50 else f' - {post}'}"
                        )
                else:
                    logger.error(f"Failed to send tweet {index + 1}/{len(posts)}")
                    if index == 0:  # If first post fails, whole message fails
                        return TweetProcessingResult(
                            success=False,
                            message="Failed to send first tweet post",
                            dao_id=message.dao_id,
                            tweet_id=None,
                            chunks_processed=index,
                        )
                    # For subsequent posts, we can continue

            except tweepy.TooManyRequests as e:
                retry_after = int(e.response.headers.get("Retry-After", 900))  # Default 15min
                jitter = random.uniform(1.0, 1.5)
                wait_until = datetime.now(timezone.utc) + timedelta(seconds=retry_after * jitter)
                backend.upsert_job_cooldown(
                    job_type="tweet",
                    wait_until=wait_until,
                    reason=f"twitter-429 (Retry-After: {retry_after}s)"
                )
                logger.warning(f"Tweet job cooldown set until {wait_until}")
                return TweetProcessingResult(
                    success=False,
                    message=f"Rate limited until {wait_until}",
                    dao_id=message.dao_id,
                )
            except Exception as post_error:
                # Check if it's a Twitter duplicate content error
                error_message = str(post_error)
                if "duplicate content" in error_message.lower():
                    logger.error(
                        f"Twitter duplicate content error for post {index + 1}/{len(posts)}: '{post}'"
                    )
                    logger.error(f"Full error: {error_message}")
                else:
                    logger.error(
                        f"Error sending post {index + 1}/{len(posts)}: {error_message}"
                    )

                if index == 0:  # Critical failure on first post
                    raise post_error

        return TweetProcessingResult(
            success=tweets_sent > 0,
            message=f"Successfully sent {tweets_sent}/{len(posts)} tweet posts as thread",
            tweet_id=previous_tweet_id,
            dao_id=message.dao_id,
            tweets_sent=tweets_sent,
            chunks_processed=len(posts),
        )

    def _should_retry_on_error(self, error: Exception, context: JobContext) -> bool:
        """Determine if error should trigger retry."""
        # Import tweepy exceptions for retry logic
        try:
            import tweepy

            retry_errors = (
                ConnectionError,
                TimeoutError,
                tweepy.TooManyRequests,
                tweepy.ServiceUnavailable,
            )
            return isinstance(error, retry_errors)
        except ImportError:
            # Fallback if tweepy not available
            retry_errors = (ConnectionError, TimeoutError)
            return isinstance(error, retry_errors)

    async def _handle_execution_error(
        self, error: Exception, context: JobContext
    ) -> Optional[List[TweetProcessingResult]]:
        """Handle execution errors with recovery logic."""
        try:
            import tweepy

            if isinstance(error, tweepy.TooManyRequests):
                logger.warning("Twitter API rate limit reached, will retry later")
                return None  # Let default retry handling take over

            if isinstance(error, tweepy.ServiceUnavailable):
                logger.warning("Twitter service unavailable, will retry later")
                return None
        except ImportError:
            pass

        if isinstance(error, (ConnectionError, TimeoutError)):
            logger.warning(f"Network error: {str(error)}, will retry")
            return None

        # For other errors, don't retry
        return [
            TweetProcessingResult(
                success=False,
                message=f"Unrecoverable error: {str(error)}",
                error=error,
            )
        ]

    async def _post_execution_cleanup(
        self, context: JobContext, results: List[TweetProcessingResult]
    ) -> None:
        """Cleanup after task execution."""
        # Clear cached pending messages
        self._pending_messages = None

        # Don't clear Twitter services cache as they can be reused
        logger.debug(
            f"Cleanup completed. Cached Twitter services: {len(self._twitter_services)}"
        )

    async def _execute_impl(self, context: JobContext) -> List[TweetProcessingResult]:
        """Execute tweet sending task with batch processing."""
        results: List[TweetProcessingResult] = []

        if not self._pending_messages:
            logger.debug("No pending tweet messages to process")
            return results

        processed_count = 0
        success_count = 0
        batch_size = getattr(context, "batch_size", 5)

        # Process messages in batches
        for i in range(0, len(self._pending_messages), batch_size):
            batch = self._pending_messages[i : i + batch_size]

            for message in batch:
                logger.debug(f"Processing tweet message: {message.id}")
                result = await self._process_tweet_message(message)
                results.append(result)
                processed_count += 1

                if result.success:
                    success_count += 1
                    # Mark message as processed with result
                    result_dict = {
                        "success": result.success,
                        "message": result.message,
                        "tweet_id": result.tweet_id,
                        "dao_id": str(result.dao_id) if result.dao_id else None,
                        "tweets_sent": result.tweets_sent,
                        "chunks_processed": result.chunks_processed,
                        "error": str(result.error) if result.error else None,
                    }
                    backend.update_queue_message(
                        queue_message_id=message.id,
                        update_data=QueueMessageBase(
                            is_processed=True, result=result_dict
                        ),
                    )
                    logger.debug(
                        f"Marked message {message.id} as processed with result"
                    )
                else:
                    # Store result for failed processing
                    result_dict = {
                        "success": result.success,
                        "message": result.message,
                        "tweet_id": result.tweet_id,
                        "dao_id": str(result.dao_id) if result.dao_id else None,
                        "tweets_sent": result.tweets_sent,
                        "chunks_processed": result.chunks_processed,
                        "error": str(result.error) if result.error else None,
                    }
                    backend.update_queue_message(
                        queue_message_id=message.id,
                        update_data=QueueMessageBase(result=result_dict),
                    )
                    logger.debug(f"Stored result for failed message {message.id}")

        logger.info(
            f"Tweet task completed - Processed: {processed_count}, "
            f"Successful: {success_count}, Failed: {processed_count - success_count}"
        )

        return results


# Create instance for auto-registration
tweet_task = TweetTask()
