"""Handler for capturing FT airdrop transactions (send-many operations)."""

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


class AirdropFTHandler(ChainhookEventHandler):
    """Handler for capturing and processing FT airdrop transactions.

    This handler identifies contract calls with send-many method on faktory contracts,
    parses the FT transfer events to extract airdrop details, and creates airdrop records
    in the database.
    """

    def can_handle_transaction(self, transaction: TransactionWithReceipt) -> bool:
        """Check if this handler can handle the given transaction.

        This handler can handle contract call transactions with send-many method
        on faktory contracts.

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

        # Check if this is a faktory contract (typically has "faktory" in the name)
        contract_identifier = tx_data_content.get("contract_identifier", "")
        is_faktory_contract = "faktory" in contract_identifier.lower()

        # Access success from TransactionMetadata
        tx_success = tx_metadata.success

        if is_send_many and is_faktory_contract and tx_success:
            self.logger.debug(
                f"Found send-many airdrop method: {tx_method} on faktory contract: {contract_identifier}"
            )

        return (
            tx_kind_type == "ContractCall"
            and is_send_many
            and is_faktory_contract
            and tx_success is True
        )

    def _parse_ft_transfer_events(self, events: List[Event]) -> Dict[str, any]:
        """Parse FT transfer events to extract airdrop information.

        Args:
            events: List of events from the transaction

        Returns:
            Dict containing parsed airdrop data
        """
        recipients = []
        total_amount = 0
        token_identifier = None
        sender = None

        for event in events:
            if event.type == "FTTransferEvent" and hasattr(event, "data"):
                event_data = event.data

                # Extract event details
                amount_str = event_data.get("amount", "0")
                recipient = event_data.get("recipient")
                event_sender = event_data.get("sender")
                asset_identifier = event_data.get("asset_identifier")

                if recipient and amount_str:
                    recipients.append(recipient)
                    try:
                        total_amount += int(amount_str)
                    except (ValueError, TypeError):
                        self.logger.warning(
                            f"Invalid amount in FT transfer: {amount_str}"
                        )

                # Set token identifier and sender from first event
                if token_identifier is None:
                    token_identifier = asset_identifier
                if sender is None:
                    sender = event_sender

        return {
            "recipients": recipients,
            "total_amount": str(total_amount),
            "token_identifier": token_identifier,
            "sender": sender,
        }

    def _extract_contract_and_token_info(self, tx_data_content: Dict) -> Dict[str, str]:
        """Extract contract identifier and derive token identifier.

        Args:
            tx_data_content: Transaction data content

        Returns:
            Dict containing contract and token identifiers
        """
        contract_identifier = tx_data_content.get("contract_identifier", "")

        # For faktory contracts, the token identifier typically follows the pattern:
        # {contract_identifier}::{token_name}
        # Extract the token name from the contract (e.g., "fast12-faktory" -> "fast12")
        token_name = ""
        if contract_identifier:
            # Extract the contract name part after the dot
            contract_parts = contract_identifier.split(".")
            if len(contract_parts) > 1:
                contract_name = contract_parts[1]
                # Remove "-faktory" suffix if present to get token name
                if contract_name.endswith("-faktory"):
                    token_name = contract_name[:-8]  # Remove "-faktory"
                else:
                    token_name = contract_name

        token_identifier = f"{contract_identifier}::{token_name}" if token_name else ""

        return {
            "contract_identifier": contract_identifier,
            "token_identifier": token_identifier,
        }

    async def handle_transaction(self, transaction: TransactionWithReceipt) -> None:
        """Handle airdrop transactions.

        Processes send-many contract call transactions and creates airdrop records
        in the database.

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

        # Extract contract and token information
        contract_info = self._extract_contract_and_token_info(tx_data_content)
        contract_identifier = contract_info["contract_identifier"]

        # Get the events from the transaction
        events = tx_metadata.receipt.events if hasattr(tx_metadata, "receipt") else []

        # Parse FT transfer events to get airdrop details
        airdrop_data = self._parse_ft_transfer_events(events)

        if not airdrop_data["recipients"]:
            self.logger.warning(f"No recipients found in airdrop transaction {tx_id}")
            return

        # Use token identifier from events if available, otherwise use derived one
        token_identifier = (
            airdrop_data["token_identifier"] or contract_info["token_identifier"]
        )
        sender = airdrop_data["sender"]

        self.logger.info(
            f"Processing airdrop transaction {tx_id}: "
            f"{airdrop_data['total_amount']} tokens to {len(airdrop_data['recipients'])} recipients"
        )

        # Check if airdrop already exists
        existing_airdrops = backend.list_airdrops(filters=AirdropFilter(tx_hash=tx_id))

        if existing_airdrops:
            self.logger.info(f"Airdrop already exists for transaction {tx_id}")
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
                    token_identifier=token_identifier,
                    success=True,
                    total_amount_airdropped=airdrop_data["total_amount"],
                    recipients=airdrop_data["recipients"],
                    proposal_tx_id=None,  # Will be updated later if used for proposal boosting
                )
            )

            self.logger.info(
                f"Created airdrop record {airdrop.id} for transaction {tx_id}: "
                f"{airdrop_data['total_amount']} tokens airdropped to {len(airdrop_data['recipients'])} recipients"
            )

        except Exception as e:
            self.logger.error(
                f"Error creating airdrop record for transaction {tx_id}: {str(e)}"
            )
            raise
