import json
import os
from .bun import BunScriptRunner
from backend.factory import backend
from backend.models import (
    UUID,
    ContractStatus,
    DAOBase,
    ExtensionCreate,
    ProposalCreate,
    TokenBase,
)
from config import config
from langchain.tools import BaseTool
from lib.hiro import HiroApi
from lib.logger import configure_logger
from lib.platform import PlatformApi
from pydantic import BaseModel, Field
from services.daos import (
    TokenServiceError,
    bind_token_to_dao,
    generate_dao_dependencies,
    generate_token_dependencies,
)
from typing import Dict, Optional, Type, Union

logger = configure_logger(__name__)


class ContractDAODeployInput(BaseModel):
    """Input schema for ContractDAODeploy tool."""

    token_symbol: str = Field(
        ..., description="The symbol for the token for the DAO (e.g., 'HUMAN')"
    )
    token_name: str = Field(
        ..., description="The name of the token for the DAO (e.g., 'Human')"
    )
    token_description: str = Field(
        ...,
        description="The description of the token for the DAO (e.g., 'The Human Token')",
    )
    token_max_supply: str = Field(
        ...,
        description="Initial supply of the token for the DAO. Default is 1000000000",
    )
    token_decimals: str = Field(
        ...,
        description="Number of decimals for the token for the DAO. Default is 6",
    )
    origin_address: str = Field(
        ...,
        description="The address of the originator of the DAO (e.g., 'ST1PQHQKV0Y2Q6Z7X1QZQ4VH6QZ6QZJWZQXGJ5YJ8')",
    )
    mission: str = Field(
        ...,
        description="The mission of the DAO serves as the unifying purpose and guiding principle of an AI DAO. It defines its goals, values, and desired impact, aligning participants and AI resources to achieve a shared outcome.",
    )
    tweet_origin: str = Field(
        ...,
        description="The ID of the tweet that originated the DAO (e.g., '1440000000000000000')",
    )


