from crewai_tools import BaseTool
from lib.velar import VelarApi


class VelarGetPriceHistory(BaseTool):
    def __init__(self):
        super().__init__(
            name="VELAR: Get Token Price History",
            description=(
                "Retrieve monthly price history for a token's STX trading pair. "
                "Input: Token symbol (e.g., 'ALEX', 'DIKO'). "
                "Returns: Array of price points with timestamps and USD values."
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
            name="VELAR: Get Available Tokens",
            description=(
                "Get all available tokens tradeable on Velar DEX. "
                "Returns: List of tokens with their contract addresses and metadata."
            ),
        )

    def _run(self) -> str:
        """
        Retrieve all tokens from the Velar API and return a formatted string.

        Returns:
            str: A formatted string containing all tokens.
        """
        obj = VelarApi()

        return obj.get_tokens()
