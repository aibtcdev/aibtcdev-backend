from backend.factory import backend
from backend.models import UUID, XCredsFilter
from langchain.tools import BaseTool
from lib.logger import configure_logger
from lib.twitter import TwitterService
from pydantic import BaseModel, Field
from typing import Optional, Type

logger = configure_logger(__name__)


class TwitterPostTweetInput(BaseModel):
    """Input schema for posting tweets or replying to existing tweets."""

    content: str = Field(
        ...,
        description="The content of the tweet to be posted. Required to be less than 280 characters.",
    )


class TwitterPostTweetTool(BaseTool):
    name: str = "twitter_post_tweet"
    description: str = (
        "Post a new tweet or reply to an existing tweet on Twitter."
        "Required to be less than 280 characters."
    )
    args_schema: Type[BaseModel] = TwitterPostTweetInput
    return_direct: bool = False
    agent_id: Optional[UUID] = None

    def __init__(
        self,
        agent_id: Optional[UUID] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.agent_id = agent_id

    def _deploy(self, content: str, **kwargs) -> str:
        """Execute the tool to post a tweet synchronously."""

        if self.agent_id is None:
            raise ValueError("Agent ID is required")

        if len(content) > 280:
            return "Error: Tweet content exceeds 280 characters limit. Please shorten your message."

        try:
            x_creds = backend.list_x_creds(
                filters=XCredsFilter(agent_id=self.agent_id),
            )
            if not x_creds:
                return "No X creds found for this agent"
            x_creds = x_creds[0]
            twitter_service = TwitterService(
                consumer_key=x_creds.consumer_key,
                consumer_secret=x_creds.consumer_secret,
                access_token=x_creds.access_token,
                access_secret=x_creds.access_secret,
                client_id=x_creds.client_id,
                client_secret=x_creds.client_secret,
            )
            twitter_service.initialize()
            response = twitter_service.post_tweet(text=content)

            logger.info(f"Response: {response}")
            if response:
                return f"https://x.com/i/web/status/{response.id}"
            return "Failed to post tweet"
        except Exception as e:
            logger.error(f"Error posting tweet: {str(e)}")
            return f"Error posting tweet: {str(e)}"

    def _run(self, content: str, **kwargs) -> str:
        return self._deploy(content, **kwargs)

    async def _arun(self, content: str, **kwargs) -> str:
        """Execute the tool to post a tweet asynchronously."""
        return self._deploy(content, **kwargs)
