"""Handler for checking burn height against proposal start blocks."""

from typing import Dict, List, Optional
from uuid import UUID

from backend.factory import backend
from backend.models import (
    ContractStatus,
    ProposalFilter,
    QueueMessageCreate,
    WalletTokenFilter,
)
from lib.logger import configure_logger
from services.webhooks.chainhook.handlers.base import ChainhookEventHandler
from services.webhooks.chainhook.models import Event, TransactionWithReceipt


class DAOProposalBurnHeightHandler(ChainhookEventHandler):
    """Handler for checking burn height against proposal start blocks.

    This handler monitors burn height events and identifies proposals that should
    start at or after the current burn height. For each eligible proposal, it
    finds relevant agents holding governance tokens and creates queue messages
    for them to evaluate and vote.
    """

    def __init__(self):
        """Initialize the handler with a logger."""
        super().__init__()
        self.logger = configure_logger(self.__class__.__name__)

    def can_handle(self, transaction: TransactionWithReceipt) -> bool:
        """Check if this handler can handle the given transaction.

        This handler looks for burn block height events.

        Args:
            transaction: The transaction to check

        Returns:
            bool: True if this handler can handle the transaction, False otherwise
        """
        tx_data = self.extract_transaction_data(transaction)
        tx_metadata = tx_data["tx_metadata"]

        # Check if this is a burn block height event
        events = tx_metadata.receipt.events if hasattr(tx_metadata, "receipt") else []

        for event in events:
            if (
                event.type == "SmartContractEvent"
                and hasattr(event, "data")
                and event.data.get("topic") == "print"
            ):
                value = event.data.get("value", {})
                if value.get("notification") == "burn-block-height":
                    return True

        return False

    def _get_burn_height_from_events(self, events: List[Event]) -> Optional[int]:
        """Extract the burn block height from transaction events.

        Args:
            events: List of events from the transaction

        Returns:
            Optional[int]: The burn block height if found, None otherwise
        """
        for event in events:
            if (
                event.type == "SmartContractEvent"
                and hasattr(event, "data")
                and event.data.get("topic") == "print"
            ):
                value = event.data.get("value", {})
                if value.get("notification") == "burn-block-height":
                    return value.get("height")
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
        """Handle burn height check transactions.

        Processes burn height events, finds proposals that should start at or after
        the current burn height, and creates queue messages for token holders to vote.

        Args:
            transaction: The transaction to handle
        """
        tx_data = self.extract_transaction_data(transaction)
        tx_metadata = tx_data["tx_metadata"]

        # Get burn height from events
        events = tx_metadata.receipt.events if hasattr(tx_metadata, "receipt") else []
        burn_height = self._get_burn_height_from_events(events)

        if burn_height is None:
            self.logger.warning("Could not determine burn height from transaction")
            return

        self.logger.info(f"Processing burn height: {burn_height}")

        # Find proposals that should start at this height
        proposals = backend.list_proposals(
            filters=ProposalFilter(
                status=ContractStatus.DEPLOYED,
            )
        )

        # Filter proposals that should start at or after this burn height
        eligible_proposals = [
            p
            for p in proposals
            if p.start_block is not None and p.start_block <= burn_height
        ]

        if not eligible_proposals:
            self.logger.info(
                f"No eligible proposals found for burn height {burn_height}"
            )
            return

        self.logger.info(f"Found {len(eligible_proposals)} eligible proposals")

        # Process each eligible proposal
        for proposal in eligible_proposals:
            # Get the DAO for this proposal
            dao = backend.get_dao(proposal.dao_id)
            if not dao:
                self.logger.warning(f"No DAO found for proposal {proposal.id}")
                continue

            # Get agents holding governance tokens
            agents = self._get_agent_token_holders(dao.id)
            if not agents:
                self.logger.warning(f"No agents found holding tokens for DAO {dao.id}")
                continue

            # Create queue messages for each agent to evaluate and vote
            for agent in agents:
                new_message = backend.create_queue_message(
                    QueueMessageCreate(
                        type="dao_proposal_vote",
                        message={
                            "action_proposals_contract": proposal.contract_principal,
                            "proposal_id": proposal.proposal_id,
                            "dao_name": dao.name,
                            "burn_height": burn_height,
                        },
                        dao_id=dao.id,
                        wallet_id=agent["wallet_id"],
                    )
                )
                self.logger.info(
                    f"Created queue message for agent {agent['agent_id']} "
                    f"to evaluate proposal {proposal.proposal_id}: {new_message.id}"
                )
