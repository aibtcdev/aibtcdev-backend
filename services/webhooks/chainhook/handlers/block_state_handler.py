"""Handler for tracking the latest block state from chainhooks."""

import logging
from typing import Optional

from backend.models import ChainState, ChainStateBase, ChainStateCreate
from backend.supabase import SupabaseBackend
from config import config
from services.webhooks.chainhook.models import (
    Apply,
    ChainHookData,
    TransactionWithReceipt,
)

from .base import ChainhookEventHandler

logger = logging.getLogger(__name__)


class BlockStateHandler(ChainhookEventHandler):
    """Handler for tracking the latest block state."""

    def __init__(self, db: SupabaseBackend):
        """Initialize the handler with database connection."""
        super().__init__()
        self.db = db
        self._latest_chain_state: Optional[ChainState] = None

    def can_handle(self, transaction: TransactionWithReceipt) -> bool:
        """Check if this handler can handle the given transaction.

        This handler processes all transactions as it tracks block state.

        Args:
            transaction: The transaction to check

        Returns:
            bool: Always returns True as this handler processes all transactions
        """
        return True

    async def handle_transaction(self, transaction: TransactionWithReceipt) -> None:
        """Handle a single transaction.

        This handler doesn't process individual transactions, only block state.

        Args:
            transaction: The transaction to handle
        """
        pass

    async def handle(self, data: ChainHookData) -> bool:
        """Handle incoming chainhook data by updating the latest block state.

        Args:
            data: The chainhook webhook payload

        Returns:
            bool: True if block state was updated successfully
        """
        if not data.apply:
            logger.warning("No apply blocks in chainhook data")
            return False

        # Get the latest block from the webhook data
        latest_apply = data.apply[-1]
        if not latest_apply:
            logger.warning("No blocks in apply list")
            return False

        try:
            # Get current chain state
            current_state = self.db.get_latest_chain_state(
                network=config.network.network
            )

            # Extract block info
            block_height = latest_apply.block_identifier.index
            block_hash = latest_apply.block_identifier.hash

            if current_state:
                # Only update if new block is higher
                if block_height <= current_state.block_height:
                    logger.debug(
                        f"Skipping block update - current: {current_state.block_height}, "
                        f"new: {block_height}"
                    )
                    return True

                # Update existing record
                updated = self.db.update_chain_state(
                    current_state.id,
                    ChainStateBase(block_height=block_height, block_hash=block_hash),
                )
                if not updated:
                    logger.error("Failed to update chain state")
                    return False

                self._latest_chain_state = updated

            else:
                # Create first record
                created = self.db.create_chain_state(
                    ChainStateCreate(
                        block_height=block_height,
                        block_hash=block_hash,
                        network=config.network.network,
                    )
                )
                if not created:
                    logger.error("Failed to create chain state")
                    return False

                self._latest_chain_state = created

            logger.info(f"Updated chain state to block {block_height}")
            return True

        except Exception as e:
            logger.error(f"Error updating chain state: {e}")
            return False

    @property
    def latest_chain_state(self) -> Optional[ChainState]:
        """Get the latest known chain state."""
        if not self._latest_chain_state:
            self._latest_chain_state = self.db.get_latest_chain_state()
        return self._latest_chain_state
