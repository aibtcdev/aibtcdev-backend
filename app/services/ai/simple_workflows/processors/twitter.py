"""Twitter processing utilities for simple workflows.

This module provides functions to retrieve tweet data from the database and format
it for consumption by LLMs.
"""

from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from app.backend.factory import backend
from app.lib.logger import configure_logger

logger = configure_logger(__name__)


async def fetch_tweet(tweet_db_id: UUID) -> Optional[Dict[str, Any]]:
    """Fetch stored tweet data from database.

    Args:
        tweet_db_id: Database ID of the tweet record

    Returns:
        Dictionary containing tweet data or None if failed
    """
    try:
        tweet = backend.get_x_tweet(tweet_db_id)
        if not tweet:
            logger.warning(f"Tweet with ID {tweet_db_id} not found in database")
            return None

        # Fetch author information if available
        author_info = {}
        if tweet.author_id:
            try:
                author = backend.get_x_user(tweet.author_id)
                if author:
                    author_info = {
                        "author_description": author.description,
                        "author_location": author.location,
                        "author_url": author.url,
                        "author_verified": author.verified,
                        "author_verified_type": author.verified_type,
                        "author_bitcoin_face_score": author.bitcoin_face_score,
                        "author_profile_image_url": author.profile_image_url,
                    }
                    logger.debug(
                        f"Retrieved author info for user {author.username}, bitcoin_face_score: {author.bitcoin_face_score}"
                    )
            except Exception as e:
                logger.warning(
                    f"Error fetching author info for tweet {tweet_db_id}: {str(e)}"
                )

        # Convert to dictionary format
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
            **author_info,  # Include author information
        }

        logger.debug(f"Retrieved tweet data for ID {tweet_db_id}")
        return tweet_data

    except Exception as e:
        logger.error(f"Error retrieving tweet data for ID {tweet_db_id}: {str(e)}")
        return None


def format_tweet(tweet_data: Dict[str, Any]) -> str:
    """Format tweet data for inclusion in proposal content.

    Args:
        tweet_data: Tweet data dictionary from database

    Returns:
        Formatted tweet content
    """
    try:
        text = tweet_data.get("text", "")
        # Escape curly braces in tweet text to prevent template parsing issues
        text = text.replace("{", "{{").replace("}", "}}")

        author_name = tweet_data.get("author_name", "")
        author_username = tweet_data.get("author_username", "")
        created_at = tweet_data.get("created_at", "")
        tweet_images_analysis = tweet_data.get("tweet_images_analysis", [])

        # Extract author information
        author_description = tweet_data.get("author_description", "")
        author_location = tweet_data.get("author_location", "")
        author_url = tweet_data.get("author_url", "")
        author_verified = tweet_data.get("author_verified", False)
        author_verified_type = tweet_data.get("author_verified_type", "")
        author_bitcoin_face_score = tweet_data.get("author_bitcoin_face_score")

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

        # Format bitcoin face score
        bitcoin_face_str = (
            f"{author_bitcoin_face_score:.4f}"
            if author_bitcoin_face_score is not None
            else "None"
        )

        formatted_tweet = f"""
<tweet>
  <author>{author_name} (@{author_username})</author>
  <created_at>{created_str}</created_at>
  <text>{text}</text>
  <author_info>
    <description>{author_description or "None"}</description>
    <location>{author_location or "None"}</location>
    <url>{author_url or "None"}</url>
    <verified>{author_verified}</verified>
    <verified_type>{author_verified_type or "None"}</verified_type>
    <bitcoin_face_score>{bitcoin_face_str}</bitcoin_face_score>
  </author_info>
  <tweet_images_analysis>{str(tweet_images_analysis) if tweet_images_analysis else "None"}</tweet_images_analysis>
</tweet>
"""
        return formatted_tweet.strip()

    except Exception as e:
        logger.error(f"Error formatting tweet content: {str(e)}")
        return f"<tweet><text>Error formatting tweet: {str(e)}</text></tweet>"


def extract_tweet_images(tweet_data: Dict[str, Any]) -> List[str]:
    """Extract image URLs from stored tweet data.

    Args:
        tweet_data: Tweet data dictionary from database

    Returns:
        List of image URLs
    """
    try:
        # Get images directly from the stored tweet data
        image_urls = tweet_data.get("images", [])

        # Ensure we have a list and remove any None values
        if not isinstance(image_urls, list):
            image_urls = []
        else:
            image_urls = [url for url in image_urls if url]

        logger.debug(
            f"Retrieved {len(image_urls)} images from stored tweet: {image_urls}"
        )
        return image_urls

    except Exception as e:
        logger.error(f"Error extracting images from stored tweet: {str(e)}")
        return []


