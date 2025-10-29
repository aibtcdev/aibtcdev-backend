"""Agent account deployment task implementation."""

import json
from dataclasses import dataclass
import re
import time
from typing import Any, Dict, List, Optional

from app.backend.factory import backend
from app.backend.models import (
    AgentBase,
    QueueMessage,
    QueueMessageBase,
    QueueMessageFilter,
    QueueMessageType,
    Wallet,
    WalletFilter,
)
from app.config import config
from app.lib.logger import configure_logger
from app.services.infrastructure.job_management.base import (
    BaseTask,
    JobContext,
    RunnerConfig,
    RunnerResult,
)
from app.services.infrastructure.job_management.decorators import JobPriority, job
from app.tools.agent_account import AgentAccountDeployTool
from app.tools.agent_account_configuration import AgentAccountApproveContractTool

logger = configure_logger(__name__)


@dataclass
class AgentAccountDeployResult(RunnerResult):
    """Result of agent account deployment operation."""

    accounts_processed: int = 0
    accounts_deployed: int = 0
    errors: List[str] = None

    def __post_init__(self):
        self.errors = self.errors or []


@job(
    job_type="agent_account_deployer",
    name="Agent Account Deployer",
    description="Deploys agent account contracts with enhanced monitoring and error handling",
    interval_seconds=300,  # 5 minutes
    priority=JobPriority.MEDIUM,
    max_retries=2,
    retry_delay_seconds=180,
    timeout_seconds=120,
    max_concurrent=1,
    requires_blockchain=True,
    batch_size=5,
    enable_dead_letter_queue=True,
)
class AgentAccountDeployerTask(BaseTask[AgentAccountDeployResult]):
    """Task runner for deploying agent account contracts with enhanced capabilities."""

    QUEUE_TYPE = QueueMessageType.get_or_create("agent_account_deploy")

    def __init__(self, config: Optional[RunnerConfig] = None):
        super().__init__(config)

    async def _validate_config(self, context: JobContext) -> bool:
        """Validate task configuration."""
        try:
            # Check if backend wallet configuration is available
            if not config.backend_wallet or not config.backend_wallet.seed_phrase:
                logger.error(
                    "Backend wallet seed phrase not configured",
                    extra={"task": "agent_account_deploy", "validation": "config"},
                )
                return False
            return True
        except Exception as e:
            logger.error(
                "Config validation failed",
                extra={"task": "agent_account_deploy", "error": str(e)},
                exc_info=True,
            )
            return False

    async def _validate_resources(self, context: JobContext) -> bool:
        """Validate resource availability."""
        try:
            # Test agent account deploy tool initialization
            tool = AgentAccountDeployTool(seed_phrase=config.backend_wallet.seed_phrase)
            if not tool:
                logger.error(
                    "Cannot initialize AgentAccountDeployTool",
                    extra={"task": "agent_account_deploy", "validation": "resources"},
                )
                return False

            return True
        except Exception as e:
            logger.error(
                "Resource validation failed",
                extra={"task": "agent_account_deploy", "error": str(e)},
                exc_info=True,
            )
            return False

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate task-specific conditions."""
        try:
            # Get pending messages from the queue
            pending_messages = await self.get_pending_messages()
            message_count = len(pending_messages)
            logger.debug(
                "Checking pending deployment messages",
                extra={"task": "agent_account_deploy", "message_count": message_count},
            )

            if message_count == 0:
                logger.debug(
                    "No pending messages found", extra={"task": "agent_account_deploy"}
                )
                return False

            # Validate that at least one message has valid deployment data
            for message in pending_messages:
                message_data = self._parse_message_data(message.message)
                if self._validate_message_data(message_data):
                    logger.debug(
                        "Found valid deployment message",
                        extra={
                            "task": "agent_account_deploy",
                            "message_id": message.id,
                        },
                    )
                    return True

            logger.warning(
                "No valid deployment data found",
                extra={"task": "agent_account_deploy", "message_count": message_count},
            )
            return False

        except Exception as e:
            logger.error(
                "Error validating task",
                extra={"task": "agent_account_deploy", "error": str(e)},
                exc_info=True,
            )
            return False

    def _parse_message_data(self, message: Any) -> Dict[str, Any]:
        """Parse message data from either string or dictionary format."""
        if message is None:
            return {}

        if isinstance(message, dict):
            return message

        try:
            # Try to parse as JSON string
            return json.loads(message)
        except (json.JSONDecodeError, TypeError):
            logger.error(
                "Failed to parse message data",
                extra={"task": "agent_account_deploy", "message": str(message)},
            )
            return {}

    def _validate_message_data(self, message_data: Dict[str, Any]) -> bool:
        """Validate the message data contains required fields."""
        required_fields = [
            "agent_mainnet_address",
            "agent_testnet_address",
        ]
        return all(field in message_data for field in required_fields)

    def _parse_deployment_output(self, output: str) -> Optional[Dict[str, Any]]:
        """Parse deployment output JSON."""
        try:
            output_data = json.loads(output)
            if output_data and output_data.get("success") and output_data.get("data"):
                return output_data["data"]
            else:
                logger.warning(
                    "Output data missing required fields",
                    extra={
                        "task": "agent_account_deploy",
                        "has_success": bool(output_data and output_data.get("success")),
                        "has_data": bool(output_data and output_data.get("data")),
                    },
                )
                return None
        except (json.JSONDecodeError, IndexError) as e:
            logger.error(
                "Failed to parse deployment output",
                extra={
                    "task": "agent_account_deploy",
                    "error": str(e),
                    "output_length": len(output),
                },
            )
            return None

    async def _approve_aibtc_brew_contract(
        self, wallet: Wallet, agent_account_contract: str
    ):
        aibtc_brew_contract = "ST2Q77H5HHT79JK4932JCFDX4VY6XA3Y1F61A25CD.aibtc-brew-action-proposal-voting"
        approval_type = "VOTING"
        try:
            tool = AgentAccountApproveContractTool(wallet_id=wallet.id)
            result = await tool._arun(
                agent_account_contract=agent_account_contract,
                contract_to_approve=aibtc_brew_contract,
                approval_type=approval_type,
            )
            logger.info(
                "Approved aibtc-brew contract for agent account",
                extra={
                    "task": "agent_account_deploy",
                    "wallet_id": str(wallet.id),
                    "success": result.get("success", False),
                    "result": result,
                },
            )
        except Exception as e:
            logger.error(
                "Error approving aibtc-brew contract",
                extra={
                    "task": "agent_account_deploy",
                    "wallet_id": str(wallet.id),
                    "agent_account_contract": agent_account_contract,
                    "aibtc_brew_contract": aibtc_brew_contract,
                    "approval_type": approval_type,
                    "error": str(e),
                },
            )

    async def _seed_agent_wallet_with_stx(
        self, recipient: str, amount: int = 1000000, fee: int = 4000
    ):
        """Seed an agent wallet with STX from the backend wallet."""
        try:
            from app.tools.bun import BunScriptRunner

            result = BunScriptRunner.bun_run_with_seed_phrase(
                config.backend_wallet.seed_phrase,
                "stacks-wallet",
                "transfer-my-stx.ts",
                recipient,
                str(amount),
                str(fee),
                "",
            )

            if result.get("success"):
                logger.info(
                    "Seeded agent wallet with STX",
                    extra={
                        "task": "agent_account_deploy",
                        "recipient": recipient,
                        "amount": amount,
                        "fee": fee,
                        "result": result,
                    },
                )
        except Exception as e:
            logger.error(
                "Error seeding agent wallet with STX",
                extra={
                    "task": "agent_account_deploy",
                    "recipient": recipient,
                    "amount": amount,
                    "fee": fee,
                    "error": str(e),
                },
            )

    async def process_message(self, message: QueueMessage) -> Dict[str, Any]:
        """Process a single agent account deployment message."""
        message_id = message.id
        message_data = self._parse_message_data(message.message)

        logger.debug(
            "Processing deployment message",
            extra={"task": "agent_account_deploy", "message_id": message_id},
        )

        try:
            # Validate message data
            if not self._validate_message_data(message_data):
                error_msg = "Invalid message data"
                logger.error(
                    "Message validation failed",
                    extra={
                        "task": "agent_account_deploy",
                        "message_id": message_id,
                        "error": error_msg,
                    },
                )
                result = {
                    "success": False,
                    "error": f"{error_msg} in message {message_id}",
                }

                # Store result and mark as processed
                update_data = QueueMessageBase(is_processed=True, result=result)
                backend.update_queue_message(message_id, update_data)

                return result

            # Determine which agent address to use based on network configuration
            if config.network.network == "mainnet":
                agent_address = message_data["agent_mainnet_address"]
                wallet_filters = WalletFilter(mainnet_address=agent_address)
            else:
                agent_address = message_data["agent_testnet_address"]
                wallet_filters = WalletFilter(testnet_address=agent_address)

            logger.debug(
                "Looking up wallet for agent",
                extra={
                    "task": "agent_account_deploy",
                    "network": config.network.network,
                    "agent_address": agent_address,
                },
            )

            wallets = backend.list_wallets(wallet_filters)

            if not wallets:
                error_msg = f"No wallet found for {config.network.network} agent address: {agent_address}"
                logger.error(
                    "No wallet found for agent",
                    extra={
                        "task": "agent_account_deploy",
                        "network": config.network.network,
                        "agent_address": agent_address,
                    },
                )
                result = {"success": False, "error": error_msg}
                update_data = QueueMessageBase(is_processed=True, result=result)
                backend.update_queue_message(message_id, update_data)
                return result

            wallet = wallets[0]

            # 2025/10 ADDED TO SUPPORT AIBTC-BREW
            if (
                config.auto_voting_approval.enabled
                and config.network.network == "testnet"
            ):
                if wallet.testnet_address is not None:
                    await self._seed_agent_wallet_with_stx(wallet.testnet_address)

            # Get the profile associated with this wallet
            if not wallet.profile_id:
                error_msg = f"No profile associated with wallet {wallet.id}"
                logger.error(
                    "No profile associated with wallet",
                    extra={"task": "agent_account_deploy", "wallet_id": wallet.id},
                )
                result = {"success": False, "error": error_msg}
                update_data = QueueMessageBase(is_processed=True, result=result)
                backend.update_queue_message(message_id, update_data)
                return result

            profile = backend.get_profile(wallet.profile_id)
            if not profile:
                error_msg = f"Profile {wallet.profile_id} not found"
                logger.error(
                    "Profile not found",
                    extra={
                        "task": "agent_account_deploy",
                        "profile_id": wallet.profile_id,
                    },
                )
                result = {"success": False, "error": error_msg}
                update_data = QueueMessageBase(is_processed=True, result=result)
                backend.update_queue_message(message_id, update_data)
                return result

            # Determine the correct owner address based on network configuration
            if config.network.network == "mainnet":
                owner_address = profile.mainnet_address
            else:
                owner_address = profile.testnet_address

            if not owner_address:
                error_msg = f"No {config.network.network} address found for profile {profile.id}"
                logger.error(
                    "No network address found for profile",
                    extra={
                        "task": "agent_account_deploy",
                        "network": config.network.network,
                        "profile_id": profile.id,
                    },
                )
                result = {"success": False, "error": error_msg}
                update_data = QueueMessageBase(is_processed=True, result=result)
                backend.update_queue_message(message_id, update_data)
                return result

            logger.debug(
                "Using owner address for deployment",
                extra={
                    "task": "agent_account_deploy",
                    "network": config.network.network,
                    "owner_address": owner_address,
                },
            )

            # Initialize the AgentAccountDeployTool with seed phrase
            logger.debug(
                "Preparing deployment tool", extra={"task": "agent_account_deploy"}
            )
            deploy_tool = AgentAccountDeployTool(
                seed_phrase=config.backend_wallet.seed_phrase
            )

            # Execute the deployment
            logger.debug(
                "Executing deployment",
                extra={
                    "task": "agent_account_deploy",
                    "agent_address": agent_address,
                    "owner_address": owner_address,
                },
            )
            deployment_result = await deploy_tool._arun(
                owner_address=owner_address,
                agent_address=agent_address,
                network=config.network.network,
            )
            logger.debug(
                "Deployment completed",
                extra={
                    "task": "agent_account_deploy",
                    "success": deployment_result.get("success"),
                    "has_output": bool(deployment_result.get("output")),
                },
            )

            # Check if this is a ContractAlreadyExists case first
            is_contract_already_exists = (
                deployment_result.get("success") is False
                and deployment_result.get("output")
                and "ContractAlreadyExists" in deployment_result.get("output", "")
            )

            if is_contract_already_exists:
                logger.info(
                    "Contract already exists",
                    extra={
                        "task": "agent_account_deploy",
                        "agent_address": agent_address,
                    },
                )

            # Extract contract information from deployment result and update agent record
            if deployment_result.get("success") and deployment_result.get("output"):
                data = self._parse_deployment_output(deployment_result["output"])

                if data:
                    # Try to extract contract information from different possible fields
                    contract_name = None
                    deployer_address = None

                    # Check for displayName first (this is what we see in the logs)
                    if data.get("displayName"):
                        contract_name = data["displayName"]
                        logger.debug(
                            "Found contract name in displayName",
                            extra={
                                "task": "agent_account_deploy",
                                "contract_name": contract_name,
                            },
                        )

                    # Fallback to name field
                    elif data.get("name"):
                        contract_name = data["name"]
                        logger.debug(
                            "Found contract name in name field",
                            extra={
                                "task": "agent_account_deploy",
                                "contract_name": contract_name,
                            },
                        )

                    # If we have a contract name, we need to derive the deployer address
                    if contract_name:
                        # The deployer address should be derived from the backend wallet seed phrase
                        # For now, we'll use a simple approach to get the address
                        try:
                            # Use the BunScriptRunner to get the deployer address
                            from app.tools.bun import BunScriptRunner

                            address_result = BunScriptRunner.bun_run_with_seed_phrase(
                                config.backend_wallet.seed_phrase,
                                "stacks-wallet",
                                "get-my-wallet-address.ts",
                            )

                            if address_result.get("success") and address_result.get(
                                "output"
                            ):
                                deployer_address = address_result["output"].strip()

                                # Validate that we got a proper Stacks address
                                if not deployer_address:
                                    logger.error(
                                        "Empty deployer address returned",
                                        extra={"task": "agent_account_deploy"},
                                    )
                                elif not (
                                    deployer_address.startswith("ST")
                                    or deployer_address.startswith("SP")
                                ):
                                    logger.error(
                                        "Invalid Stacks address format",
                                        extra={
                                            "task": "agent_account_deploy",
                                            "address": deployer_address,
                                        },
                                    )
                                else:
                                    logger.debug(
                                        "Derived deployer address",
                                        extra={
                                            "task": "agent_account_deploy",
                                            "deployer_address": deployer_address,
                                        },
                                    )

                                    # Construct the full contract principal
                                    full_contract_principal = (
                                        f"{deployer_address}.{contract_name}"
                                    )

                                    logger.info(
                                        "Agent account deployed with contract",
                                        extra={
                                            "task": "agent_account_deploy",
                                            "contract_principal": full_contract_principal,
                                        },
                                    )

                                    # 2025/10 ADDED TO SUPPORT AIBTC-BREW
                                    if (
                                        config.auto_voting_approval.enabled
                                        and config.network.network == "testnet"
                                    ):
                                        if wallet.testnet_address is not None:
                                            await self._approve_aibtc_brew_contract(
                                                wallet, full_contract_principal
                                            )

                                    # Update the agent with the deployed contract address
                                    try:
                                        if wallet.agent_id:
                                            # Update the agent with the deployed contract address
                                            agent_update = AgentBase(
                                                account_contract=full_contract_principal
                                            )
                                            backend.update_agent(
                                                wallet.agent_id, agent_update
                                            )
                                            logger.info(
                                                "Updated agent with contract address",
                                                extra={
                                                    "task": "agent_account_deploy",
                                                    "agent_id": wallet.agent_id,
                                                    "contract_principal": full_contract_principal,
                                                },
                                            )

                                        else:
                                            logger.warning(
                                                "Wallet has no associated agent_id",
                                                extra={
                                                    "task": "agent_account_deploy",
                                                    "wallet_id": wallet.id,
                                                    "agent_address": agent_address,
                                                },
                                            )

                                    except Exception as e:
                                        logger.error(
                                            "Failed to update agent with contract address",
                                            extra={
                                                "task": "agent_account_deploy",
                                                "error": str(e),
                                                "agent_id": wallet.agent_id,
                                            },
                                            exc_info=True,
                                        )
                                # Don't fail the entire deployment if agent update fails
                            else:
                                logger.error(
                                    "Failed to derive deployer address",
                                    extra={
                                        "task": "agent_account_deploy",
                                        "result": str(address_result),
                                    },
                                )

                        except Exception as e:
                            logger.error(
                                "Error deriving deployer address",
                                extra={"task": "agent_account_deploy", "error": str(e)},
                                exc_info=True,
                            )
                    else:
                        logger.warning(
                            "No contract name found in deployment result",
                            extra={"task": "agent_account_deploy"},
                        )
                else:
                    logger.warning(
                        "No data found in deployment result",
                        extra={"task": "agent_account_deploy"},
                    )
            else:
                logger.warning(
                    "Deployment result missing required fields",
                    extra={
                        "task": "agent_account_deploy",
                        "has_success": bool(deployment_result.get("success")),
                        "has_output": bool(deployment_result.get("output")),
                    },
                )

            # Also check for failed deployments with ContractAlreadyExists error
            if deployment_result.get("success") is False and deployment_result.get(
                "output"
            ):
                try:
                    # Try to parse JSON from the output, handling multiple possible formats
                    output_lines = deployment_result["output"].split("\n")
                    output_data = None

                    # Try to find a line that contains valid JSON
                    for line in reversed(output_lines):  # Start from the end
                        line = line.strip()
                        if line and line.startswith("{") and line.endswith("}"):
                            try:
                                output_data = json.loads(line)
                                break
                            except json.JSONDecodeError:
                                continue

                    # If no valid JSON found, try to extract from the raw output string
                    if (
                        not output_data
                        and "ContractAlreadyExists" in deployment_result["output"]
                    ):
                        # Create a synthetic output_data structure for processing
                        output_data = {
                            "success": False,
                            "message": deployment_result["output"],
                        }

                    if output_data and (
                        output_data.get("success") is False
                        and "ContractAlreadyExists"
                        in str(output_data.get("message", ""))
                    ):
                        logger.info(
                            "Contract already exists - extracting contract info",
                            extra={"task": "agent_account_deploy"},
                        )

                        # Initialize variables
                        contract_name = None
                        deployer_address = None

                        # Method 1: Extract aibtc-acct pattern directly from the message
                        message = output_data.get("message", "")
                        aibtc_acct_match = re.search(
                            r"aibtc-acct-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}",
                            message,
                        )
                        if aibtc_acct_match:
                            contract_name = aibtc_acct_match.group(0)
                            logger.debug(
                                "Found aibtc-acct pattern in error",
                                extra={
                                    "task": "agent_account_deploy",
                                    "contract_name": contract_name,
                                },
                            )

                        # Method 2: Try to extract from contract_identifier if available
                        if not contract_name and "contract_identifier" in message:
                            contract_id_match = re.search(
                                r'"contract_identifier":"([^"]+)"', message
                            )
                            if contract_id_match:
                                contract_identifier = contract_id_match.group(1)
                                # Extract deployer address and contract name from identifier
                                if "." in contract_identifier:
                                    deployer_address, contract_name = (
                                        contract_identifier.split(".", 1)
                                    )
                                    logger.debug(
                                        "Found contract identifier",
                                        extra={
                                            "task": "agent_account_deploy",
                                            "contract_identifier": contract_identifier,
                                            "deployer": deployer_address,
                                            "contract": contract_name,
                                        },
                                    )

                        # Method 2b: Also try to extract deployer address from contract_identifier even if we already have contract_name
                        if (
                            contract_name
                            and not deployer_address
                            and "contract_identifier" in message
                        ):
                            contract_id_match = re.search(
                                r'"contract_identifier":"([^"]+)"', message
                            )
                            if contract_id_match:
                                contract_identifier = contract_id_match.group(1)
                                if "." in contract_identifier:
                                    deployer_address, _ = contract_identifier.split(
                                        ".", 1
                                    )
                                    logger.debug(
                                        "Extracted deployer from contract_identifier",
                                        extra={
                                            "task": "agent_account_deploy",
                                            "deployer_address": deployer_address,
                                        },
                                    )

                        # Method 3: Try to extract from reason_data if available
                        if not contract_name and "reason_data" in message:
                            reason_data_match = re.search(
                                r'"reason_data":{[^}]*"contract_identifier":"([^"]+)"',
                                message,
                            )
                            if reason_data_match:
                                contract_identifier = reason_data_match.group(1)
                                if "." in contract_identifier:
                                    deployer_address, contract_name = (
                                        contract_identifier.split(".", 1)
                                    )
                                    logger.debug(
                                        "Found contract identifier in reason_data",
                                        extra={
                                            "task": "agent_account_deploy",
                                            "contract_identifier": contract_identifier,
                                            "deployer": deployer_address,
                                            "contract": contract_name,
                                        },
                                    )

                        # Method 3b: Also try to extract deployer address from reason_data even if we already have contract_name
                        if (
                            contract_name
                            and not deployer_address
                            and "reason_data" in message
                        ):
                            reason_data_match = re.search(
                                r'"reason_data":{[^}]*"contract_identifier":"([^"]+)"',
                                message,
                            )
                            if reason_data_match:
                                contract_identifier = reason_data_match.group(1)
                                if "." in contract_identifier:
                                    deployer_address, _ = contract_identifier.split(
                                        ".", 1
                                    )
                                    logger.debug(
                                        "Extracted deployer from reason_data",
                                        extra={
                                            "task": "agent_account_deploy",
                                            "deployer_address": deployer_address,
                                        },
                                    )

                        # If we still don't have a deployer address, derive it from seed phrase
                        if contract_name and not deployer_address:
                            try:
                                from app.tools.bun import BunScriptRunner

                                address_result = (
                                    BunScriptRunner.bun_run_with_seed_phrase(
                                        config.backend_wallet.seed_phrase,
                                        "stacks-wallet",
                                        "get-my-wallet-address.ts",
                                    )
                                )

                                if address_result.get("success") and address_result.get(
                                    "output"
                                ):
                                    deployer_address = address_result["output"].strip()
                                    logger.debug(
                                        "Derived deployer address from seed",
                                        extra={
                                            "task": "agent_account_deploy",
                                            "deployer_address": deployer_address,
                                        },
                                    )
                            except Exception as e:
                                logger.error(
                                    "Error deriving deployer address",
                                    extra={
                                        "task": "agent_account_deploy",
                                        "error": str(e),
                                    },
                                    exc_info=True,
                                )

                        # If we have both contract name and deployer address, update the agent
                        if contract_name and deployer_address:
                            full_contract_principal = (
                                f"{deployer_address}.{contract_name}"
                            )

                            logger.info(
                                "Found existing contract",
                                extra={
                                    "task": "agent_account_deploy",
                                    "contract_principal": full_contract_principal,
                                },
                            )

                            try:
                                if wallet.agent_id:
                                    agent_update = AgentBase(
                                        account_contract=full_contract_principal
                                    )
                                    backend.update_agent(wallet.agent_id, agent_update)
                                    logger.info(
                                        "Updated agent with existing contract",
                                        extra={
                                            "task": "agent_account_deploy",
                                            "agent_id": wallet.agent_id,
                                            "contract_principal": full_contract_principal,
                                        },
                                    )

                                else:
                                    logger.warning(
                                        "Wallet has no associated agent_id for existing contract",
                                        extra={
                                            "task": "agent_account_deploy",
                                            "wallet_id": wallet.id,
                                            "agent_address": agent_address,
                                        },
                                    )
                            except Exception as e:
                                logger.error(
                                    "Failed to update agent with existing contract",
                                    extra={
                                        "task": "agent_account_deploy",
                                        "error": str(e),
                                        "agent_id": wallet.agent_id,
                                    },
                                    exc_info=True,
                                )
                        else:
                            logger.warning(
                                "Could not extract contract information from error",
                                extra={
                                    "task": "agent_account_deploy",
                                    "has_contract_name": bool(contract_name),
                                    "has_deployer_address": bool(deployer_address),
                                },
                            )

                except (json.JSONDecodeError, Exception) as e:
                    logger.error(
                        "Failed to parse failed deployment output",
                        extra={"task": "agent_account_deploy", "error": str(e)},
                        exc_info=True,
                    )
                    # Still treat ContractAlreadyExists as successful even if parsing fails
                    if is_contract_already_exists:
                        logger.info(
                            "Treating ContractAlreadyExists as successful despite parsing error",
                            extra={"task": "agent_account_deploy"},
                        )

            # Determine if this should be considered a successful deployment
            # Both successful deployments and ContractAlreadyExists should be considered successful
            deployed = (
                deployment_result.get("success") is True or is_contract_already_exists
            )

            result = {
                "success": True,
                "deployed": deployed,
                "result": deployment_result,
            }

            # Store result and mark as processed
            update_data = QueueMessageBase(is_processed=True, result=result)
            backend.update_queue_message(message_id, update_data)

            logger.info(
                "Successfully deployed agent account",
                extra={
                    "task": "agent_account_deploy",
                    "message_id": message_id,
                    "deployed": deployed,
                },
            )

            return result

        except Exception as e:
            error_msg = f"Error processing message {message_id}: {str(e)}"
            logger.error(
                "Error processing message",
                extra={
                    "task": "agent_account_deploy",
                    "message_id": message_id,
                    "error": str(e),
                },
                exc_info=True,
            )
            result = {"success": False, "error": error_msg}

            # Store result even for failed processing
            update_data = QueueMessageBase(result=result)
            backend.update_queue_message(message_id, update_data)

            return result

    async def get_pending_messages(self) -> List[QueueMessage]:
        """Get all unprocessed messages from the queue."""
        filters = QueueMessageFilter(type=self.QUEUE_TYPE, is_processed=False)
        messages = backend.list_queue_messages(filters=filters)

        # Messages are already parsed by the backend, but we log them for debugging
        for message in messages:
            logger.debug(
                "Queue message raw data",
                extra={
                    "task": "agent_account_deploy",
                    "message_id": message.id,
                    "message": repr(message.message),
                },
            )

        return messages

    def _should_retry_on_error(self, error: Exception, context: JobContext) -> bool:
        """Determine if error should trigger retry."""
        # Retry on network errors, blockchain timeouts
        retry_errors = (
            ConnectionError,
            TimeoutError,
        )

        # Don't retry on validation errors
        if "invalid message data" in str(error).lower():
            return False
        if "missing" in str(error).lower() and "required" in str(error).lower():
            return False

        return isinstance(error, retry_errors)

    async def _handle_execution_error(
        self, error: Exception, context: JobContext
    ) -> Optional[List[AgentAccountDeployResult]]:
        """Handle execution errors with recovery logic."""
        if "blockchain" in str(error).lower() or "contract" in str(error).lower():
            logger.warning(
                "Blockchain/contract error - will retry",
                extra={"task": "agent_account_deploy", "error": str(error)},
            )
            return None

        if isinstance(error, (ConnectionError, TimeoutError)):
            logger.warning(
                "Network error - will retry",
                extra={"task": "agent_account_deploy", "error": str(error)},
            )
            return None

        # For validation errors, don't retry
        return [
            AgentAccountDeployResult(
                success=False,
                message=f"Unrecoverable error: {str(error)}",
                error=error,
            )
        ]

    async def _post_execution_cleanup(
        self, context: JobContext, results: List[AgentAccountDeployResult]
    ) -> None:
        """Cleanup after task execution."""
        logger.debug("Task cleanup completed", extra={"task": "agent_account_deploy"})

    async def _execute_impl(
        self, context: JobContext
    ) -> List[AgentAccountDeployResult]:
        """Run the agent account deployment task with batch processing."""
        pending_messages = await self.get_pending_messages()
        message_count = len(pending_messages)
        logger.debug(
            "Found pending deployment messages",
            extra={"task": "agent_account_deploy", "message_count": message_count},
        )

        if not pending_messages:
            return [
                AgentAccountDeployResult(
                    success=True,
                    message="No pending messages found",
                    accounts_processed=0,
                    accounts_deployed=0,
                )
            ]

        # Process each message in batches
        processed_count = 0
        deployed_count = 0
        errors = []
        batch_size = getattr(context, "batch_size", 5)

        logger.info(
            "Processing deployment messages",
            extra={
                "task": "agent_account_deploy",
                "message_count": message_count,
                "batch_size": batch_size,
            },
        )

        # Process messages in batches
        for i in range(0, len(pending_messages), batch_size):
            batch = pending_messages[i : i + batch_size]

            for message in batch:
                try:
                    result = await self.process_message(message)
                    processed_count += 1

                    if result.get("success"):
                        if result.get("deployed", False):
                            deployed_count += 1
                    else:
                        errors.append(result.get("error", "Unknown error"))

                    time.sleep(5)

                except Exception as e:
                    error_msg = f"Exception processing message {message.id}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(
                        "Exception processing message",
                        extra={
                            "task": "agent_account_deploy",
                            "message_id": message.id,
                            "error": str(e),
                        },
                        exc_info=True,
                    )

        logger.info(
            "Agent account deployment completed",
            extra={
                "task": "agent_account_deploy",
                "processed": processed_count,
                "deployed": deployed_count,
                "errors": len(errors),
            },
        )

        return [
            AgentAccountDeployResult(
                success=True,
                message=f"Processed {processed_count} account(s), deployed {deployed_count} account(s)",
                accounts_processed=processed_count,
                accounts_deployed=deployed_count,
                errors=errors,
            )
        ]


# Create instance for auto-registration
agent_account_deployer = AgentAccountDeployerTask()
