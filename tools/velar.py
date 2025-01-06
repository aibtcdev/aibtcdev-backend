from langchain.tools import BaseTool
from lib.velar import VelarApi
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional, Type, Union


class VelarPriceHistoryInput(BaseModel):
    """Input schema for retrieving token price history from Velar."""

    token_symbol: str = Field(
        ..., description="The symbol of the token to get price history for."
    )


class VelarGetPriceHistory(BaseTool):
    name: str = "velar_token_price_history"
    description: str = (
        "Retrieve historical price data for a specific cryptocurrency token from Velar. "
        "Returns monthly price data points for the token's STX trading pair."
    )
    args_schema: Type[BaseModel] = VelarPriceHistoryInput
    return_direct: bool = False

    def _deploy(self, token_symbol: str, **kwargs) -> str:
        """Execute the tool to get token price history."""
        obj = VelarApi()
        token_stx_pools = obj.get_token_stx_pools(token_symbol.upper())
        return obj.get_token_price_history(token_stx_pools[0]["id"], "month")

    def _run(self, token_symbol: str, **kwargs) -> str:
        """Execute the tool to get token price history."""
        return self._deploy(token_symbol, **kwargs)

    async def _arun(self, token_symbol: str, **kwargs) -> str:
        """Async version of the tool."""
        return self._deploy(token_symbol, **kwargs)


class VelarGetTokensInput(BaseModel):
    """Input schema for retrieving available tokens from Velar.
    This tool doesn't require any input parameters but we define the schema for consistency.
    """

    pass


class VelarGetTokens(BaseTool):
    name: str = "velar_list_tokens"
    description: str = (
        "Retrieve a list of all available tokens from the Velar API with their details "
        "including symbols, names, and contract information."
    )
    args_schema: Type[BaseModel] = VelarGetTokensInput
    return_direct: bool = False

    def _deploy(self, **kwargs) -> str:
        """Execute the tool to get available tokens."""
        obj = VelarApi()
        return obj.get_tokens()

    def _run(self, **kwargs) -> str:
        """Execute the tool to get available tokens."""
        return self._deploy(**kwargs)

    async def _arun(self, **kwargs) -> str:
        """Async version of the tool."""
        return self._deploy(**kwargs)
