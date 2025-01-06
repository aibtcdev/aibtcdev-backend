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
            "stacks-dao",
            "cli.ts",
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
            "stacks-dao",
            "cli.ts",
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
            "stacks-dao",
            "cli.ts",
            "treasury",
            "deposit-stx",
            "-t", treasury_id,
            "-a", str(amount),
        )


class TreasuryWithdrawTool(BaseTool):
    name: str = "Withdraw STX from DAO treasury"
    description: str = "Withdraw STX tokens from the DAO treasury"
    args_schema: Type[BaseModel] = TreasuryWithdrawToolSchema
    account_index: Optional[str] = None

    def __init__(self, account_index: str, **kwargs):
        super().__init__(**kwargs)
        self.account_index = account_index

    def _run(
        self,
        treasury_id: str,
        amount: int,
        recipient: str,
    ) -> str:
        return BunScriptRunner.bun_run(
            self.account_index,
            "stacks-dao",
            "cli.ts",
            "treasury",
            "withdraw-stx",
            "-t", treasury_id,
            "-a", str(amount)
            "-r", recipient
        )