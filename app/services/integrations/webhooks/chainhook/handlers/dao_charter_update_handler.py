"""Handler for DAO charter update transactions."""

import logging
from typing import Any, Dict

from app.backend.factory import backend
from app.backend.models import DAOBase, ExtensionFilter, ContractStatus
from app.services.integrations.webhooks.chainhook.handlers.base import ChainhookEventHandler
from app.services.integrations.webhooks.chainhook.models import TransactionWithReceipt
from app.services.integrations.webhooks.dao.models import ContractType, ExtensionsSubtype
from app.services.processing.stacks_chainhook_adapter.parsers.clarity import ClarityParser


class DAOCharterUpdateHandler(ChainhookEventHandler):
    """Handler for set-dao-charter contract calls.

    This handler detects transactions that update a DAO's charter and processes
    the event to update the backend database.
    """

    def __init__(self):
        super().__init__()
        self.parser = ClarityParser(logger=self.logger)

    def can_handle_transaction(self, transaction: TransactionWithReceipt) -> bool:
        """Check if this is a set-dao-charter transaction."""
        tx_data = self.extract_transaction_data(transaction)
        tx_metadata = tx_data["tx_metadata"]
        if not hasattr(tx_metadata, "kind") or tx_metadata.kind.type != "ContractCall":
            return False

        if not tx_metadata.success:
            return False

        contract_data = tx_metadata.kind.data
        method = getattr(contract_data, "method", "")
        contract_id = getattr(contract_data, "contract_identifier", "")

        return method == "set-dao-charter" and "-dao-charter" in contract_id

    async def handle_transaction(self, transaction: TransactionWithReceipt) -> None:
        """Handle the charter update transaction."""
        tx_data = self.extract_transaction_data(transaction)

        if not tx_data["tx_metadata"].success:
            self.logger.warning("Transaction failed, skipping charter update")
            return

        # Find the print event (smart_contract_log)
        print_events = [
            event for event in tx_data["tx_metadata"].receipt.events
            if event.type == "SmartContractEvent" and "print" in event.data.get("topic", "")
        ]
        if not print_events:
            self.logger.warning("No print event found in set-dao-charter transaction")
            return

        # Parse the Clarity repr from the event
        for event in print_events:
            parsed_data = self.parser.parse(event.data)
            if isinstance(parsed_data, dict) and "payload" in parsed_data:
                payload = parsed_data["payload"]
                dao_principal = payload.get("dao", "")
                new_charter = payload.get("charter", "")
                previous_charter = payload.get("previousCharter", "")

                self.logger.info(
                    f"Detected DAO charter update for DAO {dao_principal}: "
                    f"New charter length: {len(new_charter)}"
                )

                # Query for DAO ID via extensions
                ext_filter = ExtensionFilter(
                    contract_principal=dao_principal,
                    type=ContractType.EXTENSIONS.value,
                    subtype=ExtensionsSubtype.DAO_CHARTER.value,
                    status=ContractStatus.DEPLOYED
                )
                extensions = backend.list_extensions(ext_filter)
                if not extensions or not extensions[0].dao_id:
                    self.logger.error(f"No matching DAO found for principal {dao_principal}")
                    return

                dao_id = extensions[0].dao_id

                # Optional: Validate previous_charter
                current_dao = backend.get_dao(dao_id)
                if current_dao and current_dao.charter != previous_charter:
                    self.logger.warning("Charter mismatch, possible race condition - skipping")
                    return

                # Update the DAO
                update_data = DAOBase(charter=new_charter)
                updated_dao = backend.update_dao(dao_id, update_data)
                if updated_dao:
                    self.logger.info(f"Successfully updated DAO {dao_id} with new charter")
                else:
                    self.logger.error(f"Failed to update DAO {dao_id}")
