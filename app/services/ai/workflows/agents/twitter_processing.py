from typing import Any, Dict, List, Optional
from uuid import UUID

from app.backend.factory import backend
from app.lib.logger import configure_logger
from app.services.ai.workflows.mixins.capability_mixins import BaseCapabilityMixin

logger = configure_logger(__name__)


class TwitterProcessingNode(BaseCapabilityMixin):
    """Workflow node to process X/Twitter URLs: retrieve stored tweet data and process tweet images."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Twitter processing node.

        Args:
            config: Optional configuration dictionary
        """
        super().__init__(config=config, state_key="tweet_content")
        self.initialize()

    async def _process_tweet_by_id(self, tweet_db_id: UUID) -> Optional[Dict[str, Any]]:
        """Get stored tweet data from database.

        Args:
            tweet_db_id: Database ID of the tweet record

        Returns:
            Dictionary containing tweet data or None if failed
        """
        try:
            tweet = backend.get_x_tweet(tweet_db_id)
            if not tweet:
                self.logger.warning(
                    f"Tweet with ID {tweet_db_id} not found in database"
                )
                return None

            # Convert to dictionary format expected by TwitterProcessingNode
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
            }

            self.logger.debug(f"Retrieved tweet data for ID {tweet_db_id}")
            return tweet_data

        except Exception as e:
            self.logger.error(
                f"Error retrieving tweet data for ID {tweet_db_id}: {str(e)}"
            )
            return None

    def _extract_images_from_tweet(self, tweet_data: Dict[str, Any]) -> List[str]:
        """Extract image URLs from stored tweet data.

        Args:
            tweet_data: Tweet data dictionary from database

        Returns:
            List of image URLs
        """
        try:
            # Get images directly from the stored tweet data (TwitterDataService stores them in images field)
            image_urls = tweet_data.get("images", [])

            # Ensure we have a list and remove any None values
            if not isinstance(image_urls, list):
                image_urls = []
            else:
                image_urls = [url for url in image_urls if url]

            self.logger.debug(
                f"Retrieved {len(image_urls)} images from stored tweet: {image_urls}"
            )
            return image_urls

        except Exception as e:
            self.logger.error(f"Error extracting images from stored tweet: {str(e)}")
            return []

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
        """Process tweet database IDs to retrieve stored tweet data and format content.

        Args:
            state: The current workflow state containing tweet_db_ids

        Returns:
            Formatted tweet content string, and updates state with tweet images
        """
        proposal_id = state.get("proposal_id", "unknown")
        tweet_db_ids = state.get("tweet_db_ids", [])

        if not tweet_db_ids:
            self.logger.info(
                f"[TwitterProcessorNode:{proposal_id}] No tweet_db_ids provided, skipping."
            )
            return ""

        self.logger.info(
            f"[TwitterProcessorNode:{proposal_id}] Processing {len(tweet_db_ids)} stored tweets."
        )

        tweet_contents = []
        tweet_images = []

        for tweet_db_id in tweet_db_ids:
            if not isinstance(tweet_db_id, UUID):
                self.logger.warning(
                    f"[TwitterProcessorNode:{proposal_id}] Invalid tweet DB ID: {tweet_db_id}"
                )
                continue

            self.logger.debug(
                f"[TwitterProcessorNode:{proposal_id}] Processing tweet DB ID: {tweet_db_id}"
            )

            # Get stored tweet content
            tweet_data = await self._process_tweet_by_id(tweet_db_id)
            if not tweet_data:
                self.logger.warning(
                    f"[TwitterProcessorNode:{proposal_id}] Could not retrieve tweet: {tweet_db_id}"
                )
                continue

            # Format tweet content
            formatted_tweet = self._format_tweet_for_content(tweet_data)
            tweet_contents.append(formatted_tweet)

            self.logger.debug(
                f"[TwitterProcessorNode:{proposal_id}] Formatted tweet content: {formatted_tweet[:200]}..."
            )

            # Extract images from stored tweet
            tweet_image_urls = self._extract_images_from_tweet(tweet_data)
            for image_url in tweet_image_urls:
                tweet_images.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url},
                        "source": "tweet",
                        "tweet_id": tweet_data.get("id"),  # Original Twitter ID
                        "tweet_db_id": str(tweet_db_id),  # Database ID
                    }
                )

            self.logger.debug(
                f"[TwitterProcessorNode:{proposal_id}] Processed tweet {tweet_db_id}, found {len(tweet_image_urls)} images"
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
