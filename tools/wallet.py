from typing import Optional
from crewai_tools import BaseTool
from .bun import BunScriptRunner
from pydantic import BaseModel, Field
from typing import Any, Optional, Type


class WalletGetMyBalance(BaseTool):
    name: str = "Wallet: Get My Balance"
    description: str = "Get the balance of the wallet."
    account_index: Optional[str] = None

    def __init__(self, account_index: str, **kwargs):
        super().__init__(**kwargs)
        self.account_index = account_index

    def _run(self):
        return BunScriptRunner.bun_run(
            self.account_index, "stacks-wallet", "get-my-wallet-balance.ts"
        )


class WalletGetMyAddress(BaseTool):
    name: str = "Wallet: Get My Address"
    description: str = "Get the address of the wallet."
    account_index: Optional[str] = None

    def __init__(self, account_index: str, **kwargs):
        super().__init__(**kwargs)
        self.account_index = account_index

    def _run(self):
        return BunScriptRunner.bun_run(
            self.account_index, "stacks-wallet", "get-my-wallet-address.ts"
        )
