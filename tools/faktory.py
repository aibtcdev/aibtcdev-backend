from backend.models import UUID
from decimal import Decimal
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from tools.bun import BunScriptRunner
from typing import Any, Dict, Optional, Type


class FaktoryBaseInput(BaseModel):
    """Base input schema for Faktory tools that don't require parameters."""

    pass

class FaktoryExecuteBuyInput(BaseModel):
      """Input schema for Faktory buy order execution."""

    stx_amount: str = Field(..., description="Amount of STX to spend on the purchase")
    dex_contract_id: str = Field(..., description="Contract ID of the DEX")
    slippage: Optional[str] = Field(
        default="50",
        description="Slippage tolerance in basis points (default: 50, which is 0.5%)",
    )

class FaktoryExecuteBuyTool(BaseTool):
    name: str = "faktory_execute_buy"
    description: str = (
        "Execute a buy order on Faktory DEX with specified STX amount and token details"
    )
    args_schema: Type[BaseModel] = FaktoryExecuteBuyInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = UUID("00000000-0000-0000-0000-000000000000")

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        stx_amount: str,
        dex_contract_id: str,
        silppage: Optional[str] = "50",
        **kwargs,
    ) -> str:
        """Execute the tool to place a buy order."""
        return BunScriptRunner.bun_run(
            self.wallet_id,
            "stacks-faktory",
            "exec-buy.ts",
            stx_amount,
            dex_contract_id,
            slippage,
        )
    
    def _run(
        self,
        stx_amount: str,
        dex_contract_id: str,
        slippage: Optional[str] = "50",
        **kwargs,
    ) -> str:
        """Execute the tool to place a buy order."""
        return self._deploy(
            stx_amount, dex_contract_id, slippage
        )

    async def _arun(
        self,
        stx_amount: str,
        dex_contract_id: str,
        slippage: Optional[str] = "50",
        **kwargs,
    ) -> str:
        """Execute the tool to place a buy order (async)."""
        return self._deploy(
            stx_amount, dex_contract_id, slippage
        )



