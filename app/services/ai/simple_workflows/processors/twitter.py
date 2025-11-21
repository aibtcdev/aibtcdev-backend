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
            "videos": tweet.videos or [],
            "tweet_images_analysis": tweet.tweet_images_analysis or [],
            "quoted_tweet_db_id": tweet.quoted_tweet_db_id,
            "quoted_tweet_id": tweet.quoted_tweet_id,
            "replied_to_tweet_db_id": tweet.replied_to_tweet_db_id,
            "replied_to_tweet_id": tweet.replied_to_tweet_id,
            "in_reply_to_user_id": tweet.in_reply_to_user_id,
            "conversation_id": tweet.conversation_id,
            "is_worthy": tweet.is_worthy,
            "tweet_type": tweet.tweet_type,
            "confidence_score": tweet.confidence_score,
            "reason": tweet.reason,
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

        # Check if this tweet has a replied-to post
        replied_tweet_db_id = tweet_data.get("replied_to_tweet_db_id")
        replied_post_xml = ""

        if replied_tweet_db_id:
            try:
                # Fetch the replied-to tweet data
                replied_tweet = backend.get_x_tweet(replied_tweet_db_id)
                if replied_tweet:
                    # Get replied-to tweet author info
                    replied_author_info = {}
                    if replied_tweet.author_id:
                        replied_author = backend.get_x_user(replied_tweet.author_id)
                        if replied_author:
                            replied_author_info = {
                                "description": replied_author.description,
                                "location": replied_author.location,
                                "url": replied_author.url,
                                "verified": replied_author.verified,
                                "verified_type": replied_author.verified_type,
                                "bitcoin_face_score": replied_author.bitcoin_face_score,
                            }

                    # Format replied-to tweet creation date
                    replied_created_str = ""
                    if replied_tweet.created_at_twitter:
                        try:
                            if hasattr(replied_tweet.created_at_twitter, "strftime"):
                                replied_created_str = (
                                    replied_tweet.created_at_twitter.strftime(
                                        "%Y-%m-%d %H:%M:%S"
                                    )
                                )
                            else:
                                replied_created_str = str(
                                    replied_tweet.created_at_twitter
                                )
                        except (AttributeError, ValueError, TypeError):
                            replied_created_str = str(replied_tweet.created_at_twitter)

                    # Format replied-to author bitcoin face score
                    replied_bitcoin_face_str = (
                        f"{replied_author_info.get('bitcoin_face_score', 0):.4f}"
                        if replied_author_info.get("bitcoin_face_score") is not None
                        else "None"
                    )

                    # Escape curly braces in replied-to tweet text
                    replied_text = replied_tweet.message or ""
                    replied_text = replied_text.replace("{", "{{").replace("}", "}}")

                    replied_post_xml = f"""
  <replied_to_post>
    <author>{replied_tweet.author_name or "Unknown"} (@{replied_tweet.author_username or "unknown"})</author>
    <created_at>{replied_created_str}</created_at>
    <text>{replied_text}</text>
    <author_info>
      <description>{replied_author_info.get("description") or "None"}</description>
      <location>{replied_author_info.get("location") or "None"}</location>
      <url>{replied_author_info.get("url") or "None"}</url>
      <verified>{replied_author_info.get("verified", False)}</verified>
      <verified_type>{replied_author_info.get("verified_type") or "None"}</verified_type>
      <bitcoin_face_score>{replied_bitcoin_face_str}</bitcoin_face_score>
    </author_info>
    <tweet_images_analysis>{str(replied_tweet.tweet_images_analysis) if replied_tweet.tweet_images_analysis else "None"}</tweet_images_analysis>
    <videos>{str(replied_tweet.videos or [])}</videos>
  </replied_to_post>"""
            except Exception as e:
                logger.warning(
                    f"Error fetching replied-to tweet {replied_tweet_db_id}: {str(e)}"
                )
                replied_post_xml = f"""
  <replied_to_post>
    <error>Could not retrieve replied-to post: {str(e)}</error>
  </replied_to_post>"""

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
    <videos>{str(quoted_tweet.videos or [])}</videos>
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
  <tweet_images_analysis>{str(tweet_images_analysis) if tweet_images_analysis else "None"}</tweet_images_analysis>
  <videos>{str(tweet_data.get("videos", []))}</videos>{replied_post_xml}{quoted_post_xml}
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


