"""Handler for updating transaction status in the database."""

from typing import Any, List, Tuple

from backend.factory import backend
from backend.models import (
    ContractStatus,
    ExtensionBase,
    ExtensionFilter,
    ProposalBase,
    ProposalFilter,
    TokenBase,
    TokenFilter,
)
from services.webhooks.chainhook.handlers.base import ChainhookEventHandler
from services.webhooks.chainhook.models import TransactionWithReceipt


class TransactionStatusHandler(ChainhookEventHandler):
    """Handler for updating transaction status in the database.

    This handler is responsible for finding and updating the status of
    pending extensions, tokens, and proposals when their corresponding
    transactions are confirmed on the blockchain.
    """

    def can_handle(self, transaction: TransactionWithReceipt) -> bool:
        """Check if this handler can handle the given transaction.

        This handler can handle any transaction as it simply checks if the
        transaction ID matches any pending items in the database.

        Args:
            transaction: The transaction to check

        Returns:
            bool: True if this handler can handle the transaction, False otherwise
        """
        # This handler can handle any transaction that has a transaction ID
        return True

    def _get_pending_items(self) -> Tuple[List[Any], List[Any], List[Any]]:
        """Get all pending extensions, tokens, and proposals.

        Returns:
            Tuple of lists containing pending extensions, tokens, and proposals
        """
        non_processed_extensions = backend.list_extensions(
            filters=ExtensionFilter(status=ContractStatus.PENDING)
        )
        non_processed_tokens = backend.list_tokens(
            filters=TokenFilter(status=ContractStatus.PENDING)
        )
        non_processed_proposals = backend.list_proposals(
            filters=ProposalFilter(status=ContractStatus.PENDING)
        )

        self.logger.info(
            f"Found {len(non_processed_extensions)} pending extensions, "
            f"{len(non_processed_tokens)} pending tokens, "
            f"{len(non_processed_proposals)} pending proposals"
        )

        return non_processed_extensions, non_processed_tokens, non_processed_proposals

    def _update_pending_items(
        self,
        tx_id: str,
        non_processed_extensions: List[Any],
        non_processed_tokens: List[Any],
        non_processed_proposals: List[Any],
    ) -> None:
        """Update status of pending items if they match the transaction ID.

        Args:
            tx_id: Transaction ID to match
            non_processed_extensions: List of pending extensions
            non_processed_tokens: List of pending tokens
            non_processed_proposals: List of pending proposals
        """
        for extension in non_processed_extensions:
            if extension.tx_id == tx_id:
                self.logger.info(
                    f"Updating extension {extension.id} from {extension.status} to {ContractStatus.DEPLOYED}"
                )
                backend.update_extension(
                    extension.id,
                    update_data=ExtensionBase(status=ContractStatus.DEPLOYED),
                )

        for token in non_processed_tokens:
            if token.tx_id == tx_id:
                self.logger.info(
                    f"Updating token {token.id} from {token.status} to {ContractStatus.DEPLOYED}"
                )
                backend.update_token(
                    token.id,
                    update_data=TokenBase(status=ContractStatus.DEPLOYED),
                )

        for proposal in non_processed_proposals:
            if proposal.tx_id == tx_id:
                self.logger.info(
                    f"Updating proposal {proposal.id} from {proposal.status} to {ContractStatus.DEPLOYED}"
                )
                backend.update_proposal(
                    proposal.id,
                    update_data=ProposalBase(status=ContractStatus.DEPLOYED),
                )

    async def handle_transaction(self, transaction: TransactionWithReceipt) -> None:
        """Handle transaction status updates.

        Updates the status of any pending items in the database if they match
        the transaction ID.

        Args:
            transaction: The transaction to handle
        """
        tx_data = self.extract_transaction_data(transaction)
        tx_id = tx_data["tx_id"]

        self.logger.info(f"Processing transaction status for transaction {tx_id}")

        # Get all pending items
        pending_items = self._get_pending_items()

        # Update pending items if they match the transaction ID
        self._update_pending_items(tx_id, *pending_items)
