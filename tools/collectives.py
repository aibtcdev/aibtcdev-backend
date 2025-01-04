import json
import logging
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
from uuid import UUID

logger = logging.getLogger(__name__)


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
    wallet_id: Optional[UUID] = UUID("00000000-0000-0000-0000-000000000000")

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

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
            logger.debug(
                f"Starting deployment with token_symbol={token_symbol}, "
                f"token_name={token_name}, token_description={token_description}, "
                f"token_max_supply={token_max_supply}, token_decimals={token_decimals}, "
                f"mission={mission}"
            )

            # Generate collective dependencies and get collective record
            logger.debug("Step 1: Generating collective dependencies...")
            collective_record = generate_collective_dependencies(
                token_name, mission, token_description
            )
            logger.debug(f"Generated collective record type: {type(collective_record)}")
            logger.debug(f"Generated collective record content: {collective_record}")

            # Generate token dependencies and get token record
            logger.debug("Step 2: Generating token dependencies...")
            logger.debug(f"Converting token_decimals from str to int: {token_decimals}")
            token_decimals_int = int(token_decimals)
            logger.debug(f"Converted token_decimals to: {token_decimals_int}")

            metadata_url, token_record = generate_token_dependencies(
                token_name,
                token_symbol,
                token_description,
                token_decimals_int,  # Convert to int for database
                token_max_supply,
            )
            logger.debug(f"Generated token record type: {type(token_record)}")
            logger.debug(f"Generated token record content: {token_record}")
            logger.debug(f"Generated metadata_url: {metadata_url}")

            # Verify record IDs before binding
            logger.debug("Step 3: Verifying record IDs before binding...")
            try:
                token_id = token_record["id"]
                collective_id = collective_record["id"]
                logger.debug(f"Token ID: {token_id}, Collective ID: {collective_id}")
            except (KeyError, TypeError) as e:
                logger.error(f"Failed to extract IDs from records: {str(e)}")
                logger.error(
                    f"Token record keys: {token_record.keys() if isinstance(token_record, dict) else 'Not a dict'}"
                )
                logger.error(
                    f"Collective record keys: {collective_record.keys() if isinstance(collective_record, dict) else 'Not a dict'}"
                )
                raise ValueError(f"Invalid record format: {str(e)}")

            # Bind token to collective
            logger.debug("Step 4: Binding token to collective...")
            bind_result = bind_token_to_collective(token_id, collective_id)
            if not bind_result:
                logger.error("Failed to bind token to collective")
                logger.error(f"Token ID: {token_id}")
                logger.error(f"Collective ID: {collective_id}")
                return {
                    "output": "",
                    "error": "Failed to bind token to collective",
                    "success": False,
                }
            logger.debug("Successfully bound token to collective")

            # Deploy contracts
            logger.debug("Step 5: Deploying contracts...")
            logger.debug(
                f"BunScriptRunner parameters: wallet_id={self.wallet_id}, "
                f"token_symbol={token_symbol}, token_name={token_name}, "
                f"token_max_supply={token_max_supply}, token_decimals={token_decimals}, "
                f"metadata_url={metadata_url}"
            )

            result = BunScriptRunner.bun_run(
                self.wallet_id,
                "stacks-contracts",
                "deploy-dao.ts",
                token_symbol,
                token_name,
                token_max_supply,
                token_decimals,  # Keep as string for TypeScript
                metadata_url,
            )
            logger.debug(f"Contract deployment result type: {type(result)}")
            logger.debug(f"Contract deployment result content: {result}")

            if not result["success"]:
                logger.error(
                    f"Contract deployment failed: {result.get('error', 'Unknown error')}"
                )
                logger.error(f"Deployment output: {result.get('output', 'No output')}")
                return {
                    "output": result["output"],
                    "error": result["error"],
                    "success": False,
                }

            # Parse deployment output
            logger.debug("Step 6: Parsing deployment output...")
            try:
                deployment_data = json.loads(result["output"])
                logger.debug(f"Parsed deployment data: {deployment_data}")
                if not deployment_data["success"]:
                    error_msg = deployment_data.get("error", "Unknown deployment error")
                    logger.error(f"Deployment unsuccessful: {error_msg}")
                    return {
                        "output": result["output"],
                        "error": error_msg,
                        "success": False,
                    }

                # Update token record with contract information
                logger.debug("Step 7: Updating token with contract information...")
                contracts = deployment_data["contracts"]
                token_updates = {
                    "contract_principal": contracts["token"]["contractPrincipal"],
                    "tx_id": contracts["token"]["transactionId"],
                }
                logger.debug(f"Token updates: {token_updates}")

                if not backend.update_token(token_id, token_updates):
                    logger.error("Failed to update token with contract information")
                    return {
                        "output": "",
                        "error": "Failed to update token with contract information",
                        "success": False,
                    }

                # Create capabilities
                logger.debug("Step 8: Creating capabilities...")
                for contract_name, contract_data in contracts.items():
                    if contract_name != "token":
                        logger.debug(f"Creating capability for {contract_name}")
                        capability_result = backend.create_capability(
                            CapabilityCreate(
                                collective_id=collective_id,
                                type=contract_name,
                                contract_principal=contract_data["contractPrincipal"],
                                tx_id=contract_data["transactionId"],
                                status="deployed",
                            )
                        )
                        if not capability_result:
                            logger.error(f"Failed to add {contract_name} capability")
                            return {
                                "output": "",
                                "error": f"Failed to add {contract_name} capability",
                                "success": False,
                            }
                        logger.debug(
                            f"Successfully created capability for {contract_name}"
                        )

                logger.debug("Deployment completed successfully")
                return {
                    "output": result["output"],
                    "error": None,
                    "success": True,
                }

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse deployment output: {str(e)}")
                logger.error(f"Raw output: {result['output']}")
                return {
                    "output": result["output"],
                    "error": f"Failed to parse deployment output: {str(e)}",
                    "success": False,
                }

        except TokenServiceError as e:
            logger.error(f"TokenServiceError occurred: {str(e)}")
            if hasattr(e, "details"):
                logger.error(f"Error details: {e.details}")
            error_msg = f"Failed to create token dependencies: {str(e)}"
            details = e.details if hasattr(e, "details") else None
            return {
                "output": details if details else "",
                "error": error_msg,
                "success": False,
            }
        except Exception as e:
            logger.error(f"Unexpected error during deployment: {str(e)}", exc_info=True)
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
