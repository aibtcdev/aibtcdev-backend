"""Handler for capturing new DAO action proposals."""

from typing import Dict, List, Optional

from backend.factory import backend
from backend.models import (
    ContractStatus,
    ExtensionFilter,
    ProposalCreate,
    ProposalFilter,
)
from lib.logger import configure_logger
from services.webhooks.chainhook.handlers.base import ChainhookEventHandler
from services.webhooks.chainhook.models import Event, TransactionWithReceipt


class DAOProposalHandler(ChainhookEventHandler):
    """Handler for capturing and processing new DAO action proposals.

    This handler identifies contract calls related to proposing actions in DAO contracts,
    creates proposal records in the database, and triggers the burn height handler
    to manage voting queue messages.
    """

    def __init__(self):
        """Initialize the handler with a logger."""
        super().__init__()
        self.logger = configure_logger(self.__class__.__name__)

    def can_handle(self, transaction: TransactionWithReceipt) -> bool:
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
            self.logger.debug(f"Found proposal method: {tx_method}")

        return (
            tx_kind_type == "ContractCall" and is_proposal_method and tx_success is True
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

    def _get_proposal_id_from_events(self, events: List[Event]) -> Optional[Dict]:
        """Extract the proposal information from transaction events.

        Args:
            events: List of events from the transaction

        Returns:
            Optional[Dict]: Dictionary containing proposal information if found, None otherwise
        """
        for event in events:
            # Find print events with proposal information
            if (
                event.type == "SmartContractEvent"
                and hasattr(event, "data")
                and event.data.get("topic") == "print"
            ):
                event_data = event.data
                value = event_data.get("value", {})

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
                        "liquid_tokens": str(
                            payload.get("liquidTokens")
                        ),  # Convert to string to handle large numbers
                        "parameters": payload.get("parameters"),
                    }

        self.logger.warning("Could not find proposal information in transaction events")
        return None

    async def handle_transaction(self, transaction: TransactionWithReceipt) -> None:
        """Handle DAO proposal transactions.

        Processes new action proposal transactions and creates proposal records in the database.
        The burn height handler will manage the creation of voting queue messages.

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

        # Get the proposal ID from the transaction events
        events = tx_metadata.receipt.events if hasattr(tx_metadata, "receipt") else []
        proposal_info = self._get_proposal_id_from_events(events)
        if proposal_info is None:
            self.logger.warning(
                "Could not determine proposal information from transaction"
            )
            return

        self.logger.info(
            f"Processing new proposal {proposal_info['proposal_id']} for DAO {dao_data['name']} "
            f"(contract: {contract_identifier})"
        )

        # Check if the proposal already exists in the database
        existing_proposals = backend.list_proposals(
            filters=ProposalFilter(
                dao_id=dao_data["id"],
                contract_principal=contract_identifier,
                proposal_id=proposal_info["proposal_id"],
            )
        )

        if not existing_proposals:
            # Create a new proposal record in the database
            proposal_title = f"Proposal #{proposal_info['proposal_id']}"
            proposal = backend.create_proposal(
                ProposalCreate(
                    dao_id=dao_data["id"],
                    title=proposal_title,
                    description=f"On-chain proposal {proposal_info['proposal_id']} for {dao_data['name']}",
                    contract_principal=contract_identifier,
                    tx_id=tx_id,
                    proposal_id=proposal_info["proposal_id"],
                    status=ContractStatus.DEPLOYED,  # Since it's already on-chain
                    # Add new fields from payload
                    action=proposal_info["action"],
                    caller=proposal_info["caller"],
                    creator=proposal_info["creator"],
                    created_at_block=proposal_info["created_at_block"],
                    end_block=proposal_info["end_block"],
                    start_block=proposal_info["start_block"],
                    liquid_tokens=proposal_info["liquid_tokens"],
                    parameters=proposal_info["parameters"],
                )
            )
            self.logger.info(f"Created new proposal record in database: {proposal.id}")
        else:
            self.logger.info(
                f"Proposal already exists in database: {existing_proposals[0].id}"
            )
