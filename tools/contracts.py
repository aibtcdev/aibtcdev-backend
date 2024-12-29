import json
from .bun import BunScriptRunner
from crewai_tools import BaseTool
from db.factory import db
from pydantic import BaseModel, Field
from services.daos import (
    TokenServiceError,
    bind_token_to_collective,
    generate_collective_dependencies,
    generate_token_dependencies,
)
from typing import Dict, Type, Union


class ContractError(Exception):
    """Base exception for contract-related errors"""

    def __init__(self, message: str, details: Dict = None):
        super().__init__(message)
        self.details = details or {}


class ContractCollectiveDeployToolSchema(BaseModel):
    """Input schema for ContractCollectiveDeployToolSchema."""

    token_symbol: str = Field(
        ..., description="The symbol for the token for the collective (e.g., 'HUMAN')"
    )
    token_name: str = Field(
        ..., description="The name of the token for the collective (e.g., 'Human')"
    )
    token_description: str = Field(
        ...,
        description="The description of the token for the collective (e.g., 'The Human Token')",
    )
    token_max_supply: str = Field(
        ...,
        description="Initial supply of the token for the collective. Default is 1000000000",
    )
    token_decimals: str = Field(
        ...,
        description="Number of decimals for the token for the collective. Default is 6",
    )
    mission: str = Field(..., description="The mission statement for the collective")


class ContractCollectiveDeployTool(BaseTool):
    name: str = "Collective Deploy Tool"
    description: str = """
    Deploy a new collective with a token and a bonding curve for stacks.
    """
    args_schema: type[BaseModel] = ContractCollectiveDeployToolSchema
    account_index: str = "0"

    def __init__(self, account_index: str, **kwargs):
        super().__init__(**kwargs)
        self.account_index = account_index

    def _run(
        self,
        token_symbol: str,
        token_name: str,
        token_description: str,
        token_max_supply: str,
        token_decimals: str,
        mission: str,
    ) -> Dict[str, Union[str, bool, None]]:
        try:

            # Generate collective dependencies and get collective record
            collective_record = generate_collective_dependencies(
                token_name, mission, token_description
            )

            # Generate token dependencies and get token record
            metadata_url, token_record = generate_token_dependencies(
                token_name,
                token_symbol,
                token_description,
                token_decimals,
                token_max_supply,
            )

            if not bind_token_to_collective(
                token_record["id"], collective_record["id"]
            ):
                return {
                    "output": "",
                    "error": "Failed to bind token to collective",
                    "success": False,
                }

            # Deploy contracts
            result = BunScriptRunner.bun_run(
                self.account_index,
                "stacks-contracts",
                "deploy-dao.ts",
                token_symbol,
                token_name,
                token_max_supply,
                token_decimals,
                metadata_url,
            )

            if not result["success"]:
                return {
                    "output": result["output"],
                    "error": result["error"],
                    "success": False,
                }

            # Parse deployment output
            try:
                deployment_data = json.loads(result["output"])
                if not deployment_data["success"]:
                    return {
                        "output": result["output"],
                        "error": deployment_data.get(
                            "error", "Unknown deployment error"
                        ),
                        "success": False,
                    }

                # Update token record with contract information
                contracts = deployment_data["contracts"]
                token_updates = {
                    "contract_principal": contracts["token"]["contractPrincipal"],
                    "tx_id": contracts["token"]["transactionId"],
                }

                if not db.update_token(token_record["id"], token_updates):
                    return {
                        "output": "",
                        "error": "Failed to update token with contract information",
                        "success": False,
                    }

                for contract_name, contract_data in contracts.items():
                    if contract_name != "token":
                        if not db.add_capability(
                            collective_record["id"],
                            contract_name,
                            contract_data["contractPrincipal"],
                            contract_data["transactionId"],
                            "deployed",
                        ):
                            return {
                                "output": "",
                                "error": f"Failed to add {contract_name} capability",
                                "success": False,
                            }

                return {
                    "output": result["output"],
                    "error": None,
                    "success": True,
                }

            except json.JSONDecodeError as e:
                return {
                    "output": result["output"],
                    "error": f"Failed to parse deployment output: {str(e)}",
                    "success": False,
                }

        except TokenServiceError as e:
            error_msg = f"Failed to create token dependencies: {str(e)}"
            details = e.details if hasattr(e, "details") else None
            return {
                "output": details if details else "",
                "error": error_msg,
                "success": False,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error during token deployment: {str(e)}",
                "output": "",
            }


class ContractSIP10DeployToolSchema(BaseModel):
    """Input schema for ContractSIP10DeployTool."""

    token_symbol: str = Field(..., description="Symbol of the token.")
    token_name: str = Field(..., description="Name of the token.")
    token_description: str = Field(
        ..., description="Description of the token. Default is an empty string."
    )
    token_decimals: int = Field(
        ..., description="Number of decimals for the token. Default is 6"
    )
    token_max_supply: str = Field(
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
        token_symbol: str,
        token_name: str,
        token_decimals: int,
        token_description: str,
        token_max_supply: str,
    ) -> Dict[str, Union[str, bool, None]]:
        try:
            token_url, token_data = generate_token_dependencies(
                token_name,
                token_symbol,
                token_description,
                token_decimals,
                token_max_supply,
            )

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

        except TokenServiceError as e:
            error_msg = f"Failed to create token dependencies: {str(e)}"
            if e.details:
                error_msg += f"\nDetails: {e.details}"
            return {"success": False, "error": error_msg, "details": e.details}
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error during token deployment: {str(e)}",
            }


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
        try:
            return BunScriptRunner.bun_run(
                self.account_index,
                "sip-010-ft",
                "transfer.ts",
                contract_address,
                recipient,
                str(amount),
            )
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error during token transfer: {str(e)}",
            }


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
        try:
            return BunScriptRunner.bun_run(
                self.account_index,
                "sip-010-ft",
                "get-token-info.ts",
                contract_address,
            )
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error during token info retrieval: {str(e)}",
            }


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
        try:
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
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error during DAO executor deployment: {str(e)}",
            }
