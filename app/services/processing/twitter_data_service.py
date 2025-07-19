import re
import os
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
        return {"error": "No image URL provided"}

    try:
        # HuggingFace API endpoint from config
        api_url = config.huggingface.api_url
        token = config.huggingface.token

        if not token:
            return {"error": "HUGGING_FACE token not found in environment"}

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # Fetch and encode image
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()

        image = Image.open(io.BytesIO(response.content)).convert("RGB")
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        img_str = base64.b64encode(buffered.getvalue()).decode()

        # Call HuggingFace API
        payload = {
            "inputs": f"data:image/jpeg;base64,{img_str}",
            "confidence_threshold": 0.7,
        }

        response = requests.post(api_url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()

        result = response.json()

        # Extract probabilities from result
        if isinstance(result, list) and len(result) > 0:
            return result[0].get("probabilities", {})

        return {"error": "No analysis results returned"}

    except requests.exceptions.ConnectionError:
        return {"error": "HuggingFace API not available"}
    except Exception as e:
        return {"error": f"Analysis failed: {str(e)}"}


def fetch_user_profile(username):
    """
    Fetch user profile data by username

    Args:
        username (str): Twitter/X username (without @)

    Returns:
        dict: User profile data
    """
    token = os.getenv("DAOROUNDUP_BEARER_TOKEN")
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


def detect_keywords_in_description(description):
    """
    Detect specific keywords in user description

    Args:
        description (str): User bio/description text

    Returns:
        dict: Contains found keywords and detection results
    """
    if not description:
        return {"keywords_found": [], "has_keywords": False}

    # Keywords to search for (case-insensitive)
    target_keywords = ["FACES", "$FACES", "AIBTC"]
    found_keywords = []

    # Convert description to uppercase for case-insensitive search
    description_upper = description.upper()

    # Check for each keyword
    for keyword in target_keywords:
        if keyword.upper() in description_upper:
            found_keywords.append(keyword)

    return {
        "keywords_found": found_keywords,
        "has_keywords": len(found_keywords) > 0,
        "keyword_count": len(found_keywords),
    }


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
                }

                # Extract author information from includes if available
                if hasattr(tweet_response, "includes") and tweet_response.includes:
                    if "users" in tweet_response.includes:
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

                    if "media" in tweet_response.includes:
                        tweet_data["media_objects"] = tweet_response.includes["media"]
                        logger.debug(
                            f"Found {len(tweet_response.includes['media'])} media objects in API v2 response"
                        )

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
            if entities and isinstance(entities, dict) and "media" in entities:
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
                media_objects = tweet_data.get("media_objects", [])
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

    async def _store_user_if_needed(self, tweet_data: Dict[str, Any]) -> Optional[UUID]:
        """Store user data if not already exists.

        Args:
            tweet_data: Tweet data containing user information

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
                logger.debug(f"User {author_username} already exists in database")
                return existing_users[0].id

            # Create new user record
            user_data = XUserCreate(
                name=tweet_data.get("author_name"),
                username=author_username,
                user_id=tweet_data.get("author_id"),  # Twitter user ID
            )

            user = backend.create_x_user(user_data)
            logger.info(f"Created new user record for {author_username}")
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

            # Store user data if needed
            author_id = await self._store_user_if_needed(tweet_data)

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

            # Fetch author profile data and analyze Bitcoin face
            author_profile_data = {}
            author_pfp_analysis = {}
            author_keywords = {}

            author_username = tweet_data.get("author_username")
            if author_username:
                try:
                    profile_data = fetch_user_profile(author_username)
                    if not profile_data.get("error"):
                        author_profile_data = profile_data

                        # Analyze profile image for Bitcoin face
                        profile_image_url = profile_data.get("profile_image_url")
                        if profile_image_url:
                            pfp_analysis = analyze_bitcoin_face(profile_image_url)
                            if not pfp_analysis.get("error"):
                                author_pfp_analysis = pfp_analysis

                        # Detect keywords in description
                        description = profile_data.get("description")
                        if description:
                            author_keywords = detect_keywords_in_description(
                                description
                            )

                except Exception as e:
                    logger.warning(
                        f"Error fetching author profile for {author_username}: {str(e)}"
                    )

            # Analyze tweet images for Bitcoin faces
            tweet_images_analysis = []
            for image_url in image_urls:
                try:
                    image_analysis = analyze_bitcoin_face(image_url)
                    if not image_analysis.get("error"):
                        tweet_images_analysis.append(
                            {"image_url": image_url, "analysis": image_analysis}
                        )
                except Exception as e:
                    logger.warning(f"Error analyzing tweet image {image_url}: {str(e)}")

            # Create tweet record
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
                # New fields for Bitcoin face analysis
                author_profile_data=author_profile_data,
                author_pfp_analysis=author_pfp_analysis,
                author_keywords=author_keywords,
                tweet_images_analysis=tweet_images_analysis,
            )

            tweet_record = backend.create_x_tweet(tweet_create_data)
            logger.info(
                f"Successfully stored tweet {tweet_id} with {len(image_urls)} images"
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


# Global instance for reuse across the application
twitter_data_service = TwitterDataService()
