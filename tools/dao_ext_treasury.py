from typing import Any, Dict, Optional, Type
from uuid import UUID

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from tools.bun import BunScriptRunner
from tools.dao_base import DAOToolResponse


class GetAllowedAssetInput(BaseModel):
    """Input schema for checking if an asset is allowed."""

    treasury_contract: str = Field(..., description="Contract ID of the treasury")
    asset_contract: str = Field(..., description="Contract ID of the asset to check")


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
            return DAOToolResponse.error_response("Wallet ID is required")

        args = [treasury_contract, asset_contract]

        result = BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/extensions/treasury/read-only",
            "get-allowed-asset.ts",
            *args,
        )

        if not result["success"]:
            return DAOToolResponse.error_response(
                result.get("error", "Unknown error"), result.get("output")
            )

        return DAOToolResponse.success_response(
            "Successfully processed treasury operation", result.get("output")
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

    treasury_contract: str = Field(..., description="Contract ID of the treasury")
    asset_contract: str = Field(..., description="Contract ID of the asset to check")


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
            return DAOToolResponse.error_response("Wallet ID is required")

        args = [treasury_contract, asset_contract]

        result = BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/extensions/treasury/read-only",
            "is-allowed-asset.ts",
            *args,
        )

        if not result["success"]:
            return DAOToolResponse.error_response(
                result.get("error", "Unknown error"), result.get("output")
            )

        return DAOToolResponse.success_response(
            "Successfully processed treasury operation", result.get("output")
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
