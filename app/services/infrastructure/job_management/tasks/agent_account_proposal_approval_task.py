"""Agent account proposal approval task implementation."""

from dataclasses import dataclass
import time
from typing import Any, Dict, List, Optional

from app.backend.factory import backend
from app.backend.models import (
    AgentBase,
    AgentFilter,
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
                "Error validating config",
                extra={"task": "proposal_approval", "error": str(e)},
                exc_info=True,
            )
            return False

    async def _validate_resources(self, context: JobContext) -> bool:
        """Validate resource availability."""
        try:
            # Test that backend is available
            if not backend:
                logger.error(
                    "Backend not available",
                    extra={"task": "proposal_approval"},
                )
                return False
            return True
        except Exception as e:
            logger.error(
                "Resource validation failed",
                extra={"task": "proposal_approval", "error": str(e)},
            )
            return False

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate task-specific conditions."""
        try:
            # Get pending messages from the queue
            pending_messages = await self.get_pending_messages()
            message_count = len(pending_messages)
            logger.debug(
                "Found pending messages",
                extra={"task": "proposal_approval", "message_count": message_count},
            )

            if message_count == 0:
                logger.debug(
                    "No pending messages found",
                    extra={"task": "proposal_approval"},
                )
                return False

            # Validate that at least one message has valid approval data
            for message in pending_messages:
                if self._validate_message_data(message):
                    logger.debug(
                        "Found valid message",
                        extra={"task": "proposal_approval"},
                    )
                    return True

            logger.warning(
                "No valid approval data found in pending messages",
                extra={"task": "proposal_approval"},
            )
            return False

        except Exception as e:
            logger.error(
                "Error validating task",
                extra={"task": "proposal_approval", "error": str(e)},
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

    async def _get_agent_by_contract(self, agent_account_contract: str):
        """Get agent by account contract address."""
        try:
            agents = backend.list_agents(
                filters=AgentFilter(account_contract=agent_account_contract)
            )
            return agents[0] if agents else None
        except Exception as e:
            logger.error(
                "Error getting agent for contract",
                extra={
                    "task": "proposal_approval",
                    "agent_account_contract": agent_account_contract,
                    "error": str(e),
                },
            )
            return None

    async def _is_already_approved_in_database(
        self, agent_account_contract: str, contract_to_approve: str
    ) -> bool:
        """Check if the contract is already approved by looking at the agent's approved_contracts array."""
        try:
            agent = await self._get_agent_by_contract(agent_account_contract)
            if not agent:
                logger.warning(
                    "Agent not found for contract",
                    extra={
                        "task": "proposal_approval",
                        "agent_account_contract": agent_account_contract,
                    },
                )
                return False

            # Check if the contract is in the approved_contracts array
            if (
                agent.approved_contracts
                and contract_to_approve in agent.approved_contracts
            ):
                logger.info(
                    "Contract already approved in database",
                    extra={
                        "task": "proposal_approval",
                        "agent_account_contract": agent_account_contract,
                        "contract_to_approve": contract_to_approve,
                    },
                )
                return True

            return False

        except Exception as e:
            logger.warning(
                "Could not check database approval status",
                extra={"task": "proposal_approval", "error": str(e)},
            )
            return False

    async def _is_already_approved(
        self, message_data: Dict[str, Any], wallet_id: str
    ) -> bool:
        """Check if the contract is already approved both in database and on-chain."""
        try:
            agent_account_contract = message_data["agent_account_contract"]
            contract_to_approve = message_data["contract_to_approve"]

            # First check our database records
            if await self._is_already_approved_in_database(
                agent_account_contract, contract_to_approve
            ):
                return True

            # If not in database, check on-chain as backup
            check_tool = AgentAccountIsApprovedContractTool(wallet_id=wallet_id)
            result = await check_tool._arun(
                agent_account_contract=agent_account_contract,
                contract_principal=contract_to_approve,
            )

            if result.get("success") and result.get("data"):
                # Parse the result to check if approved
                is_approved = result["data"].get("approved", False)
                if is_approved:
                    logger.info(
                        "Contract already approved on-chain",
                        extra={
                            "task": "proposal_approval",
                            "agent_account_contract": agent_account_contract,
                            "contract_to_approve": contract_to_approve,
                        },
                    )
                    # Update our database to reflect the on-chain state
                    await self._update_agent_approved_contracts(
                        agent_account_contract, contract_to_approve
                    )
                    return True

            return False

        except Exception as e:
            logger.warning(
                "Could not check approval status",
                extra={"task": "proposal_approval", "error": str(e)},
            )
            # If we can't check, proceed with approval attempt
            return False

    async def _update_agent_approved_contracts(
        self, agent_account_contract: str, contract_to_approve: str
    ) -> bool:
        """Update the agent's approved_contracts array with the newly approved contract."""
        try:
            agent = await self._get_agent_by_contract(agent_account_contract)
            if not agent:
                logger.error(
                    "Agent not found for contract",
                    extra={
                        "task": "proposal_approval",
                        "agent_account_contract": agent_account_contract,
                    },
                )
                return False

            # Get current approved contracts or initialize empty list
            current_approved = agent.approved_contracts or []

            # Add the new contract if not already present
            if contract_to_approve not in current_approved:
                updated_approved = current_approved + [contract_to_approve]

                # Create update data
                update_data = AgentBase(approved_contracts=updated_approved)

                # Update the agent
                backend.update_agent(agent.id, update_data)
                logger.info(
                    "Updated agent approved_contracts",
                    extra={
                        "task": "proposal_approval",
                        "agent_account_contract": agent_account_contract,
                        "contract_to_approve": contract_to_approve,
                    },
                )
                return True
            else:
                logger.debug(
                    "Contract already in approved_contracts",
                    extra={
                        "task": "proposal_approval",
                        "agent_account_contract": agent_account_contract,
                        "contract_to_approve": contract_to_approve,
                    },
                )
                return True

        except Exception as e:
            logger.error(
                "Failed to update agent approved_contracts",
                extra={
                    "task": "proposal_approval",
                    "agent_account_contract": agent_account_contract,
                    "error": str(e),
                },
                exc_info=True,
            )
            return False

    async def process_message(self, message: QueueMessage) -> Dict[str, Any]:
        """Process a single agent account proposal approval message."""
        message_id = message.id
        message_data = message.message or {}

        logger.debug(
            "Processing message",
            extra={"task": "proposal_approval", "message_id": message_id},
        )

        try:
            # Validate message data
            if not self._validate_message_data(message):
                error_msg = "Invalid message data"
                logger.error(
                    error_msg,
                    extra={"task": "proposal_approval", "message_id": message_id},
                )
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
                "Processing approval",
                extra={
                    "task": "proposal_approval",
                    "agent_account_contract": agent_account_contract,
                    "contract_to_approve": contract_to_approve,
                    "approval_type": approval_type,
                },
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

            logger.debug(
                "Approval result",
                extra={
                    "task": "proposal_approval",
                    "message_id": message_id,
                    "approval_result": approval_result,
                },
            )

            result = {
                "success": approval_result.get("success", False),
                "skipped": False,
                "result": approval_result,
            }

            # If approval was successful, update the agent's approved_contracts array
            if result["success"]:
                update_success = await self._update_agent_approved_contracts(
                    agent_account_contract, contract_to_approve
                )
                if not update_success:
                    logger.warning(
                        "Approval succeeded but failed to update agent database record",
                        extra={
                            "task": "proposal_approval",
                            "agent_account_contract": agent_account_contract,
                        },
                    )

            # Store result and mark as processed
            update_data = QueueMessageBase(is_processed=True, result=result)
            backend.update_queue_message(message_id, update_data)

            if result["success"]:
                logger.info(
                    "Successfully approved contract",
                    extra={"task": "proposal_approval", "message_id": message_id},
                )
            else:
                logger.error(
                    "Failed to approve contract",
                    extra={
                        "task": "proposal_approval",
                        "message_id": message_id,
                        "approval_result": approval_result,
                    },
                )

            return result

        except Exception as e:
            logger.error(
                "Error processing message",
                extra={
                    "task": "proposal_approval",
                    "message_id": message_id,
                    "error": str(e),
                },
                exc_info=True,
            )
            error_msg = f"Error processing message {message_id}: {str(e)}"
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
            logger.warning(
                "Blockchain/contract error, will retry",
                extra={"task": "proposal_approval", "error": str(error)},
            )
            return None

        if isinstance(error, (ConnectionError, TimeoutError)):
            logger.warning(
                "Network error, will retry",
                extra={"task": "proposal_approval", "error": str(error)},
            )
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
        logger.debug(
            "Task cleanup completed",
            extra={"task": "proposal_approval"},
        )

    async def _execute_impl(
        self, context: JobContext
    ) -> List[AgentAccountProposalApprovalResult]:
        """Run the agent account proposal approval task with batch processing."""
        pending_messages = await self.get_pending_messages()
        message_count = len(pending_messages)
        logger.debug(
            "Found pending messages",
            extra={"task": "proposal_approval", "message_count": message_count},
        )

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
            "Processing messages",
            extra={"task": "proposal_approval", "message_count": message_count},
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

                    time.sleep(5)

                except Exception as e:
                    error_msg = f"Exception processing message {message.id}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(
                        "Exception processing message",
                        extra={
                            "task": "proposal_approval",
                            "message_id": message.id,
                            "error": str(e),
                        },
                        exc_info=True,
                    )

        logger.info(
            "Task completed",
            extra={
                "task": "proposal_approval",
                "processed_count": processed_count,
                "successful_count": successful_count,
                "skipped_count": skipped_count,
                "error_count": len(errors),
            },
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
