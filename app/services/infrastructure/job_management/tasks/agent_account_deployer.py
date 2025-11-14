"""Agent account deployment task implementation."""

import json
from dataclasses import dataclass
import time
from typing import Any, Dict, List, Optional

from app.backend.factory import backend
from app.backend.models import (
    AgentBase,
    QueueMessage,
    QueueMessageBase,
    QueueMessageFilter,
    QueueMessageType,
    WalletFilter,
)
from app.config import config
from app.lib.logger import configure_logger
from app.lib.utils import parse_agent_tool_result_strict
from app.services.infrastructure.job_management.base import (
    BaseTask,
    JobContext,
    RunnerConfig,
    RunnerResult,
)
from app.services.infrastructure.job_management.decorators import JobPriority, job
from app.tools.agent_account import AgentAccountDeployTool

logger = configure_logger(__name__)


@dataclass
class AgentAccountDeployResult(RunnerResult):
    """Result of agent account deployment operation."""

    accounts_processed: int = 0
    accounts_deployed: int = 0
    errors: Optional[List[str]] = None

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
            parsed_result = parse_agent_tool_result_strict(deployment_result)

            logger.debug(
                "Deployment completed",
                extra={
                    "task": "agent_account_deploy",
                    "py_success": parsed_result.py_success,
                    "ts_success": parsed_result.ts_success,
                    "ts_data": parsed_result.ts_data,
                },
            )

            # handle python tool failure
            if parsed_result.py_success is False:
                error_msg = "Deployer tool failed in Python layer"
                logger.error(
                    error_msg,
                    extra={
                        "py_success": parsed_result.py_success,
                        "py_error": parsed_result.py_error,
                        "ts_data": parsed_result.ts_data,
                    },
                )
                result = {"success": False, "error": error_msg}
                return result

            # handle typescript tool failure
            contract_already_exists = False
            if parsed_result.ts_success is False:
                tool_output_message_str = str(parsed_result.ts_data)
                # handle special case - already deployed contract
                if "ContractAlreadyExists" in tool_output_message_str:
                    logger.warning(
                        "Contract already exists; treating as successful deployment"
                    )
                    contract_already_exists = True
                else:
                    error_msg = "Deployer tool failed in TypeScript layer"
                    logger.error(
                        error_msg,
                        extra={
                            "ts_success": parsed_result.ts_success,
                            "ts_data": parsed_result.ts_data,
                        },
                    )
                    result = {"success": False, "error": error_msg}
                    return result

            # get the contract name from tool data
            contract_name = (
                parsed_result.ts_data.get("displayName")
                if isinstance(parsed_result.ts_data, dict)
                else None
            )

            if contract_name is None:
                error_msg = "Unable to find contract name in tool output"
                logger.error(
                    error_msg,
                    extra={
                        "ts_data": parsed_result.ts_data,
                    },
                )
                result = {"success": False, "error": error_msg}
                return result

            # get deployer account address using script
            try:
                # Use the BunScriptRunner to get the deployer address
                from app.tools.bun import BunScriptRunner

                address_result = BunScriptRunner.bun_run_with_seed_phrase(
                    config.backend_wallet.seed_phrase,
                    "stacks-wallet",
                    "get-my-wallet-address.ts",
                )

                parsed_address_result = parse_agent_tool_result_strict(address_result)

                if (
                    parsed_address_result.py_success is False
                    or parsed_address_result.ts_success is False
                ):
                    error_msg = "Deployer tool failed to get deployer address"
                    logger.error(
                        error_msg,
                        extra={
                            "py_success": parsed_address_result.py_success,
                            "py_error": parsed_address_result.py_error,
                            "ts_success": parsed_address_result.ts_success,
                            "ts_data": parsed_address_result.ts_data,
                        },
                    )
                    result = {"success": False, "error": error_msg}
                    return result

                # returned as a string in the tool
                deployer_address = str(parsed_address_result.ts_data)

                if not deployer_address or not deployer_address.startswith(
                    ("SP", "SM", "ST", "SN")
                ):
                    error_msg = "Invalid Stacks address format"
                    logger.error(
                        error_msg,
                        extra={
                            "task": "agent_account_deploy",
                            "deployer_address": deployer_address,
                        },
                    )
                    result = {"success": False, "error": error_msg}
                    return result

                logger.debug(
                    "Derived deployer address",
                    extra={
                        "task": "agent_account_deploy",
                        "deployer_address": deployer_address,
                    },
                )

                # Construct the full contract principal
                full_contract_principal = f"{deployer_address}.{contract_name}"

                logger.info(
                    "Agent account contract deployed",
                    extra={
                        "task": "agent_account_deploy",
                        "contract_principal": full_contract_principal,
                    },
                )

                # verify we have the agent_id before continuing
                if wallet.agent_id is None:
                    error_msg = "Unable to get agent id from wallet to update info"
                    logger.warning(
                        error_msg,
                        extra={"wallet_id": wallet.id, "agent_id": wallet.agent_id},
                    )
                    result = {"success": False, "error": error_msg}
                    return result

                # update the agent with the deployed contract address
                try:
                    # Update the agent with the deployed contract address
                    agent_update = AgentBase(account_contract=full_contract_principal)
                    backend.update_agent(wallet.agent_id, agent_update)
                    logger.info(
                        "Updated agent with contract address",
                        extra={
                            "task": "agent_account_deploy",
                            "agent_id": wallet.agent_id,
                            "contract_principal": full_contract_principal,
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
            except Exception as e:
                error_msg = "Failed to get deployer address from tool"
                logger.error(
                    error_msg,
                    extra={
                        "task": "agent_account_deploy",
                        "error": str(e),
                        "agent_id": wallet.agent_id,
                    },
                )

            final_result = {
                "success": True
                if contract_already_exists
                else parsed_result.py_success,
                "deployed": parsed_result.ts_success or contract_already_exists,
                "result": parsed_result.ts_data,
            }

            # Store result and mark as processed
            update_data = QueueMessageBase(is_processed=True, result=final_result)
            backend.update_queue_message(message_id, update_data)

            logger.info(
                "Successfully deployed agent account",
                extra={
                    "task": "agent_account_deploy",
                    "message_id": message_id,
                    "deployed": final_result["deployed"],
                },
            )

            return final_result

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
