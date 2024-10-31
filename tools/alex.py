import requests
from crewai_tools import BaseTool
from textwrap import dedent
from lib.alex import AlexApi


class AlexGetPriceHistory(BaseTool):
    def __init__(self):
        super().__init__(
            name="ALEX: Get Token Price History",
            description=(
                "Retrieve historical price data for a specified cryptocurrency symbol."
            ),
            args={"token_address": {"type": "string"}},
        )

    def _run(self, token_address: str) -> str:
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
    def __init__(self):
        super().__init__(
            name="ALEX: Get All Avaliable Token Info",
            description="Retrieve all pair data from the Alex API.",
        )

    def _run(self) -> str:
        """
        Retrieve all pairs from the Alex API and return a formatted string.

        Returns:
            str: A formatted string containing all pair data.
        """
        obj = AlexApi()
        pairs = obj.get_pairs()

        return [
            {"token": pair["wrapped_token_y"], "token_pool_id": pair["pool_id"]}
            for pair in pairs
            if pair["wrapped_token_x"] == "STX"
        ]


class AlexGetTokenPoolVolume(BaseTool):
    def __init__(self):
        super().__init__(
            name="ALEX: Get Token Pool Volume",
            description="Retrieve pool volume data for a specified token pool ID.",
            args={"token_pool_id": {"type": "string"}},
        )

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
