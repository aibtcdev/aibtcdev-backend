from typing import Any, Dict, Optional, Type
from uuid import UUID

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from app.tools.bun import BunScriptRunner


class AgentAccountDepositStxInput(BaseModel):
    """Input schema for depositing STX into an agent account."""

    agent_account_contract: str = Field(
        ...,
        description="Contract principal of the agent account to deposit into",
        example="ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM.aibtc-agent-account-test",
    )
    amount: int = Field(
        ...,
        description="Amount of STX to deposit in microSTX",
        example=1000000,
        gt=0,
    )


class AgentAccountDepositStxTool(BaseTool):
    name: str = "agent_account_deposit_stx"
    description: str = (
        "Deposit STX into an agent account contract. "
        "Returns the transaction ID of the deposit."
    )
    args_schema: Type[BaseModel] = AgentAccountDepositStxInput
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
        amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to deposit STX."""
        if self.wallet_id is None:
            return {
                "success": False,
                "message": "Wallet ID is required",
                "data": None,
            }

        args = [agent_account_contract, str(amount)]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-cohort-0/agent-account/public",
            "deposit-stx.ts",
            *args,
        )

    def _run(
        self,
        agent_account_contract: str,
        amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool."""
        return self._run_script(agent_account_contract, amount, **kwargs)

    async def _arun(
        self,
        agent_account_contract: str,
        amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._run_script(agent_account_contract, amount, **kwargs)


class AgentAccountDepositFtInput(BaseModel):
    """Input schema for depositing a Fungible Token (FT) into an agent account."""

    agent_account_contract: str = Field(
        ...,
        description="Contract principal of the agent account to deposit into",
        example="ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM.aibtc-agent-account-test",
    )
    ft_contract: str = Field(
        ...,
        description="Contract principal of the Fungible Token to deposit",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-token",
    )
    amount: int = Field(
        ...,
        description="Amount of the token to deposit in its base units",
        example=1000,
        gt=0,
    )


class AgentAccountDepositFtTool(BaseTool):
    name: str = "agent_account_deposit_ft"
    description: str = (
        "Deposit a Fungible Token (FT) into an agent account contract. "
        "Returns the transaction ID of the deposit."
    )
    args_schema: Type[BaseModel] = AgentAccountDepositFtInput
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
        ft_contract: str,
        amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to deposit an FT."""
        if self.wallet_id is None:
            return {
                "success": False,
                "message": "Wallet ID is required",
                "data": None,
            }

        args = [agent_account_contract, ft_contract, str(amount)]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-cohort-0/agent-account/public",
            "deposit-ft.ts",
            *args,
        )

    def _run(
        self,
        agent_account_contract: str,
        ft_contract: str,
        amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool."""
        return self._run_script(agent_account_contract, ft_contract, amount, **kwargs)

    async def _arun(
        self,
        agent_account_contract: str,
        ft_contract: str,
        amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._run_script(agent_account_contract, ft_contract, amount, **kwargs)


class AgentAccountGetConfigurationInput(BaseModel):
    """Input schema for getting the configuration of an agent account."""

    agent_account_contract: str = Field(
        ...,
        description="Contract principal of the agent account to query",
        example="ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM.aibtc-agent-account-test",
    )


class AgentAccountGetConfigurationTool(BaseTool):
    name: str = "agent_account_get_configuration"
    description: str = "Retrieves the configuration of an agent account, including owner, agent, and sBTC addresses."
    args_schema: Type[BaseModel] = AgentAccountGetConfigurationInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(
        self,
        wallet_id: Optional[UUID] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _run_script(self, agent_account_contract: str, **kwargs) -> Dict[str, Any]:
        """Execute the tool to get configuration."""
        if self.wallet_id is None:
            return {
                "success": False,
                "message": "Wallet ID is required",
                "data": None,
            }

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-cohort-0/agent-account/read-only",
            "get-configuration.ts",
            agent_account_contract,
        )

    def _run(self, agent_account_contract: str, **kwargs) -> Dict[str, Any]:
        """Execute the tool."""
        return self._run_script(agent_account_contract, **kwargs)

    async def _arun(self, agent_account_contract: str, **kwargs) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._run_script(agent_account_contract, **kwargs)


class AgentAccountIsApprovedContractInput(BaseModel):
    """Input schema for checking if a contract is approved by an agent account."""

    agent_account_contract: str = Field(
        ...,
        description="Contract principal of the agent account to query",
        example="ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM.aibtc-agent-account-test",
    )
    contract_principal: str = Field(
        ...,
        description="The contract principal to check for approval status",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-token",
    )


class AgentAccountIsApprovedContractTool(BaseTool):
    name: str = "agent_account_is_approved_contract"
    description: str = (
        "Checks if a given contract principal is approved for use by the agent account."
    )
    args_schema: Type[BaseModel] = AgentAccountIsApprovedContractInput
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
        self, agent_account_contract: str, contract_principal: str, **kwargs
    ) -> Dict[str, Any]:
        """Execute the tool to check contract approval."""
        if self.wallet_id is None:
            return {
                "success": False,
                "message": "Wallet ID is required",
                "data": None,
            }

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-cohort-0/agent-account/read-only",
            "is-approved-contract.ts",
            agent_account_contract,
            contract_principal,
        )

    def _run(
        self, agent_account_contract: str, contract_principal: str, **kwargs
    ) -> Dict[str, Any]:
        """Execute the tool."""
        return self._run_script(agent_account_contract, contract_principal, **kwargs)

    async def _arun(
        self, agent_account_contract: str, contract_principal: str, **kwargs
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._run_script(agent_account_contract, contract_principal, **kwargs)
