import os
from backend.factory import backend
from backend.models import DAOFilter, Profile, QueueMessageBase, QueueMessageFilter
from datetime import datetime
from lib.logger import configure_logger
from services.langgraph import execute_langgraph_stream
from tools.tools_factory import filter_tools_by_names, initialize_tools
from uuid import UUID

logger = configure_logger(__name__)


class DAORunner:
    """Handles processing of queued DAO deployment requests."""

    def __init__(self):
        """Initialize the runner with necessary tools."""
        self.tools_map_all = initialize_tools(
            Profile(
                id=UUID(
                    os.getenv(
                        "AIBTC_TWITTER_PROFILE_ID",
                        "9e650de6-93b8-4160-9f4b-938d00b5c6f8",
                    )
                ),
                created_at=datetime.now(),
            ),
            agent_id=UUID(
                os.getenv(
                    "AIBTC_TWITTER_AGENT_ID", "13059e46-1b4d-4b87-9593-b556dcefdeb2"
                )
            ),
            crewai=False,
        )
        self.tools_map = filter_tools_by_names(
            ["contract_dao_deploy"], self.tools_map_all
        )
        logger.info(f"Initialized tools_map with {len(self.tools_map)} tools")

    async def run(self) -> None:
        """Process DAO deployments and queue."""
        try:
            # Check for any pending Twitter DAOs
            pending_daos = backend.list_daos(
                filters=DAOFilter(is_deployed=False, is_broadcasted=True)
            )

            if pending_daos:
                logger.info("Found pending Twitter DAO, skipping queue processing")
                return

            # No pending DAOs, process next from queue
            queue_messages = backend.list_queue_messages(
                filters=QueueMessageFilter(type="daos", is_processed=False)
            )
            if not queue_messages:
                logger.info("No messages in queue")
                return

            message = queue_messages[0]
            logger.info(f"Processing message: {message}")

            # Construct the input for the tool
            tool_input = (
                f"Please deploy a DAO with the following parameters:\n"
                f"Token Symbol: {message.message['parameters']['token_symbol']}\n"
                f"Token Name: {message.message['parameters']['token_name']}\n"
                f"Token Description: {message.message['parameters']['token_description']}\n"
                f"Token Max Supply: {message.message['parameters']['token_max_supply']}\n"
                f"Token Decimals: {message.message['parameters']['token_decimals']}\n"
                f"Mission: {message.message['parameters']['mission']}"
            )

            # Execute using langgraph
            async for chunk in execute_langgraph_stream(
                history=[], input_str=tool_input, tools_map=self.tools_map
            ):
                if chunk["type"] == "result":
                    logger.info(f"DAO deployment completed: {chunk['content']}")
                    # Mark message as processed after successful deployment
                    backend.update_queue_message(
                        queue_message_id=message.id,
                        update_data=QueueMessageBase(is_processed=True),
                    )
                elif chunk["type"] == "tool":
                    logger.info(f"Tool execution: {chunk}")

        except Exception as e:
            logger.error(f"Error in runner: {str(e)}")
            raise


# Global runner instance
runner = DAORunner()


async def execute_runner_job() -> None:
    """Execute the runner job to process DAO deployments."""
    try:
        logger.info("Starting DAO runner")
        await runner.run()
        logger.info("Completed DAO runner")

    except Exception as e:
        logger.error(f"Error in runner job: {str(e)}")
        raise
