"""Handler for capturing DAO proposal conclusions."""

from typing import Dict, List, Optional

from backend.factory import backend
from backend.models import ProposalBase, ProposalFilter, ProposalType
from lib.logger import configure_logger
from services.integrations.webhooks.chainhook.handlers.base import ChainhookEventHandler
from services.integrations.webhooks.chainhook.models import (
    Event,
    TransactionWithReceipt,
)


class DAOProposalConclusionHandler(ChainhookEventHandler):
    """Handler for capturing and processing DAO proposal conclusions.

    This handler identifies contract calls related to concluding proposals in DAO contracts
    and updates proposal records in the database with conclusion data.
    """

    def __init__(self):
        """Initialize the handler with a logger."""
        super().__init__()
        self.logger = configure_logger(self.__class__.__name__)

    def can_handle_transaction(self, transaction: TransactionWithReceipt) -> bool:
        """Check if this handler can handle the given transaction.

        This handler can handle contract call transactions related to concluding proposals.

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

        # Check if the method name is "conclude-proposal"
        tx_method = tx_data_content.get("method", "")
        is_conclude_method = tx_method == "conclude-proposal"

        # Access success from TransactionMetadata
        tx_success = tx_metadata.success

        if is_conclude_method and tx_success:
            self.logger.debug(f"Found conclude proposal method: {tx_method}")

        return (
            tx_kind_type == "ContractCall" and is_conclude_method and tx_success is True
        )

    def _get_conclusion_info_from_events(self, events: List[Event]) -> Optional[Dict]:
        """Extract the conclusion information from transaction events.

        Args:
            events: List of events from the transaction

        Returns:
            Optional[Dict]: Dictionary containing conclusion information if found, None otherwise
        """
        for event in events:
            # Find print events with conclusion information
            if not isinstance(event, Event):
                self.logger.debug(f"Skipping non-Event object: {type(event)}")
                continue

            if not hasattr(event, "type") or event.type != "SmartContractEvent":
                continue

            if not hasattr(event, "data"):
                continue

            event_data = event.data
            if not isinstance(event_data, dict):
                self.logger.debug(f"Event data is not a dictionary: {type(event_data)}")
                continue

            if event_data.get("topic") != "print":
                continue

            value = event_data.get("value")
            if not isinstance(value, dict):
                self.logger.debug(f"Event value is not a dictionary: {type(value)}")
                continue

            if value.get("notification") != "conclude-proposal":
                continue

            payload = value.get("payload")
            if not isinstance(payload, dict):
                self.logger.warning("Empty or invalid payload in conclusion event")
                continue

            # Extract all the conclusion data
            try:
                # Common fields for both types
                base_data = {
                    "caller": payload.get("caller"),
                    "concluded_by": payload.get("concludedBy"),
                    "executed": payload.get("executed"),
                    "liquid_tokens": str(
                        payload.get("liquidTokens", "0")
                    ),  # Default to "0"
                    "met_quorum": payload.get("metQuorum"),
                    "met_threshold": payload.get("metThreshold"),
                    "passed": payload.get("passed"),
                    "votes_against": str(
                        payload.get("votesAgainst", "0")
                    ),  # Default to "0"
                    "votes_for": str(payload.get("votesFor", "0")),  # Default to "0"
                }

                # Check if it's an action proposal (has proposal_id) or core proposal (has proposal contract)
                if "proposalId" in payload:
                    # Action proposal
                    base_data["proposal_id"] = payload.get("proposalId")
                    base_data["type"] = ProposalType.ACTION
                elif "proposal" in payload:
                    # Core proposal
                    # Note: proposal_contract field was removed from the model
                    # The proposal contract info is stored in contract_principal
                    base_data["type"] = ProposalType.CORE
                else:
                    self.logger.warning(
                        "Could not determine proposal type from payload"
                    )
                    continue

                return base_data

            except Exception as e:
                self.logger.error(f"Error extracting conclusion data: {str(e)}")
                continue

        self.logger.warning(
            "Could not find conclusion information in transaction events"
        )
        return None

    async def handle_transaction(self, transaction: TransactionWithReceipt) -> None:
        """Handle DAO proposal conclusion transactions.

        Processes conclusion transactions and updates proposal records in the database with conclusion data.

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

        # Get the conclusion information from the transaction events
        events = tx_metadata.receipt.events if hasattr(tx_metadata, "receipt") else []
        conclusion_info = self._get_conclusion_info_from_events(events)
        if conclusion_info is None:
            self.logger.warning(
                "Could not determine conclusion information from transaction"
            )
            return

        # Extract conclusion details
        proposal_id = conclusion_info.get("proposal_id")

        if not proposal_id:
            self.logger.warning("Missing proposal ID in conclusion information")
            return

        self.logger.info(
            f"Processing conclusion for proposal {proposal_id} "
            f"(contract: {contract_identifier}, tx_id: {tx_id})"
        )

        # Find the proposal in the database
        proposals = backend.list_proposals(
            filters=ProposalFilter(
                contract_principal=contract_identifier,
                proposal_id=proposal_id,
            )
        )

        if not proposals:
            self.logger.warning(
                f"No proposal found for ID {proposal_id} in contract {contract_identifier}"
            )
            return

        proposal = proposals[0]

        # Update the proposal with conclusion data
        self.logger.info(f"Updating proposal {proposal.id} with conclusion data")

        update_data = ProposalBase(
            concluded_by=conclusion_info.get("concluded_by"),
            executed=conclusion_info.get("executed"),
            met_quorum=conclusion_info.get("met_quorum"),
            met_threshold=conclusion_info.get("met_threshold"),
            passed=conclusion_info.get("passed"),
            votes_against=conclusion_info.get("votes_against"),
            votes_for=conclusion_info.get("votes_for"),
            # Update liquid_tokens if it wasn't set before
            liquid_tokens=(
                conclusion_info.get("liquid_tokens")
                if not proposal.liquid_tokens
                else proposal.liquid_tokens
            ),
        )

        try:
            updated_proposal = backend.update_proposal(proposal.id, update_data)
            if updated_proposal:
                self.logger.info(
                    f"Successfully updated proposal {proposal.id} with conclusion data"
                )
            else:
                self.logger.warning(f"Failed to update proposal {proposal.id}")
        except Exception as e:
            self.logger.error(f"Error updating proposal {proposal.id}: {str(e)}")
