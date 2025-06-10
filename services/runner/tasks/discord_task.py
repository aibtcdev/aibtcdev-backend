from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

from backend.factory import backend
from backend.models import (
    QueueMessage,
    QueueMessageBase,
    QueueMessageFilter,
    QueueMessageType,
)
from lib.logger import configure_logger
from services.discord.discord_factory import create_discord_service
from services.runner.base import BaseTask, JobContext, RunnerConfig, RunnerResult
from config import config

logger = configure_logger(__name__)


@dataclass
class DiscordProcessingResult(RunnerResult):
    """Result of Discord message processing operation."""

    queue_message_id: Optional[UUID] = None
    dao_id: Optional[UUID] = None


class DiscordTask(BaseTask[DiscordProcessingResult]):
    """Task for sending Discord messages from the queue."""

    def __init__(self, config: Optional[RunnerConfig] = None):
        super().__init__(config)
        self._pending_messages: Optional[List[QueueMessage]] = None
        self.discord_service = None

    async def _validate_config(self, context: JobContext) -> bool:
        """Validate task configuration."""
        # No special config needed for Discord
        return True

    async def _validate_prerequisites(self, context: JobContext) -> bool:
        """Validate task prerequisites."""
        try:
            self._pending_messages = backend.list_queue_messages(
                filters=QueueMessageFilter(
                    type=QueueMessageType.DISCORD, is_processed=False
                )
            )
            return True
        except Exception as e:
            logger.error(
                f"Error validating Discord prerequisites: {str(e)}", exc_info=True
            )
            self._pending_messages = None
            return False

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate task-specific conditions."""
        if not self._pending_messages:
            logger.debug("No pending Discord messages found")
            return False
        logger.debug(f"Found {len(self._pending_messages)} pending Discord messages")
        return True

    async def _process_discord_message(
        self, message: QueueMessage
    ) -> DiscordProcessingResult:
        """Process a single Discord queue message."""
        try:
            # Extract content and optional embeds from message.message
            if not message.message:
                return DiscordProcessingResult(
                    success=False,
                    message="Discord message is empty",
                    queue_message_id=message.id,
                    dao_id=message.dao_id,
                )
            content = message.message.get("content")
            embeds = message.message.get("embeds")
            tts = message.message.get("tts", False)
            proposal_status = message.message.get("proposal_status")
            webhook_url = message.message.get("webhook_url")  # Allow override

            # Select appropriate webhook URL based on proposal status
            if not webhook_url:
                if proposal_status == "passed":
                    webhook_url = config.discord.webhook_url_passed
                elif proposal_status == "failed":
                    webhook_url = config.discord.webhook_url_failed
                else:
                    # Default to passed webhook for backwards compatibility
                    webhook_url = config.discord.webhook_url_passed

            discord_service = create_discord_service(webhook_url=webhook_url)
            if not discord_service:
                return DiscordProcessingResult(
                    success=False,
                    message="Failed to initialize Discord service",
                    queue_message_id=message.id,
                    dao_id=message.dao_id,
                )

            result = discord_service.send_message(content, embeds=embeds, tts=tts)
            if result.get("success"):
                logger.info(f"Successfully sent Discord message for queue {message.id}")
                return DiscordProcessingResult(
                    success=True,
                    message="Successfully sent Discord message",
                    queue_message_id=message.id,
                    dao_id=message.dao_id,
                )
            else:
                logger.error(f"Failed to send Discord message: {result}")
                return DiscordProcessingResult(
                    success=False,
                    message=f"Failed to send Discord message: {result}",
                    queue_message_id=message.id,
                    dao_id=message.dao_id,
                )
        except Exception as e:
            logger.error(
                f"Error processing Discord message {message.id}: {str(e)}",
                exc_info=True,
            )
            return DiscordProcessingResult(
                success=False,
                message=f"Error sending Discord message: {str(e)}",
                error=e,
                queue_message_id=message.id,
                dao_id=message.dao_id,
            )

    async def _execute_impl(self, context: JobContext) -> List[DiscordProcessingResult]:
        """Execute Discord message sending task."""
        results: List[DiscordProcessingResult] = []
        if not self._pending_messages:
            return results
        for message in self._pending_messages:
            logger.debug(f"Processing Discord message: {message.id}")
            result = await self._process_discord_message(message)
            results.append(result)
            if result.success:
                backend.update_queue_message(
                    queue_message_id=message.id,
                    update_data=QueueMessageBase(is_processed=True),
                )
                logger.debug(f"Marked Discord message {message.id} as processed")
        return results


discord_task = DiscordTask()
