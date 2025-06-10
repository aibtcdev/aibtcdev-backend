import base64
from typing import Any, Dict, List, Optional

import httpx
import magic

from lib.logger import configure_logger
from lib.utils import extract_image_urls
from services.workflows.capability_mixins import BaseCapabilityMixin

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
    """Workflow node to process proposal images: extract URLs, download, and base64 encode."""

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
        proposal_data_str = state.get("proposal_data", "")

        if not proposal_data_str:
            self.logger.info(
                f"[ImageProcessorNode:{proposal_id}] No proposal_data, skipping."
            )
            # Return empty list to ensure state is updated
            return []

        self.logger.info(
            f"[ImageProcessorNode:{proposal_id}] Starting image processing."
        )
        image_urls = extract_image_urls(proposal_data_str)

        if not image_urls:
            self.logger.info(f"[ImageProcessorNode:{proposal_id}] No image URLs found.")
            # Return empty list explicitly to ensure state is updated
            return []

        processed_images = []
        async with httpx.AsyncClient() as client:
            for url in image_urls:
                try:
                    self.logger.debug(
                        f"[ImageProcessorNode:{proposal_id}] Processing image URL: {url}"
                    )
                    response = await client.get(url, timeout=10.0)
                    response.raise_for_status()

                    # Detect MIME type from actual image content using python-magic
                    image_content = response.content
                    mime_type = detect_image_mime_type(image_content)

                    # Encode to base64
                    image_data = base64.b64encode(image_content).decode("utf-8")

                    processed_images.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_data}"
                            },
                        }
                    )
                    self.logger.debug(
                        f"[ImageProcessorNode:{proposal_id}] Successfully processed image: {url} (detected as {mime_type})"
                    )
                except Exception as e:
                    self.logger.error(
                        f"[ImageProcessorNode:{proposal_id}] Error processing {url}: {str(e)}"
                    )

        self.logger.info(
            f"[ImageProcessorNode:{proposal_id}] Processed {len(processed_images)} images."
        )
        return processed_images