def format_tweet_images(
    tweet_data: Dict[str, Any], tweet_db_id: UUID
) -> List[Dict[str, Any]]:
    """Format tweet images for LLM consumption.

    Args:
        tweet_data: Tweet data dictionary
        tweet_db_id: Database ID of the tweet

    Returns:
        List of formatted image dictionaries
    """
    tweet_image_urls = extract_tweet_images(tweet_data)
    tweet_images = []

    for image_url in tweet_image_urls:
        tweet_images.append(
            {
                "type": "image_url",
                "image_url": {"url": image_url, "detail": "auto"},
                "source": "tweet",
                "tweet_id": tweet_data.get("id"),  # Original Twitter ID
                "tweet_db_id": str(tweet_db_id),  # Database ID
            }
        )

    return tweet_images


async def process_tweets(
    tweet_db_ids: List[UUID],
    proposal_id: str = "unknown",
) -> Tuple[str, List[Dict[str, Any]]]:
    """Process tweet database IDs to retrieve stored tweet data and format content.

    Args:
        tweet_db_ids: List of tweet database IDs to process
        proposal_id: Optional proposal ID for logging

    Returns:
        Tuple of (combined_tweet_content, tweet_image_blobs)
    """
    if not tweet_db_ids:
        logger.info(
            f"[TwitterProcessor:{proposal_id}] No tweet_db_ids provided, skipping."
        )
        return "", []

    logger.info(
        f"[TwitterProcessor:{proposal_id}] Processing {len(tweet_db_ids)} stored tweets."
    )

    tweet_contents = []
    tweet_images = []

    for tweet_db_id in tweet_db_ids:
        if not isinstance(tweet_db_id, UUID):
            logger.warning(
                f"[TwitterProcessor:{proposal_id}] Invalid tweet DB ID: {tweet_db_id}"
            )
            continue

        logger.debug(
            f"[TwitterProcessor:{proposal_id}] Processing tweet DB ID: {tweet_db_id}"
        )

        # Get stored tweet content
        tweet_data = await fetch_tweet(tweet_db_id)
        if not tweet_data:
            logger.warning(
                f"[TwitterProcessor:{proposal_id}] Could not retrieve tweet: {tweet_db_id}"
            )
            continue

        # Format tweet content
        formatted_tweet = format_tweet(tweet_data)
        tweet_contents.append(formatted_tweet)

        logger.debug(
            f"[TwitterProcessor:{proposal_id}] Formatted tweet content: {formatted_tweet[:200]}..."
        )

        # Extract and format images from stored tweet
        tweet_image_blobs = format_tweet_images(tweet_data, tweet_db_id)
        tweet_images.extend(tweet_image_blobs)

        logger.debug(
            f"[TwitterProcessor:{proposal_id}] Processed tweet {tweet_db_id}, found {len(tweet_image_blobs)} images"
        )

    # Combine all tweet content
    combined_tweet_content = "\n\n".join(tweet_contents) if tweet_contents else ""

    logger.info(
        f"[TwitterProcessor:{proposal_id}] Processed {len(tweet_contents)} tweets, found {len(tweet_images)} total images."
    )

    return combined_tweet_content, tweet_images


def count_tweet_images(tweet_images: List[Dict[str, Any]]) -> int:
    """Count the number of tweet images.

    Args:
        tweet_images: List of tweet image dictionaries

    Returns:
        Number of tweet images
    """
    if not tweet_images:
        return 0

    return len([img for img in tweet_images if img.get("source") == "tweet"])


def get_tweet_image_urls(tweet_images: List[Dict[str, Any]]) -> List[str]:
    """Extract image URLs from tweet images.

    Args:
        tweet_images: List of tweet image dictionaries

    Returns:
        List of image URLs from tweets
    """
    if not tweet_images:
        return []

    urls = []
    for image in tweet_images:
        if image.get("source") == "tweet" and image.get("type") == "image_url":
            url = image.get("image_url", {}).get("url")
            if url:
                urls.append(url)

    return urls
