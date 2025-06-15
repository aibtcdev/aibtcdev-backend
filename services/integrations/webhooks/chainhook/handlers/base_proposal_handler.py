"""Base handler for DAO proposals."""

from typing import Dict, Optional

from backend.factory import backend
from backend.models import ExtensionFilter
from lib.logger import configure_logger
from services.integrations.webhooks.chainhook.handlers.base import ChainhookEventHandler
from services.integrations.webhooks.chainhook.models import (
    Event,
    TransactionWithReceipt,
)


class BaseProposalHandler(ChainhookEventHandler):
    """Base handler for DAO proposals.

    This handler provides common functionality for both core and action proposals.
    """

    def __init__(self):
        """Initialize the handler with a logger."""
        super().__init__()
        self.logger = configure_logger(self.__class__.__name__)

    def _find_dao_for_contract(self, contract_identifier: str) -> Optional[Dict]:
        """Find the DAO associated with the given contract.

        Args:
            contract_identifier: The contract identifier to search for

        Returns:
            Optional[Dict]: The DAO data if found, None otherwise
        """
        # Find extensions with this contract principal
        extensions = backend.list_extensions(
            filters=ExtensionFilter(
                contract_principal=contract_identifier,
            )
        )

        if not extensions:
            self.logger.warning(
                f"No extensions found for contract {contract_identifier}"
            )
            return None

        # Get the DAO for the first matching extension
        dao_id = extensions[0].dao_id
        if not dao_id:
            self.logger.warning("Extension found but no DAO ID associated with it")
            return None

        dao = backend.get_dao(dao_id)
        if not dao:
            self.logger.warning(f"No DAO found with ID {dao_id}")
            return None

        self.logger.info(f"Found DAO for contract {contract_identifier}: {dao.name}")
        return dao.model_dump()

    def _get_proposal_info_from_events(self, events: list[Event]) -> Optional[Dict]:
        """Extract the proposal information from transaction events.

        This method should be implemented by subclasses to handle their specific
        proposal event formats.

        Args:
            events: List of events from the transaction

        Returns:
            Optional[Dict]: Dictionary containing proposal information if found, None otherwise
        """
        raise NotImplementedError(
            "Subclasses must implement _get_proposal_info_from_events"
        )

    def can_handle_transaction(self, transaction: TransactionWithReceipt) -> bool:
        """Check if this handler can handle the given transaction.

        This method should be implemented by subclasses to check for their specific
        proposal types.

        Args:
            transaction: The transaction to check

        Returns:
            bool: True if this handler can handle the transaction, False otherwise
        """
        raise NotImplementedError("Subclasses must implement can_handle_transaction")

    async def handle_transaction(self, transaction: TransactionWithReceipt) -> None:
        """Handle proposal transactions.

        This method should be implemented by subclasses to handle their specific
        proposal types.

        Args:
            transaction: The transaction to handle
        """
        raise NotImplementedError("Subclasses must implement handle_transaction")