class ContractDAODeployTool(BaseTool):
    name: str = "contract_dao_deploy"
    description: str = (
        "Deploy a new DAO with a token and a bonding curve for Stacks blockchain. "
        "Example usage: 'deploy a community DAO named 'GreenEarth' with a token named 'Green Token' and a purpose statement "
        "'Promoting global environmental sustainability through decentralized collaboration and funding.'"
    )
    args_schema: Type[BaseModel] = ContractDAODeployInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

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
        origin_address: str,
        mission: str,
        tweet_origin: str = "",
        **kwargs,
    ) -> Dict[str, Union[str, bool, None]]:
        """Core deployment logic used by both sync and async methods."""
        try:
            if self.wallet_id is None:
                return {
                    "success": False,
                    "error": "Wallet ID is required",
                    "output": "",
                }

            # get the address for the wallet based on network from config
            network = config.network.network

            hiro = HiroApi()
            current_block_height = hiro.get_current_block_height()
            logger.debug(f"Current block height: {current_block_height}")

            logger.debug(
                f"Starting deployment with token_symbol={token_symbol}, "
                f"token_name={token_name}, token_description={token_description}, "
                f"token_max_supply={token_max_supply}, token_decimals={token_decimals}, "
                f"mission={mission}"
            )

            # Generate dao dependencies and get dao record
            logger.debug("Step 1: Generating dao dependencies...")
            dao_record = generate_dao_dependencies(
                token_name, mission, token_description, self.wallet_id
            )
            logger.debug(f"Generated dao record type: {type(dao_record)}")
            logger.debug(f"Generated dao record content: {dao_record}")

            # Generate token dependencies and get token record
            logger.debug("Step 2: Generating token dependencies...")
            logger.debug(f"Converting token_decimals from str to int: {token_decimals}")
            token_decimals_int = int(token_decimals)
            logger.debug(f"Converted token_decimals to: {token_decimals_int}")

            metadata_url, token_record = generate_token_dependencies(
                token_name,
                token_symbol,
                mission,
                token_decimals_int,  # Convert to int for database
                token_max_supply,
            )
            logger.debug(f"Generated token record type: {type(token_record)}")
            logger.debug(f"Generated token record content: {token_record}")
            logger.debug(f"Generated metadata_url: {metadata_url}")

            # Bind token to dao
            logger.debug("Step 4: Binding token to dao...")
            bind_result = bind_token_to_dao(token_record.id, dao_record.id)
            if not bind_result:
                logger.error("Failed to bind token to dao")
                logger.error(f"Token ID: {token_record.id}")
                logger.error(f"DAO ID: {dao_record.id}")
                return {
                    "output": "",
                    "error": "Failed to bind token to dao",
                    "success": False,
                }
            logger.debug("Successfully bound token to dao")

            # Deploy contracts
            logger.debug("Step 5: Deploying contracts...")
            logger.debug(
                f"BunScriptRunner parameters: wallet_id={self.wallet_id}, "
                f"token_symbol={token_symbol}, token_name={token_name}, "
                f"token_max_supply={token_max_supply}, metadata_url={metadata_url}, "
                f"logo_url={token_record.image_url}, origin_address={origin_address}, "
                f"dao_manifest={mission}, tweet_origin={tweet_origin}"
            )
            # "Usage: bun run deploy-dao.ts <tokenSymbol> <tokenName> <tokenMaxSupply> <tokenUri> <logoUrl> <originAddress> <daoManifest> <tweetOrigin>"

            result = BunScriptRunner.bun_run(
                self.wallet_id,
                "stacks-contracts",
                "deploy-dao.ts",
                token_symbol,
                token_name,
                token_max_supply,
                metadata_url,
                token_record.image_url,
                origin_address,
                mission,
                tweet_origin,
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

                backend.update_dao(
                    dao_record.id, update_data=DAOBase(is_broadcasted=True)
                )
                # Update token record with contract information
                logger.debug("Step 7: Updating token with contract information...")
                contracts = deployment_data["contracts"]
                token_updates = TokenBase(
                    contract_principal=contracts["token"]["contractPrincipal"],
                    tx_id=contracts["token"]["transactionId"],
                    status=ContractStatus.PENDING,
                )
                logger.debug(f"Token updates: {token_updates}")
                if not backend.update_token(token_record.id, token_updates):
                    logger.error("Failed to update token with contract information")
                    return {
                        "output": "",
                        "error": "Failed to update token with contract information",
                        "success": False,
                    }

                # Create extensions
                logger.debug("Step 8: Creating extensions...")
                for contract_name, contract_data in contracts.items():
                    platform = PlatformApi()
                    chainhook = platform.create_contract_deployment_hook(
                        txid=contract_data.get("transactionId"),
                        network=network,
                        name=f"{dao_record.id}",
                        start_block=current_block_height,
                        expire_after_occurrence=1,
                    )
                    logger.debug(f"Created chainhook: {chainhook}")

                    if (
                        contract_name != "token"
                        and contract_name != "aibtc-base-bootstrap-initialization"
                    ):
                        logger.debug(f"Creating extension for {contract_name}")
                        extension_result = backend.create_extension(
                            ExtensionCreate(
                                dao_id=dao_record.id,
                                type=contract_name,
                                contract_principal=contract_data["contractPrincipal"],
                                tx_id=contract_data["transactionId"],
                                status="PENDING",
                            )
                        )
                        if not extension_result:
                            logger.error(f"Failed to add {contract_name} extension")
                            return {
                                "output": "",
                                "error": f"Failed to add {contract_name} extension",
                                "success": False,
                            }
                        logger.debug(
                            f"Successfully created extension for {contract_name}"
                        )
                    if contract_name == "aibtc-base-bootstrap-initialization":
                        logger.debug(
                            f"Successfully created extension for {contract_name}"
                        )
                        proposal_result = backend.create_proposal(
                            ProposalCreate(
                                dao_id=dao_record.id,
                                status=ContractStatus.PENDING,
                                tx_id=contract_data["transactionId"],
                                contract_principal=contract_data["contractPrincipal"],
                                title="Initialize DAO",
                                description="Initialize the DAO",
                            )
                        )

                logger.debug("Deployment completed successfully")
                return {
                    "output": result["output"],
                    "dao_id": dao_record.id,
                    "image_url": token_record.image_url,
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
        origin_address: str,
        mission: str,
        tweet_origin: str = "",
        **kwargs,
    ) -> Dict[str, Union[str, bool, None]]:
        """Execute the tool to deploy a new dao."""
        return self._deploy(
            token_symbol,
            token_name,
            token_description,
            token_max_supply,
            token_decimals,
            origin_address,
            mission,
            tweet_origin,
            **kwargs,
        )

    async def _arun(
        self,
        token_symbol: str,
        token_name: str,
        token_description: str,
        token_max_supply: str,
        token_decimals: str,
        origin_address: str,
        mission: str,
        tweet_origin: str = "",
        **kwargs,
    ) -> Dict[str, Union[str, bool, None]]:
        """Async version of the tool."""
        return self._deploy(
            token_symbol,
            token_name,
            token_description,
            token_max_supply,
            token_decimals,
            origin_address,
            mission,
            tweet_origin,
            **kwargs,
        )
