import os
import requests
from crewai_tools import BaseTool


class GetLunarData(BaseTool):
    name: str = "GetLunarData"
    description: str = (
        "Fetches data for a specific token from LunarCrush including price, market cap, "
        "24h trading volume, and percentage changes."
    )

    def _run(self, token_contract_addr: str) -> str:
        """
        Fetches token data using the LunarCrush API and returns the data as a formatted string.

        The API key is fetched from the environment variable 'LUNARCRUSH_API_KEY'.

        Parameters:
        token_contract_addr -- The contract address of the token.

        Returns:
        str -- A formatted string containing token price, market cap, trading volume,
               and percentage changes.
        """
        # Get the API key from the environment variable
        api_key = os.getenv("LUNARCRUSH_API_KEY")

        if not api_key:
            return "Error: API key not found. Please set the 'LUNARCRUSH_API_KEY' environment variable."

        # LunarCrush API URL
        url = f"https://lunarcrush.com/api4/public/coins/{token_contract_addr}/v1"

        # Request headers including API key
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        try:
            # Make the API request
            response = requests.get(url, headers=headers)

            # Check if the request was successful
            response.raise_for_status()  # Raise an exception for HTTP errors

            # Parse the JSON response
            data = response.json()
            token_data = data["data"]

            # Extract relevant token data
            price = token_data["price"]
            market_cap = token_data["market_cap"]
            volume_24h = token_data["volume_24h"]
            percent_change_24h = token_data["percent_change_24h"]
            percent_change_7d = token_data["percent_change_7d"]
            alt_rank = token_data["alt_rank"]

            # Format the result as a string
            return (
                f"Token Price: ${price:.6f}\n"
                f"Market Cap: ${market_cap:.2f}\n"
                f"24h Trading Volume: ${volume_24h:.2f}\n"
                f"24h Change: {percent_change_24h}%\n"
                f"7d Change: {percent_change_7d}%\n"
                f"Alt Rank: {alt_rank}"
            )

        except requests.RequestException as e:
            # Handle any API or network errors
            return f"Error fetching token data: {e}"
