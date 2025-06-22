"""Enhanced Tweet Task using the new job queue system."""

from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID


from backend.factory import backend
from backend.models import (
    QueueMessage,
    QueueMessageBase,
    QueueMessageFilter,
    QueueMessageType,
    XCredsFilter,
)
from config import config
from lib.logger import configure_logger
from lib.utils import extract_image_urls
from services.communication.twitter_service import TwitterService
from services.infrastructure.job_management.base import (
    BaseTask,
    JobContext,
    RunnerConfig,
    RunnerResult,
)
from services.infrastructure.job_management.decorators import JobPriority, job
import re

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
    interval_seconds=30,
    priority=JobPriority.HIGH,
    max_retries=3,
    retry_delay_seconds=60,
    timeout_seconds=300,
    max_concurrent=1,
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
        """Initialize Twitter service with credentials from config."""
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

            # Initialize Twitter service with credentials from config
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
            logger.debug("No pending tweet messages found")
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
        """Check if a message is valid for processing."""
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

            # Check for message field (new format) or chunks field (alternative format)
            if "message" in message.message:
                tweet_data = message.message["message"]
                if not tweet_data:
                    logger.debug(
                        f"Tweet message {message.id} invalid: message data is None or empty"
                    )
                    return False

                # Handle new chunked array format
                if isinstance(tweet_data, list):
                    if not tweet_data:
                        logger.debug(
                            f"Tweet message {message.id} invalid: message array is empty"
                        )
                        return False

                    # Validate each chunk
                    for i, chunk in enumerate(tweet_data):
                        if not isinstance(chunk, str):
                            logger.debug(
                                f"Tweet message {message.id} invalid: chunk {i} is not a string, got {type(chunk)}"
                            )
                            return False
                        if not chunk.strip():
                            logger.debug(
                                f"Tweet message {message.id} invalid: chunk {i} is empty or whitespace"
                            )
                            return False

                    logger.debug(
                        f"Tweet message {message.id} is valid with {len(tweet_data)} chunks"
                    )
                    return True

                # Handle legacy string format for backward compatibility
                elif isinstance(tweet_data, str):
                    if not tweet_data.strip():
                        logger.debug(
                            f"Tweet message {message.id} invalid: tweet text is only whitespace"
                        )
                        return False

                    logger.debug(
                        f"Tweet message {message.id} is valid (legacy format) with content: {tweet_data[:50]}..."
                    )
                    return True

                else:
                    logger.debug(
                        f"Tweet message {message.id} invalid: message data is not a string or array, got {type(tweet_data)}"
                    )
                    return False
            elif "chunks" in message.message:
                # Handle alternative chunks format
                tweet_data = message.message["chunks"]
                if not tweet_data:
                    logger.debug(
                        f"Tweet message {message.id} invalid: chunks data is None or empty"
                    )
                    return False

                if isinstance(tweet_data, list):
                    if not tweet_data:
                        logger.debug(
                            f"Tweet message {message.id} invalid: chunks array is empty"
                        )
                        return False

                    # Validate each chunk
                    for i, chunk in enumerate(tweet_data):
                        if not isinstance(chunk, str):
                            logger.debug(
                                f"Tweet message {message.id} invalid: chunk {i} is not a string, got {type(chunk)}"
                            )
                            return False
                        if not chunk.strip():
                            logger.debug(
                                f"Tweet message {message.id} invalid: chunk {i} is empty or whitespace"
                            )
                            return False

                    logger.debug(
                        f"Tweet message {message.id} is valid with {len(tweet_data)} chunks (chunks format)"
                    )
                    return True
                else:
                    logger.debug(
                        f"Tweet message {message.id} invalid: chunks data is not an array, got {type(tweet_data)}"
                    )
                    return False
            else:
                logger.debug(
                    f"Tweet message {message.id} invalid: neither 'chunks' nor 'message' key found. Keys: {list(message.message.keys())}"
                )
                return False

        except Exception as e:
            logger.debug(f"Tweet message {message.id} validation error: {str(e)}")
            return False

    async def _process_tweet_message(
        self, message: QueueMessage
    ) -> TweetProcessingResult:
        """Process a single tweet message with enhanced error handling and threading support.

        Now supports the new chunked message format:
        {
            "chunks": ["chunk1", "chunk2", "chunk3", ...],
            "total_chunks": 3
        }

        Also maintains backward compatibility with legacy format:
        {
            "message": "Main tweet content",
            "reply_to_tweet_id": "optional_tweet_id_to_reply_to",
            "follow_up_message": "optional_follow_up_content"
        }
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

            # Handle message field (can be array or string) or chunks field
            if "message" in message.message:
                tweet_data = message.message["message"]

                # Handle new chunked array format
                if isinstance(tweet_data, list):
                    logger.info(
                        f"Processing chunked tweet message for DAO {message.dao_id} with {len(tweet_data)} chunks"
                    )
                    logger.debug(
                        f"First chunk preview: {tweet_data[0][:100]}..."
                        if tweet_data
                        else "No chunks"
                    )

                    return await self._process_chunked_message(
                        message, twitter_service, tweet_data
                    )

                # Handle legacy string format for backward compatibility
                elif isinstance(tweet_data, str):
                    logger.info(
                        f"Processing legacy format tweet message for DAO {message.dao_id}"
                    )
                    return await self._process_legacy_message(message, twitter_service)

            elif "chunks" in message.message:
                # Handle alternative chunks format
                tweet_data = message.message["chunks"]
                logger.info(
                    f"Processing chunked tweet message (chunks format) for DAO {message.dao_id} with {len(tweet_data)} chunks"
                )
                logger.debug(
                    f"First chunk preview: {tweet_data[0][:100]}..."
                    if tweet_data
                    else "No chunks"
                )

                return await self._process_chunked_message(
                    message, twitter_service, tweet_data
                )

            else:
                logger.warning(f"Tweet message {message.id} has unrecognized format")
                return TweetProcessingResult(
                    success=False,
                    message="Tweet message format not recognized",
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
                tweet_id=getattr(message, "tweet_id", None),
                dao_id=message.dao_id,
            )

    async def _process_chunked_message(
        self, message: QueueMessage, twitter_service: TwitterService, chunks: List[str]
    ) -> TweetProcessingResult:
        """Process a message with pre-chunked content."""
        previous_tweet_id = getattr(
            message, "tweet_id", None
        )  # Use existing tweet_id if threading
        tweets_sent = 0

        # Check if chunks already have thread indices (e.g., "(1/3)")
        has_indices = len(chunks) > 1 and any(
            "(" in chunk and "/" in chunk and ")" in chunk for chunk in chunks
        )

        logger.info(
            f"Processing {len(chunks)} pre-chunked tweets for DAO {message.dao_id}"
            f"{' with thread indices' if has_indices else ''}"
        )

        for index, chunk in enumerate(chunks):
            try:
                # Check for image URLs in the chunk
                image_urls = extract_image_urls(chunk)
                image_url = image_urls[0] if image_urls else None

                if image_url:
                    # Remove image URL from text
                    chunk = re.sub(re.escape(image_url), "", chunk).strip()
                    chunk = re.sub(r"\s+", " ", chunk)

                # Post the tweet
                if index == 0 and image_url:
                    tweet_response = await twitter_service.post_tweet_with_media(
                        image_url=image_url,
                        text=chunk,
                        reply_id=previous_tweet_id,
                    )
                else:
                    tweet_response = await twitter_service._apost_tweet(
                        text=chunk,
                        reply_in_reply_to_tweet_id=previous_tweet_id,
                    )

                if tweet_response:
                    tweets_sent += 1
                    previous_tweet_id = tweet_response.id
                    logger.info(
                        f"Successfully posted tweet chunk {index + 1}/{len(chunks)}: {tweet_response.id}"
                        f"{f' - {chunk[:50]}...' if len(chunk) > 50 else f' - {chunk}'}"
                    )
                else:
                    logger.error(
                        f"Failed to send tweet chunk {index + 1}/{len(chunks)}"
                    )
                    if index == 0:  # If first chunk fails, whole message fails
                        return TweetProcessingResult(
                            success=False,
                            message="Failed to send first tweet chunk",
                            dao_id=message.dao_id,
                            tweet_id=previous_tweet_id,
                            chunks_processed=index,
                        )
                    # For subsequent chunks, we can continue

            except Exception as chunk_error:
                logger.error(
                    f"Error sending chunk {index + 1}/{len(chunks)}: {str(chunk_error)}"
                )
                if index == 0:  # Critical failure on first chunk
                    raise chunk_error

        return TweetProcessingResult(
            success=tweets_sent > 0,
            message=f"Successfully sent {tweets_sent}/{len(chunks)} tweet chunks"
            f"{' with thread indices' if has_indices else ''}",
            tweet_id=previous_tweet_id,
            dao_id=message.dao_id,
            tweets_sent=tweets_sent,
            chunks_processed=len(chunks),
        )

    async def _process_legacy_message(
        self, message: QueueMessage, twitter_service: TwitterService
    ) -> TweetProcessingResult:
        """Process a message in the legacy format for backward compatibility."""
        # Extract tweet text
        tweet_text = message.message["message"]
        if not isinstance(tweet_text, str):
            logger.warning(
                f"Tweet message {message.id} content is not a string: {type(tweet_text)}"
            )
            return TweetProcessingResult(
                success=False,
                message=f"Tweet content is not a string: {type(tweet_text)}",
                dao_id=message.dao_id,
            )

        # Check for threading information
        reply_to_tweet_id = message.message.get("reply_to_tweet_id")
        if reply_to_tweet_id:
            logger.info(
                f"Tweet will be threaded as reply to tweet ID: {reply_to_tweet_id}"
            )

        logger.info(f"Sending legacy format tweet for DAO {message.dao_id}")
        logger.debug(f"Tweet content: {tweet_text[:100]}...")

        # Look for image URLs in the text
        image_urls = extract_image_urls(tweet_text)
        image_url = image_urls[0] if image_urls else None

        if image_url:
            # Remove image URL from text
            tweet_text = re.sub(re.escape(image_url), "", tweet_text).strip()
            tweet_text = re.sub(r"\s+", " ", tweet_text)

        # Split tweet text if necessary
        chunks = self._split_text_into_chunks(tweet_text)
        # Use reply_to_tweet_id as initial thread ID, or message.tweet_id for continuation
        previous_tweet_id = reply_to_tweet_id or getattr(message, "tweet_id", None)
        tweets_sent = 0

        for index, chunk in enumerate(chunks):
            try:
                if index == 0 and image_url:
                    tweet_response = await twitter_service.post_tweet_with_media(
                        image_url=image_url,
                        text=chunk,
                        reply_id=previous_tweet_id,
                    )
                else:
                    tweet_response = await twitter_service._apost_tweet(
                        text=chunk,
                        reply_in_reply_to_tweet_id=previous_tweet_id,
                    )

                if tweet_response:
                    tweets_sent += 1
                    previous_tweet_id = tweet_response.id
                    logger.info(
                        f"Successfully posted tweet chunk {index + 1}: {tweet_response.id}"
                    )
                else:
                    logger.error(f"Failed to send tweet chunk {index + 1}")
                    if index == 0:
                        return TweetProcessingResult(
                            success=False,
                            message="Failed to send first tweet chunk",
                            dao_id=message.dao_id,
                            tweet_id=previous_tweet_id,
                            chunks_processed=index,
                        )

            except Exception as chunk_error:
                logger.error(f"Error sending chunk {index + 1}: {str(chunk_error)}")
                if index == 0:
                    raise chunk_error

        result = TweetProcessingResult(
            success=tweets_sent > 0,
            message=f"Successfully sent {tweets_sent}/{len(chunks)} tweet chunks",
            tweet_id=previous_tweet_id,
            dao_id=message.dao_id,
            tweets_sent=tweets_sent,
            chunks_processed=len(chunks),
        )

        # Check if there's a follow-up message to create as a thread
        if result.success and result.tweet_id:
            follow_up_tweet_id = await self._create_follow_up_tweet(
                message, result.tweet_id
            )
            if follow_up_tweet_id:
                result.tweets_sent += 1
                result.tweet_id = follow_up_tweet_id
                result.message += " with follow-up thread"
                logger.info(
                    f"Successfully created follow-up tweet thread: {follow_up_tweet_id}"
                )

        return result

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

    def _split_text_into_chunks(self, text: str, limit: int = 280) -> List[str]:
        """Split text into chunks not exceeding the limit without cutting words."""
        words = text.split()
        chunks = []
        current = ""
        for word in words:
            if len(current) + len(word) + (1 if current else 0) <= limit:
                current = f"{current} {word}".strip()
            else:
                if current:
                    chunks.append(current)
                current = word
        if current:
            chunks.append(current)
        return chunks

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

    async def _create_follow_up_tweet(
        self, message: QueueMessage, original_tweet_id: str
    ) -> Optional[str]:
        """Create a follow-up tweet as a thread to the original tweet (legacy format only)."""
        try:
            follow_up_content = message.message.get("follow_up_message")
            if not follow_up_content:
                return None

            logger.info(f"Creating follow-up tweet as thread to {original_tweet_id}")

            # Get Twitter service for this DAO
            twitter_service = await self._get_twitter_service(message.dao_id)
            if not twitter_service:
                logger.error("Failed to get Twitter service for follow-up tweet")
                return None

            # Check for image URLs in the follow-up text
            image_urls = extract_image_urls(follow_up_content)
            image_url = image_urls[0] if image_urls else None

            if image_url:
                # Remove image URL from text
                follow_up_content = re.sub(
                    re.escape(image_url), "", follow_up_content
                ).strip()
                follow_up_content = re.sub(r"\s+", " ", follow_up_content)

            # Split follow-up text if necessary
            chunks = self._split_text_into_chunks(follow_up_content)
            previous_tweet_id = original_tweet_id

            for index, chunk in enumerate(chunks):
                try:
                    if index == 0 and image_url:
                        tweet_response = await twitter_service.post_tweet_with_media(
                            image_url=image_url,
                            text=chunk,
                            reply_id=previous_tweet_id,
                        )
                    else:
                        tweet_response = await twitter_service._apost_tweet(
                            text=chunk,
                            reply_in_reply_to_tweet_id=previous_tweet_id,
                        )

                    if tweet_response:
                        previous_tweet_id = tweet_response.id
                        logger.info(
                            f"Successfully posted follow-up tweet chunk {index + 1}: {tweet_response.id}"
                        )
                    else:
                        logger.error(
                            f"Failed to send follow-up tweet chunk {index + 1}"
                        )
                        break

                except Exception as chunk_error:
                    logger.error(
                        f"Error sending follow-up tweet chunk {index + 1}: {str(chunk_error)}"
                    )
                    break

            return previous_tweet_id

        except Exception as e:
            logger.error(f"Error creating follow-up tweet: {str(e)}", exc_info=True)
            return None


# Create instance for auto-registration
tweet_task = TweetTask()
