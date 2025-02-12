from ..base import BaseTask, JobContext, RunnerConfig, RunnerResult
from backend.factory import backend
from backend.models import (
    DAOBase,
    QueueMessageBase,
    QueueMessageFilter,
    TokenFilter,
    XTweetFilter,
    XUserBase,
)
from dataclasses import dataclass
from lib.logger import configure_logger
from services.twitter import TweetData, TwitterMentionHandler, create_twitter_handler
from services.workflows import generate_dao_tweet
from typing import Any, Dict, List, Optional
from uuid import UUID

logger = configure_logger(__name__)


@dataclass
class TweetProcessingResult(RunnerResult):
    """Result of tweet processing operation."""

    tweet_id: Optional[str] = None
    dao_id: Optional[UUID] = None


class TweetTask(BaseTask[TweetProcessingResult]):
    """Task for processing tweets."""

    def __init__(self, config: Optional[RunnerConfig] = None):
        super().__init__(config)
        self.twitter_handler = create_twitter_handler()

    async def _process_tweet_message(
        self, message: Any, dao_messages: list
    ) -> TweetProcessingResult:
        """Process a single tweet message."""
        try:
            if not message.dao_id:
                return TweetProcessingResult(
                    success=False, message="Tweet message has no dao_id", dao_id=None
                )

            # Get the DAO and token info
            dao = backend.get_dao(message.dao_id)
            if not dao:
                return TweetProcessingResult(
                    success=False,
                    message=f"No DAO found for id: {message.dao_id}",
                    dao_id=message.dao_id,
                )

            token = backend.list_tokens(filters=TokenFilter(dao_id=message.dao_id))
            if not token:
                return TweetProcessingResult(
                    success=False,
                    message=f"No token found for DAO: {message.dao_id}",
                    dao_id=message.dao_id,
                )

            # Find matching DAO message
            matching_dao_message = self._find_matching_dao_message(
                token[0], dao_messages
            )
            if not matching_dao_message:
                return TweetProcessingResult(
                    success=False,
                    message=f"No matching DAO message found for dao_id: {message.dao_id}",
                    dao_id=message.dao_id,
                )

            result = await self._handle_tweet_response(
                message, dao, token[0], matching_dao_message
            )
            return result

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

    def _find_matching_dao_message(
        self, token: Any, dao_messages: list
    ) -> Optional[Any]:
        """Find matching DAO message based on token details."""
        for dao_message in dao_messages:
            if not isinstance(dao_message.message, dict):
                continue

            params = dao_message.message.get("parameters", {})
            if (
                params.get("token_symbol") == token.symbol
                and params.get("token_name") == token.name
                and params.get("token_max_supply") == token.max_supply
            ):
                logger.debug(
                    f"Found matching DAO message: {dao_message.id} for token {token.symbol}"
                )
                return dao_message
        return None

    async def _handle_tweet_response(
        self, message: Any, dao: Any, token: Any, dao_message: Any
    ) -> TweetProcessingResult:
        """Handle the tweet response generation and posting."""
        try:
            # Generate and post tweet
            generated_tweet = await generate_dao_tweet(
                dao_name=dao.name,
                dao_symbol=token.symbol,
                dao_mission=dao.mission,
                dao_id=dao.id,
            )

            logger.debug(
                f"Posting response for tweet_id: {dao_message.tweet_id}, "
                f"conversation_id: {dao_message.conversation_id}"
            )

            await self.twitter_handler._post_response(
                tweet_data=TweetData(
                    tweet_id=dao_message.tweet_id,
                    conversation_id=dao_message.conversation_id,
                ),
                response_content=generated_tweet["tweet_text"],
            )

            # Update author information
            await self._update_author_info(message, dao, dao_message)

            return TweetProcessingResult(
                success=True,
                message="Successfully processed tweet",
                tweet_id=dao_message.tweet_id,
                dao_id=dao.id,
            )

        except Exception as e:
            logger.error(
                f"Error handling tweet response for message {message.id}: {str(e)}",
                exc_info=True,
            )
            return TweetProcessingResult(
                success=False,
                message=f"Error handling tweet response: {str(e)}",
                error=e,
                dao_id=dao.id,
            )

    async def _update_author_info(
        self, message: Any, dao: Any, dao_message: Any
    ) -> None:
        """Update author information in the database."""
        tweet_info = backend.list_x_tweets(
            filters=XTweetFilter(tweet_id=dao_message.tweet_id)
        )
        if not tweet_info:
            logger.error(f"No tweet info found for tweet_id: {dao_message.tweet_id}")
            return

        author_id = tweet_info[0].author_id
        author_info = backend.get_x_user(author_id)
        if not author_info:
            logger.warning(f"No author info found for author_id: {author_id}")
            return

        # Update DAO with author
        backend.update_dao(
            dao_id=dao.id,
            update_data=DAOBase(author_id=author_id),
        )

        # Update user info if available
        user = await self.twitter_handler.twitter_service.get_user_by_user_id(
            author_info.user_id
        )
        if user:
            logger.debug(f"Updating user info for: {user.username}")
            backend.update_x_user(
                x_user_id=author_info.id,
                update_data=XUserBase(
                    name=user.name,
                    username=user.username,
                    description=user.description,
                    location=user.location,
                    profile_image_url=user.profile_image_url,
                    profile_banner_url=user.profile_banner_url,
                    protected=user.protected,
                    verified=user.verified,
                    verified_type=user.verified_type,
                    subscription_type=user.subscription_type,
                ),
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

            # Get processed DAO messages
            dao_messages = backend.list_queue_messages(
                filters=QueueMessageFilter(type="daos", is_processed=True)
            )
            logger.debug(f"Found {len(dao_messages)} processed DAO messages")

            for message in queue_messages:
                logger.info(f"Processing tweet message: {message}")
                result = await self._process_tweet_message(message, dao_messages)
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
