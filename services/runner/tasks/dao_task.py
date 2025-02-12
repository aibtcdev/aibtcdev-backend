from ..base import BaseTask, JobContext, RunnerConfig, RunnerResult
from backend.factory import backend
from backend.models import DAOFilter, Profile, QueueMessageBase, QueueMessageFilter
from dataclasses import dataclass
from datetime import datetime
from lib.logger import configure_logger
from services.workflows import execute_langgraph_stream
from tools.tools_factory import filter_tools_by_names, initialize_tools
from typing import Any, Dict, List, Optional
from uuid import UUID

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
        self.tools_map_all = initialize_tools(
            Profile(id=self.config.twitter_profile_id, created_at=datetime.now()),
            agent_id=self.config.twitter_agent_id,
        )
        self.tools_map = filter_tools_by_names(
            ["contract_dao_deploy"], self.tools_map_all
        )
        logger.debug(f"Initialized tools_map with {len(self.tools_map)} tools")

    async def _validate_config(self, context: JobContext) -> bool:
        """Validate DAO task configuration."""
        try:
            logger.debug("Checking DAO deployment tools availability")
            if not self.tools_map:
                logger.error("No DAO deployment tools available")
                return False

            logger.debug("Checking tools initialization")
            if not self.tools_map_all:
                logger.error("Tools not properly initialized")
                return False

            logger.debug("DAO task configuration validation successful")
            return True
        except Exception as e:
            logger.error(f"Error validating DAO config: {str(e)}", exc_info=True)
            return False

    async def _validate_prerequisites(self, context: JobContext) -> bool:
        """Validate DAO task prerequisites."""
        try:
            logger.debug("Checking for pending DAO deployments")
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

            logger.debug("DAO task prerequisites validation successful")
            return True
        except Exception as e:
            logger.error(f"Error validating DAO prerequisites: {str(e)}", exc_info=True)
            return False

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate DAO task specific conditions."""
        try:
            logger.debug("Checking for unprocessed DAO messages")
            queue_messages = backend.list_queue_messages(
                filters=QueueMessageFilter(type="daos", is_processed=False)
            )
            has_messages = bool(queue_messages)
            if not has_messages:
                logger.info("No unprocessed DAO messages found in queue")
            else:
                logger.debug(f"Found {len(queue_messages)} unprocessed DAO messages")
            return has_messages
        except Exception as e:
            logger.error(
                f"Error in DAO task-specific validation: {str(e)}", exc_info=True
            )
            return False

    def _get_dao_parameters(self, message: Dict[str, Any]) -> Optional[str]:
        """Extract and validate DAO parameters from message."""
        try:
            params = message["parameters"]
            return (
                f"Please deploy a DAO with the following parameters:\n"
                f"Token Symbol: {params['token_symbol']}\n"
                f"Token Name: {params['token_name']}\n"
                f"Token Description: {params['token_description']}\n"
                f"Token Max Supply: {params['token_max_supply']}\n"
                f"Token Decimals: {params['token_decimals']}\n"
                f"Mission: {params['mission']}"
            )
        except KeyError as e:
            logger.error(f"Missing required parameter in message: {e}")
            return None

    async def _process_dao_message(self, message: Any) -> DAOProcessingResult:
        """Process a single DAO message."""
        try:
            tool_input = self._get_dao_parameters(message.message)
            if not tool_input:
                return DAOProcessingResult(
                    success=False,
                    message="Failed to extract DAO parameters from message",
                )

            deployment_data = {}
            async for chunk in execute_langgraph_stream(
                history=[], input_str=tool_input, tools_map=self.tools_map
            ):
                if chunk["type"] == "result":
                    deployment_data = chunk["content"]
                    logger.info(f"DAO deployment completed: {deployment_data}")
                elif chunk["type"] == "tool":
                    logger.debug(f"Tool execution: {chunk}")

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

    async def validate(self, context: JobContext) -> bool:
        """Validate DAO deployment prerequisites."""
        try:
            # Check for pending DAOs
            pending_daos = backend.list_daos(
                filters=DAOFilter(
                    is_deployed=False,
                    is_broadcasted=True,
                    wallet_id=self.config.twitter_wallet_id,
                )
            )
            if pending_daos:
                logger.debug("Found pending Twitter DAO, skipping queue processing")
                return False

            # Check queue
            queue_messages = backend.list_queue_messages(
                filters=QueueMessageFilter(type="daos", is_processed=False)
            )
            return bool(queue_messages)
        except Exception as e:
            logger.error(f"Error validating DAO task: {str(e)}", exc_info=True)
            return False

    async def execute(self, context: JobContext) -> List[DAOProcessingResult]:
        """Execute DAO deployment task."""
        results: List[DAOProcessingResult] = []
        try:
            # Process queue
            queue_messages = backend.list_queue_messages(
                filters=QueueMessageFilter(type="daos", is_processed=False)
            )
            if not queue_messages:
                logger.debug("No messages in queue")
                return results

            message = queue_messages[0]
            logger.info(f"Processing DAO deployment message: {message}")

            result = await self._process_dao_message(message)
            results.append(result)

            if result.success:
                backend.update_queue_message(
                    queue_message_id=message.id,
                    update_data=QueueMessageBase(is_processed=True),
                )

            return results

        except Exception as e:
            logger.error(f"Error in DAO task: {str(e)}", exc_info=True)
            results.append(
                DAOProcessingResult(
                    success=False, message=f"Error in DAO task: {str(e)}", error=e
                )
            )
            return results
