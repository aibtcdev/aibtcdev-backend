from .bun import BunScriptRunner
from crewai_tools import BaseTool
from pydantic import BaseModel, Field
from typing import Dict, Type, Union


class ContractSIP10DeployToolSchema(BaseModel):
    """Input schema for ContractSIP10DeployTool."""

    token_symbol: str = Field(..., description="Symbol of the token.")
    token_name: str = Field(..., description="Name of the token.")
    token_decimals: int = Field(
        ..., description="Number of decimals for the token. Default is 6"
    )
    token_url: str = Field(..., description="URL associated with the token.")
    token_max_supply: int = Field(
        ..., description="Initial supply of the token. Default is 1000000000"
    )


class ContractSIP10DeployTool(BaseTool):
    name: str = "Deploy a new token with its contract."
    description: str = "Deploy a new token with its contract."
    args_schema: Type[BaseModel] = ContractSIP10DeployToolSchema
    account_index: str = "0"

    def __init__(self, account_index: str, **kwargs):
        super().__init__(**kwargs)
        self.account_index = account_index

    def _run(
        self,
        token_symbol,
        token_name,
        token_decimals,
        token_url,
        token_max_supply,
    ) -> Dict[str, str | bool | None]:
        return BunScriptRunner.bun_run(
            self.account_index,
            "sip-010-ft",
            "deploy.ts",
            token_name,
            token_symbol,
            str(token_decimals),
            token_url,
            str(token_max_supply),
        )


class ContractSIP10SendToolSchema(BaseModel):
    """Input schema for ContractSIP10SendTool."""

    contract_address: str = Field(
        ...,
        description="Contract address of the token. Format: contract_address.contract_name",
    )
    recipient: str = Field(..., description="Recipient address to send tokens to.")
    amount: int = Field(
        ...,
        description="Amount of tokens to send. Needs to be in microunits based on decimals of token.",
    )


class ContractSIP10SendTool(BaseTool):
    name: str = "Send fungible tokens to a recipient."
    description: str = "Send fungible tokens from your wallet to a recipient address."
    args_schema: Type[BaseModel] = ContractSIP10SendToolSchema
    account_index: str = "0"

    def __init__(self, account_index: str, **kwargs):
        super().__init__(**kwargs)
        self.account_index = account_index

    def _run(
        self,
        contract_address: str,
        recipient: str,
        amount: int,
    ) -> Dict[str, Union[str, bool, None]]:
        return BunScriptRunner.bun_run(
            self.account_index,
            "sip-010-ft",
            "transfer.ts",
            contract_address,
            recipient,
            str(amount),
        )


class ContractSIP10InfoToolSchema(BaseModel):
    """Input schema for ContractSIP10InfoTool."""

    contract_address: str = Field(
        ...,
        description="Contract address of the token. Format: contract_address.contract_name",
    )


class ContractSIP10InfoTool(BaseTool):
    name: str = "Get fungible token information."
    description: str = (
        "Get token information including name, symbol, decimals, and supply."
    )
    args_schema: Type[BaseModel] = ContractSIP10InfoToolSchema
    account_index: str = "0"

    def __init__(self, account_index: str, **kwargs):
        super().__init__(**kwargs)
        self.account_index = account_index

    def _run(
        self,
        contract_address: str,
    ) -> Dict[str, Union[str, bool, None]]:
        return BunScriptRunner.bun_run(
            self.account_index,
            "sip-010-ft",
            "get-token-info.ts",
            contract_address,
        )


class ContractDAOExecutorDeployToolSchema(BaseModel):
    """Input schema for ContractDAOExecutorDeployTool."""

    dao_name: str = Field(..., description="Name of the DAO.")
    contract_id: str = Field(..., description="Contract ID for the DAO.")


class ContractDAOExecutorDeployTool(BaseTool):
    name: str = "Deploy a new DAO executor contract."
    description: str = (
        "Deploy a new DAO executor contract with specified name and contract ID."
    )
    args_schema: Type[BaseModel] = ContractDAOExecutorDeployToolSchema
    account_index: str = "0"

    def __init__(self, account_index: str, **kwargs):
        super().__init__(**kwargs)
        self.account_index = account_index

    def _run(
        self,
        dao_name: str,
        contract_id: str,
    ) -> Dict[str, Union[str, bool, None]]:
        return BunScriptRunner.bun_run(
            self.account_index,
            "stacks-dao",
            "cli.ts",
            "executor",
            "deploy",
            "-n",
            dao_name,
            "-c",
            contract_id,
            "-d",
        )
