import re
from io import BytesIO
from typing import Any, Dict, List, Optional, TypedDict
from urllib.parse import urlparse

import requests
import tweepy
from pydantic import BaseModel

from app.backend.factory import backend
from app.backend.models import (
    QueueMessageCreate,
    XTweetBase,
    XTweetCreate,
    XTweetFilter,
    XUserCreate,
    XUserFilter,
)
from app.config import config
from app.lib.logger import configure_logger

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
        bearer_token: str,
    ):
        """Initialize the Twitter service with API credentials."""
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.access_token = access_token
        self.access_secret = access_secret
        self.client_id = client_id
        self.client_secret = client_secret
        self.bearer_token = bearer_token
        self.client = None
        self.api = None

    async def _ainitialize(self) -> None:
        self.initialize()

    def initialize(self) -> None:
        """Initialize the Twitter client and API."""
        try:
            # Initialize OAuth1 handler for API v1.1 (needed for media upload)
            auth = tweepy.OAuth1UserHandler(
                self.consumer_key,
                self.consumer_secret,
                self.access_token,
                self.access_secret,
            )
            self.api = tweepy.API(auth, wait_on_rate_limit=True)

            # Initialize Client for API v2 (used for tweet creation)
            self.client = tweepy.Client(
                consumer_key=self.consumer_key,
                consumer_secret=self.consumer_secret,
                access_token=self.access_token,
                access_token_secret=self.access_secret,
                bearer_token=self.bearer_token,
                wait_on_rate_limit=True,
            )
            logger.info("Twitter client and API initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Twitter client: {str(e)}")
            raise

    def _get_extension(self, url: str) -> str:
        """Extract file extension from URL."""
        path = urlparse(url).path.lower()
        for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]:
            if path.endswith(ext):
                return ext
        return ".jpg"

    def _split_text_into_chunks(self, text: str, limit: int = 280) -> List[str]:
        """Split text into chunks not exceeding the limit without cutting words."""
        words = text.split()
        chunks = []
        current = ""
        for word in words:
            if len(current) + len(word) + (1 if current else 0) <= limit:
                current = f"{current} {word}".strip()
            else:
                if current:
                    chunks.append(current)
                current = word
        if current:
            chunks.append(current)
        return chunks

    async def post_tweet_with_media(
        self,
        image_url: str,
        text: str,
        reply_id: Optional[str] = None,
    ) -> Optional[tweepy.Response]:
        """Post a tweet with media attachment."""
        try:
            if self.api is None or self.client is None:
                raise Exception("Twitter client is not initialized")

            headers = {"User-Agent": "Mozilla/5.0 (compatible; AIBTC Bot/1.0)"}
            response = requests.get(image_url, headers=headers, timeout=30)
            response.raise_for_status()

            # Validate content type and size
            content_type = response.headers.get("content-type", "").lower()
            if not any(
                ct in content_type
                for ct in ["image/jpeg", "image/png", "image/gif", "image/webp"]
            ):
                logger.warning(f"Unsupported content type: {content_type}")
                return None

            if len(response.content) > 5 * 1024 * 1024:  # 5MB limit
                logger.warning(f"Image too large: {len(response.content)} bytes")
                return None

            # Upload media using API v1.1
            extension = self._get_extension(image_url)
            media = self.api.media_upload(
                filename=f"image{extension}",
                file=BytesIO(response.content),
            )

            # Create tweet with media using API v2
            result = self.client.create_tweet(
                text=text,
                media_ids=[media.media_id_string],
                in_reply_to_tweet_id=reply_id,
            )

            if result and result.data:
                logger.info(
                    f"Successfully posted tweet with media: {result.data['id']}"
                )
                return result

            return None

        except Exception as e:
            logger.error(f"Failed to post tweet with media: {str(e)}")
            return None

    async def post_tweet_with_chunks(
        self,
        text: str,
        image_url: Optional[str] = None,
        reply_id: Optional[str] = None,
    ) -> Optional[List[tweepy.Response]]:
        """Post a tweet, splitting into chunks if necessary and handling media."""
        try:
            if self.client is None:
                raise Exception("Twitter client is not initialized")

            # Process image URL if present
            if image_url:
                # Remove image URL from text
                text = re.sub(re.escape(image_url), "", text).strip()
                text = re.sub(r"\s+", " ", text)

            # Split text into chunks
            chunks = self._split_text_into_chunks(text)
            previous_tweet_id = reply_id
            responses = []

            for index, chunk in enumerate(chunks):
                try:
                    if index == 0 and image_url:
                        # First chunk with media
                        response = await self.post_tweet_with_media(
                            image_url=image_url,
                            text=chunk,
                            reply_id=previous_tweet_id,
                        )
                    else:
                        # Regular tweet
                        response = await self._apost_tweet(
                            text=chunk,
                            reply_in_reply_to_tweet_id=previous_tweet_id,
                        )

                    if response and response.data:
                        responses.append(response)
                        previous_tweet_id = response.data["id"]
                        logger.info(
                            f"Successfully posted tweet chunk {index + 1}: {response.data['id']}"
                        )
                    else:
                        logger.error(f"Failed to send tweet chunk {index + 1}")
                        if index == 0:  # If first chunk fails, whole message fails
                            return None

                except Exception as chunk_error:
                    logger.error(f"Error sending chunk {index + 1}: {str(chunk_error)}")
                    if index == 0:  # Critical failure on first chunk
                        raise chunk_error

            return responses if responses else None

        except Exception as e:
            logger.error(f"Error posting tweet with chunks: {str(e)}")
            return None

    async def _apost_tweet(
        self, text: str, reply_in_reply_to_tweet_id: Optional[str] = None
    ) -> Optional[tweepy.Response]:
        """
        Post a new tweet or reply to an existing tweet.

        Args:
            text: The content of the tweet
            reply_in_reply_to_tweet_id: Optional ID of tweet to reply to

        Returns:
            Tweet response if successful, None if failed
        """
        return await self.post_tweet(text, reply_in_reply_to_tweet_id)

    async def post_tweet(
        self, text: str, reply_in_reply_to_tweet_id: Optional[str] = None
    ) -> Optional[tweepy.Response]:
        """
        Post a new tweet or reply to an existing tweet.

        Args:
            text: The content of the tweet
            reply_in_reply_to_tweet_id: Optional ID of tweet to reply to

        Returns:
            Tweet response if successful, None if failed
        """
        try:
            if self.client is None:
                raise Exception("Twitter client is not initialized")

            response = self.client.create_tweet(
                text=text, in_reply_to_tweet_id=reply_in_reply_to_tweet_id
            )

            if response and response.data:
                logger.info(
                    f"Successfully posted tweet: {text[:20]}... (ID: {response.data['id']})"
                )
                return response
            else:
                logger.error(f"Failed to post tweet: {text[:20]}...")
                return None

        except Exception as e:
            logger.error(f"Failed to post tweet: {str(e)}")
            return None

    async def get_user_by_username(self, username: str) -> Optional[tweepy.User]:
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
            if response and response.data:
                return response.data
            return None

        except Exception as e:
            logger.error(f"Failed to get user info for {username}: {str(e)}")
            return None

    async def get_user_by_user_id(self, user_id: str) -> Optional[tweepy.User]:
        """
        Get user information by user ID.

        Args:
            user_id: Twitter user ID

        Returns:
            User data if found, None if not found or error
        """
        try:
            if self.client is None:
                raise Exception("Twitter client is not initialized")

            response = self.client.get_user(id=user_id)
            if response and response.data:
                return response.data
            return None

        except Exception as e:
            logger.error(f"Failed to get user info for {user_id}: {str(e)}")
            return None

    async def get_mentions_by_user_id(
        self, user_id: str, max_results: int = 100
    ) -> List[tweepy.Tweet]:
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
                id=user_id,
                max_results=min(max_results, 100),  # API limit
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

            if response and response.data:
                logger.info(f"Successfully retrieved {len(response.data)} mentions")
                return response.data
            else:
                logger.info("No mentions found")
                return []

        except Exception as e:
            logger.error(f"Failed to get mentions: {str(e)}")
            return []

    async def get_me(self) -> Optional[tweepy.User]:
        """
        Get information about the authenticated user.

        Returns:
            User data if successful, None if failed
        """
        try:
            if self.client is None:
                raise Exception("Twitter client is not initialized")

            response = self.client.get_me()
            if response and response.data:
                return response.data
            return None

        except Exception as e:
            logger.error(f"Failed to get authenticated user info: {str(e)}")
            return None

    async def follow_user(self, target_username: str) -> bool:
        """
        Follow a user using their username. Uses the authenticated user as the follower.

        Args:
            target_username: Username of the account to follow (without @ symbol)

        Returns:
            True if successful, False if failed
        """
        try:
            if self.client is None:
                raise Exception("Twitter client is not initialized")

            # Get target user's ID
            target_user = await self.get_user_by_username(target_username)
            if not target_user:
                raise Exception(f"Failed to get user info for {target_username}")

            # Follow the user
            response = self.client.follow_user(target_user_id=target_user.id)
            if response:
                logger.info(f"Successfully followed user: {target_username}")
                return True
            return False

        except Exception as e:
            logger.error(f"Failed to follow user {target_username}: {str(e)}")
            return False

    async def unfollow_user(self, target_username: str) -> bool:
        """
        Unfollow a user using their username. Uses the authenticated user as the unfollower.

        Args:
            target_username: Username of the account to unfollow (without @ symbol)

        Returns:
            True if successful, False if failed
        """
        try:
            if self.client is None:
                raise Exception("Twitter client is not initialized")

            # Get target user's ID
            target_user = await self.get_user_by_username(target_username)
            if not target_user:
                raise Exception(f"Failed to get user info for {target_username}")

            # Unfollow the user
            response = self.client.unfollow_user(target_user_id=target_user.id)
            if response:
                logger.info(f"Successfully unfollowed user: {target_username}")
                return True
            return False

        except Exception as e:
            logger.error(f"Failed to unfollow user {target_username}: {str(e)}")
            return False

    async def get_tweet_by_id(self, tweet_id: str) -> Optional[tweepy.Response]:
        """
        Get a tweet by its ID using Twitter API v2.

        Args:
            tweet_id: The ID of the tweet to retrieve

        Returns:
            Full response object if found, None if not found or error
        """
        try:
            if self.client is None:
                raise Exception("Twitter client is not initialized")

            response = self.client.get_tweet(
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
                    "variants",
                ],
            )

            if response and response.data:
                logger.info(f"Successfully retrieved tweet: {tweet_id}")
                return response
            else:
                logger.warning(f"Tweet not found: {tweet_id}")
                return None

        except Exception as e:
            logger.error(f"Failed to get tweet {tweet_id}: {str(e)}")
            return None

    async def get_status_by_id(
        self, tweet_id: str, tweet_mode: str = "extended"
    ) -> Optional[tweepy.models.Status]:
        """
        Get a tweet by its ID using Twitter API v1.1 (for extended tweet support).

        Args:
            tweet_id: The ID of the tweet to retrieve
            tweet_mode: Tweet mode - "extended" for full text, "compat" for compatibility mode

        Returns:
            Status object if found, None if not found or error
        """
        try:
            if self.api is None:
                raise Exception("Twitter API is not initialized")

            status = self.api.get_status(
                id=tweet_id,
                tweet_mode=tweet_mode,
                include_entities=True,
                include_ext_alt_text=True,
                include_card_uri=True,
            )

            if status:
                logger.info(f"Successfully retrieved status: {tweet_id}")
                return status
            else:
                logger.warning(f"Status not found: {tweet_id}")
                return None

        except Exception as e:
            logger.error(f"Failed to get status {tweet_id}: {str(e)}")
            return None

    async def search_tweets_by_conversation_id(
        self, conversation_id: str, max_results: int = 100
    ) -> List[tweepy.Tweet]:
        """
        Search for tweets in a specific conversation using conversation_id.

        Args:
            conversation_id: The conversation ID to search for
            max_results: Maximum number of tweets to return (default 100, max 100)

        Returns:
            List of tweets in the conversation
        """
        try:
            if self.client is None:
                raise Exception("Twitter client is not initialized")

            query = f"conversation_id:{conversation_id}"

            response = self.client.search_recent_tweets(
                query=query,
                max_results=min(max_results, 100),  # API limit
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
                    "variants",
                ],
            )

            if response and response.data:
                logger.info(
                    f"Found {len(response.data)} tweets in conversation {conversation_id}"
                )
                return response.data
            else:
                logger.info(f"No tweets found in conversation {conversation_id}")
                return []

        except Exception as e:
            logger.error(
                f"Failed to search tweets by conversation ID {conversation_id}: {str(e)}"
            )
            return []

    async def get_conversation_context(
        self, tweet_id: str, include_later_replies: bool = True
    ) -> Dict[str, Any]:
        """
        Get full conversation context for any tweet ID following the decision tree:

        1. Fetch the tweet info
        2. Check if it's the original post (tweet.id == tweet.conversation_id)
        3. If original: get all replies
        4. If reply: get original + this tweet + optionally later replies

        Args:
            tweet_id: ID of any tweet in the conversation
            include_later_replies: Whether to include replies that came after the given tweet

        Returns:
            Dictionary containing:
            - original_tweet: The original tweet that started the conversation
            - target_tweet: The tweet that was requested (if different from original)
            - replies: List of reply tweets
            - is_original: Boolean indicating if the requested tweet is the original
            - conversation_id: The conversation ID
        """
        try:
            if self.client is None:
                raise Exception("Twitter client is not initialized")

            # Step 1: Fetch the tweet info
            tweet_response = await self.get_tweet_by_id(tweet_id)
            if not tweet_response or not tweet_response.data:
                logger.error(f"Could not fetch tweet {tweet_id}")
                return {
                    "original_tweet": None,
                    "target_tweet": None,
                    "replies": [],
                    "is_original": False,
                    "conversation_id": None,
                    "error": f"Tweet {tweet_id} not found",
                }

            target_tweet = tweet_response.data
            conversation_id = target_tweet.conversation_id

            # Step 2: Check if it's the original post
            is_original = str(target_tweet.id) == str(conversation_id)

            logger.info(
                f"Tweet {tweet_id} - Original: {is_original}, Conversation: {conversation_id}"
            )

            if is_original:
                # This is the original post - get all replies
                logger.debug(f"Fetching replies for original tweet {tweet_id}")
                all_conversation_tweets = await self.search_tweets_by_conversation_id(
                    conversation_id
                )

                # Filter out the original tweet from replies
                replies = [
                    tweet
                    for tweet in all_conversation_tweets
                    if str(tweet.id) != str(conversation_id)
                ]

                # Sort replies by creation time
                replies.sort(
                    key=lambda x: x.created_at
                    if hasattr(x, "created_at") and x.created_at
                    else ""
                )

                return {
                    "original_tweet": target_tweet,
                    "target_tweet": target_tweet,
                    "replies": replies,
                    "is_original": True,
                    "conversation_id": conversation_id,
                    "total_tweets": len(replies) + 1,
                }
            else:
                # This is a reply - get the original and conversation context
                logger.debug(
                    f"Fetching original tweet and context for reply {tweet_id}"
                )

                # Get the original tweet
                original_response = await self.get_tweet_by_id(conversation_id)
                original_tweet = original_response.data if original_response else None

                if not original_tweet:
                    logger.error(f"Could not fetch original tweet {conversation_id}")
                    return {
                        "original_tweet": None,
                        "target_tweet": target_tweet,
                        "replies": [],
                        "is_original": False,
                        "conversation_id": conversation_id,
                        "error": f"Original tweet {conversation_id} not found",
                    }

                # Get all tweets in the conversation
                all_conversation_tweets = await self.search_tweets_by_conversation_id(
                    conversation_id
                )

                # Sort all tweets by creation time
                all_tweets = [original_tweet] + all_conversation_tweets
                all_tweets.sort(
                    key=lambda x: x.created_at
                    if hasattr(x, "created_at") and x.created_at
                    else ""
                )

                # Find the position of the target tweet
                target_position = -1
                for i, tweet in enumerate(all_tweets):
                    if str(tweet.id) == str(tweet_id):
                        target_position = i
                        break

                if include_later_replies and target_position >= 0:
                    # Include tweets from the original up to and including later replies
                    relevant_tweets = all_tweets
                    replies = [
                        tweet
                        for tweet in relevant_tweets
                        if str(tweet.id) != str(conversation_id)
                    ]
                else:
                    # Include tweets from the original up to the target tweet
                    if target_position >= 0:
                        relevant_tweets = all_tweets[: target_position + 1]
                        replies = [
                            tweet
                            for tweet in relevant_tweets
                            if str(tweet.id) != str(conversation_id)
                        ]
                    else:
                        # Fallback: just return what we have
                        replies = [
                            tweet
                            for tweet in all_conversation_tweets
                            if str(tweet.id) != str(conversation_id)
                        ]

                return {
                    "original_tweet": original_tweet,
                    "target_tweet": target_tweet,
                    "replies": replies,
                    "is_original": False,
                    "conversation_id": conversation_id,
                    "total_tweets": len(replies) + 1,
                }

        except Exception as e:
            logger.error(
                f"Failed to get conversation context for tweet {tweet_id}: {str(e)}"
            )
            return {
                "original_tweet": None,
                "target_tweet": None,
                "replies": [],
                "is_original": False,
                "conversation_id": None,
                "error": str(e),
            }

    async def is_original_tweet(self, tweet_id: str) -> Optional[bool]:
        """
        Check if a tweet is the original post in a conversation.

        Args:
            tweet_id: ID of the tweet to check

        Returns:
            True if original, False if reply, None if error/not found
        """
        try:
            tweet_response = await self.get_tweet_by_id(tweet_id)
            if not tweet_response or not tweet_response.data:
                return None

            tweet = tweet_response.data
            return str(tweet.id) == str(tweet.conversation_id)

        except Exception as e:
            logger.error(f"Failed to check if tweet {tweet_id} is original: {str(e)}")
            return None

    async def get_tweet_replies(self, tweet_id: str) -> List[tweepy.Tweet]:
        """
        Get all replies to a specific tweet (only works if the tweet is the original post).

        Args:
            tweet_id: ID of the original tweet

        Returns:
            List of reply tweets
        """
        try:
            # First verify this is an original tweet
            is_original = await self.is_original_tweet(tweet_id)
            if not is_original:
                logger.warning(
                    f"Tweet {tweet_id} is not an original tweet, cannot get direct replies"
                )
                return []

            # Get all tweets in the conversation
            all_tweets = await self.search_tweets_by_conversation_id(tweet_id)

            # Filter out the original tweet
            replies = [tweet for tweet in all_tweets if str(tweet.id) != str(tweet_id)]

            # Sort by creation time
            replies.sort(
                key=lambda x: x.created_at
                if hasattr(x, "created_at") and x.created_at
                else ""
            )

            logger.info(f"Found {len(replies)} replies to tweet {tweet_id}")
            return replies

        except Exception as e:
            logger.error(f"Failed to get replies for tweet {tweet_id}: {str(e)}")
            return []

    async def get_user_timeline(
        self,
        user_id: str,
        count: int = 5,
        exclude_replies: bool = True,
        include_rts: bool = False,
    ) -> List[tweepy.Tweet]:
        """
        Get a user's timeline (recent tweets).

        Args:
            user_id: Twitter user ID
            count: Maximum number of tweets to return (default 5, max 100)
            exclude_replies: Whether to exclude reply tweets (default True)
            include_rts: Whether to include retweets (default False)

        Returns:
            List of tweets from the user's timeline
        """
        try:
            if self.client is None:
                raise Exception("Twitter client is not initialized")

            # Build the exclude parameter for API v2
            exclude_list = []
            if exclude_replies:
                exclude_list.append("replies")
            if not include_rts:
                exclude_list.append("retweets")

            response = self.client.get_users_tweets(
                id=user_id,
                max_results=min(count, 100),  # API limit
                exclude=exclude_list if exclude_list else None,
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
                    "variants",
                ],
            )

            if response and response.data:
                logger.info(
                    f"Successfully retrieved {len(response.data)} tweets from user {user_id}'s timeline"
                )
                return response.data
            else:
                logger.info(f"No tweets found for user {user_id}")
                return []

        except Exception as e:
            logger.error(f"Failed to get timeline for user {user_id}: {str(e)}")
            return []


