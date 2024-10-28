from crewai_tools import BaseTool
from .bun import BunScriptRunner


class BitflowGetAvailableTokens(BaseTool):
    def __init__(self):
        super().__init__(
            name="Bitflow: Get available tokens list",
            description="Get the list of available tokens for trading",
        )

    def _run(self):
        return BunScriptRunner.bun_run("stacks-bitflow", "get-tokens.ts")


class BitflowExecuteTradeTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="Bitflow: Execute Swap/Trade",
            description="Execute a market order to buy the specified amount of the token",
            args={
                "fee": {"type": "string"},
                "amount": {"type": "string"},
                "tokenA": {"type": "string"},
                "tokenB": {"type": "string"},
            },
        )

    def _run(self, fee, amount, tokenA, tokenB):
        return BunScriptRunner.bun_run(
            "stacks-bitflow", "exec-swap.ts", fee, amount, tokenA, tokenB
        )
