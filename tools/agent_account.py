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
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-token",
    )
    dao_token_dex_contract: str = Field(
        ...,
        description="Contract principal of the DAO token DEX",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-token-dex",
    )
    save_to_file: bool = Field(
        False,
        description="Whether to save the contract to a file",
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

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

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
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            owner_address,
            agent_address,
            dao_token_contract,
            dao_token_dex_contract,
            str(save_to_file).lower(),
        ]

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
