"""DAO proposal voter task implementation."""

import json
from dataclasses import dataclass
from typing import Any, Dict, List

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
from services.runner.base import BaseTask, JobContext, RunnerResult
from tools.dao_ext_action_proposals import VoteOnActionProposalTool

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

    async def get_pending_messages(self) -> List[QueueMessage]:
        """Get all unprocessed DAO proposal vote messages from the queue."""
        filters = QueueMessageFilter(type=self.QUEUE_TYPE, is_processed=False)
        return backend.list_queue_messages(filters=filters)

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate that we have pending messages to process."""
        try:
            pending_messages = await self.get_pending_messages()

            if not pending_messages:
                logger.info("No pending DAO proposal vote messages to process")
                return False

            logger.info(
                f"Found {len(pending_messages)} pending DAO proposal vote messages"
            )
            return True

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
                update_data = QueueMessageBase(is_processed=True)
                backend.update_queue_message(message_id, update_data)
                logger.info(
                    f"Successfully processed all {successful_votes} votes for message {message_id} - marking as processed"
                )
            elif successful_votes > 0:
                logger.warning(
                    f"Only {successful_votes}/{len(results)} votes succeeded for message {message_id} - leaving unprocessed for retry"
                )
            else:
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
            return {"success": False, "error": error_msg}

    async def _execute_impl(self, context: JobContext) -> List[DAOProposalVoteResult]:
        """Run the DAO proposal voter task by processing each message directly."""
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
        errors = []

        for message in pending_messages:
            try:
                result = await self.process_message(message)
                processed_count += 1

                if result.get("success"):
                    votes_processed = result.get("votes_processed", 0)
                    total_votes_processed += votes_processed
                    logger.debug(
                        f"Message {message.id}: processed {votes_processed} votes"
                    )
                else:
                    error_msg = result.get("error", "Unknown error")
                    errors.append(f"Message {message.id}: {error_msg}")
                    logger.error(f"Failed to process message {message.id}: {error_msg}")

            except Exception as e:
                error_msg = f"Exception processing message {message.id}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg, exc_info=True)

        logger.info(
            f"Task completed - Processed: {processed_count}/{message_count} messages, "
            f"Votes: {total_votes_processed}, Errors: {len(errors)}"
        )

        return [
            DAOProposalVoteResult(
                success=True,
                message=f"Processed {processed_count} message(s), voted on {total_votes_processed} vote(s)",
                proposals_processed=processed_count,
                proposals_voted=total_votes_processed,
                errors=errors,
            )
        ]


# Instantiate the task for use in the registry
dao_proposal_voter = DAOProposalVoterTask()
