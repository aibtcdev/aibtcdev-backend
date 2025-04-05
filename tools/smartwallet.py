from typing import Any, Dict, Optional, Type
from uuid import UUID

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from tools.bun import BunScriptRunner


class SmartWalletGenerateSmartWalletInput(BaseModel):
    """Input schema for generating a smart wallet contract."""

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
    generate_files: bool = Field(
        False,
        description="Whether to generate contract files",
    )


class SmartWalletGenerateSmartWalletTool(BaseTool):
    name: str = "smartwallet_generate_smart_wallet"
    description: str = (
        "Generate a new smart wallet contract with specified owner and agent addresses. "
        "Returns the contract name, hash, and source code."
    )
    args_schema: Type[BaseModel] = SmartWalletGenerateSmartWalletInput
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
        generate_files: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to generate smart wallet."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            owner_address,
            agent_address,
            dao_token_contract,
            dao_token_dex_contract,
            str(generate_files).lower(),
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/smart-wallet",
            "generate-smart-wallet.ts",
            *args,
        )

    def _run(
        self,
        owner_address: str,
        agent_address: str,
        dao_token_contract: str,
        dao_token_dex_contract: str,
        generate_files: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to generate smart wallet."""
        return self._deploy(
            owner_address,
            agent_address,
            dao_token_contract,
            dao_token_dex_contract,
            generate_files,
            **kwargs,
        )

    async def _arun(
        self,
        owner_address: str,
        agent_address: str,
        dao_token_contract: str,
        dao_token_dex_contract: str,
        generate_files: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            owner_address,
            agent_address,
            dao_token_contract,
            dao_token_dex_contract,
            generate_files,
            **kwargs,
        )


class SmartWalletGenerateMySmartWalletInput(BaseModel):
    """Input schema for generating a smart wallet contract using the current agent as the agent address."""

    owner_address: str = Field(
        ...,
        description="Stacks address of the wallet owner",
        example="ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM",
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
    generate_files: bool = Field(
        False,
        description="Whether to generate contract files",
    )


class SmartWalletGenerateMySmartWalletTool(BaseTool):
    name: str = "smartwallet_generate_my_smart_wallet"
    description: str = (
        "Generate a new smart wallet contract using the current agent as the agent address. "
        "Returns the contract name, hash, and source code."
    )
    args_schema: Type[BaseModel] = SmartWalletGenerateMySmartWalletInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        owner_address: str,
        dao_token_contract: str,
        dao_token_dex_contract: str,
        generate_files: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to generate smart wallet."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            owner_address,
            dao_token_contract,
            dao_token_dex_contract,
            str(generate_files).lower(),
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/smart-wallet",
            "generate-my-smart-wallet.ts",
            *args,
        )

    def _run(
        self,
        owner_address: str,
        dao_token_contract: str,
        dao_token_dex_contract: str,
        generate_files: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to generate smart wallet."""
        return self._deploy(
            owner_address,
            dao_token_contract,
            dao_token_dex_contract,
            generate_files,
            **kwargs,
        )

    async def _arun(
        self,
        owner_address: str,
        dao_token_contract: str,
        dao_token_dex_contract: str,
        generate_files: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            owner_address,
            dao_token_contract,
            dao_token_dex_contract,
            generate_files,
            **kwargs,
        )


class SmartWalletDeploySmartWalletInput(BaseModel):
    """Input schema for deploying a smart wallet contract."""

    owner_address: str = Field(
        ...,
        description="Stacks address of the wallet owner",
        example="ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM",
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


class SmartWalletDeploySmartWalletTool(BaseTool):
    name: str = "smartwallet_deploy_smart_wallet"
    description: str = (
        "Deploy a new smart wallet contract with specified owner and agent addresses. "
        "Returns the deployed contract address and transaction ID."
    )
    args_schema: Type[BaseModel] = SmartWalletDeploySmartWalletInput
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
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to deploy smart wallet."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            owner_address,
            agent_address,
            dao_token_contract,
            dao_token_dex_contract,
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/smart-wallet",
            "deploy-smart-wallet.ts",
            *args,
        )

    def _run(
        self,
        owner_address: str,
        agent_address: str,
        dao_token_contract: str,
        dao_token_dex_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to deploy smart wallet."""
        return self._deploy(
            owner_address,
            agent_address,
            dao_token_contract,
            dao_token_dex_contract,
            **kwargs,
        )

    async def _arun(
        self,
        owner_address: str,
        agent_address: str,
        dao_token_contract: str,
        dao_token_dex_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            owner_address,
            agent_address,
            dao_token_contract,
            dao_token_dex_contract,
            **kwargs,
        )


class SmartWalletDeployMySmartWalletInput(BaseModel):
    """Input schema for deploying a smart wallet contract using the current agent as the agent address."""

    owner_address: str = Field(
        ...,
        description="Stacks address of the wallet owner",
        example="ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM",
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


class SmartWalletDeployMySmartWalletTool(BaseTool):
    name: str = "smartwallet_deploy_my_smart_wallet"
    description: str = (
        "Deploy a new smart wallet contract using the current agent as the agent address. "
        "Returns the deployed contract address and transaction ID."
    )
    args_schema: Type[BaseModel] = SmartWalletDeployMySmartWalletInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        owner_address: str,
        dao_token_contract: str,
        dao_token_dex_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to deploy smart wallet."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            owner_address,
            dao_token_contract,
            dao_token_dex_contract,
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/smart-wallet",
            "deploy-my-smart-wallet.ts",
            *args,
        )

    def _run(
        self,
        owner_address: str,
        dao_token_contract: str,
        dao_token_dex_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to deploy smart wallet."""
        return self._deploy(
            owner_address,
            dao_token_contract,
            dao_token_dex_contract,
            **kwargs,
        )

    async def _arun(
        self,
        owner_address: str,
        dao_token_contract: str,
        dao_token_dex_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            owner_address,
            dao_token_contract,
            dao_token_dex_contract,
            **kwargs,
        )


class SmartWalletIsApprovedAssetInput(BaseModel):
    """Input schema for checking if an asset is approved in a smart wallet."""

    smart_wallet_contract: str = Field(
        ...,
        description="Contract principal of the smart wallet",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-user-agent-smart-wallet",
    )
    asset_contract: str = Field(
        ...,
        description="Contract principal of the asset",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-token",
    )


class SmartWalletIsApprovedAssetTool(BaseTool):
    name: str = "smartwallet_is_approved_asset"
    description: str = (
        "Check if an asset is approved for use with a smart wallet. "
        "Returns true if the asset is approved, false otherwise."
    )
    args_schema: Type[BaseModel] = SmartWalletIsApprovedAssetInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        smart_wallet_contract: str,
        asset_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to check asset approval."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            smart_wallet_contract,
            asset_contract,
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/smart-wallet/read-only",
            "is-approved-asset.ts",
            *args,
        )

    def _run(
        self,
        smart_wallet_contract: str,
        asset_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to check asset approval."""
        return self._deploy(
            smart_wallet_contract,
            asset_contract,
            **kwargs,
        )

    async def _arun(
        self,
        smart_wallet_contract: str,
        asset_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            smart_wallet_contract,
            asset_contract,
            **kwargs,
        )


class SmartWalletGetBalanceStxInput(BaseModel):
    """Input schema for getting STX balance from a smart wallet."""

    smart_wallet_contract: str = Field(
        ...,
        description="Contract principal of the smart wallet",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-user-agent-smart-wallet",
    )


class SmartWalletGetBalanceStxTool(BaseTool):
    name: str = "smartwallet_get_balance_stx"
    description: str = (
        "Get the STX balance from a smart wallet. " "Returns the balance in microSTX."
    )
    args_schema: Type[BaseModel] = SmartWalletGetBalanceStxInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        smart_wallet_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get STX balance."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [smart_wallet_contract]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/smart-wallet/read-only",
            "get-balance-stx.ts",
            *args,
        )

    def _run(
        self,
        smart_wallet_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get STX balance."""
        return self._deploy(smart_wallet_contract, **kwargs)

    async def _arun(
        self,
        smart_wallet_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(smart_wallet_contract, **kwargs)


class SmartWalletGetConfigurationInput(BaseModel):
    """Input schema for getting smart wallet configuration."""

    smart_wallet_contract: str = Field(
        ...,
        description="Contract principal of the smart wallet",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-user-agent-smart-wallet",
    )


class SmartWalletGetConfigurationTool(BaseTool):
    name: str = "smartwallet_get_configuration"
    description: str = (
        "Get the configuration of a smart wallet. "
        "Returns owner, agent, and other configuration details."
    )
    args_schema: Type[BaseModel] = SmartWalletGetConfigurationInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        smart_wallet_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get wallet configuration."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [smart_wallet_contract]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/smart-wallet/read-only",
            "get-configuration.ts",
            *args,
        )

    def _run(
        self,
        smart_wallet_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get wallet configuration."""
        return self._deploy(smart_wallet_contract, **kwargs)

    async def _arun(
        self,
        smart_wallet_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(smart_wallet_contract, **kwargs)


class SmartWalletApproveAssetInput(BaseModel):
    """Input schema for approving an asset in a smart wallet."""

    smart_wallet_contract: str = Field(
        ...,
        description="Contract principal of the smart wallet",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-user-agent-smart-wallet",
    )
    asset_contract: str = Field(
        ...,
        description="Contract principal of the asset to approve",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-token",
    )


class SmartWalletApproveAssetTool(BaseTool):
    name: str = "smartwallet_approve_asset"
    description: str = (
        "Approve an asset for use with a smart wallet. "
        "Returns the transaction ID of the approval transaction."
    )
    args_schema: Type[BaseModel] = SmartWalletApproveAssetInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        smart_wallet_contract: str,
        asset_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to approve asset."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            smart_wallet_contract,
            asset_contract,
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/smart-wallet/public",
            "approve-asset.ts",
            *args,
        )

    def _run(
        self,
        smart_wallet_contract: str,
        asset_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to approve asset."""
        return self._deploy(
            smart_wallet_contract,
            asset_contract,
            **kwargs,
        )

    async def _arun(
        self,
        smart_wallet_contract: str,
        asset_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            smart_wallet_contract,
            asset_contract,
            **kwargs,
        )


class SmartWalletRevokeAssetInput(BaseModel):
    """Input schema for revoking an asset from a smart wallet."""

    smart_wallet_contract: str = Field(
        ...,
        description="Contract principal of the smart wallet",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-user-agent-smart-wallet",
    )
    asset_contract: str = Field(
        ...,
        description="Contract principal of the asset to revoke",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-token",
    )


class SmartWalletRevokeAssetTool(BaseTool):
    name: str = "smartwallet_revoke_asset"
    description: str = (
        "Revoke an asset from a smart wallet. "
        "Returns the transaction ID of the revocation transaction."
    )
    args_schema: Type[BaseModel] = SmartWalletRevokeAssetInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        smart_wallet_contract: str,
        asset_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to revoke asset."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            smart_wallet_contract,
            asset_contract,
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/smart-wallet/public",
            "revoke-asset.ts",
            *args,
        )

    def _run(
        self,
        smart_wallet_contract: str,
        asset_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to revoke asset."""
        return self._deploy(
            smart_wallet_contract,
            asset_contract,
            **kwargs,
        )

    async def _arun(
        self,
        smart_wallet_contract: str,
        asset_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            smart_wallet_contract,
            asset_contract,
            **kwargs,
        )


class SmartWalletDepositStxInput(BaseModel):
    """Input schema for depositing STX to a smart wallet."""

    smart_wallet_contract: str = Field(
        ...,
        description="Contract principal of the smart wallet",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-user-agent-smart-wallet",
    )
    amount: int = Field(
        ...,
        description="Amount of STX to deposit in microSTX",
        example=1000000,
        gt=0,
    )


class SmartWalletDepositStxTool(BaseTool):
    name: str = "smartwallet_deposit_stx"
    description: str = (
        "Deposit STX to a smart wallet. "
        "Returns the transaction ID of the deposit transaction."
    )
    args_schema: Type[BaseModel] = SmartWalletDepositStxInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        smart_wallet_contract: str,
        amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to deposit STX."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            smart_wallet_contract,
            str(amount),
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/smart-wallet/public",
            "deposit-stx.ts",
            *args,
        )

    def _run(
        self,
        smart_wallet_contract: str,
        amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to deposit STX."""
        return self._deploy(
            smart_wallet_contract,
            amount,
            **kwargs,
        )

    async def _arun(
        self,
        smart_wallet_contract: str,
        amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            smart_wallet_contract,
            amount,
            **kwargs,
        )


class SmartWalletWithdrawStxInput(BaseModel):
    """Input schema for withdrawing STX from a smart wallet."""

    smart_wallet_contract: str = Field(
        ...,
        description="Contract principal of the smart wallet",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-user-agent-smart-wallet",
    )
    amount: int = Field(
        ...,
        description="Amount of STX to withdraw in microSTX",
        example=1000000,
        gt=0,
    )


class SmartWalletWithdrawStxTool(BaseTool):
    name: str = "smartwallet_withdraw_stx"
    description: str = (
        "Withdraw STX from a smart wallet. "
        "Returns the transaction ID of the withdrawal transaction."
    )
    args_schema: Type[BaseModel] = SmartWalletWithdrawStxInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        smart_wallet_contract: str,
        amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to withdraw STX."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            smart_wallet_contract,
            str(amount),
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/smart-wallet/public",
            "withdraw-stx.ts",
            *args,
        )

    def _run(
        self,
        smart_wallet_contract: str,
        amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to withdraw STX."""
        return self._deploy(
            smart_wallet_contract,
            amount,
            **kwargs,
        )

    async def _arun(
        self,
        smart_wallet_contract: str,
        amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            smart_wallet_contract,
            amount,
            **kwargs,
        )


class SmartWalletDepositFtInput(BaseModel):
    """Input schema for depositing fungible tokens to a smart wallet."""

    smart_wallet_contract: str = Field(
        ...,
        description="Contract principal of the smart wallet",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-user-agent-smart-wallet",
    )
    ft_contract: str = Field(
        ...,
        description="Contract principal of the fungible token",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-token",
    )
    amount: int = Field(
        ...,
        description="Amount of tokens to deposit",
        example=1000,
        gt=0,
    )


class SmartWalletDepositFtTool(BaseTool):
    name: str = "smartwallet_deposit_ft"
    description: str = (
        "Deposit fungible tokens to a smart wallet. "
        "Returns the transaction ID of the deposit transaction."
    )
    args_schema: Type[BaseModel] = SmartWalletDepositFtInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        smart_wallet_contract: str,
        ft_contract: str,
        amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to deposit fungible tokens."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            smart_wallet_contract,
            ft_contract,
            str(amount),
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/smart-wallet/public",
            "deposit-ft.ts",
            *args,
        )

    def _run(
        self,
        smart_wallet_contract: str,
        ft_contract: str,
        amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to deposit fungible tokens."""
        return self._deploy(
            smart_wallet_contract,
            ft_contract,
            amount,
            **kwargs,
        )

    async def _arun(
        self,
        smart_wallet_contract: str,
        ft_contract: str,
        amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            smart_wallet_contract,
            ft_contract,
            amount,
            **kwargs,
        )


class SmartWalletWithdrawFtInput(BaseModel):
    """Input schema for withdrawing fungible tokens from a smart wallet."""

    smart_wallet_contract: str = Field(
        ...,
        description="Contract principal of the smart wallet",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-user-agent-smart-wallet",
    )
    ft_contract: str = Field(
        ...,
        description="Contract principal of the fungible token",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-token",
    )
    amount: int = Field(
        ...,
        description="Amount of tokens to withdraw",
        example=1000,
        gt=0,
    )


class SmartWalletWithdrawFtTool(BaseTool):
    name: str = "smartwallet_withdraw_ft"
    description: str = (
        "Withdraw fungible tokens from a smart wallet. "
        "Returns the transaction ID of the withdrawal transaction."
    )
    args_schema: Type[BaseModel] = SmartWalletWithdrawFtInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        smart_wallet_contract: str,
        ft_contract: str,
        amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to withdraw fungible tokens."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            smart_wallet_contract,
            ft_contract,
            str(amount),
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/smart-wallet/public",
            "withdraw-ft.ts",
            *args,
        )

    def _run(
        self,
        smart_wallet_contract: str,
        ft_contract: str,
        amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to withdraw fungible tokens."""
        return self._deploy(
            smart_wallet_contract,
            ft_contract,
            amount,
            **kwargs,
        )

    async def _arun(
        self,
        smart_wallet_contract: str,
        ft_contract: str,
        amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            smart_wallet_contract,
            ft_contract,
            amount,
            **kwargs,
        )


class SmartWalletProxyCreateProposalInput(BaseModel):
    """Input schema for creating a core proposal through a smart wallet."""

    smart_wallet_contract: str = Field(
        ...,
        description="Contract principal of the smart wallet",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-user-agent-smart-wallet",
    )
    dao_core_proposals_extension_contract: str = Field(
        ...,
        description="Contract principal of the DAO core proposals extension",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-core-proposals-v2",
    )
    dao_proposal_contract: str = Field(
        ...,
        description="Contract principal of the DAO proposal",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.proposal-add-extension",
    )
    dao_token_contract: str = Field(
        ...,
        description="Contract principal of the DAO token",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-token",
    )


class SmartWalletProxyCreateProposalTool(BaseTool):
    name: str = "smartwallet_proxy_create_proposal"
    description: str = (
        "Create a core proposal through a smart wallet. "
        "Returns the transaction ID of the proposal creation transaction."
    )
    args_schema: Type[BaseModel] = SmartWalletProxyCreateProposalInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        smart_wallet_contract: str,
        dao_core_proposals_extension_contract: str,
        dao_proposal_contract: str,
        dao_token_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to create a core proposal."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            smart_wallet_contract,
            dao_core_proposals_extension_contract,
            dao_proposal_contract,
            dao_token_contract,
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/smart-wallet/public",
            "proxy-create-proposal.ts",
            *args,
        )

    def _run(
        self,
        smart_wallet_contract: str,
        dao_core_proposals_extension_contract: str,
        dao_proposal_contract: str,
        dao_token_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to create a core proposal."""
        return self._deploy(
            smart_wallet_contract,
            dao_core_proposals_extension_contract,
            dao_proposal_contract,
            dao_token_contract,
            **kwargs,
        )

    async def _arun(
        self,
        smart_wallet_contract: str,
        dao_core_proposals_extension_contract: str,
        dao_proposal_contract: str,
        dao_token_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            smart_wallet_contract,
            dao_core_proposals_extension_contract,
            dao_proposal_contract,
            dao_token_contract,
            **kwargs,
        )


class SmartWalletProxyProposeActionSendMessageInput(BaseModel):
    """Input schema for proposing a send message action through a smart wallet."""

    smart_wallet_contract: str = Field(
        ...,
        description="Contract principal of the smart wallet",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-user-agent-smart-wallet",
    )
    dao_action_proposals_extension_contract: str = Field(
        ...,
        description="Contract principal of the DAO action proposals extension",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-action-proposals-v2",
    )
    dao_action_proposal_contract: str = Field(
        ...,
        description="Contract principal of the DAO action proposal",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-action-send-message",
    )
    dao_token_contract: str = Field(
        ...,
        description="Contract principal of the DAO token",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-token",
    )
    message: str = Field(
        ...,
        description="Message to send",
        example="hello world",
    )


class SmartWalletProxyProposeActionSendMessageTool(BaseTool):
    name: str = "smartwallet_proxy_propose_action_send_message"
    description: str = (
        "Propose a send message action through a smart wallet. "
        "Returns the transaction ID of the action proposal transaction."
    )
    args_schema: Type[BaseModel] = SmartWalletProxyProposeActionSendMessageInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        smart_wallet_contract: str,
        dao_action_proposals_extension_contract: str,
        dao_action_proposal_contract: str,
        dao_token_contract: str,
        message: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose a send message action."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            smart_wallet_contract,
            dao_action_proposals_extension_contract,
            dao_action_proposal_contract,
            dao_token_contract,
            message,
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/smart-wallet/public",
            "proxy-propose-action-send-message.ts",
            *args,
        )

    def _run(
        self,
        smart_wallet_contract: str,
        dao_action_proposals_extension_contract: str,
        dao_action_proposal_contract: str,
        dao_token_contract: str,
        message: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose a send message action."""
        return self._deploy(
            smart_wallet_contract,
            dao_action_proposals_extension_contract,
            dao_action_proposal_contract,
            dao_token_contract,
            message,
            **kwargs,
        )

    async def _arun(
        self,
        smart_wallet_contract: str,
        dao_action_proposals_extension_contract: str,
        dao_action_proposal_contract: str,
        dao_token_contract: str,
        message: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            smart_wallet_contract,
            dao_action_proposals_extension_contract,
            dao_action_proposal_contract,
            dao_token_contract,
            message,
            **kwargs,
        )


class SmartWalletVoteOnActionProposalInput(BaseModel):
    """Input schema for voting on an action proposal through a smart wallet."""

    smart_wallet_contract: str = Field(
        ...,
        description="Contract principal of the smart wallet",
        example="ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM.aibtc-user-agent-smart-wallet",
    )
    dao_action_proposals_extension_contract: str = Field(
        ...,
        description="Contract principal of the DAO action proposals extension",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-action-proposals-v2",
    )
    proposal_id: int = Field(
        ...,
        description="ID of the action proposal",
        example=1,
        gt=0,
    )
    vote: bool = Field(
        ...,
        description="True to vote in favor, False to vote against",
        example=True,
    )


class SmartWalletVoteOnActionProposalTool(BaseTool):
    name: str = "smartwallet_vote_on_action_proposal"
    description: str = (
        "Vote on an action proposal through a smart wallet. "
        "Returns the transaction ID of the vote transaction."
    )
    args_schema: Type[BaseModel] = SmartWalletVoteOnActionProposalInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        smart_wallet_contract: str,
        dao_action_proposals_extension_contract: str,
        proposal_id: int,
        vote: bool,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to vote on an action proposal."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            smart_wallet_contract,
            dao_action_proposals_extension_contract,
            str(proposal_id),
            str(vote).lower(),
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/smart-wallet/public",
            "vote-on-action-proposal.ts",
            *args,
        )

    def _run(
        self,
        smart_wallet_contract: str,
        dao_action_proposals_extension_contract: str,
        proposal_id: int,
        vote: bool,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to vote on an action proposal."""
        return self._deploy(
            smart_wallet_contract,
            dao_action_proposals_extension_contract,
            proposal_id,
            vote,
            **kwargs,
        )

    async def _arun(
        self,
        smart_wallet_contract: str,
        dao_action_proposals_extension_contract: str,
        proposal_id: int,
        vote: bool,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            smart_wallet_contract,
            dao_action_proposals_extension_contract,
            proposal_id,
            vote,
            **kwargs,
        )


class SmartWalletVoteOnCoreProposalInput(BaseModel):
    """Input schema for voting on a core proposal through a smart wallet."""

    smart_wallet_contract: str = Field(
        ...,
        description="Contract principal of the smart wallet",
        example="ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM.aibtc-user-agent-smart-wallet",
    )
    dao_core_proposals_extension_contract: str = Field(
        ...,
        description="Contract principal of the DAO core proposals extension",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-core-proposals-v2",
    )
    dao_proposal_contract: str = Field(
        ...,
        description="Contract principal of the DAO proposal",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-onchain-messaging-send",
    )
    vote: bool = Field(
        ...,
        description="True to vote in favor, False to vote against",
        example=True,
    )


class SmartWalletVoteOnCoreProposalTool(BaseTool):
    name: str = "smartwallet_vote_on_core_proposal"
    description: str = (
        "Vote on a core proposal through a smart wallet. "
        "Returns the transaction ID of the vote transaction."
    )
    args_schema: Type[BaseModel] = SmartWalletVoteOnCoreProposalInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        smart_wallet_contract: str,
        dao_core_proposals_extension_contract: str,
        dao_proposal_contract: str,
        vote: bool,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to vote on a core proposal."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            smart_wallet_contract,
            dao_core_proposals_extension_contract,
            dao_proposal_contract,
            str(vote).lower(),
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/smart-wallet/public",
            "vote-on-core-proposal.ts",
            *args,
        )

    def _run(
        self,
        smart_wallet_contract: str,
        dao_core_proposals_extension_contract: str,
        dao_proposal_contract: str,
        vote: bool,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to vote on a core proposal."""
        return self._deploy(
            smart_wallet_contract,
            dao_core_proposals_extension_contract,
            dao_proposal_contract,
            vote,
            **kwargs,
        )

    async def _arun(
        self,
        smart_wallet_contract: str,
        dao_core_proposals_extension_contract: str,
        dao_proposal_contract: str,
        vote: bool,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            smart_wallet_contract,
            dao_core_proposals_extension_contract,
            dao_proposal_contract,
            vote,
            **kwargs,
        )


class SmartWalletConcludeActionProposalInput(BaseModel):
    """Input schema for concluding an action proposal through a smart wallet."""

    smart_wallet_contract: str = Field(
        ...,
        description="Contract principal of the smart wallet",
        example="ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM.aibtc-user-agent-smart-wallet",
    )
    dao_action_proposals_extension_contract: str = Field(
        ...,
        description="Contract principal of the DAO action proposals extension",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-action-proposals-v2",
    )
    proposal_id: int = Field(
        ...,
        description="ID of the action proposal",
        example=1,
        gt=0,
    )


class SmartWalletConcludeActionProposalTool(BaseTool):
    name: str = "smartwallet_conclude_action_proposal"
    description: str = (
        "Conclude an action proposal through a smart wallet. "
        "Returns the transaction ID of the conclusion transaction."
    )
    args_schema: Type[BaseModel] = SmartWalletConcludeActionProposalInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        smart_wallet_contract: str,
        dao_action_proposals_extension_contract: str,
        proposal_id: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to conclude an action proposal."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            smart_wallet_contract,
            dao_action_proposals_extension_contract,
            str(proposal_id),
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/smart-wallet/public",
            "conclude-action-proposal.ts",
            *args,
        )

    def _run(
        self,
        smart_wallet_contract: str,
        dao_action_proposals_extension_contract: str,
        proposal_id: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to conclude an action proposal."""
        return self._deploy(
            smart_wallet_contract,
            dao_action_proposals_extension_contract,
            proposal_id,
            **kwargs,
        )

    async def _arun(
        self,
        smart_wallet_contract: str,
        dao_action_proposals_extension_contract: str,
        proposal_id: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            smart_wallet_contract,
            dao_action_proposals_extension_contract,
            proposal_id,
            **kwargs,
        )


class SmartWalletConcludeCoreProposalInput(BaseModel):
    """Input schema for concluding a core proposal through a smart wallet."""

    smart_wallet_contract: str = Field(
        ...,
        description="Contract principal of the smart wallet",
        example="ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM.aibtc-user-agent-smart-wallet",
    )
    dao_core_proposals_extension_contract: str = Field(
        ...,
        description="Contract principal of the DAO core proposals extension",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-core-proposals-v2",
    )
    dao_proposal_contract: str = Field(
        ...,
        description="Contract principal of the DAO proposal",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-onchain-messaging-send",
    )


class SmartWalletConcludeCoreProposalTool(BaseTool):
    name: str = "smartwallet_conclude_core_proposal"
    description: str = (
        "Conclude a core proposal through a smart wallet. "
        "Returns the transaction ID of the conclusion transaction."
    )
    args_schema: Type[BaseModel] = SmartWalletConcludeCoreProposalInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        smart_wallet_contract: str,
        dao_core_proposals_extension_contract: str,
        dao_proposal_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to conclude a core proposal."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            smart_wallet_contract,
            dao_core_proposals_extension_contract,
            dao_proposal_contract,
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/smart-wallet/public",
            "conclude-core-proposal.ts",
            *args,
        )

    def _run(
        self,
        smart_wallet_contract: str,
        dao_core_proposals_extension_contract: str,
        dao_proposal_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to conclude a core proposal."""
        return self._deploy(
            smart_wallet_contract,
            dao_core_proposals_extension_contract,
            dao_proposal_contract,
            **kwargs,
        )

    async def _arun(
        self,
        smart_wallet_contract: str,
        dao_core_proposals_extension_contract: str,
        dao_proposal_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            smart_wallet_contract,
            dao_core_proposals_extension_contract,
            dao_proposal_contract,
            **kwargs,
        )


class SmartWalletProxyProposeActionAddResourceInput(BaseModel):
    """Input schema for proposing an action to add a resource through a smart wallet."""

    smart_wallet_contract: str = Field(
        ...,
        description="Contract principal of the smart wallet",
        example="ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM.aibtc-user-agent-smart-wallet",
    )
    dao_action_proposals_extension_contract: str = Field(
        ...,
        description="Contract principal of the DAO action proposals extension",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-action-proposals-v2",
    )
    dao_action_proposal_contract: str = Field(
        ...,
        description="Contract principal of the DAO action proposal",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-onchain-messaging-send",
    )
    dao_token_contract: str = Field(
        ...,
        description="Contract principal of the DAO token",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-token",
    )
    resource_name: str = Field(
        ...,
        description="Name of the resource to add",
        example="my-resource",
    )
    resource_contract: str = Field(
        ...,
        description="Contract principal of the resource",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.my-resource",
    )


class SmartWalletProxyProposeActionAddResourceTool(BaseTool):
    name: str = "smartwallet_proxy_propose_action_add_resource"
    description: str = (
        "Propose an action to add a resource through a smart wallet. "
        "Returns the transaction ID of the proposal transaction."
    )
    args_schema: Type[BaseModel] = SmartWalletProxyProposeActionAddResourceInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        smart_wallet_contract: str,
        dao_action_proposals_extension_contract: str,
        dao_action_proposal_contract: str,
        dao_token_contract: str,
        resource_name: str,
        resource_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose an action to add a resource."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            smart_wallet_contract,
            dao_action_proposals_extension_contract,
            dao_action_proposal_contract,
            dao_token_contract,
            resource_name,
            resource_contract,
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/smart-wallet/public",
            "proxy-propose-action-add-resource.ts",
            *args,
        )

    def _run(
        self,
        smart_wallet_contract: str,
        dao_action_proposals_extension_contract: str,
        dao_action_proposal_contract: str,
        dao_token_contract: str,
        resource_name: str,
        resource_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose an action to add a resource."""
        return self._deploy(
            smart_wallet_contract,
            dao_action_proposals_extension_contract,
            dao_action_proposal_contract,
            dao_token_contract,
            resource_name,
            resource_contract,
            **kwargs,
        )

    async def _arun(
        self,
        smart_wallet_contract: str,
        dao_action_proposals_extension_contract: str,
        dao_action_proposal_contract: str,
        dao_token_contract: str,
        resource_name: str,
        resource_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            smart_wallet_contract,
            dao_action_proposals_extension_contract,
            dao_action_proposal_contract,
            dao_token_contract,
            resource_name,
            resource_contract,
            **kwargs,
        )


class SmartWalletProxyProposeActionAllowAssetInput(BaseModel):
    """Input schema for proposing an action to allow an asset through a smart wallet."""

    smart_wallet_contract: str = Field(
        ...,
        description="Contract principal of the smart wallet",
        example="ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM.aibtc-user-agent-smart-wallet",
    )
    dao_action_proposals_extension_contract: str = Field(
        ...,
        description="Contract principal of the DAO action proposals extension",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-action-proposals-v2",
    )
    dao_action_proposal_contract: str = Field(
        ...,
        description="Contract principal of the DAO action proposal",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-onchain-messaging-send",
    )
    dao_token_contract: str = Field(
        ...,
        description="Contract principal of the DAO token",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-token",
    )
    asset_contract: str = Field(
        ...,
        description="Contract principal of the asset",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.my-asset",
    )


class SmartWalletProxyProposeActionAllowAssetTool(BaseTool):
    name: str = "smartwallet_proxy_propose_action_allow_asset"
    description: str = (
        "Propose an action to allow an asset through a smart wallet. "
        "Returns the transaction ID of the proposal transaction."
    )
    args_schema: Type[BaseModel] = SmartWalletProxyProposeActionAllowAssetInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        smart_wallet_contract: str,
        dao_action_proposals_extension_contract: str,
        dao_action_proposal_contract: str,
        dao_token_contract: str,
        asset_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose an action to allow an asset."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            smart_wallet_contract,
            dao_action_proposals_extension_contract,
            dao_action_proposal_contract,
            dao_token_contract,
            asset_contract,
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/smart-wallet/public",
            "proxy-propose-action-allow-asset.ts",
            *args,
        )

    def _run(
        self,
        smart_wallet_contract: str,
        dao_action_proposals_extension_contract: str,
        dao_action_proposal_contract: str,
        dao_token_contract: str,
        asset_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose an action to allow an asset."""
        return self._deploy(
            smart_wallet_contract,
            dao_action_proposals_extension_contract,
            dao_action_proposal_contract,
            dao_token_contract,
            asset_contract,
            **kwargs,
        )

    async def _arun(
        self,
        smart_wallet_contract: str,
        dao_action_proposals_extension_contract: str,
        dao_action_proposal_contract: str,
        dao_token_contract: str,
        asset_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            smart_wallet_contract,
            dao_action_proposals_extension_contract,
            dao_action_proposal_contract,
            dao_token_contract,
            asset_contract,
            **kwargs,
        )


class SmartWalletProxyProposeActionToggleResourceByNameInput(BaseModel):
    """Input schema for proposing an action to toggle a resource by name through a smart wallet."""

    smart_wallet_contract: str = Field(
        ...,
        description="Contract principal of the smart wallet",
        example="ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM.aibtc-user-agent-smart-wallet",
    )
    dao_action_proposals_extension_contract: str = Field(
        ...,
        description="Contract principal of the DAO action proposals extension",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-action-proposals-v2",
    )
    dao_action_proposal_contract: str = Field(
        ...,
        description="Contract principal of the DAO action proposal",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-onchain-messaging-send",
    )
    dao_token_contract: str = Field(
        ...,
        description="Contract principal of the DAO token",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-token",
    )
    resource_name: str = Field(
        ...,
        description="Name of the resource to toggle",
        example="my-resource",
    )


class SmartWalletProxyProposeActionToggleResourceByNameTool(BaseTool):
    name: str = "smartwallet_proxy_propose_action_toggle_resource_by_name"
    description: str = (
        "Propose an action to toggle a resource by name through a smart wallet. "
        "Returns the transaction ID of the proposal transaction."
    )
    args_schema: Type[BaseModel] = (
        SmartWalletProxyProposeActionToggleResourceByNameInput
    )
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        smart_wallet_contract: str,
        dao_action_proposals_extension_contract: str,
        dao_action_proposal_contract: str,
        dao_token_contract: str,
        resource_name: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose an action to toggle a resource by name."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            smart_wallet_contract,
            dao_action_proposals_extension_contract,
            dao_action_proposal_contract,
            dao_token_contract,
            resource_name,
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/smart-wallet/public",
            "proxy-propose-action-toggle-resource-by-name.ts",
            *args,
        )

    def _run(
        self,
        smart_wallet_contract: str,
        dao_action_proposals_extension_contract: str,
        dao_action_proposal_contract: str,
        dao_token_contract: str,
        resource_name: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose an action to toggle a resource by name."""
        return self._deploy(
            smart_wallet_contract,
            dao_action_proposals_extension_contract,
            dao_action_proposal_contract,
            dao_token_contract,
            resource_name,
            **kwargs,
        )

    async def _arun(
        self,
        smart_wallet_contract: str,
        dao_action_proposals_extension_contract: str,
        dao_action_proposal_contract: str,
        dao_token_contract: str,
        resource_name: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            smart_wallet_contract,
            dao_action_proposals_extension_contract,
            dao_action_proposal_contract,
            dao_token_contract,
            resource_name,
            **kwargs,
        )


class SmartWalletProxyProposeActionSetAccountHolderInput(BaseModel):
    """Input schema for proposing an action to set the account holder through a smart wallet."""

    smart_wallet_contract: str = Field(
        ...,
        description="Contract principal of the smart wallet",
        example="ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM.aibtc-user-agent-smart-wallet",
    )
    dao_action_proposals_extension_contract: str = Field(
        ...,
        description="Contract principal of the DAO action proposals extension",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-action-proposals-v2",
    )
    dao_action_proposal_contract: str = Field(
        ...,
        description="Contract principal of the DAO action proposal",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-onchain-messaging-send",
    )
    dao_token_contract: str = Field(
        ...,
        description="Contract principal of the DAO token",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-token",
    )
    account_holder: str = Field(
        ...,
        description="Principal of the new account holder",
        example="ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM",
    )


class SmartWalletProxyProposeActionSetAccountHolderTool(BaseTool):
    name: str = "smartwallet_proxy_propose_action_set_account_holder"
    description: str = (
        "Propose an action to set the account holder through a smart wallet. "
        "Returns the transaction ID of the proposal transaction."
    )
    args_schema: Type[BaseModel] = SmartWalletProxyProposeActionSetAccountHolderInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        smart_wallet_contract: str,
        dao_action_proposals_extension_contract: str,
        dao_action_proposal_contract: str,
        dao_token_contract: str,
        account_holder: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose an action to set the account holder."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            smart_wallet_contract,
            dao_action_proposals_extension_contract,
            dao_action_proposal_contract,
            dao_token_contract,
            account_holder,
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/smart-wallet/public",
            "proxy-propose-action-set-account-holder.ts",
            *args,
        )

    def _run(
        self,
        smart_wallet_contract: str,
        dao_action_proposals_extension_contract: str,
        dao_action_proposal_contract: str,
        dao_token_contract: str,
        account_holder: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose an action to set the account holder."""
        return self._deploy(
            smart_wallet_contract,
            dao_action_proposals_extension_contract,
            dao_action_proposal_contract,
            dao_token_contract,
            account_holder,
            **kwargs,
        )

    async def _arun(
        self,
        smart_wallet_contract: str,
        dao_action_proposals_extension_contract: str,
        dao_action_proposal_contract: str,
        dao_token_contract: str,
        account_holder: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            smart_wallet_contract,
            dao_action_proposals_extension_contract,
            dao_action_proposal_contract,
            dao_token_contract,
            account_holder,
            **kwargs,
        )


class SmartWalletProxyProposeActionSetWithdrawalAmountInput(BaseModel):
    """Input schema for proposing an action to set the withdrawal amount through a smart wallet."""

    smart_wallet_contract: str = Field(
        ...,
        description="Contract principal of the smart wallet",
        example="ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM.aibtc-user-agent-smart-wallet",
    )
    dao_action_proposals_extension_contract: str = Field(
        ...,
        description="Contract principal of the DAO action proposals extension",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-action-proposals-v2",
    )
    dao_action_proposal_contract: str = Field(
        ...,
        description="Contract principal of the DAO action proposal",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-onchain-messaging-send",
    )
    dao_token_contract: str = Field(
        ...,
        description="Contract principal of the DAO token",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-token",
    )
    withdrawal_amount: int = Field(
        ...,
        description="New withdrawal amount in micro-STX",
        example=1000000,
        gt=0,
    )


class SmartWalletProxyProposeActionSetWithdrawalAmountTool(BaseTool):
    name: str = "smartwallet_proxy_propose_action_set_withdrawal_amount"
    description: str = (
        "Propose an action to set the withdrawal amount through a smart wallet. "
        "Returns the transaction ID of the proposal transaction."
    )
    args_schema: Type[BaseModel] = SmartWalletProxyProposeActionSetWithdrawalAmountInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        smart_wallet_contract: str,
        dao_action_proposals_extension_contract: str,
        dao_action_proposal_contract: str,
        dao_token_contract: str,
        withdrawal_amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose an action to set the withdrawal amount."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            smart_wallet_contract,
            dao_action_proposals_extension_contract,
            dao_action_proposal_contract,
            dao_token_contract,
            str(withdrawal_amount),
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/smart-wallet/public",
            "proxy-propose-action-set-withdrawal-amount.ts",
            *args,
        )

    def _run(
        self,
        smart_wallet_contract: str,
        dao_action_proposals_extension_contract: str,
        dao_action_proposal_contract: str,
        dao_token_contract: str,
        withdrawal_amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose an action to set the withdrawal amount."""
        return self._deploy(
            smart_wallet_contract,
            dao_action_proposals_extension_contract,
            dao_action_proposal_contract,
            dao_token_contract,
            withdrawal_amount,
            **kwargs,
        )

    async def _arun(
        self,
        smart_wallet_contract: str,
        dao_action_proposals_extension_contract: str,
        dao_action_proposal_contract: str,
        dao_token_contract: str,
        withdrawal_amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            smart_wallet_contract,
            dao_action_proposals_extension_contract,
            dao_action_proposal_contract,
            dao_token_contract,
            withdrawal_amount,
            **kwargs,
        )


class SmartWalletProxyProposeActionSetWithdrawalPeriodInput(BaseModel):
    """Input schema for proposing an action to set the withdrawal period through a smart wallet."""

    smart_wallet_contract: str = Field(
        ...,
        description="Contract principal of the smart wallet",
        example="ST1PQHQKV0RJXZFY1DGX8MNSNYVE3VGZJSRTPGZGM.aibtc-user-agent-smart-wallet",
    )
    dao_action_proposals_extension_contract: str = Field(
        ...,
        description="Contract principal of the DAO action proposals extension",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-action-proposals-v2",
    )
    dao_action_proposal_contract: str = Field(
        ...,
        description="Contract principal of the DAO action proposal",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-onchain-messaging-send",
    )
    dao_token_contract: str = Field(
        ...,
        description="Contract principal of the DAO token",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-token",
    )
    withdrawal_period: int = Field(
        ...,
        description="New withdrawal period in blocks",
        example=144,
        gt=0,
    )


class SmartWalletProxyProposeActionSetWithdrawalPeriodTool(BaseTool):
    name: str = "smartwallet_proxy_propose_action_set_withdrawal_period"
    description: str = (
        "Propose an action to set the withdrawal period through a smart wallet. "
        "Returns the transaction ID of the proposal transaction."
    )
    args_schema: Type[BaseModel] = SmartWalletProxyProposeActionSetWithdrawalPeriodInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        smart_wallet_contract: str,
        dao_action_proposals_extension_contract: str,
        dao_action_proposal_contract: str,
        dao_token_contract: str,
        withdrawal_period: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose an action to set the withdrawal period."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            smart_wallet_contract,
            dao_action_proposals_extension_contract,
            dao_action_proposal_contract,
            dao_token_contract,
            str(withdrawal_period),
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/smart-wallet/public",
            "proxy-propose-action-set-withdrawal-period.ts",
            *args,
        )

    def _run(
        self,
        smart_wallet_contract: str,
        dao_action_proposals_extension_contract: str,
        dao_action_proposal_contract: str,
        dao_token_contract: str,
        withdrawal_period: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to propose an action to set the withdrawal period."""
        return self._deploy(
            smart_wallet_contract,
            dao_action_proposals_extension_contract,
            dao_action_proposal_contract,
            dao_token_contract,
            withdrawal_period,
            **kwargs,
        )

    async def _arun(
        self,
        smart_wallet_contract: str,
        dao_action_proposals_extension_contract: str,
        dao_action_proposal_contract: str,
        dao_token_contract: str,
        withdrawal_period: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            smart_wallet_contract,
            dao_action_proposals_extension_contract,
            dao_action_proposal_contract,
            dao_token_contract,
            withdrawal_period,
            **kwargs,
        )


class SmartWalletDepositSTXInput(BaseModel):
    """Input schema for depositing STX to a smart wallet."""

    smart_wallet_contract: str = Field(
        ...,
        description="Contract principal of the smart wallet",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-smart-wallet-ST3YT-S5D18",
    )
    amount: int = Field(..., description="Amount of STX to deposit in microstacks")


class SmartWalletDepositSTXTool(BaseTool):
    name: str = "smartwallet_deposit_stx"
    description: str = (
        "Deposit STX into a smart wallet. "
        "The amount should be specified in microstacks (1 STX = 1,000,000 microstacks)."
    )
    args_schema: Type[BaseModel] = SmartWalletDepositSTXInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        smart_wallet_contract: str,
        amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to deposit STX to a smart wallet."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [smart_wallet_contract, str(amount)]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/smart-wallet/public",
            "deposit-stx.ts",
            *args,
        )

    def _run(
        self,
        smart_wallet_contract: str,
        amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to deposit STX to a smart wallet."""
        return self._deploy(smart_wallet_contract, amount, **kwargs)

    async def _arun(
        self,
        smart_wallet_contract: str,
        amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool to deposit STX to a smart wallet."""
        return self._deploy(smart_wallet_contract, amount, **kwargs)


class SmartWalletDepositFTInput(BaseModel):
    """Input schema for depositing fungible tokens to a smart wallet."""

    smart_wallet_contract: str = Field(
        ...,
        description="Contract principal of the smart wallet",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-smart-wallet-ST3YT-S5D18",
    )
    ft_contract: str = Field(
        ...,
        description="Contract principal of the fungible token",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-token",
    )
    amount: int = Field(..., description="Amount of tokens to deposit")


class SmartWalletDepositFTTool(BaseTool):
    name: str = "smartwallet_deposit_ft"
    description: str = (
        "Deposit fungible tokens into a smart wallet. "
        "Requires the token contract principal and amount to deposit."
    )
    args_schema: Type[BaseModel] = SmartWalletDepositFTInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        smart_wallet_contract: str,
        ft_contract: str,
        amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to deposit fungible tokens."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [smart_wallet_contract, ft_contract, str(amount)]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/smart-wallet/public",
            "deposit-ft.ts",
            *args,
        )

    def _run(
        self,
        smart_wallet_contract: str,
        ft_contract: str,
        amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to deposit fungible tokens."""
        return self._deploy(smart_wallet_contract, ft_contract, amount, **kwargs)

    async def _arun(
        self,
        smart_wallet_contract: str,
        ft_contract: str,
        amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(smart_wallet_contract, ft_contract, amount, **kwargs)


class SmartWalletApproveAssetInput(BaseModel):
    """Input schema for approving an asset in a smart wallet."""

    smart_wallet_contract: str = Field(
        ...,
        description="Contract principal of the smart wallet",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-smart-wallet-ST3YT-S5D18",
    )
    asset_contract: str = Field(
        ...,
        description="Contract principal of the asset to approve",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-token",
    )


class SmartWalletApproveAssetTool(BaseTool):
    name: str = "smartwallet_approve_asset"
    description: str = (
        "Approve an asset for use with the smart wallet. "
        "This allows the smart wallet to interact with the specified asset contract."
    )
    args_schema: Type[BaseModel] = SmartWalletApproveAssetInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        smart_wallet_contract: str,
        asset_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to approve an asset."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [smart_wallet_contract, asset_contract]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/smart-wallet/public",
            "approve-asset.ts",
            *args,
        )

    def _run(
        self,
        smart_wallet_contract: str,
        asset_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to approve an asset."""
        return self._deploy(smart_wallet_contract, asset_contract, **kwargs)

    async def _arun(
        self,
        smart_wallet_contract: str,
        asset_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(smart_wallet_contract, asset_contract, **kwargs)


class SmartWalletRevokeAssetInput(BaseModel):
    """Input schema for revoking an asset from a smart wallet."""

    smart_wallet_contract: str = Field(
        ...,
        description="Contract principal of the smart wallet",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-smart-wallet-ST3YT-S5D18",
    )
    asset_contract: str = Field(
        ...,
        description="Contract principal of the asset to revoke",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-token",
    )


class SmartWalletRevokeAssetTool(BaseTool):
    name: str = "smartwallet_revoke_asset"
    description: str = (
        "Revoke an asset from the smart wallet. "
        "This prevents the smart wallet from interacting with the specified asset contract."
    )
    args_schema: Type[BaseModel] = SmartWalletRevokeAssetInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        smart_wallet_contract: str,
        asset_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to revoke an asset."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [smart_wallet_contract, asset_contract]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/smart-wallet/public",
            "revoke-asset.ts",
            *args,
        )

    def _run(
        self,
        smart_wallet_contract: str,
        asset_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to revoke an asset."""
        return self._deploy(smart_wallet_contract, asset_contract, **kwargs)

    async def _arun(
        self,
        smart_wallet_contract: str,
        asset_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(smart_wallet_contract, asset_contract, **kwargs)


class SmartWalletGetBalanceSTXInput(BaseModel):
    """Input schema for getting STX balance from a smart wallet."""

    smart_wallet_contract: str = Field(
        ...,
        description="Contract principal of the smart wallet",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-smart-wallet-ST3YT-S5D18",
    )


class SmartWalletGetBalanceSTXTool(BaseTool):
    name: str = "smartwallet_get_balance_stx"
    description: str = (
        "Get the STX balance from a smart wallet. Returns the current STX balance as a number."
    )
    args_schema: Type[BaseModel] = SmartWalletGetBalanceSTXInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        smart_wallet_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get STX balance."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [smart_wallet_contract]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/smart-wallet/read-only",
            "get-balance-stx.ts",
            *args,
        )

    def _run(
        self,
        smart_wallet_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get STX balance."""
        return self._deploy(smart_wallet_contract, **kwargs)

    async def _arun(
        self,
        smart_wallet_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(smart_wallet_contract, **kwargs)


class SmartWalletIsApprovedAssetInput(BaseModel):
    """Input schema for checking if an asset is approved in a smart wallet."""

    smart_wallet_contract: str = Field(
        ...,
        description="Contract principal of the smart wallet",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-smart-wallet-ST3YT-S5D18",
    )
    asset_contract: str = Field(
        ...,
        description="Contract principal of the asset to check",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-faktory",
    )


class SmartWalletIsApprovedAssetTool(BaseTool):
    name: str = "smartwallet_is_approved_asset"
    description: str = (
        "Check if a specific asset is approved in the smart wallet. "
        "Returns true if the asset is approved, false if not."
    )
    args_schema: Type[BaseModel] = SmartWalletIsApprovedAssetInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        smart_wallet_contract: str,
        asset_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to check if asset is approved."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [smart_wallet_contract, asset_contract]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/smart-wallet/read-only",
            "is-approved-asset.ts",
            *args,
        )

    def _run(
        self,
        smart_wallet_contract: str,
        asset_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to check if asset is approved."""
        return self._deploy(smart_wallet_contract, asset_contract, **kwargs)

    async def _arun(
        self,
        smart_wallet_contract: str,
        asset_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(smart_wallet_contract, asset_contract, **kwargs)


class SmartWalletGetConfigurationInput(BaseModel):
    """Input schema for getting smart wallet configuration."""

    smart_wallet_contract: str = Field(
        ...,
        description="Contract principal of the smart wallet",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-smart-wallet-ST3YT-S5D18",
    )


class SmartWalletGetConfigurationTool(BaseTool):
    name: str = "smartwallet_get_configuration"
    description: str = (
        "Get the configuration of a smart wallet. "
        "Returns information about the agent, user, smart wallet, DAO token, and sBTC token."
    )
    args_schema: Type[BaseModel] = SmartWalletGetConfigurationInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        smart_wallet_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get smart wallet configuration."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [smart_wallet_contract]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/smart-wallet/read-only",
            "get-configuration.ts",
            *args,
        )

    def _run(
        self,
        smart_wallet_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get smart wallet configuration."""
        return self._deploy(smart_wallet_contract, **kwargs)

    async def _arun(
        self,
        smart_wallet_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(smart_wallet_contract, **kwargs)


class SmartWalletDeploySmartWalletInput(BaseModel):
    """Input schema for deploying a smart wallet."""

    owner_address: str = Field(
        ...,
        description="Stacks address of the wallet owner",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA",
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


class SmartWalletDeploySmartWalletTool(BaseTool):
    name: str = "smartwallet_deploy"
    description: str = (
        "Deploy a new smart wallet for a user. "
        "The smart wallet will be owned by the specified address and linked to the DAO token. "
        "Returns the deployed smart wallet contract address and transaction ID."
    )
    args_schema: Type[BaseModel] = SmartWalletDeploySmartWalletInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        owner_address: str,
        dao_token_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to deploy a smart wallet."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [owner_address, dao_token_contract]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao",
            "deploy-smart-wallet.ts",
            *args,
        )

    def _run(
        self,
        owner_address: str,
        dao_token_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to deploy a smart wallet."""
        return self._deploy(owner_address, dao_token_contract, **kwargs)

    async def _arun(
        self,
        owner_address: str,
        dao_token_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(owner_address, dao_token_contract, **kwargs)
