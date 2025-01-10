from .bun import BunScriptRunner
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Dict, Optional, Type, Union
from uuid import UUID


class WalletGetBalanceInput(BaseModel):
    """Input schema for getting wallet balance information.
    No parameters required as it uses the wallet_id from initialization.
    """

    pass


class WalletGetMyBalance(BaseTool):
    name: str = "wallet_get_my_balance"
    description: str = (
        "Get my wallet balance and amount of tokens including STX, fungible tokens (FT), and "
        "non-fungible tokens (NFTs) associated with my wallet"
    )
    args_schema: Type[BaseModel] = WalletGetBalanceInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = UUID("00000000-0000-0000-0000-000000000000")

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(self, **kwargs) -> Dict[str, Union[str, bool, None]]:
        """Execute the tool to get wallet balance."""
        return BunScriptRunner.bun_run(
            self.wallet_id, "stacks-wallet", "get-my-wallet-balance.ts"
        )

    def _run(self, **kwargs) -> Dict[str, Union[str, bool, None]]:
        """Execute the tool to get wallet balance."""
        return self._deploy(**kwargs)

    async def _arun(self, **kwargs) -> Dict[str, Union[str, bool, None]]:
        """Async version of the tool."""
        return self._deploy(**kwargs)


class WalletGetAddressInput(BaseModel):
    """Input schema for getting wallet address.
    No parameters required as it uses the wallet_id from initialization.
    """

    pass


class WalletGetMyAddress(BaseTool):
    name: str = "wallet_get_my_address"
    description: str = "Get my Stacks STX address"
    args_schema: Type[BaseModel] = WalletGetAddressInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = UUID("00000000-0000-0000-0000-000000000000")

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(self, **kwargs) -> Dict[str, Union[str, bool, None]]:
        """Execute the tool to get wallet address."""
        return BunScriptRunner.bun_run(
            self.wallet_id, "stacks-wallet", "get-my-wallet-address.ts"
        )

    def _run(self, **kwargs) -> Dict[str, Union[str, bool, None]]:
        """Execute the tool to get wallet address."""
        return self._deploy(**kwargs)

    async def _arun(self, **kwargs) -> Dict[str, Union[str, bool, None]]:
        """Async version of the tool."""
        return self._deploy(**kwargs)


class WalletFundMyWalletFaucet(BaseTool):
    name: str = "wallet_fund_my_wallet_faucet"
    description: str = (
        "Fund my wallet with test STX tokens when running on testnet. This "
        "operation only works on the Stacks testnet."
    )
    args_schema: Type[BaseModel] = WalletGetAddressInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = UUID("00000000-0000-0000-0000-000000000000")

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(self, **kwargs) -> Dict[str, Union[str, bool, None]]:
        """Execute the tool to fund wallet on testnet."""
        return BunScriptRunner.bun_run(
            self.wallet_id, "stacks-wallet", "testnet-stx-faucet-me.ts"
        )

    def _run(self, **kwargs) -> Dict[str, Union[str, bool, None]]:
        """Execute the tool to fund wallet on testnet."""
        return self._deploy(**kwargs)

    async def _arun(self, **kwargs) -> Dict[str, Union[str, bool, None]]:
        """Async version of the tool."""
        return self._deploy(**kwargs)


class WalletSendSTXInput(BaseModel):
    """Input schema for sending STX tokens."""

    recipient: str = Field(..., description="Recipient STX address.")
    amount: int = Field(
        ..., description="Amount of STX to send not in microSTX. Default is 1."
    )
    fee: Optional[int] = Field(
        200, description="Transaction fee in microSTX. Default is 200."
    )
    memo: Optional[str] = Field(
        "", description="Optional memo to include with the transaction."
    )


