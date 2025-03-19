"""DAO proposal conclusion task implementation."""

from dataclasses import dataclass
from typing import Any, Dict, List

from backend.factory import backend
from backend.models import (
    QueueMessage,
    QueueMessageBase,
    QueueMessageFilter,
    QueueMessageType,
    TokenFilter,
)
from config import config
from lib.logger import configure_logger
from services.runner.base import BaseTask, JobContext, RunnerResult
from tools.dao_ext_action_proposals import ConcludeActionProposalTool

logger = configure_logger(__name__)


@dataclass
class DAOProposalConcludeResult(RunnerResult):
    """Result of DAO proposal conclusion operation."""

    proposals_processed: int = 0
    proposals_concluded: int = 0
    errors: List[str] = None

    def __post_init__(self):
        self.errors = self.errors or []


class DAOProposalConcluderTask(BaseTask[DAOProposalConcludeResult]):
    """Task runner for processing and concluding DAO proposals."""

    QUEUE_TYPE = QueueMessageType.DAO_PROPOSAL_CONCLUDE

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate task-specific conditions."""
        try:
            # Get pending messages from the queue
            pending_messages = await self.get_pending_messages()
            message_count = len(pending_messages)
            logger.debug(f"Found {message_count} pending proposal conclusion messages")

            if message_count == 0:
                logger.info("No pending proposal conclusion messages found")
                return False

            # Validate that at least one message has a valid proposal
            for message in pending_messages:
                message_data = message.message or {}
                proposal_id = message_data.get("proposal_id")

                if not proposal_id:
                    logger.warning(f"Message {message.id} missing proposal_id")
                    continue

                # Check if the proposal exists in the database
                proposal = backend.get_proposal(proposal_id)
                if proposal:
                    logger.info(f"Found valid proposal {proposal_id} to conclude")
                    return True
                else:
                    logger.warning(f"Proposal {proposal_id} not found in database")

            logger.warning("No valid proposals found in pending messages")
            return False

        except Exception as e:
            logger.error(
                f"Error validating proposal conclusion task: {str(e)}", exc_info=True
            )
            return False

    async def process_message(self, message: QueueMessage) -> Dict[str, Any]:
        """Process a single DAO proposal conclusion message."""
        message_id = message.id
        message_data = message.message or {}
        dao_id = message.dao_id

        logger.debug(f"Processing proposal conclusion message {message_id}")

        # Get the proposal ID from the message
        proposal_id = message_data.get("proposal_id")
        if not proposal_id:
            error_msg = f"Missing proposal_id in message {message_id}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        try:
            # Get the proposal details from the database
            proposal = backend.get_proposal(proposal_id)
            if not proposal:
                error_msg = f"Proposal {proposal_id} not found in database"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

            # Get the DAO information
            dao = backend.get_dao(dao_id) if dao_id else None
            if not dao:
                error_msg = f"DAO not found for proposal {proposal_id}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

            # Get the DAO token information
            tokens = backend.list_tokens(filters=TokenFilter(dao_id=dao_id))
            if not tokens:
                error_msg = f"No token found for DAO: {dao_id}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

            # Use the first token as the DAO token
            dao_token = tokens[0]

            # Initialize the ConcludeActionProposalTool
            logger.debug(f"Preparing to conclude proposal {proposal.proposal_id}")
            conclude_tool = ConcludeActionProposalTool(
                wallet_id=config.scheduler.dao_proposal_conclude_runner_wallet_id
            )

            # Execute the conclusion
            logger.debug("Executing conclusion...")
            conclusion_result = await conclude_tool._arun(
                action_proposals_voting_extension=proposal.contract_principal,  # This is the voting extension contract
                proposal_id=proposal.proposal_id,  # This is the on-chain proposal ID
                action_proposal_contract_to_execute=proposal.action,  # This is the contract that will be executed
                dao_token_contract_address=dao_token.contract_principal,  # This is the DAO token contract
            )
            logger.debug(f"Conclusion result: {conclusion_result}")

            # Mark the message as processed
            update_data = QueueMessageBase(is_processed=True)
            backend.update_queue_message(message_id, update_data)

            return {"success": True, "concluded": True, "result": conclusion_result}

        except Exception as e:
            error_msg = f"Error processing message {message_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "error": error_msg}

    async def get_pending_messages(self) -> List[QueueMessage]:
        """Get all unprocessed messages from the queue."""
        filters = QueueMessageFilter(type=self.QUEUE_TYPE, is_processed=False)
        return backend.list_queue_messages(filters=filters)

    async def _execute_impl(
        self, context: JobContext
    ) -> List[DAOProposalConcludeResult]:
        """Run the DAO proposal conclusion task."""
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
        errors = []

        for message in pending_messages:
            result = await self.process_message(message)
            processed_count += 1

            if result.get("success"):
                if result.get("concluded", False):
                    concluded_count += 1
            else:
                errors.append(result.get("error", "Unknown error"))

        logger.debug(
            f"Task metrics - Processed: {processed_count}, "
            f"Concluded: {concluded_count}, Errors: {len(errors)}"
        )

        return [
            DAOProposalConcludeResult(
                success=True,
                message=f"Processed {processed_count} proposal(s), concluded {concluded_count} proposal(s)",
                proposals_processed=processed_count,
                proposals_concluded=concluded_count,
                errors=errors,
            )
        ]


# Instantiate the task for use in the registry
dao_proposal_concluder = DAOProposalConcluderTask()
