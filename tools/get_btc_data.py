import os
import requests
from langchain.tools import BaseTool
from pydantic import BaseModel
from typing import Any, Dict, Optional, Type, Union


class GetBitcoinDataInput(BaseModel):
    """Input schema for GetBitcoinData tool.
    This tool doesn't require any input parameters but we still define the schema for consistency.
    """

    pass


class GetBitcoinData(BaseTool):
    name: str = "get_bitcoin_data"
    description: str = (
        "Fetch current Bitcoin market data including price, market cap, 24h trading volume, and percentage changes from CoinMarketCap"
    )
    args_schema: Type[BaseModel] = GetBitcoinDataInput
    return_direct: bool = False

    def _deploy(self, **kwargs) -> str:
        """Execute the tool to fetch Bitcoin market data."""
        # Get the API key from the environment variable
        api_key = os.getenv("AIBTC_CMC_API_KEY")

        if not api_key:
            return "Error: API key not found. Please set the 'AIBTC_CMC_API_KEY' environment variable."

        # CoinMarketCap API URL and parameters
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        parameters = {"symbol": "BTC", "convert": "USD"}

        # Request headers including API key
        headers = {
            "Accepts": "application/json",
            "X-CMC_PRO_API_KEY": api_key,
        }

        try:
            # Make the API request
            response = requests.get(url, headers=headers, params=parameters)
            response.raise_for_status()  # Raise an exception for HTTP errors

            # Parse the JSON response
            data = response.json()
            bitcoin_data = data["data"]["BTC"]

            # Extract relevant Bitcoin data
            price = bitcoin_data["quote"]["USD"]["price"]
            market_cap = bitcoin_data["quote"]["USD"]["market_cap"]
            volume_24h = bitcoin_data["quote"]["USD"]["volume_24h"]
            percent_change_24h = bitcoin_data["quote"]["USD"]["percent_change_24h"]
            percent_change_7d = bitcoin_data["quote"]["USD"]["percent_change_7d"]

            # Format the result as a string
            return (
                f"Bitcoin Price: ${price:.2f}\n"
                f"Market Cap: ${market_cap:.2f}\n"
                f"24h Trading Volume: ${volume_24h:.2f}\n"
                f"24h Change: {percent_change_24h:.2f}%\n"
                f"7d Change: {percent_change_7d:.2f}%"
            )

        except requests.RequestException as e:
            return f"Error fetching Bitcoin data: {e}"

    def _run(self, **kwargs) -> str:
        """Execute the tool to fetch Bitcoin market data."""
        return self._deploy(**kwargs)

    async def _arun(self, **kwargs) -> str:
        """Async version of the tool."""
        return self._deploy(**kwargs)
