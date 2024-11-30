from typing import Any, Optional, Type
from crewai_tools import BaseTool
from .bun import BunScriptRunner
from pydantic import BaseModel, Field


class WalletGetBalanceSchema(BaseModel):
    """Input schema for WalletGetMyBalance.
    This tool doesn't require any input parameters but we still define the schema for consistency.
    """
    pass


class WalletGetMyBalance(BaseTool):
    """Tool for fetching wallet balance information."""
    name: str = "Get my wallet balance"
    description: str = "Get the wallet balance including STX, FT, and NFTs."
    args_schema: Type[BaseModel] = WalletGetBalanceSchema
    account_index: Optional[str] = None

    def __init__(self, account_index: str, **kwargs):
        super().__init__(**kwargs)
        self.account_index = account_index

    def _run(self) -> str:
        """
        Get the current wallet balance.

        Returns:
            str: A formatted string containing the wallet balance information,
                including STX, fungible tokens, and NFTs.
        """
        return BunScriptRunner.bun_run(
            self.account_index, "stacks-wallet", "get-my-wallet-balance.ts"
        )


class WalletGetAddressSchema(BaseModel):
    """Input schema for WalletGetMyAddress.
    This tool doesn't require any input parameters but we still define the schema for consistency.
    """
    pass


class WalletGetMyAddress(BaseTool):
    """Tool for fetching wallet STX address."""
    name: str = "Get my wallet address"
    description: str = "Get the STX address of the wallet."
    args_schema: Type[BaseModel] = WalletGetAddressSchema
    account_index: Optional[str] = None

    def __init__(self, account_index: str, **kwargs):
        super().__init__(**kwargs)
        self.account_index = account_index

    def _run(self) -> str:
        """
        Get the wallet's STX address.

        Returns:
            str: The STX address associated with the wallet.
        """
        return BunScriptRunner.bun_run(
            self.account_index, "stacks-wallet", "get-my-wallet-address.ts"
        )


class WalletSendSTXSchema(BaseModel):
    """Input schema for WalletSendSTX."""
    recipient: str = Field(..., description="Recipient STX address.")
    amount: int = Field(..., description="Amount of STX to send (in microSTX).")
    fee: Optional[int] = Field(200, description="Transaction fee in microSTX. Default is 200.")
    memo: Optional[str] = Field("", description="Optional memo to include with the transaction.")


class WalletSendSTX(BaseTool):
    """Tool for sending STX tokens."""
    name: str = "Send STX tokens"
    description: str = "Send STX tokens from your wallet to a recipient address."
    args_schema: Type[BaseModel] = WalletSendSTXSchema
    account_index: Optional[str] = None

    def __init__(self, account_index: str, **kwargs):
        super().__init__(**kwargs)
        self.account_index = account_index

    def _run(
        self,
        recipient: str,
        amount: int,
        fee: Optional[int] = 200,
        memo: Optional[str] = "",
    ) -> str:
        return BunScriptRunner.bun_run(
            self.account_index,
            "stacks-wallet",
            "transfer-my-stx.ts",
            recipient,
            str(amount),
            str(fee),
            memo,
        )
