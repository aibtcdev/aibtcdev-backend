from typing import Any, Dict, Optional, Type
from uuid import UUID

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from tools.bun import BunScriptRunner
from tools.dao_base import DAOToolResponse


class GetInvoiceInput(BaseModel):
    """Input schema for getting invoice details."""

    payments_invoices_contract: str = Field(
        ...,
        description="Contract principal of the payments and invoices contract",
        example="ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-payments-invoices",
    )
    invoice_index: int = Field(..., description="Index of the invoice to retrieve")


class GetInvoiceTool(BaseTool):
    name: str = "dao_get_invoice"
    description: str = (
        "Get details of a specific invoice from the DAO's payments and invoices system. "
        "Returns the full invoice data if it exists."
    )
    args_schema: Type[BaseModel] = GetInvoiceInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        payments_invoices_contract: str,
        invoice_index: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get invoice details."""
        if self.wallet_id is None:
            return DAOToolResponse.error_response("Wallet ID is required")

        args = [payments_invoices_contract, str(invoice_index)]

        result = BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/extensions/payments-invoices/read-only",
            "get-invoice.ts",
            *args,
        )

        if not result["success"]:
            return DAOToolResponse.error_response(
                result.get("error", "Unknown error"), result.get("output")
            )

        return DAOToolResponse.success_response(
            "Successfully retrieved invoice details", result.get("output")
        )

    def _run(
        self,
        payments_invoices_contract: str,
        invoice_index: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get invoice details."""
        return self._deploy(payments_invoices_contract, invoice_index, **kwargs)

    async def _arun(
        self,
        payments_invoices_contract: str,
        invoice_index: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(payments_invoices_contract, invoice_index, **kwargs)


class GetResourceInput(BaseModel):
    """Input schema for getting resource details."""

    payments_invoices_contract: str = Field(
        ...,
        description="Contract principal of the payments and invoices contract",
        example="ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-payments-invoices",
    )
    resource_index: int = Field(..., description="Index of the resource to retrieve")


class GetResourceTool(BaseTool):
    name: str = "dao_get_resource"
    description: str = (
        "Get details of a specific resource from the DAO's payments and invoices system. "
        "Returns the full resource data if it exists."
    )
    args_schema: Type[BaseModel] = GetResourceInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        payments_invoices_contract: str,
        resource_index: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get resource details."""
        if self.wallet_id is None:
            return DAOToolResponse.error_response("Wallet ID is required")

        args = [payments_invoices_contract, str(resource_index)]

        result = BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/extensions/payments-invoices/read-only",
            "get-resource.ts",
            *args,
        )

        if not result["success"]:
            return DAOToolResponse.error_response(
                result.get("error", "Unknown error"), result.get("output")
            )

        return DAOToolResponse.success_response(
            "Successfully retrieved resource details", result.get("output")
        )

    def _run(
        self,
        payments_invoices_contract: str,
        resource_index: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get resource details."""
        return self._deploy(payments_invoices_contract, resource_index, **kwargs)

    async def _arun(
        self,
        payments_invoices_contract: str,
        resource_index: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(payments_invoices_contract, resource_index, **kwargs)


class GetResourceByNameInput(BaseModel):
    """Input schema for getting resource details by name."""

    payments_invoices_contract: str = Field(
        ...,
        description="Contract principal of the payments and invoices contract",
        example="ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-payments-invoices",
    )
    resource_name: str = Field(..., description="Name of the resource to retrieve")


class GetResourceByNameTool(BaseTool):
    name: str = "dao_get_resource_by_name"
    description: str = (
        "Get details of a specific resource by its name from the DAO's payments and invoices system. "
        "Returns the full resource data if it exists."
    )
    args_schema: Type[BaseModel] = GetResourceByNameInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        payments_invoices_contract: str,
        resource_name: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get resource details by name."""
        if self.wallet_id is None:
            return DAOToolResponse.error_response("Wallet ID is required")

        args = [payments_invoices_contract, resource_name]

        result = BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/extensions/payments-invoices/read-only",
            "get-resource-by-name.ts",
            *args,
        )

        if not result["success"]:
            return DAOToolResponse.error_response(
                result.get("error", "Unknown error"), result.get("output")
            )

        return DAOToolResponse.success_response(
            "Successfully retrieved resource details by name", result.get("output")
        )

    def _run(
        self,
        payments_invoices_contract: str,
        resource_name: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to get resource details by name."""
        return self._deploy(payments_invoices_contract, resource_name, **kwargs)

    async def _arun(
        self,
        payments_invoices_contract: str,
        resource_name: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(payments_invoices_contract, resource_name, **kwargs)


class PayInvoiceInput(BaseModel):
    """Input schema for paying an invoice."""

    payments_invoices_contract: str = Field(
        ...,
        description="Contract principal of the payments and invoices contract",
        example="ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-payments-invoices",
    )
    resource_index: int = Field(..., description="Index of the resource to pay for")
    memo: Optional[str] = Field(
        None, description="Optional memo to include with the payment"
    )


class PayInvoiceTool(BaseTool):
    name: str = "dao_pay_invoice"
    description: str = (
        "Pay an invoice for a specific resource in the DAO's payments and invoices system. "
        "Optionally includes a memo with the payment."
    )
    args_schema: Type[BaseModel] = PayInvoiceInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        payments_invoices_contract: str,
        resource_index: int,
        memo: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to pay an invoice."""
        if self.wallet_id is None:
            return DAOToolResponse.error_response("Wallet ID is required")

        args = [payments_invoices_contract, str(resource_index)]

        if memo:
            args.append(memo)

        result = BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/extensions/payments-invoices/public",
            "pay-invoice.ts",
            *args,
        )

        if not result["success"]:
            return DAOToolResponse.error_response(
                result.get("error", "Unknown error"), result.get("output")
            )

        return DAOToolResponse.success_response(
            "Successfully processed invoice payment", result.get("output")
        )

    def _run(
        self,
        payments_invoices_contract: str,
        resource_index: int,
        memo: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to pay an invoice."""
        return self._deploy(payments_invoices_contract, resource_index, memo, **kwargs)

    async def _arun(
        self,
        payments_invoices_contract: str,
        resource_index: int,
        memo: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(payments_invoices_contract, resource_index, memo, **kwargs)


class PayInvoiceByResourceNameInput(BaseModel):
    """Input schema for paying an invoice by resource name."""

    payments_invoices_contract: str = Field(
        ...,
        description="Contract principal of the payments and invoices contract",
        example="ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.faces-payments-invoices",
    )
    resource_name: str = Field(..., description="Name of the resource to pay for")
    memo: Optional[str] = Field(
        None, description="Optional memo to include with the payment"
    )


class PayInvoiceByResourceNameTool(BaseTool):
    name: str = "dao_pay_invoice_by_resource_name"
    description: str = (
        "Pay an invoice for a specific resource by its name in the DAO's payments and invoices system. "
        "Optionally includes a memo with the payment."
    )
    args_schema: Type[BaseModel] = PayInvoiceByResourceNameInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        payments_invoices_contract: str,
        resource_name: str,
        memo: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to pay an invoice by resource name."""
        if self.wallet_id is None:
            return DAOToolResponse.error_response("Wallet ID is required")

        args = [payments_invoices_contract, resource_name]

        if memo:
            args.append(memo)

        result = BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/extensions/payments-invoices/public",
            "pay-invoice-by-resource-name.ts",
            *args,
        )

        if not result["success"]:
            return DAOToolResponse.error_response(
                result.get("error", "Unknown error"), result.get("output")
            )

        return DAOToolResponse.success_response(
            "Successfully processed invoice payment by resource name",
            result.get("output"),
        )

    def _run(
        self,
        payments_invoices_contract: str,
        resource_name: str,
        memo: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to pay an invoice by resource name."""
        return self._deploy(payments_invoices_contract, resource_name, memo, **kwargs)

    async def _arun(
        self,
        payments_invoices_contract: str,
        resource_name: str,
        memo: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(payments_invoices_contract, resource_name, memo, **kwargs)
