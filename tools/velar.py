from typing import Type
from crewai_tools import BaseTool
from lib.velar import VelarApi
from pydantic import BaseModel, Field


class VelarPriceHistorySchema(BaseModel):
    """Input schema for VelarGetPriceHistory."""
    token_symbol: str = Field(
        ...,
        description="The symbol of the token to get price history for."
    )


class VelarGetPriceHistory(BaseTool):
    """Tool for fetching token price history from Velar."""
    name: str = "Velar: Get Token Price History"
    description: str = "Retrieve historical price data for a specified cryptocurrency symbol."
    args_schema: Type[BaseModel] = VelarPriceHistorySchema

    def _run(self, token_symbol: str) -> str:
        """
        Retrieve historical price data for a specified cryptocurrency symbol.

        Args:
            token_symbol (str): The symbol of the token.

        Returns:
            str: A formatted string containing the token price history.
        """
        obj = VelarApi()
        token_stx_pools = obj.get_token_stx_pools(token_symbol.upper())
        return obj.get_token_price_history(token_stx_pools[0]["id"], "month")


class VelarGetTokensSchema(BaseModel):
    """Input schema for VelarGetTokens.
    This tool doesn't require any input parameters but we still define the schema for consistency.
    """
    pass


class VelarGetTokens(BaseTool):
    """Tool for fetching available tokens from Velar."""
    name: str = "Velar: Get All Available Token Info"
    description: str = "Retrieve a list of tokens from the Velar API."
    args_schema: Type[BaseModel] = VelarGetTokensSchema

    def _run(self) -> str:
        """
        Retrieve all tokens from the Velar API.

        Returns:
            str: A formatted string containing all available tokens.
        """
        obj = VelarApi()
        return obj.get_tokens()
