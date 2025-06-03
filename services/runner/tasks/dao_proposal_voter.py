"""DAO proposal voter task implementation."""

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from backend.factory import backend
from backend.models import (
    ProposalFilterN,
    QueueMessage,
    QueueMessageBase,
    QueueMessageFilter,
    QueueMessageType,
    VoteBase,
    VoteFilter,
    WalletFilterN,
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


@dataclass
class VotingContext:
    """Cached context for voting operations to avoid redundant queries."""

    pending_messages: List[QueueMessage]
    proposal_ids: Set[str]
    proposals_by_id: Dict[str, Any]
    wallets_by_id: Dict[str, Any]
    unvoted_votes_by_proposal: Dict[str, List[Any]]


class DAOProposalVoterTask(BaseTask[DAOProposalVoteResult]):
    """Task runner for processing and voting on DAO proposals."""

    QUEUE_TYPE = QueueMessageType.DAO_PROPOSAL_VOTE

    async def _build_voting_context(self) -> Optional[VotingContext]:
        """Build a comprehensive context with all necessary data to minimize database calls."""
        try:
            # 1. Get all pending messages
            pending_messages = await self.get_pending_messages()
            if not pending_messages:
                logger.info("No pending proposal voting messages found")
                return None

            # 2. Extract all proposal IDs from messages
            proposal_ids = set()
            wallet_ids = set()

            for message in pending_messages:
                message_data = message.message or {}
                proposal_id = message_data.get("proposal_id")
                if proposal_id:
                    proposal_ids.add(proposal_id)
                if message.wallet_id:
                    wallet_ids.add(message.wallet_id)

            if not proposal_ids:
                logger.warning("No valid proposal IDs found in pending messages")
                return None

                # 3. Batch fetch all proposals using enhanced list_proposals_n method
            proposals_by_id = {}
            if proposal_ids:
                # Convert proposal_ids to integers and use enhanced batch fetch
                int_proposal_ids = []
                for proposal_id in proposal_ids:
                    if proposal_id.isdigit():
                        int_proposal_ids.append(int(proposal_id))

                if int_proposal_ids:
                    enhanced_filter = ProposalFilterN(proposal_ids=int_proposal_ids)
                    proposals = backend.list_proposals_n(enhanced_filter)
                    proposals_by_id = {
                        str(p.proposal_id): p
                        for p in proposals
                        if p.proposal_id is not None
                    }

            # 4. Batch fetch all wallets using enhanced list_wallets_n method
            wallets_by_id = {}
            if wallet_ids:
                enhanced_wallet_filter = WalletFilterN(ids=list(wallet_ids))
                wallets = backend.list_wallets_n(enhanced_wallet_filter)
                wallets_by_id = {str(w.id): w for w in wallets}

            # 5. Batch fetch all unvoted votes for all proposals
            unvoted_votes_by_proposal = {}
            if proposal_ids:
                # Get all unvoted votes for all proposals at once
                all_unvoted_votes = backend.list_votes(VoteFilter(voted=False))

                # Group by proposal_id
                for vote in all_unvoted_votes:
                    if vote.proposal_id:
                        proposal_key = str(vote.proposal_id)
                        if proposal_key in proposal_ids:
                            if proposal_key not in unvoted_votes_by_proposal:
                                unvoted_votes_by_proposal[proposal_key] = []
                            unvoted_votes_by_proposal[proposal_key].append(vote)

            return VotingContext(
                pending_messages=pending_messages,
                proposal_ids=proposal_ids,
                proposals_by_id=proposals_by_id,
                wallets_by_id=wallets_by_id,
                unvoted_votes_by_proposal=unvoted_votes_by_proposal,
            )

        except Exception as e:
            logger.error(f"Error building voting context: {str(e)}", exc_info=True)
            return None

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate task-specific conditions using optimized batch queries."""
        try:
            voting_context = await self._build_voting_context()
            if not voting_context:
                return False

            # Check if we have valid proposals with unvoted votes
            valid_proposals_found = False
            for proposal_id in voting_context.proposal_ids:
                if (
                    proposal_id in voting_context.proposals_by_id
                    and proposal_id in voting_context.unvoted_votes_by_proposal
                    and voting_context.unvoted_votes_by_proposal[proposal_id]
                ):

                    unvoted_count = len(
                        voting_context.unvoted_votes_by_proposal[proposal_id]
                    )
                    logger.info(
                        f"Found valid proposal {proposal_id} with {unvoted_count} unvoted votes to process"
                    )
                    valid_proposals_found = True
                    break

            if not valid_proposals_found:
                logger.warning(
                    "No valid proposals with unvoted votes found in pending messages"
                )

            # Cache the context for later use in execution
            self._voting_context = voting_context
            return valid_proposals_found

        except Exception as e:
            logger.error(
                f"Error validating proposal voter task: {str(e)}", exc_info=True
            )
            return False

    async def process_message(
        self, message: QueueMessage, voting_context: VotingContext
    ) -> Dict[str, Any]:
        """Process a single DAO proposal voting message using cached context."""
        message_id = message.id
        message_data = message.message or {}
        wallet_id = message.wallet_id

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
            # Use cached proposal data
            proposal = voting_context.proposals_by_id.get(proposal_id)
            if not proposal:
                error_msg = f"Proposal {proposal_id} not found in database"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

            # Get unvoted votes from cached data
            all_unvoted_votes = voting_context.unvoted_votes_by_proposal.get(
                proposal_id, []
            )

            # Filter for this specific wallet
            unvoted_votes = [
                vote for vote in all_unvoted_votes if vote.wallet_id == wallet_id
            ]

            if not unvoted_votes:
                error_msg = f"No unvoted votes found for proposal {proposal_id} and wallet {wallet_id}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

            # Use cached wallet data
            wallet = voting_context.wallets_by_id.get(str(wallet_id))
            if not wallet:
                error_msg = f"Wallet {wallet_id} not found"
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

                # Get the correct address based on network configuration
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
        """Run the DAO proposal voter task using cached context."""
        # Use cached context from validation if available
        voting_context = getattr(self, "_voting_context", None)
        if not voting_context:
            voting_context = await self._build_voting_context()

        if not voting_context or not voting_context.pending_messages:
            return [
                DAOProposalVoteResult(
                    success=True,
                    message="No pending messages found",
                    proposals_processed=0,
                    proposals_voted=0,
                )
            ]

        message_count = len(voting_context.pending_messages)
        logger.debug(f"Found {message_count} pending proposal voting messages")

        # Process each message
        processed_count = 0
        voted_count = 0
        errors = []

        for message in voting_context.pending_messages:
            result = await self.process_message(message, voting_context)
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

        # Clear cached context
        if hasattr(self, "_voting_context"):
            delattr(self, "_voting_context")

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
