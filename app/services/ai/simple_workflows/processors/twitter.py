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
                # Get x_users data (primary source for Twitter verification)
                author = backend.get_x_user(tweet.author_id)
                if author:
                    author_info = {
                        "author_description": author.description,
                        "author_location": author.location,
                        "author_url": author.url,
                        "author_verified": author.verified,  # Twitter verification
                        "author_verified_type": author.verified_type,  # Twitter verification type
                        "author_bitcoin_face_score": author.bitcoin_face_score,
                        "author_profile_image_url": author.profile_image_url,
                        "author_name": author.name,  # Use x_users.name as fallback
                        "author_username": author.username,  # Use x_users.username as fallback
                    }

                    # Try to get additional profile data by username match
                    if author.username:
                        try:
                            logger.debug(
                                f"Looking up profile for username: {author.username}"
                            )
                            profiles = backend.list_profiles_by_username(
                                author.username
                            )
                            logger.debug(
                                f"Found {len(profiles)} profiles for username: {author.username}"
                            )
                            if profiles:
                                profile = profiles[0]
                                # Add profile-specific data and override verified with platform verification
                                author_info.update(
                                    {
                                        "author_profile_email": profile.email,
                                        "author_profile_image": profile.profile_image,
                                        "author_verified": profile.is_verified,  # Use platform verification instead of Twitter verification
                                        "author_verified_type": author.verified_type,  # Use x_users.verified_type
                                    }
                                )
                                logger.debug(
                                    f"Retrieved profile info for user {author.username}, platform_verified: {profile.is_verified}, user_type: {profile.user_type}"
                                )
                            else:
                                logger.debug(
                                    f"No profile found for username: {author.username}"
                                )
                        except Exception as e:
                            logger.debug(
                                f"Could not fetch profile data for {author.username}: {str(e)}"
                            )

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

        # Extract enhanced profile information (removed user_type)

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

        # Check if this tweet has a quoted post
        quoted_tweet_db_id = tweet_data.get("quoted_tweet_db_id")
        quoted_post_xml = ""

        if quoted_tweet_db_id:
            try:
                # Fetch the quoted tweet data
                quoted_tweet = backend.get_x_tweet(quoted_tweet_db_id)
                if quoted_tweet:
                    # Get quoted tweet author info
                    quoted_author_info = {}
                    if quoted_tweet.author_id:
                        quoted_author = backend.get_x_user(quoted_tweet.author_id)
                        if quoted_author:
                            quoted_author_info = {
                                "description": quoted_author.description,
                                "location": quoted_author.location,
                                "url": quoted_author.url,
                                "verified": quoted_author.verified,
                                "verified_type": quoted_author.verified_type,
                                "bitcoin_face_score": quoted_author.bitcoin_face_score,
                            }

                    # Format quoted tweet creation date
                    quoted_created_str = ""
                    if quoted_tweet.created_at_twitter:
                        try:
                            if hasattr(quoted_tweet.created_at_twitter, "strftime"):
                                quoted_created_str = (
                                    quoted_tweet.created_at_twitter.strftime(
                                        "%Y-%m-%d %H:%M:%S"
                                    )
                                )
                            else:
                                quoted_created_str = str(
                                    quoted_tweet.created_at_twitter
                                )
                        except (AttributeError, ValueError, TypeError):
                            quoted_created_str = str(quoted_tweet.created_at_twitter)

                    # Format quoted author bitcoin face score
                    quoted_bitcoin_face_str = (
                        f"{quoted_author_info.get('bitcoin_face_score', 0):.4f}"
                        if quoted_author_info.get("bitcoin_face_score") is not None
                        else "None"
                    )

                    # Escape curly braces in quoted tweet text
                    quoted_text = quoted_tweet.message or ""
                    quoted_text = quoted_text.replace("{", "{{").replace("}", "}}")

                    quoted_post_xml = f"""
  <quoted_post>
    <author>{quoted_tweet.author_name or "Unknown"} (@{quoted_tweet.author_username or "unknown"})</author>
    <created_at>{quoted_created_str}</created_at>
    <text>{quoted_text}</text>
    <author_info>
      <description>{quoted_author_info.get("description") or "None"}</description>
      <location>{quoted_author_info.get("location") or "None"}</location>
      <url>{quoted_author_info.get("url") or "None"}</url>
      <verified>{quoted_author_info.get("verified", False)}</verified>
      <verified_type>{quoted_author_info.get("verified_type") or "None"}</verified_type>
      <bitcoin_face_score>{quoted_bitcoin_face_str}</bitcoin_face_score>
    </author_info>
    <tweet_images_analysis>{str(quoted_tweet.tweet_images_analysis) if quoted_tweet.tweet_images_analysis else "None"}</tweet_images_analysis>
  </quoted_post>"""
            except Exception as e:
                logger.warning(
                    f"Error fetching quoted tweet {quoted_tweet_db_id}: {str(e)}"
                )
                quoted_post_xml = f"""
  <quoted_post>
    <error>Could not retrieve quoted post: {str(e)}</error>
  </quoted_post>"""

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
  <tweet_images_analysis>{str(tweet_images_analysis) if tweet_images_analysis else "None"}</tweet_images_analysis>{quoted_post_xml}
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
