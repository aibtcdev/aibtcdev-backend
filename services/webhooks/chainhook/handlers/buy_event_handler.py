"""Handler for capturing buy function events from contracts."""

from typing import Any, Dict

from lib.logger import configure_logger
from services.webhooks.chainhook.handlers.base import ChainhookEventHandler
from services.webhooks.chainhook.models import (
    Event,
    TransactionMetadata,
    TransactionWithReceipt,
)


class BuyEventHandler(ChainhookEventHandler):
    """Handler for capturing and logging events from contract buy function calls.

    This handler identifies contract calls with the "buy" function name
    and logs only FTTransferEvent events associated with these transactions.
    """

    def __init__(self):
        """Initialize the handler with a logger."""
        super().__init__()
        self.logger = configure_logger(self.__class__.__name__)

    def can_handle(self, transaction: TransactionWithReceipt) -> bool:
        """Check if this handler can handle the given transaction.

        This handler can handle contract call transactions with the "buy" function name.

        Args:
            transaction: The transaction to check

        Returns:
            bool: True if this handler can handle the transaction, False otherwise
        """
        tx_data = self.extract_transaction_data(transaction)
        tx_kind = tx_data["tx_kind"]
        tx_data_content = tx_data["tx_data"]
        tx_metadata = tx_data["tx_metadata"]

        # Only handle ContractCall type transactions with 'buy' method
        if not isinstance(tx_kind, dict):
            self.logger.debug(f"Skipping: tx_kind is not a dict: {type(tx_kind)}")
            return False

        tx_kind_type = tx_kind.get("type")

        if not isinstance(tx_data_content, dict):
            self.logger.debug(
                f"Skipping: tx_data_content is not a dict: {type(tx_data_content)}"
            )
            return False

        tx_method = tx_data_content.get("method")

        # Check if the method name contains "buy" (case-insensitive)
        is_buy_method = tx_method and "buy" in tx_method.lower()

        if is_buy_method:
            self.logger.debug(f"Found buy method: {tx_method}")

        return tx_kind_type == "ContractCall" and is_buy_method

    async def handle_transaction(self, transaction: TransactionWithReceipt) -> None:
        """Handle buy function call transactions.

        Logs only FTTransferEvent events associated with buy function call transactions.

        Args:
            transaction: The transaction to handle
        """
        tx_data = self.extract_transaction_data(transaction)
        tx_id = tx_data["tx_id"]
        tx_data_content = tx_data["tx_data"]
        tx_metadata = tx_data["tx_metadata"]

        # Access sender directly from TransactionMetadata
        sender = tx_metadata.sender
        contract_identifier = tx_data_content.get("contract_identifier", "unknown")
        args = tx_data_content.get("args", [])

        self.logger.info(
            f"Processing buy function call from {sender} to contract {contract_identifier} "
            f"with args: {args}, tx_id: {tx_id}"
        )

        # Log only FTTransferEvent events from the transaction
        if hasattr(tx_metadata, "receipt") and hasattr(tx_metadata.receipt, "events"):
            events = tx_metadata.receipt.events
            ft_transfer_events = [
                event for event in events if event.type == "FTTransferEvent"
            ]

            if ft_transfer_events:
                self.logger.info(
                    f"Found {len(ft_transfer_events)} FTTransferEvent events in transaction {tx_id}"
                )

                for i, event in enumerate(ft_transfer_events):
                    event_data = event.data
                    self.logger.info(
                        f"FTTransferEvent {i+1}/{len(ft_transfer_events)}: Data={event_data}"
                    )
            else:
                self.logger.info(
                    f"No FTTransferEvent events found in transaction {tx_id}"
                )
        else:
            self.logger.warning(f"No events found in transaction {tx_id}")
