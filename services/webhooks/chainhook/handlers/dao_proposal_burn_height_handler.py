"""Handler for checking burn height against proposal start blocks."""

from typing import Dict, List, Optional
from uuid import UUID

from backend.factory import backend
from backend.models import (
    ContractStatus,
    ProposalFilter,
    QueueMessageCreate,
    QueueMessageFilter,
    QueueMessageType,
)
from config import config
from lib.logger import configure_logger
from services.webhooks.chainhook.handlers.base import ChainhookEventHandler
from services.webhooks.chainhook.models import ChainHookData, TransactionWithReceipt


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
        self.chainhook_data: Optional[ChainHookData] = None

    def set_chainhook_data(self, data: ChainHookData) -> None:
        """Set the chainhook data for this handler.

        Args:
            data: The chainhook data to set
        """
        self.chainhook_data = data

    def can_handle_transaction(self, transaction: TransactionWithReceipt) -> bool:
        """Check if this handler can handle the given transaction.

        This handler processes blocks with Coinbase transactions since they indicate
        a new block has been mined.

        Args:
            transaction: The transaction to check

        Returns:
            bool: True if this is a Coinbase transaction, False otherwise
        """
        if isinstance(transaction.metadata, dict):
            kind = transaction.metadata.get("kind", {})
        else:
            kind = transaction.metadata.kind

        if isinstance(kind, dict):
            return kind.get("type") == "Coinbase"
        return getattr(kind, "type", None) == "Coinbase"

    def _get_burn_height(self, tx_data: Dict) -> Optional[int]:
        """Extract the burn block height from transaction data.

        Args:
            tx_data: Transaction data (unused)

        Returns:
            Optional[int]: The burn block height from bitcoin anchor block identifier
        """
        # Get burn height from the apply block data
        if self.chainhook_data and self.chainhook_data.apply:
            apply_block = self.chainhook_data.apply[0]  # Get first apply block
            if (
                apply_block.metadata
                and apply_block.metadata.bitcoin_anchor_block_identifier
            ):
                return apply_block.metadata.bitcoin_anchor_block_identifier.index
        return None

    def _get_agent_token_holders(self, dao_id: UUID) -> List[Dict]:
        """Get agents that hold tokens for the given DAO.

        Args:
            dao_id: The ID of the DAO

        Returns:
            List[Dict]: List of agents with their wallet IDs
        """
        # Use the specialized backend method for getting agents with DAO tokens
        agents_with_tokens_dto = backend.get_agents_with_dao_tokens(dao_id)

        if not agents_with_tokens_dto:
            self.logger.error(f"No agents found with tokens for DAO {dao_id}")
            return []

        # Convert DTOs to the expected format
        agents_with_tokens = [
            {"agent_id": dto.agent_id, "wallet_id": dto.wallet_id}
            for dto in agents_with_tokens_dto
        ]

        self.logger.info(
            f"Found {len(agents_with_tokens)} agents holding tokens for DAO {dao_id}"
        )

        return agents_with_tokens

    def _queue_message_exists(
        self,
        message_type: QueueMessageType,
        proposal_id: UUID,
        dao_id: UUID,
        wallet_id: Optional[UUID] = None,
    ) -> bool:
        """Check if a queue message already exists for the given parameters.

        Args:
            message_type: Type of queue message
            proposal_id: The proposal ID
            dao_id: The DAO ID
            wallet_id: Optional wallet ID for vote messages

        Returns:
            bool: True if message exists, False otherwise
        """
        filters = QueueMessageFilter(
            type=message_type,
            dao_id=dao_id,
            is_processed=False,
        )

        if wallet_id:
            filters.wallet_id = wallet_id

        existing_messages = backend.list_queue_messages(filters=filters)

        # Check if any existing message is for this specific proposal
        return any(
            msg.message and msg.message.get("proposal_id") == str(proposal_id)
            for msg in existing_messages
        )

    async def handle_transaction(self, transaction: TransactionWithReceipt) -> None:
        """Handle burn height check transactions.

        Processes burn height events, finds proposals that should start at or after
        the current burn height, and creates queue messages for token holders to vote.
        Also handles veto window notifications.

        Args:
            transaction: The transaction to handle
        """
        tx_data = self.extract_transaction_data(transaction)
        burn_height = self._get_burn_height(tx_data)

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

        # Filter proposals that should start or end at this burn height
        vote_proposals = [
            p
            for p in proposals
            if p.vote_start is not None
            and p.vote_end is not None
            and p.vote_start == burn_height
            and p.content is not None  # Ensure content exists
        ]

        end_proposals = [
            p
            for p in proposals
            if p.vote_start is not None
            and p.exec_start is not None
            and p.exec_start == burn_height
            and p.content is not None  # Ensure content exists
        ]

        # Add veto window proposals
        veto_start_proposals = [
            p
            for p in proposals
            if p.vote_end is not None
            and p.vote_end == burn_height
            and p.content is not None
        ]

        veto_end_proposals = [
            p
            for p in proposals
            if p.exec_start is not None
            and p.exec_start == burn_height
            and p.content is not None
        ]

        if not (
            vote_proposals
            or end_proposals
            or veto_start_proposals
            or veto_end_proposals
        ):
            self.logger.info(
                f"No eligible proposals found for burn height {burn_height}"
            )
            return

        self.logger.info(
            f"Found {len(vote_proposals)} proposals to vote, "
            f"{len(end_proposals)} proposals to conclude, "
            f"{len(veto_start_proposals)} proposals entering veto window, "
            f"{len(veto_end_proposals)} proposals ending veto window"
        )

        # Process veto window start notifications
        for proposal in veto_start_proposals:
            dao = backend.get_dao(proposal.dao_id)
            if not dao:
                self.logger.warning(f"No DAO found for proposal {proposal.id}")
                continue

            # Check if a veto notification message already exists
            if self._queue_message_exists(
                QueueMessageType.get_or_create("discord"), proposal.id, dao.id
            ):
                self.logger.debug(
                    f"Veto notification Discord message already exists for proposal {proposal.id}, skipping"
                )
                continue

            # Create veto window start Discord message
            message = (
                f"⚠️ **VETO WINDOW OPEN: Proposal #{proposal.proposal_id} of {dao.name}**\n\n"
                f"**Proposal:**\n{proposal.content[:100]}...\n\n"
                f"**Veto Window Details:**\n"
                f"• Opens at: Block {proposal.vote_end}\n"
                f"• Closes at: Block {proposal.exec_start}\n\n"
                f"View proposal details: {config.api.base_url}/proposals/{dao.id}"
            )

            backend.create_queue_message(
                QueueMessageCreate(
                    type=QueueMessageType.get_or_create("discord"),
                    message={"content": message, "proposal_status": "veto_window_open"},
                    dao_id=dao.id,
                )
            )
            self.logger.info(
                f"Created veto window start Discord message for proposal {proposal.id}"
            )

        # Process veto window end notifications
        for proposal in veto_end_proposals:
            dao = backend.get_dao(proposal.dao_id)
            if not dao:
                self.logger.warning(f"No DAO found for proposal {proposal.id}")
                continue

            # Check if a veto end notification message already exists
            if self._queue_message_exists(
                QueueMessageType.get_or_create("discord"), proposal.id, dao.id
            ):
                self.logger.debug(
                    f"Veto end notification Discord message already exists for proposal {proposal.id}, skipping"
                )
                continue

            # Create veto window end Discord message
            message = (
                f"🔒 **VETO WINDOW CLOSED: Proposal #{proposal.proposal_id} of {dao.name}**\n\n"
                f"**Proposal:**\n{proposal.content[:100]}...\n\n"
                f"**Status:**\n"
                f"• Veto window has now closed\n"
                f"• Proposal will be executed if it passed voting\n\n"
                f"View proposal details: {config.api.base_url}/proposals/{dao.id}"
            )

            backend.create_queue_message(
                QueueMessageCreate(
                    type=QueueMessageType.get_or_create("discord"),
                    message={
                        "content": message,
                        "proposal_status": "veto_window_closed",
                    },
                    dao_id=dao.id,
                )
            )
            self.logger.info(
                f"Created veto window end Discord message for proposal {proposal.id}"
            )

        # Process proposals that are ending
        for proposal in end_proposals:
            dao = backend.get_dao(proposal.dao_id)
            if not dao:
                self.logger.warning(f"No DAO found for proposal {proposal.id}")
                continue

            # Check if a conclude message already exists for this proposal
            if self._queue_message_exists(
                QueueMessageType.get_or_create("dao_proposal_conclude"),
                proposal.id,
                dao.id,
            ):
                self.logger.debug(
                    f"Conclude queue message already exists for proposal {proposal.id}, skipping"
                )
                continue

            # For conclude messages, we only need to create one message per proposal
            message_data = {
                "proposal_id": proposal.id,
            }

            backend.create_queue_message(
                QueueMessageCreate(
                    type=QueueMessageType.get_or_create("dao_proposal_conclude"),
                    message=message_data,
                    dao_id=dao.id,
                    wallet_id=None,  # No specific wallet needed for conclusion
                )
            )

            self.logger.info(
                f"Created conclude queue message for proposal {proposal.id}"
            )

        # Process proposals that are ready for voting
        for proposal in vote_proposals:
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

            # Create vote queue messages for each agent
            for agent in agents:
                # Check if a queue message already exists for this proposal+wallet combination
                if self._queue_message_exists(
                    QueueMessageType.get_or_create("dao_proposal_vote"),
                    proposal.id,
                    dao.id,
                    agent["wallet_id"],
                ):
                    self.logger.debug(
                        f"Queue message already exists for proposal {proposal.id} "
                        f"and wallet {agent['wallet_id']}, skipping"
                    )
                    continue

                message_data = {
                    "proposal_id": proposal.id,
                }

                backend.create_queue_message(
                    QueueMessageCreate(
                        type=QueueMessageType.get_or_create("dao_proposal_vote"),
                        message=message_data,
                        dao_id=dao.id,
                        wallet_id=agent["wallet_id"],
                    )
                )

                self.logger.info(
                    f"Created vote queue message for agent {agent['agent_id']} "
                    f"to vote on proposal {proposal.id}"
                )
