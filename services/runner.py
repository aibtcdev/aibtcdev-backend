import os
from backend.factory import backend
from backend.models import (
    DAOFilter,
    Profile,
    QueueMessageBase,
    QueueMessageFilter,
    TokenFilter,
)
from datetime import datetime
from lib.logger import configure_logger
from services.langgraph import execute_langgraph_stream
from services.tweet_generator import generate_dao_tweet
from services.twitter import TwitterMentionHandler
from tools.tools_factory import filter_tools_by_names, initialize_tools
from uuid import UUID

logger = configure_logger(__name__)


class TweetRunner:
    """Handles processing of queued tweet responses."""

    def __init__(self):
        """Initialize the Twitter handler."""
        self.twitter_handler = TwitterMentionHandler()

    async def run(self) -> None:
        """Process tweet responses from queue."""
        try:
            # Get unprocessed tweet messages from queue
            queue_messages = backend.list_queue_messages(
                filters=QueueMessageFilter(type="tweet", is_processed=False)
            )
            if not queue_messages:
                logger.info("No tweet messages in queue")
                return

            ## the tweet type messages don't have the tweet_id and conversation_id so we need to look through the dao type messages to get them
            dao_messages = backend.list_queue_messages(
                filters=QueueMessageFilter(type="daos", is_processed=True)
            )

            ## i need to make a map of dao_id to tweet_id and conversation_id
            dao_messages_map = {message.dao_id: message for message in dao_messages}

            for message in queue_messages:
                logger.info(f"Processing tweet message: {message}")
                try:
                    response_content = ""

                    # Get the DAO info if available and generate tweet
                    if message.dao_id:
                        dao = backend.get_dao(message.dao_id)
                        token = backend.list_tokens(
                            filters=TokenFilter(dao_id=message.dao_id)
                        )
                        dao_message = dao_messages_map[message.dao_id]
                        if dao and token and len(token) > 0:
                            # Generate an exciting tweet about the DAO deployment
                            generated_tweet = await generate_dao_tweet(
                                dao_name=dao.name,
                                dao_symbol=token[0].symbol,
                                dao_mission=dao.mission,
                            )
                            response_content = generated_tweet["tweet_text"]
                    else:
                        # Use the base message if no DAO info
                        response_content = (
                            message.message.get("message", "")
                            if isinstance(message.message, dict)
                            else ""
                        )

                    # Post the response
                    await self.twitter_handler._post_response(
                        {
                            "tweet_id": dao_message.tweet_id,
                            "conversation_id": dao_message.conversation_id,
                        },
                        response_content,
                    )

                    # Mark message as processed
                    backend.update_queue_message(
                        queue_message_id=message.id,
                        update_data=QueueMessageBase(is_processed=True),
                    )
                    logger.info(f"Successfully processed tweet message {message.id}")

                except Exception as e:
                    logger.error(
                        f"Error processing tweet message {message.id}: {str(e)}"
                    )
                    continue

        except Exception as e:
            logger.error(f"Error in tweet runner: {str(e)}")
            raise


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
            backend.update_queue_message(
                queue_message_id=message.id,
                update_data=QueueMessageBase(is_processed=True),
            )
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

                elif chunk["type"] == "tool":
                    logger.info(f"Tool execution: {chunk}")

        except Exception as e:
            logger.error(f"Error in runner: {str(e)}")
            raise


# Global runner instances
dao_runner = DAORunner()
tweet_runner = TweetRunner()


async def execute_runner_job(runner_type: str = "dao") -> None:
    """Execute the runner jobs to process DAO deployments and tweets.

    Args:
        runner_type: The type of runner to execute ("dao" or "tweet")
    """
    try:
        if runner_type == "dao":
            logger.info("Starting DAO runner")
            await dao_runner.run()
            logger.info("Completed DAO runner")
        elif runner_type == "tweet":
            logger.info("Starting Tweet runner")
            await tweet_runner.run()
            logger.info("Completed Tweet runner")
        else:
            logger.error(f"Unknown runner type: {runner_type}")
            raise ValueError(f"Unknown runner type: {runner_type}")

    except Exception as e:
        logger.error(f"Error in runner job: {str(e)}")
        raise
