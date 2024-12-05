from typing import Any, Optional, Type
from crewai_tools import BaseTool
from pydantic import BaseModel, Field


class TwitterPostTweetSchema(BaseModel):
    """Input schema for TwitterPostTweetTool."""
    text: str = Field(
        ...,
        description="The content of the tweet to be posted",
    )
    reply_to_tweet_id: Optional[str] = Field(
        None,
        description="Optional ID of the tweet to reply to",
    )


class TwitterPostTweetTool(BaseTool):
    name: str = "Twitter: Post Tweet"
    description: str = "Post a new tweet or reply to an existing tweet"
    args_schema: Type[BaseModel] = TwitterPostTweetSchema
    twitter_service: Optional[Any] = None

    def __init__(self, twitter_service: Any, **kwargs):
        super().__init__(**kwargs)
        self.twitter_service = twitter_service

    async def _run(self, text: str, reply_to_tweet_id: Optional[str] = None) -> str:
        """
        Post a new tweet or reply to an existing tweet.

        Args:
            text (str): The content of the tweet
            reply_to_tweet_id (Optional[str]): Optional ID of tweet to reply to

        Returns:
            str: Response message indicating success or failure
        """
        try:
            if self.twitter_service is None:
                return "Twitter client is not initialized"
            response = await self.twitter_service.post_tweet(
                text=text,
                reply_in_reply_to_tweet_id=reply_to_tweet_id
            )
            if response:
                return f"Successfully posted tweet: {text[:50]}..."
            return "Failed to post tweet"
        except Exception as e:
            return f"Error posting tweet: {str(e)}"
