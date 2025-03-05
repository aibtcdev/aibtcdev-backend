from typing import Any, Dict, Optional, Type
from uuid import UUID

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from tools.bun import BunScriptRunner


class IsExtensionInput(BaseModel):
    """Input schema for checking if a contract is an extension."""

    base_dao_contract: str = Field(
        ...,
        description="Contract principal of the base DAO",
        example="ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-base-dao",
    )
    extension_contract: str = Field(
        ...,
        description="Contract principal of the extension to check",
        example="ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-dao-charter",
    )


class IsExtensionTool(BaseTool):
    name: str = "dao_is_extension"
    description: str = (
        "Check if a given contract is an extension of the base DAO. "
        "Returns true if the contract is a registered extension, false otherwise."
    )
    args_schema: Type[BaseModel] = IsExtensionInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        base_dao_contract: str,
        extension_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to check extension status."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            base_dao_contract,
            extension_contract,
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id, "aibtc-dao/base-dao/read-only", "is-extension.ts", *args
        )

    def _run(
        self,
        base_dao_contract: str,
        extension_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to check extension status."""
        return self._deploy(base_dao_contract, extension_contract, **kwargs)

    async def _arun(
        self,
        base_dao_contract: str,
        extension_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(base_dao_contract, extension_contract, **kwargs)


class ExecutedAtInput(BaseModel):
    """Input schema for checking when a proposal was executed."""

    base_dao_contract: str = Field(
        ...,
        description="Contract principal of the base DAO",
        example="ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-base-dao",
    )
    proposal_contract: str = Field(
        ...,
        description="Contract principal of the proposal to check",
        example="ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-proposal",
    )


class ExecutedAtTool(BaseTool):
    name: str = "dao_executed_at"
    description: str = (
        "Check when a proposal was executed in the DAO. "
        "Returns the block height at which the proposal was executed, or null if not executed."
    )
    args_schema: Type[BaseModel] = ExecutedAtInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        base_dao_contract: str,
        proposal_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to check proposal execution block."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            base_dao_contract,
            proposal_contract,
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id, "aibtc-dao/base-dao/read-only", "executed-at.ts", *args
        )

    def _run(
        self,
        base_dao_contract: str,
        proposal_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to check proposal execution block."""
        return self._deploy(base_dao_contract, proposal_contract, **kwargs)

    async def _arun(
        self,
        base_dao_contract: str,
        proposal_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(base_dao_contract, proposal_contract, **kwargs)
