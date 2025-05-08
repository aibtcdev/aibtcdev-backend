"""Handler for capturing new DAO proposals."""

from services.webhooks.chainhook.handlers.action_proposal_handler import (
    ActionProposalHandler,
)
from services.webhooks.chainhook.handlers.base import ChainhookEventHandler
from services.webhooks.chainhook.handlers.core_proposal_handler import (
    CoreProposalHandler,
)
from services.webhooks.chainhook.models import TransactionWithReceipt


class DAOProposalHandler(ChainhookEventHandler):
    """Handler for capturing and processing new DAO proposals.

    This handler coordinates between core and action proposal handlers to process
    all types of DAO proposals.
    """

    def __init__(self):
        """Initialize the handler with core and action proposal handlers."""
        super().__init__()
        self.core_handler = CoreProposalHandler()
        self.action_handler = ActionProposalHandler()

    def can_handle_transaction(self, transaction: TransactionWithReceipt) -> bool:
        """Check if this handler can handle the given transaction.

        This handler can handle both core and action proposal transactions.

        Args:
            transaction: The transaction to check

        Returns:
            bool: True if this handler can handle the transaction, False otherwise
        """
        return self.core_handler.can_handle_transaction(
            transaction
        ) or self.action_handler.can_handle_transaction(transaction)

    async def handle_transaction(self, transaction: TransactionWithReceipt) -> None:
        """Handle proposal transactions.

        Routes the transaction to either the core or action proposal handler.

        Args:
            transaction: The transaction to handle
        """
        # Extract transaction data to determine which handler to use
        tx_data = self.extract_transaction_data(transaction)
        tx_data_content = tx_data["tx_data"]

        # Get the method name to determine which handler to use
        method = tx_data_content.get("method", "")

        if method == "create-proposal":
            await self.core_handler.handle_transaction(transaction)
        elif method == "propose-action":
            await self.action_handler.handle_transaction(transaction)
        else:
            self.logger.warning(f"Unknown proposal method: {method}")
