from uuid import UUID
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
from tools.bun import BunScriptRunner
from tools.dao_base import DAOToolResponse
from typing import Dict, Optional, Type, Any

class GetInvoiceInput(BaseModel):
    """Input schema for getting invoice details."""
    payments_invoices_contract: str = Field(
        ..., 
        description="Contract ID of the payments and invoices contract"
    )
    invoice_index: int = Field(
        ...,
        description="Index of the invoice to retrieve"
    )

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

        args = [
            payments_invoices_contract,
            str(invoice_index)
        ]

        result = BunScriptRunner.bun_run(
            self.wallet_id,
            "payments-invoices",
            "get-invoice.ts",
            *args
        )

        if not result["success"]:
            return DAOToolResponse.error_response(
                result.get("error", "Unknown error"),
                result.get("output", "")
            )
            
        return DAOToolResponse.success_response(
            result["output"],
            {"raw_result": result}
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
        description="Contract ID of the payments and invoices contract"
    )
    resource_index: int = Field(
        ...,
        description="Index of the resource to retrieve"
    )

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
            return {
                "success": False,
                "error": "Wallet ID is required",
                "output": "",
            }

        args = [
            payments_invoices_contract,
            str(resource_index)
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "payments-invoices",
            "get-resource.ts",
            *args
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
        description="Contract ID of the payments and invoices contract"
    )
    resource_name: str = Field(
        ...,
        description="Name of the resource to retrieve"
    )

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
            return {
                "success": False,
                "error": "Wallet ID is required",
                "output": "",
            }

        args = [
            payments_invoices_contract,
            resource_name
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "payments-invoices",
            "get-resource-by-name.ts",
            *args
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
        description="Contract ID of the payments and invoices contract"
    )
    resource_index: int = Field(
        ...,
        description="Index of the resource to pay for"
    )
    memo: Optional[str] = Field(
        None,
        description="Optional memo to include with the payment"
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
            return {
                "success": False,
                "error": "Wallet ID is required",
                "output": "",
            }

        args = [
            payments_invoices_contract,
            str(resource_index)
        ]
        
        if memo:
            args.append(memo)

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "payments-invoices",
            "pay-invoice.ts",
            *args
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
        description="Contract ID of the payments and invoices contract"
    )
    resource_name: str = Field(
        ...,
        description="Name of the resource to pay for"
    )
    memo: Optional[str] = Field(
        None,
        description="Optional memo to include with the payment"
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
            return {
                "success": False,
                "error": "Wallet ID is required",
                "output": "",
            }

        args = [
            payments_invoices_contract,
            resource_name
        ]
        
        if memo:
            args.append(memo)

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "payments-invoices",
            "pay-invoice-by-resource-name.ts",
            *args
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
