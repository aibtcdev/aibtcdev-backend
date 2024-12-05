from typing import Type
from crewai_tools import BaseTool
from lib.alex import AlexApi
from pydantic import BaseModel, Field


class AlexPriceHistorySchema(BaseModel):
    """Input schema for AlexGetPriceHistory."""
    token_address: str = Field(..., description="The address of the token to get price history for.")


class AlexGetPriceHistory(BaseTool):
    name: str = "ALEX: Get Token Price History"
    description: str = "Retrieve historical price data for a specified cryptocurrency symbol."
    args_schema: Type[BaseModel] = AlexPriceHistorySchema

    def _run(self, token_address: str) -> list:
        """
        Retrieve historical price data for a specified cryptocurrency symbol.

        Args:
            token_address (str): The address of the token.

        Returns:
            str: A formatted string containing the token price history.
        """
        obj = AlexApi()
        return obj.get_price_history(token_address)


class AlexGetSwapInfo(BaseTool):
    name: str = "ALEX: Get All Available Token Info"
    description: str = "Retrieve all pair data from the Alex API."

    def _run(self) -> list:
        """
        Retrieve all pairs from the Alex API and return a formatted string.

        Returns:
            str: A formatted string containing all pair data.
        """
        obj = AlexApi()
        pairs = obj.get_pairs()
        return [
            {"token": pair.get("wrapped_token_y"), "token_pool_id": pair.get("pool_id")}
            for pair in pairs
            if pair.get("wrapped_token_x") == "STX"
        ]


class AlexTokenPoolVolumeSchema(BaseModel):
    """Input schema for AlexGetTokenPoolVolume."""
    token_pool_id: str = Field(..., description="The token pool ID to get volume data for.")


class AlexGetTokenPoolVolume(BaseTool):
    name: str = "ALEX: Get Token Pool Volume"
    description: str = "Retrieve pool volume data for a specified token pool ID."
    args_schema: Type[BaseModel] = AlexTokenPoolVolumeSchema

    def _run(self, token_pool_id: str) -> str:
        """
        Retrieve pool volume data for a specified pool token ID.

        Args:
            token_pool_id (str): The token pool ID.

        Returns:
            str: A formatted string containing the pool volume data.
        """
        obj = AlexApi()
        return obj.get_token_pool_price(token_pool_id)
