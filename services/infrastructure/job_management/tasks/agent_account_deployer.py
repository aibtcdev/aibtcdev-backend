"""Agent account deployment task implementation."""

import json
from dataclasses import dataclass
import re
import time
from typing import Any, Dict, List, Optional

from backend.factory import backend
from backend.models import (
    AgentBase,
    QueueMessage,
    QueueMessageBase,
    QueueMessageFilter,
    QueueMessageType,
    WalletFilter,
)
from config import config
from lib.logger import configure_logger
from services.infrastructure.job_management.base import (
    BaseTask,
    JobContext,
    RunnerConfig,
    RunnerResult,
)
from services.infrastructure.job_management.decorators import JobPriority, job
from tools.agent_account import AgentAccountDeployTool

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
                    "Backend wallet seed phrase not configured for agent account deployment"
                )
                return False
            return True
        except Exception as e:
            logger.error(
                f"Error validating agent account deployer config: {str(e)}",
                exc_info=True,
            )
            return False

    async def _validate_resources(self, context: JobContext) -> bool:
        """Validate resource availability."""
        try:
            # Test agent account deploy tool initialization
            tool = AgentAccountDeployTool(seed_phrase=config.backend_wallet.seed_phrase)
            if not tool:
                logger.error("Cannot initialize AgentAccountDeployTool")
                return False

            return True
        except Exception as e:
            logger.error(f"Resource validation failed: {str(e)}")
            return False

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate task-specific conditions."""
        try:
            # Get pending messages from the queue
            pending_messages = await self.get_pending_messages()
            message_count = len(pending_messages)
            logger.debug(
                f"Found {message_count} pending agent account deployment messages"
            )

            if message_count == 0:
                logger.debug("No pending agent account deployment messages found")
                return False

            # Validate that at least one message has valid deployment data
            for message in pending_messages:
                message_data = self._parse_message_data(message.message)
                if self._validate_message_data(message_data):
                    logger.debug("Found valid agent account deployment message")
                    return True

            logger.warning("No valid deployment data found in pending messages")
            return False

        except Exception as e:
            logger.error(
                f"Error validating agent account deployment task: {str(e)}",
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
            logger.error(f"Failed to parse message data: {message}")
            return {}

    def _validate_message_data(self, message_data: Dict[str, Any]) -> bool:
        """Validate the message data contains required fields."""
        required_fields = [
            "agent_mainnet_address",
            "agent_testnet_address",
            "dao_token_contract",
            "dao_token_dex_contract",
        ]
        return all(field in message_data for field in required_fields)

    async def process_message(self, message: QueueMessage) -> Dict[str, Any]:
        """Process a single agent account deployment message."""
        message_id = message.id
        message_data = self._parse_message_data(message.message)

        logger.debug(f"Processing agent account deployment message {message_id}")

        try:
            # Validate message data
            if not self._validate_message_data(message_data):
                error_msg = f"Invalid message data in message {message_id}"
                logger.error(error_msg)
                result = {"success": False, "error": error_msg}

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
                f"Looking up wallet for {config.network.network} agent address: {agent_address}"
            )

            wallets = backend.list_wallets(wallet_filters)

            if not wallets:
                error_msg = f"No wallet found for {config.network.network} agent address: {agent_address}"
                logger.error(error_msg)
                result = {"success": False, "error": error_msg}
                update_data = QueueMessageBase(is_processed=True, result=result)
                backend.update_queue_message(message_id, update_data)
                return result

            wallet = wallets[0]

            # Get the profile associated with this wallet
            if not wallet.profile_id:
                error_msg = f"No profile associated with wallet {wallet.id}"
                logger.error(error_msg)
                result = {"success": False, "error": error_msg}
                update_data = QueueMessageBase(is_processed=True, result=result)
                backend.update_queue_message(message_id, update_data)
                return result

            profile = backend.get_profile(wallet.profile_id)
            if not profile:
                error_msg = f"Profile {wallet.profile_id} not found"
                logger.error(error_msg)
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
                logger.error(error_msg)
                result = {"success": False, "error": error_msg}
                update_data = QueueMessageBase(is_processed=True, result=result)
                backend.update_queue_message(message_id, update_data)
                return result

            logger.debug(
                f"Using owner address {owner_address} for {config.network.network} network"
            )

            # Initialize the AgentAccountDeployTool with seed phrase
            logger.debug("Preparing to deploy agent account")
            deploy_tool = AgentAccountDeployTool(
                seed_phrase=config.backend_wallet.seed_phrase
            )

            # Execute the deployment
            logger.debug("Executing deployment...")
            deployment_result = await deploy_tool._arun(
                owner_address=owner_address,
                agent_address=agent_address,
                dao_token_contract=message_data["dao_token_contract"],
                dao_token_dex_contract=message_data["dao_token_dex_contract"],
            )
            logger.debug(f"Deployment result: {deployment_result}")

            # Extract contract information from deployment result and update agent record
            if deployment_result.get("success") and deployment_result.get("output"):
                # Parse the JSON output to get the actual response data
                try:
                    output_data = json.loads(
                        deployment_result["output"].split("\n")[-1]
                    )  # Get the last JSON line
                    if output_data.get("success") and output_data.get("data"):
                        data = output_data["data"]
                    else:
                        logger.warning("Output data missing success or data fields")
                        data = None
                except (json.JSONDecodeError, IndexError) as e:
                    logger.error(f"Failed to parse deployment output: {str(e)}")
                    data = None

                if data:
                    # Try to extract contract information from different possible fields
                    contract_name = None
                    deployer_address = None

                    # Check for displayName first (this is what we see in the logs)
                    if data.get("displayName"):
                        contract_name = data["displayName"]
                        logger.debug(
                            f"Found contract name in displayName: {contract_name}"
                        )

                    # Fallback to name field
                    elif data.get("name"):
                        contract_name = data["name"]
                        logger.debug(
                            f"Found contract name in name field: {contract_name}"
                        )

                    # If we have a contract name, we need to derive the deployer address
                    if contract_name:
                        # The deployer address should be derived from the backend wallet seed phrase
                        # For now, we'll use a simple approach to get the address
                        try:
                            # Use the BunScriptRunner to get the deployer address
                            from tools.bun import BunScriptRunner

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
                                        "Empty deployer address returned from script"
                                    )
                                elif not (
                                    deployer_address.startswith("ST")
                                    or deployer_address.startswith("SP")
                                ):
                                    logger.error(
                                        f"Invalid Stacks address format: {deployer_address}"
                                    )
                                else:
                                    logger.debug(
                                        f"Derived deployer address: {deployer_address}"
                                    )

                                    # Construct the full contract principal
                                    full_contract_principal = (
                                        f"{deployer_address}.{contract_name}"
                                    )

                                    logger.info(
                                        f"Agent account deployed with contract: {full_contract_principal}"
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
                                                f"Updated agent {wallet.agent_id} with contract address: {full_contract_principal}"
                                            )
                                        else:
                                            logger.warning(
                                                f"Wallet {wallet.id} found for address {agent_address} but no associated agent_id"
                                            )

                                    except Exception as e:
                                        logger.error(
                                            f"Failed to update agent with contract address: {str(e)}",
                                            exc_info=True,
                                        )
                                # Don't fail the entire deployment if agent update fails
                            else:
                                logger.error(
                                    f"Failed to derive deployer address: {address_result}"
                                )

                        except Exception as e:
                            logger.error(
                                f"Error deriving deployer address: {str(e)}",
                                exc_info=True,
                            )
                    else:
                        logger.warning("No contract name found in deployment result")
                else:
                    logger.warning("No contract name found in deployment result")
            else:
                logger.warning("Deployment result missing success or output fields")

            # Also check for failed deployments with ContractAlreadyExists error
            if deployment_result.get("success") is False and deployment_result.get(
                "output"
            ):
                try:
                    # Parse the JSON output to get the actual response data
                    output_data = json.loads(
                        deployment_result["output"].split("\n")[-1]
                    )  # Get the last JSON line

                    if output_data.get(
                        "success"
                    ) is False and "ContractAlreadyExists" in str(
                        output_data.get("message", "")
                    ):
                        logger.info(
                            "Contract already exists - attempting to extract contract info from error"
                        )

                        # Method 1: Try to parse the nested JSON in the error message
                        message = output_data.get("message", "")
                        if "displayName" in message:
                            # Extract displayName from the error message JSON
                            display_name_match = re.search(
                                r'"displayName":"([^"]+)"', message
                            )
                            if display_name_match:
                                display_name = display_name_match.group(1)
                                # Use the base contract name instead of displayName
                                contract_name = "aibtc-agent-account"
                                logger.debug(
                                    f"Found displayName in error: {display_name}, using contract name: {contract_name}"
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
                                        f"Found contract identifier: {contract_identifier}"
                                    )
                                    logger.debug(
                                        f"Extracted deployer: {deployer_address}, contract: {contract_name}"
                                    )

                        # If we still don't have a deployer address, derive it from seed phrase
                        if contract_name and not deployer_address:
                            try:
                                from tools.bun import BunScriptRunner

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
                                        f"Derived deployer address: {deployer_address}"
                                    )
                            except Exception as e:
                                logger.error(
                                    f"Error deriving deployer address: {str(e)}"
                                )

                        # If we have both contract name and deployer address, update the agent
                        if contract_name and deployer_address:
                            full_contract_principal = (
                                f"{deployer_address}.{contract_name}"
                            )

                            logger.info(
                                f"Contract already exists: {full_contract_principal}"
                            )

                            try:
                                if wallet.agent_id:
                                    agent_update = AgentBase(
                                        account_contract=full_contract_principal
                                    )
                                    backend.update_agent(wallet.agent_id, agent_update)
                                    logger.info(
                                        f"Updated agent {wallet.agent_id} with existing contract: {full_contract_principal}"
                                    )
                                else:
                                    logger.warning(
                                        f"Wallet {wallet.id} found for address {agent_address} but no associated agent_id"
                                    )
                            except Exception as e:
                                logger.error(
                                    f"Failed to update agent with existing contract: {str(e)}",
                                    exc_info=True,
                                )
                        else:
                            logger.warning(
                                "Could not extract contract information from ContractAlreadyExists error"
                            )

                except (json.JSONDecodeError, Exception) as e:
                    logger.error(f"Failed to parse failed deployment output: {str(e)}")

            result = {"success": True, "deployed": True, "result": deployment_result}

            # Store result and mark as processed
            update_data = QueueMessageBase(is_processed=True, result=result)
            backend.update_queue_message(message_id, update_data)

            logger.info(f"Successfully deployed agent account for message {message_id}")

            return result

        except Exception as e:
            error_msg = f"Error processing message {message_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
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
            logger.debug(f"Queue message raw data: {message.message!r}")

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
            logger.warning(f"Blockchain/contract error: {str(error)}, will retry")
            return None

        if isinstance(error, (ConnectionError, TimeoutError)):
            logger.warning(f"Network error: {str(error)}, will retry")
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
        logger.debug("Agent account deployer task cleanup completed")

    async def _execute_impl(
        self, context: JobContext
    ) -> List[AgentAccountDeployResult]:
        """Run the agent account deployment task with batch processing."""
        pending_messages = await self.get_pending_messages()
        message_count = len(pending_messages)
        logger.debug(f"Found {message_count} pending agent account deployment messages")

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

        logger.info(f"Processing {message_count} agent account deployment messages")

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
                    logger.error(error_msg, exc_info=True)

        logger.info(
            f"Agent account deployment completed - Processed: {processed_count}, "
            f"Deployed: {deployed_count}, Errors: {len(errors)}"
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
