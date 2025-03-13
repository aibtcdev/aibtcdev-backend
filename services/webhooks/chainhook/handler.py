"""Chainhook webhook handler implementation."""

from typing import Any, Dict

from lib.logger import configure_logger
from services.webhooks.base import WebhookHandler
from services.webhooks.chainhook.handlers.base import ChainhookEventHandler
from services.webhooks.chainhook.handlers.buy_event_handler import BuyEventHandler
from services.webhooks.chainhook.handlers.contract_message_handler import (
    ContractMessageHandler,
)
from services.webhooks.chainhook.handlers.dao_proposal_burn_height_handler import (
    DAOProposalBurnHeightHandler,
)
from services.webhooks.chainhook.handlers.dao_proposal_handler import DAOProposalHandler
from services.webhooks.chainhook.handlers.dao_vote_handler import DAOVoteHandler
from services.webhooks.chainhook.handlers.sell_event_handler import SellEventHandler
from services.webhooks.chainhook.models import ChainHookData


class ChainhookHandler(WebhookHandler):
    """Handler for Chainhook webhook events.

    This handler coordinates the processing of Chainhook webhook events
    by delegating to specialized handlers based on the event type.
    """

    def __init__(self):
        """Initialize the handler with a logger and specialized handlers."""
        super().__init__()
        self.logger = configure_logger(self.__class__.__name__)
        self.handlers = [
            ContractMessageHandler(),
            BuyEventHandler(),
            SellEventHandler(),
            DAOProposalHandler(),
            DAOProposalBurnHeightHandler(),
            DAOVoteHandler(),
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

            # Set chainhook data for all handlers
            for handler in self.handlers:
                handler.set_chainhook_data(parsed_data)

            for apply in parsed_data.apply:
                for transaction in apply.transactions:
                    self.logger.debug(
                        f"Processing transaction {transaction.transaction_identifier.hash}"
                    )

                    # Try each handler in turn
                    for handler in self.handlers:
                        if handler.can_handle(transaction):
                            self.logger.debug(
                                f"Using handler {handler.__class__.__name__} for transaction"
                            )
                            await handler.handle_transaction(transaction)

            self.logger.info("Finished processing all transactions in webhook")
            return {
                "success": True,
                "message": "Successfully processed webhook",
            }

        except Exception as e:
            self.logger.error(
                f"Error handling chainhook webhook: {str(e)}", exc_info=True
            )
            raise
