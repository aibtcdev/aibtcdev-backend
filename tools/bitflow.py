from .bun import BunScriptRunner
from backend.models import UUID
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Dict, Optional, Type, Union


class BitflowBaseInput(BaseModel):
    """Base input schema for Bitflow tools."""


class BitflowExecuteTradeInput(BitflowBaseInput):
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
        description="Token symbol that you are expecting to give up for the trade",
    )
    tokenB: str = Field(
        ...,
        description="Token symbol that you are expecting to receive after the trade",
    )


class BitflowGetAvailableTokens(BaseTool):
    name: str = "bitflow_get_available_tokens"
    description: str = "Get the list of available tokens for trading on Bitflow"
    args_schema: Type[BaseModel] = BitflowBaseInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(self, **kwargs) -> Dict[str, Union[str, bool, None]]:
        """Execute the tool to get available tokens."""
        if self.wallet_id is None:
            raise ValueError("Wallet ID is required")
        return BunScriptRunner.bun_run(
            self.wallet_id, "stacks-bitflow", "get-tokens.ts"
        )

    def _run(self, **kwargs) -> Dict[str, Union[str, bool, None]]:
        """Execute the tool to get available tokens."""
        return self._deploy()

    async def _arun(self, **kwargs) -> Dict[str, Union[str, bool, None]]:
        """Async version of the tool."""
        return self._deploy()


class BitflowExecuteTradeTool(BaseTool):
    name: str = "bitflow_execute_trade"
    description: str = (
        "Execute a market order to swap/trade tokens on Bitflow with specified parameters"
    )
    args_schema: Type[BaseModel] = BitflowExecuteTradeInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self, slippage: str, amount: str, tokenA: str, tokenB: str, **kwargs
    ) -> Dict[str, Union[str, bool, None]]:
        """Execute the tool to perform a token swap."""
        if self.wallet_id is None:
            raise ValueError("Wallet ID is required")
        return BunScriptRunner.bun_run(
            self.wallet_id,
            "stacks-bitflow",
            "execute-trade.ts",
            slippage,
            amount,
            tokenA,
            tokenB,
        )

    def _run(
        self, slippage: str, amount: str, tokenA: str, tokenB: str, **kwargs
    ) -> Dict[str, Union[str, bool, None]]:
        """Execute the tool to perform a token swap."""
        return self._deploy(slippage, amount, tokenA, tokenB, **kwargs)

    async def _arun(
        self, slippage: str, amount: str, tokenA: str, tokenB: str, **kwargs
    ) -> Dict[str, Union[str, bool, None]]:
        """Async version of the tool."""
        return self._deploy(slippage, amount, tokenA, tokenB, **kwargs)
