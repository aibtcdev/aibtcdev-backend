import re
from typing import Any, Dict, List, Optional

from lib.logger import configure_logger
from services.ai.workflows.mixins.capability_mixins import BaseCapabilityMixin
from services.communication.twitter_service import create_twitter_service_from_config

logger = configure_logger(__name__)


class TwitterProcessingNode(BaseCapabilityMixin):
    """Workflow node to process X/Twitter URLs: extract tweet IDs, fetch tweet content, and process tweet images."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Twitter processing node.

        Args:
            config: Optional configuration dictionary
        """
        super().__init__(config=config, state_key="tweet_content")
        self.initialize()
        self.twitter_service = None

    async def _initialize_twitter_service(self):
        """Initialize Twitter service if not already initialized."""
        if self.twitter_service is None:
            try:
                self.twitter_service = create_twitter_service_from_config()
                await self.twitter_service._ainitialize()
                self.logger.info("Twitter service initialized successfully")
            except Exception as e:
                self.logger.error(f"Failed to initialize Twitter service: {str(e)}")
                self.twitter_service = None

    def _extract_twitter_urls(self, text: str) -> List[str]:
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

    def _extract_tweet_id_from_url(self, url: str) -> Optional[str]:
        """Extract tweet ID from X/Twitter URL.

        Args:
            url: Twitter/X URL

        Returns:
            Tweet ID if found, None otherwise
        """
        pattern = r"https?://(?:x\.com|twitter\.com)/[^/]+/status/(\d+)"
        match = re.search(pattern, url, re.IGNORECASE)
        return match.group(1) if match else None

    async def _fetch_tweet_content(self, tweet_id: str) -> Optional[Dict[str, Any]]:
        """Fetch tweet content using the Twitter service.

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
            tweet = await self.twitter_service.get_tweet_by_id(tweet_id)
            if tweet:
                tweet_data = {
                    "id": tweet.id,
                    "text": tweet.text,
                    "author_id": tweet.author_id,
                    "created_at": getattr(tweet, "created_at", None),
                    "public_metrics": getattr(tweet, "public_metrics", {}),
                    "entities": getattr(tweet, "entities", {}),
                    "attachments": getattr(tweet, "attachments", {}),
                }
                self.logger.info(f"Successfully fetched tweet {tweet_id} using API v2")
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
                    "entities": status.entities,
                    "extended_entities": getattr(status, "extended_entities", {}),
                }
                self.logger.info(
                    f"Successfully fetched tweet {tweet_id} using API v1.1"
                )
                return tweet_data

            self.logger.warning(f"Tweet {tweet_id} not found")
            return None

        except Exception as e:
            self.logger.error(f"Error fetching tweet {tweet_id}: {str(e)}")
            return None

    def _extract_images_from_tweet(self, tweet_data: Dict[str, Any]) -> List[str]:
        """Extract image URLs from tweet data.

        Args:
            tweet_data: Tweet data dictionary

        Returns:
            List of image URLs
        """
        image_urls = []

        try:
            # Check extended_entities for media (API v1.1)
            extended_entities = tweet_data.get("extended_entities", {})
            if "media" in extended_entities:
                for media in extended_entities["media"]:
                    if media.get("type") == "photo":
                        media_url = media.get("media_url_https") or media.get(
                            "media_url"
                        )
                        if media_url:
                            image_urls.append(media_url)

            # Check entities for media (fallback)
            entities = tweet_data.get("entities", {})
            if "media" in entities:
                for media in entities["media"]:
                    if media.get("type") == "photo":
                        media_url = media.get("media_url_https") or media.get(
                            "media_url"
                        )
                        if media_url:
                            image_urls.append(media_url)

            # Check attachments for media keys (API v2)
            attachments = tweet_data.get("attachments", {})
            if "media_keys" in attachments:
                # Note: For API v2, we would need to make additional calls to get media URLs
                # This is a simplified version - full implementation would require media expansion
                self.logger.debug(
                    f"Found media keys in tweet, but media expansion not implemented: {attachments['media_keys']}"
                )

            # Remove duplicates
            image_urls = list(set(image_urls))

            self.logger.debug(
                f"Extracted {len(image_urls)} images from tweet: {image_urls}"
            )

        except Exception as e:
            self.logger.error(f"Error extracting images from tweet: {str(e)}")

        return image_urls

    def _format_tweet_for_content(self, tweet_data: Dict[str, Any]) -> str:
        """Format tweet data for inclusion in proposal content.

        Args:
            tweet_data: Tweet data dictionary

        Returns:
            Formatted tweet content
        """
        try:
            text = tweet_data.get("text", "")
            author_name = tweet_data.get("author_name", "")
            author_username = tweet_data.get("author_username", "")
            created_at = tweet_data.get("created_at", "")

            # Format creation date
            created_str = ""
            if created_at:
                try:
                    if hasattr(created_at, "strftime"):
                        created_str = created_at.strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        created_str = str(created_at)
                except (AttributeError, ValueError, TypeError):
                    created_str = str(created_at)

            formatted_tweet = f"""
