"""DAO proposal evaluation task implementation."""

from dataclasses import dataclass
from typing import Any, Dict, List

from backend.factory import backend
from backend.models import (
    QueueMessage,
    QueueMessageBase,
    QueueMessageCreate,
    QueueMessageFilter,
    QueueMessageType,
    VoteCreate,
)
from lib.logger import configure_logger
from services.runner.base import BaseTask, JobContext, RunnerResult
from services.workflows.proposal_evaluation import evaluate_and_vote_on_proposal

logger = configure_logger(__name__)


@dataclass
class DAOProposalEvaluationResult(RunnerResult):
    """Result of DAO proposal evaluation operation."""

    proposals_processed: int = 0
    proposals_evaluated: int = 0
    errors: List[str] = None

    def __post_init__(self):
        self.errors = self.errors or []


class DAOProposalEvaluationTask(BaseTask[DAOProposalEvaluationResult]):
    """Task runner for evaluating DAO proposals."""

    QUEUE_TYPE = QueueMessageType.DAO_PROPOSAL_EVALUATION
    DEFAULT_CONFIDENCE_THRESHOLD = 0.7
    DEFAULT_AUTO_VOTE = False

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate task-specific conditions."""
        try:
            # Get pending messages from the queue
            pending_messages = await self.get_pending_messages()
            message_count = len(pending_messages)
            logger.debug(f"Found {message_count} pending proposal evaluation messages")

            if message_count == 0:
                logger.info("No pending proposal evaluation messages found")
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
                    logger.info(f"Found valid proposal {proposal_id} to process")
                    return True
                else:
                    logger.warning(f"Proposal {proposal_id} not found in database")

            logger.warning("No valid proposals found in pending messages")
            return False

        except Exception as e:
            logger.error(
                f"Error validating proposal evaluation task: {str(e)}", exc_info=True
            )
            return False

    async def process_message(self, message: QueueMessage) -> Dict[str, Any]:
        """Process a single DAO proposal evaluation message."""
        message_id = message.id
        message_data = message.message or {}
        wallet_id = message.wallet_id
        dao_id = message.dao_id

        logger.debug(
            f"Processing proposal evaluation message {message_id} for wallet {wallet_id}"
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
                wallet_id=wallet_id,
                auto_vote=self.DEFAULT_AUTO_VOTE,  # Don't auto-vote, just evaluate
                confidence_threshold=self.DEFAULT_CONFIDENCE_THRESHOLD,
                dao_id=dao_id,
            )

            # Extract evaluation results
            evaluation = result.get("evaluation", {})
            approval = evaluation.get("approve", False)
            confidence = evaluation.get("confidence_score", 0.0)
            reasoning = evaluation.get("reasoning", "No reasoning provided")
            formatted_prompt = result.get("formatted_prompt", "No prompt provided")
            total_cost = result.get("total_overall_cost", 0.0)
            model = result.get("evaluation_model_info", {}).get("name", "Unknown")

            logger.info(
                f"Proposal {proposal.id} ({dao.name}): Evaluated with result "
                f"{'FOR' if approval else 'AGAINST'} with confidence {confidence:.2f}"
            )

            wallet = backend.get_wallet(wallet_id)

            # Create a vote record with the evaluation results
            vote_data = VoteCreate(
                wallet_id=wallet_id,
                dao_id=dao_id,
                agent_id=None,  # This will be set from the wallet if it exists
                proposal_id=proposal_id,
                answer=approval,
                reasoning=reasoning,
                confidence=confidence,
                prompt=formatted_prompt,
                cost=total_cost,
                model=model,
                profile_id=wallet.profile_id,
            )

            # Create the vote record
            vote = backend.create_vote(vote_data)
            if not vote:
                logger.error("Failed to create vote record")
                return {"success": False, "error": "Failed to create vote record"}

            logger.info(f"Created vote record {vote.id} for proposal {proposal_id}")

            # Create a DAO_PROPOSAL_VOTE message with the vote record ID
            vote_message_data = {"proposal_id": proposal_id, "vote_id": str(vote.id)}

            vote_message = backend.create_queue_message(
                QueueMessageCreate(
                    type=QueueMessageType.DAO_PROPOSAL_VOTE,
                    message=vote_message_data,
                    dao_id=dao_id,
                    wallet_id=wallet_id,
                )
            )

            if not vote_message:
                logger.error("Failed to create vote queue message")
                return {
                    "success": False,
                    "error": "Failed to create vote queue message",
                }

            logger.info(f"Created vote queue message {vote_message.id}")

            # Mark the evaluation message as processed
            update_data = QueueMessageBase(is_processed=True)
            backend.update_queue_message(message_id, update_data)

            return {
                "success": True,
                "vote_id": str(vote.id),
                "vote_message_id": str(vote_message.id),
                "approve": approval,
                "confidence": confidence,
            }

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
    ) -> List[DAOProposalEvaluationResult]:
        """Run the DAO proposal evaluation task."""
        pending_messages = await self.get_pending_messages()
        message_count = len(pending_messages)
        logger.debug(f"Found {message_count} pending proposal evaluation messages")

        if not pending_messages:
            return [
                DAOProposalEvaluationResult(
                    success=True,
                    message="No pending messages found",
                    proposals_processed=0,
                    proposals_evaluated=0,
                )
            ]

        # Process each message
        processed_count = 0
        evaluated_count = 0
        errors = []

        for message in pending_messages:
            result = await self.process_message(message)
            processed_count += 1

            if result.get("success"):
                evaluated_count += 1
            else:
                errors.append(result.get("error", "Unknown error"))

        logger.debug(
            f"Task metrics - Processed: {processed_count}, "
            f"Evaluated: {evaluated_count}, Errors: {len(errors)}"
        )

        return [
            DAOProposalEvaluationResult(
                success=True,
                message=f"Processed {processed_count} proposal(s), evaluated {evaluated_count} proposal(s)",
                proposals_processed=processed_count,
                proposals_evaluated=evaluated_count,
                errors=errors,
            )
        ]


# Instantiate the task for use in the registry
dao_proposal_evaluation = DAOProposalEvaluationTask()
