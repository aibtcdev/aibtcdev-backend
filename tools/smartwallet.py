from typing import Any, Dict, Optional, Type
from uuid import UUID

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from tools.bun import BunScriptRunner


class GetBalanceSTXInput(BaseModel):
    """Input schema for getting STX balance from a smart wallet."""

    smart_wallet_contract: str = Field(
        ...,
        description="Contract principal of the smart wallet",
        example="ST35K818S3K2GSNEBC3M35GA3W8Q7X72KF4RVM3QA.aibtc-smart-wallet-ST3YT-S5D18",
    )


class GetBalanceSTXTool(BaseTool):
    name: str = "smartwallet_get_balance_stx"
    description: str = (
        "Get the STX balance from a smart wallet. "
        "Returns the current STX balance as a number."
    )
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
