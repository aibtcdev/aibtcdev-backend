from ..base import BaseTask, JobContext, RunnerConfig, RunnerResult
from backend.factory import backend
from backend.models import QueueMessageBase, QueueMessageFilter, XCredsFilter
from dataclasses import dataclass
from lib.logger import configure_logger
from lib.twitter import TwitterService
from typing import Any, List, Optional
from uuid import UUID

logger = configure_logger(__name__)


@dataclass
class TweetProcessingResult(RunnerResult):
    """Result of tweet processing operation."""

    tweet_id: Optional[str] = None
    dao_id: Optional[UUID] = None


class TweetTask(BaseTask[TweetProcessingResult]):
    """Task for processing tweets from queue and posting them to Twitter."""

    def __init__(self, config: Optional[RunnerConfig] = None):
        super().__init__(config)
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
            return True
        except Exception as e:
            logger.error(f"Error initializing Twitter service: {str(e)}", exc_info=True)
            return False

    async def _process_tweet_message(self, message: Any) -> TweetProcessingResult:
        """Process a single tweet message."""
        try:
            if not message.dao_id:
                return TweetProcessingResult(
                    success=False, message="Tweet message has no dao_id", dao_id=None
                )

            # Initialize Twitter service for this DAO
            if not await self._initialize_twitter_service(message.dao_id):
                return TweetProcessingResult(
                    success=False,
                    message=f"Failed to initialize Twitter service for DAO: {message.dao_id}",
                    dao_id=message.dao_id,
                )

            # Parse the message body
            try:
                tweet_text = message.message.get("body")
                if not tweet_text:
                    return TweetProcessingResult(
                        success=False,
                        message="No tweet text found in message body",
                        dao_id=message.dao_id,
                    )
            except Exception as e:
                logger.error(f"Error parsing message body: {str(e)}", exc_info=True)
                return TweetProcessingResult(
                    success=False,
                    message=f"Error parsing message body: {str(e)}",
                    dao_id=message.dao_id,
                )

            # Post the tweet
            tweet_response = await self.twitter_service._apost_tweet(
                text=tweet_text, reply_in_reply_to_tweet_id=message.tweet_id
            )

            if not tweet_response:
                return TweetProcessingResult(
                    success=False, message="Failed to post tweet", dao_id=message.dao_id
                )

            return TweetProcessingResult(
                success=True,
                message="Successfully posted tweet",
                tweet_id=tweet_response.id,
                dao_id=message.dao_id,
            )

        except Exception as e:
            logger.error(
                f"Error processing tweet message {message.id}: {str(e)}", exc_info=True
            )
            return TweetProcessingResult(
                success=False,
                message=f"Error processing tweet: {str(e)}",
                error=e,
                dao_id=message.dao_id if hasattr(message, "dao_id") else None,
            )

    async def validate(self, context: JobContext) -> bool:
        """Validate tweet processing prerequisites."""
        try:
            # Check if we have unprocessed messages
            queue_messages = backend.list_queue_messages(
                filters=QueueMessageFilter(type="tweet", is_processed=False)
            )
            return bool(queue_messages)
        except Exception as e:
            logger.error(f"Error validating tweet task: {str(e)}", exc_info=True)
            return False

    async def execute(self, context: JobContext) -> List[TweetProcessingResult]:
        """Execute tweet processing task."""
        results: List[TweetProcessingResult] = []
        try:
            # Get unprocessed tweet messages
            queue_messages = backend.list_queue_messages(
                filters=QueueMessageFilter(type="tweet", is_processed=False)
            )
            if not queue_messages:
                logger.debug("No tweet messages in queue")
                return results

            for message in queue_messages:
                logger.info(f"Processing tweet message: {message}")
                result = await self._process_tweet_message(message)
                results.append(result)

                if result.success:
                    backend.update_queue_message(
                        queue_message_id=message.id,
                        update_data=QueueMessageBase(is_processed=True),
                    )

            return results
        except Exception as e:
            logger.error(f"Error in tweet task: {str(e)}", exc_info=True)
            results.append(
                TweetProcessingResult(
                    success=False, message=f"Error in tweet task: {str(e)}", error=e
                )
            )
            return results
