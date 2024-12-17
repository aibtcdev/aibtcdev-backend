from lib.logger import configure_logger
from pytwitter import Api
from pytwitter.models import Tweet, User
from typing import List, Optional

logger = configure_logger(__name__)


class TwitterService:
    def __init__(
        self,
        consumer_key: str,
        consumer_secret: str,
        access_token: str,
        access_secret: str,
        client_id: str,
        client_secret: str,
    ):
        """Initialize the Twitter service with API credentials."""
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.access_token = access_token
        self.access_secret = access_secret
        self.client_id = client_id
        self.client_secret = client_secret
        self.client = None

    async def initialize(self) -> None:
        """Initialize the Twitter client."""
        try:
            self.client = Api(
                client_id=self.client_id,
                client_secret=self.client_secret,
                consumer_key=self.consumer_key,
                consumer_secret=self.consumer_secret,
                access_token=self.access_token,
                access_secret=self.access_secret,
                application_only_auth=False,
            )
            logger.info("Twitter client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Twitter client: {str(e)}")
            raise

    async def post_tweet(
        self, text: str, reply_in_reply_to_tweet_id: Optional[str] = None
    ) -> Optional[Tweet]:
        """
        Post a new tweet or reply to an existing tweet.

        Args:
            text: The content of the tweet
            reply_in_reply_to_tweet_id: Optional ID of tweet to reply to

        Returns:
            Tweet data if successful, None if failed
        """
        try:
            if self.client is None:
                raise Exception("Twitter client is not initialized")
            response = self.client.create_tweet(
                text=text, reply_in_reply_to_tweet_id=reply_in_reply_to_tweet_id
            )
            logger.info(f"Successfully posted tweet: {text[:20]}...")
            if type(response) == Tweet:
                return response
        except Exception as e:
            logger.error(f"Failed to post tweet: {str(e)}")
            return None

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """
        Get user information by username.

        Args:
            username: Twitter username without @ symbol

        Returns:
            User data if found, None if not found or error
        """
        try:
            if self.client is None:
                raise Exception("Twitter client is not initialized")
            response = self.client.get_user(username=username)
            if type(response) == User:
                return response
        except Exception as e:
            logger.error(f"Failed to get user info for {username}: {str(e)}")
            return None

    async def get_mentions_by_user_id(
        self, user_id: str, max_results: int = 100
    ) -> List[Tweet]:
        """
        Get mentions for a specific user.

        Args:
            user_id: Twitter user ID to get mentions for
            max_results: Maximum number of mentions to return (default 100)

        Returns:
            List of mention data
        """
        try:
            if self.client is None:
                raise Exception("Twitter client is not initialized")
            response = self.client.get_mentions(
                user_id=user_id,
                max_results=max_results,
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
                place_fields=[
                    "contained_within",
                    "country",
                    "country_code",
                    "full_name",
                    "geo",
                    "id",
                    "name",
                    "place_type",
                ],
                poll_fields=[
                    "duration_minutes",
                    "end_datetime",
                    "id",
                    "options",
                    "voting_status",
                ],
            )
            logger.info(f"Successfully retrieved {len(response.data)} mentions")
            return response.data

        except Exception as e:
            logger.error(f"Failed to get mentions: {str(e)}")
            return []
