"""Enhanced Tweet Task using the new job queue system."""

from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import UUID

import random
import re
import tweepy

from app.backend.factory import backend
from app.backend.models import (
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
from collections import defaultdict

from app.services.infrastructure.job_management.decorators import JobPriority, job

logger = configure_logger(__name__)


@dataclass
class TweetProcessingResult(RunnerResult):
    """Result of tweet processing operation."""

    tweet_id: Optional[str] = None
    first_tweet_id: Optional[str] = None
    dao_id: Optional[UUID] = None
    tweets_sent: int = 0
    total_posts: int = 0
    partial_success: bool = False
    chunks_processed: int = 0


@job(
    job_type="tweet",
    name="Tweet Processor",
    description="Processes and sends tweets for DAOs with automatic retry and error handling",
    interval_seconds=120,
    priority=JobPriority.NORMAL,  # Changed from HIGH to NORMAL to not dominate queue
    max_retries=3,
    retry_delay_seconds=60,
    timeout_seconds=300,
    max_concurrent=1,
    requires_twitter=True,
    batch_size=3,
    enable_dead_letter_queue=True,
)
class TweetTask(BaseTask[TweetProcessingResult]):
    """Enhanced task for sending tweets with improved error handling and monitoring."""

    def __init__(self, config: Optional[RunnerConfig] = None):
        super().__init__(config)
        self._pending_messages: Optional[List[QueueMessage]] = None
        self._twitter_services: dict[UUID, TwitterService] = {}
        self._rate_limited_this_run = False

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
            # Check job cooldown first
            cooldown = backend.get_job_cooldown("tweet")
            now = datetime.now(timezone.utc)
            if cooldown and cooldown.wait_until and now < cooldown.wait_until:
                logger.info(
                    f"Tweet task skipped: cooldown active until {cooldown.wait_until} "
                    f"(reason: {cooldown.reason})"
                )
                self._pending_messages = []
                return False

            # Cache pending messages for later use
            self._pending_messages = backend.list_queue_messages(
                filters=QueueMessageFilter(
                    type=QueueMessageType.get_or_create("tweet"), is_processed=False
                )
            )
            logger.debug(
                f"Found {len(self._pending_messages)} unprocessed tweet messages"
            )

            # Prioritize: 1 oldest/incomplete per DAO, max 3 total/run
            dao_to_msgs: defaultdict[UUID, List[QueueMessage]] = defaultdict(list)
            for msg in self._pending_messages:
                dao_to_msgs[msg.dao_id].append(msg)

            self._pending_messages = []
            for dao_id, msgs in dao_to_msgs.items():
                # Sort by tweets_sent asc (incomplete first)
                incomplete = sorted(
                    msgs,
                    key=lambda m: m.result.get("tweets_sent", 0) if m.result else 0,
                )
                self._pending_messages.append(incomplete[0])
                if len(self._pending_messages) >= 3:
                    break

            logger.info(
                f"Limited to {len(self._pending_messages)} msgs across {len(dao_to_msgs)} DAOs"
            )

            # Log some details about the messages for debugging
            if self._pending_messages:
                for idx, msg in enumerate(self._pending_messages[:3]):  # Log first 3
                    logger.debug(
                        f"Tweet message {idx + 1}: ID={msg.id}, DAO={msg.dao_id}, "
                        f"Message type={type(msg.message)}, Content preview: {str(msg.message)[:100]}"
                    )

            return len(self._pending_messages) > 0
        except Exception as e:
            logger.error(f"Error loading pending tweets: {str(e)}", exc_info=True)
            self._pending_messages = None
            return False

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate task-specific conditions."""
        return True

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

            # Check if already complete from prior result
            if message.result and isinstance(message.result, dict):
                prior_sent = message.result.get("tweets_sent", 0)
                posts_len = len(posts)
                if prior_sent >= posts_len:
                    logger.debug(
                        f"Tweet message {message.id} already complete ({prior_sent}/{posts_len})"
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

        Each post will be validated to ensure ≤280 characters, splitting longer posts
        without breaking words. Posts are sent as a threaded sequence.
        Supports resumption from partial failures using stored result.
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
                    first_tweet_id=None,
                    total_posts=0,
                    partial_success=False,
                    dao_id=message.dao_id,
                )

            # Get Twitter service for this DAO
            twitter_service = await self._get_twitter_service(message.dao_id)
            if not twitter_service:
                return TweetProcessingResult(
                    success=False,
                    message=f"Failed to get Twitter service for DAO: {message.dao_id}",
                    first_tweet_id=None,
                    total_posts=0,
                    partial_success=False,
                    dao_id=message.dao_id,
                )

            # Get posts array from new format
            if "posts" not in message.message:
                logger.warning(f"Tweet message {message.id} missing 'posts' field")
                return TweetProcessingResult(
                    success=False,
                    message="Tweet message missing 'posts' field",
                    first_tweet_id=None,
                    total_posts=0,
                    partial_success=False,
                    dao_id=message.dao_id,
                )

            posts = message.message["posts"]
            total_posts = len(posts)
            if not isinstance(posts, list) or not posts:
                logger.warning(f"Tweet message {message.id} has invalid posts array")
                return TweetProcessingResult(
                    success=False,
                    message="Tweet message has invalid posts array",
                    first_tweet_id=None,
                    total_posts=total_posts,
                    partial_success=False,
                    dao_id=message.dao_id,
                )

            # Parse prior result for resumption
            prior_sent = 0
            resume_info: Optional[Dict[str, Optional[str]]] = None
            if message.result and isinstance(message.result, dict):
                prior_sent = message.result.get("tweets_sent", 0)
                if prior_sent > 0:
                    resume_info = {
                        "first_tweet_id": message.result.get("first_tweet_id"),
                        "previous_tweet_id": message.result.get("tweet_id"),
                    }
                    logger.info(
                        f"Resuming message {message.id}: {prior_sent}/{total_posts} already sent"
                    )

            if resume_info:
                start_index = prior_sent
                remaining_posts = posts[start_index:]
                total_remaining = len(remaining_posts)
                logger.info(
                    f"Resuming with {total_remaining} remaining posts, replying to {resume_info['previous_tweet_id']}"
                )
            else:
                remaining_posts = posts
                total_remaining = total_posts
                logger.info(
                    f"Starting new message {message.id} for DAO {message.dao_id} with {total_remaining} posts"
                )

            # Validate and split remaining posts to ensure ≤280 characters
            processed_remaining_posts = []
            for i, post in enumerate(remaining_posts):
                orig_index = prior_sent + i + 1 if resume_info else i + 1
                if len(post) <= 280:
                    processed_remaining_posts.append(post)
                    logger.debug(
                        f"Post {orig_index} is within 280 character limit ({len(post)} chars)"
                    )
                else:
                    # Split post into chunks without breaking words
                    chunks = split_text_into_chunks(post, limit=280)
                    processed_remaining_posts.extend(chunks)
                    logger.info(
                        f"Post {orig_index} exceeded 280 chars ({len(post)} chars), split into {len(chunks)} chunks"
                    )

            logger.info(
                f"After validation/splitting: {len(processed_remaining_posts)} remaining posts ready to send"
            )

            sub_result = await self._process_posts(
                message,
                twitter_service,
                processed_remaining_posts,
                resume_info or {},
                total_remaining,
            )

            total_sent = prior_sent + sub_result["tweets_sent_this_run"]
            first_tweet_id = sub_result["first_tweet_id"]
            tweet_id = sub_result["final_tweet_id"]
            success = total_sent == total_posts
            partial_success = total_sent > prior_sent and not success

            return TweetProcessingResult(
                success=success,
                partial_success=partial_success,
                message=f"Sent {sub_result['tweets_sent_this_run']} more posts ({total_sent}/{total_posts} total)",
                first_tweet_id=first_tweet_id,
                tweet_id=tweet_id,
                tweets_sent=total_sent,
                total_posts=total_posts,
                chunks_processed=total_sent,
                dao_id=message.dao_id,
            )

        except Exception as e:
            logger.error(
                f"Error processing tweet message {message.id}: {str(e)}", exc_info=True
            )
            return TweetProcessingResult(
                success=False,
                message=f"Error sending tweet: {str(e)}",
                error=e,
                first_tweet_id=None,
                total_posts=len(message.message["posts"])
                if message.message and "posts" in message.message
                else 0,
                partial_success=False,
                tweet_id=None,
                dao_id=message.dao_id,
            )

    async def _process_posts(
        self,
        message: QueueMessage,
        twitter_service: TwitterService,
        remaining_posts: List[str],
        resume_info: Dict[str, Optional[str]],
        total_remaining: int,
    ) -> Dict[str, Any]:
        """Process remaining posts with automatic threading and resumption support."""
        previous_tweet_id = resume_info.get("previous_tweet_id")
        first_tweet_id = resume_info.get("first_tweet_id")
        tweets_sent_this_run = 0
        is_first_ever = previous_tweet_id is None

        logger.info(
            f"Processing {len(remaining_posts)} remaining posts for DAO {message.dao_id} "
            f"(first_ever={is_first_ever}, prior_last={previous_tweet_id})"
        )

        # Debug: Log all remaining post content to identify duplicates
        for i, post in enumerate(remaining_posts):
            logger.debug(f"Remaining post {i + 1} content: '{post}'")

        for index, post in enumerate(remaining_posts):
            try:
                # Check for image URLs in the post
                image_urls = extract_image_urls(post)
                image_url = image_urls[0] if image_urls else None

                if image_url:
                    # Remove image URL from text
                    post = re.sub(re.escape(image_url), "", post).strip()
                    post = re.sub(r"\s+", " ", post)

                # Determine reply_id: None for first ever, else previous_tweet_id
                reply_tweet_id = (
                    None if previous_tweet_id is None else previous_tweet_id
                )

                # Post the tweet
                if image_url:
                    tweet_response = await twitter_service.post_tweet_with_media(
                        image_url=image_url,
                        text=post,
                        reply_id=reply_tweet_id,
                    )
                else:
                    tweet_response = await twitter_service._apost_tweet(
                        text=post,
                        reply_in_reply_to_tweet_id=reply_tweet_id,
                    )
                logger.debug(f"Tweet response: {tweet_response}")

                if tweet_response and tweet_response.data:
                    tweets_sent_this_run += 1
                    previous_tweet_id = tweet_response.data["id"]
                    if first_tweet_id is None:
                        first_tweet_id = previous_tweet_id
                        logger.info(
                            f"Successfully created new thread with tweet {tweet_response.data['id']}"
                            f"{f' - {post[:50]}...' if len(post) > 50 else f' - {post}'}"
                        )
                    else:
                        logger.info(
                            f"Successfully posted thread reply {index + 1}/{total_remaining}: {tweet_response.data['id']}"
                            f"{f' - {post[:50]}...' if len(post) > 50 else f' - {post}'}"
                        )
                else:
                    logger.error(
                        f"Failed to send remaining tweet {index + 1}/{total_remaining}"
                    )
                    if (
                        is_first_ever and index == 0
                    ):  # First post ever fails -> whole run fails
                        return {
                            "tweets_sent_this_run": 0,
                            "final_tweet_id": previous_tweet_id,
                            "first_tweet_id": first_tweet_id,
                            "success_this_run": False,
                            "partial_success_this_run": False,
                        }
                    # For other failures, continue for partial success

            except tweepy.TooManyRequests as e:
                retry_after = int(
                    e.response.headers.get("Retry-After", 900)
                )  # Default 15min
                jitter = random.uniform(0, 30)  # Additive jitter: 0-30 seconds
                wait_until = datetime.now(timezone.utc) + timedelta(
                    seconds=retry_after + jitter
                )
                backend.upsert_job_cooldown(
                    job_type="tweet",
                    wait_until=wait_until,
                    reason=f"twitter-429 (Retry-After: {retry_after}s)",
                )
                logger.warning(f"Tweet job cooldown set until {wait_until}")
                self._rate_limited_this_run = True
                logger.warning(
                    f"Tweet rate limited; cooldown={wait_until}; stopping batch"
                )
                raise Exception(f"Twitter rate limited until {wait_until}")
            except tweepy.Forbidden as e:
                error_msg = str(e).lower()
                if "duplicate" in error_msg or "status is a duplicate" in error_msg:
                    logger.warning(
                        f"Skipping duplicate post {index + 1}/{total_remaining}: '{post[:100]}...'"
                    )
                    tweets_sent_this_run += (
                        1  # Treat as already sent to avoid retry loop
                    )
                    continue
                else:
                    logger.error(
                        f"Forbidden error on post {index + 1}/{total_remaining}: {e}"
                    )
                    if is_first_ever and index == 0:
                        return {
                            "tweets_sent_this_run": 0,
                            "final_tweet_id": previous_tweet_id,
                            "first_tweet_id": first_tweet_id,
                            "success_this_run": False,
                            "partial_success_this_run": False,
                        }
            except Exception as post_error:
                error_message = str(post_error)
                logger.error(
                    f"Error sending remaining post {index + 1}/{total_remaining}: {error_message}"
                )

                if is_first_ever and index == 0:  # Critical failure on first post ever
                    raise post_error

        success_this_run = tweets_sent_this_run == total_remaining
        partial_success_this_run = tweets_sent_this_run > 0 and not success_this_run

        return {
            "tweets_sent_this_run": tweets_sent_this_run,
            "final_tweet_id": previous_tweet_id,
            "first_tweet_id": first_tweet_id,
            "success_this_run": success_this_run,
            "partial_success_this_run": partial_success_this_run,
        }

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

        # Reset rate limit flag for next run
        self._rate_limited_this_run = False

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

            if self._rate_limited_this_run:
                logger.warning("Skipping remaining batch: rate limited this run")
                break

            for message in batch:
                logger.debug(f"Processing tweet message: {message.id}")
                result = await self._process_tweet_message(message)
                results.append(result)
                processed_count += 1

                # Build result dict with all fields (cumulative)
                result_dict = {
                    "success": result.success,
                    "partial_success": result.partial_success,
                    "message": result.message,
                    "tweet_id": result.tweet_id,
                    "first_tweet_id": result.first_tweet_id,
                    "dao_id": str(result.dao_id) if result.dao_id else None,
                    "tweets_sent": result.tweets_sent,
                    "total_posts": result.total_posts,
                    "chunks_processed": result.chunks_processed,
                    "error": str(result.error) if result.error else None,
                }

                # Always update result; set is_processed only on full success
                update_data = QueueMessageBase(result=result_dict)
                if result.success:
                    update_data.is_processed = True

                backend.update_queue_message(
                    queue_message_id=message.id,
                    update_data=update_data,
                )

                if result.success:
                    success_count += 1
                    status = "success"
                    logger.info(
                        f"Message {message.id} fully completed ({status}): "
                        f"{result.tweets_sent}/{result.total_posts} posts, "
                        f"thread root: {result.first_tweet_id}"
                    )
                else:
                    status = "partial success" if result.partial_success else "failure"
                    logger.info(
                        f"Message {message.id} {status} ({result.tweets_sent}/{result.total_posts}): "
                        f"will retry remaining posts, thread root: {result.first_tweet_id}"
                    )

        logger.info(
            f"Tweet task completed - Processed: {processed_count}, "
            f"Successful: {success_count}, Failed: {processed_count - success_count}"
        )

        return results


# Create instance for auto-registration
tweet_task = TweetTask()
