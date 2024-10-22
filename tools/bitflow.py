from crewai_tools import BaseTool
from .bun import BunScriptRunner


class ExecuteBitflowTradeTool(BaseTool):
    """Tool for executing a market order to buy the specified amount of the token."""

    def __init__(self):
        super().__init__(
            name="ExecuteBitflowTrade",
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
            "stacks-bitflow", "exec-swap.ts", f"{fee} {amount} {tokenA} {tokenB}"
        )
