"""Handler for capturing buy function events from contracts."""

from backend.factory import backend
from backend.models import (
    HolderBase,
    HolderCreate,
    HolderFilter,
    TokenFilter,
    WalletFilter,
)
from lib.logger import configure_logger
from services.webhooks.chainhook.handlers.base import ChainhookEventHandler
from services.webhooks.chainhook.models import TransactionWithReceipt


class BuyEventHandler(ChainhookEventHandler):
    """Handler for capturing and logging events from contract buy function calls.

    This handler identifies contract calls with the "buy" function name
    and logs only FTTransferEvent events associated with these transactions.
    """

    def __init__(self):
        """Initialize the handler with a logger."""
        super().__init__()
        self.logger = configure_logger(self.__class__.__name__)

    def can_handle_transaction(self, transaction: TransactionWithReceipt) -> bool:
        """Check if this handler can handle the given transaction.

        This handler can handle contract call transactions with the "buy" function name.

        Args:
            transaction: The transaction to check

        Returns:
            bool: True if this handler can handle the transaction, False otherwise
        """
        tx_data = self.extract_transaction_data(transaction)
        tx_kind = tx_data["tx_kind"]
        tx_data_content = tx_data["tx_data"]

        # Only handle ContractCall type transactions with 'buy' method
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

        # Check if the method name contains "buy" (case-insensitive)
        is_buy_method = tx_method and "buy" in tx_method.lower()

        if is_buy_method:
            self.logger.debug(f"Found buy method: {tx_method}")

        return tx_kind_type == "ContractCall" and is_buy_method

    async def handle_transaction(self, transaction: TransactionWithReceipt) -> None:
        """Handle buy function call transactions and track token purchases by our wallets."""
        tx_data = self.extract_transaction_data(transaction)
        tx_id = tx_data["tx_id"]
        tx_data_content = tx_data["tx_data"]
        tx_metadata = tx_data["tx_metadata"]

        # Access sender directly from TransactionMetadata
        sender = tx_metadata.sender
        contract_identifier = tx_data_content.get("contract_identifier", "unknown")
        args = tx_data_content.get("args", [])

        self.logger.info(
            f"Processing buy function call from {sender} to contract {contract_identifier} "
            f"with args: {args}, tx_id: {tx_id}"
        )

        # Check if the sender is one of our wallets
        wallets = backend.list_wallets(WalletFilter(mainnet_address=sender))
        if not wallets:
            # If not found in mainnet addresses, check testnet addresses
            wallets = backend.list_wallets(WalletFilter(testnet_address=sender))
            if not wallets:
                self.logger.info(
                    f"Sender {sender} is not one of our wallets (checked both mainnet and testnet). "
                    f"Ignoring event."
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
                self.logger.info(f"FTTransferEvent events: {ft_transfer_events}")
                for event in ft_transfer_events:
                    # Extract token info from event data
                    event_data = event.data
                    token_asset = event_data.get("asset_identifier").split("::")[0]
                    amount = event_data.get("amount")
                    recipient = event_data.get("recipient")

                    # Only process if our wallet is the recipient
                    if recipient != sender:
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
                    existing_records = backend.list_holders(
                        HolderFilter(
                            wallet_id=wallet.id,
                            token_id=token.id,
                            dao_id=token.dao_id,
                        )
                    )

                    if existing_records:
                        # Update existing record - increase the amount
                        record = existing_records[0]
                        # Convert string to decimal for addition, then back to string
                        current_amount = float(record.amount)
                        bought_amount = float(amount)
                        new_amount = current_amount + bought_amount
                        new_amount_str = str(new_amount)

                        # Create a HolderBase instance for the update
                        update_data = HolderBase(
                            wallet_id=record.wallet_id,
                            token_id=record.token_id,
                            dao_id=record.dao_id,
                            amount=new_amount_str,
                        )

                        backend.update_holder(record.id, update_data)
                        self.logger.info(
                            f"Updated token balance after buy for wallet {wallet.id}: "
                            f"token {token.id} (DAO {dao_id}), new amount: {new_amount_str}"
                        )
                    else:
                        # Create new record
                        new_record = HolderCreate(
                            wallet_id=wallet.id,
                            token_id=token.id,
                            dao_id=dao_id,
                            amount=str(amount),
                        )
                        backend.create_holder(new_record)
                        self.logger.info(
                            f"Created new token balance record for wallet {wallet.id}: "
                            f"token {token.id} (DAO {dao_id}), amount: {amount}"
                        )
            else:
                self.logger.info(
                    f"No FTTransferEvent events found in transaction {tx_id}"
                )
        else:
            self.logger.warning(f"No events found in transaction {tx_id}")
