from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from backend.factory import backend
from backend.models import (
    DAOFilter,
    Profile,
    QueueMessage,
    QueueMessageBase,
    QueueMessageFilter,
    QueueMessageType,
)
from lib.logger import configure_logger
from services.workflows import execute_workflow_stream
from tools.tools_factory import filter_tools_by_names, initialize_tools

from ..base import BaseTask, JobContext, RunnerConfig, RunnerResult

logger = configure_logger(__name__)


@dataclass
class DAOProcessingResult(RunnerResult):
    """Result of DAO processing operation."""

    dao_id: Optional[UUID] = None
    deployment_data: Optional[Dict[str, Any]] = None


class DAOTask(BaseTask[DAOProcessingResult]):
    """Task for processing DAO deployments."""

    def __init__(self, config: Optional[RunnerConfig] = None):
        super().__init__(config)
        self._pending_messages = None
        self.tools_map_all = initialize_tools(
            Profile(id=self.config.twitter_profile_id, created_at=datetime.now()),
            agent_id=self.config.twitter_agent_id,
        )
        self.tools_map = filter_tools_by_names(
            ["contract_deploy_dao"], self.tools_map_all
        )
        logger.debug(f"Initialized {len(self.tools_map)} DAO deployment tools")

    async def _validate_config(self, context: JobContext) -> bool:
        """Validate task configuration."""
        try:
            if not self.tools_map:
                logger.error("No DAO deployment tools available")
                return False

            if not self.tools_map_all:
                logger.error("Tools not properly initialized")
                return False

            return True
        except Exception as e:
            logger.error(f"Error validating DAO config: {str(e)}", exc_info=True)
            return False

    async def _validate_prerequisites(self, context: JobContext) -> bool:
        """Validate task prerequisites."""
        try:
            # Check for pending DAOs first
            pending_daos = backend.list_daos(
                filters=DAOFilter(
                    is_deployed=False,
                    is_broadcasted=True,
                    wallet_id=self.config.twitter_wallet_id,
                )
            )
            if pending_daos:
                logger.info(
                    f"Found {len(pending_daos)} pending Twitter DAO(s), skipping queue processing"
                )
                return False

            # Cache pending messages for later use
            self._pending_messages = backend.list_queue_messages(
                filters=QueueMessageFilter(
                    type=QueueMessageType.DAO, is_processed=False
                )
            )
            return True
        except Exception as e:
            logger.error(f"Error validating DAO prerequisites: {str(e)}", exc_info=True)
            self._pending_messages = None
            return False

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate task-specific conditions."""
        try:
            if not self._pending_messages:
                logger.debug("No pending DAO messages found")
                return False

            message_count = len(self._pending_messages)
            if message_count > 0:
                logger.debug(f"Found {message_count} unprocessed DAO messages")
                return True

            logger.debug("No unprocessed DAO messages to process")
            return False

        except Exception as e:
            logger.error(f"Error in DAO task validation: {str(e)}", exc_info=True)
            return False

    async def _validate_message(
        self, message: QueueMessage
    ) -> Optional[DAOProcessingResult]:
        """Validate a single message before processing."""
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
                return DAOProcessingResult(
                    success=False,
                    message=f"Missing required parameters: {', '.join(missing_params)}",
                )

            return None  # Validation passed

        except Exception as e:
            logger.error(
                f"Error validating message {message.id}: {str(e)}", exc_info=True
            )
            return DAOProcessingResult(
                success=False,
                message=f"Error validating message: {str(e)}",
                error=e,
            )

    def _get_dao_parameters(self, message: QueueMessage) -> Optional[str]:
        """Extract and format DAO parameters from message."""
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
            logger.error(f"Missing required parameter in message: {e}")
            return None

    async def _process_dao_message(self, message: QueueMessage) -> DAOProcessingResult:
        """Process a single DAO message."""
        try:
            # Validate message first
            validation_result = await self._validate_message(message)
            if validation_result:
                return validation_result

            tool_input = self._get_dao_parameters(message)
            if not tool_input:
                return DAOProcessingResult(
                    success=False,
                    message="Failed to extract DAO parameters from message",
                )

            logger.info(f"Processing DAO deployment for message {message.id}")
            logger.debug(f"DAO deployment parameters: {tool_input}")

            deployment_data = {}
            async for chunk in execute_workflow_stream(
                history=[], input_str=tool_input, tools_map=self.tools_map
            ):
                if chunk["type"] == "result":
                    deployment_data = chunk["content"]
                    logger.info("DAO deployment completed successfully")
                    logger.debug(f"Deployment data: {deployment_data}")
                elif chunk["type"] == "tool":
                    logger.debug(f"Executing tool: {chunk}")

            return DAOProcessingResult(
                success=True,
                message="Successfully processed DAO deployment",
                deployment_data=deployment_data,
            )

        except Exception as e:
            logger.error(f"Error processing DAO message: {str(e)}", exc_info=True)
            return DAOProcessingResult(
                success=False, message=f"Error processing DAO: {str(e)}", error=e
            )

    async def _execute_impl(self, context: JobContext) -> List[DAOProcessingResult]:
        """Execute DAO deployment task."""
        results: List[DAOProcessingResult] = []
        try:
            if not self._pending_messages:
                return results

            # Process one message at a time for DAOs
            message = self._pending_messages[0]
            logger.debug(f"Processing DAO deployment message: {message.id}")

            result = await self._process_dao_message(message)
            results.append(result)

            if result.success:
                backend.update_queue_message(
                    queue_message_id=message.id,
                    update_data=QueueMessageBase(is_processed=True),
                )
                logger.debug(f"Marked message {message.id} as processed")

            return results

        except Exception as e:
            logger.error(f"Error in DAO task: {str(e)}", exc_info=True)
            results.append(
                DAOProcessingResult(
                    success=False, message=f"Error in DAO task: {str(e)}", error=e
                )
            )
            return results


dao_task = DAOTask()
