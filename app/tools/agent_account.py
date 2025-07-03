from typing import Any, Dict, Optional, Type
from uuid import UUID

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from app.tools.bun import BunScriptRunner


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

    def _run_script(
        self,
        owner_address: str,
        agent_address: str,
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
        save_to_file: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to deploy agent account."""
        return self._run_script(
            owner_address,
            agent_address,
            save_to_file,
            **kwargs,
        )

    async def _arun(
        self,
        owner_address: str,
        agent_address: str,
        save_to_file: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._run_script(
            owner_address,
            agent_address,
            save_to_file,
            **kwargs,
        )
