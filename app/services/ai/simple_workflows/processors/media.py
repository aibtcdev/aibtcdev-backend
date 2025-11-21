"""Media processing utilities for simple workflows.

This module provides functions to extract image and video URLs from text and format them
for consumption by LLM vision models.
"""

from typing import Any, Dict, List

from app.lib.logger import configure_logger
from app.lib.utils import extract_image_urls, extract_video_urls

logger = configure_logger(__name__)


async def process_media(
    proposal_content: str,
    proposal_id: str = "unknown",
) -> List[Dict[str, Any]]:
    """Process media (images and videos) in the proposal content.

    Args:
        proposal_content: The proposal content to search for images
        proposal_id: Optional proposal ID for logging

    Returns:
        List of dictionaries containing processed images in OpenAI vision format
    """
    if not proposal_content:
        logger.info(f"[ImageProcessor:{proposal_id}] No proposal_content, skipping.")
        return []

    logger.info(f"[MediaProcessor:{proposal_id}] Starting media processing.")

    # Extract media URLs from the proposal content
    image_urls = extract_image_urls(proposal_content)
    video_urls = extract_video_urls(proposal_content)

    if not image_urls and not video_urls:
        logger.info(f"[MediaProcessor:{proposal_id}] No media URLs found.")
        return []

    # Format media for OpenAI vision API
    processed_media = []
    for url in image_urls:
        logger.debug(f"[MediaProcessor:{proposal_id}] Processing image URL: {url}")
        processed_media.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": url,
                    "detail": "auto",
                },
            }
        )
    for url in video_urls:
        logger.debug(f"[MediaProcessor:{proposal_id}] Processing video URL: {url}")
        processed_media.append(
            {
                "type": "video_url",
                "video_url": {
                    "url": url,
                    "detail": "auto",
                },
            }
        )

    logger.info(
        f"[MediaProcessor:{proposal_id}] Processed {len(processed_media)} media items ({len(image_urls)} images + {len(video_urls)} videos)."
    )
    return processed_media


def format_media_for_messages(media: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Format processed media for inclusion in message content.

    Args:
        media: List of processed media (images/videos)

    Returns:
        List of media formatted for message content
    """
    if not media:
        return []

    formatted_media = []
    for item in media:
        item_type = item.get("type")
        if item_type in ("image_url", "video_url"):
            # Ensure detail parameter is set
            item_with_detail = item.copy()
            url_key = "image_url" if item_type == "image_url" else "video_url"
            if "detail" not in item_with_detail.get(url_key, {}):
                item_with_detail[url_key]["detail"] = "auto"
            formatted_media.append(item_with_detail)

    return formatted_media


def count_media(media: List[Dict[str, Any]]) -> int:
    """Count the number of valid media items (images + videos).

    Args:
        media: List of processed media

    Returns:
        Number of valid media items
    """
    if not media:
        return 0

    return len([m for m in media if m.get("type") in ("image_url", "video_url")])


def get_media_urls(media: List[Dict[str, Any]]) -> List[str]:
    """Extract media URLs from processed media.

    Args:
        media: List of processed media

    Returns:
        List of media URLs (images + videos)
    """
    if not media:
        return []

    urls = []
    for item in media:
        item_type = item.get("type")
        url_key = "image_url" if item_type == "image_url" else "video_url"
        url = item.get(url_key, {}).get("url")
        if url:
            urls.append(url)

    return urls
