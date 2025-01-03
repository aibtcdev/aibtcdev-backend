from langchain.tools import BaseTool
from lib.alex import AlexApi
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Type


class AlexPriceHistoryInput(BaseModel):
    """Input schema for AlexGetPriceHistory."""

    token_address: str = Field(
        ..., description="The address of the token to get price history for."
    )


class AlexTokenPoolVolumeInput(BaseModel):
    """Input schema for AlexGetTokenPoolVolume."""

    token_pool_id: str = Field(
        ..., description="The token pool ID to get volume data for."
    )


class AlexGetPriceHistory(BaseTool):
    name: str = "alex_get_price_history"
    description: str = (
        "Retrieve historical price data for a specified cryptocurrency token address"
    )
    args_schema: Type[BaseModel] = AlexPriceHistoryInput
    return_direct: bool = False

    def _deploy(self, token_address: str, **kwargs) -> List[Any]:
        """Execute the tool to get price history."""
        obj = AlexApi()
        return obj.get_price_history(token_address)

    def _run(self, token_address: str, **kwargs) -> List[Any]:
        """Execute the tool to get price history."""
        return self._deploy(token_address)

    async def _arun(self, token_address: str, **kwargs) -> List[Any]:
        """Async version of the tool."""
        return self._deploy(token_address)


class AlexGetSwapInfo(BaseTool):
    name: str = "alex_get_swap_info"
    description: str = "Retrieve all available token pair data from the Alex DEX"
    return_direct: bool = False

    def _deploy(self, **kwargs) -> List[Dict[str, str]]:
        """Execute the tool to get swap info."""
        obj = AlexApi()
        pairs = obj.get_pairs()
        return [
            {"token": pair.get("wrapped_token_y"), "token_pool_id": pair.get("pool_id")}
            for pair in pairs
            if pair.get("wrapped_token_x") == "STX"
        ]

    def _run(self, **kwargs) -> List[Dict[str, str]]:
        """Execute the tool to get swap info."""
        return self._deploy()

    async def _arun(self, **kwargs) -> List[Dict[str, str]]:
        """Async version of the tool."""
        return self._deploy()


class AlexGetTokenPoolVolume(BaseTool):
    name: str = "alex_get_token_pool_volume"
    description: str = "Retrieve pool volume data for a specified token pool ID"
    args_schema: Type[BaseModel] = AlexTokenPoolVolumeInput
    return_direct: bool = False

    def _deploy(self, token_pool_id: str, **kwargs) -> str:
        """Execute the tool to get token pool volume."""
        obj = AlexApi()
        return obj.get_token_pool_price(token_pool_id)

    def _run(self, token_pool_id: str, **kwargs) -> str:
        """Execute the tool to get token pool volume."""
        return self._deploy(token_pool_id)

    async def _arun(self, token_pool_id: str, **kwargs) -> str:
        """Async version of the tool."""
        return self._deploy(token_pool_id)
