from typing import Any, Dict, Optional, Type
from uuid import UUID

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from tools.bun import BunScriptRunner


class AgentAccountApproveContractInput(BaseModel):
    """Input schema for approving a contract for use with an agent account."""

    agent_account_contract: str = Field(
        ...,
        description="Contract principal of the agent account",
        example="ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM.aibtc-agent-account-test",
    )
    contract_to_approve: str = Field(
        ...,
        description="The contract principal to approve",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.slow7-action-proposal-voting",
    )


class AgentAccountApproveContractTool(BaseTool):
    name: str = "agent_account_approve_contract"
    description: str = (
        "Approves a contract, allowing the agent account to interact with it. "
        "Returns the transaction ID of the approval."
    )
    args_schema: Type[BaseModel] = AgentAccountApproveContractInput
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
        contract_to_approve: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to approve a contract."""
        if self.wallet_id is None:
            return {
                "success": False,
                "message": "Wallet ID is required",
                "data": None,
            }

        args = [agent_account_contract, contract_to_approve]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-cohort-0/agent-account/public",
            "approve-contract.ts",
            *args,
        )

    def _run(
        self,
        agent_account_contract: str,
        contract_to_approve: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool."""
        return self._run_script(
            agent_account_contract, contract_to_approve, **kwargs
        )

    async def _arun(
        self,
        agent_account_contract: str,
        contract_to_approve: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._run_script(
            agent_account_contract, contract_to_approve, **kwargs
        )


class AgentAccountRevokeContractInput(BaseModel):
    """Input schema for revoking a contract's approval from an agent account."""

    agent_account_contract: str = Field(
        ...,
        description="Contract principal of the agent account",
        example="ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM.aibtc-agent-account-test",
    )
    contract_to_revoke: str = Field(
        ...,
        description="The contract principal to revoke",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.slow7-action-proposal-voting",
    )


class AgentAccountRevokeContractTool(BaseTool):
    name: str = "agent_account_revoke_contract"
    description: str = (
        "Revokes a contract's approval, preventing the agent account from interacting with it. "
        "Returns the transaction ID of the revocation."
    )
    args_schema: Type[BaseModel] = AgentAccountRevokeContractInput
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
        contract_to_revoke: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to revoke a contract."""
        if self.wallet_id is None:
            return {
                "success": False,
                "message": "Wallet ID is required",
                "data": None,
            }

        args = [agent_account_contract, contract_to_revoke]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-cohort-0/agent-account/public",
            "revoke-contract.ts",
            *args,
        )

    def _run(
        self,
        agent_account_contract: str,
        contract_to_revoke: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool."""
        return self._run_script(
            agent_account_contract, contract_to_revoke, **kwargs
        )

    async def _arun(
        self,
        agent_account_contract: str,
        contract_to_revoke: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._run_script(
            agent_account_contract, contract_to_revoke, **kwargs
        )
