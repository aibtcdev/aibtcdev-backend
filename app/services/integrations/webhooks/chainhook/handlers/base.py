"""Base class for Chainhook event handlers."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from app.lib.logger import configure_logger
from app.services.integrations.webhooks.chainhook.models import (
    Apply,
    ChainHookData,
    TransactionWithReceipt,
)


class ChainhookEventHandler(ABC):
    """Base class for specialized Chainhook event handlers.

    This class provides common functionality and defines the interface
    that all Chainhook event handlers must implement.

    Handlers can process events at two levels:
    1. Transaction level - by implementing can_handle and handle_transaction
    2. Block level - by implementing can_handle_block and handle_block

    Most handlers will only need to implement transaction-level handling,
    but some (like BlockStateHandler) may need block-level handling.
    """

    def __init__(self):
        """Initialize the handler with a logger."""
        self.logger = configure_logger(self.__class__.__name__)
        self.chainhook_data: Optional[ChainHookData] = None

    def set_chainhook_data(self, data: ChainHookData) -> None:
        """Set the chainhook data for this handler.

        Args:
            data: The chainhook data to set
        """
        self.chainhook_data = data

    # ----------------------------------------------------------------
    # Transaction-level handling (required for all handlers)
    # ----------------------------------------------------------------
    @abstractmethod
    def can_handle_transaction(self, transaction: TransactionWithReceipt) -> bool:
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

    # ----------------------------------------------------------------
    # Block-level handling (optional for handlers)
    # ----------------------------------------------------------------
    def can_handle_block(self, block: Apply) -> bool:
        """Check if this handler can handle the given block.

        By default, handlers don't process blocks directly unless overridden.
        Override this method along with handle_block if your handler needs
        to process entire blocks.

        Args:
            block: The block to check

        Returns:
            bool: True if this handler can handle the block, False otherwise
        """
        return False

    async def handle_block(self, block: Apply) -> None:
        """Handle a single block.

        By default, handlers don't process blocks directly unless overridden.
        Override this method along with can_handle_block if your handler needs
        to process entire blocks.

        Args:
            block: The block to handle
        """
        pass

    async def post_block_processing(self) -> None:
        """Perform any necessary operations after all blocks have been processed.

        This method is called after all blocks in the chainhook data have been processed.
        Handlers can override this to perform cleanup or state updates.
        """
        pass

    # ----------------------------------------------------------------
    # Helper methods
    # ----------------------------------------------------------------
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
