from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Any, Optional, Type


class TwitterPostTweetInput(BaseModel):
    """Input schema for posting tweets or replying to existing tweets."""

    text: str = Field(
        ...,
        description="The content of the tweet to be posted",
    )
    reply_to_tweet_id: Optional[str] = Field(
        None,
        description="Optional ID of the tweet to reply to",
    )


class TwitterPostTweetTool(BaseTool):
    name = "twitter_post_tweet"
    description = (
        "Post a new tweet or reply to an existing tweet on Twitter. Returns a success "
        "message with the first 50 characters of the tweet if successful."
    )
    args_schema: Type[BaseModel] = TwitterPostTweetInput
    return_direct: bool = False

    def __init__(self, twitter_service: Any, **kwargs):
        super().__init__(**kwargs)
        self.twitter_service = twitter_service

    def _deploy(
        self, text: str, reply_to_tweet_id: Optional[str] = None, **kwargs
    ) -> str:
        """Execute the tool to post a tweet synchronously."""
        try:
            if self.twitter_service is None:
                return "Twitter client is not initialized"
            response = self.twitter_service.post_tweet(
                text=text, reply_in_reply_to_tweet_id=reply_to_tweet_id
            )
            if response:
                return f"Successfully posted tweet: {text[:50]}..."
            return "Failed to post tweet"
        except Exception as e:
            return f"Error posting tweet: {str(e)}"

    async def _run(
        self, text: str, reply_to_tweet_id: Optional[str] = None, **kwargs
    ) -> str:
        return self._deploy(text, reply_to_tweet_id, **kwargs)

    async def _arun(
        self, text: str, reply_to_tweet_id: Optional[str] = None, **kwargs
    ) -> str:
        """Execute the tool to post a tweet asynchronously."""
        return self._deploy(text, reply_to_tweet_id, **kwargs)
