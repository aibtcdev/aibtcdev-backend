from typing import Any, Dict, Optional, Type
from uuid import UUID

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from tools.bun import BunScriptRunner


class AgentAccountFaktoryBuyAssetInput(BaseModel):
    """Input schema for buying assets through an agent account via Faktory."""

    agent_account_contract: str = Field(
        ...,
        description="Contract principal of the agent account to use for buying",
        example="ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM.aibtc-acct-ST1PQ-PGZGM-ST35K-VM3QA",
    )
    faktory_dex_contract: str = Field(
        ...,
        description="Contract principal of the Faktory DEX to buy from",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.slow7-token-dex",
    )
    asset_contract: str = Field(
        ...,
        description="Contract principal of the asset to buy",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.slow7-token",
    )
    amount_to_spend: float = Field(
        ...,
        description="Amount of sBTC to spend",
        example=0.5,
        gt=0,
    )
    slippage: Optional[int] = Field(
        1,
        description="Percentage of slippage tolerance (e.g., 1 for 1%)",
        example=1,
        ge=0,
        le=100,
    )


class AgentAccountFaktoryBuyAssetTool(BaseTool):
    name: str = "agent_account_faktory_buy_asset"
    description: str = (
        "Buy assets through an agent account contract using a Faktory DEX. "
        "Returns the transaction ID and details of the asset purchase."
    )
    args_schema: Type[BaseModel] = AgentAccountFaktoryBuyAssetInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(
        self,
        wallet_id: Optional[UUID] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _run_script(
        self,
        agent_account_contract: str,
        faktory_dex_contract: str,
        asset_contract: str,
        amount_to_spend: float,
        slippage: Optional[int] = 1,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to buy assets through agent account."""
        if self.wallet_id is None:
            return {
                "success": False,
                "message": "Wallet ID is required",
                "data": None,
            }

        args = [
            agent_account_contract,
            faktory_dex_contract,
            asset_contract,
            str(amount_to_spend),
            str(slippage),
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-cohort-0/agent-account/public",
            "faktory-buy-asset.ts",
            *args,
        )

    def _run(
        self,
        agent_account_contract: str,
        faktory_dex_contract: str,
        asset_contract: str,
        amount_to_spend: float,
        slippage: Optional[int] = 1,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to buy assets through agent account."""
        return self._run_script(
            agent_account_contract,
            faktory_dex_contract,
            asset_contract,
            amount_to_spend,
            slippage,
            **kwargs,
        )

    async def _arun(
        self,
        agent_account_contract: str,
        faktory_dex_contract: str,
        asset_contract: str,
        amount_to_spend: float,
        slippage: Optional[int] = 1,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._run_script(
            agent_account_contract,
            faktory_dex_contract,
            asset_contract,
            amount_to_spend,
            slippage,
            **kwargs,
        )


class AgentAccountFaktorySellAssetInput(BaseModel):
    """Input schema for selling assets through an agent account via Faktory."""

    agent_account_contract: str = Field(
        ...,
        description="Contract principal of the agent account to use for selling",
        example="ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM.aibtc-acct-ST1PQ-PGZGM-ST35K-VM3QA",
    )
    faktory_dex_contract: str = Field(
        ...,
        description="Contract principal of the Faktory DEX to sell on",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.slow7-token-dex",
    )
    asset_contract: str = Field(
        ...,
        description="Contract principal of the asset to sell",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.slow7-token",
    )
    amount_to_sell: float = Field(
        ...,
        description="Amount of the asset to sell (in its base units)",
        example=1000,
        gt=0,
    )
    slippage: Optional[int] = Field(
        1,
        description="Percentage of slippage tolerance (e.g., 1 for 1%)",
        example=1,
        ge=0,
        le=100,
    )


class AgentAccountFaktorySellAssetTool(BaseTool):
    name: str = "agent_account_faktory_sell_asset"
    description: str = (
        "Sell assets from an agent account contract using a Faktory DEX. "
        "Returns the transaction ID and details of the asset sale."
    )
    args_schema: Type[BaseModel] = AgentAccountFaktorySellAssetInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(
        self,
        wallet_id: Optional[UUID] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _run_script(
        self,
        agent_account_contract: str,
        faktory_dex_contract: str,
        asset_contract: str,
        amount_to_sell: float,
        slippage: Optional[int] = 1,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to sell assets from an agent account."""
        if self.wallet_id is None:
            return {
                "success": False,
                "message": "Wallet ID is required",
                "data": None,
            }

        args = [
            agent_account_contract,
            faktory_dex_contract,
            asset_contract,
            str(amount_to_sell),
            str(slippage),
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-cohort-0/agent-account/public",
            "faktory-sell-asset.ts",
            *args,
        )

    def _run(
        self,
        agent_account_contract: str,
        faktory_dex_contract: str,
        asset_contract: str,
        amount_to_sell: float,
        slippage: Optional[int] = 1,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to sell assets from an agent account."""
        return self._run_script(
            agent_account_contract,
            faktory_dex_contract,
            asset_contract,
            amount_to_sell,
            slippage,
            **kwargs,
        )

    async def _arun(
        self,
        agent_account_contract: str,
        faktory_dex_contract: str,
        asset_contract: str,
        amount_to_sell: float,
        slippage: Optional[int] = 1,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._run_script(
            agent_account_contract,
            faktory_dex_contract,
            asset_contract,
            amount_to_sell,
            slippage,
            **kwargs,
        )
