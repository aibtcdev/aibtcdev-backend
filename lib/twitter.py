from lib.logger import configure_logger
from pytwitter import Api
from pytwitter.models import Tweet, User
from typing import List, Optional
from datetime import datetime

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
            
            # Create tweet with error handling
            try:
                response = self.client.create_tweet(
                    text=text, reply_in_reply_to_tweet_id=reply_in_reply_to_tweet_id
                )
                logger.info(f"Successfully posted tweet: {text[:20]}...")
                
                # Ensure we have a valid response with an ID
                if response and hasattr(response, 'id'):
                    return response
                else:
                    logger.error(f"Invalid tweet response: {response}")
                    return None
                    
            except Exception as tweet_error:
                logger.error(f"Error creating tweet: {str(tweet_error)}")
                return None
                
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
        self, user_id: str, max_results: int = 100, since_id: Optional[str] = None
    ) -> List[Tweet]:
        """
        Get mentions for a specific user.

        Args:
            user_id: Twitter user ID to get mentions for
            max_results: Maximum number of mentions to return (default 100)
            since_id: Only return mentions newer than this tweet ID

        Returns:
            List of mention data
        """
        try:
            if self.client is None:
                raise Exception("Twitter client is not initialized")
            
            all_mentions = []
            pagination_token = None
            total_requests = 0
            max_requests = 5  # Limit the number of pagination requests to avoid rate limits
            
            # First request - get the most recent mentions
            try:
                response = self.client.get_mentions(
                    user_id=user_id,
                    max_results=max_results,
                    since_id=since_id,
                    tweet_fields=[
                        "id",
                        "text",
                        "created_at",
                        "author_id",
                        "conversation_id",
                        "in_reply_to_user_id",
                        "referenced_tweets",
                    ],
                    expansions=[
                        "author_id",
                        "referenced_tweets.id",
                        "in_reply_to_user_id",
                    ],
                    user_fields=[
                        "id",
                        "name",
                        "username",
                    ]
                )
                
                if response.data:
                    logger.info(f"Initial request retrieved {len(response.data)} mentions")
                    for mention in response.data:
                        logger.debug(f"Retrieved mention {mention.id} created at {mention.created_at}")
                    all_mentions.extend(response.data)
                    
                    # If we have a next token and want more mentions, continue paginating
                    if hasattr(response, 'meta') and hasattr(response.meta, 'next_token'):
                        pagination_token = response.meta.next_token
                        total_requests += 1
                        
                        # Get older mentions through pagination
                        while total_requests < max_requests and pagination_token:
                            try:
                                logger.info(f"Fetching page {total_requests + 1} with token: {pagination_token[:10]}...")
                                response = self.client.get_mentions(
                                    user_id=user_id,
                                    max_results=max_results,
                                    pagination_token=pagination_token,
                                    tweet_fields=[
                                        "id",
                                        "text",
                                        "created_at",
                                        "author_id",
                                        "conversation_id",
                                        "in_reply_to_user_id",
                                        "referenced_tweets",
                                    ],
                                    expansions=[
                                        "author_id",
                                        "referenced_tweets.id",
                                        "in_reply_to_user_id",
                                    ],
                                    user_fields=[
                                        "id",
                                        "name",
                                        "username",
                                    ]
                                )
                                
                                if not response.data:
                                    break
                                    
                                logger.info(f"Page {total_requests + 1} retrieved {len(response.data)} mentions")
                                for mention in response.data:
                                    logger.debug(f"Retrieved mention {mention.id} created at {mention.created_at}")
                                all_mentions.extend(response.data)
                                
                                if not hasattr(response, 'meta') or not hasattr(response.meta, 'next_token'):
                                    break
                                    
                                pagination_token = response.meta.next_token
                                total_requests += 1
                                
                            except Exception as e:
                                logger.error(f"Error in pagination request {total_requests + 1}: {str(e)}")
                                break
                else:
                    logger.info("No mentions found in initial request")
                    
            except Exception as e:
                logger.error(f"Error in initial request: {str(e)}")
                return []
            
            # Sort mentions by creation time to ensure newest first
            if all_mentions:
                all_mentions.sort(key=lambda x: x.created_at, reverse=True)
                logger.info(f"Newest mention from: {all_mentions[0].created_at}")
                logger.info(f"Oldest mention from: {all_mentions[-1].created_at}")
            
            logger.info(f"Successfully retrieved {len(all_mentions)} total mentions across {total_requests + 1} requests")
            return all_mentions

        except Exception as e:
            logger.error(f"Failed to get mentions: {str(e)}")
            return []

    async def get_user_tweets(self, user_id: str, max_results: int = 25) -> List[Tweet]:
        """
        Get recent tweets from a specific user, including replies and retweets.

        Args:
            user_id: Twitter user ID to get tweets for
            max_results: Maximum number of tweets to return (default 25)

        Returns:
            List of tweet data
        """
        try:
            if self.client is None:
                raise Exception("Twitter client is not initialized")
            response = self.client.get_timelines(
                user_id=user_id,
                max_results=max_results,
                tweet_fields=[
                    "id", "text", "created_at", "author_id", "conversation_id",
                    "in_reply_to_user_id", "referenced_tweets", "public_metrics",
                    "entities", "context_annotations"
                ],
                expansions=[
                    "referenced_tweets.id", "referenced_tweets.id.author_id",
                    "entities.mentions.username"
                ]
            )
            logger.info(f"Successfully retrieved {len(response.data)} tweets for user {user_id}")
            return response.data
        except Exception as e:
            logger.error(f"Failed to get user tweets: {str(e)}")
            return []

    async def get_user_profile(self, user_id: str) -> Optional[User]:
        """
        Get detailed profile information for a user.

        Args:
            user_id: Twitter user ID

        Returns:
            User profile data if found, None if not found or error
        """
        try:
            if self.client is None:
                raise Exception("Twitter client is not initialized")
                
            response = self.client.get_user(
                user_id=user_id,
                user_fields=[
                    "id", "username"  # Minimal fields to reduce rate limit impact
                ]
            )
            if type(response) == User:
                return response
                
        except Exception as e:
            if "Too Many Requests" in str(e):
                logger.warning(f"Rate limit hit while fetching user profile for {user_id} - continuing without profile")
            else:
                logger.error(f"Failed to get user profile for {user_id}: {str(e)}")
            return None

    async def get_pinned_tweet(self, user_id: str) -> Optional[Tweet]:
        """
        Get the pinned tweet of a user if it exists.

        Args:
            user_id: Twitter user ID

        Returns:
            Pinned tweet data if found, None if not found or error
        """
        try:
            if self.client is None:
                raise Exception("Twitter client is not initialized")
            
            # First get user profile to get pinned tweet ID
            user_profile = await self.get_user_profile(user_id)
            if not user_profile or not hasattr(user_profile, "pinned_tweet_id"):
                return None

            # Get the pinned tweet
            response = self.client.get_tweet(
                tweet_id=user_profile.pinned_tweet_id,
                tweet_fields=[
                    "id", "text", "created_at", "author_id", "entities",
                    "context_annotations"
                ]
            )
            return response
        except Exception as e:
            logger.error(f"Failed to get pinned tweet for {user_id}: {str(e)}")
            return None
