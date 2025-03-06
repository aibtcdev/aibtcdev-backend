"""DAO proposal voter task implementation."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from backend.factory import backend
from backend.models import (
    ProposalFilter,
    QueueMessage,
    QueueMessageBase,
    QueueMessageFilter,
    QueueMessageType,
)
from lib.logger import configure_logger
from services.runner.base import BaseTask, JobContext, RunnerResult
from services.workflows.proposal_evaluation import evaluate_and_vote_on_proposal

logger = configure_logger(__name__)


@dataclass
class DAOProposalVoteResult(RunnerResult):
    """Result of DAO proposal voting operation."""

    proposals_processed: int = 0
    proposals_voted: int = 0
    errors: List[str] = None

    def __post_init__(self):
        self.errors = self.errors or []


class DAOProposalVoterTask(BaseTask[DAOProposalVoteResult]):
    """Task runner for processing and voting on DAO proposals."""

    QUEUE_TYPE = QueueMessageType.DAO_PROPOSAL_VOTE
    DEFAULT_CONFIDENCE_THRESHOLD = 0.7
    DEFAULT_AUTO_VOTE = True

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate task-specific conditions."""
        try:
            pending_messages = await self.get_pending_messages()
            message_count = len(pending_messages)

            if message_count > 0:
                logger.debug(f"Found {message_count} pending proposal voting messages")
                return True
            else:
                logger.debug("No pending proposal voting messages")
                return False

        except Exception as e:
            logger.error(
                f"Error validating proposal voter task: {str(e)}", exc_info=True
            )
            return False

    async def process_message(self, message: QueueMessage) -> Dict[str, Any]:
        """Process a single DAO proposal voting message."""
        message_id = message.id
        message_data = message.message or {}
        wallet_id = message.wallet_id
        dao_id = message.dao_id

        logger.debug(
            f"Processing proposal voting message {message_id} for wallet {wallet_id}"
        )

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

            # Execute the proposal evaluation workflow
            logger.info(f"Evaluating proposal {proposal.id} for DAO {dao.name}")

            result = await evaluate_and_vote_on_proposal(
                proposal_id=proposal.id,
                dao_name=dao.name,
                wallet_id=wallet_id,
                auto_vote=self.DEFAULT_AUTO_VOTE,
                confidence_threshold=self.DEFAULT_CONFIDENCE_THRESHOLD,
            )

            # Log the results
            evaluation = result.get("evaluation", {})
            approval = evaluation.get("approve", False)
            confidence = evaluation.get("confidence_score", 0.0)
            reasoning = evaluation.get("reasoning", "No reasoning provided")

            if result.get("auto_voted", False):
                logger.info(
                    f"Proposal {proposal.id} ({dao.name}): Voted {'FOR' if approval else 'AGAINST'} "
                    f"with confidence {confidence:.2f}"
                )
            else:
                logger.info(
                    f"Proposal {proposal.id} ({dao.name}): No auto-vote - "
                    f"confidence {confidence:.2f} below threshold"
                )

            logger.debug(f"Proposal {proposal.id} reasoning: {reasoning}")

            # Mark the message as processed using QueueMessageBase
            update_data = QueueMessageBase(is_processed=True)
            backend.update_queue_message(message_id, update_data)

            return {
                "success": True,
                "auto_voted": result.get("auto_voted", False),
                "approve": approval,
            }

        except Exception as e:
            error_msg = f"Error processing message {message_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "error": error_msg}

    async def get_pending_messages(self) -> List[QueueMessage]:
        """Get all unprocessed messages from the queue."""
        filters = QueueMessageFilter(type=self.QUEUE_TYPE, is_processed=False)
        return backend.list_queue_messages(filters=filters)

    async def _execute_impl(self, context: JobContext) -> List[DAOProposalVoteResult]:
        """Run the DAO proposal voter task."""
        pending_messages = await self.get_pending_messages()
        message_count = len(pending_messages)
        logger.debug(f"Found {message_count} pending proposal voting messages")

        if not pending_messages:
            return [
                DAOProposalVoteResult(
                    success=True,
                    message="No pending messages found",
                    proposals_processed=0,
                    proposals_voted=0,
                )
            ]

        # Process each message
        processed_count = 0
        voted_count = 0
        errors = []

        for message in pending_messages:
            result = await self.process_message(message)
            processed_count += 1

            if result.get("success"):
                if result.get("auto_voted", False):
                    voted_count += 1
            else:
                errors.append(result.get("error", "Unknown error"))

        logger.debug(
            f"Task metrics - Processed: {processed_count}, "
            f"Voted: {voted_count}, Errors: {len(errors)}"
        )

        return [
            DAOProposalVoteResult(
                success=True,
                message=f"Processed {processed_count} proposal(s), voted on {voted_count} proposal(s)",
                proposals_processed=processed_count,
                proposals_voted=voted_count,
                errors=errors,
            )
        ]


# Instantiate the task for use in the registry
dao_proposal_voter = DAOProposalVoterTask()
