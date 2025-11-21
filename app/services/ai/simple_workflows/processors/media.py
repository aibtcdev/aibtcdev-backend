"""Image processing utilities for simple workflows.

This module provides functions to extract image URLs from text and format them
for consumption by LLM vision models.
"""

from typing import Any, Dict, List

from app.lib.logger import configure_logger
from app.lib.utils import extract_image_urls

logger = configure_logger(__name__)


async def process_images(
    proposal_content: str,
    proposal_id: str = "unknown",
) -> List[Dict[str, Any]]:
    """Process images in the proposal content.

    Args:
        proposal_content: The proposal content to search for images
        proposal_id: Optional proposal ID for logging

    Returns:
        List of dictionaries containing processed images in OpenAI vision format
    """
    if not proposal_content:
        logger.info(f"[ImageProcessor:{proposal_id}] No proposal_content, skipping.")
        return []

    logger.info(f"[ImageProcessor:{proposal_id}] Starting image processing.")

    # Extract image URLs from the proposal content
    image_urls = extract_image_urls(proposal_content)

    if not image_urls:
        logger.info(f"[ImageProcessor:{proposal_id}] No image URLs found.")
        return []

    # Format images for OpenAI vision API
    processed_images = []
    for url in image_urls:
        logger.debug(f"[ImageProcessor:{proposal_id}] Processing image URL: {url}")

        # Create OpenAI vision format
        processed_images.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": url,
                    "detail": "auto",  # Let OpenAI decide the detail level
                },
            }
        )

        logger.debug(
            f"[ImageProcessor:{proposal_id}] Successfully processed image: {url}"
        )

    logger.info(
        f"[ImageProcessor:{proposal_id}] Processed {len(processed_images)} images."
    )
    return processed_images


def format_images_for_messages(images: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Format processed images for inclusion in message content.

    Args:
        images: List of processed images

    Returns:
        List of images formatted for message content
    """
    if not images:
        return []

    formatted_images = []
    for image in images:
        if image.get("type") == "image_url":
            # Ensure detail parameter is set
            image_with_detail = image.copy()
            if "detail" not in image_with_detail.get("image_url", {}):
                image_with_detail["image_url"]["detail"] = "auto"
            formatted_images.append(image_with_detail)

    return formatted_images


def count_images(images: List[Dict[str, Any]]) -> int:
    """Count the number of valid images.

    Args:
        images: List of processed images

    Returns:
        Number of valid images
    """
    if not images:
        return 0

    return len([img for img in images if img.get("type") == "image_url"])


def get_image_urls(images: List[Dict[str, Any]]) -> List[str]:
    """Extract image URLs from processed images.

    Args:
        images: List of processed images

    Returns:
        List of image URLs
    """
    if not images:
        return []

    urls = []
    for image in images:
        if image.get("type") == "image_url":
            url = image.get("image_url", {}).get("url")
            if url:
                urls.append(url)

    return urls
