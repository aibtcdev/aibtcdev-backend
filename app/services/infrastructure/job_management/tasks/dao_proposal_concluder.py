"""DAO proposal conclusion task implementation."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.backend.factory import backend
from app.backend.models import (
    QueueMessage,
    QueueMessageBase,
    QueueMessageFilter,
    QueueMessageType,
    TokenFilter,
)
from app.config import config
from app.lib.logger import configure_logger
from app.services.infrastructure.job_management.base import (
    BaseTask,
    JobContext,
    RunnerResult,
)
from app.services.infrastructure.job_management.decorators import JobPriority, job
from app.tools.dao_ext_action_proposals import ConcludeActionProposalTool

logger = configure_logger(__name__)


@dataclass
class DAOProposalConcludeResult(RunnerResult):
    """Result of DAO proposal conclusion operation."""

    proposals_processed: int = 0
    proposals_concluded: int = 0
    conclusions_successful: int = 0
    errors: List[str] = None

    def __post_init__(self):
        self.errors = self.errors or []


@job(
    job_type="dao_proposal_conclude",
    name="DAO Proposal Concluder",
    description="Processes and concludes DAO proposals with enhanced monitoring and error handling",
    interval_seconds=60,
    priority=JobPriority.MEDIUM,
    max_retries=2,
    retry_delay_seconds=90,
    timeout_seconds=240,
    max_concurrent=1,
    requires_blockchain=True,
    batch_size=2,
    enable_dead_letter_queue=True,
)
class DAOProposalConcluderTask(BaseTask[DAOProposalConcludeResult]):
    """Task runner for processing and concluding DAO proposals with enhanced capabilities."""

    QUEUE_TYPE = QueueMessageType.get_or_create("dao_proposal_conclude")
    MAX_MESSAGE_RETRIES = 3

    async def _validate_config(self, context: JobContext) -> bool:
        """Validate task configuration."""
        try:
            # Check if backend wallet configuration is available
            if not config.backend_wallet or not config.backend_wallet.seed_phrase:
                logger.error(
                    "Backend wallet seed phrase not configured",
                    extra={"task": "dao_proposal_conclude", "validation": "config"},
                )
                return False
            return True
        except Exception as e:
            logger.error(
                "Config validation failed",
                extra={"task": "dao_proposal_conclude", "error": str(e)},
                exc_info=True,
            )
            return False

    async def _validate_resources(self, context: JobContext) -> bool:
        """Validate resource availability."""
        try:
            return True
        except Exception as e:
            logger.error(
                "Resource validation failed",
                extra={"task": "dao_proposal_conclude", "error": str(e)},
            )
            return False

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate task-specific conditions."""
        try:
            # Get pending messages from the queue
            pending_messages = await self.get_pending_messages()
            message_count = len(pending_messages)
            logger.debug(
                "Found pending proposal conclusion messages",
                extra={"task": "dao_proposal_conclude", "message_count": message_count},
            )

            if message_count == 0:
                logger.debug(
                    "No pending messages found", extra={"task": "dao_proposal_conclude"}
                )
                return False

            # Validate each message has valid proposal data
            valid_messages = []
            for message in pending_messages:
                if await self._is_message_valid(message):
                    valid_messages.append(message)

            if valid_messages:
                logger.debug(
                    "Found valid messages",
                    extra={
                        "task": "dao_proposal_conclude",
                        "valid_count": len(valid_messages),
                    },
                )
                return True

            logger.warning(
                "No valid proposals found in pending messages",
                extra={"task": "dao_proposal_conclude"},
            )
            return False

        except Exception as e:
            logger.error(
                "Error validating task",
                extra={"task": "dao_proposal_conclude", "error": str(e)},
                exc_info=True,
            )
            return False

    async def _is_message_valid(self, message: QueueMessage) -> bool:
        """Check if a proposal conclusion message is valid for processing."""
        try:
            if not message.message or not message.dao_id:
                return False

            proposal_id = message.message.get("proposal_id")
            if not proposal_id:
                return False

            # Check if the proposal exists in the database
            proposal = backend.get_proposal(proposal_id)
            if not proposal:
                return False

            return True
        except Exception:
            return False

    async def _process_message(self, message: QueueMessage) -> Dict[str, Any]:
        """Process a single DAO proposal conclusion message with enhanced error handling."""
        message_id = message.id
        message_data = message.message or {}
        dao_id = message.dao_id

        logger.debug(
            "Processing proposal conclusion message",
            extra={"task": "dao_proposal_conclude", "message_id": message_id},
        )

        # Get the proposal ID from the message
        proposal_id = message_data.get("proposal_id")
        if not proposal_id:
            error_msg = f"Missing proposal_id in message {message_id}"
            logger.error(
                "Missing proposal_id in message",
                extra={"task": "dao_proposal_conclude", "message_id": message_id},
            )
            return {"success": False, "error": error_msg}

        try:
            # Get the proposal details from the database
            proposal = backend.get_proposal(proposal_id)
            if not proposal:
                error_msg = f"Proposal {proposal_id} not found in database"
                logger.error(
                    "Proposal not found in database",
                    extra={"task": "dao_proposal_conclude", "proposal_id": proposal_id},
                )
                return {"success": False, "error": error_msg}

            # Get the DAO information
            dao = backend.get_dao(dao_id) if dao_id else None
            if not dao:
                error_msg = f"DAO not found for proposal {proposal_id}"
                logger.error(
                    "DAO not found for proposal",
                    extra={"task": "dao_proposal_conclude", "proposal_id": proposal_id},
                )
                return {"success": False, "error": error_msg}

            # Get the DAO token information
            tokens = backend.list_tokens(filters=TokenFilter(dao_id=dao_id))
            if not tokens:
                error_msg = f"No token found for DAO: {dao_id}"
                logger.error(
                    "No token found for DAO",
                    extra={"task": "dao_proposal_conclude", "dao_id": str(dao_id)},
                )
                return {"success": False, "error": error_msg}

            # Use the first token as the DAO token
            dao_token = tokens[0]

            logger.info(
                "Preparing to conclude proposal",
                extra={
                    "task": "dao_proposal_conclude",
                    "proposal_id": proposal.proposal_id,
                    "dao_name": dao.name,
                },
            )

            # Initialize the ConcludeActionProposalTool
            conclude_tool = ConcludeActionProposalTool(
                seed_phrase=config.backend_wallet.seed_phrase
            )

            # Execute the conclusion
            logger.debug(
                "Executing conclusion", extra={"task": "dao_proposal_conclude"}
            )
            conclusion_result = await conclude_tool._arun(
                action_proposals_voting_extension=proposal.contract_principal,  # This is the voting extension contract
                proposal_id=proposal.proposal_id,  # This is the on-chain proposal ID
                action_proposal_contract_to_execute=proposal.action,  # This is the contract that will be executed
                dao_token_contract_address=dao_token.contract_principal,  # This is the DAO token contract
            )
            logger.debug(
                "Conclusion result",
                extra={
                    "task": "dao_proposal_conclude",
                    "success": conclusion_result.get("success"),
                    "has_result": bool(conclusion_result),
                },
            )

            from app.lib.utils import extract_transaction_id_from_tool_result

            if conclusion_result.get("success", False):
                tx_id = extract_transaction_id_from_tool_result(conclusion_result)
                if not tx_id:
                    result = {
                        "success": False,
                        "error": "No transaction ID in tool result",
                    }
                else:
                    result = {
                        "success": True,
                        "concluded": True,
                        "result": conclusion_result,
                        "tx_id": tx_id,
                    }
                    logger.info(
                        "Successfully concluded proposal",
                        extra={
                            "task": "dao_proposal_conclude",
                            "proposal_id": proposal.proposal_id,
                        },
                    )
            else:
                error_msg = conclusion_result.get("message", "Tool execution failed")
                result = {"success": False, "error": error_msg}
                logger.error(
                    "Failed to conclude proposal",
                    extra={
                        "task": "dao_proposal_conclude",
                        "proposal_id": proposal.proposal_id,
                        "error": error_msg,
                    },
                )

            # Handle retries for failure cases
            current_retries = (
                message.result.get("retry_count", 0) if message.result else 0
            )
            if not result["success"]:
                current_retries += 1
                result["retry_count"] = current_retries
                if current_retries >= self.MAX_MESSAGE_RETRIES:
                    result["final_status"] = "failed_after_retries"
                    update_data = QueueMessageBase(is_processed=True, result=result)
                    backend.update_queue_message(message_id, update_data)
                    logger.error(
                        "Message failed after max retries - marking as processed",
                        extra={
                            "task": "dao_proposal_conclude",
                            "message_id": message_id,
                            "retry_count": current_retries,
                        },
                    )
                else:
                    update_data = QueueMessageBase(result=result)
                    backend.update_queue_message(message_id, update_data)
                    logger.warning(
                        "Message processing failed - incrementing retry count",
                        extra={
                            "task": "dao_proposal_conclude",
                            "message_id": message_id,
                            "retry_count": current_retries,
                        },
                    )
            else:
                # For success, include retry_count reset if needed
                result["retry_count"] = 0
                update_data = QueueMessageBase(is_processed=True, result=result)
                backend.update_queue_message(message_id, update_data)

            return result

        except Exception as e:
            error_msg = f"Error processing message {message_id}: {str(e)}"
            logger.error(
                "Error processing message",
                extra={
                    "task": "dao_proposal_conclude",
                    "message_id": message_id,
                    "error": str(e),
                },
                exc_info=True,
            )
            result = {"success": False, "error": error_msg}

            # Handle retries for exception case
            current_retries = (
                message.result.get("retry_count", 0) if message.result else 0
            )
            current_retries += 1
            result["retry_count"] = current_retries
            if current_retries >= self.MAX_MESSAGE_RETRIES:
                result["final_status"] = "failed_after_retries"
                update_data = QueueMessageBase(is_processed=True, result=result)
                backend.update_queue_message(message_id, update_data)
                logger.error(
                    "Message failed after max retries - marking as processed",
                    extra={
                        "task": "dao_proposal_conclude",
                        "message_id": message_id,
                        "retry_count": current_retries,
                    },
                )
            else:
                update_data = QueueMessageBase(result=result)
                backend.update_queue_message(message_id, update_data)
                logger.warning(
                    "Message processing failed - incrementing retry count",
                    extra={
                        "task": "dao_proposal_conclude",
                        "message_id": message_id,
                        "retry_count": current_retries,
                    },
                )

            return result

    async def get_pending_messages(self) -> List[QueueMessage]:
        """Get all unprocessed messages from the queue."""
        filters = QueueMessageFilter(type=self.QUEUE_TYPE, is_processed=False)
        return backend.list_queue_messages(filters=filters)

    def _should_retry_on_error(self, error: Exception, context: JobContext) -> bool:
        """Determine if error should trigger retry."""
        # Retry on network errors, blockchain timeouts
        retry_errors = (
            ConnectionError,
            TimeoutError,
        )

        # Don't retry on validation errors
        if "not found" in str(error).lower():
            return False
        if "missing" in str(error).lower() and "proposal_id" in str(error).lower():
            return False

        return isinstance(error, retry_errors)

    async def _handle_execution_error(
        self, error: Exception, context: JobContext
    ) -> Optional[List[DAOProposalConcludeResult]]:
        """Handle execution errors with recovery logic."""
        if "blockchain" in str(error).lower() or "contract" in str(error).lower():
            logger.warning(
                "Blockchain/contract error, will retry",
                extra={"task": "dao_proposal_conclude", "error": str(error)},
            )
            return None

        if isinstance(error, (ConnectionError, TimeoutError)):
            logger.warning(
                "Network error, will retry",
                extra={"task": "dao_proposal_conclude", "error": str(error)},
            )
            return None

        # For validation errors, don't retry
        return [
            DAOProposalConcludeResult(
                success=False,
                message=f"Unrecoverable error: {str(error)}",
                error=error,
            )
        ]

    async def _post_execution_cleanup(
        self, context: JobContext, results: List[DAOProposalConcludeResult]
    ) -> None:
        """Cleanup after task execution."""
        logger.debug("Task cleanup completed", extra={"task": "dao_proposal_conclude"})

    async def _execute_impl(
        self, context: JobContext
    ) -> List[DAOProposalConcludeResult]:
        """Run the DAO proposal conclusion task with batch processing."""
        pending_messages = await self.get_pending_messages()
        message_count = len(pending_messages)
        logger.debug(f"Found {message_count} pending proposal conclusion messages")

        if not pending_messages:
            return [
                DAOProposalConcludeResult(
                    success=True,
                    message="No pending messages found",
                    proposals_processed=0,
                    proposals_concluded=0,
                )
            ]

        # Process each message
        processed_count = 0
        concluded_count = 0
        successful_conclusions = 0
        errors = []
        batch_size = getattr(context, "batch_size", 2)

        # Process messages in batches
        for i in range(0, len(pending_messages), batch_size):
            batch = pending_messages[i : i + batch_size]

            for message in batch:
                try:
                    result = await self._process_message(message)
                    processed_count += 1

                    if result.get("success"):
                        if result.get("concluded", False):
                            concluded_count += 1
                            successful_conclusions += 1
                    else:
                        errors.append(result.get("error", "Unknown error"))

                except Exception as e:
                    error_msg = f"Exception processing message {message.id}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(
                        "Exception processing message",
                        extra={
                            "task": "dao_proposal_conclude",
                            "message_id": str(message.id),
                            "error": str(e),
                        },
                        exc_info=True,
                    )

        logger.info(
            "DAO proposal concluder task completed",
            extra={
                "task": "dao_proposal_conclude",
                "processed": processed_count,
                "concluded": concluded_count,
                "errors": len(errors),
            },
        )

        return [
            DAOProposalConcludeResult(
                success=True,
                message=f"Processed {processed_count} proposal(s), concluded {concluded_count} proposal(s)",
                proposals_processed=processed_count,
                proposals_concluded=concluded_count,
                conclusions_successful=successful_conclusions,
                errors=errors,
            )
        ]


# Create instance for auto-registration
dao_proposal_concluder = DAOProposalConcluderTask()
