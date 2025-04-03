from typing import Any, Dict, Optional, Type
from uuid import UUID

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from tools.bun import BunScriptRunner


class DepositSTXInput(BaseModel):
    """Input schema for depositing STX to a smart wallet."""

    smart_wallet_contract: str = Field(
        ...,
        description="Contract principal of the smart wallet",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-smart-wallet-ST3YT-S5D18",
    )
    amount: int = Field(..., description="Amount of STX to deposit in microstacks")


class DepositSTXTool(BaseTool):
    name: str = "smartwallet_deposit_stx"
    description: str = (
        "Deposit STX into a smart wallet. "
        "The amount should be specified in microstacks (1 STX = 1,000,000 microstacks)."
    )
    args_schema: Type[BaseModel] = DepositSTXInput
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


class DepositFTInput(BaseModel):
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


class DepositFTTool(BaseTool):
    name: str = "smartwallet_deposit_ft"
    description: str = (
        "Deposit fungible tokens into a smart wallet. "
        "Requires the token contract principal and amount to deposit."
    )
    args_schema: Type[BaseModel] = DepositFTInput
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


class ApproveAssetInput(BaseModel):
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


class ApproveAssetTool(BaseTool):
    name: str = "smartwallet_approve_asset"
    description: str = (
        "Approve an asset for use with the smart wallet. "
        "This allows the smart wallet to interact with the specified asset contract."
    )
    args_schema: Type[BaseModel] = ApproveAssetInput
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


class RevokeAssetInput(BaseModel):
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


class RevokeAssetTool(BaseTool):
    name: str = "smartwallet_revoke_asset"
    description: str = (
        "Revoke an asset from the smart wallet. "
        "This prevents the smart wallet from interacting with the specified asset contract."
    )
    args_schema: Type[BaseModel] = RevokeAssetInput
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


class GetBalanceSTXInput(BaseModel):
    """Input schema for getting STX balance from a smart wallet."""

    smart_wallet_contract: str = Field(
        ...,
        description="Contract principal of the smart wallet",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-smart-wallet-ST3YT-S5D18",
    )


class GetBalanceSTXTool(BaseTool):
    name: str = "smartwallet_get_balance_stx"
    description: str = "Get the STX balance from a smart wallet. Returns the current STX balance as a number."
    args_schema: Type[BaseModel] = GetBalanceSTXInput
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


class IsApprovedAssetInput(BaseModel):
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


class IsApprovedAssetTool(BaseTool):
    name: str = "smartwallet_is_approved_asset"
    description: str = (
        "Check if a specific asset is approved in the smart wallet. "
        "Returns true if the asset is approved, false if not."
    )
    args_schema: Type[BaseModel] = IsApprovedAssetInput
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


class GetConfigurationInput(BaseModel):
    """Input schema for getting smart wallet configuration."""

    smart_wallet_contract: str = Field(
        ...,
        description="Contract principal of the smart wallet",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-smart-wallet-ST3YT-S5D18",
    )


class GetConfigurationTool(BaseTool):
    name: str = "smartwallet_get_configuration"
    description: str = (
        "Get the configuration of a smart wallet. "
        "Returns information about the agent, user, smart wallet, DAO token, and sBTC token."
    )
    args_schema: Type[BaseModel] = GetConfigurationInput
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


class DeploySmartWalletInput(BaseModel):
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


class DeploySmartWalletTool(BaseTool):
    name: str = "smartwallet_deploy"
    description: str = (
        "Deploy a new smart wallet for a user. "
        "The smart wallet will be owned by the specified address and linked to the DAO token. "
        "Returns the deployed smart wallet contract address and transaction ID."
    )
    args_schema: Type[BaseModel] = DeploySmartWalletInput
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
