"""Handler for capturing buy function events from contracts."""

from app.backend.factory import backend
from app.backend.models import (
    AgentFilter,
    ContractStatus,
    ExtensionFilter,
    HolderBase,
    HolderCreate,
    HolderFilter,
    QueueMessageCreate,
    QueueMessageType,
    TokenFilter,
    WalletFilter,
)
from app.lib.logger import configure_logger
from app.services.integrations.webhooks.chainhook.handlers.base import (
    ChainhookEventHandler,
)
from app.services.integrations.webhooks.chainhook.models import TransactionWithReceipt


class BuyEventHandler(ChainhookEventHandler):
    """Handler for capturing and logging events from contract buy function calls and token distributions.

    This handler identifies:
    1. Contract calls with "buy" function name where our wallets purchase tokens
    2. Contract calls with "send-many" or similar distribution functions where tokens are sent to our agent accounts
    3. Any transaction that results in FTTransferEvent events to our wallets or agent accounts
    """

    def __init__(self):
        """Initialize the handler with a logger."""
        super().__init__()
        self.logger = configure_logger(self.__class__.__name__)

    def can_handle_transaction(self, transaction: TransactionWithReceipt) -> bool:
        """Check if this handler can handle the given transaction.

        This handler can handle contract call transactions with:
        - "buy" function name (our wallets purchasing tokens)
        - "send-many" function name (airdrops/distributions to our accounts)
        - Any transaction that has FTTransferEvent events involving our accounts

        Args:
            transaction: The transaction to check

        Returns:
            bool: True if this handler can handle the transaction, False otherwise
        """
        tx_data = self.extract_transaction_data(transaction)
        tx_kind = tx_data["tx_kind"]
        tx_data_content = tx_data["tx_data"]

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

        tx_method = tx_data_content.get("method")

        # Check if the method is one we're interested in
        interesting_methods = ["buy", "send-many", "transfer", "mint", "airdrop"]
        is_interesting_method = tx_method and any(
            method.lower() in tx_method.lower() for method in interesting_methods
        )

        if is_interesting_method:
            self.logger.debug(f"Found interesting method: {tx_method}")

        # Also check if transaction has FT transfer events involving our accounts
        tx_metadata = tx_data["tx_metadata"]
        has_relevant_ft_events = self._has_relevant_ft_transfer_events(tx_metadata)

        if has_relevant_ft_events:
            self.logger.debug("Found FT transfer events involving our accounts")

        return tx_kind_type == "ContractCall" and (
            is_interesting_method or has_relevant_ft_events
        )

    def _has_relevant_ft_transfer_events(self, tx_metadata) -> bool:
        """Check if the transaction has FT transfer events involving our wallets or agent accounts."""
        if not (
            hasattr(tx_metadata, "receipt") and hasattr(tx_metadata.receipt, "events")
        ):
            return False

        events = tx_metadata.receipt.events
        ft_transfer_events = [
            event for event in events if event.type == "FTTransferEvent"
        ]

        if not ft_transfer_events:
            return False

        # Check if any FT transfer events involve our accounts
        for event in ft_transfer_events:
            event_data = event.data
            sender = event_data.get("sender")
            recipient = event_data.get("recipient")

            # Check if sender or recipient is one of our wallets
            if self._is_our_wallet_address(sender) or self._is_our_wallet_address(
                recipient
            ):
                return True

            # Check if recipient is one of our agent account contracts
            if self._is_our_agent_account(recipient):
                return True

        return False

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

    def _is_our_agent_account(self, address: str) -> bool:
        """Check if the given address is one of our agent account contracts."""
        if not address:
            return False

        agents = backend.list_agents(AgentFilter(account_contract=address))
        return bool(agents)

    async def handle_transaction(self, transaction: TransactionWithReceipt) -> None:
        """Handle token transfer transactions involving our wallets or agent accounts."""
        tx_data = self.extract_transaction_data(transaction)
        tx_id = tx_data["tx_id"]
        tx_data_content = tx_data["tx_data"]
        tx_metadata = tx_data["tx_metadata"]

        # Access sender directly from TransactionMetadata
        sender = tx_metadata.sender
        contract_identifier = tx_data_content.get("contract_identifier", "unknown")
        method = tx_data_content.get("method", "unknown")

        self.logger.info(
            f"Processing token transfer transaction: method={method}, "
            f"sender={sender}, contract={contract_identifier}, tx_id={tx_id}"
        )

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
                    await self._process_ft_transfer_event(event, method, tx_id)
            else:
                self.logger.info(
                    f"No FTTransferEvent events found in transaction {tx_id}"
                )
        else:
            self.logger.warning(f"No events found in transaction {tx_id}")

    async def _process_ft_transfer_event(self, event, method: str, tx_id: str) -> None:
        """Process a single FT transfer event."""
        event_data = event.data
        token_asset = event_data.get("asset_identifier").split("::")[0]
        amount = event_data.get("amount")
        sender = event_data.get("sender")
        recipient = event_data.get("recipient")

        self.logger.info(
            f"Processing FT transfer: {amount} tokens from {sender} to {recipient}, "
            f"asset: {token_asset}"
        )

        # Find the token in our database
        tokens = backend.list_tokens(TokenFilter(contract_principal=token_asset))
        if not tokens:
            self.logger.warning(f"Unknown token asset: {token_asset}")
            return

        token = tokens[0]
        dao_id = token.dao_id

        # Check if this is a transfer TO one of our agent accounts
        recipient_agent = None
        if self._is_our_agent_account(recipient):
            agents = backend.list_agents(AgentFilter(account_contract=recipient))
            if agents:
                recipient_agent = agents[0]
                self.logger.info(f"Token transfer TO our agent account: {recipient}")
                await self._handle_agent_account_receipt(
                    recipient_agent, token, amount, method, dao_id
                )

        # Check if this is a transfer FROM one of our wallets (existing buy logic)
        elif self._is_our_wallet_address(sender) and sender == recipient:
            # This is the existing buy scenario where our wallet buys tokens
            wallets = backend.list_wallets(WalletFilter(mainnet_address=sender))
            if not wallets:
                wallets = backend.list_wallets(WalletFilter(testnet_address=sender))

            if wallets:
                wallet = wallets[0]
                self.logger.info(f"Token purchase by our wallet: {sender}")
                await self._handle_wallet_purchase(wallet, token, amount, dao_id)

    async def _handle_agent_account_receipt(
        self, agent, token, amount: str, method: str, dao_id
    ) -> None:
        """Handle tokens received by one of our agent accounts."""
        self.logger.info(
            f"Agent {agent.account_contract} received {amount} tokens of {token.contract_principal}"
        )

        # Check if we already have a holder record for this agent+token
        existing_records = backend.list_holders(
            HolderFilter(
                agent_id=agent.id,
                token_id=token.id,
                dao_id=dao_id,
            )
        )

        should_trigger_approval = False

        if existing_records:
            # Update existing record - increase the amount
            record = existing_records[0]
            current_amount = float(record.amount)
            received_amount = float(amount)
            new_amount = current_amount + received_amount
            new_amount_str = str(new_amount)

            # Create a HolderBase instance for the update
            update_data = HolderBase(
                agent_id=record.agent_id,
                token_id=record.token_id,
                dao_id=record.dao_id,
                amount=new_amount_str,
            )

            backend.update_holder(record.id, update_data)
            self.logger.info(
                f"Updated token balance for agent {agent.id}: "
                f"token {token.id} (DAO {dao_id}), new amount: {new_amount_str}"
            )

            # Check if this was a first meaningful receipt (balance was 0)
            if current_amount == 0 and received_amount > 0:
                should_trigger_approval = True
                self.logger.info(
                    f"First meaningful token receipt detected for agent {agent.id} - will trigger proposal approval"
                )
        else:
            # Create new record
            new_record = HolderCreate(
                agent_id=agent.id,
                token_id=token.id,
                dao_id=dao_id,
                amount=str(amount),
                address=agent.account_contract,
            )
            backend.create_holder(new_record)
            self.logger.info(
                f"Created new token balance record for agent {agent.id}: "
                f"token {token.id} (DAO {dao_id}), amount: {amount}"
            )

            # First token receipt should trigger approval
            should_trigger_approval = True
            self.logger.info(
                f"First token receipt detected for agent {agent.id} - will trigger proposal approval"
            )

        # Queue proposal approval if this is a first-time receipt
        if should_trigger_approval:
            await self._queue_proposal_approval_for_agent(agent, dao_id, token)

    async def _handle_wallet_purchase(self, wallet, token, amount: str, dao_id) -> None:
        """Handle tokens purchased by one of our wallets (existing logic)."""
        # Check if we already have a record for this wallet+token
        existing_records = backend.list_holders(
            HolderFilter(
                wallet_id=wallet.id,
                token_id=token.id,
                dao_id=dao_id,
            )
        )

        should_trigger_approval = False

        if existing_records:
            # Update existing record - increase the amount
            record = existing_records[0]
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

            # Check if this was a first meaningful purchase (balance was 0)
            if current_amount == 0 and bought_amount > 0:
                should_trigger_approval = True
                self.logger.info(
                    f"First meaningful token purchase detected for wallet {wallet.id} - will trigger proposal approval"
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

            # First token purchase should trigger approval
            should_trigger_approval = True
            self.logger.info(
                f"First token purchase detected for wallet {wallet.id} - will trigger proposal approval"
            )

        # Queue proposal approval if this is a first-time purchase
        if should_trigger_approval:
            await self._queue_proposal_approval_for_wallet(wallet, dao_id, token)

    async def _queue_proposal_approval_for_agent(self, agent, dao_id, token) -> None:
        """Queue a proposal approval message for the agent account."""
        try:
            # Find the DAO's ACTION_PROPOSAL_VOTING extension
            extensions = backend.list_extensions(
                ExtensionFilter(
                    dao_id=dao_id,
                    subtype="ACTION_PROPOSAL_VOTING",
                    status=ContractStatus.DEPLOYED,
                )
            )

            if not extensions:
                self.logger.warning(
                    f"No ACTION_PROPOSAL_VOTING extension found for DAO {dao_id}"
                )
                return

            voting_extension = extensions[0]

            # Get the wallet associated with this agent
            wallets = backend.list_wallets(WalletFilter(agent_id=agent.id))
            if not wallets:
                self.logger.warning(
                    f"No wallet found for agent {agent.id} - cannot queue approval"
                )
                return

            wallet = wallets[0]

            # Create queue message for proposal approval
            approval_message = QueueMessageCreate(
                type=QueueMessageType.get_or_create("agent_account_proposal_approval"),
                dao_id=dao_id,
                wallet_id=wallet.id,  # Include the wallet_id
                message={
                    "agent_account_contract": agent.account_contract,
                    "contract_to_approve": voting_extension.contract_principal,
                    "approval_type": "VOTING",
                    "token_contract": token.contract_principal,
                    "reason": "First token receipt - enabling proposal voting",
                },
            )

            backend.create_queue_message(approval_message)
            self.logger.info(
                f"Queued proposal approval for agent {agent.account_contract} "
                f"to approve {voting_extension.contract_principal} using wallet {wallet.id}"
            )

        except Exception as e:
            self.logger.error(
                f"Failed to queue proposal approval for agent {agent.id}: {str(e)}",
                exc_info=True,
            )

    async def _queue_proposal_approval_for_wallet(self, wallet, dao_id, token) -> None:
        """Queue a proposal approval message for the agent account associated with the wallet."""
        try:
            # Find the DAO's ACTION_PROPOSAL_VOTING extension
            extensions = backend.list_extensions(
                ExtensionFilter(
                    dao_id=dao_id,
                    subtype="ACTION_PROPOSAL_VOTING",
                    status=ContractStatus.DEPLOYED,
                )
            )

            if not extensions:
                self.logger.warning(
                    f"No ACTION_PROPOSAL_VOTING extension found for DAO {dao_id}"
                )
                return

            voting_extension = extensions[0]

            # Get the agent account contract from the wallet
            if not wallet.agent_id:
                self.logger.warning(f"No agent associated with wallet {wallet.id}")
                return

            agent = backend.get_agent(wallet.agent_id)
            if not agent or not agent.account_contract:
                self.logger.warning(
                    f"No agent account contract found for agent {wallet.agent_id}"
                )
                return

            # Create queue message for proposal approval
            approval_message = QueueMessageCreate(
                type=QueueMessageType.get_or_create("agent_account_proposal_approval"),
                wallet_id=wallet.id,
                dao_id=dao_id,
                message={
                    "agent_account_contract": agent.account_contract,
                    "contract_to_approve": voting_extension.contract_principal,
                    "approval_type": "VOTING",
                    "token_contract": token.contract_principal,
                    "reason": "First token purchase - enabling proposal voting",
                },
            )

            backend.create_queue_message(approval_message)
            self.logger.info(
                f"Queued proposal approval for agent {agent.account_contract} "
                f"to approve {voting_extension.contract_principal}"
            )

        except Exception as e:
            self.logger.error(
                f"Failed to queue proposal approval for wallet {wallet.id}: {str(e)}",
                exc_info=True,
            )
