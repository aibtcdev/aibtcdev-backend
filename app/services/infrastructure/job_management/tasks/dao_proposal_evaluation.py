"""DAO proposal evaluation task implementation."""

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Dict, List
from uuid import UUID

from app.backend.factory import backend
from app.backend.models import (
    QueueMessage,
    QueueMessageBase,
    QueueMessageFilter,
    QueueMessageType,
    VoteCreate,
    VoteFilter,
)
from app.lib.logger import configure_logger
from app.services.infrastructure.job_management.base import (
    BaseTask,
    JobContext,
    RunnerResult,
)
from app.services.infrastructure.job_management.decorators import JobPriority, job
from app.services.ai.simple_workflows.orchestrator import (
    evaluate_proposal_comprehensive,
)

logger = configure_logger(__name__)


@dataclass
class DAOProposalEvaluationResult(RunnerResult):
    """Result of DAO proposal evaluation operation."""

    proposals_processed: int = 0
    proposals_evaluated: int = 0
    errors: List[str] = None

    def __post_init__(self):
        self.errors = self.errors or []


@job(
    job_type="dao_proposal_evaluation",
    name="DAO Proposal Evaluator",
    description="Evaluates DAO proposals using AI analysis with concurrent processing",
    interval_seconds=30,
    priority=JobPriority.HIGH,
    max_retries=3,
    retry_delay_seconds=60,
    timeout_seconds=300,
    max_concurrent=1,
    requires_ai=True,
    batch_size=5,
    enable_dead_letter_queue=True,
)
class DAOProposalEvaluationTask(BaseTask[DAOProposalEvaluationResult]):
    """Task runner for evaluating DAO proposals with concurrent processing.

    This task processes multiple DAO proposal evaluation messages concurrently
    instead of sequentially. Key features:
    - Uses asyncio.gather() for concurrent execution
    - Semaphore controls maximum concurrent operations to prevent resource exhaustion
    - Configurable concurrency limit (default: 5)
    - Graceful error handling that doesn't stop the entire batch
    - Performance timing and detailed logging
    """

    QUEUE_TYPE = QueueMessageType.get_or_create("dao_proposal_evaluation")
    DEFAULT_SCORE_THRESHOLD = 70.0
    DEFAULT_AUTO_VOTE = False
    DEFAULT_MAX_CONCURRENT_EVALUATIONS = (
        5  # Limit concurrent evaluations to avoid rate limits
    )

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

    def _has_proposal_been_evaluated(
        self, proposal_id: str, wallet_id: str = None
    ) -> bool:
        """Check if a proposal has already been evaluated by looking at the votes table.

        Note: This method is deprecated in favor of batch evaluation checking.
        Use _filter_unevaluated_messages for better performance.

        Args:
            proposal_id: The UUID of the proposal to check
            wallet_id: Optional wallet ID to check for specific wallet evaluation

        Returns:
            bool: True if the proposal has been evaluated, False otherwise
        """
        try:
            # Create filter to look for existing votes for this proposal
            vote_filter = VoteFilter(proposal_id=proposal_id)

            # If wallet_id is provided, check for evaluation by that specific wallet
            if wallet_id:
                vote_filter.wallet_id = wallet_id

            # Get existing votes for this proposal
            existing_votes = backend.list_votes(filters=vote_filter)

            # Check if any votes have evaluation data (indicating evaluation was performed)
            for vote in existing_votes:
                if (
                    vote.evaluation_score
                    or vote.evaluation
                    or vote.reasoning
                    or vote.confidence is not None
                ):
                    logger.debug(
                        f"Found existing evaluation for proposal {proposal_id}"
                    )
                    return True

            return False

        except Exception as e:
            logger.error(
                f"Error checking if proposal {proposal_id} was evaluated: {str(e)}"
            )
            return False

    def _filter_unevaluated_messages(
        self, messages: List[QueueMessage]
    ) -> List[QueueMessage]:
        """Filter out messages for proposals that have already been evaluated.

        This method performs a single batch query to check all proposal-wallet pairs,
        significantly reducing database load compared to individual checks.

        Args:
            messages: List of queue messages to filter

        Returns:
            List of messages for proposals that haven't been evaluated yet
        """
        if not messages:
            return []

        # Extract proposal-wallet pairs from messages
        proposal_wallet_pairs = []
        message_lookup = {}  # Map pairs to original messages

        for message in messages:
            message_data = message.message or {}
            proposal_id = message_data.get("proposal_id")
            wallet_id = message.wallet_id

            if proposal_id and wallet_id:
                try:
                    # Convert to UUID objects for consistency
                    proposal_uuid = (
                        UUID(proposal_id)
                        if isinstance(proposal_id, str)
                        else proposal_id
                    )
                    wallet_uuid = (
                        UUID(wallet_id) if isinstance(wallet_id, str) else wallet_id
                    )

                    pair = (proposal_uuid, wallet_uuid)
                    proposal_wallet_pairs.append(pair)
                    message_lookup[pair] = message
                except ValueError as e:
                    logger.warning(f"Invalid UUID in message {message.id}: {e}")
                    continue

        if not proposal_wallet_pairs:
            logger.debug("No valid proposal-wallet pairs found in messages")
            return []

        # Batch check which proposals have been evaluated
        try:
            evaluation_status = backend.check_proposals_evaluated_batch(
                proposal_wallet_pairs
            )

            # Filter out already evaluated proposals
            unevaluated_messages = []
            skipped_count = 0

            for pair, is_evaluated in evaluation_status.items():
                if not is_evaluated and pair in message_lookup:
                    unevaluated_messages.append(message_lookup[pair])
                elif is_evaluated:
                    skipped_count += 1

            # Log summary instead of individual skipped proposals
            if skipped_count > 0:
                logger.info(f"Skipped {skipped_count} already-evaluated proposals")

            logger.info(
                f"Filtered to {len(unevaluated_messages)} unevaluated proposals from {len(messages)} total messages"
            )
            return unevaluated_messages

        except Exception as e:
            logger.error(f"Error in batch evaluation check: {str(e)}")
            # Fallback to original behavior if batch check fails
            logger.warning("Falling back to individual evaluation checks")
            return messages

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

            # Note: Individual evaluation check removed here as it's now handled
            # in batch during the pre-filtering phase in _execute_impl
            # This significantly reduces database queries and log spam

            # Get the DAO information
            dao = backend.get_dao(dao_id) if dao_id else None
            if not dao:
                error_msg = f"DAO not found for proposal {proposal_id}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

            # Execute the proposal evaluation workflow
            logger.info(f"Evaluating proposal {proposal.id} for DAO {dao.name}")

            # Get proposal data
            proposal_content = proposal.content or "No content provided"

            evaluation = await evaluate_proposal_comprehensive(
                proposal_content=proposal_content,
                dao_id=dao_id,
                proposal_id=str(proposal.id),
                streaming=False,
            )

            # Extract evaluation results from the nested structure
            evaluation_data = evaluation.get("evaluation", {})
            approval = evaluation_data.get("decision", False)
            overall_score = evaluation_data.get("final_score", 0)
            reasoning = evaluation_data.get("explanation", "")
            formatted_prompt = ""  # Not available in the new model structure
            total_cost = evaluation_data.get("token_usage", {}).get("total_cost", 0.0)
            model = evaluation_data.get("token_usage", {}).get("model", "Unknown")
            evaluation_scores = {
                "categories": [
                    {
                        "category": cat.get("category", ""),
                        "score": cat.get("score", 0),
                        "weight": cat.get("weight", 0),
                        "reasoning": cat.get("reasoning", ""),
                    }
                    for cat in evaluation_data.get("categories", [])
                ],
                "final_score": evaluation_data.get("final_score", 0),
            }  # Convert categories to scores format
            evaluation_flags = evaluation_data.get("flags", [])

            logger.info(
                f"Proposal {proposal.id} ({dao.name}): Evaluated with result "
                f"{'FOR' if approval else 'AGAINST'} with score {overall_score}"
            )

            wallet = backend.get_wallet(wallet_id)

            # Create a vote record with the evaluation results
            vote_data = VoteCreate(
                wallet_id=wallet_id,
                dao_id=dao_id,
                agent_id=(
                    wallet.agent_id if wallet else None
                ),  # This will be set from the wallet if it exists
                proposal_id=proposal_id,
                answer=approval,
                reasoning=reasoning,
                confidence=overall_score
                / 100.0,  # Convert score to 0-1 range for compatibility
                prompt=formatted_prompt,
                cost=total_cost,
                model=model,
                profile_id=wallet.profile_id if wallet else None,
                evaluation_score=evaluation_scores,  # Store the complete evaluation scores
                flags=evaluation_flags,  # Store the evaluation flags
                evaluation=evaluation_data,  # Already a dictionary from the nested structure
            )

            # Create the vote record
            vote = backend.create_vote(vote_data)
            if not vote:
                logger.error("Failed to create vote record")
                return {"success": False, "error": "Failed to create vote record"}

            logger.info(f"Created vote record {vote.id} for proposal {proposal_id}")

            # Mark the evaluation message as processed
            update_data = QueueMessageBase(
                is_processed=True,
                result={
                    "success": True,
                    "vote_id": str(vote.id),
                    "approve": approval,
                    "overall_score": overall_score,
                },
            )
            backend.update_queue_message(message_id, update_data)

            return {
                "success": True,
                "vote_id": str(vote.id),
                "approve": approval,
                "overall_score": overall_score,
            }

        except Exception as e:
            error_msg = f"Error processing message {message_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            update_data = QueueMessageBase(
                is_processed=True,
                result={
                    "success": False,
                    "error": error_msg,
                },
            )
            backend.update_queue_message(message_id, update_data)

            return {"success": False, "error": error_msg}

    async def get_pending_messages(self) -> List[QueueMessage]:
        """Get all unprocessed messages from the queue."""
        filters = QueueMessageFilter(type=self.QUEUE_TYPE, is_processed=False)
        return backend.list_queue_messages(filters=filters)

    async def process_message_with_semaphore(
        self, semaphore: asyncio.Semaphore, message: QueueMessage
    ) -> Dict[str, Any]:
        """Process a message with concurrency control using semaphore.

        This wrapper ensures that each message processing is controlled by the
        semaphore to limit concurrent operations and prevent resource exhaustion.
        """
        async with semaphore:
            try:
                return await self.process_message(message)
            except Exception as e:
                # Log the error and return a failure result instead of raising
                # This prevents one failed message from crashing the entire batch
                error_msg = f"Failed to process message {message.id}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                return {"success": False, "error": error_msg}

    def get_max_concurrent_evaluations(self, context: JobContext) -> int:
        """Get the maximum number of concurrent evaluations from context or default.

        This allows for dynamic configuration of concurrency limits based on:
        - Context configuration
        - Environment variables
        - System load considerations
        """
        # Allow context to override the default concurrency limit
        context_limit = getattr(context, "max_concurrent_evaluations", None)

        if context_limit is not None:
            logger.debug(f"Using context-provided concurrency limit: {context_limit}")
            return context_limit

        # Could also check environment variables or system resources here
        # import os
        # env_limit = os.getenv("DAO_EVAL_MAX_CONCURRENT")
        # if env_limit:
        #     return int(env_limit)

        return self.DEFAULT_MAX_CONCURRENT_EVALUATIONS

    async def _execute_impl(
        self, context: JobContext
    ) -> List[DAOProposalEvaluationResult]:
        """Run the DAO proposal evaluation task with optimized batch processing.

        This method now includes pre-filtering to remove already-evaluated proposals
        before concurrent processing, significantly reducing database load and log spam.
        """
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

        # Pre-filter messages to remove already-evaluated proposals
        # This single batch operation replaces many individual database queries
        unevaluated_messages = self._filter_unevaluated_messages(pending_messages)
        skipped_count = len(pending_messages) - len(unevaluated_messages)

        if not unevaluated_messages:
            return [
                DAOProposalEvaluationResult(
                    success=True,
                    message=f"All {message_count} proposals already evaluated",
                    proposals_processed=message_count,
                    proposals_evaluated=0,
                )
            ]

        # Process only unevaluated messages concurrently
        max_concurrent = min(
            self.get_max_concurrent_evaluations(context), len(unevaluated_messages)
        )
        semaphore = asyncio.Semaphore(max_concurrent)

        logger.info(
            f"Processing {len(unevaluated_messages)} unevaluated messages "
            f"(skipped {skipped_count} already evaluated) "
            f"with max {max_concurrent} concurrent evaluations"
        )

        # Create tasks for concurrent processing (using only unevaluated messages)
        tasks = [
            self.process_message_with_semaphore(semaphore, message)
            for message in unevaluated_messages
        ]

        # Execute all tasks concurrently and collect results
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        execution_time = time.time() - start_time

        logger.info(
            f"Completed concurrent processing of {len(unevaluated_messages)} messages in {execution_time:.2f} seconds"
        )

        # Process results
        processed_count = len(results)
        evaluated_count = 0
        errors = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error_msg = f"Exception processing message {unevaluated_messages[i].id}: {str(result)}"
                logger.error(error_msg, exc_info=True)
                errors.append(error_msg)
            elif isinstance(result, dict):
                if result.get("success"):
                    # All processed messages should be evaluations (no skipped since pre-filtered)
                    evaluated_count += 1
                else:
                    errors.append(result.get("error", "Unknown error"))
            else:
                error_msg = f"Unexpected result type for message {unevaluated_messages[i].id}: {type(result)}"
                logger.error(error_msg)
                errors.append(error_msg)

        logger.debug(
            f"Task metrics - Processed: {processed_count}, "
            f"Evaluated: {evaluated_count}, Errors: {len(errors)}"
        )

        return [
            DAOProposalEvaluationResult(
                success=True,
                message=f"Processed {processed_count} proposal(s), evaluated {evaluated_count} proposal(s), skipped {skipped_count} already evaluated",
                proposals_processed=message_count,  # Total messages including skipped
                proposals_evaluated=evaluated_count,
                errors=errors,
            )
        ]


# Instantiate the task for use in the registry
dao_proposal_evaluation = DAOProposalEvaluationTask()
