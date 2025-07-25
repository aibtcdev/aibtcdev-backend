"""Agent account proposal approval task implementation."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.backend.factory import backend
from app.backend.models import (
    QueueMessage,
    QueueMessageBase,
    QueueMessageFilter,
    QueueMessageType,
)
from app.lib.logger import configure_logger
from app.services.infrastructure.job_management.base import (
    BaseTask,
    JobContext,
    RunnerConfig,
    RunnerResult,
)
from app.services.infrastructure.job_management.decorators import JobPriority, job
from app.tools.agent_account_configuration import AgentAccountApproveContractTool
from app.tools.agent_account_asset_management import AgentAccountIsApprovedContractTool

logger = configure_logger(__name__)


@dataclass
class AgentAccountProposalApprovalResult(RunnerResult):
    """Result of agent account proposal approval operation."""

    approvals_processed: int = 0
    approvals_successful: int = 0
    approvals_skipped: int = 0
    errors: List[str] = None

    def __post_init__(self):
        self.errors = self.errors or []


@job(
    job_type="agent_account_proposal_approval",
    name="Agent Account Proposal Approval",
    description="Approves DAO proposal contracts for agent accounts to enable voting with enhanced monitoring and error handling",
    interval_seconds=30,  # Check every 30 seconds
    priority=JobPriority.MEDIUM,
    max_retries=2,
    retry_delay_seconds=60,
    timeout_seconds=120,
    max_concurrent=1,
    requires_blockchain=True,
    batch_size=3,
    enable_dead_letter_queue=True,
)
class AgentAccountProposalApprovalTask(BaseTask[AgentAccountProposalApprovalResult]):
    """Task runner for processing agent account proposal approvals with enhanced capabilities."""

    QUEUE_TYPE = QueueMessageType.get_or_create("agent_account_proposal_approval")

    def __init__(self, config: Optional[RunnerConfig] = None):
        super().__init__(config)

    async def _validate_config(self, context: JobContext) -> bool:
        """Validate task configuration."""
        try:
            # We need wallet IDs to initialize the approval tools
            return True
        except Exception as e:
            logger.error(
                f"Error validating agent account proposal approval config: {str(e)}",
                exc_info=True,
            )
            return False

    async def _validate_resources(self, context: JobContext) -> bool:
        """Validate resource availability."""
        try:
            # Test that backend is available
            if not backend:
                logger.error(
                    "Backend not available for agent account proposal approval"
                )
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
            logger.debug(f"Found {message_count} pending proposal approval messages")

            if message_count == 0:
                logger.debug("No pending proposal approval messages found")
                return False

            # Validate that at least one message has valid approval data
            for message in pending_messages:
                if self._validate_message_data(message):
                    logger.debug("Found valid proposal approval message")
                    return True

            logger.warning("No valid approval data found in pending messages")
            return False

        except Exception as e:
            logger.error(
                f"Error validating agent account proposal approval task: {str(e)}",
                exc_info=True,
            )
            return False

    def _validate_message_data(self, message: QueueMessage) -> bool:
        """Validate the message data contains required fields."""
        if not message.message or not isinstance(message.message, dict):
            return False

        required_fields = [
            "agent_account_contract",
            "contract_to_approve",
            "approval_type",
        ]

        message_data = message.message
        return all(
            field in message_data and message_data[field] for field in required_fields
        )

    async def _is_already_approved(
        self, message_data: Dict[str, Any], wallet_id: str
    ) -> bool:
        """Check if the contract is already approved to avoid duplicate approvals."""
        try:
            agent_account_contract = message_data["agent_account_contract"]
            contract_to_approve = message_data["contract_to_approve"]

            # Initialize the check tool
            check_tool = AgentAccountIsApprovedContractTool(wallet_id=wallet_id)

            # Check if already approved
            result = await check_tool._arun(
                agent_account_contract=agent_account_contract,
                contract_principal=contract_to_approve,
            )

            if result.get("success") and result.get("data"):
                # Parse the result to check if approved
                is_approved = result["data"].get("approved", False)
                if is_approved:
                    logger.info(
                        f"Contract {contract_to_approve} already approved for agent {agent_account_contract}"
                    )
                    return True

            return False

        except Exception as e:
            logger.warning(f"Could not check approval status: {str(e)}")
            # If we can't check, proceed with approval attempt
            return False

    async def process_message(self, message: QueueMessage) -> Dict[str, Any]:
        """Process a single agent account proposal approval message."""
        message_id = message.id
        message_data = message.message or {}

        logger.debug(f"Processing proposal approval message {message_id}")

        try:
            # Validate message data
            if not self._validate_message_data(message):
                error_msg = f"Invalid message data in message {message_id}"
                logger.error(error_msg)
                result = {"success": False, "error": error_msg, "skipped": False}

                # Store result and mark as processed
                update_data = QueueMessageBase(is_processed=True, result=result)
                backend.update_queue_message(message_id, update_data)
                return result

            agent_account_contract = message_data["agent_account_contract"]
            contract_to_approve = message_data["contract_to_approve"]
            approval_type = message_data["approval_type"]
            wallet_id = message.wallet_id

            logger.info(
                f"Processing approval for agent {agent_account_contract} "
                f"to approve {contract_to_approve} with type {approval_type}"
            )

            # Check if already approved
            if await self._is_already_approved(message_data, wallet_id):
                result = {
                    "success": True,
                    "skipped": True,
                    "message": "Contract already approved",
                }
                update_data = QueueMessageBase(is_processed=True, result=result)
                backend.update_queue_message(message_id, update_data)
                return result

            # Initialize and execute the agent account approve contract tool
            approve_tool = AgentAccountApproveContractTool(wallet_id=wallet_id)
            approval_result = await approve_tool._arun(
                agent_account_contract=agent_account_contract,
                contract_to_approve=contract_to_approve,
                approval_type=approval_type,
            )

            logger.debug(f"Approval result for message {message_id}: {approval_result}")

            result = {
                "success": approval_result.get("success", False),
                "skipped": False,
                "result": approval_result,
            }

            # Store result and mark as processed
            update_data = QueueMessageBase(is_processed=True, result=result)
            backend.update_queue_message(message_id, update_data)

            if result["success"]:
                logger.info(f"Successfully approved contract for message {message_id}")
            else:
                logger.error(
                    f"Failed to approve contract for message {message_id}: {approval_result}"
                )

            return result

        except Exception as e:
            error_msg = f"Error processing message {message_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            result = {"success": False, "error": error_msg, "skipped": False}

            # Store result even for failed processing
            update_data = QueueMessageBase(result=result)
            backend.update_queue_message(message_id, update_data)

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
        if "invalid message data" in str(error).lower():
            return False
        if "missing" in str(error).lower() and "required" in str(error).lower():
            return False

        return isinstance(error, retry_errors)

    async def _handle_execution_error(
        self, error: Exception, context: JobContext
    ) -> Optional[List[AgentAccountProposalApprovalResult]]:
        """Handle execution errors with recovery logic."""
        if "blockchain" in str(error).lower() or "contract" in str(error).lower():
            logger.warning(f"Blockchain/contract error: {str(error)}, will retry")
            return None

        if isinstance(error, (ConnectionError, TimeoutError)):
            logger.warning(f"Network error: {str(error)}, will retry")
            return None

        # For validation errors, don't retry
        return [
            AgentAccountProposalApprovalResult(
                success=False,
                message=f"Unrecoverable error: {str(error)}",
                error=error,
            )
        ]

    async def _post_execution_cleanup(
        self, context: JobContext, results: List[AgentAccountProposalApprovalResult]
    ) -> None:
        """Cleanup after task execution."""
        logger.debug("Agent account proposal approval task cleanup completed")

    async def _execute_impl(
        self, context: JobContext
    ) -> List[AgentAccountProposalApprovalResult]:
        """Run the agent account proposal approval task with batch processing."""
        pending_messages = await self.get_pending_messages()
        message_count = len(pending_messages)
        logger.debug(f"Found {message_count} pending proposal approval messages")

        if not pending_messages:
            return [
                AgentAccountProposalApprovalResult(
                    success=True,
                    message="No pending messages found",
                    approvals_processed=0,
                    approvals_successful=0,
                    approvals_skipped=0,
                )
            ]

        # Process each message in batches
        processed_count = 0
        successful_count = 0
        skipped_count = 0
        errors = []
        batch_size = getattr(context, "batch_size", 3)

        logger.info(
            f"Processing {message_count} agent account proposal approval messages"
        )

        # Process messages in batches
        for i in range(0, len(pending_messages), batch_size):
            batch = pending_messages[i : i + batch_size]

            for message in batch:
                try:
                    result = await self.process_message(message)
                    processed_count += 1

                    if result.get("success"):
                        if result.get("skipped", False):
                            skipped_count += 1
                        else:
                            successful_count += 1
                    else:
                        errors.append(result.get("error", "Unknown error"))

                except Exception as e:
                    error_msg = f"Exception processing message {message.id}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg, exc_info=True)

        logger.info(
            f"Agent account proposal approval completed - Processed: {processed_count}, "
            f"Successful: {successful_count}, Skipped: {skipped_count}, Errors: {len(errors)}"
        )

        return [
            AgentAccountProposalApprovalResult(
                success=True,
                message=f"Processed {processed_count} approval(s), successful {successful_count}, skipped {skipped_count}",
                approvals_processed=processed_count,
                approvals_successful=successful_count,
                approvals_skipped=skipped_count,
                errors=errors,
            )
        ]


# Create instance for auto-registration
agent_account_proposal_approval = AgentAccountProposalApprovalTask()
