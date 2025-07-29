"""Handler for capturing DAO action proposal vetos."""

from typing import Dict, Optional

from app.backend.factory import backend
from app.backend.models import (
    ProposalFilter,
    ProposalType,
    VetoCreate,
    VetoFilter,
    AgentFilter,
)
from app.services.integrations.webhooks.chainhook.handlers.base import (
    ChainhookEventHandler,
)
from app.services.integrations.webhooks.chainhook.models import (
    Event,
    TransactionWithReceipt,
)


class ActionVetoHandler(ChainhookEventHandler):
    """Handler for capturing and processing DAO action proposal vetos.

    This handler identifies contract calls related to vetoing action proposals
    and creates veto records in the database.
    """

    def _find_proposal(
        self, contract_identifier: str, proposal_identifier: int
    ) -> Optional[Dict]:
        """Find the action proposal in the database.

        Args:
            contract_identifier: The contract identifier
            proposal_identifier: The on-chain proposal ID

        Returns:
            Optional[Dict]: The proposal data if found, None otherwise
        """
        proposals = backend.list_proposals(
            filters=ProposalFilter(
                contract_principal=contract_identifier,
                proposal_id=proposal_identifier,
                type=ProposalType.ACTION,
            )
        )

        if not proposals:
            self.logger.warning(
                f"No action proposal found for ID {proposal_identifier} in {contract_identifier}"
            )
            return None

        return proposals[0]

    def _get_veto_info_from_events(self, events: list[Event]) -> Optional[Dict]:
        """Extract the veto information from transaction events.

        Args:
            events: List of events from the transaction

        Returns:
            Optional[Dict]: Dictionary containing veto information if found, None otherwise
        """
        # Collect all potential veto events
        veto_events = []

        for event in events:
            # Find print events with veto information
            if (
                event.type == "SmartContractEvent"
                and hasattr(event, "data")
                and event.data.get("topic") == "print"
            ):
                event_data = event.data
                value = event_data.get("value", {})

                # Check for veto notification formats
                notification = value.get("notification", "")
                if (
                    "veto-action-proposal" in notification
                    or "action-proposal-voting" in notification
                ):
                    payload = value.get("payload", {})
                    if not payload:
                        self.logger.warning("Empty payload in veto event")
                        continue

                    # Extract the voting contract identifier from the event
                    voting_contract = event_data.get("contract_identifier")

                    veto_info = {
                        "proposal_identifier": payload.get("proposalId"),
                        "vetoer": payload.get("vetoer"),
                        "caller": payload.get("contractCaller"),
                        "tx_sender": payload.get("txSender"),
                        "amount": self._extract_amount(payload.get("amount")),
                        "vetoer_user_id": payload.get("vetoerUserId"),
                        "voting_contract": voting_contract,
                        "notification": notification,
                    }
                    veto_events.append(veto_info)

        if not veto_events:
            self.logger.warning("Could not find veto information in transaction events")
            return None

        # Prioritize events from voting contracts (they have complete information)
        voting_contract_events = [
            event
            for event in veto_events
            if "action-proposal-voting" in event.get("notification", "")
            or event.get("vetoer")
        ]

        if voting_contract_events:
            # Use the first voting contract event (has complete info)
            selected_event = voting_contract_events[0]
        else:
            # Fallback to the first event found
            selected_event = veto_events[0]

        # Remove the notification field before returning
        selected_event.pop("notification", None)
        return selected_event

    def _extract_amount(self, amount) -> str:
        """Extract and convert the amount from Clarity format to a string.

        Args:
            amount: The amount value which could be a string with 'u' prefix, integer, or None

        Returns:
            str: The amount as a string, or "0" if None
        """
        if amount is None:
            return "0"

        amount_str = str(amount)
        if amount_str.startswith("u"):
            # Remove the 'u' prefix and return as string
            return amount_str[1:]
        else:
            return amount_str

    def can_handle_transaction(self, transaction: TransactionWithReceipt) -> bool:
        """Check if this handler can handle the given transaction.

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
            return False

        tx_kind_type = tx_kind.get("type")

        if not isinstance(tx_data_content, dict):
            return False

        # Check if the method name contains "veto" and "proposal"
        tx_method = tx_data_content.get("method", "")
        is_veto_method = "veto-action-proposal" in tx_method

        # Access success from TransactionMetadata
        tx_success = tx_metadata.success

        return tx_kind_type == "ContractCall" and is_veto_method and tx_success is True

    async def handle_transaction(self, transaction: TransactionWithReceipt) -> None:
        """Handle veto transactions.

        Processes veto transactions and creates veto records in the database.

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

        # Get the veto information from the transaction events
        events = tx_metadata.receipt.events if hasattr(tx_metadata, "receipt") else []
        veto_info = self._get_veto_info_from_events(events)
        if veto_info is None:
            self.logger.warning("Could not determine veto information from transaction")
            return

        # Extract veto details
        proposal_identifier = veto_info.get("proposal_identifier")
        vetoer_address = veto_info.get("vetoer")
        amount = veto_info.get("amount")
        contract_caller = veto_info.get("caller")
        tx_sender = veto_info.get("tx_sender")
        vetoer_user_id = veto_info.get("vetoer_user_id")

        # Use the voting contract from the event if available, otherwise use the transaction contract
        voting_contract = veto_info.get("voting_contract")
        proposal_contract = voting_contract if voting_contract else contract_identifier

        if not proposal_identifier or not vetoer_address:
            self.logger.warning(
                "Missing proposal identifier or vetoer address in veto information"
            )
            return

        self.logger.info(
            f"Processing veto on proposal {proposal_identifier} by {vetoer_address} "
            f"(tx contract: {contract_identifier}, proposal contract: {proposal_contract}, "
            f"tx_id: {tx_id}, amount: {amount})"
        )

        # Find the proposal in the database
        proposal = self._find_proposal(proposal_contract, proposal_identifier)
        if not proposal:
            self.logger.warning(
                f"No proposal found for identifier {proposal_identifier} in contract {proposal_contract}"
            )
            return

        # Check if veto already exists
        existing_vetos = backend.list_vetos(
            filters=VetoFilter(
                proposal_id=proposal.id,
                address=vetoer_address,
                tx_id=tx_id,
            )
        )

        if existing_vetos:
            self.logger.info(
                f"Veto already exists for proposal {proposal.id} by {vetoer_address}"
            )
            return

        # Try to determine the DAO ID from the proposal
        dao_id = proposal.dao_id

        # Check if the vetoer address is an agent account contract and find the corresponding agent
        agent_id = None
        if "aibtc-acct-" in vetoer_address:
            # This appears to be an agent account contract address
            # Try to find the agent by account_contract
            try:
                agents = backend.list_agents(
                    filters=AgentFilter(account_contract=vetoer_address)
                )
                if agents:
                    agent_id = agents[0].id
                    self.logger.info(
                        f"Found agent {agent_id} for account contract {vetoer_address}"
                    )
                else:
                    self.logger.warning(
                        f"No agent found for account contract {vetoer_address}"
                    )
            except Exception as e:
                self.logger.error(
                    f"Error finding agent for account contract {vetoer_address}: {str(e)}"
                )

        # Create the veto record
        new_veto = VetoCreate(
            proposal_id=proposal.id,
            address=vetoer_address,
            tx_id=tx_id,
            dao_id=dao_id,
            agent_id=agent_id,
            amount=amount,
            contract_caller=contract_caller,
            tx_sender=tx_sender,
            vetoer_user_id=vetoer_user_id,
            reasoning="Veto captured from blockchain transaction",
        )

        self.logger.info(f"Creating veto with data: {new_veto.model_dump()}")

        try:
            veto = backend.create_veto(new_veto)
            self.logger.info(f"Created new veto record with ID: {veto.id}")
        except Exception as e:
            self.logger.error(f"Failed to create veto record: {str(e)}")
            import traceback

            self.logger.error(f"Full traceback: {traceback.format_exc()}")