class UserProfile(TypedDict):
    """Type definition for user profile data."""

    name: str
    age: int
    email: str


class TweetData(BaseModel):
    """Pydantic model for tweet data."""

    tweet_id: Optional[str] = None
    author_id: Optional[str] = None
    text: Optional[str] = None
    conversation_id: Optional[str] = None

    @classmethod
    def from_tweepy_tweet(cls, tweet: "tweepy.Tweet") -> "TweetData":
        """Create TweetData from a tweepy Tweet object."""
        return cls(
            tweet_id=tweet.id,
            author_id=tweet.author_id,
            text=tweet.text,
            conversation_id=tweet.conversation_id,
        )


class TwitterConfig(BaseModel):
    """Configuration for Twitter service."""

    consumer_key: str
    consumer_secret: str
    client_id: str
    client_secret: str
    access_token: str
    access_secret: str
    bearer_token: str
    user_id: str
    whitelisted_authors: List[str]
    whitelist_enabled: bool = False


class TweetRepository:
    """Repository for handling tweet storage and retrieval."""

    async def store_tweet(self, tweet_data: TweetData) -> None:
        """Store tweet and author data in the database."""
        try:
            authors = await backend.list_x_users(
                filters=XUserFilter(user_id=tweet_data.author_id)
            )
            if authors and len(authors) > 0:
                author = authors[0]
                logger.debug(
                    f"Found existing author {tweet_data.author_id} in database"
                )
            else:
                logger.info(f"Creating new author record for {tweet_data.author_id}")
                author = await backend.create_x_user(
                    XUserCreate(user_id=str(tweet_data.author_id))
                )

            logger.debug(f"Creating tweet record for {tweet_data.tweet_id}")
            await backend.create_x_tweet(
                XTweetCreate(
                    author_id=author.id,
                    tweet_id=tweet_data.tweet_id,
                    message=tweet_data.text,
                    conversation_id=tweet_data.conversation_id,
                )
            )
        except Exception as e:
            logger.error(f"Failed to store tweet/author data: {str(e)}", exc_info=True)
            raise

    async def update_tweet_analysis(
        self,
        tweet_id: str,
        is_worthy: bool,
        tweet_type: str,
        confidence_score: float,
        reason: str,
    ) -> None:
        """Update tweet with analysis results."""
        try:
            tweets = await backend.list_x_tweets(
                filters=XTweetFilter(tweet_id=tweet_id)
            )
            if tweets and len(tweets) > 0:
                logger.debug("Updating existing tweet record with analysis results")
                await backend.update_x_tweet(
                    x_tweet_id=tweets[0].id,
                    update_data=XTweetBase(
                        is_worthy=is_worthy,
                        tweet_type=tweet_type,
                        confidence_score=confidence_score,
                        reason=reason,
                    ),
                )
        except Exception as e:
            logger.error(f"Failed to update tweet analysis: {str(e)}", exc_info=True)
            raise

    async def get_conversation_history(
        self, conversation_id: str, user_id: str
    ) -> List[Dict[str, str]]:
        """Retrieve conversation history for a given conversation ID."""
        try:
            conversation_tweets = await backend.list_x_tweets(
                filters=XTweetFilter(conversation_id=conversation_id)
            )
            logger.debug(
                f"Retrieved {len(conversation_tweets)} tweets from conversation {conversation_id}"
            )
            return [
                {
                    "role": "user" if tweet.author_id != user_id else "assistant",
                    "content": tweet.message,
                }
                for tweet in conversation_tweets
                if tweet.message
            ]
        except Exception as e:
            logger.error(
                f"Failed to retrieve conversation history: {str(e)}", exc_info=True
            )
            raise


