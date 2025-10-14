import re
import requests
import base64
import io
from typing import Any, Dict, List, Optional
from uuid import UUID
from PIL import Image
from dotenv import load_dotenv

from app.backend.factory import backend
from app.backend.models import (
    TweetType,
    XTweetCreate,
    XTweetFilter,
    XUserCreate,
    XUserFilter,
)
from app.lib.logger import configure_logger
from app.services.communication.twitter_service import (
    create_twitter_service_from_config,
)
from app.config import config

# Load environment variables
load_dotenv()

logger = configure_logger(__name__)


def analyze_bitcoin_face(image_url):
    """
    Analyze an image URL to detect if it's a Bitcoin face using HuggingFace API

    Args:
        image_url (str): URL of the image to analyze

    Returns:
        dict: Bitcoin face analysis results with probabilities
    """
    if not image_url:
        logger.warning("analyze_bitcoin_face: No image URL provided")
        return {"error": "No image URL provided"}

    try:
        # HuggingFace API endpoint from config
        api_url = config.huggingface.api_url
        token = config.huggingface.token

        logger.debug(f"analyze_bitcoin_face: API URL: {api_url}")
        logger.debug(f"analyze_bitcoin_face: Token present: {bool(token)}")

        if not token:
            logger.error(
                "analyze_bitcoin_face: HUGGING_FACE token not found in environment"
            )
            return {"error": "HUGGING_FACE token not found in environment"}

        if not api_url:
            logger.error("analyze_bitcoin_face: HuggingFace API URL not configured")
            return {"error": "HuggingFace API URL not configured"}

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # Fetch and encode image
        logger.debug(f"analyze_bitcoin_face: Fetching image from: {image_url}")
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()

        logger.debug(
            f"analyze_bitcoin_face: Image fetched successfully, size: {len(response.content)} bytes"
        )

        image = Image.open(io.BytesIO(response.content)).convert("RGB")
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        img_str = base64.b64encode(buffered.getvalue()).decode()

        logger.debug(
            f"analyze_bitcoin_face: Image encoded to base64, length: {len(img_str)}"
        )

        # Call HuggingFace API
        payload = {
            "inputs": f"data:image/jpeg;base64,{img_str}",
            "confidence_threshold": 0.7,
        }

        logger.debug(f"analyze_bitcoin_face: Calling HuggingFace API at {api_url}")
        response = requests.post(api_url, headers=headers, json=payload, timeout=60)

        logger.debug(
            f"analyze_bitcoin_face: API response status: {response.status_code}"
        )
        logger.debug(
            f"analyze_bitcoin_face: API response headers: {dict(response.headers)}"
        )

        if response.status_code != 200:
            logger.error(
                f"analyze_bitcoin_face: API returned status {response.status_code}: {response.text}"
            )
            return {
                "error": f"API returned status {response.status_code}: {response.text}"
            }

        response.raise_for_status()

        result = response.json()
        logger.debug(f"analyze_bitcoin_face: API response: {result}")

        # Extract probabilities from result
        if isinstance(result, list) and len(result) > 0:
            probabilities = result[0].get("probabilities", {})
            logger.info(
                f"analyze_bitcoin_face: Analysis successful, probabilities: {probabilities}"
            )
            return probabilities

        logger.warning(f"analyze_bitcoin_face: Unexpected result format: {result}")
        return {"error": "No analysis results returned", "raw_response": result}

    except requests.exceptions.ConnectionError as e:
        logger.error(f"analyze_bitcoin_face: Connection error: {str(e)}")
        return {"error": "HuggingFace API not available"}
    except requests.exceptions.Timeout as e:
        logger.error(f"analyze_bitcoin_face: Timeout error: {str(e)}")
        return {"error": "HuggingFace API timeout"}
    except requests.exceptions.HTTPError as e:
        logger.error(f"analyze_bitcoin_face: HTTP error: {str(e)}")
        return {"error": f"HTTP error: {str(e)}"}
    except Exception as e:
        logger.error(f"analyze_bitcoin_face: Unexpected error: {str(e)}", exc_info=True)
        return {"error": f"Analysis failed: {str(e)}"}