def extract_tweet_videos(tweet_data: Dict[str, Any]) -> List[str]:
    """Extract video URLs from stored tweet data.

    Args:
        tweet_data: Tweet data dictionary from database

    Returns:
        List of video URLs
    """
    try:
        # Get videos directly from the stored tweet data
        video_urls = tweet_data.get("videos", [])

        # Ensure we have a list and remove any None values
        if not isinstance(video_urls, list):
            video_urls = []
        else:
            video_urls = [url for url in video_urls if url]

        logger.debug(
            f"Retrieved {len(video_urls)} videos from stored tweet: {video_urls}"
        )
        return video_urls

    except Exception as e:
        logger.error(f"Error extracting videos from stored tweet: {str(e)}")
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


def format_tweet_videos(
    tweet_data: Dict[str, Any], tweet_db_id: UUID
) -> List[Dict[str, Any]]:
    """Format tweet videos for LLM consumption.

    Args:
        tweet_data: Tweet data dictionary
        tweet_db_id: Database ID of the tweet

    Returns:
        List of formatted video dictionaries
    """
    tweet_video_urls = extract_tweet_videos(tweet_data)
    tweet_videos = []

    for video_url in tweet_video_urls:
        tweet_videos.append(
            {
                "type": "video_url",
                "video_url": {"url": video_url, "detail": "auto"},
                "source": "tweet",
                "tweet_id": tweet_data.get("id"),  # Original Twitter ID
                "tweet_db_id": str(tweet_db_id),  # Database ID
            }
        )

    return tweet_videos


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
    tweet_media = []

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

        # Extract and format media from stored tweet
        tweet_image_blobs = format_tweet_images(tweet_data, tweet_db_id)
        tweet_media.extend(tweet_image_blobs)

        tweet_video_blobs = format_tweet_videos(tweet_data, tweet_db_id)
        tweet_media.extend(tweet_video_blobs)

        logger.debug(
            f"[TwitterProcessor:{proposal_id}] Processed tweet {tweet_db_id}, found {len(tweet_image_blobs)} images, {len(tweet_video_blobs)} videos"
        )

    # Combine all tweet content
    combined_tweet_content = "\n\n".join(tweet_contents) if tweet_contents else ""

    logger.info(
        f"[TwitterProcessor:{proposal_id}] Processed {len(tweet_contents)} tweets, found {len(tweet_media)} total media items."
    )

    return combined_tweet_content, tweet_media


def count_tweet_media(tweet_media: List[Dict[str, Any]]) -> int:
    """Count the number of tweet media items (images + videos).

    Args:
        tweet_media: List of tweet media dictionaries

    Returns:
        Number of tweet media items
    """
    if not tweet_media:
        return 0

    return len([m for m in tweet_media if m.get("source") == "tweet" and m.get("type") in ("image_url", "video_url")])


def get_tweet_media_urls(tweet_media: List[Dict[str, Any]]) -> List[str]:
    """Extract media URLs from tweet media.

    Args:
        tweet_media: List of tweet media dictionaries

    Returns:
        List of media URLs from tweets
    """
    if not tweet_media:
        return []

    urls = []
    for item in tweet_media:
        if item.get("source") == "tweet":
            item_type = item.get("type")
            url_key = "image_url" if item_type == "image_url" else "video_url"
            url = item.get(url_key, {}).get("url")
            if url:
                urls.append(url)

    return urls
