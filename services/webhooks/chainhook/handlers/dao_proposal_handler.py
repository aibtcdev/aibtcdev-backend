"""Handler for capturing new DAO action proposals."""

from typing import Dict, List, Optional
from uuid import UUID

from backend.factory import backend
from backend.models import (
    ContractStatus,
    ExtensionFilter,
    ProposalCreate,
    ProposalFilter,
    QueueMessageCreate,
    WalletTokenFilter,
)
from lib.logger import configure_logger
from services.webhooks.chainhook.handlers.base import ChainhookEventHandler
from services.webhooks.chainhook.models import Event, TransactionWithReceipt


class DAOProposalHandler(ChainhookEventHandler):
    """Handler for capturing and processing new DAO action proposals.

    This handler identifies contract calls related to proposing actions in DAO contracts,
    finds relevant agents holding governance tokens for the DAO, and
    creates queue messages for those agents to evaluate and vote on the proposal.
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

        # Check if the method name is related to proposing actions
        tx_method = tx_data_content.get("method", "")
        is_proposal_method = (
            "propose" in tx_method.lower() and "action" in tx_method.lower()
        )

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
                type="action_proposals",  # Assuming this is the type for action proposal extensions
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

    def _get_proposal_id_from_events(self, events: List[Event]) -> Optional[int]:
        """Extract the proposal ID from transaction events.

        Args:
            events: List of events from the transaction

        Returns:
            Optional[int]: The proposal ID if found, None otherwise
        """
        for event in events:
            # Find events related to proposal creation
            if "proposal" in event.type.lower() and hasattr(event, "data"):
                event_data = event.data
                # Look for fields that might contain the proposal ID
                for field_name, value in event_data.items():
                    if "id" in field_name.lower() or "proposal" in field_name.lower():
                        try:
                            return int(value)
                        except (ValueError, TypeError):
                            continue

        self.logger.warning("Could not find proposal ID in transaction events")
        return None

    def _get_agent_token_holders(self, dao_id: UUID) -> List[Dict]:
        """Get agents that hold tokens for the given DAO.

        Args:
            dao_id: The ID of the DAO

        Returns:
            List[Dict]: List of agents with their wallet IDs
        """
        # Get wallet-token pairs for this DAO
        wallet_tokens = backend.list_wallet_tokens(WalletTokenFilter(dao_id=dao_id))

        if not wallet_tokens:
            self.logger.info(f"No wallet tokens found for DAO {dao_id}")
            return []

        # Get unique wallet IDs
        wallet_ids = list(set(wt.wallet_id for wt in wallet_tokens))

        # Get agents that own these wallets
        agents_with_tokens = []
        for wallet_id in wallet_ids:
            wallet = backend.get_wallet(wallet_id)
            if wallet and wallet.agent_id:
                agents_with_tokens.append(
                    {"agent_id": wallet.agent_id, "wallet_id": wallet_id}
                )

        self.logger.info(
            f"Found {len(agents_with_tokens)} agents holding tokens for DAO {dao_id}"
        )
        return agents_with_tokens

    async def handle_transaction(self, transaction: TransactionWithReceipt) -> None:
        """Handle DAO proposal transactions.

        Processes new action proposal transactions, identifies agents holding
        governance tokens for the associated DAO, and creates queue messages
        for them to evaluate and vote on the proposal.

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
        proposal_id = self._get_proposal_id_from_events(events)
        if proposal_id is None:
            self.logger.warning("Could not determine proposal ID from transaction")
            return

        self.logger.info(
            f"Processing new proposal {proposal_id} for DAO {dao_data['name']} "
            f"(contract: {contract_identifier})"
        )

        # Check if the proposal already exists in the database
        existing_proposals = backend.list_proposals(
            filters=ProposalFilter(
                dao_id=dao_data["id"],
                contract_principal=contract_identifier,
                proposal_id=proposal_id,
            )
        )

        if not existing_proposals:
            # Create a new proposal record in the database
            proposal_title = f"Proposal #{proposal_id}"
            proposal = backend.create_proposal(
                ProposalCreate(
                    dao_id=dao_data["id"],
                    title=proposal_title,
                    description=f"On-chain proposal {proposal_id} for {dao_data['name']}",
                    contract_principal=contract_identifier,
                    tx_id=tx_id,
                    proposal_id=proposal_id,
                    status=ContractStatus.DEPLOYED,  # Since it's already on-chain
                )
            )
            self.logger.info(f"Created new proposal record in database: {proposal.id}")
        else:
            self.logger.info(
                f"Proposal already exists in database: {existing_proposals[0].id}"
            )

        # Get agents holding governance tokens for this DAO
        agents = self._get_agent_token_holders(dao_data["id"])
        if not agents:
            self.logger.warning(
                f"No agents found holding tokens for DAO {dao_data['id']}"
            )
            return

        # Create queue messages for each agent to evaluate and vote on the proposal
        for agent in agents:
            new_message = backend.create_queue_message(
                QueueMessageCreate(
                    type="dao_proposal_vote",
                    message={
                        "action_proposals_contract": contract_identifier,
                        "proposal_id": proposal_id,
                        "dao_name": dao_data["name"],
                        "tx_id": tx_id,
                    },
                    dao_id=dao_data["id"],
                    wallet_id=agent["wallet_id"],
                )
            )
            self.logger.info(
                f"Created queue message for agent {agent['agent_id']} "
                f"to evaluate proposal {proposal_id}: {new_message.id}"
            )
