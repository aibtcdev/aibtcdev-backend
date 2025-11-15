from dataclasses import dataclass
from typing import Any, List, Optional
from uuid import UUID

from app.backend.factory import backend
from app.backend.models import (
    QueueMessageBase,
    QueueMessageCreate,
    QueueMessageFilter,
    QueueMessageType,
    TokenFilter,
)
from app.lib.logger import configure_logger
from app.services.ai.simple_workflows import generate_dao_tweet

from ..base import BaseTask, JobContext, RunnerConfig, RunnerResult
from ..decorators import JobPriority, job

logger = configure_logger(__name__)


@dataclass
class DAODeploymentTweetResult(RunnerResult):
    """Result of DAO deployment tweet processing operation."""

    dao_id: Optional[UUID] = None
    tweet_id: Optional[str] = None
    congratulatory_tweets_generated: int = 0
    tweet_messages_created: int = 0


@job(
    job_type="dao_deployment_tweet",
    name="DAO Deployment Tweet Generator",
    description="Generates congratulatory tweets for successfully deployed DAOs with enhanced monitoring and error handling",
    interval_seconds=45,
    priority=JobPriority.MEDIUM,
    max_retries=3,
    retry_delay_seconds=60,
    timeout_seconds=180,
    max_concurrent=1,
    requires_ai=True,
    batch_size=5,
    enable_dead_letter_queue=True,
)
class DAODeploymentTweetTask(BaseTask[DAODeploymentTweetResult]):
    """Task for generating congratulatory tweets for successfully deployed DAOs with enhanced capabilities."""

    def __init__(self, config: Optional[RunnerConfig] = None):
        super().__init__(config)
        self._pending_messages = None

    async def _validate_config(self, context: JobContext) -> bool:
        """Validate DAO deployment tweet task configuration."""
        try:
            # Check if generate_dao_tweet workflow is available for deployment congratulations
            return True
        except Exception as e:
            logger.error(
                "Error validating DAO deployment tweet task config",
                extra={"error": str(e)},
                exc_info=True,
            )
            return False

    async def _validate_resources(self, context: JobContext) -> bool:
        """Validate resource availability for DAO deployment tweet generation."""
        try:
            return True
        except Exception as e:
            logger.error(
                "Backend not available for DAO deployment tweets",
                extra={"error": str(e)},
            )
            return False

    async def _validate_prerequisites(self, context: JobContext) -> bool:
        """Validate DAO deployment tweet task prerequisites."""
        try:
            # Cache pending deployment tweet messages for later use
            self._pending_messages = backend.list_queue_messages(
                filters=QueueMessageFilter(
                    type=QueueMessageType.get_or_create("dao_deployment_tweet"),
                    is_processed=False,
                )
            )
            return True
        except Exception as e:
            logger.error(
                "Error validating DAO deployment tweet prerequisites",
                extra={"error": str(e)},
                exc_info=True,
            )
            self._pending_messages = None
            return False

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate DAO deployment tweet task-specific conditions."""
        try:
            if not self._pending_messages:
                logger.debug(
                    "No pending DAO deployment tweet messages found",
                )
                return False

            # Validate each message has valid deployed DAO data
            valid_messages = []
            for message in self._pending_messages:
                if await self._is_deployment_message_valid(message):
                    valid_messages.append(message)

            self._pending_messages = valid_messages

            if valid_messages:
                logger.debug(
                    "Found valid DAO deployment tweet messages",
                    extra={
                        "valid_message_count": len(valid_messages),
                    },
                )
                return True

            logger.debug(
                "No valid DAO deployment tweet messages to process",
            )
            return False

        except Exception as e:
            logger.error(
                "Error in DAO deployment tweet task validation",
                extra={"error": str(e)},
                exc_info=True,
            )
            return False

    async def _is_deployment_message_valid(self, message: Any) -> bool:
        """Check if a DAO deployment tweet message is valid for processing."""
        try:
            if not message.dao_id:
                return False

            # Validate DAO exists and is successfully deployed
            dao = backend.get_dao(message.dao_id)
            if not dao or not dao.is_deployed:
                return False

            # Validate token exists for the deployed DAO
            token = backend.list_tokens(filters=TokenFilter(dao_id=message.dao_id))
            if not token:
                return False

            return True
        except Exception:
            return False

    async def _validate_deployment_message(
        self, message: Any
    ) -> Optional[DAODeploymentTweetResult]:
        """Validate a single DAO deployment message before processing."""
        try:
            if not message.dao_id:
                return DAODeploymentTweetResult(
                    success=False,
                    message="DAO deployment message has no dao_id",
                    dao_id=None,
                )

            # Validate DAO exists and is successfully deployed
            dao = backend.get_dao(message.dao_id)
            if not dao:
                return DAODeploymentTweetResult(
                    success=False,
                    message=f"No DAO found for deployment tweet: {message.dao_id}",
                    dao_id=message.dao_id,
                )

            if not dao.is_deployed:
                return DAODeploymentTweetResult(
                    success=False,
                    message=f"DAO is not yet deployed, cannot tweet congratulations: {message.dao_id}",
                    dao_id=message.dao_id,
                )

            # Validate token exists for the deployed DAO
            token = backend.list_tokens(filters=TokenFilter(dao_id=message.dao_id))
            if not token:
                return DAODeploymentTweetResult(
                    success=False,
                    message=f"No token found for deployed DAO: {message.dao_id}",
                    dao_id=message.dao_id,
                )

            return None  # Validation passed

        except Exception as e:
            logger.error(
                "Error validating DAO deployment message",
                extra={
                    "message_id": message.id,
                    "error": str(e),
                },
                exc_info=True,
            )
            return DAODeploymentTweetResult(
                success=False,
                message=f"Error validating deployment message: {str(e)}",
                error=e,
                dao_id=message.dao_id if hasattr(message, "dao_id") else None,
            )

    async def _process_dao_deployment_message(
        self, message: Any
    ) -> DAODeploymentTweetResult:
        """Process a single DAO deployment message to generate congratulatory tweet."""
        try:
            # Validate deployment message first
            validation_result = await self._validate_deployment_message(message)
            if validation_result:
                return validation_result

            # Get the validated deployed DAO and token info
            dao = backend.get_dao(message.dao_id)
            token = backend.list_tokens(filters=TokenFilter(dao_id=message.dao_id))[0]

            logger.info(
                "Generating congratulatory tweet for deployed DAO",
                extra={
                    "dao_name": dao.name,
                    "dao_id": dao.id,
                },
            )
            logger.debug(
                "Deployed DAO details",
                extra={
                    "symbol": token.symbol,
                    "mission_preview": dao.mission[:100] + "..."
                    if len(dao.mission) > 100
                    else dao.mission,
                },
            )

            # Generate congratulatory tweet for the deployment
            generated_congratulatory_tweet = await generate_dao_tweet(
                dao_name=dao.name,
                dao_symbol=token.symbol,
                dao_mission=dao.mission,
                dao_id=dao.id,
            )

            if (
                not generated_congratulatory_tweet
                or not generated_congratulatory_tweet.get("tweet_text")
            ):
                return DAODeploymentTweetResult(
                    success=False,
                    message="Failed to generate congratulatory tweet content for DAO deployment",
                    dao_id=dao.id,
                    tweet_id=message.tweet_id,
                )

            # Create a new congratulatory tweet message in the queue
            congratulatory_tweet_message = backend.create_queue_message(
                QueueMessageCreate(
                    type="tweet",
                    dao_id=dao.id,
                    message={"message": generated_congratulatory_tweet["tweet_text"]},
                    tweet_id=message.tweet_id,
                    conversation_id=message.conversation_id,
                )
            )

            logger.info(
                "Created congratulatory tweet message for deployed DAO",
                extra={"dao_name": dao.name},
            )
            logger.debug(
                "Congratulatory tweet message ID",
                extra={
                    "tweet_message_id": congratulatory_tweet_message.id,
                },
            )
            logger.debug(
                "Generated congratulatory tweet content",
                extra={
                    "content_preview": generated_congratulatory_tweet["tweet_text"][
                        :100
                    ]
                    + "..."
                    if len(generated_congratulatory_tweet["tweet_text"]) > 100
                    else generated_congratulatory_tweet["tweet_text"],
                },
            )

            return DAODeploymentTweetResult(
                success=True,
                message="Successfully generated congratulatory tweet for DAO deployment",
                dao_id=dao.id,
                tweet_id=message.tweet_id,
                congratulatory_tweets_generated=1,
                tweet_messages_created=1,
            )

        except Exception as e:
            logger.error(
                "Error processing DAO deployment message",
                extra={
                    "message_id": message.id,
                    "error": str(e),
                },
                exc_info=True,
            )
            return DAODeploymentTweetResult(
                success=False,
                message=f"Error processing DAO deployment tweet: {str(e)}",
                error=e,
                dao_id=message.dao_id if hasattr(message, "dao_id") else None,
            )

    def _should_retry_on_error(self, error: Exception, context: JobContext) -> bool:
        """Determine if DAO deployment tweet error should trigger retry."""
        # Retry on network errors, AI service timeouts
        retry_errors = (
            ConnectionError,
            TimeoutError,
        )

        # Don't retry on DAO deployment validation errors
        if "DAO is not yet deployed" in str(error):
            return False
        if "No DAO found" in str(error):
            return False
        if "No token found for deployed DAO" in str(error):
            return False

        return isinstance(error, retry_errors)

    async def _handle_execution_error(
        self, error: Exception, context: JobContext
    ) -> Optional[List[DAODeploymentTweetResult]]:
        """Handle DAO deployment tweet execution errors with recovery logic."""
        if "ai" in str(error).lower() or "openai" in str(error).lower():
            logger.warning(
                "AI service error during congratulatory tweet generation, will retry",
                extra={"error": str(error)},
            )
            return None

        if isinstance(error, (ConnectionError, TimeoutError)):
            logger.warning(
                "Network error during DAO deployment tweet, will retry",
                extra={"error": str(error)},
            )
            return None

        # For DAO deployment validation errors, don't retry
        return [
            DAODeploymentTweetResult(
                success=False,
                message=f"Unrecoverable DAO deployment tweet error: {str(error)}",
                error=error,
            )
        ]

    async def _post_execution_cleanup(
        self, context: JobContext, results: List[DAODeploymentTweetResult]
    ) -> None:
        """Cleanup after DAO deployment tweet task execution."""
        # Clear cached pending messages
        self._pending_messages = None
        logger.debug(
            "DAO deployment tweet task cleanup completed",
        )

    async def _execute_impl(
        self, context: JobContext
    ) -> List[DAODeploymentTweetResult]:
        """Execute DAO deployment tweet processing task with batch processing."""
        results: List[DAODeploymentTweetResult] = []

        if not self._pending_messages:
            logger.debug(
                "No pending DAO deployment tweet messages to process",
            )
            return results

        processed_count = 0
        success_count = 0
        batch_size = getattr(context, "batch_size", 5)

        # Process deployment tweet messages in batches
        for i in range(0, len(self._pending_messages), batch_size):
            batch = self._pending_messages[i : i + batch_size]

            for message in batch:
                logger.debug(
                    "Processing DAO deployment tweet message",
                    extra={"message_id": message.id},
                )
                result = await self._process_dao_deployment_message(message)
                results.append(result)
                processed_count += 1

                if result.success:
                    success_count += 1
                    backend.update_queue_message(
                        queue_message_id=message.id,
                        update_data=QueueMessageBase(is_processed=True),
                    )
                    logger.debug(
                        "Marked DAO deployment tweet message as processed",
                        extra={
                            "message_id": message.id,
                        },
                    )

        logger.info(
            "DAO deployment tweet task completed",
            extra={
                "processed_count": processed_count,
                "successful_count": success_count,
                "failed_count": processed_count - success_count,
            },
        )

        return results


# Create instance for auto-registration
dao_deployment_tweet_task = DAODeploymentTweetTask()