class TweetAnalyzer:
    """Handles tweet analysis and processing logic."""

    def __init__(self, tweet_repository: TweetRepository):
        """Initialize with dependencies."""
        self.tweet_repository = tweet_repository

    async def analyze_tweet_content(
        self, tweet_data: TweetData, history: List[Dict[str, str]]
    ) -> Dict:
        """Analyze tweet content and determine if it needs processing."""
        logger.info(
            f"Analyzing tweet {tweet_data.tweet_id} from user {tweet_data.author_id}"
        )
        logger.debug(f"Tweet content: {tweet_data.text}")
        logger.debug(f"Conversation history size: {len(history)} messages")

        filtered_content = "\n".join(
            f"{msg['role']}: {msg['content']}" for msg in history
        )

        try:
            # Import here to avoid circular dependency
            from app.services.ai.simple_workflows import analyze_tweet

            analysis_result = await analyze_tweet(
                tweet_text=tweet_data.text,
                filtered_content=filtered_content,
            )

            logger.info(
                f"Analysis complete for {tweet_data.tweet_id} - "
                f"Worthy: {analysis_result['is_worthy']}, "
                f"Type: {analysis_result['tweet_type']}, "
                f"Confidence: {analysis_result['confidence_score']}"
            )
            logger.debug(f"Analysis reason: {analysis_result['reason']}")

            await self.tweet_repository.update_tweet_analysis(
                tweet_id=tweet_data.tweet_id,
                is_worthy=analysis_result["is_worthy"],
                tweet_type=analysis_result["tweet_type"],
                confidence_score=analysis_result["confidence_score"],
                reason=analysis_result["reason"],
            )

            return analysis_result
        except Exception as e:
            logger.error(
                f"Analysis failed for tweet {tweet_data.tweet_id}: {str(e)}",
                exc_info=True,
            )
            raise


