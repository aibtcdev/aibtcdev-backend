from typing import Any, Optional, Type
from crewai_tools import BaseTool
from .bun import BunScriptRunner
from pydantic import BaseModel, Field


class BitflowGetAvailableTokens(BaseTool):
    name: str = "Bitflow: Get a list of available tokens"
    description: str = "Get the list of available tokens for trading"

    def _run(self):
        """
        Get the list of available tokens for trading.

        Returns:
            str: A formatted string containing the list of available tokens.
        """
        return BunScriptRunner.bun_run("0", "stacks-bitflow", "get-tokens.ts")


class BitflowExecuteTradeToolSchema(BaseModel):
    """Input schema for BitflowExecuteTradeTool."""
    slippage: str = Field(
        ...,
        description="Slippage amount for the trade. Default to 0.04 which equates to 4%",
    )
    amount: str = Field(
        ...,
        description="Amount of whole tokens to trade. Default to 1",
    )
    tokenA: str = Field(
        ..., 
        description="Token symbol that you are expecting to give up for the trade"
    )
    tokenB: str = Field(
        ...,
        description="Token symbol that you are expecting to receive after the trade",
    )


class BitflowExecuteTradeTool(BaseTool):
    name: str = "Bitflow: Execute Swap/Trade"
    description: str = "Execute a market order to buy the specified amount of the token."
    args_schema: Type[BaseModel] = BitflowExecuteTradeToolSchema
    account_index: Optional[str] = None

    def __init__(self, account_index: str, **kwargs):
        super().__init__(**kwargs)
        self.account_index = account_index

    def _run(self, slippage: str, amount: str, tokenA: str, tokenB: str) -> str:
        """
        Execute a market order to swap/trade tokens.

        Args:
            slippage (str): Slippage amount for the trade (e.g., "0.04" for 4%)
            amount (str): Amount of whole tokens to trade
            tokenA (str): Token symbol to give up
            tokenB (str): Token symbol to receive

        Returns:
            str: A formatted string containing the trade execution result.
        """
        return BunScriptRunner.bun_run(
            self.account_index,
            "stacks-bitflow",
            "exec-swap.ts",
            slippage,
            amount,
            f"token-{tokenA.lower()}",
            f"token-{tokenB.lower()}",
        )
