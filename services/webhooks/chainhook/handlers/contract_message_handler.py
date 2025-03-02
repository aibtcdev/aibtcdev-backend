"""Handler for capturing messages from contracts."""

from typing import Any, Dict

from backend.factory import backend
from backend.models import ExtensionFilter, QueueMessageCreate
from services.webhooks.chainhook.handlers.base import ChainhookEventHandler
from services.webhooks.chainhook.models import (
    TransactionMetadata,
    TransactionWithReceipt,
)


class ContractMessageHandler(ChainhookEventHandler):
    """Handler for capturing and processing messages from contracts.

    This handler identifies contract calls with specific patterns and
    creates appropriate queue messages for further processing.
    """

    def can_handle(self, transaction: TransactionWithReceipt) -> bool:
        """Check if this handler can handle the given transaction.

        This handler can handle contract call transactions with specific characteristics.

        Args:
            transaction: The transaction to check

        Returns:
            bool: True if this handler can handle the transaction, False otherwise
        """
        tx_data = self.extract_transaction_data(transaction)
        tx_kind = tx_data["tx_kind"]
        tx_data_content = tx_data["tx_data"]
        tx_metadata = tx_data["tx_metadata"]

        # Only handle ContractCall type transactions with 'send' method and unsuccessful status
        if not isinstance(tx_kind, dict):
            self.logger.warning(f"Unexpected tx_kind type: {type(tx_kind)}")
            return False

        tx_kind_type = tx_kind.get("type")

        if not isinstance(tx_data_content, dict):
            self.logger.warning(
                f"Unexpected tx_data_content type: {type(tx_data_content)}"
            )
            return False

        tx_method = tx_data_content.get("method")

        # Access success directly from TransactionMetadata
        tx_success = tx_metadata.success

        # Check if args[1] is "true"
        args = tx_data_content.get("args", [0, "false"])
        should_process = False
        if len(args) > 1 and isinstance(args[1], str):
            should_process = args[1].lower().strip('"').replace('\\"', "") == "true"

        if not should_process:
            self.logger.info(
                f"Skipping transaction as args[1] is not 'true': {args[1] if len(args) > 1 else 'missing'}"
            )

        return (
            tx_kind_type == "ContractCall"
            and tx_method == "send"
            and tx_success is False
            and should_process
        )

    async def handle_transaction(self, transaction: TransactionWithReceipt) -> None:
        """Handle contract message transactions.

        Processes contract call transactions that contain messages,
        creates queue messages for them, and associates them with the appropriate DAO.

        Args:
            transaction: The transaction to handle
        """
        tx_data = self.extract_transaction_data(transaction)
        tx_data_content = tx_data["tx_data"]
        tx_metadata = tx_data["tx_metadata"]

        # Access sender directly from TransactionMetadata
        sender = tx_metadata.sender

        # Get args from tx_data_content
        if not isinstance(tx_data_content, dict):
            self.logger.warning(
                f"Unexpected tx_data_content type: {type(tx_data_content)}"
            )
            return

        args = tx_data_content.get("args", [0, "false"])
        contract_identifier = tx_data_content.get("contract_identifier")

        self.logger.info(f"Processing message from sender {sender} with args: {args}")

        # Find the extension associated with this contract
        extension = backend.list_extensions(
            filters=ExtensionFilter(contract_principal=contract_identifier)
        )

        if extension:
            # Strip quotes from the message if it's a string
            message = args[0]
            if isinstance(message, str):
                # Handle both regular quotes and escaped quotes
                message = message.strip('"')
                # Remove escaped quotes (\") if present
                message = message.replace('\\"', "")

            # Create a new queue message for the DAO
            new_message = backend.create_queue_message(
                QueueMessageCreate(
                    type="tweet",
                    message={"message": message},
                    dao_id=extension[0].dao_id,
                )
            )
            self.logger.info(f"Created queue message: {new_message}")
        else:
            self.logger.warning(
                f"No extension found for contract {contract_identifier}"
            )