<tweet>
  <author>{author_name} (@{author_username})</author>
  <created_at>{created_str}</created_at>
  <text>{text}</text>
</tweet>
"""
            return formatted_tweet.strip()

        except Exception as e:
            self.logger.error(f"Error formatting tweet content: {str(e)}")
            return f"<tweet><text>Error formatting tweet: {str(e)}</text></tweet>"

    async def process(self, state: Dict[str, Any]) -> str:
        """Process Twitter URLs in the proposal data.

        Args:
            state: The current workflow state

        Returns:
            Formatted tweet content string, and updates state with tweet images
        """
        proposal_id = state.get("proposal_id", "unknown")
        proposal_content = state.get("proposal_content", "")

        if not proposal_content:
            self.logger.info(
                f"[TwitterProcessorNode:{proposal_id}] No proposal_content, skipping."
            )
            return ""

        self.logger.info(
            f"[TwitterProcessorNode:{proposal_id}] Starting Twitter URL processing."
        )

        # Extract Twitter URLs
        twitter_urls = self._extract_twitter_urls(proposal_content)

        if not twitter_urls:
            self.logger.info(
                f"[TwitterProcessorNode:{proposal_id}] No Twitter URLs found."
            )
            return ""

        self.logger.info(
            f"[TwitterProcessorNode:{proposal_id}] Found {len(twitter_urls)} Twitter URLs: {twitter_urls}"
        )

        tweet_contents = []
        tweet_images = []

        for url in twitter_urls:
            tweet_id = self._extract_tweet_id_from_url(url)
            if not tweet_id:
                self.logger.warning(
                    f"[TwitterProcessorNode:{proposal_id}] Could not extract tweet ID from URL: {url}"
                )
                continue

            self.logger.debug(
                f"[TwitterProcessorNode:{proposal_id}] Processing tweet ID: {tweet_id}"
            )

            # Fetch tweet content
            tweet_data = await self._fetch_tweet_content(tweet_id)
            if not tweet_data:
                self.logger.warning(
                    f"[TwitterProcessorNode:{proposal_id}] Could not fetch tweet: {tweet_id}"
                )
                continue

            # Format tweet content
            formatted_tweet = self._format_tweet_for_content(tweet_data)
            tweet_contents.append(formatted_tweet)

            # Extract images from tweet
            tweet_image_urls = self._extract_images_from_tweet(tweet_data)
            for image_url in tweet_image_urls:
                tweet_images.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url},
                        "source": "tweet",
                        "tweet_id": tweet_id,
                    }
                )

            self.logger.debug(
                f"[TwitterProcessorNode:{proposal_id}] Processed tweet {tweet_id}, found {len(tweet_image_urls)} images"
            )

        # Update state with tweet images (will be merged with proposal_images later)
        if "tweet_images" not in state:
            state["tweet_images"] = []
        state["tweet_images"].extend(tweet_images)

        # Combine all tweet content
        combined_tweet_content = "\n\n".join(tweet_contents) if tweet_contents else ""

        self.logger.info(
            f"[TwitterProcessorNode:{proposal_id}] Processed {len(tweet_contents)} tweets, found {len(tweet_images)} total images."
        )

        return combined_tweet_content
