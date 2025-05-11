import base64
from typing import Any, Dict, List, Optional

import httpx

from lib.logger import configure_logger
from lib.utils import extract_image_urls
from services.workflows.capability_mixins import BaseCapabilityMixin

logger = configure_logger(__name__)


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
                    image_data = base64.b64encode(response.content).decode("utf-8")

                    # Determine MIME type from URL extension
                    mime_type = "image/jpeg"  # Default
                    if url.lower().endswith((".jpg", ".jpeg")):
                        mime_type = "image/jpeg"
                    elif url.lower().endswith(".png"):
                        mime_type = "image/png"
                    elif url.lower().endswith(".gif"):
                        mime_type = "image/gif"
                    elif url.lower().endswith(".webp"):
                        mime_type = "image/webp"

                    processed_images.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_data}"
                            },
                        }
                    )
                    self.logger.debug(
                        f"[ImageProcessorNode:{proposal_id}] Successfully processed image: {url}"
                    )
                except Exception as e:
                    self.logger.error(
                        f"[ImageProcessorNode:{proposal_id}] Error processing {url}: {str(e)}"
                    )

        self.logger.info(
            f"[ImageProcessorNode:{proposal_id}] Processed {len(processed_images)} images."
        )
        return processed_images