class TwitterMentionHandler:
    """Handles Twitter mention processing and responses."""

    def __init__(
        self,
        config: TwitterConfig,
        tweet_repository: TweetRepository,
        tweet_analyzer: TweetAnalyzer,
    ):
        """Initialize with dependencies."""
        self.config = config
        self.tweet_repository = tweet_repository
        self.tweet_analyzer = tweet_analyzer
        self.twitter_service = TwitterService(
            consumer_key=config.consumer_key,
            consumer_secret=config.consumer_secret,
            client_id=config.client_id,
            client_secret=config.client_secret,
            access_token=config.access_token,
            access_secret=config.access_secret,
            bearer_token=config.bearer_token,
        )

    async def _post_response(
        self, tweet_data: TweetData, response_content: str
    ) -> None:
        """Post a response tweet.

        Args:
            tweet_data: Data about the tweet to respond to
            response_content: Content of the response tweet
        """
        logger.debug(f"Posting response to tweet {tweet_data.tweet_id}")
        await self.twitter_service._ainitialize()
        await self.twitter_service._apost_tweet(
            text=response_content, reply_in_reply_to_tweet_id=tweet_data.tweet_id
        )

    def _is_author_whitelisted(self, author_id: str) -> bool:
        """Check if the author is in the whitelist."""
        logger.debug(f"Checking whitelist status for author {author_id}")
        is_whitelisted = str(author_id) in self.config.whitelisted_authors
        logger.debug(f"Author {author_id} whitelist status: {is_whitelisted}")
        return is_whitelisted

    async def _handle_mention(self, mention) -> None:
        """Process a single mention for analysis."""
        tweet_data = TweetData.from_tweepy_tweet(mention)

        logger.debug(
            f"Processing mention - Tweet ID: {tweet_data.tweet_id}, "
            f"Author: {tweet_data.author_id}, Text: {tweet_data.text[:50]}..."
        )

        # Check if tweet exists in our database
        try:
            existing_tweets = await backend.list_x_tweets(
                filters=XTweetFilter(tweet_id=tweet_data.tweet_id)
            )
            if existing_tweets and len(existing_tweets) > 0:
                logger.debug(
                    f"Tweet {tweet_data.tweet_id} already exists in database, skipping processing"
                )
                return
        except Exception as e:
            logger.error(
                f"Database error checking tweet {tweet_data.tweet_id}: {str(e)}",
                exc_info=True,
            )
            raise

        await self.tweet_repository.store_tweet(tweet_data)

        try:
            if self.config.whitelist_enabled:
                if self._is_author_whitelisted(tweet_data.author_id):
                    logger.info(
                        f"Processing whitelisted mention {tweet_data.tweet_id} "
                        f"from user {tweet_data.author_id}"
                    )
                    await self._process_mention(tweet_data)
                else:
                    logger.warning(
                        f"Skipping non-whitelisted mention {tweet_data.tweet_id} "
                        f"from user {tweet_data.author_id}"
                    )
            else:
                logger.debug("Whitelist check disabled, processing all mentions")
                await self._process_mention(tweet_data)
        except Exception as e:
            logger.error(
                f"Failed to process mention {tweet_data.tweet_id}: {str(e)}",
                exc_info=True,
            )
            raise

    async def _process_mention(self, tweet_data: TweetData) -> None:
        """Process mention after validation."""
        history = await self.tweet_repository.get_conversation_history(
            tweet_data.conversation_id, self.config.user_id
        )

        analysis_result = await self.tweet_analyzer.analyze_tweet_content(
            tweet_data, history
        )

        if analysis_result["is_worthy"] and analysis_result["tool_request"]:
            logger.info(
                f"Queueing tool request for tweet {tweet_data.tweet_id} - "
                f"Tool: {analysis_result['tool_request'].tool_name}"
            )
            backend.create_queue_message(
                new_queue_message=QueueMessageCreate(
                    type="daos",
                    tweet_id=tweet_data.tweet_id,
                    conversation_id=tweet_data.conversation_id,
                    message=analysis_result["tool_request"].model_dump(),
                )
            )
        elif analysis_result["is_worthy"]:
            logger.debug(
                f"Tweet {tweet_data.tweet_id} worthy but no tool request present"
            )
        else:
            logger.debug(f"Tweet {tweet_data.tweet_id} not worthy of processing")

    async def process_mentions(self) -> None:
        """Process all new mentions for analysis."""
        try:
            logger.info("Starting Twitter mention processing")
            await self.twitter_service._ainitialize()
            mentions = await self.twitter_service.get_mentions_by_user_id(
                self.config.user_id
            )

            if not mentions:
                logger.info("No new mentions found to process")
                return

            logger.info(f"Found {len(mentions)} mentions to process")
            for mention in mentions:
                try:
                    logger.debug(f"Processing mention {mention.id}")
                    await self._handle_mention(mention)
                except Exception as e:
                    logger.error(
                        f"Failed to process mention {mention.id}: {str(e)}",
                        exc_info=True,
                    )
                    continue

        except Exception as e:
            logger.error(f"Twitter mention processing failed: {str(e)}", exc_info=True)
            raise


