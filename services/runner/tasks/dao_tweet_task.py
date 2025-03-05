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

logger = configure_logger(__name__)


@dataclass
class DAOTweetProcessingResult(RunnerResult):
    """Result of DAO tweet processing operation."""

    dao_id: Optional[UUID] = None
    tweet_id: Optional[str] = None


class DAOTweetTask(BaseTask[DAOTweetProcessingResult]):
    """Task for generating tweets for completed DAOs."""

    def __init__(self, config: Optional[RunnerConfig] = None):
        super().__init__(config)
        self._pending_messages = None

    async def _validate_config(self, context: JobContext) -> bool:
        """Validate task configuration."""
        try:
            # No specific config requirements for this task
            return True
        except Exception as e:
            logger.error(
                f"Error validating DAO tweet task config: {str(e)}", exc_info=True
            )
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

            message_count = len(self._pending_messages)
            if message_count > 0:
                logger.debug(f"Found {message_count} pending DAO tweet messages")
                return True

            logger.debug("No pending DAO tweet messages to process")
            return False

        except Exception as e:
            logger.error(f"Error in DAO tweet task validation: {str(e)}", exc_info=True)
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
        """Process a single DAO message."""
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
                f"DAO details - Symbol: {token.symbol}, Mission: {dao.mission}"
            )

            # Generate tweet
            generated_tweet = await generate_dao_tweet(
                dao_name=dao.name,
                dao_symbol=token.symbol,
                dao_mission=dao.mission,
                dao_id=dao.id,
            )

            # Create a new tweet message in the queue
            tweet_message = backend.create_queue_message(
                QueueMessageCreate(
                    type="tweet",
                    dao_id=dao.id,
                    message={"body": generated_tweet["tweet_text"]},
                    tweet_id=message.tweet_id,
                    conversation_id=message.conversation_id,
                )
            )

            logger.info(f"Created tweet message for DAO: {dao.name}")
            logger.debug(f"Tweet message ID: {tweet_message.id}")

            return DAOTweetProcessingResult(
                success=True,
                message="Successfully generated tweet",
                dao_id=dao.id,
                tweet_id=message.tweet_id,
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

    async def _execute_impl(
        self, context: JobContext
    ) -> List[DAOTweetProcessingResult]:
        """Execute DAO tweet processing task."""
        results: List[DAOTweetProcessingResult] = []
        try:
            if not self._pending_messages:
                return results

            processed_count = 0
            success_count = 0

            for message in self._pending_messages:
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

            logger.debug(
                f"Task metrics - Processed: {processed_count}, "
                f"Successful: {success_count}"
            )

            return results

        except Exception as e:
            logger.error(f"Error in DAO tweet task: {str(e)}", exc_info=True)
            results.append(
                DAOTweetProcessingResult(
                    success=False, message=f"Error in DAO tweet task: {str(e)}", error=e
                )
            )
            return results


dao_tweet_task = DAOTweetTask()
