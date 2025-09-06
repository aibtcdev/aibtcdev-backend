"""Handler for capturing STX transfer events and transaction fees."""

from datetime import datetime

from app.backend.factory import backend
from app.backend.models import (
    WalletBase,
    WalletFilter,
)
from app.lib.logger import configure_logger
from app.services.integrations.webhooks.chainhook.handlers.base import (
    ChainhookEventHandler,
)
from app.services.integrations.webhooks.chainhook.models import TransactionWithReceipt


class STXEventHandler(ChainhookEventHandler):
    """Handler for capturing and tracking STX balance changes in agent wallets.

    This handler identifies:
    1. STXTransferEvent operations where our wallets are senders or recipients
    2. Transaction fees paid by our wallets
    3. Any operation that affects STX balances in our agent wallets

    STX amounts are tracked in micro-STX (1 STX = 1,000,000 micro-STX).
    """

    def __init__(self):
        """Initialize the handler with a logger."""
        super().__init__()
        self.logger = configure_logger(self.__class__.__name__)

    def can_handle_transaction(self, transaction: TransactionWithReceipt) -> bool:
        """Check if this handler can handle the given transaction.

        This handler can handle any transaction that:
        1. Has STXTransferEvent operations involving our wallets
        2. Has transaction fees paid by our wallets
        3. Contains STX operations with our wallet addresses

        Args:
            transaction: The transaction to check

        Returns:
            bool: True if this handler can handle the transaction, False otherwise
        """
        tx_data = self.extract_transaction_data(transaction)
        tx_metadata = tx_data["tx_metadata"]

        # Check if transaction sender is one of our wallets (for fee tracking)
        sender = tx_metadata.sender
        if self._is_our_wallet_address(sender):
            self.logger.debug(f"Found transaction from our wallet: {sender}")
            return True

        # Check if any operations involve our wallets
        operations = transaction.operations
        if not operations:
            return False

        for operation in operations:
            # Convert operation to dict if it's not already
            if hasattr(operation, "__dict__"):
                op_dict = operation.__dict__
            else:
                op_dict = operation

            # Check if this is an STX operation
            if not self._is_stx_operation(op_dict):
                continue

            # Check if the operation involves our wallet
            account_info = op_dict.get("account", {})
            account_address = account_info.get("address") if account_info else None

            if account_address and self._is_our_wallet_address(account_address):
                self.logger.debug(
                    f"Found STX operation involving our wallet: {account_address}"
                )
                return True

        return False

    def _is_stx_operation(self, operation_dict: dict) -> bool:
        """Check if the operation is an STX-related operation."""
        # Check if operation type suggests STX movement
        operation_type = operation_dict.get("type", "").upper()
        if operation_type not in ["CREDIT", "DEBIT"]:
            return False

        # Check if the currency is STX
        amount_info = operation_dict.get("amount", {})
        currency_info = amount_info.get("currency", {}) if amount_info else {}
        currency_symbol = currency_info.get("symbol", "") if currency_info else ""

        return currency_symbol == "STX"

    def _is_our_wallet_address(self, address: str) -> bool:
        """Check if the given address belongs to one of our wallets."""
        if not address:
            return False

        # Check mainnet addresses
        wallets = backend.list_wallets(WalletFilter(mainnet_address=address))
        if wallets:
            return True

        # Check testnet addresses
        wallets = backend.list_wallets(WalletFilter(testnet_address=address))
        return bool(wallets)

    def _get_wallet_by_address(self, address: str):
        """Get wallet by address (mainnet or testnet)."""
        if not address:
            return None

        # Check mainnet addresses first
        wallets = backend.list_wallets(WalletFilter(mainnet_address=address))
        if wallets:
            return wallets[0]

        # Check testnet addresses
        wallets = backend.list_wallets(WalletFilter(testnet_address=address))
        if wallets:
            return wallets[0]

        return None

    async def handle_transaction(self, transaction: TransactionWithReceipt) -> None:
        """Handle STX transfer transactions and fee payments involving our wallets."""
        tx_data = self.extract_transaction_data(transaction)
        tx_id = tx_data["tx_id"]
        tx_metadata = tx_data["tx_metadata"]

        # Handle transaction fees paid by our wallets
        sender = tx_metadata.sender
        transaction_fee = tx_metadata.fee

        if self._is_our_wallet_address(sender) and transaction_fee > 0:
            await self._handle_transaction_fee(sender, transaction_fee, tx_id)

        # Handle STX transfer operations
        operations = transaction.operations
        if operations:
            for operation in operations:
                await self._process_stx_operation(operation, tx_id)

    async def _handle_transaction_fee(
        self, sender_address: str, fee_amount: int, tx_id: str
    ) -> None:
        """Handle transaction fees paid by our wallets."""
        wallet = self._get_wallet_by_address(sender_address)
        if not wallet:
            return

        self.logger.info(
            f"Processing transaction fee: {fee_amount} micro-STX paid by wallet {wallet.id} "
            f"({sender_address}) in transaction {tx_id}"
        )

        # Deduct fee from wallet balance
        await self._update_wallet_balance(wallet, -fee_amount, "transaction_fee", tx_id)

    async def _process_stx_operation(self, operation, tx_id: str) -> None:
        """Process a single STX operation."""
        # Convert operation to dict if it's not already
        if hasattr(operation, "__dict__"):
            op_dict = operation.__dict__
        else:
            op_dict = operation

        # Check if this is an STX operation
        if not self._is_stx_operation(op_dict):
            return

        # Extract operation details
        account_info = op_dict.get("account", {})
        account_address = account_info.get("address") if account_info else None

        if not account_address or not self._is_our_wallet_address(account_address):
            return

        amount_info = op_dict.get("amount", {})
        amount_value = amount_info.get("value", 0) if amount_info else 0
        operation_type = op_dict.get("type", "").upper()
        operation_status = op_dict.get("status", "").upper()

        # Only process successful operations
        if operation_status != "SUCCESS":
            self.logger.debug(f"Skipping non-successful operation: {operation_status}")
            return

        wallet = self._get_wallet_by_address(account_address)
        if not wallet:
            return

        self.logger.info(
            f"Processing STX operation: {operation_type} {amount_value} micro-STX "
            f"for wallet {wallet.id} ({account_address}) in transaction {tx_id}"
        )

        # Calculate balance change based on operation type
        balance_change = 0
        operation_description = ""

        if operation_type == "CREDIT":
            balance_change = amount_value
            operation_description = "stx_transfer_received"
        elif operation_type == "DEBIT":
            balance_change = -amount_value
            operation_description = "stx_transfer_sent"

        if balance_change != 0:
            await self._update_wallet_balance(
                wallet, balance_change, operation_description, tx_id
            )

    async def _update_wallet_balance(
        self, wallet, balance_change: int, operation_type: str, tx_id: str
    ) -> None:
        """Update the STX balance for a wallet."""
        # Get current balance (default to 0 if None)
        current_balance_str = wallet.stx_balance or "0"
        current_balance = int(current_balance_str)

        # Calculate new balance
        new_balance = current_balance + balance_change

        # Ensure balance doesn't go negative (shouldn't happen in practice, but safety check)
        if new_balance < 0:
            self.logger.warning(
                f"Wallet {wallet.id} balance would go negative: {current_balance} + {balance_change} = {new_balance}. "
                f"Setting to 0. Transaction: {tx_id}"
            )
            new_balance = 0

        # Update only the balance fields
        update_data = WalletBase(
            stx_balance=str(new_balance),
            balance_updated_at=datetime.now(),
        )

        backend.update_wallet(wallet.id, update_data)

        self.logger.info(
            f"Updated STX balance for wallet {wallet.id}: "
            f"{current_balance} -> {new_balance} micro-STX "
            f"(change: {balance_change:+d}, operation: {operation_type}, tx: {tx_id})"
        )

        # Convert to STX for logging (1 STX = 1,000,000 micro-STX)
        current_stx = current_balance / 1_000_000
        new_stx = new_balance / 1_000_000
        change_stx = balance_change / 1_000_000

        self.logger.info(
            f"STX balance in human-readable format: "
            f"{current_stx:.6f} -> {new_stx:.6f} STX "
            f"(change: {change_stx:+.6f} STX)"
        )
