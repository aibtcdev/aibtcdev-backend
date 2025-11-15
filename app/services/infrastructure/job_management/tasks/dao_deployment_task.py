from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.backend.factory import backend
from app.backend.models import (
    DAOFilter,
    QueueMessage,
    QueueMessageBase,
    QueueMessageFilter,
    QueueMessageType,
)
from app.lib.logger import configure_logger
from app.services.ai.simple_workflows import execute_workflow_stream
from app.tools.tools_factory import filter_tools_by_names, initialize_tools

from ..base import BaseTask, JobContext, RunnerConfig, RunnerResult
from ..decorators import JobPriority, job

logger = configure_logger(__name__)


@dataclass
class DAODeploymentResult(RunnerResult):
    """Result of DAO deployment operation."""

    dao_id: Optional[UUID] = None
    deployment_data: Optional[Dict[str, Any]] = None
    daos_processed: int = 0
    deployments_successful: int = 0


@job(
    job_type="dao_deployment",
    name="DAO Deployment Processor",
    description="Processes DAO deployment requests with enhanced monitoring and error handling",
    interval_seconds=60,
    priority=JobPriority.HIGH,
    max_retries=2,
    retry_delay_seconds=120,
    timeout_seconds=600,
    max_concurrent=1,
    requires_blockchain=True,
    batch_size=1,
    enable_dead_letter_queue=True,
)
class DAODeploymentTask(BaseTask[DAODeploymentResult]):
    """Task for processing DAO deployments with enhanced capabilities."""

    def __init__(self, config: Optional[RunnerConfig] = None):
        super().__init__(config)
        self._pending_messages = None
        self.tools_map_all = initialize_tools(None, None)
        self.tools_map = filter_tools_by_names(
            ["contract_deploy_dao"], self.tools_map_all
        )
        logger.debug(
            "Initialized DAO deployment tools",
            extra={"tools_count": len(self.tools_map)},
        )

    async def _validate_config(self, context: JobContext) -> bool:
        """Validate DAO deployment task configuration."""
        try:
            if not self.tools_map:
                logger.debug(
                    "No DAO deployment tools available",
                )
                return False

            if not self.tools_map_all:
                logger.debug("Tools not properly initialized")
                return False

            # Configuration validation passed
            logger.debug("Configuration validation passed")

            return True
        except Exception as e:
            logger.error(
                "Error validating config",
                extra={"error": str(e)},
                exc_info=True,
            )
            return False

    async def _validate_resources(self, context: JobContext) -> bool:
        """Validate resource availability for DAO deployment."""
        try:
            # Check if we have required tools initialized
            if not self.tools_map:
                logger.error(
                    "DAO deployment tools not available",
                )
                return False

            return True
        except Exception as e:
            logger.error(
                "Resource validation failed",
                extra={"error": str(e)},
            )
            return False

    async def _validate_prerequisites(self, context: JobContext) -> bool:
        """Validate DAO deployment task prerequisites."""
        try:
            # Check for pending DAOs first
            pending_daos = backend.list_daos(
                filters=DAOFilter(
                    is_deployed=False,
                    is_broadcasted=True,
                )
            )
            if pending_daos:
                logger.info(
                    "Found pending Twitter DAOs, skipping queue processing",
                    extra={
                        "pending_count": len(pending_daos),
                    },
                )
                return False

            # Cache pending messages for later use
            self._pending_messages = backend.list_queue_messages(
                filters=QueueMessageFilter(
                    type=QueueMessageType.get_or_create("dao_deployment"),
                    is_processed=False,
                )
            )
            return True
        except Exception as e:
            logger.error(
                "Error validating prerequisites",
                extra={"error": str(e)},
                exc_info=True,
            )
            self._pending_messages = None
            return False

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate DAO deployment task-specific conditions."""
        try:
            if not self._pending_messages:
                logger.debug("No pending messages found")
                return False

            # Validate each message has required parameters
            valid_messages = []
            for message in self._pending_messages:
                if await self._is_message_valid(message):
                    valid_messages.append(message)

            self._pending_messages = valid_messages
            message_count = len(valid_messages)

            if message_count > 0:
                logger.debug(
                    "Found valid messages",
                    extra={"message_count": message_count},
                )
                return True

            logger.debug("No valid messages to process")
            return False

        except Exception as e:
            logger.error(
                "Error in task validation",
                extra={"error": str(e)},
                exc_info=True,
            )
            return False

    async def _is_message_valid(self, message: QueueMessage) -> bool:
        """Check if a message has valid DAO deployment parameters."""
        try:
            if not message.message or not isinstance(message.message, dict):
                return False

            params = message.message.get("parameters", {})
            required_params = [
                "token_symbol",
                "token_name",
                "token_description",
                "token_max_supply",
                "token_decimals",
                "origin_address",
                "mission",
            ]

            # Check all required parameters exist and are not empty
            for param in required_params:
                if param not in params or not params[param]:
                    logger.debug(
                        "Message missing required parameter",
                        extra={
                            "message_id": str(message.id),
                            "missing_param": param,
                        },
                    )
                    return False

            return True
        except Exception:
            return False

    async def _validate_message(
        self, message: QueueMessage
    ) -> Optional[DAODeploymentResult]:
        """Validate a single DAO deployment message before processing."""
        try:
            params = message.message.get("parameters", {})
            required_params = [
                "token_symbol",
                "token_name",
                "token_description",
                "token_max_supply",
                "token_decimals",
                "origin_address",
                "mission",
            ]

            missing_params = [p for p in required_params if p not in params]
            if missing_params:
                return DAODeploymentResult(
                    success=False,
                    message=f"Missing required parameters: {', '.join(missing_params)}",
                )

            return None  # Validation passed

        except Exception as e:
            logger.error(
                "Error validating message",
                extra={
                    "message_id": str(message.id),
                    "error": str(e),
                },
                exc_info=True,
            )
            return DAODeploymentResult(
                success=False,
                message=f"Error validating message: {str(e)}",
                error=e,
            )

    def _get_dao_deployment_parameters(self, message: QueueMessage) -> Optional[str]:
        """Extract and format DAO deployment parameters from message."""
        try:
            params = message.message["parameters"]
            return (
                f"Please deploy a DAO with the following parameters:\n"
                f"Token Symbol: {params['token_symbol']}\n"
                f"Token Name: {params['token_name']}\n"
                f"Token Description: {params['token_description']}\n"
                f"Token Max Supply: {params['token_max_supply']}\n"
                f"Token Decimals: {params['token_decimals']}\n"
                f"Origin Address: {params['origin_address']}\n"
                f"Tweet Origin: {message.tweet_id}\n"
                f"Mission: {params['mission']}"
            )
        except KeyError as e:
            logger.error(
                "Missing required parameter in message",
                extra={"missing_param": str(e)},
            )
            return None

    async def _process_dao_deployment_message(
        self, message: QueueMessage
    ) -> DAODeploymentResult:
        """Process a single DAO deployment message with enhanced error handling."""
        try:
            # Validate message first
            validation_result = await self._validate_message(message)
            if validation_result:
                return validation_result

            tool_input = self._get_dao_deployment_parameters(message)
            if not tool_input:
                return DAODeploymentResult(
                    success=False,
                    message="Failed to extract DAO deployment parameters from message",
                )

            logger.info(
                "Processing DAO deployment",
                extra={"message_id": str(message.id)},
            )
            logger.debug(
                "DAO deployment parameters prepared",
                extra={"parameters": tool_input},
            )

            deployment_data = {}
            async for chunk in execute_workflow_stream(
                history=[], input_str=tool_input, tools_map=self.tools_map
            ):
                if chunk["type"] == "result":
                    deployment_data = chunk["content"]
                    logger.info(
                        "DAO deployment completed successfully",
                    )
                    logger.debug(
                        "Deployment data received",
                        extra={"data": deployment_data},
                    )
                elif chunk["type"] == "tool":
                    logger.debug(
                        "Executing tool",
                        extra={"tool_chunk": chunk},
                    )

            # Extract DAO ID if available from deployment data
            dao_id = None
            if isinstance(deployment_data, dict):
                dao_id = deployment_data.get("dao_id")

            return DAODeploymentResult(
                success=True,
                message="Successfully processed DAO deployment",
                deployment_data=deployment_data,
                dao_id=dao_id,
                daos_processed=1,
                deployments_successful=1,
            )

        except Exception as e:
            logger.error(
                "Error processing DAO deployment message",
                extra={"error": str(e)},
                exc_info=True,
            )
            return DAODeploymentResult(
                success=False,
                message=f"Error processing DAO deployment: {str(e)}",
                error=e,
                daos_processed=1,
                deployments_successful=0,
            )

    def _should_retry_on_error(self, error: Exception, context: JobContext) -> bool:
        """Determine if DAO deployment error should trigger retry."""
        # Retry on network errors, temporary blockchain issues
        retry_errors = (
            ConnectionError,
            TimeoutError,
        )

        # Don't retry on validation errors or tool configuration issues
        if "Missing required parameter" in str(error):
            return False
        if "Tools not properly initialized" in str(error):
            return False

        return isinstance(error, retry_errors)

    async def _handle_execution_error(
        self, error: Exception, context: JobContext
    ) -> Optional[List[DAODeploymentResult]]:
        """Handle DAO deployment execution errors with recovery logic."""
        if "blockchain" in str(error).lower() or "network" in str(error).lower():
            logger.warning(
                "Blockchain/network error during DAO deployment, will retry",
                extra={"error": str(error)},
            )
            return None  # Let default retry handling take over

        # For validation errors, don't retry
        return [
            DAODeploymentResult(
                success=False,
                message=f"Unrecoverable DAO deployment error: {str(error)}",
                error=error,
            )
        ]

    async def _post_execution_cleanup(
        self, context: JobContext, results: List[DAODeploymentResult]
    ) -> None:
        """Cleanup after DAO deployment task execution."""
        # Clear cached pending messages
        self._pending_messages = None
        logger.debug("Task cleanup completed")

    async def _execute_impl(self, context: JobContext) -> List[DAODeploymentResult]:
        """Execute DAO deployment task with enhanced processing."""
        results: List[DAODeploymentResult] = []
        try:
            if not self._pending_messages:
                return results

            # Process one message at a time for DAO deployments (they're resource intensive)
            message = self._pending_messages[0]
            logger.debug(
                "Processing DAO deployment message",
                extra={"message_id": str(message.id)},
            )

            result = await self._process_dao_deployment_message(message)
            results.append(result)

            if result.success:
                backend.update_queue_message(
                    queue_message_id=message.id,
                    update_data=QueueMessageBase(
                        is_processed=True,
                        result=result.model_dump(),
                    ),
                )
                logger.debug(
                    "Marked message as processed",
                    extra={"message_id": str(message.id)},
                )
                logger.info(
                    "DAO deployment task completed successfully",
                )
            else:
                logger.error(
                    "DAO deployment failed",
                    extra={"message": result.message},
                )

            return results

        except Exception as e:
            logger.error(
                "Error in DAO deployment task",
                extra={"error": str(e)},
                exc_info=True,
            )
            results.append(
                DAODeploymentResult(
                    success=False,
                    message=f"Error in DAO deployment task: {str(e)}",
                    error=e,
                    daos_processed=1,
                    deployments_successful=0,
                )
            )
            return results


# Create instance for auto-registration
dao_deployment_task = DAODeploymentTask()
