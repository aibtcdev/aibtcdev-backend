from typing import Any, Dict, Optional, Type
from uuid import UUID

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from tools.bun import BunScriptRunner
from tools.dao_base import DAOToolResponse


class GetCurrentDaoCharterInput(BaseModel):
    """Input schema for getting current DAO charter."""

    dao_charter_contract: str = Field(
        ...,
        description="Contract principal of the DAO charter",
        example="ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-dao-charter",
    )


class GetCurrentDaoCharterTool(BaseTool):
    name: str = "dao_get_current_charter"
    description: str = (
        "Get the current version of the DAO charter. "
        "Returns the full text of the current charter if one exists."
    )
    args_schema: Type[BaseModel] = GetCurrentDaoCharterInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        dao_charter_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get current charter."""
        if self.wallet_id is None:
            return DAOToolResponse.error_response("Wallet ID is required")

        args = [dao_charter_contract]

        result = BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/extensions/dao-charter/read-only",
            "get-current-dao-charter.ts",
            *args,
        )

        if not result["success"]:
            return DAOToolResponse.error_response(
                result.get("error", "Unknown error"), result.get("output")
            )

        return DAOToolResponse.success_response(
            "Successfully retrieved charter", result.get("output")
        )

    def _run(
        self,
        dao_charter_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get current charter."""
        return self._deploy(dao_charter_contract, **kwargs)

    async def _arun(
        self,
        dao_charter_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(dao_charter_contract, **kwargs)


class GetCurrentDaoCharterVersionInput(BaseModel):
    """Input schema for getting current DAO charter version."""

    dao_charter_contract: str = Field(
        ...,
        description="Contract principal of the DAO charter",
        example="ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-dao-charter",
    )


class GetCurrentDaoCharterVersionTool(BaseTool):
    name: str = "dao_get_current_charter_version"
    description: str = (
        "Get the version number of the current DAO charter. "
        "Returns the version number if a charter exists."
    )
    args_schema: Type[BaseModel] = GetCurrentDaoCharterVersionInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        dao_charter_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get current charter version."""
        if self.wallet_id is None:
            return DAOToolResponse.error_response("Wallet ID is required")

        args = [dao_charter_contract]

        result = BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/extensions/dao-charter/read-only",
            "get-current-dao-charter-version.ts",
            *args,
        )

        if not result["success"]:
            return DAOToolResponse.error_response(
                result.get("error", "Unknown error"), result.get("output")
            )

        return DAOToolResponse.success_response(
            "Successfully retrieved charter version", result.get("output")
        )

    def _run(
        self,
        dao_charter_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get current charter version."""
        return self._deploy(dao_charter_contract, **kwargs)

    async def _arun(
        self,
        dao_charter_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(dao_charter_contract, **kwargs)


class GetDaoCharterInput(BaseModel):
    """Input schema for getting a specific DAO charter version."""

    dao_charter_contract: str = Field(
        ...,
        description="Contract principal of the DAO charter",
        example="ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-dao-charter",
    )
    version: int = Field(..., description="Version number of the charter to retrieve")


class GetDaoCharterTool(BaseTool):
    name: str = "dao_get_charter"
    description: str = (
        "Get a specific version of the DAO charter. "
        "Returns the full text of the requested charter version if it exists."
    )
    args_schema: Type[BaseModel] = GetDaoCharterInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        dao_charter_contract: str,
        version: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get specific charter version."""
        if self.wallet_id is None:
            return DAOToolResponse.error_response("Wallet ID is required")

        args = [dao_charter_contract, str(version)]

        result = BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/extensions/dao-charter/read-only",
            "get-dao-charter.ts",
            *args,
        )

        if not result["success"]:
            return DAOToolResponse.error_response(
                result.get("error", "Unknown error"), result.get("output")
            )

        return DAOToolResponse.success_response(
            "Successfully retrieved DAO charter version", result.get("output")
        )

    def _run(
        self,
        dao_charter_contract: str,
        version: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get specific charter version."""
        return self._deploy(dao_charter_contract, version, **kwargs)

    async def _arun(
        self,
        dao_charter_contract: str,
        version: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(dao_charter_contract, version, **kwargs)
