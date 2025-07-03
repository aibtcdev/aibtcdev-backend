from typing import Optional, Type

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from app.backend.factory import backend
from app.backend.models import UUID, XCredsFilter
from app.lib.logger import configure_logger
from app.services.communication.twitter_service import TwitterService

logger = configure_logger(__name__)


class TwitterPostTweetInput(BaseModel):
    """Input schema for posting tweets or replying to existing tweets."""

    content: str = Field(
        ...,
        description="The content of the tweet to be posted. Required to be less than 280 characters.",
    )


class TwitterGetTweetInput(BaseModel):
    """Input schema for getting a tweet by its ID."""

    tweet_id: str = Field(
        ...,
        description="The ID of the tweet to retrieve. This should be the numeric tweet ID as a string.",
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
            # Find the DAO associated with this agent through holders
            from app.backend.models import HolderFilter

            holders = backend.list_holders(filters=HolderFilter(agent_id=self.agent_id))
            if not holders:
                return "No DAO association found for this agent"

            # Get X creds for the DAO
            dao_id = holders[0].dao_id
            x_creds = backend.list_x_creds(
                filters=XCredsFilter(dao_id=dao_id),
            )
            if not x_creds:
                return "No X creds found for this agent's DAO"
            x_creds = x_creds[0]
            twitter_service = TwitterService(
                consumer_key=x_creds.consumer_key,
                consumer_secret=x_creds.consumer_secret,
                access_token=x_creds.access_token,
                access_secret=x_creds.access_secret,
                client_id=x_creds.client_id,
                client_secret=x_creds.client_secret,
                bearer_token=x_creds.bearer_token,
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


class TwitterGetTweetTool(BaseTool):
    name: str = "twitter_get_tweet"
    description: str = (
        "Retrieve a tweet by its ID. Returns comprehensive tweet data including "
        "text, author information, metrics, entities, and metadata."
    )
    args_schema: Type[BaseModel] = TwitterGetTweetInput
    return_direct: bool = False
    agent_id: Optional[UUID] = None

    def __init__(
        self,
        agent_id: Optional[UUID] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.agent_id = agent_id

    def _deploy(self, tweet_id: str, **kwargs) -> str:
        """Execute the tool to get a tweet by ID synchronously."""

        if self.agent_id is None:
            raise ValueError("Agent ID is required")

        try:
            # Find the DAO associated with this agent through holders
            from app.backend.models import HolderFilter

            holders = backend.list_holders(filters=HolderFilter(agent_id=self.agent_id))
            if not holders:
                return "No DAO association found for this agent"

            # Get X creds for the DAO
            dao_id = holders[0].dao_id
            x_creds = backend.list_x_creds(
                filters=XCredsFilter(dao_id=dao_id),
            )
            if not x_creds:
                return "No X creds found for this agent's DAO"

            x_creds = x_creds[0]
            twitter_service = TwitterService(
                consumer_key=x_creds.consumer_key,
                consumer_secret=x_creds.consumer_secret,
                access_token=x_creds.access_token,
                access_secret=x_creds.access_secret,
                client_id=x_creds.client_id,
                client_secret=x_creds.client_secret,
                bearer_token=x_creds.bearer_token,
            )
            twitter_service.initialize()

            # Use async method in sync context - we need to handle this properly
            import asyncio

            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # Get the full response with includes (media data)
            response = loop.run_until_complete(
                twitter_service.client.get_tweet(
                    id=tweet_id,
                    tweet_fields=[
                        "id",
                        "text",
                        "created_at",
                        "author_id",
                        "conversation_id",
                        "in_reply_to_user_id",
                        "referenced_tweets",
                        "public_metrics",
                        "entities",
                        "attachments",
                        "context_annotations",
                        "withheld",
                        "reply_settings",
                        "lang",
                    ],
                    expansions=[
                        "author_id",
                        "referenced_tweets.id",
                        "referenced_tweets.id.author_id",
                        "entities.mentions.username",
                        "attachments.media_keys",
                        "attachments.poll_ids",
                        "in_reply_to_user_id",
                        "geo.place_id",
                    ],
                    media_fields=[
                        "duration_ms",
                        "height",
                        "media_key",
                        "preview_image_url",
                        "type",
                        "url",
                        "width",
                        "public_metrics",
                        "alt_text",
                    ],
                    user_fields=[
                        "id",
                        "name",
                        "username",
                        "created_at",
                        "description",
                        "entities",
                        "location",
                        "pinned_tweet_id",
                        "profile_image_url",
                        "protected",
                        "public_metrics",
                        "url",
                        "verified",
                        "withheld",
                    ],
                )
            )

            if response and response.data:
                tweet = response.data

                # Format as readable string
                result = f"Tweet ID: {tweet.id}\n"
                result += f"Text: {tweet.text}\n"
                result += f"Author ID: {tweet.author_id}\n"
                result += f"Created: {tweet.created_at}\n"
                result += f"Language: {tweet.lang}\n"
                result += f"Conversation ID: {tweet.conversation_id}\n"

                if tweet.public_metrics:
                    metrics = tweet.public_metrics
                    result += f"Metrics - Retweets: {metrics.retweet_count}, "
                    result += f"Likes: {metrics.like_count}, "
                    result += f"Replies: {metrics.reply_count}, "
                    result += f"Quotes: {metrics.quote_count}\n"

                if tweet.in_reply_to_user_id:
                    result += f"In reply to user: {tweet.in_reply_to_user_id}\n"

                if (
                    tweet.entities
                    and hasattr(tweet.entities, "hashtags")
                    and tweet.entities.hashtags
                ):
                    hashtags = [tag.tag for tag in tweet.entities.hashtags]
                    result += f"Hashtags: {', '.join(hashtags)}\n"

                if (
                    tweet.entities
                    and hasattr(tweet.entities, "mentions")
                    and tweet.entities.mentions
                ):
                    mentions = [mention.username for mention in tweet.entities.mentions]
                    result += f"Mentions: {', '.join(mentions)}\n"

                if (
                    tweet.entities
                    and hasattr(tweet.entities, "urls")
                    and tweet.entities.urls
                ):
                    urls = [url.expanded_url for url in tweet.entities.urls]
                    result += f"URLs: {', '.join(urls)}\n"

                # Handle media attachments (images, videos, etc.)
                if (
                    hasattr(response, "includes")
                    and response.includes
                    and hasattr(response.includes, "media")
                ):
                    media_list = response.includes.media
                    if media_list:
                        result += f"Media Attachments ({len(media_list)}):\n"
                        for i, media in enumerate(media_list, 1):
                            result += f"  Media {i}:\n"
                            result += f"    Type: {media.type}\n"
                            result += f"    Media Key: {media.media_key}\n"

                            if hasattr(media, "url") and media.url:
                                result += f"    URL: {media.url}\n"

                            if (
                                hasattr(media, "preview_image_url")
                                and media.preview_image_url
                            ):
                                result += (
                                    f"    Preview URL: {media.preview_image_url}\n"
                                )

                            if hasattr(media, "width") and media.width:
                                result += (
                                    f"    Dimensions: {media.width}x{media.height}\n"
                                )

                            if hasattr(media, "alt_text") and media.alt_text:
                                result += f"    Alt Text: {media.alt_text}\n"

                            if hasattr(media, "duration_ms") and media.duration_ms:
                                result += f"    Duration: {media.duration_ms}ms\n"

                # Handle attachments section
                elif (
                    tweet.attachments
                    and hasattr(tweet.attachments, "media_keys")
                    and tweet.attachments.media_keys
                ):
                    result += f"Media Keys: {', '.join(tweet.attachments.media_keys)}\n"
                    result += "Note: Media details not available in response includes\n"

                result += f"Tweet URL: https://x.com/i/web/status/{tweet.id}"

                logger.info(f"Successfully retrieved tweet: {tweet_id}")
                return result
            else:
                return f"Tweet with ID {tweet_id} not found or not accessible"

        except Exception as e:
            logger.error(f"Error getting tweet {tweet_id}: {str(e)}")
            return f"Error getting tweet: {str(e)}"

    def _run(self, tweet_id: str, **kwargs) -> str:
        return self._deploy(tweet_id, **kwargs)

    async def _arun(self, tweet_id: str, **kwargs) -> str:
        """Execute the tool to get a tweet by ID asynchronously."""

        if self.agent_id is None:
            raise ValueError("Agent ID is required")

        try:
            # Find the DAO associated with this agent through holders
            from app.backend.models import HolderFilter

            holders = backend.list_holders(filters=HolderFilter(agent_id=self.agent_id))
            if not holders:
                return "No DAO association found for this agent"

            # Get X creds for the DAO
            dao_id = holders[0].dao_id
            x_creds = backend.list_x_creds(
                filters=XCredsFilter(dao_id=dao_id),
            )
            if not x_creds:
                return "No X creds found for this agent's DAO"

            x_creds = x_creds[0]
            twitter_service = TwitterService(
                consumer_key=x_creds.consumer_key,
                consumer_secret=x_creds.consumer_secret,
                access_token=x_creds.access_token,
                access_secret=x_creds.access_secret,
                client_id=x_creds.client_id,
                client_secret=x_creds.client_secret,
            )
            await twitter_service._ainitialize()

            # Get the full response with includes (media data)
            response = await twitter_service.client.get_tweet(
                id=tweet_id,
                tweet_fields=[
                    "id",
                    "text",
                    "created_at",
                    "author_id",
                    "conversation_id",
                    "in_reply_to_user_id",
                    "referenced_tweets",
                    "public_metrics",
                    "entities",
                    "attachments",
                    "context_annotations",
                    "withheld",
                    "reply_settings",
                    "lang",
                ],
                expansions=[
                    "author_id",
                    "referenced_tweets.id",
                    "referenced_tweets.id.author_id",
                    "entities.mentions.username",
                    "attachments.media_keys",
                    "attachments.poll_ids",
                    "in_reply_to_user_id",
                    "geo.place_id",
                ],
                media_fields=[
                    "duration_ms",
                    "height",
                    "media_key",
                    "preview_image_url",
                    "type",
                    "url",
                    "width",
                    "public_metrics",
                    "alt_text",
                ],
                user_fields=[
                    "id",
                    "name",
                    "username",
                    "created_at",
                    "description",
                    "entities",
                    "location",
                    "pinned_tweet_id",
                    "profile_image_url",
                    "protected",
                    "public_metrics",
                    "url",
                    "verified",
                    "withheld",
                ],
            )

            if response and response.data:
                tweet = response.data

                # Format comprehensive tweet data
                result = f"Tweet ID: {tweet.id}\n"
                result += f"Text: {tweet.text}\n"
                result += f"Author ID: {tweet.author_id}\n"
                result += f"Created: {tweet.created_at}\n"
                result += f"Language: {tweet.lang}\n"
                result += f"Conversation ID: {tweet.conversation_id}\n"

                if tweet.public_metrics:
                    metrics = tweet.public_metrics
                    result += f"Metrics - Retweets: {metrics.retweet_count}, "
                    result += f"Likes: {metrics.like_count}, "
                    result += f"Replies: {metrics.reply_count}, "
                    result += f"Quotes: {metrics.quote_count}\n"

                if tweet.in_reply_to_user_id:
                    result += f"In reply to user: {tweet.in_reply_to_user_id}\n"

                if (
                    tweet.entities
                    and hasattr(tweet.entities, "hashtags")
                    and tweet.entities.hashtags
                ):
                    hashtags = [tag.tag for tag in tweet.entities.hashtags]
                    result += f"Hashtags: {', '.join(hashtags)}\n"

                if (
                    tweet.entities
                    and hasattr(tweet.entities, "mentions")
                    and tweet.entities.mentions
                ):
                    mentions = [mention.username for mention in tweet.entities.mentions]
                    result += f"Mentions: {', '.join(mentions)}\n"

                if (
                    tweet.entities
                    and hasattr(tweet.entities, "urls")
                    and tweet.entities.urls
                ):
                    urls = [url.expanded_url for url in tweet.entities.urls]
                    result += f"URLs: {', '.join(urls)}\n"

                # Handle media attachments (images, videos, etc.)
                if (
                    hasattr(response, "includes")
                    and response.includes
                    and hasattr(response.includes, "media")
                ):
                    media_list = response.includes.media
                    if media_list:
                        result += f"Media Attachments ({len(media_list)}):\n"
                        for i, media in enumerate(media_list, 1):
                            result += f"  Media {i}:\n"
                            result += f"    Type: {media.type}\n"
                            result += f"    Media Key: {media.media_key}\n"

                            if hasattr(media, "url") and media.url:
                                result += f"    URL: {media.url}\n"

                            if (
                                hasattr(media, "preview_image_url")
                                and media.preview_image_url
                            ):
                                result += (
                                    f"    Preview URL: {media.preview_image_url}\n"
                                )

                            if hasattr(media, "width") and media.width:
                                result += (
                                    f"    Dimensions: {media.width}x{media.height}\n"
                                )

                            if hasattr(media, "alt_text") and media.alt_text:
                                result += f"    Alt Text: {media.alt_text}\n"

                            if hasattr(media, "duration_ms") and media.duration_ms:
                                result += f"    Duration: {media.duration_ms}ms\n"

                # Handle attachments section
                elif (
                    tweet.attachments
                    and hasattr(tweet.attachments, "media_keys")
                    and tweet.attachments.media_keys
                ):
                    result += f"Media Keys: {', '.join(tweet.attachments.media_keys)}\n"
                    result += "Note: Media details not available in response includes\n"

                result += f"Tweet URL: https://x.com/i/web/status/{tweet.id}"

                logger.info(f"Successfully retrieved tweet: {tweet_id}")
                return result
            else:
                return f"Tweet with ID {tweet_id} not found or not accessible"

        except Exception as e:
            logger.error(f"Error getting tweet {tweet_id}: {str(e)}")
            return f"Error getting tweet: {str(e)}"
