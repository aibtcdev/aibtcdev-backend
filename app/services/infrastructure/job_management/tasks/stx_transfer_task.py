"""STX transfer task implementation."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.backend.factory import backend
from app.backend.models import (
    QueueMessage,
    QueueMessageBase,
    QueueMessageFilter,
    QueueMessageType,
)
from app.config import config
from app.lib.logger import configure_logger
from app.services.infrastructure.job_management.base import (
    BaseTask,
    JobContext,
    RunnerConfig,
    RunnerResult,
)
from app.services.infrastructure.job_management.decorators import JobPriority, job
from app.tools.wallet import WalletSendSTX

logger = configure_logger(__name__)


@dataclass
class STXTransferResult(RunnerResult):
    """Result of STX transfer operation."""

    transfers_processed: int = 0
    transfers_successful: int = 0
    total_amount_sent: int = 0
    errors: List[str] = None

    def __post_init__(self):
        self.errors = self.errors or []


@job(
    job_type="stx_transfer",
    name="STX Transfer Processor",
    description="Processes STX transfer requests from queue with enhanced monitoring and error handling",
    interval_seconds=30,  # Check every 30 seconds
    priority=JobPriority.HIGH,
    max_retries=3,
    retry_delay_seconds=60,
    timeout_seconds=180,
    max_concurrent=1,
    requires_blockchain=True,
    batch_size=5,
    enable_dead_letter_queue=True,
)
class STXTransferTask(BaseTask[STXTransferResult]):
    """Task runner for processing STX transfers with enhanced capabilities."""

    QUEUE_TYPE = QueueMessageType.get_or_create("stx_transfer")

    def __init__(self, config: Optional[RunnerConfig] = None):
        super().__init__(config)

    async def _validate_config(self, context: JobContext) -> bool:
        """Validate task configuration."""
        try:
            # Check if backend wallet seed phrase is configured for cases where wallet_id is None
            if not config.backend_wallet.seed_phrase:
                logger.warning(
                    "Backend wallet seed phrase not configured - transfers with wallet_id=None will fail"
                )
            return True
        except Exception as e:
            logger.error(
                f"Error validating STX transfer config: {str(e)}", exc_info=True
            )
            return False

    async def _validate_resources(self, context: JobContext) -> bool:
        """Validate resource availability."""
        try:
            # Test that we can initialize the WalletSendSTX tool
            # We'll use a dummy wallet_id for testing - actual wallet_id comes from messages
            test_tool = WalletSendSTX(wallet_id=None)
            if not test_tool:
                logger.error("Cannot initialize WalletSendSTX tool")
                return False

            return True
        except Exception as e:
            logger.error(f"Resource validation failed: {str(e)}")
            return False

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate task-specific conditions."""
        try:
            # Get pending messages from the queue
            pending_messages = await self.get_pending_messages()
            message_count = len(pending_messages)
            logger.debug(f"Found {message_count} pending STX transfer messages")

            if message_count == 0:
                logger.debug("No pending STX transfer messages found")
                return False

            # Validate that at least one message has valid transfer data
            for message in pending_messages:
                if self._validate_message_data(message):
                    logger.debug("Found valid STX transfer message")
                    return True

            logger.warning("No valid transfer data found in pending messages")
            return False

        except Exception as e:
            logger.error(f"Error validating STX transfer task: {str(e)}", exc_info=True)
            return False

    def _validate_message_data(self, message: QueueMessage) -> bool:
        """Validate the message data contains required fields for STX transfer."""
        try:
            if not message.message or not isinstance(message.message, dict):
                return False

            # Check required fields
            required_fields = ["recipient", "amount"]
            for field in required_fields:
                if field not in message.message:
                    return False

            # Validate wallet_id is present OR we have backend wallet config for None case
            if not message.wallet_id and not config.backend_wallet.seed_phrase:
                return False

            # Validate recipient is a valid string
            recipient = message.message.get("recipient")
            if not isinstance(recipient, str) or not recipient.strip():
                return False

            # Validate amount is a positive integer
            amount = message.message.get("amount")
            if not isinstance(amount, int) or amount <= 0:
                return False

            return True
        except Exception:
            return False

    async def process_message(self, message: QueueMessage) -> Dict[str, Any]:
        """Process a single STX transfer message."""
        message_id = message.id
        message_data = message.message

        logger.debug(f"Processing STX transfer message {message_id}")

        try:
            # Validate message data
            if not self._validate_message_data(message):
                error_msg = f"Invalid message data in message {message_id}"
                logger.error(error_msg)
                result = {"success": False, "error": error_msg}

                # Store result and mark as processed
                update_data = QueueMessageBase(is_processed=True, result=result)
                backend.update_queue_message(message_id, update_data)
                return result

            # Extract transfer parameters
            recipient = message_data["recipient"]
            amount = message_data["amount"]
            fee = message_data.get("fee", 200)  # Default fee
            memo = message_data.get("memo", "")  # Default empty memo

            # Validate and truncate memo to ensure it doesn't exceed 34 bytes
            if memo:
                memo_bytes = memo.encode("utf-8")
                if len(memo_bytes) > 34:
                    # Truncate to fit within 34 bytes, preserving as much as possible
                    memo = memo_bytes[:31].decode("utf-8", errors="ignore") + "..."
                    logger.warning(
                        f"Memo truncated from {len(memo_bytes)} bytes to fit 34-byte limit: '{memo}'"
                    )

            wallet_id = message.wallet_id

            # If wallet_id is None, use backend wallet with seed phrase
            if wallet_id is None:
                if not config.backend_wallet.seed_phrase:
                    error_msg = "No wallet_id provided and backend wallet seed phrase not configured"
                    logger.error(error_msg)
                    result = {"success": False, "error": error_msg}
                    update_data = QueueMessageBase(is_processed=True, result=result)
                    backend.update_queue_message(message_id, update_data)
                    return result

                logger.debug(
                    f"Transfer parameters - Recipient: {recipient}, Amount: {amount} STX, "
                    f"Fee: {fee} microSTX, Using backend wallet (seed phrase)"
                )

                # Initialize the WalletSendSTX tool with seed phrase instead of wallet_id
                from app.tools.bun import BunScriptRunner

                send_tool = type(
                    "WalletSendSTXBackend",
                    (),
                    {
                        "_arun": lambda self,
                        recipient,
                        amount,
                        fee,
                        memo: BunScriptRunner.bun_run_with_seed_phrase(
                            config.backend_wallet.seed_phrase,
                            "stacks-wallet",
                            "transfer-my-stx.ts",
                            recipient,
                            str(amount),
                            str(fee),
                            memo or "",
                        )
                    },
                )()
            else:
                logger.debug(
                    f"Transfer parameters - Recipient: {recipient}, Amount: {amount} STX, "
                    f"Fee: {fee} microSTX, Wallet: {wallet_id}"
                )

                # Initialize the WalletSendSTX tool with the wallet_id
                send_tool = WalletSendSTX(wallet_id=wallet_id)

            # Execute the transfer
            logger.debug("Executing STX transfer...")
            transfer_result = send_tool._arun(
                recipient=recipient,
                amount=amount,
                fee=fee,
                memo=memo,
            )
            logger.debug(f"Transfer result: {transfer_result}")

            # Check if transfer was successful
            if transfer_result.get("success"):
                wallet_info = (
                    "backend wallet (seed phrase)"
                    if wallet_id is None
                    else f"wallet {wallet_id}"
                )
                logger.info(
                    f"Successfully sent {amount} STX to {recipient} from {wallet_info}"
                )
                result = {
                    "success": True,
                    "transferred": True,
                    "amount": amount,
                    "recipient": recipient,
                    "wallet_type": "backend" if wallet_id is None else "user",
                    "result": transfer_result,
                }
            else:
                error_msg = transfer_result.get("error", "Unknown transfer error")
                logger.error(f"STX transfer failed: {error_msg}")
                result = {
                    "success": False,
                    "error": error_msg,
                    "result": transfer_result,
                }

            # Store result and mark as processed
            update_data = QueueMessageBase(is_processed=True, result=result)
            backend.update_queue_message(message_id, update_data)

            return result

        except Exception as e:
            error_msg = f"Error processing message {message_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            result = {"success": False, "error": error_msg}

            # Store result even for failed processing
            update_data = QueueMessageBase(result=result)
            backend.update_queue_message(message_id, update_data)

            return result

    async def get_pending_messages(self) -> List[QueueMessage]:
        """Get all unprocessed messages from the queue."""
        filters = QueueMessageFilter(type=self.QUEUE_TYPE, is_processed=False)
        messages = backend.list_queue_messages(filters=filters)

        # Log messages for debugging
        for message in messages:
            logger.debug(f"Queue message raw data: {message.message!r}")

        return messages

    def _should_retry_on_error(self, error: Exception, context: JobContext) -> bool:
        """Determine if error should trigger retry."""
        # Retry on network errors, blockchain timeouts
        retry_errors = (
            ConnectionError,
            TimeoutError,
        )

        # Don't retry on validation errors
        if "invalid message data" in str(error).lower():
            return False
        if "missing" in str(error).lower() and "required" in str(error).lower():
            return False
        if "insufficient funds" in str(error).lower():
            return False

        return isinstance(error, retry_errors)

    async def _handle_execution_error(
        self, error: Exception, context: JobContext
    ) -> Optional[List[STXTransferResult]]:
        """Handle execution errors with recovery logic."""
        if "blockchain" in str(error).lower() or "stx" in str(error).lower():
            logger.warning(f"Blockchain/STX error: {str(error)}, will retry")
            return None

        if isinstance(error, (ConnectionError, TimeoutError)):
            logger.warning(f"Network error: {str(error)}, will retry")
            return None

        # For validation errors, don't retry
        return [
            STXTransferResult(
                success=False,
                message=f"Unrecoverable error: {str(error)}",
                error=error,
            )
        ]

    async def _post_execution_cleanup(
        self, context: JobContext, results: List[STXTransferResult]
    ) -> None:
        """Cleanup after task execution."""
        logger.debug("STX transfer task cleanup completed")

    async def _execute_impl(self, context: JobContext) -> List[STXTransferResult]:
        """Run the STX transfer task with batch processing."""
        pending_messages = await self.get_pending_messages()
        message_count = len(pending_messages)
        logger.debug(f"Found {message_count} pending STX transfer messages")

        if not pending_messages:
            return [
                STXTransferResult(
                    success=True,
                    message="No pending messages found",
                    transfers_processed=0,
                    transfers_successful=0,
                    total_amount_sent=0,
                )
            ]

        # Process each message in batches
        processed_count = 0
        successful_count = 0
        total_amount = 0
        errors = []
        batch_size = getattr(context, "batch_size", 5)

        logger.info(f"Processing {message_count} STX transfer messages")

        # Process messages in batches
        for i in range(0, len(pending_messages), batch_size):
            batch = pending_messages[i : i + batch_size]

            for message in batch:
                try:
                    result = await self.process_message(message)
                    processed_count += 1

                    if result.get("success"):
                        if result.get("transferred", False):
                            successful_count += 1
                            total_amount += result.get("amount", 0)
                    else:
                        errors.append(result.get("error", "Unknown error"))

                except Exception as e:
                    error_msg = f"Exception processing message {message.id}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg, exc_info=True)

        logger.info(
            f"STX transfer completed - Processed: {processed_count}, "
            f"Successful: {successful_count}, Total sent: {total_amount} STX, "
            f"Errors: {len(errors)}"
        )

        return [
            STXTransferResult(
                success=True,
                message=f"Processed {processed_count} transfer(s), sent {successful_count} transfer(s), total amount: {total_amount} STX",
                transfers_processed=processed_count,
                transfers_successful=successful_count,
                total_amount_sent=total_amount,
                errors=errors,
            )
        ]


# Create instance for auto-registration
stx_transfer_task = STXTransferTask()
