"""DAO proposal evaluation task implementation."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from backend.factory import backend
from backend.models import (
    ProposalBase,
    ProposalFilter,
    QueueMessage,
    QueueMessageBase,
    QueueMessageFilter,
    QueueMessageType,
    VoteCreate,
)
from lib.logger import configure_logger
from services.runner.base import BaseTask, JobContext, RunnerResult
from services.runner.decorators import JobPriority, job
from services.workflows import evaluate_and_vote_on_proposal

logger = configure_logger(__name__)


@dataclass
class DAOProposalEvaluationResult(RunnerResult):
    """Result of DAO proposal evaluation operation."""

    proposals_processed: int = 0
    proposals_evaluated: int = 0
    evaluations_successful: int = 0
    votes_created: int = 0
    errors: List[str] = None

    def __post_init__(self):
        self.errors = self.errors or []


@job(
    job_type="dao_proposal_evaluation",
    name="DAO Proposal Evaluator",
    description="Evaluates DAO proposals using AI analysis with enhanced monitoring and error handling",
    interval_seconds=30,
    priority=JobPriority.HIGH,
    max_retries=3,
    retry_delay_seconds=60,
    timeout_seconds=180,
    max_concurrent=1,
    requires_ai=True,
    batch_size=5,
    enable_dead_letter_queue=True,
)
class DAOProposalEvaluationTask(BaseTask[DAOProposalEvaluationResult]):
    """Task runner for evaluating DAO proposals using AI analysis with enhanced capabilities."""

    QUEUE_TYPE = QueueMessageType.get_or_create("dao_proposal_evaluation")

    async def get_pending_messages(self) -> List[QueueMessage]:
        """Get all unprocessed DAO proposal evaluation messages from the queue."""
        filters = QueueMessageFilter(type=self.QUEUE_TYPE, is_processed=False)
        return backend.list_queue_messages(filters=filters)

    async def _validate_config(self, context: JobContext) -> bool:
        """Validate task configuration."""
        try:
            # Check if AI evaluation workflow is available
            return True
        except Exception as e:
            logger.error(
                f"Error validating proposal evaluation config: {str(e)}", exc_info=True
            )
            return False

    async def _validate_resources(self, context: JobContext) -> bool:
        """Validate resource availability for AI processing."""
        try:
            # Check backend connectivity
            backend.get_api_status()
            return True
        except Exception as e:
            logger.error(f"Backend not available: {str(e)}")
            return False

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate that we have pending evaluation messages to process."""
        try:
            pending_messages = await self.get_pending_messages()

            if not pending_messages:
                logger.info("No pending DAO proposal evaluation messages found")
                return False

            # Validate each message has valid proposal data
            valid_messages = []
            for message in pending_messages:
                if await self._is_message_valid(message):
                    valid_messages.append(message)

            if valid_messages:
                logger.info(
                    f"Found {len(valid_messages)} valid DAO proposal evaluation messages"
                )
                return True

            logger.info("No valid DAO proposal evaluation messages to process")
            return False

        except Exception as e:
            logger.error(
                f"Error validating proposal evaluation task: {str(e)}", exc_info=True
            )
            return False

    async def _is_message_valid(self, message: QueueMessage) -> bool:
        """Check if a proposal evaluation message is valid for processing."""
        try:
            if not message.message or not message.dao_id:
                return False

            proposal_id = message.message.get("proposal_id")
            if not proposal_id:
                return False

            # Check if proposal exists and is ready for evaluation
            proposal = backend.get_proposal(proposal_id)
            if not proposal:
                return False

            # Check if proposal is already evaluated
            if proposal.evaluated:
                return False

            return True
        except Exception:
            return False

    async def _process_message(self, message: QueueMessage) -> Dict[str, Any]:
        """Process a single DAO proposal evaluation message with enhanced error handling."""
        message_id = message.id
        message_data = message.message or {}
        dao_id = message.dao_id

        logger.debug(f"Processing proposal evaluation message {message_id}")

        # Get the proposal ID from the message
        proposal_id = message_data.get("proposal_id")
        if not proposal_id:
            error_msg = f"Missing proposal_id in message {message_id}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        try:
            # Get the proposal details from database
            proposal = backend.get_proposal(proposal_id)
            if not proposal:
                error_msg = f"Proposal {proposal_id} not found in database"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "should_mark_processed": True,  # Remove invalid messages
                }

            # Check if proposal is already evaluated
            if proposal.evaluated:
                logger.info(f"Proposal {proposal_id} is already evaluated, skipping...")
                return {
                    "success": True,
                    "evaluated": False,
                    "message": "Proposal already evaluated",
                    "should_mark_processed": True,
                }

            # Check if the DAO has any pending proposals
            pending_proposals = backend.list_proposals(
                filters=ProposalFilter(dao_id=dao_id, is_open=True, evaluated=False)
            )

            if not pending_proposals:
                logger.info(
                    f"No pending proposals found for DAO {dao_id}, skipping evaluation"
                )
                return {
                    "success": True,
                    "evaluated": False,
                    "message": "No pending proposals to evaluate",
                    "should_mark_processed": True,
                }

            logger.info(f"Evaluating proposal {proposal.proposal_id} for DAO {dao_id}")

            # Process the proposal using the AI workflow
            evaluation_result = await evaluate_and_vote_on_proposal(
                dao_id=dao_id,
                proposal_id=proposal_id,
                auto_vote=False,
            )

            if not evaluation_result or not evaluation_result.get("success"):
                error_msg = f"Proposal evaluation failed: {evaluation_result.get('error', 'Unknown error')}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

            # Update proposal as evaluated
            proposal_update = ProposalBase(evaluated=True)
            updated_proposal = backend.update_proposal(proposal_id, proposal_update)

            if not updated_proposal:
                error_msg = "Failed to update proposal as evaluated"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

            # Create votes based on evaluation result
            votes_created = 0
            if evaluation_result.get("votes"):
                for vote_data in evaluation_result["votes"]:
                    try:
                        vote = VoteCreate(
                            proposal_id=proposal_id,
                            wallet_id=vote_data["wallet_id"],
                            answer=vote_data["answer"],
                            voted=False,
                        )
                        created_vote = backend.create_vote(vote)
                        if created_vote:
                            votes_created += 1
                            logger.debug(
                                f"Created vote {created_vote.id} for proposal {proposal_id}"
                            )
                    except Exception as e:
                        logger.error(f"Failed to create vote: {str(e)}")

            logger.info(
                f"Successfully evaluated proposal {proposal.proposal_id}, created {votes_created} votes"
            )

            return {
                "success": True,
                "evaluated": True,
                "votes_created": votes_created,
                "evaluation_result": evaluation_result,
                "should_mark_processed": True,
            }

        except Exception as e:
            error_msg = f"Error processing message {message_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "error": error_msg}

    def _should_retry_on_error(self, error: Exception, context: JobContext) -> bool:
        """Determine if error should trigger retry."""
        # Retry on network errors, AI service timeouts
        retry_errors = (
            ConnectionError,
            TimeoutError,
        )

        # Don't retry on validation errors
        if "not found" in str(error).lower():
            return False
        if "already evaluated" in str(error).lower():
            return False

        return isinstance(error, retry_errors)

    async def _handle_execution_error(
        self, error: Exception, context: JobContext
    ) -> Optional[List[DAOProposalEvaluationResult]]:
        """Handle execution errors with recovery logic."""
        if "ai" in str(error).lower() or "openai" in str(error).lower():
            logger.warning(f"AI service error: {str(error)}, will retry")
            return None

        if isinstance(error, (ConnectionError, TimeoutError)):
            logger.warning(f"Network error: {str(error)}, will retry")
            return None

        # For validation errors, don't retry
        return [
            DAOProposalEvaluationResult(
                success=False,
                message=f"Unrecoverable error: {str(error)}",
                error=error,
            )
        ]

    async def _post_execution_cleanup(
        self, context: JobContext, results: List[DAOProposalEvaluationResult]
    ) -> None:
        """Cleanup after task execution."""
        logger.debug("DAO proposal evaluation task cleanup completed")

    async def _execute_impl(
        self, context: JobContext
    ) -> List[DAOProposalEvaluationResult]:
        """Run the DAO proposal evaluation task with batch processing."""
        # Get pending messages
        pending_messages = await self.get_pending_messages()

        if not pending_messages:
            return [
                DAOProposalEvaluationResult(
                    success=True,
                    message="No pending messages found",
                    proposals_processed=0,
                    proposals_evaluated=0,
                )
            ]

        message_count = len(pending_messages)
        logger.info(f"Processing {message_count} pending proposal evaluation messages")

        # Process each message
        processed_count = 0
        evaluated_count = 0
        successful_evaluations = 0
        total_votes_created = 0
        errors = []
        batch_size = getattr(context, "batch_size", 5)

        # Process messages in batches
        for i in range(0, len(pending_messages), batch_size):
            batch = pending_messages[i : i + batch_size]

            for message in batch:
                try:
                    result = await self._process_message(message)
                    processed_count += 1

                    if result.get("success"):
                        if result.get("evaluated", False):
                            evaluated_count += 1
                            successful_evaluations += 1
                            total_votes_created += result.get("votes_created", 0)

                        # Mark message as processed if indicated and store result
                        if result.get("should_mark_processed", False):
                            update_data = QueueMessageBase(
                                is_processed=True, result=result
                            )
                            backend.update_queue_message(message.id, update_data)
                            logger.debug(
                                f"Marked message {message.id} as processed with result"
                            )

                    else:
                        error_msg = result.get("error", "Unknown error")
                        errors.append(f"Message {message.id}: {error_msg}")
                        logger.error(
                            f"Failed to process message {message.id}: {error_msg}"
                        )

                        # Store result for failed processing
                        update_data = QueueMessageBase(result=result)
                        backend.update_queue_message(message.id, update_data)
                        logger.debug(f"Stored result for failed message {message.id}")

                except Exception as e:
                    error_msg = f"Exception processing message {message.id}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg, exc_info=True)

                    # Store result for exception cases
                    error_result = {"success": False, "error": error_msg}
                    update_data = QueueMessageBase(result=error_result)
                    backend.update_queue_message(message.id, update_data)
                    logger.debug(f"Stored error result for message {message.id}")

        logger.info(
            f"DAO proposal evaluation task completed - Processed: {processed_count}/{message_count}, "
            f"Evaluated: {evaluated_count}, Votes Created: {total_votes_created}, Errors: {len(errors)}"
        )

        return [
            DAOProposalEvaluationResult(
                success=True,
                message=f"Processed {processed_count} message(s), evaluated {evaluated_count} proposal(s)",
                proposals_processed=processed_count,
                proposals_evaluated=evaluated_count,
                evaluations_successful=successful_evaluations,
                votes_created=total_votes_created,
                errors=errors,
            )
        ]


# Create instance for auto-registration
dao_proposal_evaluation = DAOProposalEvaluationTask()
