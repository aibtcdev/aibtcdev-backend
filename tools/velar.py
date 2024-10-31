from crewai_tools import BaseTool
from lib.velar import VelarApi


class VelarGetPriceHistory(BaseTool):
    def __init__(self):
        super().__init__(
            name="Velar: Get Token Price History",
            description=(
                "Retrieve historical price data for a specified cryptocurrency symbol."
            ),
            args={"token_symbol": {"type": "string"}},
        )

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


class VelarGetTokens(BaseTool):
    def __init__(self):
        super().__init__(
            name="ALEX: Get All Avaliable Token Info",
            description="Retrieve all pair data from the Alex API.",
        )

    def _run(self) -> str:
        """
        Retrieve all tokens from the Velar API and return a formatted string.

        Returns:
            str: A formatted string containing all tokens.
        """
        obj = VelarApi()

        return obj.get_tokens()
