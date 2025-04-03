"""Handler for capturing messages from contracts."""

from typing import Dict, List, Optional

from backend.factory import backend
from backend.models import ExtensionFilter, QueueMessageCreate
from services.webhooks.chainhook.handlers.base import ChainhookEventHandler
from services.webhooks.chainhook.models import Event, TransactionWithReceipt


class ContractMessageHandler(ChainhookEventHandler):
    """Handler for capturing and processing messages from contracts.

    This handler identifies contract calls with specific patterns and
    creates appropriate queue messages for further processing.
    """

    def can_handle_transaction(self, transaction: TransactionWithReceipt) -> bool:
        """Check if this handler can handle the given transaction.

        This handler can handle contract call transactions with conclude-proposal method.

        Args:
            transaction: The transaction to check

        Returns:
            bool: True if this handler can handle the transaction, False otherwise
        """
        tx_data = self.extract_transaction_data(transaction)
        tx_kind = tx_data["tx_kind"]
        tx_data_content = tx_data["tx_data"]
        tx_metadata = tx_data["tx_metadata"]

        # Only handle ContractCall type transactions
        if not isinstance(tx_kind, dict):
            self.logger.debug(f"Skipping: tx_kind is not a dict: {type(tx_kind)}")
            return False

        tx_kind_type = tx_kind.get("type")

        if not isinstance(tx_data_content, dict):
            self.logger.debug(
                f"Skipping: tx_data_content is not a dict: {type(tx_data_content)}"
            )
            return False

        # Check if the method name is exactly "conclude-proposal"
        tx_method = tx_data_content.get("method", "")
        is_conclude_proposal = tx_method == "conclude-proposal"

        # Access success from TransactionMetadata
        tx_success = tx_metadata.success

        if is_conclude_proposal and tx_success:
            self.logger.debug(f"Found conclude-proposal method: {tx_method}")

        return (
            tx_kind_type == "ContractCall"
            and is_conclude_proposal
            and tx_success is True
        )

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

    def _get_message_from_events(self, events: List[Event]) -> Optional[str]:
        """Extract the message from onchain-messaging contract events.

        Args:
            events: List of events from the transaction

        Returns:
            Optional[str]: The message if found, None otherwise
        """
        for event in events:
            # Find print events from onchain-messaging contract
            if (
                event.type == "SmartContractEvent"
                and hasattr(event, "data")
                and event.data.get("topic") == "print"
                and "onchain-messaging" in event.data.get("contract_identifier", "")
            ):
                # Get the value directly if it's a string
                value = event.data.get("value")
                if isinstance(value, str):
                    return value

        self.logger.warning("Could not find message in transaction events")
        return None

    async def handle_transaction(self, transaction: TransactionWithReceipt) -> None:
        """Handle contract message transactions.

        Processes contract call transactions that contain messages from concluded proposals,
        creates queue messages for them, and associates them with the appropriate DAO.

        Args:
            transaction: The transaction to handle
        """
        tx_data = self.extract_transaction_data(transaction)
        tx_data_content = tx_data["tx_data"]
        tx_metadata = tx_data["tx_metadata"]

        # Get contract identifier
        contract_identifier = tx_data_content.get("contract_identifier")
        if not contract_identifier:
            self.logger.warning("No contract identifier found in transaction data")
            return

        # Find the DAO for this contract
        dao_data = self._find_dao_for_contract(contract_identifier)
        if not dao_data:
            self.logger.warning(f"No DAO found for contract {contract_identifier}")
            return

        # Get the message from the transaction events
        events = tx_metadata.receipt.events if hasattr(tx_metadata, "receipt") else []
        message = self._get_message_from_events(events)
        if message is None:
            self.logger.warning("Could not find message in transaction events")
            return

        self.logger.info(f"Processing message from DAO {dao_data['name']}: {message}")

        # Create a new queue message for the DAO
        new_message = backend.create_queue_message(
            QueueMessageCreate(
                type="tweet",
                message={"message": message},
                dao_id=dao_data["id"],
            )
        )
        self.logger.info(f"Created queue message: {new_message.id}")
