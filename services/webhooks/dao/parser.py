"""Parser for DAO webhook payloads."""

from typing import Any, Dict

from lib.logger import configure_logger
from services.webhooks.base import WebhookParser
from services.webhooks.dao.models import AIBTCCoreWebhookPayload


class DAOParser(WebhookParser):
    """Parser for DAO webhook payloads.

    This parser validates and transforms raw webhook data into a structured
    DAOWebhookPayload object for further processing.
    """

    def __init__(self):
        """Initialize the DAO webhook parser."""
        super().__init__()
        self.logger = configure_logger(self.__class__.__name__)

    def parse(self, raw_data: Dict[str, Any]) -> AIBTCCoreWebhookPayload:
        """Parse the raw webhook data into a structured AIBTCCoreWebhookPayload payload.

        Args:
            raw_data: The raw webhook payload containing DAO, contracts, and token_info data

        Returns:
            AIBTCCoreWebhookPayload: A structured representation of the DAO creation data

        Raises:
            ValueError: If the payload is missing required fields or has invalid data
        """
        try:
            self.logger.info("Parsing DAO webhook payload using AIBTCCoreWebhookPayload structure")

            # Validate the payload using the new Pydantic model
            dao_payload = AIBTCCoreWebhookPayload(**raw_data)

            self.logger.info(
                f"Successfully parsed DAO webhook payload for '{dao_payload.name}' using new structure"
            )
            return dao_payload

        except Exception as e:
            self.logger.error(f"Error parsing DAO webhook payload with new structure: {str(e)}")
            raise ValueError(f"Invalid DAO webhook payload (new structure): {str(e)}")
