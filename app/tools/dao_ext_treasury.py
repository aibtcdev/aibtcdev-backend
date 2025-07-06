from typing import Any, Dict, Optional, Type
from uuid import UUID

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from app.tools.bun import BunScriptRunner


class GetAllowedAssetInput(BaseModel):
    """Input schema for checking if an asset is allowed."""

    treasury_contract: str = Field(
        ...,
        description="Contract principal of the treasury",
        examples=["ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-treasury"],
    )
    asset_contract: str = Field(
        ...,
        description="Contract principal of the asset to check",
        examples=["ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-asset"],
    )


class GetAllowedAssetTool(BaseTool):
    name: str = "dao_treasury_get_allowed_asset"
    description: str = (
        "Check if a specific asset is allowed in the DAO treasury. "
        "Returns true if the asset is allowed, false if not, or null if not found."
    )
    args_schema: Type[BaseModel] = GetAllowedAssetInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        treasury_contract: str,
        asset_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to check if asset is allowed."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [treasury_contract, asset_contract]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/extensions/treasury/read-only",
            "get-allowed-asset.ts",
            *args,
        )

    def _run(
        self,
        treasury_contract: str,
        asset_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to check if asset is allowed."""
        return self._deploy(treasury_contract, asset_contract, **kwargs)

    async def _arun(
        self,
        treasury_contract: str,
        asset_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(treasury_contract, asset_contract, **kwargs)


class IsAllowedAssetInput(BaseModel):
    """Input schema for checking if an asset is allowed."""

    treasury_contract: str = Field(
        ...,
        description="Contract principal of the treasury",
        examples=["ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-treasury"],
    )
    asset_contract: str = Field(
        ...,
        description="Contract principal of the asset to check",
        examples=["ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-asset"],
    )


class IsAllowedAssetTool(BaseTool):
    name: str = "dao_treasury_is_allowed_asset"
    description: str = (
        "Check if a specific asset is allowed in the DAO treasury. "
        "Returns true if the asset is allowed, false if not."
    )
    args_schema: Type[BaseModel] = IsAllowedAssetInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        treasury_contract: str,
        asset_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to check if asset is allowed."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [treasury_contract, asset_contract]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/extensions/treasury/read-only",
            "is-allowed-asset.ts",
            *args,
        )

    def _run(
        self,
        treasury_contract: str,
        asset_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to check if asset is allowed."""
        return self._deploy(treasury_contract, asset_contract, **kwargs)

    async def _arun(
        self,
        treasury_contract: str,
        asset_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(treasury_contract, asset_contract, **kwargs)
