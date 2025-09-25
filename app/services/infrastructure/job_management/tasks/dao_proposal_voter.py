"""DAO proposal voter task implementation."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.backend.factory import backend
from app.backend.models import (
    UUID,
    QueueMessage,
    QueueMessageBase,
    QueueMessageFilter,
    QueueMessageType,
    VoteBase,
    VoteFilter,
)
from app.config import config
from app.lib.logger import configure_logger
from app.services.infrastructure.job_management.base import (
    BaseTask,
    JobContext,
    RunnerResult,
)
from app.services.infrastructure.job_management.decorators import JobPriority, job
from app.tools.agent_account_action_proposals import (
    AgentAccountVoteOnActionProposalTool,
)

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
    MAX_MESSAGE_RETRIES = 3

    def _get_current_retry_count(self, message: QueueMessage) -> int:
        return message.result.get("retry_count", 0) if message.result else 0

    async def get_pending_messages(self) -> List[QueueMessage]:
        """Get all unprocessed DAO proposal vote messages from the queue."""
        filters = QueueMessageFilter(type=self.QUEUE_TYPE, is_processed=False)
        return backend.list_queue_messages(filters=filters)

    async def _validate_config(self, context: JobContext) -> bool:
        """Validate task configuration."""
        try:
            # Check if voting tool can be initialized
            if not config.scheduler:
                logger.error(
                    "Scheduler config not available",
                    extra={"task": "dao_proposal_voter", "validation": "config"},
                )
                return False
            return True
        except Exception as e:
            logger.error(
                "Error validating proposal voter config",
                extra={"task": "dao_proposal_voter", "error": str(e)},
                exc_info=True,
            )
            return False

    async def _validate_resources(self, context: JobContext) -> bool:
        """Validate resource availability."""
        try:
            return True
        except Exception as e:
            logger.error(
                "Backend not available",
                extra={"task": "dao_proposal_voter", "error": str(e)},
            )
            return False

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate that we have pending messages to process."""
        try:
            pending_messages = await self.get_pending_messages()

            if not pending_messages:
                logger.info(
                    "No pending DAO proposal vote messages to process",
                    extra={"task": "dao_proposal_voter"},
                )
                return False

            # Validate each message has required data
            valid_messages = []
            for message in pending_messages:
                if await self._is_message_valid(message):
                    valid_messages.append(message)

            if valid_messages:
                logger.info(
                    "Found valid DAO proposal vote messages",
                    extra={
                        "task": "dao_proposal_voter",
                        "valid_message_count": len(valid_messages),
                    },
                )
                return True

            logger.info(
                "No valid DAO proposal vote messages to process",
                extra={"task": "dao_proposal_voter"},
            )
            return False

        except Exception as e:
            logger.error(
                "Error validating proposal voter task",
                extra={"task": "dao_proposal_voter", "error": str(e)},
                exc_info=True,
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
            "Processing proposal voting message",
            extra={
                "task": "dao_proposal_voter",
                "message_id": message_id,
                "wallet_id": wallet_id,
            },
        )

        # Get the proposal ID from the message (this should be the database UUID)
        proposal_id = message_data.get("proposal_id")
        if not proposal_id:
            error_msg = "Missing proposal_id in message"
            logger.error(
                error_msg,
                extra={"task": "dao_proposal_voter", "message_id": message_id},
            )
            return {
                "success": False,
                "error": error_msg,
                "error_type": "missing_proposal_id",
                "message_id": message_id,
                "wallet_id": wallet_id,
                "status": "failed",
            }

        try:
            # Convert string UUID to UUID object
            try:
                proposal_uuid = UUID(proposal_id)
            except ValueError:
                error_msg = "Invalid proposal_id format"
                logger.error(
                    error_msg,
                    extra={
                        "task": "dao_proposal_voter",
                        "proposal_id": proposal_id,
                        "message_id": message_id,
                    },
                )
                return {
                    "success": False,
                    "error": error_msg,
                    "error_type": "invalid_proposal_id_format",
                    "proposal_id": proposal_id,
                    "message_id": message_id,
                    "wallet_id": wallet_id,
                    "status": "failed",
                }

            # Get the proposal by its database ID
            proposal = backend.get_proposal(proposal_uuid)
            if not proposal:
                error_msg = "Proposal not found in database"
                logger.error(
                    error_msg,
                    extra={"task": "dao_proposal_voter", "proposal_id": proposal_id},
                )
                return {
                    "success": False,
                    "error": error_msg,
                    "error_type": "proposal_not_found",
                    "proposal_id": proposal_id,
                    "message_id": message_id,
                    "wallet_id": wallet_id,
                    "status": "failed",
                }

            # Get the wallet
            wallet = backend.get_wallet(wallet_id)
            if not wallet:
                error_msg = "Wallet not found"
                logger.error(
                    error_msg,
                    extra={"task": "dao_proposal_voter", "wallet_id": wallet_id},
                )
                return {
                    "success": False,
                    "error": error_msg,
                    "error_type": "wallet_not_found",
                    "wallet_id": wallet_id,
                    "message_id": message_id,
                    "status": "failed",
                }

            # Get unvoted votes for this specific proposal and wallet
            votes = backend.list_votes(
                VoteFilter(proposal_id=proposal_uuid, wallet_id=wallet_id)
            )
            if not votes:
                error_msg = "No votes found for proposal and wallet"
                logger.warning(
                    error_msg,
                    extra={
                        "task": "dao_proposal_voter",
                        "proposal_id": proposal_id,
                        "wallet_id": wallet_id,
                    },
                )
                result = {
                    "success": True,
                    "message": "No votes to process",
                    "votes_processed": 0,
                    "proposal_id": proposal_id,
                    "wallet_id": wallet_id,
                    "message_id": message_id,
                    "status": "completed_no_votes",
                }
                # Mark message as processed to avoid endless retries
                update_data = QueueMessageBase(is_processed=True, result=result)
                backend.update_queue_message(message_id, update_data)
                return result

            # Filter out already voted votes
            unvoted_votes = [vote for vote in votes if not vote.voted]

            if not unvoted_votes:
                error_msg = "No unvoted votes found for proposal and wallet"
                logger.warning(
                    error_msg,
                    extra={
                        "task": "dao_proposal_voter",
                        "proposal_id": proposal_id,
                        "wallet_id": wallet_id,
                    },
                )
                result = {
                    "success": True,
                    "message": "No votes to process",
                    "votes_processed": 0,
                    "proposal_id": proposal_id,
                    "wallet_id": wallet_id,
                    "message_id": message_id,
                    "status": "completed_no_unvoted",
                }
                # Mark message as processed to avoid endless retries
                update_data = QueueMessageBase(is_processed=True, result=result)
                backend.update_queue_message(message_id, update_data)
                return result

            logger.info(
                "Found unvoted votes for proposal and wallet",
                extra={
                    "task": "dao_proposal_voter",
                    "unvoted_vote_count": len(unvoted_votes),
                    "proposal_id": proposal_id,
                    "wallet_id": wallet_id,
                },
            )

            # Get the agent to access the account contract
            if not wallet.agent_id:
                error_msg = "Wallet is not associated with an agent"
                logger.error(
                    error_msg,
                    extra={"task": "dao_proposal_voter", "wallet_id": wallet_id},
                )
                return {
                    "success": False,
                    "error": error_msg,
                    "error_type": "wallet_no_agent",
                    "wallet_id": wallet_id,
                    "message_id": message_id,
                    "status": "failed",
                }

            agent = backend.get_agent(wallet.agent_id)
            if not agent:
                error_msg = "Agent not found for wallet"
                logger.error(
                    error_msg,
                    extra={
                        "task": "dao_proposal_voter",
                        "agent_id": wallet.agent_id,
                        "wallet_id": wallet_id,
                    },
                )
                return {
                    "success": False,
                    "error": error_msg,
                    "error_type": "agent_not_found",
                    "agent_id": wallet.agent_id,
                    "wallet_id": wallet_id,
                    "message_id": message_id,
                    "status": "failed",
                }

            if not agent.account_contract:
                error_msg = "Agent does not have an account contract"
                logger.error(
                    error_msg,
                    extra={"task": "dao_proposal_voter", "agent_id": agent.id},
                )
                return {
                    "success": False,
                    "error": error_msg,
                    "error_type": "agent_no_account_contract",
                    "agent_id": agent.id,
                    "wallet_id": wallet_id,
                    "message_id": message_id,
                    "status": "failed",
                }

            # Initialize the voting tool
            voting_tool = AgentAccountVoteOnActionProposalTool(wallet_id=wallet_id)

            # Process each unvoted vote
            results = []
            for vote in unvoted_votes:
                # Submit the vote
                vote_result = await voting_tool._arun(
                    agent_account_contract=agent.account_contract,
                    dao_action_proposal_voting_contract=proposal.contract_principal,
                    proposal_id=proposal.proposal_id,
                    vote=vote.answer,
                )

                if not vote_result.get("success", False):
                    error_msg = "Failed to submit vote"
                    logger.error(
                        error_msg,
                        extra={
                            "task": "dao_proposal_voter",
                            "vote_id": vote.id,
                            "error": vote_result.get("message", "Unknown error"),
                        },
                    )
                    results.append(
                        {
                            "success": False,
                            "error": error_msg,
                            "error_type": "vote_submission_failed",
                            "vote_id": vote.id,
                            "vote_answer": vote.answer,
                            "tool_error": vote_result.get("message", "Unknown error"),
                            "proposal_id": proposal.proposal_id,
                            "contract_principal": proposal.contract_principal,
                        }
                    )
                    continue

                # Extract transaction ID using shared utility function
                from app.lib.utils import extract_transaction_id_from_tool_result

                tx_id = extract_transaction_id_from_tool_result(vote_result)

                if not tx_id:
                    logger.warning(
                        "No transaction ID found in vote result",
                        extra={
                            "task": "dao_proposal_voter",
                            "vote_result": str(vote_result),
                        },
                    )
                    results.append(
                        {
                            "success": False,
                            "error": "No transaction ID found in response",
                            "error_type": "missing_transaction_id",
                            "vote_id": vote.id,
                            "vote_answer": vote.answer,
                            "vote_result": vote_result,
                            "proposal_id": proposal.proposal_id,
                            "contract_principal": proposal.contract_principal,
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
                            "Successfully updated vote with transaction ID",
                            extra={
                                "task": "dao_proposal_voter",
                                "vote_id": vote.id,
                                "tx_id": tx_id,
                            },
                        )
                        results.append(
                            {
                                "success": True,
                                "vote_id": vote.id,
                                "tx_id": tx_id,
                                "vote_answer": vote.answer,
                                "proposal_id": proposal.proposal_id,
                                "contract_principal": proposal.contract_principal,
                                "address": address,
                            }
                        )
                    else:
                        logger.error(
                            "Failed to update vote - update_vote returned None",
                            extra={"task": "dao_proposal_voter", "vote_id": vote.id},
                        )
                        results.append(
                            {
                                "success": False,
                                "error": "Failed to update vote in database",
                                "error_type": "database_update_failed",
                                "vote_id": vote.id,
                                "vote_answer": vote.answer,
                                "tx_id": tx_id,
                                "proposal_id": proposal.proposal_id,
                                "contract_principal": proposal.contract_principal,
                            }
                        )
                except Exception as e:
                    logger.error(
                        "Error updating vote",
                        extra={
                            "task": "dao_proposal_voter",
                            "vote_id": vote.id,
                            "error": str(e),
                        },
                        exc_info=True,
                    )
                    results.append(
                        {
                            "success": False,
                            "error": f"Failed to update vote: {str(e)}",
                            "error_type": "database_update_exception",
                            "vote_id": vote.id,
                            "vote_answer": vote.answer,
                            "tx_id": tx_id,
                            "proposal_id": proposal.proposal_id,
                            "contract_principal": proposal.contract_principal,
                            "exception_details": str(e),
                        }
                    )

            # Mark the message as processed ONLY if ALL votes were handled successfully
            successful_votes = len([r for r in results if r["success"]])
            if successful_votes == len(results) and successful_votes > 0:
                result = {
                    "success": True,
                    "votes_processed": successful_votes,
                    "votes_failed": len(results) - successful_votes,
                    "total_votes": len(results),
                    "proposal_id": proposal_id,
                    "wallet_id": wallet_id,
                    "message_id": message_id,
                    "status": "completed_success",
                    "results": results,
                }
                update_data = QueueMessageBase(is_processed=True, result=result)
                backend.update_queue_message(message_id, update_data)
                logger.info(
                    "Successfully processed all votes for message - marking as processed",
                    extra={
                        "task": "dao_proposal_voter",
                        "successful_votes": successful_votes,
                        "message_id": message_id,
                    },
                )
            elif successful_votes > 0:
                result = {
                    "success": False,
                    "votes_processed": successful_votes,
                    "votes_failed": len(results) - successful_votes,
                    "total_votes": len(results),
                    "proposal_id": proposal_id,
                    "wallet_id": wallet_id,
                    "message_id": message_id,
                    "status": "partial_success",
                    "message": "Partial success - some votes failed",
                    "results": results,
                }
            else:
                result = {
                    "success": False,
                    "votes_processed": 0,
                    "votes_failed": len(results),
                    "total_votes": len(results),
                    "proposal_id": proposal_id,
                    "wallet_id": wallet_id,
                    "message_id": message_id,
                    "status": "all_failed",
                    "message": "All votes failed",
                    "results": results,
                }

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
                            "task": "dao_proposal_voter",
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
                            "task": "dao_proposal_voter",
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
            error_msg = "Error processing message"
            logger.error(
                error_msg,
                extra={
                    "task": "dao_proposal_voter",
                    "message_id": message_id,
                    "error": str(e),
                },
                exc_info=True,
            )
            result = {
                "success": False,
                "error": error_msg,
                "error_type": "processing_exception",
                "message_id": message_id,
                "wallet_id": wallet_id,
                "status": "failed",
                "exception_details": str(e),
            }

            # Handle retries for exception case
            current_retries = self._get_current_retry_count(message)
            current_retries += 1
            result["retry_count"] = current_retries
            if current_retries >= self.MAX_MESSAGE_RETRIES:
                result["final_status"] = "failed_after_retries"
                update_data = QueueMessageBase(is_processed=True, result=result)
                backend.update_queue_message(message_id, update_data)
                logger.error(
                    "Message failed after max retries - marking as processed",
                    extra={
                        "task": "dao_proposal_voter",
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
                        "task": "dao_proposal_voter",
                        "message_id": message_id,
                        "retry_count": current_retries,
                    },
                )

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
            logger.warning(
                "Blockchain/proposal error, will retry",
                extra={"task": "dao_proposal_voter", "error": str(error)},
            )
            return None

        if isinstance(error, (ConnectionError, TimeoutError)):
            logger.warning(
                "Network error, will retry",
                extra={"task": "dao_proposal_voter", "error": str(error)},
            )
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
        logger.debug(
            "DAO proposal voter task cleanup completed",
            extra={"task": "dao_proposal_voter"},
        )

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
        logger.info(
            "Processing pending proposal voting messages",
            extra={"task": "dao_proposal_voter", "message_count": message_count},
        )

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
                            "Message processed votes",
                            extra={
                                "task": "dao_proposal_voter",
                                "message_id": message.id,
                                "votes_processed": votes_processed,
                            },
                        )
                    else:
                        error_msg = result.get("error", "Unknown error")
                        errors.append(f"Message {message.id}: {error_msg}")
                        logger.error(
                            "Failed to process message",
                            extra={
                                "task": "dao_proposal_voter",
                                "message_id": message.id,
                                "error": error_msg,
                            },
                        )

                except Exception as e:
                    error_msg = f"Exception processing message {message.id}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(
                        "Exception processing message",
                        extra={
                            "task": "dao_proposal_voter",
                            "message_id": message.id,
                            "error": str(e),
                        },
                        exc_info=True,
                    )

        logger.info(
            "DAO proposal voter task completed",
            extra={
                "task": "dao_proposal_voter",
                "processed_count": processed_count,
                "total_messages": message_count,
                "votes_cast": total_votes_cast,
                "error_count": len(errors),
            },
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