class WalletSendSTX(BaseTool):
    name: str = "wallet_send_stx"
    description: str = (
        "Send STX tokens from your wallet to a recipient address. Specify amount in STX "
        "(not microSTX), optional fee in microSTX (default 200), and optional memo."
    )
    args_schema: Type[BaseModel] = WalletSendSTXInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = UUID("00000000-0000-0000-0000-000000000000")

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        recipient: str,
        amount: int,
        fee: Optional[int] = 200,
        memo: Optional[str] = "",
        **kwargs,
    ) -> Dict[str, Union[str, bool, None]]:
        """Execute the tool to send STX tokens."""
        return BunScriptRunner.bun_run(
            self.wallet_id,
            "stacks-wallet",
            "transfer-my-stx.ts",
            recipient,
            str(amount),
            str(fee),
            memo or "",
        )

    def _run(
        self,
        recipient: str,
        amount: int,
        fee: Optional[int] = 200,
        memo: Optional[str] = "",
        **kwargs,
    ) -> Dict[str, Union[str, bool, None]]:
        """Execute the tool to send STX tokens."""
        return self._deploy(recipient, amount, fee, memo)

    async def _arun(
        self,
        recipient: str,
        amount: int,
        fee: Optional[int] = 200,
        memo: Optional[str] = "",
        **kwargs,
    ) -> Dict[str, Union[str, bool, None]]:
        """Async version of the tool."""
        return self._deploy(recipient, amount, fee, memo)


class WalletGetTransactionsInput(BaseModel):
    """Input schema for getting wallet transactions.
    No parameters required as it uses the wallet_id from initialization.
    """

    pass


class WalletGetMyTransactions(BaseTool):
    name: str = "wallet_get_my_transactions"
    description: str = (
        "Get transaction history for my wallet including STX transfers and contract "
        "calls. Returns a list of transactions with their details."
    )
    args_schema: Type[BaseModel] = WalletGetTransactionsInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = UUID("00000000-0000-0000-0000-000000000000")

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(self, **kwargs) -> Dict[str, Union[str, bool, None]]:
        """Execute the tool to get transaction history."""
        return BunScriptRunner.bun_run(
            self.wallet_id, "stacks-wallet", "get-my-wallet-transactions.ts"
        )

    def _run(self, **kwargs) -> Dict[str, Union[str, bool, None]]:
        """Execute the tool to get transaction history."""
        return self._deploy(**kwargs)

    async def _arun(self, **kwargs) -> Dict[str, Union[str, bool, None]]:
        """Async version of the tool."""
        return self._deploy(**kwargs)


class WalletSIP10SendInput(BaseModel):
    """Input schema for sending SIP-010 compliant fungible tokens."""

    contract_address: str = Field(
        ...,
        description="Contract address of the token. Format: contract_address.contract_name",
    )
    recipient: str = Field(..., description="Recipient address to send tokens to.")
    amount: int = Field(
        ...,
        description="Amount of tokens to send. Needs to be in microunits based on decimals of token.",
    )


class WalletSIP10SendTool(BaseTool):
    name: str = "wallet_send_sip10_token"
    description: str = (
        "Send SIP-010 compliant fungible tokens from your wallet to a recipient address. "
        "Amount must be specified in microunits based on the token's decimals."
    )
    args_schema: Type[BaseModel] = WalletSIP10SendInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = UUID("00000000-0000-0000-0000-000000000000")

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        contract_address: str,
        recipient: str,
        amount: int,
        **kwargs,
    ) -> Dict[str, Union[str, bool, None]]:
        """Execute the tool to send SIP-010 tokens."""
        try:
            return BunScriptRunner.bun_run(
                self.wallet_id,
                "sip-010-ft",
                "transfer.ts",
                contract_address,
                recipient,
                str(amount),
            )
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error during token transfer: {str(e)}",
            }

    def _run(
        self,
        contract_address: str,
        recipient: str,
        amount: int,
        **kwargs,
    ) -> Dict[str, Union[str, bool, None]]:
        """Execute the tool to send SIP-010 tokens."""
        return self._deploy(contract_address, recipient, amount)

    async def _arun(
        self,
        contract_address: str,
        recipient: str,
        amount: int,
        **kwargs,
    ) -> Dict[str, Union[str, bool, None]]:
        """Async version of the tool."""
        return self._deploy(contract_address, recipient, amount)
