"""Handler for capturing DAO proposal votes."""

from typing import Dict, List, Optional
from uuid import UUID

from backend.factory import backend
from backend.models import ProposalFilter, VoteBase, VoteCreate, VoteFilter
from lib.logger import configure_logger
from services.webhooks.chainhook.handlers.base import ChainhookEventHandler
from services.webhooks.chainhook.models import Event, TransactionWithReceipt


class DAOVoteHandler(ChainhookEventHandler):
    """Handler for capturing and processing DAO proposal votes.

    This handler identifies contract calls related to voting on proposals in DAO contracts
    and updates vote records in the database with transaction IDs.
    """

    def __init__(self):
        """Initialize the handler with a logger."""
        super().__init__()
        self.logger = configure_logger(self.__class__.__name__)

    def can_handle(self, transaction: TransactionWithReceipt) -> bool:
        """Check if this handler can handle the given transaction.

        This handler can handle contract call transactions related to voting on proposals.

        Args:
            transaction: The transaction to check

        Returns:
            bool: True if this handler can handle the transaction, False otherwise
        """
        tx_data = self.extract_transaction_data(transaction)
        tx_kind = tx_data["tx_kind"]
        tx_data_content = tx_data["tx_data"]
        tx_metadata = tx_data["tx_metadata"]

        # Only handle ContractCall type transactions
        if not isinstance(tx_kind, dict):
            self.logger.debug(f"Skipping: tx_kind is not a dict: {type(tx_kind)}")
            return False

        tx_kind_type = tx_kind.get("type")

        if not isinstance(tx_data_content, dict):
            self.logger.debug(
                f"Skipping: tx_data_content is not a dict: {type(tx_data_content)}"
            )
            return False

        # Check if the method name contains "vote-on-proposal"
        tx_method = tx_data_content.get("method", "")
        is_vote_method = tx_method == "vote-on-proposal"

        # Access success from TransactionMetadata
        tx_success = tx_metadata.success

        if is_vote_method and tx_success:
            self.logger.debug(f"Found vote method: {tx_method}")

        return tx_kind_type == "ContractCall" and is_vote_method and tx_success is True

    def _get_vote_info_from_events(self, events: List[Event]) -> Optional[Dict]:
        """Extract the vote information from transaction events.

        Args:
            events: List of events from the transaction

        Returns:
            Optional[Dict]: Dictionary containing vote information if found, None otherwise
        """
        for event in events:
            # Find print events with vote information
            if (
                event.type == "SmartContractEvent"
                and hasattr(event, "data")
                and event.data.get("topic") == "print"
            ):
                event_data = event.data
                value = event_data.get("value", {})

                if value.get("notification") == "vote-on-proposal":
                    payload = value.get("payload", {})
                    if not payload:
                        self.logger.warning("Empty payload in vote event")
                        return None

                    # Extract the proposal ID - it could be in different formats
                    proposal_id = None
                    if "proposalId" in payload:
                        proposal_id = payload.get("proposalId")
                    elif "proposal_id" in payload:
                        proposal_id = payload.get("proposal_id")

                    # Get voter address
                    voter = None
                    if "voter" in payload:
                        voter = payload.get("voter")

                    # Get vote value (true/false)
                    vote_value = None
                    if "vote" in payload:
                        vote_value = payload.get("vote")

                    # Get token amount
                    amount = None
                    if "amount" in payload:
                        amount = str(payload.get("amount"))
                    elif "liquidTokens" in payload:
                        amount = str(payload.get("liquidTokens"))

                    # Try to determine the vote value from the transaction args
                    # This is needed because some contracts don't include the vote value in the event
                    if vote_value is None:
                        # Check if we can extract it from the method args
                        args = event_data.get("args", [])
                        if len(args) >= 2:  # Assuming second arg is the vote boolean
                            vote_str = str(args[1]).lower()
                            if vote_str in ["true", "false"]:
                                vote_value = vote_str == "true"

                    return {
                        "proposal_id": proposal_id,
                        "voter": voter,
                        "caller": payload.get("caller"),
                        "amount": amount,
                        "vote_value": vote_value,
                    }

        self.logger.warning("Could not find vote information in transaction events")
        return None

    async def handle_transaction(self, transaction: TransactionWithReceipt) -> None:
        """Handle DAO vote transactions.

        Processes vote transactions and updates vote records in the database with transaction IDs.
        If no vote record exists, creates a new one.

        Args:
            transaction: The transaction to handle
        """
        tx_data = self.extract_transaction_data(transaction)
        tx_id = tx_data["tx_id"]
        tx_data_content = tx_data["tx_data"]
        tx_metadata = tx_data["tx_metadata"]

        # Get contract identifier
        contract_identifier = tx_data_content.get("contract_identifier")
        if not contract_identifier:
            self.logger.warning("No contract identifier found in transaction data")
            return

        # Get the vote information from the transaction events
        events = tx_metadata.receipt.events if hasattr(tx_metadata, "receipt") else []
        vote_info = self._get_vote_info_from_events(events)
        if vote_info is None:
            self.logger.warning("Could not determine vote information from transaction")
            return

        # Extract vote details
        proposal_id = vote_info.get("proposal_id")
        voter_address = vote_info.get("voter")
        vote_value = vote_info.get("vote_value")
        amount = vote_info.get("amount")

        # If vote_value is not in the event, try to extract it from the transaction args
        if vote_value is None:
            args = tx_data_content.get("args", [])
            if len(args) >= 2:  # Assuming second arg is the vote boolean
                vote_str = str(args[1]).lower()
                if vote_str in ["true", "false"]:
                    vote_value = vote_str == "true"
                    self.logger.info(
                        f"Extracted vote value from transaction args: {vote_value}"
                    )

        if not proposal_id or not voter_address:
            self.logger.warning(
                "Missing proposal ID or voter address in vote information"
            )
            return

        self.logger.info(
            f"Processing vote on proposal {proposal_id} by {voter_address} "
            f"(contract: {contract_identifier}, tx_id: {tx_id}, vote: {vote_value}, amount: {amount})"
        )

        # Find the proposal in the database
        proposals = backend.list_proposals(
            filters=ProposalFilter(
                contract_principal=contract_identifier,
                proposal_id=proposal_id,
            )
        )

        if not proposals:
            self.logger.warning(
                f"No proposal found for ID {proposal_id} in contract {contract_identifier}"
            )
            return

        proposal = proposals[0]

        # Find existing votes for this proposal and voter
        votes = backend.list_votes(
            filters=VoteFilter(
                proposal_id=proposal.id,
                address=voter_address,
            )
        )

        if votes:
            # Update existing vote with transaction ID and amount
            vote = votes[0]
            self.logger.info(
                f"Updating existing vote {vote.id} with tx_id: {tx_id} and amount: {amount}"
            )

            # Update with tx_id and amount if needed
            update_data = VoteBase(tx_id=tx_id)
            if amount and not vote.amount:
                update_data.amount = amount

            backend.update_vote(vote.id, update_data)
            self.logger.info(f"Updated vote {vote.id}")
        else:
            # Create a new vote record
            self.logger.info(
                f"Creating new vote record for proposal {proposal.id} and voter {voter_address}"
            )

            # Try to determine the DAO ID from the proposal
            dao_id = proposal.dao_id

            # Create the vote record
            new_vote = VoteCreate(
                proposal_id=proposal.id,
                address=voter_address,
                tx_id=tx_id,
                answer=vote_value,  # Use the vote value from the event if available
                dao_id=dao_id,
                reasoning="Vote captured from blockchain transaction",
                amount=amount,  # Include the token amount
            )

            try:
                vote = backend.create_vote(new_vote)
                self.logger.info(f"Created new vote record with ID: {vote.id}")
            except Exception as e:
                self.logger.error(f"Failed to create vote record: {str(e)}")
