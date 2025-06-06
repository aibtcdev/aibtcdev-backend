"""Chainhook webhook handler implementation."""

from typing import Any, Dict

from lib.logger import configure_logger
from services.webhooks.base import WebhookHandler
from services.webhooks.chainhook.handlers.action_concluder_handler import (
    ActionConcluderHandler,
)
from services.webhooks.chainhook.handlers.block_state_handler import BlockStateHandler
from services.webhooks.chainhook.handlers.buy_event_handler import BuyEventHandler
from services.webhooks.chainhook.handlers.dao_proposal_burn_height_handler import (
    DAOProposalBurnHeightHandler,
)
from services.webhooks.chainhook.handlers.dao_proposal_conclusion_handler import (
    DAOProposalConclusionHandler,
)
from services.webhooks.chainhook.handlers.dao_proposal_handler import DAOProposalHandler
from services.webhooks.chainhook.handlers.dao_vote_handler import DAOVoteHandler
from services.webhooks.chainhook.handlers.sell_event_handler import SellEventHandler
from services.webhooks.chainhook.models import ChainHookData


class ChainhookHandler(WebhookHandler):
    """Handler for Chainhook webhook events.

    This handler coordinates the processing of Chainhook webhook events
    by delegating to specialized handlers based on the event type.

    The processing happens in the following order:
    1. Block-level processing - for handlers that need to process entire blocks
    2. Transaction-level processing - for handlers that process individual transactions
    3. Post-processing - for handlers that need to perform cleanup after all blocks
    """

    def __init__(self):
        """Initialize the handler with a logger and specialized handlers."""
        super().__init__()
        self.logger = configure_logger(self.__class__.__name__)
        # Initialize BlockStateHandler first as it needs to validate block heights
        self.block_state_handler = BlockStateHandler()
        self.handlers = [
            ActionConcluderHandler(),
            BuyEventHandler(),
            SellEventHandler(),
            DAOProposalHandler(),
            DAOProposalBurnHeightHandler(),
            DAOVoteHandler(),
            DAOProposalConclusionHandler(),
            self.block_state_handler,  # Add to regular handlers list too for post-processing
        ]

    async def handle(self, parsed_data: ChainHookData) -> Dict[str, Any]:
        """Handle Chainhook webhook data.

        Args:
            parsed_data: The parsed webhook data

        Returns:
            Dict containing the result of handling the webhook
        """
        try:
            self.logger.info(
                f"Processing chainhook webhook with {len(parsed_data.apply)} apply blocks"
            )

            # Set chainhook data for all handlers including block state handler
            self.block_state_handler.set_chainhook_data(parsed_data)
            for handler in self.handlers:
                handler.set_chainhook_data(parsed_data)

            # Process each block
            for apply in parsed_data.apply:
                self.logger.info(
                    f"Processing block {apply.block_identifier.hash} "
                    f"(height: {apply.block_identifier.index})"
                )

                # First, process with BlockStateHandler to update/validate chain state
                if self.block_state_handler.can_handle_block(apply):
                    await self.block_state_handler.handle_block(apply)

                # Check if BlockStateHandler successfully processed *this* block.
                # This implies the block was newer than the DB state AND the DB update succeeded.
                # We check if the handler's internal state now matches this block's height.
                block_processed_by_state_handler = (
                    self.block_state_handler.latest_chain_state is not None
                    and self.block_state_handler.latest_chain_state.block_height
                    == apply.block_identifier.index
                )

                if not block_processed_by_state_handler:
                    self.logger.warning(
                        f"Block {apply.block_identifier.index} was not processed by BlockStateHandler "
                        f"(likely older than current DB state or failed update). Skipping other handlers for this block."
                    )
                    continue  # Skip to the next block in the webhook payload

                # If BlockStateHandler processed it, proceed with other handlers for this block
                self.logger.debug(
                    f"Block {apply.block_identifier.index} validated by BlockStateHandler, proceeding."
                )

                # Process other block-level handlers
                for handler in self.handlers:
                    if (
                        handler != self.block_state_handler
                        and handler.can_handle_block(apply)
                    ):
                        self.logger.debug(
                            f"Using handler {handler.__class__.__name__} for block-level processing"
                        )
                        await handler.handle_block(apply)

                # Then process transactions within the block
                for transaction in apply.transactions:
                    self.logger.info(
                        f"Processing transaction {transaction.transaction_identifier.hash}"
                    )

                    # Try each handler in turn
                    for handler in self.handlers:
                        if handler.can_handle_transaction(transaction):
                            self.logger.debug(
                                f"Using handler {handler.__class__.__name__} for transaction-level processing"
                            )
                            await handler.handle_transaction(transaction)

            # Allow handlers to perform any post-processing
            for handler in self.handlers:
                await handler.post_block_processing()

            self.logger.debug(
                "Finished processing all blocks and transactions in webhook"
            )
            return {
                "success": True,
                "message": "Successfully processed webhook",
            }

        except Exception as e:
            self.logger.error(
                f"Error handling chainhook webhook: {str(e)}", exc_info=True
            )
            raise
