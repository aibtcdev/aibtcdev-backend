import requests
from crewai_tools import BaseTool
from lib.lunarcrush import LunarcrushApi


class LunarCrushGetTokenData(BaseTool):
    name: str = "LunarCrush: Get Token Social Stats"
    description: str = (
        "Fetches data for a specific token from LunarCrush including price, market cap, "
        "24h trading volume, percentage changes and alt rank."
    )

    def _run(self, token_contract_addr: str) -> str:
        """
        Fetches token data using the LunarCrush API and returns the data as a formatted string.

        Parameters:
        token_contract_addr -- The contract address of the token.

        Returns:
        str -- A formatted string containing token price, market cap, trading volume,
               and percentage changes.
        """
        try:
            obj = LunarcrushApi()
            return obj.get_token_socials(token_contract_addr)

        except requests.RequestException as e:
            # Handle any API or network errors
            return f"Error fetching token data: {e}"


class LunarCrushSearch(BaseTool):
    name: str = "LunarCrush: Search"
    description: str = "Allows for abritrary social searching using LunarCrush API."

    def _run(self, term: str) -> str:
        """
        Searches for social data using the LunarCrush API and returns the data as a formatted string.

        Parameters:
        term -- The term to search for.

        Returns:
        str -- A formatted string containing the search results.
        """
        try:
            obj = LunarcrushApi()
            return obj.search(term)

        except requests.RequestException as e:
            # Handle any API or network errors
            return f"Error fetching token data: {e}"
