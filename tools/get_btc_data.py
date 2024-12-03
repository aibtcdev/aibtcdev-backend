from typing import Type
import os
import requests
from crewai_tools import BaseTool
from pydantic import BaseModel


class GetBitcoinDataSchema(BaseModel):
    """Input schema for GetBitcoinData tool.
    This tool doesn't require any input parameters but we still define the schema for consistency.
    """
    pass


class GetBitcoinData(BaseTool):
    """Tool for fetching current Bitcoin market data from CoinMarketCap."""
    name: str = "GetBitcoinData"
    description: str = "Fetches Bitcoin data including price, market cap, 24h trading volume, and percentage changes."
    args_schema: Type[BaseModel] = GetBitcoinDataSchema

    def _run(self) -> str:
        """
        Fetches Bitcoin data using the CoinMarketCap API.

        Required Environment Variables:
            CMC_API_KEY: CoinMarketCap API key for authentication

        Returns:
            str: A formatted string containing Bitcoin price, market cap, trading volume,
                and percentage changes. Returns an error message if the API call fails.
        """
        # Get the API key from the environment variable
        api_key = os.getenv("CMC_API_KEY")

        if not api_key:
            return "Error: API key not found. Please set the 'CMC_API_KEY' environment variable."

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
