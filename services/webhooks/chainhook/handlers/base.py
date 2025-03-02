"""Base class for Chainhook event handlers."""

from abc import ABC, abstractmethod
from typing import Any, Dict

from lib.logger import configure_logger
from services.webhooks.chainhook.models import TransactionWithReceipt


class ChainhookEventHandler(ABC):
    """Base class for specialized Chainhook event handlers.

    This class provides common functionality and defines the interface
    that all Chainhook event handlers must implement.
    """

    def __init__(self):
        """Initialize the handler with a logger."""
        self.logger = configure_logger(self.__class__.__name__)

    @abstractmethod
    def can_handle(self, transaction: TransactionWithReceipt) -> bool:
        """Check if this handler can handle the given transaction.

        Args:
            transaction: The transaction to check

        Returns:
            bool: True if this handler can handle the transaction, False otherwise
        """
        pass

    @abstractmethod
    async def handle_transaction(self, transaction: TransactionWithReceipt) -> None:
        """Handle a single transaction.

        Args:
            transaction: The transaction to handle
        """
        pass

    def extract_transaction_data(
        self, transaction: TransactionWithReceipt
    ) -> Dict[str, Any]:
        """Extract common data from a transaction.

        Args:
            transaction: The transaction to extract data from

        Returns:
            Dict[str, Any]: Common transaction data
        """
        tx_metadata = transaction.metadata
        tx_id = transaction.transaction_identifier.hash

        # Access attributes directly for TransactionMetadata objects
        tx_kind = tx_metadata.kind
        tx_data = tx_kind.get("data", {}) if isinstance(tx_kind, dict) else {}

        return {
            "tx_id": tx_id,
            "tx_kind": tx_kind,
            "tx_data": tx_data,
            "tx_metadata": tx_metadata,
        }
