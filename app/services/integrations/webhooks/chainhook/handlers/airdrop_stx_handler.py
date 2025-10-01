"""Handler for capturing STX airdrop transactions."""

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


class AirdropSTXHandler(ChainhookEventHandler):
    """Handler for capturing and processing STX airdrop transactions.

    This handler identifies contract calls with send-many method on the specific
    SP3FBR2AGK5H9QBDH3EEN6DF8EK8JY7RX8QJ5SVTE.send-many contract,
    parses STX transfer events to extract airdrop details for agent accounts,
    validates basic requirements (minimum STX amount and recipient count),
    validates recipients against the wallets table, and creates airdrop records.

    Advanced validations (expiry and cooldown) are handled at the API level
    during proposal creation to enforce business rules only when airdrops are
    actually used in proposals.
    """

    # The specific contract we're monitoring
    TARGET_CONTRACT = "SP3FBR2AGK5H9QBDH3EEN6DF8EK8JY7RX8QJ5SVTE.send-many"

    # Business rule constants for basic transaction validation
    MIN_AMOUNT_PER_RECIPIENT = (
        100_000  # 0.1 STX in microSTX (1 STX = 1,000,000 microSTX)
    )
    MIN_RECIPIENTS = 5
    # Note: Expiry and cooldown validations are now handled at API level during proposal creation

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

        tx_hash = transaction.transaction_identifier.hash

        # Only handle ContractCall type transactions
        if not isinstance(tx_kind, dict):
            return False

        tx_kind_type = tx_kind.get("type")

        if not isinstance(tx_data_content, dict):
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

        final_result = (
            tx_kind_type == "ContractCall"
            and is_send_many
            and is_target_contract
            and tx_success is True
            and has_agent_account_transfers
        )

        if final_result:
            self.logger.info(
                "Transaction claimed for STX airdrop processing",
                extra={
                    "tx_hash": tx_hash,
                    "contract_identifier": contract_identifier,
                    "method": tx_method,
                    "event_type": "transaction_claimed",
                },
            )
        else:
            self.logger.debug(
                "Transaction rejected - criteria not met",
                extra={
                    "tx_hash": tx_hash,
                    "is_contract_call": tx_kind_type == "ContractCall",
                    "is_send_many": is_send_many,
                    "is_target_contract": is_target_contract,
                    "tx_success": tx_success,
                    "has_transfers": has_agent_account_transfers,
                    "event_type": "transaction_rejected",
                },
            )

        return final_result

    def _has_agent_account_stx_transfers(self, events: List[Event]) -> bool:
        """Check if there are any STX transfers.

        Args:
            events: List of events from the transaction

        Returns:
            bool: True if there are STX transfers (recipient validation happens later)
        """
        for event in events:
            if event.type == "STXTransferEvent" and hasattr(event, "data"):
                recipient = event.data.get("recipient", "")
                if recipient:  # Any valid recipient address
                    return True
        return False

    def _parse_stx_transfer_events(self, events: List[Event]) -> Dict[str, any]:
        """Parse STX transfer events to extract STX airdrop information.

        Args:
            events: List of events from the transaction

        Returns:
            Dict containing parsed airdrop data with individual recipient amounts
        """
        recipients = []
        recipient_amounts = {}  # Track individual amounts per recipient
        total_amount = 0
        sender = None

        for event in events:
            if event.type == "STXTransferEvent" and hasattr(event, "data"):
                event_data = event.data

                # Extract event details
                amount_str = event_data.get("amount", "0")
                recipient = event_data.get("recipient")
                event_sender = event_data.get("sender")

                # Include all recipients (validation against wallets table happens later)
                if recipient:
                    recipients.append(recipient)
                    try:
                        amount = int(amount_str)
                        total_amount += amount
                        # Track individual recipient amounts (handle multiple transfers to same recipient)
                        if recipient in recipient_amounts:
                            recipient_amounts[recipient] += amount
                        else:
                            recipient_amounts[recipient] = amount
                    except (ValueError, TypeError):
                        self.logger.warning(
                            "Invalid amount in STX transfer event",
                            extra={
                                "amount_str": amount_str,
                                "recipient": recipient,
                                "event_type": "invalid_amount",
                            },
                        )

                # Set sender from first event
                if sender is None:
                    sender = event_sender

        return {
            "recipients": recipients,
            "recipient_amounts": recipient_amounts,
            "total_amount": str(total_amount),
            "token_identifier": "STX",  # STX transfers
            "sender": sender,
        }

    async def _validate_recipients_against_wallets(
        self, recipients: List[str]
    ) -> Dict[str, bool]:
        """Validate recipients against the wallets table.

        Args:
            recipients: List of recipient addresses to validate

        Returns:
            Dict mapping each recipient to whether it exists in wallets table
        """
        from app.lib.utils import validate_wallet_recipients

        return await validate_wallet_recipients(recipients)

    def _validate_minimum_requirements(
        self, recipient_amounts: Dict[str, int], recipient_count: int
    ) -> Dict[str, str]:
        """Validate minimum STX amount per recipient and recipient count.

        Args:
            recipient_amounts: Dict mapping recipient addresses to amounts in microSTX
            recipient_count: Number of recipients

        Returns:
            Dict with validation errors, empty if all validations pass
        """
        errors = {}

        # Check minimum amount per recipient
        insufficient_recipients = []
        for recipient, amount in recipient_amounts.items():
            if amount < self.MIN_AMOUNT_PER_RECIPIENT:
                insufficient_recipients.append(
                    f"{recipient}: {amount / 1_000_000:.6f} STX (min: {self.MIN_AMOUNT_PER_RECIPIENT / 1_000_000:.1f} STX)"
                )

        if insufficient_recipients:
            errors["recipient_amounts"] = (
                f"Recipients with insufficient amounts: {', '.join(insufficient_recipients)}"
            )

        if recipient_count < self.MIN_RECIPIENTS:
            errors["recipient_count"] = (
                f"Recipient count {recipient_count} is below minimum {self.MIN_RECIPIENTS}"
            )

        return errors

    async def handle_transaction(self, transaction: TransactionWithReceipt) -> None:
        """Handle STX airdrop transactions.

        Processes send-many contract call transactions that send STX to agent accounts,
        validates basic requirements (minimum STX/recipients) and recipient registry,
        and creates airdrop records. Advanced validations (expiry, cooldown) are
        handled at API level during proposal creation.

        Args:
            transaction: The transaction to handle
        """
        tx_data = self.extract_transaction_data(transaction)
        tx_id = tx_data["tx_id"]
        tx_data_content = tx_data["tx_data"]
        tx_metadata = tx_data["tx_metadata"]

        # Get block metadata
        if not self.chainhook_data or not self.chainhook_data.apply:
            self.logger.warning(
                "No chainhook data available for block information",
                extra={"tx_id": tx_id, "event_type": "missing_block_data"},
            )
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

        # Parse STX transfer events to get airdrop details
        airdrop_data = self._parse_stx_transfer_events(events)

        if not airdrop_data["recipients"]:
            self.logger.warning(
                "No recipients found in STX airdrop transaction",
                extra={"tx_id": tx_id, "event_type": "no_recipients"},
            )
            return

        recipients = airdrop_data["recipients"]
        recipient_amounts = airdrop_data["recipient_amounts"]
        total_amount = int(airdrop_data["total_amount"])
        sender = airdrop_data["sender"]

        self.logger.info(
            "Processing STX airdrop transaction",
            extra={
                "tx_id": tx_id,
                "total_amount_stx": f"{total_amount / 1_000_000:.6f}",
                "recipient_count": len(recipients),
                "sender": sender,
                "event_type": "airdrop_processing",
            },
        )

        # Check if airdrop already exists
        existing_airdrops = backend.list_airdrops(filters=AirdropFilter(tx_hash=tx_id))

        if existing_airdrops:
            self.logger.info(
                "STX airdrop record already exists - skipping",
                extra={"tx_id": tx_id, "event_type": "airdrop_exists"},
            )
            return

        # Validate recipients against wallets table
        self.logger.debug(
            "Validating recipients against wallets table",
            extra={
                "recipient_count": len(recipients),
                "tx_id": tx_id,
                "event_type": "recipient_validation",
            },
        )
        recipient_validation = await self._validate_recipients_against_wallets(
            recipients
        )

        invalid_recipients = [
            addr for addr, is_valid in recipient_validation.items() if not is_valid
        ]

        if invalid_recipients:
            self.logger.error(
                "Airdrop validation failed - invalid recipients",
                extra={
                    "tx_id": tx_id,
                    "invalid_recipients": invalid_recipients,
                    "invalid_count": len(invalid_recipients),
                    "event_type": "validation_failed",
                },
            )
            # Create failed airdrop record
            try:
                backend.create_airdrop(
                    AirdropCreate(
                        tx_hash=tx_id,
                        block_height=block_height,
                        timestamp=timestamp,
                        sender=sender,
                        contract_identifier=contract_identifier,
                        token_identifier="STX",
                        success=False,
                        total_amount_airdropped=airdrop_data["total_amount"],
                        recipients=recipients,
                        proposal_id=None,
                    )
                )
            except Exception as e:
                self.logger.error(
                    "Failed to create airdrop record for invalid recipients",
                    extra={
                        "tx_id": tx_id,
                        "error": str(e),
                        "event_type": "record_creation_error",
                    },
                    exc_info=True,
                )
            return

        # Validate minimum requirements
        requirement_errors = self._validate_minimum_requirements(
            recipient_amounts, len(recipients)
        )
        if requirement_errors:
            self.logger.error(
                "Airdrop validation failed - minimum requirements not met",
                extra={
                    "tx_id": tx_id,
                    "requirement_errors": requirement_errors,
                    "event_type": "requirements_failed",
                },
            )
            # Create failed airdrop record
            try:
                backend.create_airdrop(
                    AirdropCreate(
                        tx_hash=tx_id,
                        block_height=block_height,
                        timestamp=timestamp,
                        sender=sender,
                        contract_identifier=contract_identifier,
                        token_identifier="STX",
                        success=False,
                        total_amount_airdropped=airdrop_data["total_amount"],
                        recipients=recipients,
                        proposal_id=None,
                    )
                )
            except Exception as e:
                self.logger.error(
                    "Failed to create airdrop record for requirement errors",
                    extra={
                        "tx_id": tx_id,
                        "error": str(e),
                        "event_type": "record_creation_error",
                    },
                    exc_info=True,
                )
            return

        # All basic validations passed - create successful airdrop record
        # Note: Expiry and cooldown validations are now handled at API level during proposal creation
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
                    total_amount_airdropped=airdrop_data["total_amount"],
                    recipients=recipients,
                    proposal_id=None,  # Can be linked to a proposal if needed
                )
            )

            self.logger.info(
                "STX airdrop record created successfully",
                extra={
                    "airdrop_id": str(airdrop.id),
                    "tx_id": tx_id,
                    "total_amount_stx": f"{total_amount / 1_000_000:.6f}",
                    "recipient_count": len(recipients),
                    "sender": sender,
                    "block_height": block_height,
                    "event_type": "airdrop_created",
                },
            )

        except Exception as e:
            self.logger.error(
                "Failed to create STX airdrop record",
                extra={
                    "tx_id": tx_id,
                    "error": str(e),
                    "event_type": "record_creation_error",
                },
                exc_info=True,
            )
            raise
