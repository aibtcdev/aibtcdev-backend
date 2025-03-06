from dataclasses import dataclass
from typing import Any, List, Optional
from uuid import UUID

from backend.factory import backend
from backend.models import (
    QueueMessage,
    QueueMessageBase,
    QueueMessageFilter,
    QueueMessageType,
    XCredsFilter,
)
from lib.logger import configure_logger
from lib.twitter import TwitterService
from services.runner.base import BaseTask, JobContext, RunnerConfig, RunnerResult

logger = configure_logger(__name__)


@dataclass
class TweetProcessingResult(RunnerResult):
    """Result of tweet processing operation."""

    tweet_id: Optional[str] = None
    dao_id: Optional[UUID] = None


class TweetTask(BaseTask[TweetProcessingResult]):
    """Task for sending tweets."""

    def __init__(self, config: Optional[RunnerConfig] = None):
        super().__init__(config)
        self._pending_messages: Optional[List[QueueMessage]] = None
        self.twitter_service = None

    async def _initialize_twitter_service(self, dao_id: UUID) -> bool:
        """Initialize Twitter service with credentials for the given DAO."""
        try:
            # Get Twitter credentials for the DAO
            creds = backend.list_x_creds(filters=XCredsFilter(dao_id=dao_id))
            if not creds:
                logger.error(f"No Twitter credentials found for DAO {dao_id}")
                return False

            # Initialize Twitter service with the credentials
            self.twitter_service = TwitterService(
                consumer_key=creds[0].consumer_key,
                consumer_secret=creds[0].consumer_secret,
                client_id=creds[0].client_id,
                client_secret=creds[0].client_secret,
                access_token=creds[0].access_token,
                access_secret=creds[0].access_secret,
            )
            await self.twitter_service._ainitialize()
            logger.debug(f"Initialized Twitter service for DAO {dao_id}")
            return True

        except Exception as e:
            logger.error(f"Error initializing Twitter service: {str(e)}", exc_info=True)
            return False

    async def _validate_config(self, context: JobContext) -> bool:
        """Validate task configuration."""
        try:
            # No specific config validation needed as credentials are per-DAO
            return True
        except Exception as e:
            logger.error(f"Error validating tweet task config: {str(e)}", exc_info=True)
            return False

    async def _validate_prerequisites(self, context: JobContext) -> bool:
        """Validate task prerequisites."""
        try:
            # Cache pending messages for later use
            self._pending_messages = backend.list_queue_messages(
                filters=QueueMessageFilter(
                    type=QueueMessageType.TWEET, is_processed=False
                )
            )
            return True
        except Exception as e:
            logger.error(
                f"Error validating tweet prerequisites: {str(e)}", exc_info=True
            )
            self._pending_messages = None
            return False

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate task-specific conditions."""
        try:
            if not self._pending_messages:
                logger.debug("No pending tweet messages found")
                return False

            message_count = len(self._pending_messages)
            if message_count > 0:
                logger.debug(f"Found {message_count} pending tweet messages")
                return True

            logger.debug("No pending tweet messages to process")
            return False

        except Exception as e:
            logger.error(f"Error in tweet task validation: {str(e)}", exc_info=True)
            return False

    async def _validate_message(
        self, message: QueueMessage
    ) -> Optional[TweetProcessingResult]:
        """Validate a single message before processing."""
        try:
            # Check if message exists
            if not message.message:
                return TweetProcessingResult(
                    success=False,
                    message="Tweet message is empty",
                    tweet_id=message.tweet_id,
                )

            # Extract tweet text from the message field
            tweet_text = None
            if isinstance(message.message, dict) and "message" in message.message:
                tweet_text = message.message["message"]
            else:
                return TweetProcessingResult(
                    success=False,
                    message=f"Unsupported tweet message format: {message.message}",
                    tweet_id=message.tweet_id,
                )

            if not tweet_text:
                return TweetProcessingResult(
                    success=False,
                    message="Tweet message content is empty",
                    tweet_id=message.tweet_id,
                )

            if not message.dao_id:
                return TweetProcessingResult(
                    success=False,
                    message="Tweet message has no dao_id",
                    dao_id=None,
                )

            # Check tweet length
            if len(tweet_text) > 280:  # Twitter's character limit
                return TweetProcessingResult(
                    success=False,
                    message=f"Tweet exceeds character limit: {len(tweet_text)} chars",
                    tweet_id=message.tweet_id,
                    dao_id=message.dao_id,
                )

            # No need to modify the message structure, keep it as is
            return None

        except Exception as e:
            logger.error(
                f"Error validating message {message.id}: {str(e)}", exc_info=True
            )
            return TweetProcessingResult(
                success=False,
                message=f"Error validating message: {str(e)}",
                error=e,
                tweet_id=message.tweet_id if hasattr(message, "tweet_id") else None,
                dao_id=message.dao_id if hasattr(message, "dao_id") else None,
            )

    async def _process_tweet_message(
        self, message: QueueMessage
    ) -> TweetProcessingResult:
        """Process a single tweet message."""
        try:
            # Validate message first
            validation_result = await self._validate_message(message)
            if validation_result:
                return validation_result

            # Initialize Twitter service for this DAO
            if not await self._initialize_twitter_service(message.dao_id):
                return TweetProcessingResult(
                    success=False,
                    message=f"Failed to initialize Twitter service for DAO: {message.dao_id}",
                    dao_id=message.dao_id,
                )

            # Extract tweet text directly from the message format
            tweet_text = message.message["message"]
            logger.info(f"Sending tweet for DAO {message.dao_id}")
            logger.debug(f"Tweet content: {tweet_text}")

            # Prepare tweet parameters
            tweet_params = {"text": tweet_text}
            if message.tweet_id:
                tweet_params["reply_in_reply_to_tweet_id"] = message.tweet_id

            # Send tweet using Twitter service
            tweet_response = await self.twitter_service._apost_tweet(**tweet_params)

            if not tweet_response:
                return TweetProcessingResult(
                    success=False,
                    message="Failed to send tweet",
                    dao_id=message.dao_id,
                    tweet_id=message.tweet_id,
                )

            logger.info(f"Successfully posted tweet {tweet_response.id}")
            logger.debug(f"Tweet ID: {tweet_response.id}")

            return TweetProcessingResult(
                success=True,
                message="Successfully sent tweet",
                tweet_id=tweet_response.id,
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
                tweet_id=message.tweet_id if hasattr(message, "tweet_id") else None,
                dao_id=message.dao_id if hasattr(message, "dao_id") else None,
            )

    async def _execute_impl(self, context: JobContext) -> List[TweetProcessingResult]:
        """Execute tweet sending task."""
        results: List[TweetProcessingResult] = []
        try:
            if not self._pending_messages:
                return results

            processed_count = 0
            success_count = 0

            for message in self._pending_messages:
                logger.debug(f"Processing tweet message: {message.id}")
                result = await self._process_tweet_message(message)
                results.append(result)
                processed_count += 1

                if result.success:
                    success_count += 1
                    backend.update_queue_message(
                        queue_message_id=message.id,
                        update_data=QueueMessageBase(is_processed=True),
                    )
                    logger.debug(f"Marked message {message.id} as processed")

            logger.debug(
                f"Task metrics - Processed: {processed_count}, "
                f"Successful: {success_count}"
            )

            return results

        except Exception as e:
            logger.error(f"Error in tweet task: {str(e)}", exc_info=True)
            results.append(
                TweetProcessingResult(
                    success=False,
                    message=f"Error in tweet task: {str(e)}",
                    error=e,
                )
            )
            return results


tweet_task = TweetTask()
