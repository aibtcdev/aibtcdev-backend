from uuid import UUID
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
from tools.bun import BunScriptRunner
from typing import Dict, Optional, Type, Any

class GetCurrentDaoCharterInput(BaseModel):
    """Input schema for getting current DAO charter."""
    dao_charter_contract: str = Field(
        ..., 
        description="Contract ID of the DAO charter"
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
            return {
                "success": False,
                "error": "Wallet ID is required",
                "output": "",
            }

        args = [dao_charter_contract]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "dao-charter",
            "get-current-dao-charter.ts",
            *args
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
        description="Contract ID of the DAO charter"
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
            return {
                "success": False,
                "error": "Wallet ID is required",
                "output": "",
            }

        args = [dao_charter_contract]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "dao-charter",
            "get-current-dao-charter-version.ts",
            *args
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
        description="Contract ID of the DAO charter"
    )
    version: int = Field(
        ...,
        description="Version number of the charter to retrieve"
    )

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
            return {
                "success": False,
                "error": "Wallet ID is required",
                "output": "",
            }

        args = [
            dao_charter_contract,
            str(version)
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "dao-charter",
            "get-dao-charter.ts",
            *args
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
