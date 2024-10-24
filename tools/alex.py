import requests
from crewai_tools import BaseTool
from textwrap import dedent


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
        url = f"https://api.alexgo.io/v1/price_history/{token_address}?limit=100"
        headers = {
            "Accept": "application/json",
        }

        response = requests.get(url, headers=headers)

        if not response.ok:
            raise Exception(
                f"Failed to get token price history: {response.status_text}"
            )

        data = response.json()

        price_history = data.get("prices", [])
        formatted_history = "\n".join(
            f"Block Height: {price['block_height']}, Price: {price['avg_price_usd']}"
            for price in price_history
        )

        return f"Token: {data['token']}\n{formatted_history}"


class AlexGetSwapInfo(BaseTool):
    def __init__(self):
        super().__init__(
            name="ALEX: Get All Avaliable Token Info",
            description="Retrieve all swap data from the Alex API.",
        )

    def _run(self) -> str:
        """
        Retrieve all swap data from the Alex API and return a formatted string.

        Returns:
            str: A formatted string containing all swap data.
        """
        url = "https://api.alexgo.io/v1/allswaps"
        headers = {
            "Accept": "application/json",
        }

        response = requests.get(url, headers=headers)

        if not response.ok:
            raise Exception(f"Failed to get all swaps: {response.status_text}")

        data = response.json()

        formatted_swaps = "\n".join(
            dedent(
                f"""Pool ID: {swap['id']}, Quote: {swap['quote']}, Symbol: {swap['quoteSymbol']}, Address: {swap['quoteId']}"""
            ).strip()
            for swap in data
        )

        return formatted_swaps


class AlexGetTokenPoolVolume(BaseTool):
    def __init__(self):
        super().__init__(
            name="ALEX: Get Token Pool Volume",
            description="Retrieve pool volume data for a specified pool token ID.",
            args={"pool_token_id": {"type": "string"}},
        )

    def _run(self, pool_token_id: str) -> str:
        """
        Retrieve pool volume data for a specified pool token ID.

        Args:
            pool_token_id (str): The pool token ID.

        Returns:
            str: A formatted string containing the pool volume data.
        """
        url = f"https://api.alexgo.io/v1/pool_volume/{pool_token_id}?limit=100"
        headers = {
            "Accept": "application/json",
        }

        response = requests.get(url, headers=headers)

        if not response.ok:
            raise Exception(f"Failed to get pool volume: {response.status_text}")

        data = response.json()

        volume_values = data.get("volume_values", [])
        formatted_volume = "\n".join(
            f"Block Height: {volume['block_height']}, Volume: {volume['volume_24h']}"
            for volume in volume_values
        )

        return f"Token: {data['token']}\n{formatted_volume}"
