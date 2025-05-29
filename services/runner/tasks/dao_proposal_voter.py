"""DAO proposal voter task implementation."""

import json
from dataclasses import dataclass
from typing import Any, Dict, List

from backend.factory import backend
from backend.models import (
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

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate task-specific conditions."""
        try:
            # Get pending messages from the queue
            pending_messages = await self.get_pending_messages()
            message_count = len(pending_messages)
            logger.debug(f"Found {message_count} pending proposal voting messages")

            if message_count == 0:
                logger.info("No pending proposal voting messages found")
                return False

            # Validate that at least one message has a valid proposal ID
            for message in pending_messages:
                message_data = message.message or {}
                proposal_id = message_data.get("proposal_id")

                if not proposal_id:
                    logger.warning(f"Message {message.id} missing proposal_id")
                    continue

                # Check if the proposal exists in the database
                proposal = backend.get_proposal(proposal_id)
                if proposal:
                    # Check if there are any unvoted votes for this proposal
                    unvoted_votes = backend.list_votes(
                        VoteFilter(
                            proposal_id=proposal_id,
                            voted=False,
                        )
                    )

                    if unvoted_votes:
                        logger.info(
                            f"Found valid proposal {proposal_id} with {len(unvoted_votes)} unvoted votes to process"
                        )
                        return True
                    else:
                        logger.warning(
                            f"No unvoted votes found for proposal {proposal_id}"
                        )
                else:
                    logger.warning(f"Proposal {proposal_id} not found in database")

            logger.warning(
                "No valid proposals with unvoted votes found in pending messages"
            )
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

            # Get unvoted votes for this proposal and wallet
            unvoted_votes = backend.list_votes(
                VoteFilter(
                    proposal_id=proposal_id,
                    wallet_id=wallet_id,
                    voted=False,
                )
            )

            if not unvoted_votes:
                error_msg = f"No unvoted votes found for proposal {proposal_id} and wallet {wallet_id}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

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

                # Log the txid for debugging
                ## Get the correct address based on network configuration
                wallet = backend.get_wallet(wallet_id)
                address = (
                    wallet.mainnet_address
                    if config.network.network == "mainnet"
                    else wallet.testnet_address
                )
                logger.debug(f"Found txid in response: {tx_id}")
                vote_data = VoteBase(
                    tx_id=tx_id,
                    voted=True,
                    address=address,
                    profile_id=wallet.profile_id,
                )
                logger.debug(
                    f"Attempting to update vote {vote.id} with data: {vote_data.model_dump()}"
                )
                try:
                    # Log the current vote state before update
                    current_vote = backend.get_vote(vote.id)
                    logger.debug(
                        f"Current vote state before update: {current_vote.model_dump() if current_vote else None}"
                    )

                    updated_vote = backend.update_vote(vote.id, vote_data)
                    if updated_vote:
                        logger.info(
                            f"Successfully updated vote {vote.id} with transaction ID {tx_id} and marked as voted"
                        )
                        logger.debug(f"Updated vote state: {updated_vote.model_dump()}")
                    else:
                        logger.error(
                            f"Failed to update vote {vote.id} - update_vote returned None"
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
                            "vote_result": vote_result,
                        }
                    )
                    continue
                results.append(
                    {
                        "success": True,
                        "vote_id": vote.id,
                        "tx_id": tx_id,
                        "vote_result": vote_result,
                    }
                )

            # Mark the message as processed if all votes were handled
            if all(result["success"] for result in results):
                update_data = QueueMessageBase(is_processed=True)
                backend.update_queue_message(message_id, update_data)
                logger.info(
                    f"Successfully processed all votes for message {message_id}"
                )
                return {
                    "success": True,
                    "results": results,
                }
            else:
                # Some votes failed
                return {
                    "success": False,
                    "error": "Some votes failed to process",
                    "results": results,
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
                # Count successful votes from the results
                voted_count += len(
                    [r for r in result.get("results", []) if r.get("success")]
                )
            else:
                errors.append(result.get("error", "Unknown error"))
                # Also add any individual vote errors
                for vote_result in result.get("results", []):
                    if not vote_result.get("success"):
                        errors.append(vote_result.get("error", "Unknown vote error"))

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
