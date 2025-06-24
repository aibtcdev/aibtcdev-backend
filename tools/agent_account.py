from typing import Any, Dict, Optional, Type
from uuid import UUID

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from tools.bun import BunScriptRunner


class AgentAccountDeployInput(BaseModel):
    """Input schema for deploying an agent account contract."""

    owner_address: str = Field(
        ...,
        description="Stacks address of the wallet owner",
        example="ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM",
    )
    agent_address: str = Field(
        ...,
        description="Stacks address of the agent",
        example="ST2CY5V39NHDPWSXMW9QDT3HC3GD6Q6XX4CFRK9AG",
    )
    dao_token_contract: str = Field(
        ...,
        description="Contract principal of the DAO token",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.slow7-token",
    )
    dao_token_dex_contract: str = Field(
        ...,
        description="Contract principal of the DAO token DEX",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.slow7-token-dex",
    )
    save_to_file: bool = Field(
        False,
        description="Whether to save the contract to a file",
    )


class AgentAccountBuyAssetInput(BaseModel):
    """Input schema for buying assets through an agent account."""

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
    amount: int = Field(
        ...,
        description="Amount of the asset to buy (in base units)",
        example=1000000,
        gt=0,
    )


class AgentAccountDeployTool(BaseTool):
    name: str = "agent_account_deploy"
    description: str = (
        "Deploy a new agent account contract with specified owner and agent addresses. "
        "Returns the deployed contract address and transaction ID."
    )
    args_schema: Type[BaseModel] = AgentAccountDeployInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None
    seed_phrase: Optional[str] = None

    def __init__(
        self,
        wallet_id: Optional[UUID] = None,
        seed_phrase: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id
        self.seed_phrase = seed_phrase

    def _deploy(
        self,
        owner_address: str,
        agent_address: str,
        dao_token_contract: str,
        dao_token_dex_contract: str,
        save_to_file: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to deploy agent account."""
        if self.seed_phrase is None and self.wallet_id is None:
            return {
                "success": False,
                "message": "Either seed phrase or wallet ID is required",
                "data": None,
            }

        args = [
            owner_address,
            agent_address,
            dao_token_contract,
            dao_token_dex_contract,
            str(save_to_file).lower(),
        ]

        # Use seed phrase if available, otherwise fall back to wallet_id
        if self.seed_phrase:
            return BunScriptRunner.bun_run_with_seed_phrase(
                self.seed_phrase,
                "aibtc-cohort-0/contract-tools",
                "deploy-agent-account.ts",
                *args,
            )
        else:
            return BunScriptRunner.bun_run(
                self.wallet_id,
                "aibtc-cohort-0/contract-tools",
                "deploy-agent-account.ts",
                *args,
            )

    def _run(
        self,
        owner_address: str,
        agent_address: str,
        dao_token_contract: str,
        dao_token_dex_contract: str,
        save_to_file: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to deploy agent account."""
        return self._deploy(
            owner_address,
            agent_address,
            dao_token_contract,
            dao_token_dex_contract,
            save_to_file,
            **kwargs,
        )

    async def _arun(
        self,
        owner_address: str,
        agent_address: str,
        dao_token_contract: str,
        dao_token_dex_contract: str,
        save_to_file: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            owner_address,
            agent_address,
            dao_token_contract,
            dao_token_dex_contract,
            save_to_file,
            **kwargs,
        )


class AgentAccountBuyAssetTool(BaseTool):
    name: str = "agent_account_buy_asset"
    description: str = (
        "Buy assets through an agent account contract using a Faktory DEX. "
        "Returns the transaction ID and details of the asset purchase."
    )
    args_schema: Type[BaseModel] = AgentAccountBuyAssetInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(
        self,
        wallet_id: Optional[UUID] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _buy_asset(
        self,
        agent_account_contract: str,
        faktory_dex_contract: str,
        asset_contract: str,
        amount: int,
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
            str(amount),
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-cohort-0/agent-account/public",
            "acct-buy-asset.ts",
            *args,
        )

    def _run(
        self,
        agent_account_contract: str,
        faktory_dex_contract: str,
        asset_contract: str,
        amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to buy assets through agent account."""
        return self._buy_asset(
            agent_account_contract,
            faktory_dex_contract,
            asset_contract,
            amount,
            **kwargs,
        )

    async def _arun(
        self,
        agent_account_contract: str,
        faktory_dex_contract: str,
        asset_contract: str,
        amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._buy_asset(
            agent_account_contract,
            faktory_dex_contract,
            asset_contract,
            amount,
            **kwargs,
        )
