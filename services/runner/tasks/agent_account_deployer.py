"""Agent account deployment task implementation."""

from dataclasses import dataclass
from typing import Any, Dict, List

from backend.factory import backend
from backend.models import (
    QueueMessage,
    QueueMessageBase,
    QueueMessageFilter,
    QueueMessageType,
)
from config import config
from lib.logger import configure_logger
from services.runner.base import BaseTask, JobContext, RunnerResult
from tools.smartwallet import SmartWalletDeploySmartWalletTool

logger = configure_logger(__name__)


@dataclass
class AgentAccountDeployResult(RunnerResult):
    """Result of agent account deployment operation."""

    accounts_processed: int = 0
    accounts_deployed: int = 0
    errors: List[str] = None

    def __post_init__(self):
        self.errors = self.errors or []


class AgentAccountDeployerTask(BaseTask[AgentAccountDeployResult]):
    """Task runner for deploying agent accounts."""

    QUEUE_TYPE = QueueMessageType.AGENT_ACCOUNT_DEPLOY

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
                logger.info("No pending agent account deployment messages found")
                return False

            # Validate that at least one message has valid deployment data
            for message in pending_messages:
                message_data = message.message or {}
                if self._validate_message_data(message_data):
                    logger.info("Found valid agent account deployment message")
                    return True

            logger.warning("No valid deployment data found in pending messages")
            return False

        except Exception as e:
            logger.error(
                f"Error validating agent account deployment task: {str(e)}",
                exc_info=True,
            )
            return False

    def _validate_message_data(self, message_data: Dict[str, Any]) -> bool:
        """Validate the message data contains required fields."""
        required_fields = [
            "owner_address",
            "dao_token_contract",
            "dao_token_dex_contract",
        ]
        return all(field in message_data for field in required_fields)

    async def process_message(self, message: QueueMessage) -> Dict[str, Any]:
        """Process a single agent account deployment message."""
        message_id = message.id
        message_data = message.message or {}

        logger.debug(f"Processing agent account deployment message {message_id}")

        try:
            # Validate message data
            if not self._validate_message_data(message_data):
                error_msg = f"Invalid message data in message {message_id}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

            # Initialize the SmartWalletDeploySmartWalletTool
            logger.debug("Preparing to deploy agent account")
            deploy_tool = SmartWalletDeploySmartWalletTool(
                wallet_id=config.scheduler.agent_account_deploy_runner_wallet_id
            )

            # Execute the deployment
            logger.debug("Executing deployment...")
            deployment_result = await deploy_tool._arun(
                owner_address=message_data["owner_address"],
                dao_token_contract=message_data["dao_token_contract"],
                dao_token_dex_contract=message_data["dao_token_dex_contract"],
            )
            logger.debug(f"Deployment result: {deployment_result}")

            # Mark the message as processed
            update_data = QueueMessageBase(is_processed=True)
            backend.update_queue_message(message_id, update_data)

            return {"success": True, "deployed": True, "result": deployment_result}

        except Exception as e:
            error_msg = f"Error processing message {message_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "error": error_msg}

    async def get_pending_messages(self) -> List[QueueMessage]:
        """Get all unprocessed messages from the queue."""
        filters = QueueMessageFilter(type=self.QUEUE_TYPE, is_processed=False)
        return backend.list_queue_messages(filters=filters)

    async def _execute_impl(
        self, context: JobContext
    ) -> List[AgentAccountDeployResult]:
        """Run the agent account deployment task."""
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

        # Process each message
        processed_count = 0
        deployed_count = 0
        errors = []

        for message in pending_messages:
            result = await self.process_message(message)
            processed_count += 1

            if result.get("success"):
                if result.get("deployed", False):
                    deployed_count += 1
            else:
                errors.append(result.get("error", "Unknown error"))

        logger.debug(
            f"Task metrics - Processed: {processed_count}, "
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


# Instantiate the task for use in the registry
agent_account_deployer = AgentAccountDeployerTask()
