from typing import Optional
from crewai_tools import BaseTool
from .bun import BunScriptRunner
from pydantic import BaseModel, Field
from typing import Any, Optional, Type


class WalletGetMyBalance(BaseTool):
    name: str = "Get my wallet balance"
    description: str = "Get the wallet balance including stx, ft, and nfts."
    account_index: Optional[str] = None

    def __init__(self, account_index: str, **kwargs):
        super().__init__(**kwargs)
        self.account_index = account_index

    def _run(self):
        return BunScriptRunner.bun_run(
            self.account_index, "stacks-wallet", "get-my-wallet-balance.ts"
        )


class WalletGetMyAddress(BaseTool):
    name: str = "Get my wallet address"
    description: str = "Get the stx address of the wallet."
    account_index: Optional[str] = None

    def __init__(self, account_index: str, **kwargs):
        super().__init__(**kwargs)
        self.account_index = account_index

    def _run(self):
        return BunScriptRunner.bun_run(
            self.account_index, "stacks-wallet", "get-my-wallet-address.ts"
        )