def create_twitter_handler() -> TwitterMentionHandler:
    """Factory function to create TwitterMentionHandler with dependencies."""
    twitter_config = TwitterConfig(
        consumer_key=config.twitter.consumer_key,
        consumer_secret=config.twitter.consumer_secret,
        client_id=config.twitter.client_id,
        client_secret=config.twitter.client_secret,
        access_token=config.twitter.access_token,
        access_secret=config.twitter.access_secret,
        bearer_token=config.twitter.bearer_token,
        user_id=config.twitter.automated_user_id,
        whitelisted_authors=config.twitter.whitelisted_authors,
        whitelist_enabled=False,
    )

    tweet_repository = TweetRepository()
    tweet_analyzer = TweetAnalyzer(tweet_repository)

    return TwitterMentionHandler(twitter_config, tweet_repository, tweet_analyzer)


def create_twitter_service_from_config() -> TwitterService:
    """Factory function to create TwitterService using config credentials."""
    return TwitterService(
        consumer_key=config.twitter.consumer_key,
        consumer_secret=config.twitter.consumer_secret,
        client_id=config.twitter.client_id,
        client_secret=config.twitter.client_secret,
        access_token=config.twitter.access_token,
        access_secret=config.twitter.access_secret,
        bearer_token=config.twitter.bearer_token,
    )


# Global handler instance
handler = create_twitter_handler()


async def execute_twitter_job() -> None:
    """Execute the Twitter job to process mentions."""
    try:
        if not handler.config.user_id:
            logger.error(
                "Cannot execute Twitter job: AIBTC_TWITTER_AUTOMATED_USER_ID not set"
            )
            return

        logger.info("Starting Twitter mention check job")
        await handler.process_mentions()
        logger.info("Successfully completed Twitter mention check job")

    except Exception as e:
        logger.error(f"Twitter job execution failed: {str(e)}", exc_info=True)
        raise
