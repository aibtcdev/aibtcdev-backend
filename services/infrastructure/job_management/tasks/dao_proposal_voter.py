"""DAO proposal voter task implementation."""

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from backend.factory import backend
from backend.models import (
    UUID,
    QueueMessage,
    QueueMessageBase,
    QueueMessageFilter,
    QueueMessageType,
    VoteBase,
    VoteFilter,
)
from config import config
from lib.logger import configure_logger
from services.infrastructure.job_management.base import (
    BaseTask,
    JobContext,
    RunnerResult,
)
from services.infrastructure.job_management.decorators import JobPriority, job
from tools.dao_ext_action_proposals import VoteOnActionProposalTool

logger = configure_logger(__name__)


@dataclass
class DAOProposalVoteResult(RunnerResult):
    """Result of DAO proposal voting operation."""

    proposals_processed: int = 0
    proposals_voted: int = 0
    votes_cast: int = 0
    errors: List[str] = None

    def __post_init__(self):
        self.errors = self.errors or []


@job(
    job_type="dao_proposal_vote",
    name="DAO Proposal Voter",
    description="Processes and votes on DAO proposals with enhanced monitoring and error handling",
    interval_seconds=30,
    priority=JobPriority.HIGH,
    max_retries=2,
    retry_delay_seconds=60,
    timeout_seconds=300,
    max_concurrent=1,
    requires_blockchain=True,
    batch_size=3,
    enable_dead_letter_queue=True,
)
class DAOProposalVoterTask(BaseTask[DAOProposalVoteResult]):
    """Task runner for processing and voting on DAO proposals with enhanced capabilities."""

    QUEUE_TYPE = QueueMessageType.get_or_create("dao_proposal_vote")

    async def get_pending_messages(self) -> List[QueueMessage]:
        """Get all unprocessed DAO proposal vote messages from the queue."""
        filters = QueueMessageFilter(type=self.QUEUE_TYPE, is_processed=False)
        return backend.list_queue_messages(filters=filters)

    async def _validate_config(self, context: JobContext) -> bool:
        """Validate task configuration."""
        try:
            # Check if voting tool can be initialized
            if not config.scheduler:
                logger.error("Scheduler config not available")
                return False
            return True
        except Exception as e:
            logger.error(
                f"Error validating proposal voter config: {str(e)}", exc_info=True
            )
            return False

    async def _validate_resources(self, context: JobContext) -> bool:
        """Validate resource availability."""
        try:
            return True
        except Exception as e:
            logger.error(f"Backend not available: {str(e)}")
            return False

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate that we have pending messages to process."""
        try:
            pending_messages = await self.get_pending_messages()

            if not pending_messages:
                logger.info("No pending DAO proposal vote messages to process")
                return False

            # Validate each message has required data
            valid_messages = []
            for message in pending_messages:
                if await self._is_message_valid(message):
                    valid_messages.append(message)

            if valid_messages:
                logger.info(
                    f"Found {len(valid_messages)} valid DAO proposal vote messages"
                )
                return True

            logger.info("No valid DAO proposal vote messages to process")
            return False

        except Exception as e:
            logger.error(
                f"Error validating proposal voter task: {str(e)}", exc_info=True
            )
            return False

    async def _is_message_valid(self, message: QueueMessage) -> bool:
        """Check if a proposal vote message is valid for processing."""
        try:
            if not message.wallet_id or not message.message:
                return False

            proposal_id = message.message.get("proposal_id")
            if not proposal_id:
                return False

            # Check if proposal exists
            try:
                proposal_uuid = UUID(proposal_id)
                proposal = backend.get_proposal(proposal_uuid)
                if not proposal:
                    return False
            except (ValueError, Exception):
                return False

            return True
        except Exception:
            return False

    async def _process_message(self, message: QueueMessage) -> Dict[str, Any]:
        """Process a single DAO proposal voting message with enhanced error handling."""
        message_id = message.id
        message_data = message.message or {}
        wallet_id = message.wallet_id

        logger.debug(
            f"Processing proposal voting message {message_id} for wallet {wallet_id}"
        )

        # Get the proposal ID from the message (this should be the database UUID)
        proposal_id = message_data.get("proposal_id")
        if not proposal_id:
            error_msg = f"Missing proposal_id in message {message_id}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        try:
            # Convert string UUID to UUID object
            try:
                proposal_uuid = UUID(proposal_id)
            except ValueError:
                error_msg = (
                    f"Invalid proposal_id format {proposal_id} in message {message_id}"
                )
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

            # Get the proposal by its database ID
            proposal = backend.get_proposal(proposal_uuid)
            if not proposal:
                error_msg = f"Proposal {proposal_id} not found in database"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

            # Get the wallet
            wallet = backend.get_wallet(wallet_id)
            if not wallet:
                error_msg = f"Wallet {wallet_id} not found"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

            # Get unvoted votes for this specific proposal and wallet
            votes = backend.list_votes(
                VoteFilter(proposal_id=proposal_uuid, wallet_id=wallet_id)
            )
            if not votes:
                error_msg = (
                    f"No votes found for proposal {proposal_id} and wallet {wallet_id}"
                )
                logger.warning(error_msg)
                return {
                    "success": True,
                    "message": "No votes to process",
                    "votes_processed": 0,
                }

            # Filter out already voted votes
            unvoted_votes = [vote for vote in votes if not vote.voted]

            if not unvoted_votes:
                error_msg = f"No unvoted votes found for proposal {proposal_id} and wallet {wallet_id}"
                logger.warning(error_msg)
                return {
                    "success": True,
                    "message": "No votes to process",
                    "votes_processed": 0,
                }

            logger.info(
                f"Found {len(unvoted_votes)} unvoted votes for proposal {proposal_id} and wallet {wallet_id}"
            )

            # Initialize the voting tool
            voting_tool = VoteOnActionProposalTool(wallet_id=wallet_id)

            # Process each unvoted vote
            results = []
            for vote in unvoted_votes:
                # Submit the vote
                vote_result = await voting_tool._arun(
                    dao_action_proposal_voting_contract=proposal.contract_principal,
                    proposal_id=proposal.proposal_id,
                    vote_for=vote.answer,
                )

                if not vote_result.get("success", False):
                    error_msg = f"Failed to submit vote {vote.id}: {vote_result.get('message', 'Unknown error')}"
                    logger.error(error_msg)
                    results.append(
                        {"success": False, "error": error_msg, "vote_id": vote.id}
                    )
                    continue

                try:
                    # Parse the output JSON string
                    output_data = (
                        json.loads(vote_result["output"])
                        if isinstance(vote_result["output"], str)
                        else vote_result["output"]
                    )
                    # Get the transaction ID from the nested data structure
                    tx_id = output_data.get("data", {}).get("txid")

                    if not tx_id:
                        logger.warning(f"No txid found in parsed output: {output_data}")
                        results.append(
                            {
                                "success": False,
                                "error": "No transaction ID found in response",
                                "vote_id": vote.id,
                                "vote_result": vote_result,
                            }
                        )
                        continue

                except (json.JSONDecodeError, KeyError) as e:
                    logger.error(f"Error parsing vote result output: {str(e)}")
                    results.append(
                        {
                            "success": False,
                            "error": f"Failed to parse vote result: {str(e)}",
                            "vote_id": vote.id,
                            "vote_result": vote_result,
                        }
                    )
                    continue

                # Get the correct address based on network configuration
                address = (
                    wallet.mainnet_address
                    if config.network.network == "mainnet"
                    else wallet.testnet_address
                )

                vote_data = VoteBase(
                    tx_id=tx_id,
                    voted=True,
                    address=address,
                    profile_id=wallet.profile_id,
                )

                try:
                    updated_vote = backend.update_vote(vote.id, vote_data)
                    if updated_vote:
                        logger.info(
                            f"Successfully updated vote {vote.id} with transaction ID {tx_id}"
                        )
                        results.append(
                            {
                                "success": True,
                                "vote_id": vote.id,
                                "tx_id": tx_id,
                            }
                        )
                    else:
                        logger.error(
                            f"Failed to update vote {vote.id} - update_vote returned None"
                        )
                        results.append(
                            {
                                "success": False,
                                "error": "Failed to update vote in database",
                                "vote_id": vote.id,
                            }
                        )
                except Exception as e:
                    logger.error(
                        f"Error updating vote {vote.id}: {str(e)}", exc_info=True
                    )
                    results.append(
                        {
                            "success": False,
                            "error": f"Failed to update vote: {str(e)}",
                            "vote_id": vote.id,
                        }
                    )

            # Mark the message as processed ONLY if ALL votes were handled successfully
            successful_votes = len([r for r in results if r["success"]])
            if successful_votes == len(results) and successful_votes > 0:
                result = {
                    "success": True,
                    "votes_processed": successful_votes,
                    "votes_failed": len(results) - successful_votes,
                    "results": results,
                }
                update_data = QueueMessageBase(is_processed=True, result=result)
                backend.update_queue_message(message_id, update_data)
                logger.info(
                    f"Successfully processed all {successful_votes} votes for message {message_id} - marking as processed"
                )
            elif successful_votes > 0:
                result = {
                    "success": False,
                    "votes_processed": successful_votes,
                    "votes_failed": len(results) - successful_votes,
                    "results": results,
                    "message": "Partial success - some votes failed",
                }
                update_data = QueueMessageBase(result=result)
                backend.update_queue_message(message_id, update_data)
                logger.warning(
                    f"Only {successful_votes}/{len(results)} votes succeeded for message {message_id} - leaving unprocessed for retry"
                )
            else:
                result = {
                    "success": False,
                    "votes_processed": 0,
                    "votes_failed": len(results),
                    "results": results,
                    "message": "All votes failed",
                }
                update_data = QueueMessageBase(result=result)
                backend.update_queue_message(message_id, update_data)
                logger.error(
                    f"No votes succeeded for message {message_id} - leaving unprocessed for retry"
                )

            return {
                "success": True,
                "votes_processed": successful_votes,
                "votes_failed": len(results) - successful_votes,
                "results": results,
            }

        except Exception as e:
            error_msg = f"Error processing message {message_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            result = {"success": False, "error": error_msg}

            # Store result even for failed processing
            update_data = QueueMessageBase(result=result)
            backend.update_queue_message(message_id, update_data)

            return result

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
        if "invalid" in str(error).lower() and "format" in str(error).lower():
            return False

        return isinstance(error, retry_errors)

    async def _handle_execution_error(
        self, error: Exception, context: JobContext
    ) -> Optional[List[DAOProposalVoteResult]]:
        """Handle execution errors with recovery logic."""
        if "blockchain" in str(error).lower() or "proposal" in str(error).lower():
            logger.warning(f"Blockchain/proposal error: {str(error)}, will retry")
            return None

        if isinstance(error, (ConnectionError, TimeoutError)):
            logger.warning(f"Network error: {str(error)}, will retry")
            return None

        # For validation errors, don't retry
        return [
            DAOProposalVoteResult(
                success=False,
                message=f"Unrecoverable error: {str(error)}",
                error=error,
            )
        ]

    async def _post_execution_cleanup(
        self, context: JobContext, results: List[DAOProposalVoteResult]
    ) -> None:
        """Cleanup after task execution."""
        logger.debug("DAO proposal voter task cleanup completed")

    async def _execute_impl(self, context: JobContext) -> List[DAOProposalVoteResult]:
        """Run the DAO proposal voter task by processing each message with batch processing."""
        # Get pending messages
        pending_messages = await self.get_pending_messages()

        if not pending_messages:
            return [
                DAOProposalVoteResult(
                    success=True,
                    message="No pending messages found",
                    proposals_processed=0,
                    proposals_voted=0,
                )
            ]

        message_count = len(pending_messages)
        logger.info(f"Processing {message_count} pending proposal voting messages")

        # Process each message
        processed_count = 0
        total_votes_processed = 0
        total_votes_cast = 0
        errors = []
        batch_size = getattr(context, "batch_size", 3)

        # Process messages in batches
        for i in range(0, len(pending_messages), batch_size):
            batch = pending_messages[i : i + batch_size]

            for message in batch:
                try:
                    result = await self._process_message(message)
                    processed_count += 1

                    if result.get("success"):
                        votes_processed = result.get("votes_processed", 0)
                        total_votes_processed += votes_processed
                        if votes_processed > 0:
                            total_votes_cast += votes_processed
                        logger.debug(
                            f"Message {message.id}: processed {votes_processed} votes"
                        )
                    else:
                        error_msg = result.get("error", "Unknown error")
                        errors.append(f"Message {message.id}: {error_msg}")
                        logger.error(
                            f"Failed to process message {message.id}: {error_msg}"
                        )

                except Exception as e:
                    error_msg = f"Exception processing message {message.id}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg, exc_info=True)

        logger.info(
            f"DAO proposal voter task completed - Processed: {processed_count}/{message_count} messages, "
            f"Votes cast: {total_votes_cast}, Errors: {len(errors)}"
        )

        return [
            DAOProposalVoteResult(
                success=True,
                message=f"Processed {processed_count} message(s), voted on {total_votes_cast} vote(s)",
                proposals_processed=processed_count,
                proposals_voted=total_votes_processed,
                votes_cast=total_votes_cast,
                errors=errors,
            )
        ]


# Create instance for auto-registration
dao_proposal_voter = DAOProposalVoterTask()
