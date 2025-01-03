import json
from .bun import BunScriptRunner
from backend.factory import backend
from backend.models import CapabilityCreate
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from services.daos import (
    TokenServiceError,
    bind_token_to_collective,
    generate_collective_dependencies,
    generate_token_dependencies,
)
from typing import Any, Dict, Optional, Type, Union


class ContractCollectiveDeployInput(BaseModel):
    """Input schema for ContractCollectiveDeploy tool."""

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
    name: str = "contract_collective_deploy"
    description: str = (
        "Deploy a new collective with a token and a bonding curve for stacks"
    )
    args_schema: Type[BaseModel] = ContractCollectiveDeployInput
    return_direct: bool = False
    account_index: str = "0"

    def __init__(self, account_index: str = "0", **kwargs):
        super().__init__(**kwargs)
        self.account_index = account_index

    def _deploy(
        self,
        token_symbol: str,
        token_name: str,
        token_description: str,
        token_max_supply: str,
        token_decimals: str,
        mission: str,
        **kwargs,
    ) -> Dict[str, Union[str, bool, None]]:
        """Core deployment logic used by both sync and async methods."""
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

                if not backend.update_token(token_record["id"], token_updates):
                    return {
                        "output": "",
                        "error": "Failed to update token with contract information",
                        "success": False,
                    }

                for contract_name, contract_data in contracts.items():
                    if contract_name != "token":
                        if not backend.create_capability(
                            CapabilityCreate(
                                collective_record["id"],
                                contract_name,
                                contract_data["contractPrincipal"],
                                contract_data["transactionId"],
                                "deployed",
                            )
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

    def _run(
        self,
        token_symbol: str,
        token_name: str,
        token_description: str,
        token_max_supply: str,
        token_decimals: str,
        mission: str,
        **kwargs,
    ) -> Dict[str, Union[str, bool, None]]:
        """Execute the tool to deploy a new collective."""
        return self._deploy(
            token_symbol,
            token_name,
            token_description,
            token_max_supply,
            token_decimals,
            mission,
            **kwargs,
        )

    async def _arun(
        self,
        token_symbol: str,
        token_name: str,
        token_description: str,
        token_max_supply: str,
        token_decimals: str,
        mission: str,
        **kwargs,
    ) -> Dict[str, Union[str, bool, None]]:
        """Async version of the tool."""
        return self._deploy(
            token_symbol,
            token_name,
            token_description,
            token_max_supply,
            token_decimals,
            mission,
            **kwargs,
        )