def fetch_user_profile(username):
    """
    Fetch user profile data by username

    Args:
        username (str): Twitter/X username (without @)

    Returns:
        dict: User profile data
    """
    token = config.twitter.bearer_token
    if not token:
        return {
            "error": "Missing API token",
            "details": "DAOROUNDUP_BEARER_TOKEN not found in environment",
        }

    url = f"https://api.twitter.com/2/users/by/username/{username}"
    headers = {"Authorization": f"Bearer {token}"}

    params = {
        "user.fields": "name,username,verified,verified_type,public_metrics,description,profile_image_url,url,location,created_at,pinned_tweet_id"
    }

    try:
        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            data = response.json()
            user_data = data.get("data", {})

            # Get full-size profile image
            profile_image_url = user_data.get("profile_image_url")
            if profile_image_url and "_normal.jpg" in profile_image_url:
                profile_image_url = profile_image_url.replace("_normal.jpg", ".jpg")
            elif profile_image_url and "_normal.png" in profile_image_url:
                profile_image_url = profile_image_url.replace("_normal.png", ".png")

            return {
                "profile_image_url": profile_image_url,
                "description": user_data.get("description"),
                "location": user_data.get("location"),
                "url": user_data.get("url"),
                "verified": user_data.get("verified", False),
                "verified_type": user_data.get("verified_type"),
                "created_at": user_data.get("created_at"),
                "pinned_tweet_id": user_data.get("pinned_tweet_id"),
            }
        else:
            return {
                "error": f"API error: {response.status_code}",
                "details": response.text,
            }

    except Exception as e:
        return {"error": f"Request failed: {str(e)}"}


