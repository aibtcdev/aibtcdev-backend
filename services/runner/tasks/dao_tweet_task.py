from dataclasses import dataclass
from typing import Any, List, Optional
from uuid import UUID

from backend.factory import backend
from backend.models import (
    QueueMessageBase,
    QueueMessageCreate,
    QueueMessageFilter,
    QueueMessageType,
    TokenFilter,
)
from lib.logger import configure_logger
from services.workflows import generate_dao_tweet

from ..base import BaseTask, JobContext, RunnerConfig, RunnerResult
from ..decorators import JobPriority, job

logger = configure_logger(__name__)


@dataclass
class DAOTweetProcessingResult(RunnerResult):
    """Result of DAO tweet processing operation."""

    dao_id: Optional[UUID] = None
    tweet_id: Optional[str] = None
    tweets_generated: int = 0
    tweet_messages_created: int = 0


@job(
    job_type="dao_tweet",
    name="DAO Tweet Generator",
    description="Generates tweets for completed DAOs with enhanced monitoring and error handling",
    interval_seconds=45,
    priority=JobPriority.MEDIUM,
    max_retries=3,
    retry_delay_seconds=60,
    timeout_seconds=180,
    max_concurrent=2,
    requires_ai=True,
    batch_size=5,
    enable_dead_letter_queue=True,
)
class DAOTweetTask(BaseTask[DAOTweetProcessingResult]):
    """Task for generating tweets for completed DAOs with enhanced capabilities."""

    def __init__(self, config: Optional[RunnerConfig] = None):
        super().__init__(config)
        self._pending_messages = None

    async def _validate_config(self, context: JobContext) -> bool:
        """Validate task configuration."""
        try:
            # Check if generate_dao_tweet workflow is available
            return True
        except Exception as e:
            logger.error(
                f"Error validating DAO tweet task config: {str(e)}", exc_info=True
            )
            return False

    async def _validate_resources(self, context: JobContext) -> bool:
        """Validate resource availability."""
        try:
            # Check backend connectivity
            backend.get_api_status()
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
                    type=QueueMessageType.DAO_TWEET, is_processed=False
                )
            )
            return True
        except Exception as e:
            logger.error(
                f"Error validating DAO tweet prerequisites: {str(e)}", exc_info=True
            )
            self._pending_messages = None
            return False

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate task-specific conditions."""
        try:
            if not self._pending_messages:
                logger.debug("No pending DAO tweet messages found")
                return False

            # Validate each message has valid DAO data
            valid_messages = []
            for message in self._pending_messages:
                if await self._is_message_valid(message):
                    valid_messages.append(message)

            self._pending_messages = valid_messages

            if valid_messages:
                logger.debug(f"Found {len(valid_messages)} valid DAO tweet messages")
                return True

            logger.debug("No valid DAO tweet messages to process")
            return False

        except Exception as e:
            logger.error(f"Error in DAO tweet task validation: {str(e)}", exc_info=True)
            return False

    async def _is_message_valid(self, message: Any) -> bool:
        """Check if a DAO tweet message is valid for processing."""
        try:
            if not message.dao_id:
                return False

            # Validate DAO exists and is deployed
            dao = backend.get_dao(message.dao_id)
            if not dao or not dao.is_deployed:
                return False

            # Validate token exists
            token = backend.list_tokens(filters=TokenFilter(dao_id=message.dao_id))
            if not token:
                return False

            return True
        except Exception:
            return False

    async def _validate_message(
        self, message: Any
    ) -> Optional[DAOTweetProcessingResult]:
        """Validate a single message before processing."""
        try:
            if not message.dao_id:
                return DAOTweetProcessingResult(
                    success=False, message="DAO message has no dao_id", dao_id=None
                )

            # Validate DAO exists and is deployed
            dao = backend.get_dao(message.dao_id)
            if not dao:
                return DAOTweetProcessingResult(
                    success=False,
                    message=f"No DAO found for id: {message.dao_id}",
                    dao_id=message.dao_id,
                )

            if not dao.is_deployed:
                return DAOTweetProcessingResult(
                    success=False,
                    message=f"DAO is not deployed: {message.dao_id}",
                    dao_id=message.dao_id,
                )

            # Validate token exists
            token = backend.list_tokens(filters=TokenFilter(dao_id=message.dao_id))
            if not token:
                return DAOTweetProcessingResult(
                    success=False,
                    message=f"No token found for DAO: {message.dao_id}",
                    dao_id=message.dao_id,
                )

            return None  # Validation passed

        except Exception as e:
            logger.error(
                f"Error validating message {message.id}: {str(e)}", exc_info=True
            )
            return DAOTweetProcessingResult(
                success=False,
                message=f"Error validating message: {str(e)}",
                error=e,
                dao_id=message.dao_id if hasattr(message, "dao_id") else None,
            )

    async def _process_dao_message(self, message: Any) -> DAOTweetProcessingResult:
        """Process a single DAO message with enhanced error handling."""
        try:
            # Validate message first
            validation_result = await self._validate_message(message)
            if validation_result:
                return validation_result

            # Get the validated DAO and token info
            dao = backend.get_dao(message.dao_id)
            token = backend.list_tokens(filters=TokenFilter(dao_id=message.dao_id))[0]

            logger.info(f"Generating tweet for DAO: {dao.name} ({dao.id})")
            logger.debug(
                f"DAO details - Symbol: {token.symbol}, Mission: {dao.mission[:100]}..."
            )

            # Generate tweet
            generated_tweet = await generate_dao_tweet(
                dao_name=dao.name,
                dao_symbol=token.symbol,
                dao_mission=dao.mission,
                dao_id=dao.id,
            )

            if not generated_tweet or not generated_tweet.get("tweet_text"):
                return DAOTweetProcessingResult(
                    success=False,
                    message="Failed to generate tweet content",
                    dao_id=dao.id,
                    tweet_id=message.tweet_id,
                )

            # Create a new tweet message in the queue
            tweet_message = backend.create_queue_message(
                QueueMessageCreate(
                    type="tweet",
                    dao_id=dao.id,
                    message={"message": generated_tweet["tweet_text"]},
                    tweet_id=message.tweet_id,
                    conversation_id=message.conversation_id,
                )
            )

            logger.info(f"Created tweet message for DAO: {dao.name}")
            logger.debug(f"Tweet message ID: {tweet_message.id}")
            logger.debug(
                f"Generated tweet content: {generated_tweet['tweet_text'][:100]}..."
            )

            return DAOTweetProcessingResult(
                success=True,
                message="Successfully generated tweet",
                dao_id=dao.id,
                tweet_id=message.tweet_id,
                tweets_generated=1,
                tweet_messages_created=1,
            )

        except Exception as e:
            logger.error(
                f"Error processing DAO message {message.id}: {str(e)}", exc_info=True
            )
            return DAOTweetProcessingResult(
                success=False,
                message=f"Error processing DAO: {str(e)}",
                error=e,
                dao_id=message.dao_id if hasattr(message, "dao_id") else None,
            )

    def _should_retry_on_error(self, error: Exception, context: JobContext) -> bool:
        """Determine if error should trigger retry."""
        # Retry on network errors, AI service timeouts
        retry_errors = (
            ConnectionError,
            TimeoutError,
        )

        # Don't retry on DAO validation errors
        if "DAO is not deployed" in str(error):
            return False
        if "No DAO found" in str(error):
            return False
        if "No token found" in str(error):
            return False

        return isinstance(error, retry_errors)

    async def _handle_execution_error(
        self, error: Exception, context: JobContext
    ) -> Optional[List[DAOTweetProcessingResult]]:
        """Handle execution errors with recovery logic."""
        if "ai" in str(error).lower() or "openai" in str(error).lower():
            logger.warning(f"AI service error: {str(error)}, will retry")
            return None

        if isinstance(error, (ConnectionError, TimeoutError)):
            logger.warning(f"Network error: {str(error)}, will retry")
            return None

        # For DAO validation errors, don't retry
        return [
            DAOTweetProcessingResult(
                success=False,
                message=f"Unrecoverable error: {str(error)}",
                error=error,
            )
        ]

    async def _post_execution_cleanup(
        self, context: JobContext, results: List[DAOTweetProcessingResult]
    ) -> None:
        """Cleanup after task execution."""
        # Clear cached pending messages
        self._pending_messages = None
        logger.debug("DAO tweet task cleanup completed")

    async def _execute_impl(
        self, context: JobContext
    ) -> List[DAOTweetProcessingResult]:
        """Execute DAO tweet processing task with batch processing."""
        results: List[DAOTweetProcessingResult] = []

        if not self._pending_messages:
            logger.debug("No pending DAO tweet messages to process")
            return results

        processed_count = 0
        success_count = 0
        batch_size = getattr(context, "batch_size", 5)

        # Process messages in batches
        for i in range(0, len(self._pending_messages), batch_size):
            batch = self._pending_messages[i : i + batch_size]

            for message in batch:
                logger.debug(f"Processing DAO tweet message: {message.id}")
                result = await self._process_dao_message(message)
                results.append(result)
                processed_count += 1

                if result.success:
                    success_count += 1
                    backend.update_queue_message(
                        queue_message_id=message.id,
                        update_data=QueueMessageBase(is_processed=True),
                    )
                    logger.debug(f"Marked message {message.id} as processed")

        logger.info(
            f"DAO tweet task completed - Processed: {processed_count}, "
            f"Successful: {success_count}, Failed: {processed_count - success_count}"
        )

        return results


# Create instance for auto-registration
dao_tweet_task = DAOTweetTask()
