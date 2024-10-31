from typing import Optional
from crewai_tools import BaseTool
from .bun import BunScriptRunner
from pydantic import BaseModel, Field
from typing import Any, Optional, Type


class BitflowGetAvailableTokens(BaseTool):
    def __init__(self):
        super().__init__(
            name="Bitflow: Get available tokens list",
            description="Get the list of available tokens for trading",
        )

    def _run(self):
        return BunScriptRunner.bun_run("0", "stacks-bitflow", "get-tokens.ts")


class BitflowExecuteTradeToolSchema(BaseModel):
    """Input schema for BitflowExecuteTradeTool."""

    fee: str = Field(..., description="Transaction fee for the trade")
    amount: str = Field(..., description="Amount of the token to trade")
    tokenA: str = Field(..., description="Token to be traded from")
    tokenB: str = Field(..., description="Token to be traded to")


class BitflowExecuteTradeTool(BaseTool):
    name: str = "Bitflow: Execute Swap/Trade"
    description: str = (
        "Execute a market order to buy the specified amount of the token."
    )
    args_schema: Type[BaseModel] = BitflowExecuteTradeToolSchema
    account_index: Optional[str] = None

    def __init__(self, account_index: str, **kwargs):
        super().__init__(**kwargs)
        self.account_index = account_index

    def _run(self, fee, amount, tokenA, tokenB):
        return BunScriptRunner.bun_run(
            self.account_index,
            "stacks-bitflow",
            "exec-swap.ts",
            fee,
            amount,
            tokenA,
            tokenB,
        )
