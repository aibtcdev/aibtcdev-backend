"""Handler for capturing STX funding transactions to agent accounts."""

import re
from datetime import datetime
from typing import Dict, List

from app.backend.factory import backend
from app.backend.models import AirdropCreate, AirdropFilter
from app.services.integrations.webhooks.chainhook.handlers.base import (
    ChainhookEventHandler,
)
from app.services.integrations.webhooks.chainhook.models import (
    Event,
    TransactionWithReceipt,
)


class AgentAccountFundingHandler(ChainhookEventHandler):
    """Handler for capturing and processing STX funding transactions to agent accounts.

    This handler identifies contract calls with send-many method on the specific
    SP3FBR2AGK5H9QBDH3EEN6DF8EK8JY7RX8QJ5SVTE.send-many contract,
    parses STX transfer events to extract funding details for agent accounts,
    and creates airdrop records in the database.
    """

    # The specific contract we're monitoring
    TARGET_CONTRACT = "SP3FBR2AGK5H9QBDH3EEN6DF8EK8JY7RX8QJ5SVTE.send-many"

    # Pattern to match agent account addresses
    AGENT_ACCOUNT_PATTERN = re.compile(
        r"\.aibtc-acct-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}$"
    )

    def can_handle_transaction(self, transaction: TransactionWithReceipt) -> bool:
        """Check if this handler can handle the given transaction.

        This handler can handle contract call transactions with send-many method
        on the specific send-many contract that send STX to agent accounts.

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

        # Check if the method name is exactly "send-many"
        tx_method = tx_data_content.get("method", "")
        is_send_many = tx_method == "send-many"

        # Check if this is the specific send-many contract
        contract_identifier = tx_data_content.get("contract_identifier", "")
        is_target_contract = contract_identifier == self.TARGET_CONTRACT

        # Access success from TransactionMetadata
        tx_success = tx_metadata.success

        # Check if there are any STX transfers to agent accounts in the events
        events = tx_metadata.receipt.events if hasattr(tx_metadata, "receipt") else []
        has_agent_account_transfers = self._has_agent_account_stx_transfers(events)

        if (
            is_send_many
            and is_target_contract
            and tx_success
            and has_agent_account_transfers
        ):
            self.logger.debug(
                f"Found send-many STX funding to agent accounts: {tx_method} on contract: {contract_identifier}"
            )

        return (
            tx_kind_type == "ContractCall"
            and is_send_many
            and is_target_contract
            and tx_success is True
            and has_agent_account_transfers
        )

    def _has_agent_account_stx_transfers(self, events: List[Event]) -> bool:
        """Check if there are any STX transfers to agent accounts.

        Args:
            events: List of events from the transaction

        Returns:
            bool: True if there are STX transfers to agent accounts
        """
        for event in events:
            if event.type == "STXTransferEvent" and hasattr(event, "data"):
                recipient = event.data.get("recipient", "")
                if self.AGENT_ACCOUNT_PATTERN.search(recipient):
                    return True
        return False

    def _parse_stx_transfer_events(self, events: List[Event]) -> Dict[str, any]:
        """Parse STX transfer events to extract agent account funding information.

        Args:
            events: List of events from the transaction

        Returns:
            Dict containing parsed funding data
        """
        recipients = []
        total_amount = 0
        sender = None

        for event in events:
            if event.type == "STXTransferEvent" and hasattr(event, "data"):
                event_data = event.data

                # Extract event details
                amount_str = event_data.get("amount", "0")
                recipient = event_data.get("recipient")
                event_sender = event_data.get("sender")

                # Only include recipients that match the agent account pattern
                if recipient and self.AGENT_ACCOUNT_PATTERN.search(recipient):
                    recipients.append(recipient)
                    try:
                        total_amount += int(amount_str)
                    except (ValueError, TypeError):
                        self.logger.warning(
                            f"Invalid amount in STX transfer: {amount_str}"
                        )

                # Set sender from first event
                if sender is None:
                    sender = event_sender

        return {
            "recipients": recipients,
            "total_amount": str(total_amount),
            "token_identifier": "STX",  # STX transfers
            "sender": sender,
        }

    async def handle_transaction(self, transaction: TransactionWithReceipt) -> None:
        """Handle agent account STX funding transactions.

        Processes send-many contract call transactions that send STX to agent accounts
        and creates airdrop records in the database.

        Args:
            transaction: The transaction to handle
        """
        tx_data = self.extract_transaction_data(transaction)
        tx_id = tx_data["tx_id"]
        tx_data_content = tx_data["tx_data"]
        tx_metadata = tx_data["tx_metadata"]

        # Get block metadata
        if not self.chainhook_data or not self.chainhook_data.apply:
            self.logger.warning("No chainhook data available for block information")
            return

        # Use the first apply block (should only be one for this transaction)
        block = self.chainhook_data.apply[0]
        block_height = block.block_identifier.index

        # Convert block timestamp to datetime
        block_timestamp = block.timestamp
        timestamp = datetime.fromtimestamp(block_timestamp)

        # Extract contract identifier
        contract_identifier = tx_data_content.get("contract_identifier", "")

        # Get the events from the transaction
        events = tx_metadata.receipt.events if hasattr(tx_metadata, "receipt") else []

        # Parse STX transfer events to get funding details
        funding_data = self._parse_stx_transfer_events(events)

        if not funding_data["recipients"]:
            self.logger.warning(
                f"No agent account recipients found in STX funding transaction {tx_id}"
            )
            return

        sender = funding_data["sender"]

        self.logger.info(
            f"Processing agent account STX funding transaction {tx_id}: "
            f"{funding_data['total_amount']} STX to {len(funding_data['recipients'])} agent accounts"
        )

        # Check if airdrop already exists
        existing_airdrops = backend.list_airdrops(filters=AirdropFilter(tx_hash=tx_id))

        if existing_airdrops:
            self.logger.info(
                f"STX funding record already exists for transaction {tx_id}"
            )
            return

        # Create the airdrop record
        try:
            airdrop = backend.create_airdrop(
                AirdropCreate(
                    tx_hash=tx_id,
                    block_height=block_height,
                    timestamp=timestamp,
                    sender=sender,
                    contract_identifier=contract_identifier,
                    token_identifier="STX",
                    success=True,
                    total_amount_airdropped=funding_data["total_amount"],
                    recipients=funding_data["recipients"],
                    proposal_tx_id=None,  # Agent account funding, not proposal-related
                )
            )

            self.logger.info(
                f"Created agent account STX funding record {airdrop.id} for transaction {tx_id}: "
                f"{funding_data['total_amount']} STX sent to {len(funding_data['recipients'])} agent accounts"
            )

        except Exception as e:
            self.logger.error(
                f"Error creating agent account funding record for transaction {tx_id}: {str(e)}"
            )
            raise
