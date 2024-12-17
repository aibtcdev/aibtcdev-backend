from .bun import BunScriptRunner
from crewai_tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type


class StacksTransactionStatusToolSchema(BaseModel):
    """Input schema for StacksTransactionStatusTool."""

    transaction_id: str = Field(
        ..., description="The ID of the transaction to check the status for."
    )


class StacksTransactionStatusTool(BaseTool):
    name: str = "Get transaction status"
    description: str = "Get the status of a transaction using its ID."
    args_schema: Type[BaseModel] = StacksTransactionStatusToolSchema

    def _run(self, transaction_id: str) -> dict:
        try:
            result = BunScriptRunner.bun_run(
                "0", "stacks-transactions", "get-transaction-status.ts", transaction_id
            )
            return result
        except Exception as e:
            return {"output": None, "error": str(e), "success": False}


class StacksTransactionToolSchema(BaseModel):
    """Input schema for StacksTransactionTool."""

    transaction_id: str = Field(
        ...,
        description="The ID of the transaction to retrieve detailed information for.",
    )


class StacksTransactionTool(BaseTool):
    name: str = "Get transaction details"
    description: str = "Retrieve detailed information about a transaction using its ID."
    args_schema: Type[BaseModel] = StacksTransactionToolSchema

    def _run(self, transaction_id: str) -> dict:
        try:
            result = BunScriptRunner.bun_run(
                "0", "stacks-transactions", "get-transaction.ts", transaction_id
            )
            return result
        except Exception as e:
            return {"output": None, "error": str(e), "success": False}


class StacksTransactionByAddressToolSchema(BaseModel):
    """Input schema for StacksTransactionByAddressTool."""

    address: str = Field(..., description="The address to retrieve transactions for.")


class StacksTransactionByAddressTool(BaseTool):
    name: str = "Get transactions by address"
    description: str = "Retrieve transactions associated with a given address."
    args_schema: Type[BaseModel] = StacksTransactionByAddressToolSchema

    def _run(self, address: str) -> dict:
        try:
            result = BunScriptRunner.bun_run(
                "0", "stacks-transactions", "get-transactions-by-address.ts", address
            )
            return result
        except Exception as e:
            return {"output": None, "error": str(e), "success": False}
