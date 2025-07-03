"""Handler for capturing new DAO core proposals."""

from typing import Dict, Optional

from app.backend.factory import backend
from app.backend.models import (
    ContractStatus,
    ProposalCreate,
    ProposalFilter,
    ProposalType,
)
from app.services.integrations.webhooks.chainhook.handlers.base_proposal_handler import (
    BaseProposalHandler,
)
from app.services.integrations.webhooks.chainhook.models import (
    Event,
    TransactionWithReceipt,
)


class CoreProposalHandler(BaseProposalHandler):
    """Handler for capturing and processing new DAO core proposals.

    This handler identifies contract calls related to proposing core contracts in DAO,
    creates proposal records in the database, and tracks their lifecycle.
    """

    def can_handle_transaction(self, transaction: TransactionWithReceipt) -> bool:
        """Check if this handler can handle the given transaction.

        This handler can handle contract call transactions related to core proposals.

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

        # Check if the method name is exactly "create-proposal"
        tx_method = tx_data_content.get("method", "")
        is_proposal_method = tx_method == "create-proposal"

        # Access success from TransactionMetadata
        tx_success = tx_metadata.success

        if is_proposal_method and tx_success:
            self.logger.debug(f"Found core proposal method: {tx_method}")

        return (
            tx_kind_type == "ContractCall" and is_proposal_method and tx_success is True
        )

    def _get_proposal_info_from_events(self, events: list[Event]) -> Optional[Dict]:
        """Extract the core proposal information from transaction events.

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
            notification = value.get("notification", "")
            if notification == "create-proposal" or notification.endswith(
                "/create-proposal"
            ):
                payload = value.get("payload", {})
                if not payload:
                    self.logger.warning("Empty payload in proposal event")
                    return None

                return {
                    "proposal": payload.get("proposal"),  # Contract to be deployed
                    "caller": payload.get("caller"),
                    "creator": payload.get("creator"),
                    "liquid_tokens": str(payload.get("liquidTokens")),
                    "bond": str(payload.get("bond")),
                    # Fields from updated payload (if available)
                    "contract_caller": payload.get("contractCaller"),
                    "created_btc": payload.get("createdBtc"),
                    "created_stx": payload.get("createdStx"),
                    "creator_user_id": payload.get("creatorUserId"),
                    "exec_end": payload.get("execEnd"),
                    "exec_start": payload.get("execStart"),
                    "memo": payload.get("memo"),
                    "tx_sender": payload.get("txSender"),
                    "vote_end": payload.get("voteEnd"),
                    "vote_start": payload.get("voteStart"),
                    "voting_delay": payload.get("votingDelay"),
                    "voting_period": payload.get("votingPeriod"),
                    "voting_quorum": payload.get("votingQuorum"),
                    "voting_reward": (
                        str(payload.get("votingReward"))
                        if payload.get("votingReward") is not None
                        else None
                    ),
                    "voting_threshold": payload.get("votingThreshold"),
                }

        self.logger.warning("Could not find proposal information in transaction events")
        return None

    async def handle_transaction(self, transaction: TransactionWithReceipt) -> None:
        """Handle core proposal transactions.

        Processes new core proposal transactions and creates proposal records in the database.

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
            f"Processing new core proposal {proposal_info['proposal']} for DAO {dao_data['name']} "
            f"(contract: {contract_identifier})"
        )

        # Check if the proposal already exists in the database
        existing_proposals = backend.list_proposals(
            filters=ProposalFilter(
                dao_id=dao_data["id"],
                contract_principal=contract_identifier,
                type=ProposalType.CORE,
            )
        )

        if not existing_proposals:
            # Create a new proposal record in the database
            proposal_title = f"Core Proposal: {proposal_info['proposal']}"
            proposal = backend.create_proposal(
                ProposalCreate(
                    dao_id=dao_data["id"],
                    title=proposal_title,
                    content=f"Core contract proposal for {proposal_info['proposal']}",
                    contract_principal=contract_identifier,
                    tx_id=tx_id,
                    status=ContractStatus.DEPLOYED,  # Since it's already on-chain
                    type=ProposalType.CORE,
                    # Add fields from payload
                    caller=proposal_info["caller"],
                    creator=proposal_info["creator"],
                    liquid_tokens=proposal_info["liquid_tokens"],
                    bond=proposal_info["bond"],
                    # Fields from updated payload (if available)
                    contract_caller=proposal_info["contract_caller"],
                    created_btc=proposal_info["created_btc"],
                    created_stx=proposal_info["created_stx"],
                    creator_user_id=proposal_info["creator_user_id"],
                    exec_end=proposal_info["exec_end"],
                    exec_start=proposal_info["exec_start"],
                    memo=proposal_info["memo"],
                    tx_sender=proposal_info["tx_sender"],
                    vote_end=proposal_info["vote_end"],
                    vote_start=proposal_info["vote_start"],
                    voting_delay=proposal_info["voting_delay"],
                    voting_period=proposal_info["voting_period"],
                    voting_quorum=proposal_info["voting_quorum"],
                    voting_reward=proposal_info["voting_reward"],
                    voting_threshold=proposal_info["voting_threshold"],
                )
            )
            self.logger.info(
                f"Created new core proposal record in database: {proposal.id}"
            )
        else:
            self.logger.info(
                f"Core proposal already exists in database: {existing_proposals[0].id}"
            )
