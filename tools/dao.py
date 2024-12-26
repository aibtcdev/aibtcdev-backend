from typing import Optional, Type, List
from pydantic import BaseModel, Field
from crewai_tools import BaseTool
from .bun import BunScriptRunner

# Schema definitions
class ExecutorListToolSchema(BaseModel):
    """Input schema for listing executor contracts."""
    pass

class ExecutorDeployToolSchema(BaseModel):
    """Input schema for deploying executor contracts."""
    name: str = Field(..., description="Name of the DAO")
    extensions: Optional[List[str]] = Field(
        default=[], description="Extension contracts to include"
    )
    include_deployer: bool = Field(
        default=False, description="Whether to include deployer in extensions"
    )
    fee: Optional[int] = Field(
        default=400000, description="Transaction fee in microSTX"
    )

class ExecutorSetExtensionToolSchema(BaseModel):
    """Input schema for setting extension status."""
    extension: str = Field(..., description="Extension contract ID")
    status: str = Field(..., description="'enable' or 'disable'")
    executor: str = Field(..., description="Executor contract ID")
    fee: Optional[int] = Field(
        default=10000, description="Transaction fee in microSTX"
    )

class TreasuryListToolSchema(BaseModel):
    """Input schema for listing treasury contracts."""
    pass

class TreasuryDeployToolSchema(BaseModel):
    """Input schema for deploying treasury contracts."""
    name: str = Field(..., description="Name of the Treasury")
    dao_contract_id: Optional[str] = Field(
        None, description="Associated DAO contract ID"
    )
    fee: Optional[int] = Field(
        default=400000, description="Transaction fee in microSTX"
    )

class TreasuryDepositToolSchema(BaseModel):
    """Input schema for depositing STX."""
    treasury_id: str = Field(..., description="Treasury contract ID")
    amount: int = Field(..., description="Amount in microSTX")
    fee: Optional[int] = Field(
        default=10000, description="Transaction fee in microSTX"
    )

class TreasuryWithdrawToolSchema(BaseModel):
    """Input schema for withdrawing STX."""
    treasury_id: str = Field(..., description="Treasury contract ID")
    amount: int = Field(..., description="Amount in microSTX")
    recipient: Optional[str] = Field(
        None, description="Optional recipient address"
    )
    fee: Optional[int] = Field(
        default=10000, description="Transaction fee in microSTX"
    )

# Base Tool
class DAOBaseTool(BaseTool):
    account_index: Optional[str] = None

    def __init__(self, account_index: str = "0", **kwargs):
        super().__init__(**kwargs)
        self.account_index = account_index

# Executor Tools
class ExecutorListTool(DAOBaseTool):
    name: str = "DAO: List Executors"
    description: str = "List all executor contracts"
    args_schema: Type[BaseModel] = ExecutorListToolSchema

    def _run(self) -> str:
        return BunScriptRunner.bun_run(
            self.account_index,
            "stacks-dao",
            "cli.ts",
            "executor",
            "list"
        )

class ExecutorDeployTool(DAOBaseTool):
    name: str = "DAO: Deploy Executor"
    description: str = "Deploy a new executor contract"
    args_schema: Type[BaseModel] = ExecutorDeployToolSchema

    def _run(self, name: str, extensions: List[str] = [], 
             include_deployer: bool = False, fee: int = 400000) -> str:
        args = ["executor", "deploy", "-n", name]
        if extensions:
            args.extend(["-e", *extensions])
        if include_deployer:
            args.append("-d")
        if fee != 400000:
            args.extend(["-f", str(fee)])
            
        return BunScriptRunner.bun_run(
            self.account_index,
            "stacks-dao",
            "cli.ts",
            *args
        )

class ExecutorSetExtensionTool(DAOBaseTool):
    name: str = "DAO: Set Extension Status"
    description: str = "Enable or disable an extension contract"
    args_schema: Type[BaseModel] = ExecutorSetExtensionToolSchema

    def _run(self, extension: str, status: str, executor: str, 
             fee: int = 10000) -> str:
        args = [
            "executor", "set-extension",
            "-e", extension,
            "-s", status,
            "-x", executor
        ]
        if fee != 10000:
            args.extend(["-f", str(fee)])
            
        return BunScriptRunner.bun_run(
            self.account_index,
            "stacks-dao",
            "cli.ts",
            *args
        )

# Treasury Tools
class TreasuryListTool(DAOBaseTool):
    name: str = "DAO: List Treasuries"
    description: str = "List all treasury contracts"
    args_schema: Type[BaseModel] = TreasuryListToolSchema

    def _run(self) -> str:
        return BunScriptRunner.bun_run(
            self.account_index,
            "stacks-dao",
            "cli.ts",
            "treasury",
            "list"
        )

class TreasuryDeployTool(DAOBaseTool):
    name: str = "DAO: Deploy Treasury"
    description: str = "Deploy a new treasury contract"
    args_schema: Type[BaseModel] = TreasuryDeployToolSchema

    def _run(self, name: str, dao_contract_id: Optional[str] = None, 
             fee: int = 400000) -> str:
        args = ["treasury", "deploy", "-n", name]
        if dao_contract_id:
            args.extend(["-d", dao_contract_id])
        if fee != 400000:
            args.extend(["-f", str(fee)])
            
        return BunScriptRunner.bun_run(
            self.account_index,
            "stacks-dao",
            "cli.ts",
            *args
        )

class TreasuryDepositTool(DAOBaseTool):
    name: str = "DAO: Deposit STX"
    description: str = "Deposit STX into treasury"
    args_schema: Type[BaseModel] = TreasuryDepositToolSchema

    def _run(self, treasury_id: str, amount: int, fee: int = 10000) -> str:
        args = [
            "treasury", "deposit-stx",
            "-t", treasury_id,
            "-a", str(amount)
        ]
        if fee != 10000:
            args.extend(["-f", str(fee)])
            
        return BunScriptRunner.bun_run(
            self.account_index,
            "stacks-dao",
            "cli.ts",
            *args
        )

class TreasuryWithdrawTool(DAOBaseTool):
    name: str = "DAO: Withdraw STX"
    description: str = "Withdraw STX from treasury"
    args_schema: Type[BaseModel] = TreasuryWithdrawToolSchema

    def _run(self, treasury_id: str, amount: int, 
             recipient: Optional[str] = None, fee: int = 10000) -> str:
        args = [
            "treasury", "withdraw-stx",
            "-t", treasury_id,
            "-a", str(amount)
        ]
        if recipient:
            args.extend(["-r", recipient])
        if fee != 10000:
            args.extend(["-f", str(fee)])
            
        return BunScriptRunner.bun_run(
            self.account_index,
            "stacks-dao",
            "cli.ts",
            *args
        )