class TwitterDataService:
    """Service to handle Twitter data fetching and persistence."""

    def __init__(self):
        """Initialize the Twitter data service."""
        self.twitter_service = None

    async def _initialize_twitter_service(self):
        """Initialize Twitter service if not already initialized."""
        if self.twitter_service is None:
            try:
                self.twitter_service = create_twitter_service_from_config()
                await self.twitter_service._ainitialize()
                logger.info("Twitter service initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Twitter service: {str(e)}")
                self.twitter_service = None

    def extract_twitter_urls(self, text: str) -> List[str]:
        """Extract X/Twitter URLs from text.

        Args:
            text: Text to search for Twitter URLs

        Returns:
            List of Twitter URLs found
        """
        # Pattern to match X.com and twitter.com URLs with status IDs
        twitter_url_pattern = r"https?://(?:x\.com|twitter\.com)/[^/]+/status/(\d+)"

        # Return full URLs, not just IDs
        urls = []
        for match in re.finditer(twitter_url_pattern, text, re.IGNORECASE):
            urls.append(match.group(0))

        return urls

    def extract_tweet_id_from_url(self, url: str) -> Optional[str]:
        """Extract tweet ID from X/Twitter URL.

        Args:
            url: Twitter/X URL

        Returns:
            Tweet ID if found, None otherwise
        """
        pattern = r"https?://(?:x\.com|twitter\.com)/[^/]+/status/(\d+)"
        match = re.search(pattern, url, re.IGNORECASE)
        return match.group(1) if match else None

    async def _fetch_tweet_from_api(self, tweet_id: str) -> Optional[Dict[str, Any]]:
        """Fetch tweet content from Twitter API.

        Args:
            tweet_id: Twitter status ID

        Returns:
            Dictionary containing tweet data or None if failed
        """
        try:
            if not self.twitter_service:
                await self._initialize_twitter_service()
                if not self.twitter_service:
                    return None

            # Try API v2 first
            tweet_response = await self.twitter_service.get_tweet_by_id(tweet_id)
            if tweet_response and tweet_response.data:
                tweet = tweet_response.data
                tweet_data = {
                    "id": tweet.id,
                    "text": tweet.text,
                    "author_id": tweet.author_id,
                    "created_at": getattr(tweet, "created_at", None),
                    "public_metrics": getattr(tweet, "public_metrics", {}),
                    "entities": getattr(tweet, "entities", {}),
                    "attachments": getattr(tweet, "attachments", {}),
                    "referenced_tweets": getattr(tweet, "referenced_tweets", []),
                }

                # Handle quoted posts from referenced_tweets
                quoted_posts = []
                referenced_tweets = getattr(tweet, "referenced_tweets", []) or []

                for ref_tweet in referenced_tweets:
                    if ref_tweet.type == "quoted":
                        quoted_posts.append(
                            {"type": ref_tweet.type, "id": ref_tweet.id}
                        )

                # Extract quoted post data from includes if available
                if hasattr(tweet_response, "includes") and tweet_response.includes:
                    if (
                        "tweets" in tweet_response.includes
                        and tweet_response.includes["tweets"]
                    ):
                        for quoted_tweet in tweet_response.includes["tweets"]:
                            # Find matching quoted posts
                            for quoted_ref in quoted_posts:
                                if str(quoted_tweet.id) == str(quoted_ref["id"]):
                                    quoted_ref["data"] = {
                                        "id": quoted_tweet.id,
                                        "text": quoted_tweet.text,
                                        "author_id": quoted_tweet.author_id,
                                        "created_at": getattr(
                                            quoted_tweet, "created_at", None
                                        ),
                                        "public_metrics": getattr(
                                            quoted_tweet, "public_metrics", {}
                                        ),
                                        "entities": getattr(
                                            quoted_tweet, "entities", {}
                                        ),
                                        "attachments": getattr(
                                            quoted_tweet, "attachments", {}
                                        ),
                                    }
                                    break

                    if (
                        "users" in tweet_response.includes
                        and tweet_response.includes["users"]
                    ):
                        # Find the author user in the includes
                        for user in tweet_response.includes["users"]:
                            user_id = None
                            if hasattr(user, "id"):
                                user_id = str(user.id)
                            elif isinstance(user, dict):
                                user_id = str(user.get("id", ""))

                            if user_id == str(tweet.author_id):
                                # Extract user information
                                if hasattr(user, "name"):
                                    tweet_data["author_name"] = user.name
                                elif isinstance(user, dict):
                                    tweet_data["author_name"] = user.get("name", "")

                                if hasattr(user, "username"):
                                    tweet_data["author_username"] = user.username
                                elif isinstance(user, dict):
                                    tweet_data["author_username"] = user.get(
                                        "username", ""
                                    )
                                break

                            # Add author info to quoted posts
                            for quoted_ref in quoted_posts:
                                if "data" in quoted_ref and user_id == str(
                                    quoted_ref["data"]["author_id"]
                                ):
                                    if hasattr(user, "name"):
                                        quoted_ref["data"]["author_name"] = user.name
                                    elif isinstance(user, dict):
                                        quoted_ref["data"]["author_name"] = user.get(
                                            "name", ""
                                        )

                                    if hasattr(user, "username"):
                                        quoted_ref["data"]["author_username"] = (
                                            user.username
                                        )
                                    elif isinstance(user, dict):
                                        quoted_ref["data"]["author_username"] = (
                                            user.get("username", "")
                                        )

                    if (
                        "media" in tweet_response.includes
                        and tweet_response.includes["media"]
                    ):
                        tweet_data["media_objects"] = tweet_response.includes["media"]
                        logger.debug(
                            f"Found {len(tweet_response.includes['media'])} media objects in API v2 response"
                        )

                # Add quoted posts to tweet data
                tweet_data["quoted_posts"] = quoted_posts

                logger.info(f"Successfully fetched tweet {tweet_id} using API v2")
                return tweet_data

            # Fallback to API v1.1
            status = await self.twitter_service.get_status_by_id(tweet_id)
            if status:
                tweet_data = {
                    "id": status.id_str,
                    "text": getattr(status, "full_text", status.text),
                    "author_id": status.user.id_str,
                    "author_username": status.user.screen_name,
                    "author_name": status.user.name,
                    "created_at": status.created_at,
                    "retweet_count": status.retweet_count,
                    "favorite_count": status.favorite_count,
                    "entities": getattr(status, "entities", None),
                    "extended_entities": getattr(status, "extended_entities", None),
                }
                logger.info(f"Successfully fetched tweet {tweet_id} using API v1.1")
                return tweet_data

            logger.warning(f"Tweet {tweet_id} not found")
            return None

        except Exception as e:
            logger.error(f"Error fetching tweet {tweet_id}: {str(e)}")
            return None

    def _extract_images_from_tweet_data(self, tweet_data: Dict[str, Any]) -> List[str]:
        """Extract image URLs from tweet data.

        Args:
            tweet_data: Tweet data dictionary

        Returns:
            List of image URLs
        """
        image_urls = []

        try:
            # Check extended_entities for media (API v1.1)
            extended_entities = tweet_data.get("extended_entities")
            if (
                extended_entities
                and isinstance(extended_entities, dict)
                and "media" in extended_entities
                and extended_entities["media"]
            ):
                for media in extended_entities["media"]:
                    if media.get("type") == "photo":
                        media_url = media.get("media_url_https") or media.get(
                            "media_url"
                        )
                        if media_url:
                            image_urls.append(media_url)

            # Check entities for media (fallback)
            entities = tweet_data.get("entities")
            if (
                entities
                and isinstance(entities, dict)
                and "media" in entities
                and entities["media"]
            ):
                for media in entities["media"]:
                    if media.get("type") == "photo":
                        media_url = media.get("media_url_https") or media.get(
                            "media_url"
                        )
                        if media_url:
                            image_urls.append(media_url)

            # Check attachments for media keys (API v2)
            attachments = tweet_data.get("attachments")
            if (
                attachments
                and isinstance(attachments, dict)
                and "media_keys" in attachments
            ):
                # For API v2, we need to check if media objects are in the tweet_data
                # This happens when the API response includes expanded media
                media_objects = tweet_data.get("media_objects", []) or []
                for media in media_objects:
                    media_url = None
                    media_type = None

                    # Handle media objects that might be Python objects or dictionaries
                    if hasattr(media, "type"):
                        media_type = media.type
                    elif isinstance(media, dict):
                        media_type = media.get("type")

                    # Extract image URL based on media type
                    if media_type == "photo":
                        # For photos, get the direct URL
                        if hasattr(media, "url"):
                            media_url = media.url
                        elif isinstance(media, dict):
                            media_url = media.get("url")

                    elif media_type in ["animated_gif", "video"]:
                        # For animated GIFs and videos, use the preview image URL
                        if hasattr(media, "preview_image_url"):
                            media_url = media.preview_image_url
                        elif isinstance(media, dict):
                            media_url = media.get("preview_image_url")

                    # If we still don't have a URL, check nested data object
                    if not media_url:
                        data_obj = None
                        if hasattr(media, "data"):
                            data_obj = media.data
                        elif isinstance(media, dict) and "data" in media:
                            data_obj = media["data"]

                        if data_obj:
                            if media_type == "photo":
                                if isinstance(data_obj, dict):
                                    media_url = data_obj.get("url")
                                elif hasattr(data_obj, "url"):
                                    media_url = data_obj.url
                            elif media_type in ["animated_gif", "video"]:
                                if isinstance(data_obj, dict):
                                    media_url = data_obj.get("preview_image_url")
                                elif hasattr(data_obj, "preview_image_url"):
                                    media_url = data_obj.preview_image_url

                    if media_url:
                        image_urls.append(media_url)
                        logger.debug(f"Extracted {media_type} image URL: {media_url}")

                # If no media objects in tweet_data, log that media expansion is needed
                if not media_objects:
                    logger.debug(
                        f"Found media keys in tweet, but no expanded media objects: {attachments['media_keys']}"
                    )

            # Remove duplicates
            image_urls = list(set(image_urls))

            logger.debug(f"Extracted {len(image_urls)} images from tweet: {image_urls}")

        except Exception as e:
            logger.error(f"Error extracting images from tweet: {str(e)}")

        return image_urls

    async def _store_user_if_needed(
        self, tweet_data: Dict[str, Any], profile_data: Optional[Dict[str, Any]] = None
    ) -> Optional[UUID]:
        """Store user data if not already exists.

        Args:
            tweet_data: Tweet data containing user information
            profile_data: Optional profile data from fetch_user_profile

        Returns:
            User ID if stored/found, None otherwise
        """
        try:
            author_username = tweet_data.get("author_username")
            if not author_username:
                logger.warning("No author username found in tweet data")
                return None

            # Check if user already exists
            existing_users = backend.list_x_users(XUserFilter(username=author_username))
            if existing_users:
                existing_user = existing_users[0]

                # Update existing user with profile data if provided and missing
                if profile_data and not profile_data.get("error"):
                    needs_update = False
                    update_data = {}

                    # Check if profile_image_url needs updating
                    if (
                        profile_data.get("profile_image_url")
                        and not existing_user.profile_image_url
                    ):
                        update_data["profile_image_url"] = profile_data[
                            "profile_image_url"
                        ]
                        needs_update = True

                    # Check if bitcoin_face_score needs analyzing
                    if existing_user.bitcoin_face_score is None and profile_data.get(
                        "profile_image_url"
                    ):
                        try:
                            pfp_analysis = analyze_bitcoin_face(
                                profile_data["profile_image_url"]
                            )
                            if not pfp_analysis.get("error"):
                                bitcoin_face_score = pfp_analysis.get("bitcoin_face")
                                if bitcoin_face_score is not None:
                                    update_data["bitcoin_face_score"] = (
                                        bitcoin_face_score
                                    )
                                    needs_update = True
                        except Exception as e:
                            logger.warning(
                                f"Error analyzing profile image for existing user {author_username}: {str(e)}"
                            )

                    # Check other fields that might need updating
                    for field in [
                        "description",
                        "location",
                        "url",
                        "verified",
                        "verified_type",
                    ]:
                        if (
                            profile_data.get(field) is not None
                            and getattr(existing_user, field, None) is None
                        ):
                            update_data[field] = profile_data[field]
                            needs_update = True

                    if needs_update:
                        # Note: This would require an update method in the backend
                        # For now, just log that an update would be beneficial
                        logger.info(
                            f"User {author_username} exists but could be updated with profile data: {list(update_data.keys())}"
                        )

                logger.debug(f"User {author_username} already exists in database")
                return existing_user.id

            # Create new user record with profile data if available
            user_create_data = {
                "name": tweet_data.get("author_name"),
                "username": author_username,
                "user_id": str(tweet_data.get("author_id"))
                if tweet_data.get("author_id")
                else None,
            }

            # Add profile data fields if available
            if profile_data and not profile_data.get("error"):
                if profile_data.get("profile_image_url"):
                    user_create_data["profile_image_url"] = profile_data[
                        "profile_image_url"
                    ]

                    # Analyze profile image for bitcoin face
                    try:
                        pfp_analysis = analyze_bitcoin_face(
                            profile_data["profile_image_url"]
                        )
                        if not pfp_analysis.get("error"):
                            bitcoin_face_score = pfp_analysis.get("bitcoin_face")
                            if bitcoin_face_score is not None:
                                user_create_data["bitcoin_face_score"] = (
                                    bitcoin_face_score
                                )
                                logger.info(
                                    f"Analyzed profile image for {author_username}, bitcoin_face_score: {bitcoin_face_score}"
                                )
                    except Exception as e:
                        logger.warning(
                            f"Error analyzing profile image for new user {author_username}: {str(e)}"
                        )

                if profile_data.get("description"):
                    user_create_data["description"] = profile_data["description"]
                if profile_data.get("location"):
                    user_create_data["location"] = profile_data["location"]
                if profile_data.get("url"):
                    user_create_data["url"] = profile_data["url"]
                if profile_data.get("verified") is not None:
                    user_create_data["verified"] = profile_data["verified"]
                if profile_data.get("verified_type"):
                    user_create_data["verified_type"] = profile_data["verified_type"]

            user_data = XUserCreate(**user_create_data)
            user = backend.create_x_user(user_data)
            logger.info(
                f"Created new user record for {author_username} with profile data"
            )
            return user.id

        except Exception as e:
            logger.error(f"Error storing user data: {str(e)}")
            return None

    async def store_tweet_data(self, tweet_url: str) -> Optional[UUID]:
        """Store tweet data in the database.

        Args:
            tweet_url: Twitter/X URL to process

        Returns:
            Tweet record ID if successful, None otherwise
        """
        try:
            # Extract tweet ID from URL
            tweet_id = self.extract_tweet_id_from_url(tweet_url)
            if not tweet_id:
                logger.warning(f"Could not extract tweet ID from URL: {tweet_url}")
                return None

            # Check if tweet already exists in database
            existing_tweets = backend.list_x_tweets(XTweetFilter(tweet_id=tweet_id))
            if existing_tweets:
                logger.debug(f"Tweet {tweet_id} already exists in database")
                return existing_tweets[0].id

            # Fetch tweet data from API
            tweet_data = await self._fetch_tweet_from_api(tweet_id)
            if not tweet_data:
                logger.warning(f"Could not fetch tweet data for ID: {tweet_id}")
                return None

            # Extract images from tweet
            image_urls = self._extract_images_from_tweet_data(tweet_data)

            # Fetch author profile data first (used for user creation)
            author_username = tweet_data.get("author_username")
            profile_data = {}
            if author_username:
                try:
                    profile_data = fetch_user_profile(author_username)
                except Exception as e:
                    logger.warning(
                        f"Error fetching author profile for {author_username}: {str(e)}"
                    )
                    profile_data = {"error": str(e)}

            # Store user data if needed (now with profile data and bitcoin face analysis)
            author_id = await self._store_user_if_needed(tweet_data, profile_data)

            # Prepare created_at_twitter field
            created_at_twitter = None
            if tweet_data.get("created_at"):
                try:
                    if hasattr(tweet_data["created_at"], "strftime"):
                        created_at_twitter = tweet_data["created_at"].strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                    else:
                        created_at_twitter = str(tweet_data["created_at"])
                except (AttributeError, ValueError, TypeError):
                    created_at_twitter = str(tweet_data["created_at"])

            # Handle quoted posts first (store them before the main tweet)
            quoted_tweet_db_id = None
            quoted_posts = tweet_data.get("quoted_posts", []) or []

            for quoted_post in quoted_posts:
                if "data" in quoted_post:
                    quoted_data = quoted_post["data"]
                    quoted_tweet_id = str(quoted_data["id"])

                    # Check if quoted tweet already exists
                    existing_quoted = backend.list_x_tweets(
                        XTweetFilter(tweet_id=quoted_tweet_id)
                    )
                    if existing_quoted:
                        quoted_tweet_db_id = existing_quoted[0].id
                        logger.debug(f"Quoted tweet {quoted_tweet_id} already exists")
                    else:
                        # Store the quoted tweet first
                        quoted_author_id = await self._store_user_if_needed(quoted_data)

                        # Extract images from quoted tweet
                        quoted_images = self._extract_images_from_tweet_data(
                            quoted_data
                        )

                        # Prepare quoted tweet creation data
                        quoted_created_at = None
                        if quoted_data.get("created_at"):
                            try:
                                if hasattr(quoted_data["created_at"], "strftime"):
                                    quoted_created_at = quoted_data[
                                        "created_at"
                                    ].strftime("%Y-%m-%d %H:%M:%S")
                                else:
                                    quoted_created_at = str(quoted_data["created_at"])
                            except (AttributeError, ValueError, TypeError):
                                quoted_created_at = str(quoted_data["created_at"])

                        quoted_tweet_create = XTweetCreate(
                            message=quoted_data.get("text"),
                            author_id=quoted_author_id,
                            tweet_id=quoted_tweet_id,
                            conversation_id=quoted_data.get("conversation_id"),
                            is_worthy=False,
                            tweet_type=TweetType.INVALID,
                            confidence_score=None,
                            reason=None,
                            images=quoted_images,
                            author_name=quoted_data.get("author_name"),
                            author_username=quoted_data.get("author_username"),
                            created_at_twitter=quoted_created_at,
                            public_metrics=quoted_data.get("public_metrics"),
                            entities=quoted_data.get("entities"),
                            attachments=quoted_data.get("attachments"),
                            tweet_images_analysis=[],
                            # No quoted_tweet_id for the quoted post itself
                        )

                        quoted_record = backend.create_x_tweet(quoted_tweet_create)
                        quoted_tweet_db_id = quoted_record.id
                        logger.info(f"Stored quoted tweet {quoted_tweet_id}")

            # Analyze tweet images for Bitcoin faces
            tweet_images_analysis = []
            # TODO: Uncomment this when we have a way to analyze images thats faster than the current implementation
            # for image_url in image_urls:
            #     try:
            #         image_analysis = analyze_bitcoin_face(image_url)
            #         if not image_analysis.get("error"):
            #             tweet_images_analysis.append(
            #                 {"image_url": image_url, "analysis": image_analysis}
            #             )
            #     except Exception as e:
            #         logger.warning(f"Error analyzing tweet image {image_url}: {str(e)}")

            # Create tweet record with quoted tweet reference
            tweet_create_data = XTweetCreate(
                message=tweet_data.get("text"),
                author_id=author_id,
                tweet_id=tweet_id,
                conversation_id=tweet_data.get("conversation_id"),
                is_worthy=False,  # Default value, can be updated later
                tweet_type=TweetType.INVALID,  # Default type - was previously CONVERSATION
                confidence_score=None,
                reason=None,
                images=image_urls,
                author_name=tweet_data.get("author_name"),
                author_username=tweet_data.get("author_username"),
                created_at_twitter=created_at_twitter,
                public_metrics=tweet_data.get("public_metrics"),
                entities=tweet_data.get("entities"),
                attachments=tweet_data.get("attachments"),
                tweet_images_analysis=tweet_images_analysis,
                # Link to quoted tweet
                quoted_tweet_id=str(quoted_posts[0]["id"]) if quoted_posts else None,
                quoted_tweet_db_id=quoted_tweet_db_id,
            )

            tweet_record = backend.create_x_tweet(tweet_create_data)
            quoted_info = (
                f" and quoted tweet {quoted_tweet_db_id}" if quoted_tweet_db_id else ""
            )
            logger.info(
                f"Successfully stored tweet {tweet_id} with {len(image_urls)} images{quoted_info}"
            )

            # Fetch and store the author's last 5 tweets
            if tweet_data.get("author_id") and tweet_data.get("author_username"):
                try:
                    author_tweet_ids = await self.fetch_and_store_author_tweets(
                        author_id=str(tweet_data["author_id"]),
                        author_username=tweet_data["author_username"],
                    )
                    if author_tweet_ids:
                        logger.info(
                            f"Stored {len(author_tweet_ids)} additional tweets from author {tweet_data['author_username']}"
                        )
                except Exception as e:
                    logger.warning(
                        f"Failed to fetch author tweets for {tweet_data.get('author_username')}: {str(e)}"
                    )

            return tweet_record.id

        except Exception as e:
            logger.error(f"Error storing tweet data for URL {tweet_url}: {str(e)}")
            return None

    async def process_twitter_urls_from_text(self, text: str) -> List[UUID]:
        """Process all Twitter URLs found in text and store them.

        Args:
            text: Text to search for Twitter URLs

        Returns:
            List of tweet database IDs that were processed/stored
        """
        try:
            twitter_urls = self.extract_twitter_urls(text)
            if not twitter_urls:
                logger.debug("No Twitter URLs found in text")
                return []

            tweet_ids = []
            for url in twitter_urls:
                tweet_id = await self.store_tweet_data(url)
                if tweet_id:
                    tweet_ids.append(tweet_id)

            logger.info(
                f"Processed {len(tweet_ids)} tweets from {len(twitter_urls)} URLs"
            )
            return tweet_ids

        except Exception as e:
            logger.error(f"Error processing Twitter URLs from text: {str(e)}")
            return []

    async def fetch_and_store_author_tweets(
        self, author_id: str, author_username: str = None
    ) -> List[UUID]:
        """Fetch and store the last 5 tweets from the specified author.

        Args:
            author_id: Twitter user ID of the author
            author_username: Optional username for logging purposes

        Returns:
            List of tweet database IDs that were stored
        """
        try:
            if not self.twitter_service:
                await self._initialize_twitter_service()
                if not self.twitter_service:
                    logger.error(
                        "Twitter service not available for fetching author tweets"
                    )
                    return []

            # Fetch the author's timeline (last 5 tweets)
            logger.info(
                f"Fetching last 5 tweets for author {author_username or author_id}"
            )
            timeline_response = await self.twitter_service.get_user_timeline(
                user_id=author_id, count=5, exclude_replies=True, include_rts=False
            )

            if not timeline_response:
                logger.warning(f"No timeline data returned for author {author_id}")
                return []

            stored_tweet_ids = []

            # Process each tweet in the timeline
            for tweet in timeline_response:
                try:
                    # Extract tweet data similar to _fetch_tweet_from_api
                    tweet_data = None

                    # Handle different response formats (API v1.1 vs v2)
                    if hasattr(tweet, "id_str"):
                        # API v1.1 format
                        tweet_data = {
                            "id": tweet.id_str,
                            "text": getattr(tweet, "full_text", tweet.text),
                            "author_id": tweet.user.id_str,
                            "author_username": tweet.user.screen_name,
                            "author_name": tweet.user.name,
                            "created_at": tweet.created_at,
                            "retweet_count": tweet.retweet_count,
                            "favorite_count": tweet.favorite_count,
                            "entities": getattr(tweet, "entities", None),
                            "extended_entities": getattr(
                                tweet, "extended_entities", None
                            ),
                        }
                    elif hasattr(tweet, "id"):
                        # API v2 format
                        tweet_data = {
                            "id": str(tweet.id),
                            "text": tweet.text,
                            "author_id": str(tweet.author_id),
                            "created_at": getattr(tweet, "created_at", None),
                            "public_metrics": getattr(tweet, "public_metrics", {}),
                            "entities": getattr(tweet, "entities", {}),
                            "attachments": getattr(tweet, "attachments", {}),
                        }

                        # Add author info if available
                        if author_username:
                            tweet_data["author_username"] = author_username

                    if not tweet_data:
                        logger.warning(
                            "Could not extract tweet data from timeline response"
                        )
                        continue

                    # Check if tweet already exists
                    existing_tweets = backend.list_x_tweets(
                        XTweetFilter(tweet_id=tweet_data["id"])
                    )
                    if existing_tweets:
                        logger.debug(
                            f"Timeline tweet {tweet_data['id']} already exists in database"
                        )
                        stored_tweet_ids.append(existing_tweets[0].id)
                        continue

                    # Extract images from tweet
                    image_urls = self._extract_images_from_tweet_data(tweet_data)

                    # Store user data if needed (reuse existing logic)
                    author_db_id = await self._store_user_if_needed(tweet_data)

                    # Prepare created_at_twitter field
                    created_at_twitter = None
                    if tweet_data.get("created_at"):
                        try:
                            if hasattr(tweet_data["created_at"], "strftime"):
                                created_at_twitter = tweet_data["created_at"].strftime(
                                    "%Y-%m-%d %H:%M:%S"
                                )
                            else:
                                created_at_twitter = str(tweet_data["created_at"])
                        except (AttributeError, ValueError, TypeError):
                            created_at_twitter = str(tweet_data["created_at"])

                    # Create tweet record with consistent structure
                    tweet_create_data = XTweetCreate(
                        message=tweet_data.get("text"),
                        author_id=author_db_id,
                        tweet_id=tweet_data["id"],
                        conversation_id=tweet_data.get("conversation_id"),
                        is_worthy=False,
                        tweet_type=TweetType.INVALID,
                        confidence_score=None,
                        reason=None,
                        images=image_urls,
                        author_name=tweet_data.get("author_name"),
                        author_username=tweet_data.get("author_username"),
                        created_at_twitter=created_at_twitter,
                        public_metrics=tweet_data.get("public_metrics"),
                        entities=tweet_data.get("entities"),
                        attachments=tweet_data.get("attachments"),
                        tweet_images_analysis=[],  # Skip image analysis for author tweets for performance
                    )

                    tweet_record = backend.create_x_tweet(tweet_create_data)
                    stored_tweet_ids.append(tweet_record.id)
                    logger.debug(
                        f"Stored author tweet {tweet_data['id']} with {len(image_urls)} images"
                    )

                except Exception as e:
                    logger.error(f"Error processing author timeline tweet: {str(e)}")
                    continue

            logger.info(
                f"Successfully stored {len(stored_tweet_ids)} tweets from author {author_username or author_id}"
            )
            return stored_tweet_ids

        except Exception as e:
            logger.error(
                f"Error fetching and storing author tweets for {author_id}: {str(e)}"
            )
            return []

    async def fetch_tweet_with_quoted(
        self, tweet_db_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Fetch tweet with quoted post if available.

        Args:
            tweet_db_id: Database ID of the tweet to fetch

        Returns:
            Dictionary containing tweet data with quoted post if available, None if not found
        """
        try:
            # Get main tweet
            tweet = backend.get_x_tweet(tweet_db_id)
            if not tweet:
                logger.warning(f"Tweet not found for ID: {tweet_db_id}")
                return None

            tweet_data = {
                "id": tweet.tweet_id,
                "text": tweet.message,
                "author_id": tweet.author_id,
                "author_name": tweet.author_name,
                "author_username": tweet.author_username,
                "created_at": tweet.created_at_twitter,
                "public_metrics": tweet.public_metrics or {},
                "entities": tweet.entities or {},
                "attachments": tweet.attachments or {},
                "images": tweet.images or [],
                "tweet_images_analysis": tweet.tweet_images_analysis or [],
            }

            # Get quoted tweet if it exists
            if tweet.quoted_tweet_db_id:
                quoted_tweet = backend.get_x_tweet(tweet.quoted_tweet_db_id)
                if quoted_tweet:
                    tweet_data["quoted_post"] = {
                        "id": quoted_tweet.tweet_id,
                        "text": quoted_tweet.message,
                        "author_id": quoted_tweet.author_id,
                        "author_name": quoted_tweet.author_name,
                        "author_username": quoted_tweet.author_username,
                        "created_at": quoted_tweet.created_at_twitter,
                        "public_metrics": quoted_tweet.public_metrics or {},
                        "entities": quoted_tweet.entities or {},
                        "attachments": quoted_tweet.attachments or {},
                        "images": quoted_tweet.images or [],
                        "tweet_images_analysis": quoted_tweet.tweet_images_analysis
                        or [],
                    }
                    logger.debug(f"Retrieved quoted post for tweet {tweet_db_id}")
                else:
                    logger.warning(
                        f"Quoted tweet {tweet.quoted_tweet_db_id} not found for tweet {tweet_db_id}"
                    )

            logger.debug(f"Retrieved tweet data with quoted post for ID {tweet_db_id}")
            return tweet_data

        except Exception as e:
            logger.error(f"Error retrieving tweet with quoted post: {str(e)}")
            return None


# Global instance for reuse across the application
twitter_data_service = TwitterDataService()
