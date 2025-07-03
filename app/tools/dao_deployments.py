import json
from typing import Dict, Optional, Type, Union

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from app.backend.factory import backend
from app.backend.models import (
    UUID,
    ContractStatus,
    DAOBase,
    ExtensionCreate,
    ProposalCreate,
    TokenBase,
)
from app.lib.logger import configure_logger
from app.services.core.dao_service import (
    TokenServiceError,
    bind_token_to_dao,
    generate_dao_dependencies,
    generate_token_dependencies,
)

from .bun import BunScriptRunner

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
    name: str = "contract_deploy_dao"
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

            # get the address for the wallet based on network from app.config

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
                # build error message based on ToolResponse in TS
                error_message = result.get("message", "Unknown error")
                error_data = result.get("data", "No error data")
                logger.error(
                    f"Contract deployment failed: {error_message} {error_data}"
                )
                logger.error(f"Deployment output: {result.get('output', 'No output')}")
                return {
                    "output": result["output"],
                    "error": result["error"] + error_message + error_data,
                    "success": False,
                }

            # Parse deployment output
            logger.debug("Step 6: Parsing deployment output...")
            try:
                deployment_data = json.loads(result["output"])
                logger.debug(f"Parsed deployment data: {deployment_data}")
                if not deployment_data["success"]:
                    error_msg = deployment_data.get(
                        "message", "Unknown deployment error"
                    )
                    error_data = deployment_data.get("data", "No error data")
                    logger.error(f"Deployment unsuccessful: {error_msg} {error_data}")
                    return {
                        "output": result["output"],
                        "error": error_msg + error_data,
                        "success": False,
                    }

                backend.update_dao(
                    dao_record.id, update_data=DAOBase(is_broadcasted=True)
                )
                # Update token record with contract information
                logger.debug("Step 7: Updating token with contract information...")
                contracts = deployment_data["data"]  # main key in ToolResponse
                token_contract = next(
                    (
                        contract
                        for contract in contracts
                        if (
                            contract["type"] == "TOKEN" and contract["subtype"] == "DAO"
                        )
                    ),
                    None,
                )
                if not token_contract:
                    logger.error("Token contract not found in deployment results")
                    return {
                        "output": "",
                        "error": "Token contract not found in deployment results",
                        "success": False,
                    }

                token_updates = TokenBase(
                    contract_principal=token_contract["address"],
                    tx_id=token_contract["txId"],
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
                for contract in contracts:
                    # set values based on DeployedContractRegistryEntry in TS
                    contract_name = contract["name"]
                    contract_address = contract["address"]
                    contract_type = contract["type"]
                    contract_subtype = contract["subtype"]
                    contract_txid = contract["txId"]

                    # if its an extension, add to db
                    if contract_type == "EXTENSIONS":
                        logger.debug(f"Creating extension for {contract_name}")
                        extension_result = backend.create_extension(
                            ExtensionCreate(
                                dao_id=dao_record.id,
                                type=contract_name,
                                contract_principal=contract_address,
                                tx_id=contract_txid,
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
                        # if its a bootstrap contract, create proposal
                        if (
                            contract_subtype == "BOOTSTRAP_INIT"
                        ):  # Use subcategory instead of name
                            logger.debug(f"Creating proposal for {contract_name}")
                            proposal_result = backend.create_proposal(
                                ProposalCreate(
                                    dao_id=dao_record.id,
                                    status=ContractStatus.PENDING,
                                    tx_id=contract_txid,
                                    contract_principal=contract_address,
                                    title="Initialize DAO",
                                    description="Initialize the DAO",
                                )
                            )
                            # Add error handling
                            if not proposal_result:
                                logger.error("Failed to create bootstrap proposal")
                                return {
                                    "output": "",
                                    "error": "Failed to create bootstrap proposal",
                                    "success": False,
                                }
                    if contract_name == "aibtc-base-bootstrap-initialization":
                        logger.debug(
                            f"Successfully created extension for {contract_name}"
                        )
                        proposal_result = backend.create_proposal(
                            ProposalCreate(
                                dao_id=dao_record.id,
                                status=ContractStatus.PENDING,
                                tx_id=contract_txid,
                                contract_principal=contract_address,
                                title="Initialize DAO",
                                description="Initialize the DAO",
                            )
                        )

                    # construct the dao with bootstrap proposal
                    logger.debug("Step 9: Constructing dao...")

                    # find required contracts
                    base_dao_contract = next(
                        (
                            contract
                            for contract in contracts
                            if contract["type"] == "BASE"
                            and contract["subtype"] == "DAO"
                        ),
                        None,
                    )
                    bootstrap_proposal_contract = next(
                        (
                            contract
                            for contract in contracts
                            if contract["subtype"] == "BOOTSTRAP_INIT"
                        ),
                        None,
                    )
                    # make sure they're found
                    if not base_dao_contract or not bootstrap_proposal_contract:
                        logger.error(
                            "Could not find base DAO or bootstrap proposal contracts"
                        )
                        logger.error(f"Base DAO found: {base_dao_contract is not None}")
                        logger.error(
                            f"Bootstrap proposal found: {bootstrap_proposal_contract is not None}"
                        )
                        return {
                            "output": "",
                            "error": "Missing required contracts for DAO construction",
                            "success": False,
                        }
                    # call tool to construct dao
                    logger.debug(f"Base DAO contract: {base_dao_contract['address']}")
                    logger.debug(
                        f"Bootstrap proposal contract: {bootstrap_proposal_contract['address']}"
                    )
                    construct_result = BunScriptRunner.bun_run(
                        self.wallet_id,
                        "stacks-contracts",
                        "construct-dao.ts",
                        base_dao_contract["address"],
                        bootstrap_proposal_contract["address"],
                    )
                    logger.debug(
                        f"DAO construction result type: {type(construct_result)}"
                    )
                    logger.debug(f"DAO construction result content: {construct_result}")
                    if not construct_result["success"]:
                        logger.error(
                            f"DAO construction failed: {construct_result.get('error', 'Unknown error')}"
                        )
                        logger.error(
                            f"Construction output: {construct_result.get('output', 'No output')}"
                        )
                        return {
                            "output": construct_result["output"],
                            "error": construct_result["error"],
                            "success": False,
                        }
                    # Parse construction output
                    try:
                        construction_data = json.loads(construct_result["output"])
                        logger.debug(f"Parsed construction data: {construction_data}")

                        if not construction_data["success"]:
                            error_msg = construction_data.get(
                                "message", "Unknown construction error"
                            )
                            error_data = construction_data.get("data", "No error data")
                            logger.error(
                                f"DAO construction unsuccessful: {error_msg} {error_data}"
                            )
                            return {
                                "output": construct_result["output"],
                                "error": error_msg + error_data,
                                "success": False,
                            }

                        # Update the DAO status to indicate construction is complete
                        backend.update_dao(
                            dao_record.id,
                            update_data=DAOBase(
                                is_constructed=True,
                                construction_tx_id=construction_data.get(
                                    "data", {}
                                ).get("txid"),
                            ),
                        )

                        logger.info(
                            f"DAO successfully constructed with txid: {construction_data.get('data', {}).get('txid')}"
                        )

                        # Return success with all the relevant information
                        return {
                            "output": construct_result["output"],
                            "dao_id": dao_record.id,
                            "image_url": token_record.image_url,
                            "txid": construction_data.get("data", {}).get("txid"),
                            "error": None,
                            "success": True,
                        }

                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse construction output: {str(e)}")
                        logger.error(f"Raw output: {construct_result['output']}")
                        return {
                            "output": construct_result["output"],
                            "error": f"Failed to parse construction output: {str(e)}",
                            "success": False,
                        }

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
