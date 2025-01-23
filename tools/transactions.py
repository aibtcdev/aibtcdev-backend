from .bun import BunScriptRunner
from backend.models import UUID
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional, Type


class StacksTransactionStatusInput(BaseModel):
    """Input schema for checking Stacks transaction status."""

    transaction_id: str = Field(
        ..., description="The ID of the transaction to check the status for."
    )


class StacksTransactionStatusTool(BaseTool):
    name: str = "stacks_transaction_status"
    description: str = (
        "Get the current status of a Stacks blockchain transaction using its ID. "
        "Returns success status and transaction details if available."
    )
    args_schema: Type[BaseModel] = StacksTransactionStatusInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(self, transaction_id: str, **kwargs) -> Dict[str, Any]:
        """Execute the tool to check transaction status."""
        if self.wallet_id is None:
            raise ValueError("Wallet ID is required")
        try:
            result = BunScriptRunner.bun_run(
                self.wallet_id,
                "stacks-transactions",
                "get-transaction-status.ts",
                transaction_id,
            )
            return result
        except Exception as e:
            return {"output": None, "error": str(e), "success": False}

    def _run(self, transaction_id: str, **kwargs) -> Dict[str, Any]:
        """Execute the tool to check transaction status."""
        return self._deploy(transaction_id, **kwargs)

    async def _arun(self, transaction_id: str, **kwargs) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(transaction_id, **kwargs)


class StacksTransactionInput(BaseModel):
    """Input schema for retrieving detailed Stacks transaction information."""

    transaction_id: str = Field(
        ...,
        description="The ID of the transaction to retrieve detailed information for.",
    )


class StacksTransactionTool(BaseTool):
    name: str = "stacks_transaction_details"
    description: str = (
        "Retrieve detailed information about a Stacks blockchain transaction using its ID. "
        "Returns transaction details including sender, recipient, amount, and status."
    )
    args_schema: Type[BaseModel] = StacksTransactionInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(self, transaction_id: str, **kwargs) -> Dict[str, Any]:
        """Execute the tool to get transaction details."""
        if self.wallet_id is None:
            raise ValueError("Wallet ID is required")
        try:
            result = BunScriptRunner.bun_run(
                self.wallet_id,
                "stacks-transactions",
                "get-transaction.ts",
                transaction_id,
            )
            return result
        except Exception as e:
            return {"output": None, "error": str(e), "success": False}

    def _run(self, transaction_id: str, **kwargs) -> Dict[str, Any]:
        """Execute the tool to get transaction details."""
        return self._deploy(transaction_id, **kwargs)

    async def _arun(self, transaction_id: str, **kwargs) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(transaction_id, **kwargs)


class StacksTransactionByAddressInput(BaseModel):
    """Input schema for retrieving transactions by Stacks address."""

    address: str = Field(..., description="The address to retrieve transactions for.")


class StacksTransactionByAddressTool(BaseTool):
    name: str = "stacks_transactions_by_address"
    description: str = (
        "Retrieve all transactions associated with a given address on the Stacks blockchain. "
        "Returns a list of transactions including their IDs, types, and timestamps."
    )
    args_schema: Type[BaseModel] = StacksTransactionByAddressInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(self, address: str, **kwargs) -> Dict[str, Any]:
        """Execute the tool to get transactions by address."""
        if self.wallet_id is None:
            raise ValueError("Wallet ID is required")
        try:
            result = BunScriptRunner.bun_run(
                self.wallet_id,
                "stacks-transactions",
                "get-transactions-by-address.ts",
                address,
            )
            return result
        except Exception as e:
            return {"output": None, "error": str(e), "success": False}

    def _run(self, address: str, **kwargs) -> Dict[str, Any]:
        """Execute the tool to get transactions by address."""
        return self._deploy(address, **kwargs)

    async def _arun(self, address: str, **kwargs) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(address, **kwargs)
