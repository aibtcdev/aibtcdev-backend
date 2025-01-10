from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Any, Optional, Type
from uuid import UUID
from backend.factory import backend
from backend.models import XCredsFilter
from lib.twitter import TwitterService


class TwitterPostTweetInput(BaseModel):
    """Input schema for posting tweets or replying to existing tweets."""

    text: str = Field(
        ...,
        description="The content of the tweet to be posted",
    )


class TwitterPostTweetTool(BaseTool):
    name = "twitter_post_tweet"
    description = (
        "Post a new tweet or reply to an existing tweet on Twitter. Returns a success "
        "message with the first 50 characters of the tweet if successful."
    )
    args_schema: Type[BaseModel] = TwitterPostTweetInput
    return_direct: bool = False
    profile_id: UUID = Field(default=UUID("00000000-0000-0000-0000-000000000000"))
    agent_id: UUID = Field(default=UUID("00000000-0000-0000-0000-000000000000"))

    def __init__(
        self,
        profile_id: UUID = UUID("00000000-0000-0000-0000-000000000000"),
        agent_id: UUID = UUID("00000000-0000-0000-0000-000000000000"),
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.profile_id = profile_id
        self.agent_id = agent_id

    def _deploy(self, text: str, **kwargs) -> str:
        """Execute the tool to post a tweet synchronously."""
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
            response = twitter_service.post_tweet(text=text)
            if response:
                return f"Successfully posted tweet: {text[:50]}..."
            return "Failed to post tweet"
        except Exception as e:
            return f"Error posting tweet: {str(e)}"

    async def _run(self, text: str, **kwargs) -> str:
        return self._deploy(text, **kwargs)

    async def _arun(self, text: str, **kwargs) -> str:
        """Execute the tool to post a tweet asynchronously."""
        return self._deploy(text, **kwargs)
