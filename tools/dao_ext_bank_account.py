from typing import Any, Dict, Optional, Type
from uuid import UUID

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from tools.bun import BunScriptRunner
from tools.dao_base import DAOToolResponse


class GetAccountTermsInput(BaseModel):
    """Input schema for getting bank account terms."""

    bank_account_contract: str = Field(
        ..., description="Contract ID of the bank account"
    )


class GetAccountTermsTool(BaseTool):
    name: str = "dao_bank_get_account_terms"
    description: str = (
        "Get the current terms of the DAO's bank account. "
        "Returns information about withdrawal limits, periods, and account holder."
    )
    args_schema: Type[BaseModel] = GetAccountTermsInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        bank_account_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get account terms."""
        if self.wallet_id is None:
            return DAOToolResponse.error_response("Wallet ID is required")

        args = [bank_account_contract]

        result = BunScriptRunner.bun_run(
            self.wallet_id, "bank-account", "get-account-terms.ts", *args
        )

        if not result["success"]:
            return DAOToolResponse.error_response(
                result.get("error", "Unknown error"), result.get("output")
            )

        return DAOToolResponse.success_response(
            "Successfully retrieved account terms", result.get("output")
        )

    def _run(
        self,
        bank_account_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get account terms."""
        return self._deploy(bank_account_contract, **kwargs)

    async def _arun(
        self,
        bank_account_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(bank_account_contract, **kwargs)


class DepositSTXInput(BaseModel):
    """Input schema for depositing STX."""

    bank_account_contract: str = Field(
        ..., description="Contract ID of the bank account"
    )
    amount: int = Field(..., description="Amount of STX to deposit in microstacks")


class DepositSTXTool(BaseTool):
    name: str = "dao_bank_deposit_stx"
    description: str = (
        "Deposit STX into the DAO's bank account. "
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
        bank_account_contract: str,
        amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to deposit STX."""
        if self.wallet_id is None:
            return DAOToolResponse.error_response("Wallet ID is required")

        args = [
            bank_account_contract,
            str(amount),
        ]

        result = BunScriptRunner.bun_run(
            self.wallet_id, "bank-account", "deposit-stx.ts", *args
        )

        if not result["success"]:
            return DAOToolResponse.error_response(
                result.get("error", "Unknown error"), result.get("output")
            )

        return DAOToolResponse.success_response(
            "Successfully deposited STX", result.get("output")
        )

    def _run(
        self,
        bank_account_contract: str,
        amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to deposit STX."""
        return self._deploy(bank_account_contract, amount, **kwargs)

    async def _arun(
        self,
        bank_account_contract: str,
        amount: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(bank_account_contract, amount, **kwargs)


class WithdrawSTXInput(BaseModel):
    """Input schema for withdrawing STX."""

    bank_account_contract: str = Field(
        ..., description="Contract ID of the bank account"
    )


class WithdrawSTXTool(BaseTool):
    name: str = "dao_bank_withdraw_stx"
    description: str = (
        "Withdraw STX from the DAO's bank account. "
        "This will withdraw the maximum allowed amount based on the account terms."
    )
    args_schema: Type[BaseModel] = WithdrawSTXInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        bank_account_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to withdraw STX."""
        if self.wallet_id is None:
            return DAOToolResponse.error_response("Wallet ID is required")

        args = [bank_account_contract]

        result = BunScriptRunner.bun_run(
            self.wallet_id, "bank-account", "withdraw-stx.ts", *args
        )

        if not result["success"]:
            return DAOToolResponse.error_response(
                result.get("error", "Unknown error"), result.get("output")
            )

        return DAOToolResponse.success_response(
            "Successfully withdrew STX", result.get("output")
        )

    def _run(
        self,
        bank_account_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to withdraw STX."""
        return self._deploy(bank_account_contract, **kwargs)

    async def _arun(
        self,
        bank_account_contract: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(bank_account_contract, **kwargs)
