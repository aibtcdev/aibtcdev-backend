import os
from backend.factory import backend
from backend.models import (
    DAOBase,
    DAOFilter,
    Profile,
    QueueMessageBase,
    QueueMessageFilter,
    TokenFilter,
    WalletFilter,
    XTweetFilter,
    XUserBase,
)
from datetime import datetime
from lib.logger import configure_logger
from services.langgraph import execute_langgraph_stream
from services.tweet_generator import generate_dao_tweet
from services.twitter import TweetData, TwitterMentionHandler
from tools.tools_factory import filter_tools_by_names, initialize_tools
from typing import Any, Dict, Optional
from uuid import UUID

logger = configure_logger(__name__)


def get_required_env_var(name: str) -> UUID:
    """Get a required environment variable and convert it to UUID."""
    value = os.getenv(name)
    if not value:
        raise ValueError(f"{name} environment variable is not set")
    return UUID(value)


class BaseRunner:
    """Base class for runners with common initialization logic."""

    def __init__(self):
        """Initialize common runner components."""
        self.twitter_profile_id = get_required_env_var("AIBTC_TWITTER_PROFILE_ID")
        self.twitter_agent_id = get_required_env_var("AIBTC_TWITTER_AGENT_ID")

        twitter_wallet = backend.list_wallets(
            filters=WalletFilter(profile_id=self.twitter_profile_id)
        )
        if not twitter_wallet:
            logger.critical(
                "No Twitter wallet found - critical system component missing"
            )
            raise RuntimeError("Twitter wallet not found")

        self.twitter_wallet_id = twitter_wallet[0].id


class TweetRunner(BaseRunner):
    """Handles processing of queued tweet responses."""

    def __init__(self):
        """Initialize the Twitter handler."""
        super().__init__()
        self.twitter_handler = TwitterMentionHandler()

    async def _process_tweet_message(self, message: Any, dao_messages: list) -> None:
        """Process a single tweet message."""
        if not message.dao_id:
            logger.warning(f"Tweet message {message.id} has no dao_id")
            return

        # Get the DAO and token info
        dao = backend.get_dao(message.dao_id)
        if not dao:
            logger.error(f"No DAO found for id: {message.dao_id}")
            return

        token = backend.list_tokens(filters=TokenFilter(dao_id=message.dao_id))
        if not token:
            logger.error(f"No token found for DAO: {message.dao_id}")
            return

        # Find matching DAO message
        matching_dao_message = self._find_matching_dao_message(token[0], dao_messages)
        if not matching_dao_message:
            logger.warning(
                f"No matching DAO message found for dao_id: {message.dao_id} "
                f"with token symbol: {token[0].symbol}, name: {token[0].name}"
            )
            return

        await self._handle_tweet_response(message, dao, token[0], matching_dao_message)

    def _find_matching_dao_message(
        self, token: Any, dao_messages: list
    ) -> Optional[Any]:
        """Find matching DAO message based on token details."""
        for dao_message in dao_messages:
            if not isinstance(dao_message.message, dict):
                continue

            params = dao_message.message.get("parameters", {})
            if (
                params.get("token_symbol") == token.symbol
                and params.get("token_name") == token.name
                and params.get("token_max_supply") == token.max_supply
            ):
                logger.debug(
                    f"Found matching DAO message: {dao_message.id} for token {token.symbol}"
                )
                return dao_message
        return None

    async def _handle_tweet_response(
        self, message: Any, dao: Any, token: Any, dao_message: Any
    ) -> None:
        """Handle the tweet response generation and posting."""
        try:
            # Generate and post tweet
            generated_tweet = await generate_dao_tweet(
                dao_name=dao.name,
                dao_symbol=token.symbol,
                dao_mission=dao.mission,
                dao_id=dao.id,
            )

            logger.debug(
                f"Posting response for tweet_id: {dao_message.tweet_id}, "
                f"conversation_id: {dao_message.conversation_id}"
            )

            await self.twitter_handler._post_response(
                tweet_data=TweetData(
                    tweet_id=dao_message.tweet_id,
                    conversation_id=dao_message.conversation_id,
                ),
                response_content=generated_tweet["tweet_text"],
            )

            # Update author information
            await self._update_author_info(message, dao, dao_message)

            logger.info(f"Successfully processed tweet message {message.id}")

        except Exception as e:
            logger.error(
                f"Error handling tweet response for message {message.id}: {str(e)}",
                exc_info=True,
            )

    async def _update_author_info(
        self, message: Any, dao: Any, dao_message: Any
    ) -> None:
        """Update author information in the database."""
        tweet_info = backend.list_x_tweets(
            filters=XTweetFilter(tweet_id=dao_message.tweet_id)
        )
        if not tweet_info:
            logger.error(f"No tweet info found for tweet_id: {dao_message.tweet_id}")
            return

        author_id = tweet_info[0].author_id
        author_info = backend.get_x_user(author_id)
        if not author_info:
            logger.warning(f"No author info found for author_id: {author_id}")
            return

        # Update DAO with author
        backend.update_dao(
            dao_id=dao.id,
            update_data=DAOBase(author_id=author_id),
        )

        # Update user info if available
        user = await self.twitter_handler.twitter_service.get_user_by_user_id(
            author_info.user_id
        )
        if user:
            logger.debug(f"Updating user info for: {user.username}")
            backend.update_x_user(
                x_user_id=author_info.id,
                update_data=XUserBase(
                    name=user.name,
                    username=user.username,
                    description=user.description,
                    location=user.location,
                    profile_image_url=user.profile_image_url,
                    profile_banner_url=user.profile_banner_url,
                    protected=user.protected,
                    verified=user.verified,
                    verified_type=user.verified_type,
                    subscription_type=user.subscription_type,
                ),
            )

    async def run(self) -> None:
        """Process tweet responses from queue."""
        try:
            # Get unprocessed tweet messages
            queue_messages = backend.list_queue_messages(
                filters=QueueMessageFilter(type="tweet", is_processed=False)
            )
            if not queue_messages:
                logger.debug("No tweet messages in queue")
                return

            # Get processed DAO messages
            dao_messages = backend.list_queue_messages(
                filters=QueueMessageFilter(type="daos", is_processed=True)
            )
            logger.debug(f"Found {len(dao_messages)} processed DAO messages")

            for message in queue_messages:
                logger.info(f"Processing tweet message: {message}")
                try:
                    await self._process_tweet_message(message, dao_messages)
                    backend.update_queue_message(
                        queue_message_id=message.id,
                        update_data=QueueMessageBase(is_processed=True),
                    )
                except Exception as e:
                    logger.error(
                        f"Error processing tweet message {message.id}: {str(e)}",
                        exc_info=True,
                    )

        except Exception as e:
            logger.error(f"Error in tweet runner: {str(e)}", exc_info=True)
            raise


