from uuid import UUID
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
from tools.bun import BunScriptRunner
from typing import Dict, Optional, Type, Any

class IsExtensionInput(BaseModel):
    """Input schema for checking if a contract is an extension."""
    base_dao_contract: str = Field(
        ..., 
        description="Contract ID of the base DAO"
    )
    extension_contract: str = Field(
        ..., 
        description="Contract ID to check if it's an extension"
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
            return {
                "success": False,
                "error": "Wallet ID is required",
                "output": "",
            }

        args = [
            base_dao_contract,
            extension_contract,
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "base-dao",
            "is-extension.ts",
            *args
        )

    def _run(
        self,
        base_dao_contract: str,
        extension_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to check extension status."""
        return self._deploy(
            base_dao_contract,
            extension_contract,
            **kwargs
        )

    async def _arun(
        self,
        base_dao_contract: str,
        extension_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            base_dao_contract,
            extension_contract,
            **kwargs
        )

class ExecutedAtInput(BaseModel):
    """Input schema for checking when a proposal was executed."""
    base_dao_contract: str = Field(
        ..., 
        description="Contract ID of the base DAO"
    )
    proposal_contract: str = Field(
        ..., 
        description="Contract ID of the proposal to check"
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
            return {
                "success": False,
                "error": "Wallet ID is required",
                "output": "",
            }

        args = [
            base_dao_contract,
            proposal_contract,
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "base-dao",
            "executed-at.ts",
            *args
        )

    def _run(
        self,
        base_dao_contract: str,
        proposal_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to check proposal execution block."""
        return self._deploy(
            base_dao_contract,
            proposal_contract,
            **kwargs
        )

    async def _arun(
        self,
        base_dao_contract: str,
        proposal_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(
            base_dao_contract,
            proposal_contract,
            **kwargs
        )
