"""Handler for capturing DAO proposal votes."""

from typing import Dict, List, Optional

from lib.logger import configure_logger
from services.webhooks.chainhook.handlers.action_vote_handler import ActionVoteHandler
from services.webhooks.chainhook.handlers.base import ChainhookEventHandler
from services.webhooks.chainhook.handlers.core_vote_handler import CoreVoteHandler
from services.webhooks.chainhook.models import Event, TransactionWithReceipt


class DAOVoteHandler(ChainhookEventHandler):
    """Handler for capturing and processing DAO proposal votes.

    This handler coordinates between core and action vote handlers to process
    all types of DAO proposal votes.
    """

    def __init__(self):
        """Initialize the handler with core and action vote handlers."""
        super().__init__()
        self.logger = configure_logger(self.__class__.__name__)
        self.core_handler = CoreVoteHandler()
        self.action_handler = ActionVoteHandler()

    def can_handle_transaction(self, transaction: TransactionWithReceipt) -> bool:
        """Check if this handler can handle the given transaction.

        This handler can handle both core and action proposal vote transactions.

        Args:
            transaction: The transaction to check

        Returns:
            bool: True if this handler can handle the transaction, False otherwise
        """
        return self.core_handler.can_handle_transaction(
            transaction
        ) or self.action_handler.can_handle_transaction(transaction)

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
        """Handle vote transactions.

        Routes the transaction to either the core or action vote handler based on
        the contract identifier.

        Args:
            transaction: The transaction to handle
        """
        tx_data = self.extract_transaction_data(transaction)
        tx_data_content = tx_data["tx_data"]

        # Get contract identifier to determine which handler to use
        contract_identifier = tx_data_content.get("contract_identifier", "")

        # Check if this is a core or action proposal vote based on the contract name
        if "core-proposals" in contract_identifier:
            await self.core_handler.handle_transaction(transaction)
        elif "action-proposals" in contract_identifier:
            await self.action_handler.handle_transaction(transaction)
        else:
            self.logger.warning(
                f"Unknown proposal contract type: {contract_identifier}"
            )