class DAORunner(BaseRunner):
    """Handles processing of queued DAO deployment requests."""

    def __init__(self):
        """Initialize the runner with necessary tools."""
        super().__init__()

        self.tools_map_all = initialize_tools(
            Profile(id=self.twitter_profile_id, created_at=datetime.now()),
            agent_id=self.twitter_agent_id,
        )
        self.tools_map = filter_tools_by_names(
            ["contract_dao_deploy"], self.tools_map_all
        )
        logger.debug(f"Initialized tools_map with {len(self.tools_map)} tools")

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

    async def run(self) -> None:
        """Process DAO deployments and queue."""
        try:
            # Check for pending DAOs
            pending_daos = backend.list_daos(
                filters=DAOFilter(
                    is_deployed=False,
                    is_broadcasted=True,
                    wallet_id=self.twitter_wallet_id,
                )
            )
            if pending_daos:
                logger.debug("Found pending Twitter DAO, skipping queue processing")
                return

            # Process queue
            queue_messages = backend.list_queue_messages(
                filters=QueueMessageFilter(type="daos", is_processed=False)
            )
            if not queue_messages:
                logger.debug("No messages in queue")
                return

            message = queue_messages[0]
            logger.info(f"Processing DAO deployment message: {message}")

            tool_input = self._get_dao_parameters(message.message)
            if not tool_input:
                logger.error("Failed to extract DAO parameters from message")
                return

            # Execute deployment
            async for chunk in execute_langgraph_stream(
                history=[], input_str=tool_input, tools_map=self.tools_map
            ):
                if chunk["type"] == "result":
                    logger.info(f"DAO deployment completed: {chunk['content']}")
                elif chunk["type"] == "tool":
                    logger.debug(f"Tool execution: {chunk}")

            backend.update_queue_message(
                queue_message_id=message.id,
                update_data=QueueMessageBase(is_processed=True),
            )

        except Exception as e:
            logger.error(f"Error in DAO runner: {str(e)}", exc_info=True)
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
        logger.error(f"Error in runner job: {str(e)}", exc_info=True)
        raise
