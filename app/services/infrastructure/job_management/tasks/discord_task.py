from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

from app.backend.factory import backend
from app.backend.models import (
    QueueMessage,
    QueueMessageBase,
    QueueMessageFilter,
    QueueMessageType,
)
from app.config import config
from app.lib.logger import configure_logger
from app.services.communication.discord.discord_factory import create_discord_service
from app.services.infrastructure.job_management.base import (
    BaseTask,
    JobContext,
    RunnerConfig,
    RunnerResult,
)
from app.services.infrastructure.job_management.decorators import JobPriority, job

logger = configure_logger(__name__)


@dataclass
class DiscordProcessingResult(RunnerResult):
    """Result of Discord message processing operation."""

    queue_message_id: Optional[UUID] = None
    dao_id: Optional[UUID] = None
    messages_sent: int = 0
    webhook_url_used: Optional[str] = None


@job(
    job_type="discord",
    name="Discord Message Sender",
    description="Sends Discord messages from queue with webhook support and enhanced error handling",
    interval_seconds=20,
    priority=JobPriority.MEDIUM,
    max_retries=3,
    retry_delay_seconds=30,
    timeout_seconds=120,
    max_concurrent=1,
    requires_discord=True,
    batch_size=10,
    enable_dead_letter_queue=True,
)
class DiscordTask(BaseTask[DiscordProcessingResult]):
    """Task for sending Discord messages from the queue with enhanced capabilities."""

    def __init__(self, config: Optional[RunnerConfig] = None):
        super().__init__(config)
        self._pending_messages: Optional[List[QueueMessage]] = None
        self._discord_services: dict[str, object] = {}

    async def _validate_config(self, context: JobContext) -> bool:
        """Validate task configuration."""
        try:
            # Check if at least one webhook URL is configured
            if (
                not config.discord.webhook_url_passed
                and not config.discord.webhook_url_failed
                and not config.discord.webhook_url_veto
            ):
                logger.error(
                    "No Discord webhook URLs configured", extra={"task": "discord"}
                )
                return False
            return True
        except Exception as e:
            logger.error(
                "Error validating Discord config",
                extra={"task": "discord", "error": str(e)},
                exc_info=True,
            )
            return False

    async def _validate_resources(self, context: JobContext) -> bool:
        """Validate resource availability."""
        try:
            # Test Discord service creation
            test_webhook = (
                config.discord.webhook_url_passed or config.discord.webhook_url_failed
            )
            discord_service = create_discord_service(webhook_url=test_webhook)
            if not discord_service:
                logger.error("Cannot create Discord service", extra={"task": "discord"})
                return False
            return True
        except Exception as e:
            logger.error(
                "Discord resource validation failed",
                extra={"task": "discord", "error": str(e)},
            )
            return False

    async def _validate_prerequisites(self, context: JobContext) -> bool:
        """Validate task prerequisites."""
        try:
            self._pending_messages = backend.list_queue_messages(
                filters=QueueMessageFilter(
                    type=QueueMessageType.get_or_create("discord"), is_processed=False
                )
            )
            return True
        except Exception as e:
            logger.error(
                "Error validating Discord prerequisites",
                extra={"task": "discord", "error": str(e)},
                exc_info=True,
            )
            self._pending_messages = None
            return False

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate task-specific conditions."""
        if not self._pending_messages:
            logger.debug("No pending Discord messages found", extra={"task": "discord"})
            return False

        # Validate each message has required content
        valid_messages = []
        for message in self._pending_messages:
            if await self._is_message_valid(message):
                valid_messages.append(message)

        self._pending_messages = valid_messages

        if valid_messages:
            logger.debug(
                "Found valid Discord messages",
                extra={"task": "discord", "valid_message_count": len(valid_messages)},
            )
            return True

        logger.debug("No valid Discord messages to process", extra={"task": "discord"})
        return False

    async def _is_message_valid(self, message: QueueMessage) -> bool:
        """Check if a Discord message is valid for processing."""
        try:
            if not message.message or not isinstance(message.message, dict):
                logger.debug(
                    "Message invalid: message field is not a dict",
                    extra={"task": "discord", "message_id": message.id},
                )
                return False

            content = message.message.get("content")
            if not content or not str(content).strip():
                logger.debug(
                    "Message invalid: content field is empty",
                    extra={"task": "discord", "message_id": message.id},
                )
                return False

            # Check for required Discord message structure
            # Content should be a string
            if not isinstance(content, str):
                logger.debug(
                    "Message invalid: content is not a string",
                    extra={"task": "discord", "message_id": message.id},
                )
                return False

            # Optional fields should have correct types if present
            embeds = message.message.get("embeds")
            if embeds is not None and not isinstance(embeds, list):
                logger.debug(
                    "Message invalid: embeds is not a list",
                    extra={"task": "discord", "message_id": message.id},
                )
                return False

            tts = message.message.get("tts")
            if tts is not None and not isinstance(tts, bool):
                logger.debug(
                    "Message invalid: tts is not a boolean",
                    extra={"task": "discord", "message_id": message.id},
                )
                return False

            proposal_status = message.message.get("proposal_status")
            if proposal_status is not None and not isinstance(proposal_status, str):
                logger.debug(
                    "Message invalid: proposal_status is not a string",
                    extra={"task": "discord", "message_id": message.id},
                )
                return False

            return True
        except Exception as e:
            logger.debug(
                "Message validation error",
                extra={"task": "discord", "message_id": message.id, "error": str(e)},
            )
            return False

    def _get_webhook_url(self, message: QueueMessage) -> str:
        """Get the appropriate webhook URL for the message."""
        # Allow message-level webhook override
        webhook_url = message.message.get("webhook_url")
        if webhook_url:
            return webhook_url

        # Select based on proposal status
        proposal_status = message.message.get("proposal_status")
        if proposal_status == "passed":
            return config.discord.webhook_url_passed
        elif proposal_status == "failed":
            return config.discord.webhook_url_failed
        elif proposal_status in ["veto_window_open", "veto_window_closed"]:
            return config.discord.webhook_url_veto
        else:
            # Default to passed webhook for backwards compatibility
            return config.discord.webhook_url_passed

    def _get_discord_service(self, webhook_url: str):
        """Get or create Discord service with caching."""
        if webhook_url in self._discord_services:
            return self._discord_services[webhook_url]

        discord_service = create_discord_service(webhook_url=webhook_url)
        if discord_service:
            self._discord_services[webhook_url] = discord_service

        return discord_service

    async def _process_discord_message(
        self, message: QueueMessage
    ) -> DiscordProcessingResult:
        """Process a single Discord queue message with enhanced error handling."""
        try:
            # Extract content and optional parameters from message.message
            if not message.message:
                logger.warning(
                    "Discord message has empty message field",
                    extra={"task": "discord", "message_id": message.id},
                )
                return DiscordProcessingResult(
                    success=False,
                    message="Discord message is empty",
                    queue_message_id=message.id,
                    dao_id=message.dao_id,
                )

            if not isinstance(message.message, dict):
                logger.warning(
                    "Discord message field is not a dict",
                    extra={
                        "task": "discord",
                        "message_id": message.id,
                        "message_type": type(message.message).__name__,
                    },
                )
                return DiscordProcessingResult(
                    success=False,
                    message=f"Discord message format invalid: expected dict, got {type(message.message)}",
                    queue_message_id=message.id,
                    dao_id=message.dao_id,
                )

            content = message.message.get("content")
            embeds = message.message.get("embeds")
            tts = message.message.get("tts", False)

            # Validate content exists and is not empty
            if not content or not str(content).strip():
                logger.warning(
                    "Discord message has empty content field",
                    extra={"task": "discord", "message_id": message.id},
                )
                return DiscordProcessingResult(
                    success=False,
                    message="Discord message content is empty",
                    queue_message_id=message.id,
                    dao_id=message.dao_id,
                )

            # Get appropriate webhook URL
            webhook_url = self._get_webhook_url(message)
            if not webhook_url:
                return DiscordProcessingResult(
                    success=False,
                    message="No webhook URL available for Discord message",
                    queue_message_id=message.id,
                    dao_id=message.dao_id,
                )

            # Get Discord service
            discord_service = self._get_discord_service(webhook_url)
            if not discord_service:
                return DiscordProcessingResult(
                    success=False,
                    message="Failed to initialize Discord service",
                    queue_message_id=message.id,
                    dao_id=message.dao_id,
                )

            logger.info(
                "Sending Discord message",
                extra={"task": "discord", "queue_id": message.id},
            )
            logger.debug(
                "Discord message content",
                extra={
                    "task": "discord",
                    "content_preview": content[:100] + "..."
                    if content and len(content) > 100
                    else content or "No content",
                },
            )
            logger.debug(
                "Discord message proposal status",
                extra={
                    "task": "discord",
                    "proposal_status": message.message.get("proposal_status", "none"),
                },
            )
            logger.debug(
                "Discord webhook URL used",
                extra={"task": "discord", "webhook_url": webhook_url},
            )

            # Send the message
            result = discord_service.send_message(content, embeds=embeds, tts=tts)

            if result.get("success"):
                logger.info(
                    "Successfully sent Discord message",
                    extra={"task": "discord", "queue_id": message.id},
                )
                return DiscordProcessingResult(
                    success=True,
                    message="Successfully sent Discord message",
                    queue_message_id=message.id,
                    dao_id=message.dao_id,
                    messages_sent=1,
                    webhook_url_used=webhook_url,
                )
            else:
                logger.error(
                    "Failed to send Discord message",
                    extra={"task": "discord", "result": str(result)},
                )
                return DiscordProcessingResult(
                    success=False,
                    message=f"Failed to send Discord message: {result}",
                    queue_message_id=message.id,
                    dao_id=message.dao_id,
                )

        except Exception as e:
            logger.error(
                "Error processing Discord message",
                extra={"task": "discord", "message_id": message.id, "error": str(e)},
                exc_info=True,
            )
            return DiscordProcessingResult(
                success=False,
                message=f"Error sending Discord message: {str(e)}",
                error=e,
                queue_message_id=message.id,
                dao_id=message.dao_id,
            )

    def _should_retry_on_error(self, error: Exception, context: JobContext) -> bool:
        """Determine if error should trigger retry."""
        # Retry on network errors, API timeouts, webhook issues
        retry_errors = (
            ConnectionError,
            TimeoutError,
        )

        # Don't retry on configuration errors
        if "webhook" in str(error).lower() and "not configured" in str(error).lower():
            return False

        return isinstance(error, retry_errors)

    async def _handle_execution_error(
        self, error: Exception, context: JobContext
    ) -> Optional[List[DiscordProcessingResult]]:
        """Handle execution errors with recovery logic."""
        if "webhook" in str(error).lower() or "discord" in str(error).lower():
            logger.warning(
                "Discord service error, will retry",
                extra={"task": "discord", "error": str(error)},
            )
            return None

        if isinstance(error, (ConnectionError, TimeoutError)):
            logger.warning(
                "Network error, will retry",
                extra={"task": "discord", "error": str(error)},
            )
            return None

        # For configuration errors, don't retry
        return [
            DiscordProcessingResult(
                success=False,
                message=f"Unrecoverable error: {str(error)}",
                error=error,
            )
        ]

    async def _post_execution_cleanup(
        self, context: JobContext, results: List[DiscordProcessingResult]
    ) -> None:
        """Cleanup after task execution."""
        # Clear cached pending messages
        self._pending_messages = None

        # Keep Discord services cached for reuse
        logger.debug(
            "Discord task cleanup completed",
            extra={
                "task": "discord",
                "cached_services_count": len(self._discord_services),
            },
        )

    async def _execute_impl(self, context: JobContext) -> List[DiscordProcessingResult]:
        """Execute Discord message sending task with batch processing."""
        results: List[DiscordProcessingResult] = []

        if not self._pending_messages:
            logger.debug(
                "No pending Discord messages to process", extra={"task": "discord"}
            )
            return results

        processed_count = 0
        success_count = 0
        batch_size = getattr(context, "batch_size", 10)

        # Process messages in batches
        for i in range(0, len(self._pending_messages), batch_size):
            batch = self._pending_messages[i : i + batch_size]

            for message in batch:
                logger.debug(
                    "Processing Discord message",
                    extra={"task": "discord", "message_id": message.id},
                )
                result = await self._process_discord_message(message)
                results.append(result)
                processed_count += 1

                if result.success:
                    success_count += 1
                    # Mark message as processed with result
                    result_dict = {
                        "success": result.success,
                        "message": result.message,
                        "queue_message_id": (
                            str(result.queue_message_id)
                            if result.queue_message_id
                            else None
                        ),
                        "dao_id": str(result.dao_id) if result.dao_id else None,
                        "messages_sent": result.messages_sent,
                        "webhook_url_used": result.webhook_url_used,
                        "error": str(result.error) if result.error else None,
                    }
                    backend.update_queue_message(
                        queue_message_id=message.id,
                        update_data=QueueMessageBase(
                            is_processed=True, result=result_dict
                        ),
                    )
                    logger.debug(
                        "Marked Discord message as processed with result",
                        extra={"task": "discord", "message_id": message.id},
                    )
                else:
                    # Store result for failed processing
                    result_dict = {
                        "success": result.success,
                        "message": result.message,
                        "queue_message_id": (
                            str(result.queue_message_id)
                            if result.queue_message_id
                            else None
                        ),
                        "dao_id": str(result.dao_id) if result.dao_id else None,
                        "messages_sent": result.messages_sent,
                        "webhook_url_used": result.webhook_url_used,
                        "error": str(result.error) if result.error else None,
                    }
                    backend.update_queue_message(
                        queue_message_id=message.id,
                        update_data=QueueMessageBase(result=result_dict),
                    )
                    logger.debug(
                        "Stored result for failed Discord message",
                        extra={"task": "discord", "message_id": message.id},
                    )

        logger.info(
            "Discord task completed",
            extra={
                "task": "discord",
                "processed_count": processed_count,
                "successful_count": success_count,
                "failed_count": processed_count - success_count,
            },
        )

        return results


# Create instance for auto-registration
discord_task = DiscordTask()
