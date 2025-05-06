"""Handler for capturing new DAO action proposals."""

from typing import Dict, Optional

from backend.factory import backend
from backend.models import (
    ContractStatus,
    ProposalCreate,
    ProposalFilter,
    ProposalType,
)
from services.webhooks.chainhook.handlers.base_proposal_handler import (
    BaseProposalHandler,
)
from services.webhooks.chainhook.models import Event, TransactionWithReceipt
from services.workflows.utils import decode_hex_parameters


class ActionProposalHandler(BaseProposalHandler):
    """Handler for capturing and processing new DAO action proposals.

    This handler identifies contract calls related to proposing actions in DAO contracts,
    creates proposal records in the database, and tracks their lifecycle.
    """

    def can_handle_transaction(self, transaction: TransactionWithReceipt) -> bool:
        """Check if this handler can handle the given transaction.

        This handler can handle contract call transactions related to proposing actions.

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

        # Check if the method name is exactly "propose-action"
        tx_method = tx_data_content.get("method", "")
        is_proposal_method = tx_method == "propose-action"

        # Access success from TransactionMetadata
        tx_success = tx_metadata.success

        if is_proposal_method and tx_success:
            self.logger.debug(f"Found action proposal method: {tx_method}")

        return (
            tx_kind_type == "ContractCall" and is_proposal_method and tx_success is True
        )

    def _get_proposal_info_from_events(self, events: list[Event]) -> Optional[Dict]:
        """Extract the action proposal information from transaction events.

        Args:
            events: List of events from the transaction

        Returns:
            Optional[Dict]: Dictionary containing proposal information if found, None otherwise
        """
        for event in events:
            # Find SmartContractEvent events
            if event.type != "SmartContractEvent" or not hasattr(event, "data"):
                continue

            event_data = event.data

            # Check if this is a print event
            if event_data.get("topic") != "print":
                continue

            # Get the value, which might be None
            value = event_data.get("value")

            # Skip events with null values
            if value is None:
                self.logger.debug("Value is None in SmartContractEvent data")
                continue

            # Check if this is a proposal event
            if value.get("notification") == "propose-action":
                payload = value.get("payload", {})
                if not payload:
                    self.logger.warning("Empty payload in proposal event")
                    return None

                return {
                    "proposal_id": payload.get("proposalId"),
                    "action": payload.get("action"),
                    "caller": payload.get("caller"),
                    "creator": payload.get("creator"),
                    "created_at_block": payload.get("createdAt"),
                    "end_block": payload.get("endBlock"),
                    "start_block": payload.get("startBlock"),
                    "liquid_tokens": str(payload.get("liquidTokens")),
                    "parameters": payload.get("parameters"),
                    "bond": str(payload.get("bond")),
                }

        self.logger.warning("Could not find proposal information in transaction events")
        return None

    async def handle_transaction(self, transaction: TransactionWithReceipt) -> None:
        """Handle action proposal transactions.

        Processes new action proposal transactions and creates proposal records in the database.

        Args:
            transaction: The transaction to handle
        """
        tx_data = self.extract_transaction_data(transaction)
        tx_id = tx_data["tx_id"]
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

        # Get the proposal info from the transaction events
        events = tx_metadata.receipt.events if hasattr(tx_metadata, "receipt") else []
        proposal_info = self._get_proposal_info_from_events(events)
        if proposal_info is None:
            self.logger.warning(
                "Could not determine proposal information from transaction"
            )
            return

        self.logger.info(
            f"Processing new action proposal {proposal_info['proposal_id']} for DAO {dao_data['name']} "
            f"(contract: {contract_identifier})"
        )

        # Check if the proposal already exists in the database
        existing_proposals = backend.list_proposals(
            filters=ProposalFilter(
                dao_id=dao_data["id"],
                contract_principal=contract_identifier,
                proposal_id=proposal_info["proposal_id"],
                type=ProposalType.ACTION,
            )
        )

        if not existing_proposals:
            # Decode parameters if they're hex encoded
            decoded_parameters = decode_hex_parameters(proposal_info["parameters"])
            parameters = (
                decoded_parameters
                if decoded_parameters is not None
                else proposal_info["parameters"]
            )

            # Create a new proposal record in the database
            proposal_title = f"Action Proposal #{proposal_info['proposal_id']}"
            proposal = backend.create_proposal(
                ProposalCreate(
                    dao_id=dao_data["id"],
                    title=proposal_title,
                    description=f"Action proposal {proposal_info['proposal_id']} for {dao_data['name']}",
                    contract_principal=contract_identifier,
                    tx_id=tx_id,
                    proposal_id=proposal_info["proposal_id"],
                    status=ContractStatus.DEPLOYED,  # Since it's already on-chain
                    type=ProposalType.ACTION,
                    # Add fields from payload
                    action=proposal_info["action"],
                    caller=proposal_info["caller"],
                    creator=proposal_info["creator"],
                    created_at_block=proposal_info["created_at_block"],
                    end_block=proposal_info["end_block"],
                    start_block=proposal_info["start_block"],
                    liquid_tokens=proposal_info["liquid_tokens"],
                    parameters=parameters,
                    bond=proposal_info["bond"],
                )
            )
            self.logger.info(
                f"Created new action proposal record in database: {proposal.id}"
            )
        else:
            self.logger.info(
                f"Action proposal already exists in database: {existing_proposals[0].id}"
            )
