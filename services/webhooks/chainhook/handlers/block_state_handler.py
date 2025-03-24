"""Handler for tracking the latest block state from chainhooks."""

from typing import Optional

from backend.factory import backend
from backend.models import ChainState, ChainStateBase, ChainStateCreate
from config import config
from lib.logger import configure_logger
from services.webhooks.chainhook.models import ChainHookData, TransactionWithReceipt

from .base import ChainhookEventHandler


class BlockStateHandler(ChainhookEventHandler):
    """Handler for tracking the latest block state."""

    def __init__(self):
        """Initialize the handler with a logger."""
        super().__init__()
        self.logger = configure_logger(self.__class__.__name__)
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
            self.logger.warning("No apply blocks in chainhook data")
            return False

        # Get the latest block from the webhook data
        latest_apply = data.apply[-1]
        if not latest_apply:
            self.logger.warning("No blocks in apply list")
            return False

        try:
            # Get current chain state
            current_state = backend.get_latest_chain_state(
                network=config.network.network
            )
            self.logger.debug(f"Current chain state: {current_state}")

            # Extract block info
            block_height = latest_apply.block_identifier.index
            block_hash = latest_apply.block_identifier.hash
            self.logger.info(
                f"Processing new block: height={block_height}, hash={block_hash}"
            )

            if current_state:
                # Only update if new block is higher
                if block_height <= current_state.block_height:
                    self.logger.debug(
                        f"Skipping block update - current: {current_state.block_height}, "
                        f"new: {block_height}"
                    )
                    return True

                # Update existing record
                self.logger.info(
                    f"Updating chain state from height {current_state.block_height} "
                    f"to {block_height}"
                )
                updated = backend.update_chain_state(
                    current_state.id,
                    ChainStateBase(block_height=block_height, block_hash=block_hash),
                )
                if not updated:
                    self.logger.error(
                        f"Failed to update chain state for block {block_height}"
                    )
                    return False

                self._latest_chain_state = updated
                self.logger.info(
                    f"Successfully updated chain state to block {block_height}"
                )

            else:
                # Create first record
                self.logger.info(
                    f"No existing chain state found. Creating first record for "
                    f"block {block_height}"
                )
                created = backend.create_chain_state(
                    ChainStateCreate(
                        block_height=block_height,
                        block_hash=block_hash,
                        network=config.network.network,
                    )
                )
                if not created:
                    self.logger.error(
                        f"Failed to create chain state for block {block_height}"
                    )
                    return False

                self._latest_chain_state = created
                self.logger.info(
                    f"Successfully created first chain state record for block {block_height}"
                )

            return True

        except Exception as e:
            self.logger.error(f"Error updating chain state: {str(e)}")
            return False

    @property
    def latest_chain_state(self) -> Optional[ChainState]:
        """Get the latest known chain state."""
        if not self._latest_chain_state:
            self._latest_chain_state = backend.get_latest_chain_state(
                network=config.network.network
            )
        return self._latest_chain_state
