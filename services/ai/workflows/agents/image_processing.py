from typing import Any, Dict, List, Optional

import magic

from lib.logger import configure_logger
from lib.utils import extract_image_urls
from services.ai.workflows.mixins.capability_mixins import BaseCapabilityMixin

logger = configure_logger(__name__)


def detect_image_mime_type(image_data: bytes) -> str:
    """Detect MIME type from image content using python-magic library.

    Args:
        image_data: Raw image bytes

    Returns:
        MIME type string, defaults to 'image/jpeg' if unknown or not an image
    """
    try:
        mime_type = magic.from_buffer(image_data, mime=True)

        # Ensure it's actually an image MIME type
        if mime_type and mime_type.startswith("image/"):
            return mime_type
        else:
            logger.warning(
                f"Detected non-image MIME type: {mime_type}, defaulting to image/jpeg"
            )
            return "image/jpeg"

    except Exception as e:
        logger.warning(f"Error detecting MIME type: {e}, defaulting to image/jpeg")
        return "image/jpeg"


class ImageProcessingNode(BaseCapabilityMixin):
    """Workflow node to process proposal images: extract URLs and format them for LLM."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the image processing node.

        Args:
            config: Optional configuration dictionary
        """
        super().__init__(config=config, state_key="proposal_images")
        self.initialize()

    async def process(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process images in the proposal data.

        Args:
            state: The current workflow state

        Returns:
            List of dictionaries containing processed images in a format suitable for LLM
        """
        proposal_id = state.get("proposal_id", "unknown")
        proposal_content = state.get("proposal_content", "")

        if not proposal_content:
            self.logger.info(
                f"[ImageProcessorNode:{proposal_id}] No proposal_content, skipping."
            )
            # Return empty list to ensure state is updated
            return []

        self.logger.info(
            f"[ImageProcessorNode:{proposal_id}] Starting image processing."
        )
        image_urls = extract_image_urls(proposal_content)

        if not image_urls:
            self.logger.info(f"[ImageProcessorNode:{proposal_id}] No image URLs found.")
            # Return empty list explicitly to ensure state is updated
            return []

        processed_images = []
        for url in image_urls:
            self.logger.debug(
                f"[ImageProcessorNode:{proposal_id}] Processing image URL: {url}"
            )

            processed_images.append(
                {
                    "type": "image_url",
                    "image_url": {"url": url},
                }
            )
            self.logger.debug(
                f"[ImageProcessorNode:{proposal_id}] Successfully processed image: {url}"
            )

        self.logger.info(
            f"[ImageProcessorNode:{proposal_id}] Processed {len(processed_images)} images."
        )
        return processed_images
