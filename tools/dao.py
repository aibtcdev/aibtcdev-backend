from typing import Optional, Type, List
from crewai_tools import BaseTool
from .bun import BunScriptRunner
from pydantic import BaseModel, Field


class ExecutorDeployToolSchema(BaseModel):
    """Input schema for ExecutorDeployTool."""
    
    name: str = Field(..., description="Name of the DAO")
    extensions: Optional[List[str]] = Field(
        default=[], description="List of extension contracts to include"
    )
    include_deployer: bool = Field(
        default=False, description="Whether to include deployer in extensions"
    )


class ExecutorDeployTool(BaseTool):
    name: str = "Deploy a new DAO executor contract"
    description: str = "Deploy a new executor contract that manages the DAO"
    args_schema: Type[BaseModel] = ExecutorDeployToolSchema
    account_index: Optional[str] = None

    def __init__(self, account_index: str, **kwargs):
        super().__init__(**kwargs)
        self.account_index = account_index

    def _run(
        self,
        name: str,
        extensions: List[str] = [],
        include_deployer: bool = False,
    ) -> str:
        extensions_str = " ".join([f"-e {ext}" for ext in extensions])
        deployer_flag = "-d" if include_deployer else ""
        return BunScriptRunner.bun_run(
            self.account_index,
            "dao",
            "executor",
            "deploy",
            "-n", name,
            extensions_str,
            deployer_flag
        )


class TreasuryDeployToolSchema(BaseModel):
    """Input schema for TreasuryDeployTool."""
    
    name: str = Field(..., description="Name of the DAO")
    dao_contract_id: str = Field(..., description="Contract ID of the executor DAO")


class TreasuryDeployTool(BaseTool):
    name: str = "Deploy a new DAO treasury contract"
    description: str = "Deploy a new treasury contract for managing DAO assets"
    args_schema: Type[BaseModel] = TreasuryDeployToolSchema
    account_index: Optional[str] = None

    def __init__(self, account_index: str, **kwargs):
        super().__init__(**kwargs)
        self.account_index = account_index

    def _run(
        self,
        name: str,
        dao_contract_id: str,
    ) -> str:
        return BunScriptRunner.bun_run(
            self.account_index,
            "dao",
            "treasury",
            "deploy",
            "-n", name,
            "-d", dao_contract_id
        )


class TreasuryDepositToolSchema(BaseModel):
    """Input schema for TreasuryDepositTool."""
    
    treasury_id: str = Field(..., description="Contract ID of the treasury")
    amount: int = Field(..., description="Amount in microSTX to deposit")


class TreasuryDepositTool(BaseTool):
    name: str = "Deposit STX into DAO treasury"
    description: str = "Deposit STX tokens into the DAO treasury"
    args_schema: Type[BaseModel] = TreasuryDepositToolSchema
    account_index: Optional[str] = None

    def __init__(self, account_index: str, **kwargs):
        super().__init__(**kwargs)
        self.account_index = account_index

    def _run(
        self,
        treasury_id: str,
        amount: int,
    ) -> str:
        return BunScriptRunner.bun_run(
            self.account_index,
            "dao",
            "treasury",
            "deposit-stx",
            "-t", treasury_id,
            "-a", str(amount)
        )


class BankAccountDeployToolSchema(BaseModel):
    """Input schema for BankAccountDeployTool."""
    
    name: str = Field(..., description="Name of the DAO")
    dao_contract_id: str = Field(..., description="Contract ID of the executor DAO")
    withdrawal_period: Optional[int] = Field(
        default=144, description="Default withdrawal period in blocks"
    )
    withdrawal_amount: Optional[int] = Field(
        default=10000000, description="Default withdrawal amount in microSTX"
    )


