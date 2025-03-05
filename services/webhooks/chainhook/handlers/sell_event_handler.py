"""Handler for capturing sell function events from contracts."""

from datetime import datetime

from backend.factory import backend
from backend.models import TokenFilter, WalletFilter, WalletTokenBase, WalletTokenFilter
from lib.logger import configure_logger
from services.webhooks.chainhook.handlers.base import ChainhookEventHandler
from services.webhooks.chainhook.models import TransactionWithReceipt


class SellEventHandler(ChainhookEventHandler):
    """Handler for capturing and logging events from contract sell function calls.

    This handler identifies contract calls with the "sell" function name
    and logs only FTTransferEvent events associated with these transactions.
    It updates wallet token balances when tokens are sold.
    """

    def __init__(self):
        """Initialize the handler with a logger."""
        super().__init__()
        self.logger = configure_logger(self.__class__.__name__)

    def can_handle(self, transaction: TransactionWithReceipt) -> bool:
        """Check if this handler can handle the given transaction.

        This handler can handle contract call transactions with the "sell" function name.

        Args:
            transaction: The transaction to check

        Returns:
            bool: True if this handler can handle the transaction, False otherwise
        """
        tx_data = self.extract_transaction_data(transaction)
        tx_kind = tx_data["tx_kind"]
        tx_data_content = tx_data["tx_data"]
        tx_metadata = tx_data["tx_metadata"]

        # Only handle ContractCall type transactions with 'sell' method
        if not isinstance(tx_kind, dict):
            self.logger.debug(f"Skipping: tx_kind is not a dict: {type(tx_kind)}")
            return False

        tx_kind_type = tx_kind.get("type")

        if not isinstance(tx_data_content, dict):
            self.logger.debug(
                f"Skipping: tx_data_content is not a dict: {type(tx_data_content)}"
            )
            return False

        tx_method = tx_data_content.get("method")

        # Check if the method name contains "sell" (case-insensitive)
        is_sell_method = tx_method and "sell" in tx_method.lower()

        if is_sell_method:
            self.logger.debug(f"Found sell method: {tx_method}")

        return tx_kind_type == "ContractCall" and is_sell_method

    async def handle_transaction(self, transaction: TransactionWithReceipt) -> None:
        """Handle sell function call transactions and track token sales by our wallets."""
        tx_data = self.extract_transaction_data(transaction)
        tx_id = tx_data["tx_id"]
        tx_data_content = tx_data["tx_data"]
        tx_metadata = tx_data["tx_metadata"]

        # Access sender directly from TransactionMetadata
        sender = tx_metadata.sender
        contract_identifier = tx_data_content.get("contract_identifier", "unknown")
        args = tx_data_content.get("args", [])

        self.logger.info(
            f"Processing sell function call from {sender} to contract {contract_identifier} "
            f"with args: {args}, tx_id: {tx_id}"
        )

        # Check if the sender is one of our wallets
        wallets = backend.list_wallets(WalletFilter(mainnet_address=sender))
        if not wallets:
            self.logger.info(
                f"Sender {sender} is not one of our wallets. Ignoring event."
            )
            return

        wallet = wallets[0]  # Get the matching wallet

        # Extract token transfer information from FTTransferEvent
        if hasattr(tx_metadata, "receipt") and hasattr(tx_metadata.receipt, "events"):
            events = tx_metadata.receipt.events
            ft_transfer_events = [
                event for event in events if event.type == "FTTransferEvent"
            ]

            if ft_transfer_events:
                self.logger.info(
                    f"Found {len(ft_transfer_events)} FTTransferEvent events in transaction {tx_id}"
                )

                for event in ft_transfer_events:
                    # Extract token info from event data
                    event_data = event.data
                    token_asset = event_data.get("asset_identifier").split("::")[0]
                    amount = event_data.get("amount")
                    sender_address = event_data.get("sender")

                    # Only process if our wallet is the sender (selling tokens)
                    if sender_address != sender:
                        continue

                    # Find the token in our database
                    tokens = backend.list_tokens(
                        TokenFilter(contract_principal=token_asset)
                    )
                    if not tokens:
                        self.logger.warning(f"Unknown token asset: {token_asset}")
                        continue

                    token = tokens[0]
                    dao_id = token.dao_id

                    # Check if we already have a record for this wallet+token
                    existing_records = backend.list_wallet_tokens(
                        WalletTokenFilter(wallet_id=wallet.id, token_id=token.id)
                    )

                    if existing_records:
                        # Update existing record - decrease the amount
                        record = existing_records[0]
                        # Convert string to decimal for subtraction, then back to string
                        current_amount = float(record.amount)
                        sold_amount = float(amount)

                        # Ensure we don't go below zero
                        new_amount = max(0, current_amount - sold_amount)
                        new_amount_str = str(new_amount)

                        # Create a WalletTokenBase instance for the update
                        update_data = WalletTokenBase(
                            wallet_id=record.wallet_id,
                            token_id=record.token_id,
                            dao_id=record.dao_id,
                            amount=new_amount_str,
                            updated_at=datetime.now(),
                        )

                        backend.update_wallet_token(record.id, update_data)
                        self.logger.info(
                            f"Updated token balance after sell for wallet {wallet.id}: "
                            f"token {token.id} (DAO {dao_id}), new amount: {new_amount_str}"
                        )
                    else:
                        self.logger.warning(
                            f"Attempted to sell token {token.id} from wallet {wallet.id} "
                            f"but no existing record found. This may indicate an inconsistency."
                        )
            else:
                self.logger.info(
                    f"No FTTransferEvent events found in transaction {tx_id}"
                )
        else:
            self.logger.warning(f"No events found in transaction {tx_id}")
