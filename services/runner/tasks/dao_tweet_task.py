from dataclasses import dataclass
from typing import Any, List, Optional
from uuid import UUID

from backend.factory import backend
from backend.models import (
    QueueMessageCreate,
    QueueMessageFilter,
    QueueMessageType,
    TokenFilter,
)
from lib.logger import configure_logger
from services.workflows import generate_dao_tweet

from ..base import BaseTask, JobContext, RunnerResult

logger = configure_logger(__name__)


@dataclass
class DAOTweetProcessingResult(RunnerResult):
    """Result of DAO tweet processing operation."""

    dao_id: Optional[UUID] = None
    tweet_id: Optional[str] = None


class DAOTweetTask(BaseTask[DAOTweetProcessingResult]):
    """Task for generating tweets for completed DAOs."""

    async def _process_dao_message(self, message: Any) -> DAOTweetProcessingResult:
        """Process a single DAO message."""
        try:
            if not message.dao_id:
                return DAOTweetProcessingResult(
                    success=False, message="DAO message has no dao_id", dao_id=None
                )

            # Get the DAO and token info
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

            token = backend.list_tokens(filters=TokenFilter(dao_id=message.dao_id))
            if not token:
                return DAOTweetProcessingResult(
                    success=False,
                    message=f"No token found for DAO: {message.dao_id}",
                    dao_id=message.dao_id,
                )

            # Generate tweet
            generated_tweet = await generate_dao_tweet(
                dao_name=dao.name,
                dao_symbol=token[0].symbol,
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

    async def validate(self, context: JobContext) -> bool:
        """Validate DAO tweet processing prerequisites."""
        try:
            # Check if we have completed DAO messages
            queue_messages = backend.list_queue_messages(
                filters=QueueMessageFilter(
                    type=QueueMessageType.DAO_TWEET, is_processed=False
                )
            )
            return bool(queue_messages)
        except Exception as e:
            logger.error(f"Error validating DAO tweet task: {str(e)}", exc_info=True)
            return False

    async def execute(self, context: JobContext) -> List[DAOTweetProcessingResult]:
        """Execute DAO tweet processing task."""
        results: List[DAOTweetProcessingResult] = []
        try:
            # Get completed DAO messages
            queue_messages = backend.list_queue_messages(
                filters=QueueMessageFilter(
                    type=QueueMessageType.DAO_TWEET, is_processed=False
                )
            )
            if not queue_messages:
                logger.debug("No completed DAO messages found")
                return results

            for message in queue_messages:
                logger.info(f"Processing DAO message for tweet generation: {message}")
                result = await self._process_dao_message(message)
                results.append(result)

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