class BankAccountDeployTool(BaseTool):
    name: str = "Deploy a new DAO bank account contract"
    description: str = "Deploy a new bank account contract for managing DAO funds"
    args_schema: Type[BaseModel] = BankAccountDeployToolSchema
    account_index: Optional[str] = None

    def __init__(self, account_index: str, **kwargs):
        super().__init__(**kwargs)
        self.account_index = account_index

    def _run(
        self,
        name: str,
        dao_contract_id: str,
        withdrawal_period: int = 144,
        withdrawal_amount: int = 10000000,
    ) -> str:
        return BunScriptRunner.bun_run(
            self.account_index,
            "dao",
            "bank",
            "deploy",
            "-n", name,
            "-d", dao_contract_id,
            "-p", str(withdrawal_period),
            "-a", str(withdrawal_amount)
        )


class MessagingDeployToolSchema(BaseModel):
    """Input schema for MessagingDeployTool."""
    
    name: str = Field(..., description="Name of the DAO")


class MessagingDeployTool(BaseTool):
    name: str = "Deploy a new DAO messaging contract"
    description: str = "Deploy a new messaging contract for DAO communications"
    args_schema: Type[BaseModel] = MessagingDeployToolSchema
    account_index: Optional[str] = None

    def __init__(self, account_index: str, **kwargs):
        super().__init__(**kwargs)
        self.account_index = account_index

    def _run(
        self,
        name: str,
    ) -> str:
        return BunScriptRunner.bun_run(
            self.account_index,
            "dao",
            "messaging",
            "deploy",
            "-n", name
        )


class MessagingSendToolSchema(BaseModel):
    """Input schema for MessagingSendTool."""
    
    contract_id: str = Field(..., description="Contract ID of the messaging contract")
    message: str = Field(..., description="Message to send")


class MessagingSendTool(BaseTool):
    name: str = "Send message through DAO messaging contract"
    description: str = "Send a message through the DAO messaging system"
    args_schema: Type[BaseModel] = MessagingSendToolSchema
    account_index: Optional[str] = None

    def __init__(self, account_index: str, **kwargs):
        super().__init__(**kwargs)
        self.account_index = account_index

    def _run(
        self,
        contract_id: str,
        message: str,
    ) -> str:
        return BunScriptRunner.bun_run(
            self.account_index,
            "dao",
            "messaging",
            "send",
            "-c", contract_id,
            "-m", message
        )


class PaymentsDeployToolSchema(BaseModel):
    """Input schema for PaymentsDeployTool."""
    
    name: str = Field(..., description="Name of the DAO")
    dao_contract_id: str = Field(..., description="Contract ID of the executor DAO")


class PaymentsDeployTool(BaseTool):
    name: str = "Deploy a new DAO payments contract"
    description: str = "Deploy a new payments contract for handling DAO payments"
    args_schema: Type[BaseModel] = PaymentsDeployToolSchema
    account_index: Optional[str] = None

    def __init__(self, account_index: str, **kwargs):
        super().__init__(**kwargs)
        self.account_index = account_index

    def _run(
        self,
        name: str,
        dao_contract_id: str,
    ) -> str:
        return BunScriptRunner.bun_run(
            self.account_index,
            "dao",
            "payments",
            "deploy",
            "-n", name,
            "-d", dao_contract_id
        )


class PaymentsAddResourceToolSchema(BaseModel):
    """Input schema for PaymentsAddResourceTool."""
    
    contract_id: str = Field(..., description="Contract ID of the payments contract")
    name: str = Field(..., description="Name of the resource")
    description: str = Field(..., description="Description of the resource")
    price: int = Field(..., description="Price in microSTX")


class PaymentsAddResourceTool(BaseTool):
    name: str = "Add resource to DAO payments contract"
    description: str = "Add a new resource to the DAO payments system"
    args_schema: Type[BaseModel] = PaymentsAddResourceToolSchema
    account_index: Optional[str] = None

    def __init__(self, account_index: str, **kwargs):
        super().__init__(**kwargs)
        self.account_index = account_index

    def _run(
        self,
        contract_id: str,
        name: str,
        description: str,
        price: int,
    ) -> str:
        return BunScriptRunner.bun_run(
            self.account_index,
            "dao",
            "payments",
            "add-resource",
            "-c", contract_id,
            "-n", name,
            "-d", description,
            "-p", str(price)
        )