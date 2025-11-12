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
    evaluate_proposal_strict,
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
        3  # Limit concurrent evaluations to avoid rate limits
    )

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate task-specific conditions."""
        try:
            # Get pending messages from the queue
            pending_messages = await self.get_pending_messages()
            message_count = len(pending_messages)
            logger.debug(
                "Found pending proposal evaluation messages",
                extra={
                    "task": "dao_proposal_evaluation",
                    "message_count": message_count,
                },
            )

            if message_count == 0:
                logger.debug(
                    "No pending messages found",
                    extra={"task": "dao_proposal_evaluation"},
                )
                return False

            # Validate that at least one message has a valid proposal
            for message in pending_messages:
                message_data = message.message or {}
                proposal_id = message_data.get("proposal_id")

                if not proposal_id:
                    logger.warning(
                        "Message missing proposal_id",
                        extra={
                            "task": "dao_proposal_evaluation",
                            "message_id": str(message.id),
                        },
                    )
                    continue

                # Check if the proposal exists in the database
                proposal = backend.get_proposal(proposal_id)
                if proposal:
                    logger.debug(
                        "Found valid proposal to process",
                        extra={
                            "task": "dao_proposal_evaluation",
                            "proposal_id": str(proposal_id),
                        },
                    )
                    return True
                else:
                    logger.warning(
                        "Proposal not found in database",
                        extra={
                            "task": "dao_proposal_evaluation",
                            "proposal_id": str(proposal_id),
                        },
                    )

            logger.warning(
                "No valid proposals found in pending messages",
                extra={"task": "dao_proposal_evaluation"},
            )
            return False

        except Exception as e:
            logger.error(
                "Error validating task",
                extra={"task": "dao_proposal_evaluation", "error": str(e)},
                exc_info=True,
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
                        "Found existing evaluation for proposal",
                        extra={
                            "task": "dao_proposal_evaluation",
                            "proposal_id": str(proposal_id),
                        },
                    )
                    return True

            return False

        except Exception as e:
            logger.error(
                "Error checking if proposal was evaluated",
                extra={
                    "task": "dao_proposal_evaluation",
                    "proposal_id": str(proposal_id),
                    "error": str(e),
                },
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
                    logger.warning(
                        "Invalid UUID in message",
                        extra={
                            "task": "dao_proposal_evaluation",
                            "message_id": str(message.id),
                            "error": str(e),
                        },
                    )
                    continue

        if not proposal_wallet_pairs:
            logger.debug(
                "No valid proposal-wallet pairs found in messages",
                extra={"task": "dao_proposal_evaluation"},
            )
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
                logger.info(
                    "Skipped already-evaluated proposals",
                    extra={
                        "task": "dao_proposal_evaluation",
                        "skipped_count": skipped_count,
                    },
                )

            logger.info(
                "Filtered to unevaluated proposals",
                extra={
                    "task": "dao_proposal_evaluation",
                    "unevaluated_count": len(unevaluated_messages),
                    "total_messages": len(messages),
                },
            )
            return unevaluated_messages

        except Exception as e:
            logger.error(
                "Error in batch evaluation check",
                extra={"task": "dao_proposal_evaluation", "error": str(e)},
            )
            # Fallback to original behavior if batch check fails
            logger.warning(
                "Falling back to individual evaluation checks",
                extra={"task": "dao_proposal_evaluation"},
            )
            return messages

    async def process_message_v2(self, message: QueueMessage) -> Dict[str, Any]:
        """Simplified v2 processing for a single DAO proposal evaluation message.

        Uses the new evaluate_proposal_strict flow for streamlined evaluation.
        Relies on evaluation function for proposal/DAO lookups and validation.
        """
        message_id = message.id
        message_data = message.message or {}
        wallet_id = message.wallet_id
        dao_id = message.dao_id
        proposal_id = message_data.get("proposal_id")

        if not proposal_id:
            error_msg = f"Missing proposal_id in message {message_id}"
            logger.error(
                "Missing proposal_id in message (v2)",
                extra={
                    "task": "dao_proposal_evaluation",
                    "message_id": str(message_id),
                },
            )
            return {"success": False, "error": error_msg}

        if not dao_id:
            error_msg = f"Missing dao_id in message {message_id}"
            logger.error(
                "Missing dao_id in message (v2)",
                extra={
                    "task": "dao_proposal_evaluation",
                    "message_id": str(message_id),
                },
            )
            return {"success": False, "error": error_msg}

        logger.debug(
            "Processing proposal evaluation message (v2)",
            extra={
                "task": "dao_proposal_evaluation",
                "message_id": str(message_id),
                "wallet_id": str(wallet_id),
                "proposal_id": str(proposal_id),
                "dao_id": str(dao_id),
            },
        )

        try:
            # Execute the simplified proposal evaluation workflow
            # (handles internal proposal/DAO fetches and validation)
            logger.info(
                "Evaluating proposal (v2)",
                extra={
                    "task": "dao_proposal_evaluation",
                    "proposal_id": str(proposal_id),
                    "dao_id": str(dao_id),
                },
            )

            evaluation_output = await evaluate_proposal_strict(
                proposal_id=proposal_id,
            )

            if not evaluation_output:
                error_msg = f"Evaluation failed for proposal {proposal_id}"
                logger.error(
                    "Evaluation returned None (v2)",
                    extra={
                        "task": "dao_proposal_evaluation",
                        "proposal_id": str(proposal_id),
                    },
                )
                return {"success": False, "error": error_msg}

            # Map EvaluationOutput to legacy structures
            evaluation_data = evaluation_output.model_dump()

            # Map decision ("APPROVE"/"REJECT") to boolean
            decision_str = evaluation_data.get("decision", "REJECT")
            approval = decision_str == "APPROVE"

            overall_score = evaluation_data.get("final_score", 0)
            confidence = evaluation_data.get("confidence", 0.0)

            # Build reasoning from category reasons
            categories_data = {
                "current_order": evaluation_data.get("current_order", {}),
                "mission": evaluation_data.get("mission", {}),
                "value": evaluation_data.get("value", {}),
                "values": evaluation_data.get("values", {}),
                "originality": evaluation_data.get("originality", {}),
                "clarity": evaluation_data.get("clarity", {}),
                "safety": evaluation_data.get("safety", {}),
                "growth": evaluation_data.get("growth", {}),
            }

            # Compile reasoning from all categories
            reasoning_parts = []
            for cat_name, cat_data in categories_data.items():
                if isinstance(cat_data, dict) and cat_data.get("reason"):
                    reasoning_parts.append(
                        f"{cat_name.replace('_', ' ').title()}: {cat_data.get('reason')}"
                    )

            reasoning = (
                "\n\n".join(reasoning_parts)
                if reasoning_parts
                else "No reasoning provided"
            )

            # Add failed gates to reasoning if present
            failed_gates = evaluation_data.get("failed", [])
            if failed_gates:
                reasoning += f"\n\nFailed Gates: {', '.join(failed_gates)}"

            formatted_prompt = ""  # Not tracked in v2
            total_cost = 0.0  # Token usage not tracked in v2
            model = "x-ai/grok-4-fast"  # Default model in v2

            # Convert categories to evaluation_scores format
            evaluation_scores = {
                "categories": [
                    {
                        "category": cat_name,
                        "score": cat_data.get("score", 0),
                        "weight": 0,  # Weights not in v2 schema
                        "reasoning": cat_data.get("reason", ""),
                        "evidence": cat_data.get("evidence", []),
                    }
                    for cat_name, cat_data in categories_data.items()
                    if isinstance(cat_data, dict)
                ],
                "final_score": overall_score,
                "confidence": confidence,
                "decision": decision_str,
            }

            evaluation_flags = failed_gates

            logger.info(
                "Proposal evaluated (v2)",
                extra={
                    "task": "dao_proposal_evaluation",
                    "proposal_id": str(proposal_id),
                    "result": "FOR" if approval else "AGAINST",
                    "score": overall_score,
                },
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
                confidence=confidence,  # Already 0.0-1.0 in v2
                prompt=formatted_prompt,
                cost=total_cost,
                model=model,
                profile_id=wallet.profile_id if wallet else None,
                evaluation_score=evaluation_scores,  # Store the complete evaluation scores with evidence
                flags=evaluation_flags,  # Store the failed gates as flags
                evaluation=evaluation_data,  # Store the complete v2 evaluation structure
            )

            # Create the vote record
            vote = backend.create_vote(vote_data)
            if not vote:
                logger.error(
                    "Failed to create vote record (v2)",
                    extra={"task": "dao_proposal_evaluation"},
                )
                return {"success": False, "error": "Failed to create vote record"}

            logger.info(
                "Created vote record (v2)",
                extra={
                    "task": "dao_proposal_evaluation",
                    "vote_id": str(vote.id),
                    "proposal_id": str(proposal_id),
                },
            )

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
            error_msg = f"Error processing message {message_id} (v2): {str(e)}"
            logger.error(
                "Error processing message (v2)",
                extra={
                    "task": "dao_proposal_evaluation",
                    "message_id": str(message_id),
                    "error": str(e),
                },
                exc_info=True,
            )
            update_data = QueueMessageBase(
                is_processed=True,
                result={
                    "success": False,
                    "error": error_msg,
                },
            )
            backend.update_queue_message(message_id, update_data)

            return {"success": False, "error": error_msg}

    async def process_message(self, message: QueueMessage) -> Dict[str, Any]:
        """Process a single DAO proposal evaluation message."""
        message_id = message.id
        message_data = message.message or {}
        wallet_id = message.wallet_id
        dao_id = message.dao_id

        logger.debug(
            "Processing proposal evaluation message",
            extra={
                "task": "dao_proposal_evaluation",
                "message_id": str(message_id),
                "wallet_id": str(wallet_id),
            },
        )

        # Get the proposal ID from the message
        proposal_id = message_data.get("proposal_id")
        if not proposal_id:
            error_msg = f"Missing proposal_id in message {message_id}"
            logger.error(
                "Missing proposal_id in message",
                extra={
                    "task": "dao_proposal_evaluation",
                    "message_id": str(message_id),
                },
            )
            return {"success": False, "error": error_msg}

        try:
            # Get the proposal details from the database
            proposal = backend.get_proposal(proposal_id)
            if not proposal:
                error_msg = f"Proposal {proposal_id} not found in database"
                logger.error(
                    "Proposal not found in database",
                    extra={
                        "task": "dao_proposal_evaluation",
                        "proposal_id": str(proposal_id),
                    },
                )
                return {"success": False, "error": error_msg}

            # Note: Individual evaluation check removed here as it's now handled
            # in batch during the pre-filtering phase in _execute_impl
            # This significantly reduces database queries and log spam

            # Get the DAO information
            dao = backend.get_dao(dao_id) if dao_id else None
            if not dao:
                error_msg = f"DAO not found for proposal {proposal_id}"
                logger.error(
                    "DAO not found for proposal",
                    extra={
                        "task": "dao_proposal_evaluation",
                        "proposal_id": str(proposal_id),
                    },
                )
                return {"success": False, "error": error_msg}

            # Execute the proposal evaluation workflow using OpenRouter v2
            logger.info(
                "Evaluating proposal",
                extra={
                    "task": "dao_proposal_evaluation",
                    "proposal_id": str(proposal.id),
                    "dao_name": dao.name,
                },
            )

            evaluation = await evaluate_proposal_comprehensive(
                dao_id=dao_id,
                proposal_id=proposal.id,
                streaming=False,
            )

            # Extract evaluation results from OpenRouter v2 structure
            evaluation_data = evaluation.get("evaluation", {})

            # Map v2 decision ("APPROVE"/"REJECT") to boolean
            decision_str = evaluation_data.get("decision", "REJECT")
            approval = decision_str == "APPROVE"

            overall_score = evaluation_data.get("final_score", 0)
            confidence = evaluation_data.get("confidence", 0.0)

            # Build reasoning from category reasons
            categories_data = {
                "current_order": evaluation_data.get("current_order", {}),
                "mission": evaluation_data.get("mission", {}),
                "value": evaluation_data.get("value", {}),
                "values": evaluation_data.get("values", {}),
                "originality": evaluation_data.get("originality", {}),
                "clarity": evaluation_data.get("clarity", {}),
                "safety": evaluation_data.get("safety", {}),
                "growth": evaluation_data.get("growth", {}),
            }

            # Compile reasoning from all categories
            reasoning_parts = []
            for cat_name, cat_data in categories_data.items():
                if isinstance(cat_data, dict) and cat_data.get("reason"):
                    reasoning_parts.append(
                        f"{cat_name.replace('_', ' ').title()}: {cat_data.get('reason')}"
                    )

            reasoning = (
                "\n\n".join(reasoning_parts)
                if reasoning_parts
                else "No reasoning provided"
            )

            # Add failed gates to reasoning if present
            failed_gates = evaluation_data.get("failed", [])
            if failed_gates:
                reasoning += f"\n\nFailed Gates: {', '.join(failed_gates)}"

            formatted_prompt = ""  # Not available in OpenRouter v2
            total_cost = 0.0  # Token usage not tracked in v2
            model = "x-ai/grok-2-1212"  # Default model used in v2

            # Convert v2 categories to evaluation_scores format
            evaluation_scores = {
                "categories": [
                    {
                        "category": cat_name,
                        "score": cat_data.get("score", 0),
                        "weight": 0,  # Weights not in v2 schema
                        "reasoning": cat_data.get("reason", ""),
                        "evidence": cat_data.get("evidence", []),
                    }
                    for cat_name, cat_data in categories_data.items()
                    if isinstance(cat_data, dict)
                ],
                "final_score": overall_score,
                "confidence": confidence,
                "decision": decision_str,
            }

            evaluation_flags = failed_gates

            logger.info(
                "Proposal evaluated",
                extra={
                    "task": "dao_proposal_evaluation",
                    "proposal_id": str(proposal.id),
                    "dao_name": dao.name,
                    "result": "FOR" if approval else "AGAINST",
                    "score": overall_score,
                },
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
                confidence=confidence,  # Use confidence from v2 (already 0.0-1.0)
                prompt=formatted_prompt,
                cost=total_cost,
                model=model,
                profile_id=wallet.profile_id if wallet else None,
                evaluation_score=evaluation_scores,  # Store the complete evaluation scores with evidence
                flags=evaluation_flags,  # Store the failed gates as flags
                evaluation=evaluation_data,  # Store the complete v2 evaluation structure
            )

            # Create the vote record
            vote = backend.create_vote(vote_data)
            if not vote:
                logger.error(
                    "Failed to create vote record",
                    extra={"task": "dao_proposal_evaluation"},
                )
                return {"success": False, "error": "Failed to create vote record"}

            logger.info(
                "Created vote record",
                extra={
                    "task": "dao_proposal_evaluation",
                    "vote_id": str(vote.id),
                    "proposal_id": str(proposal_id),
                },
            )

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
            logger.error(
                "Error processing message",
                extra={
                    "task": "dao_proposal_evaluation",
                    "message_id": str(message_id),
                    "error": str(e),
                },
                exc_info=True,
            )
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
                # TODO: using v2 now can deprecate v1 if works
                return await self.process_message_v2(message)
            except Exception as e:
                # Log the error and return a failure result instead of raising
                # This prevents one failed message from crashing the entire batch
                error_msg = f"Failed to process message {message.id}: {str(e)}"
                logger.error(
                    "Failed to process message",
                    extra={
                        "task": "dao_proposal_evaluation",
                        "message_id": str(message.id),
                        "error": str(e),
                    },
                    exc_info=True,
                )
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
            logger.debug(
                "Using context-provided concurrency limit",
                extra={"task": "dao_proposal_evaluation", "limit": context_limit},
            )
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
        logger.debug(
            "Found pending proposal evaluation messages",
            extra={"task": "dao_proposal_evaluation", "message_count": message_count},
        )

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
            "Processing unevaluated messages with concurrency",
            extra={
                "task": "dao_proposal_evaluation",
                "unevaluated_count": len(unevaluated_messages),
                "skipped_count": skipped_count,
                "max_concurrent": max_concurrent,
            },
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
            "Completed concurrent processing",
            extra={
                "task": "dao_proposal_evaluation",
                "message_count": len(unevaluated_messages),
                "execution_time": round(execution_time, 2),
            },
        )

        # Process results
        processed_count = len(results)
        evaluated_count = 0
        errors = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error_msg = f"Exception processing message {unevaluated_messages[i].id}: {str(result)}"
                logger.error(
                    "Exception processing message",
                    extra={
                        "task": "dao_proposal_evaluation",
                        "message_id": str(unevaluated_messages[i].id),
                        "error": str(result),
                    },
                    exc_info=True,
                )
                errors.append(error_msg)
            elif isinstance(result, dict):
                if result.get("success"):
                    # All processed messages should be evaluations (no skipped since pre-filtered)
                    evaluated_count += 1
                else:
                    errors.append(result.get("error", "Unknown error"))
            else:
                error_msg = f"Unexpected result type for message {unevaluated_messages[i].id}: {type(result)}"
                logger.error(
                    "Unexpected result type",
                    extra={
                        "task": "dao_proposal_evaluation",
                        "message_id": str(unevaluated_messages[i].id),
                        "result_type": str(type(result)),
                    },
                )
                errors.append(error_msg)

        logger.info(
            "Task completed",
            extra={
                "task": "dao_proposal_evaluation",
                "processed": processed_count,
                "evaluated": evaluated_count,
                "errors": len(errors),
            },
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
