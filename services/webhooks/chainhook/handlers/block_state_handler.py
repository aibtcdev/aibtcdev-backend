"""Handler for tracking the latest block state from chainhooks."""

from typing import Optional

from backend.factory import backend
from backend.models import ChainState, ChainStateBase, ChainStateCreate
from config import config
from services.webhooks.chainhook.models import (
    Apply,
    TransactionWithReceipt,
)

from .base import ChainhookEventHandler


class BlockStateHandler(ChainhookEventHandler):
    """Handler for tracking the latest block state.

    This handler operates at the block level rather than the transaction level.
    It tracks the latest block state by processing each block as it arrives.
    """

    def __init__(self):
        """Initialize the handler with a logger."""
        super().__init__()
        self._latest_chain_state: Optional[ChainState] = None

    def can_handle_transaction(self, transaction: TransactionWithReceipt) -> bool:
        """Check if this handler can handle the given transaction.

        This handler does not process individual transactions.

        Args:
            transaction: The transaction to check

        Returns:
            bool: Always returns False as this handler only processes blocks
        """
        return False

    async def handle_transaction(self, transaction: TransactionWithReceipt) -> None:
        """Handle a single transaction.

        This handler doesn't process individual transactions, only blocks.

        Args:
            transaction: The transaction to handle
        """
        pass

    def can_handle_block(self, block: Apply) -> bool:
        """Check if this handler can handle the given block.

        This handler processes all blocks to track chain state.

        Args:
            block: The block to check

        Returns:
            bool: Always returns True as this handler processes all blocks
        """
        return True

    async def handle_block(self, block: Apply) -> None:
        """Handle a single block by updating the chain state.

        Args:
            block: The block to handle
        """
        try:
            self.logger.debug(f"Received block metadata: {block.metadata}")
            # Get current chain state
            current_state = backend.get_latest_chain_state(
                network=config.network.network
            )
            self.logger.debug(f"Current chain state: {current_state}")

            # Extract block info
            block_height = block.block_identifier.index
            block_hash = block.block_identifier.hash

            # Safely extract bitcoin block height
            bitcoin_block_height = None
            if block.metadata and block.metadata.bitcoin_anchor_block_identifier:
                bitcoin_block_height = (
                    block.metadata.bitcoin_anchor_block_identifier.index
                )
            self.logger.debug(
                f"Extracted bitcoin_block_height: {bitcoin_block_height} for block_hash {block.block_identifier.hash}"
            )

            self.logger.info(
                f"Processing block: height={block_height}, hash={block_hash}, "
                f"bitcoin_height={bitcoin_block_height}"
            )

            if current_state:
                # Only update if new block is higher
                if block_height <= current_state.block_height:
                    self.logger.debug(
                        f"Skipping block update - current: {current_state.block_height}, "
                        f"new: {block_height}"
                    )
                    return

                # Update existing record
                self.logger.info(
                    f"Updating chain state from height {current_state.block_height} "
                    f"to {block_height}"
                )
                # Prepare update data, omitting bitcoin_block_height if None
                update_data = {
                    "block_height": block_height,
                    "block_hash": block_hash,
                    "network": current_state.network,
                }
                if bitcoin_block_height is not None:
                    update_data["bitcoin_block_height"] = bitcoin_block_height

                self.logger.debug(
                    f"Updating chain_state {current_state.id} with update_data: {update_data}"
                )
                updated = backend.update_chain_state(
                    current_state.id,
                    ChainStateBase(**update_data),
                )
                if not updated:
                    self.logger.error(
                        f"Failed to update chain state for block {block_height}"
                    )
                    return

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
                chain_state_create_payload = ChainStateCreate(
                    block_height=block_height,
                    block_hash=block_hash,
                    network=config.network.network,
                    bitcoin_block_height=bitcoin_block_height,
                )
                self.logger.debug(
                    f"Creating new chain_state with payload: {chain_state_create_payload.model_dump_json()}"
                )
                created = backend.create_chain_state(chain_state_create_payload)
                if not created:
                    self.logger.error(
                        f"Failed to create chain state for block {block_height}"
                    )
                    return

                self._latest_chain_state = created
                self.logger.info(
                    f"Successfully created first chain state record for block {block_height}"
                )

        except Exception as e:
            self.logger.error(f"Error updating chain state: {str(e)}")

    @property
    def latest_chain_state(self) -> Optional[ChainState]:
        """Get the latest known chain state."""
        if not self._latest_chain_state:
            self._latest_chain_state = backend.get_latest_chain_state(
                network=config.network.network
            )
        return self._latest_chain_state
