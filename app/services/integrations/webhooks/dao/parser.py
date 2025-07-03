"""Parser for DAO webhook payloads."""

from typing import Any, Dict

from app.lib.logger import configure_logger
from app.services.integrations.webhooks.base import WebhookParser
from app.services.integrations.webhooks.dao.models import DAOWebhookPayload


class DAOParser(WebhookParser):
    """Parser for DAO webhook payloads.

    This parser validates and transforms raw webhook data into a structured
    DAOWebhookPayload object for further processing.
    """

    def __init__(self):
        """Initialize the DAO webhook parser."""
        super().__init__()
        self.logger = configure_logger(self.__class__.__name__)

    def parse(self, raw_data: Dict[str, Any]) -> DAOWebhookPayload:
        """Parse the raw webhook data into a structured DAO payload.

        Args:
            raw_data: The raw webhook payload containing DAO, extensions, and token data

        Returns:
            DAOWebhookPayload: A structured representation of the DAO creation data

        Raises:
            ValueError: If the payload is missing required fields or has invalid data
        """
        try:
            self.logger.info("Parsing DAO webhook payload")

            # Validate the payload using Pydantic
            dao_payload = DAOWebhookPayload(**raw_data)

            self.logger.info(
                f"Successfully parsed DAO webhook payload for '{dao_payload.name}'"
            )
            return dao_payload

        except Exception as e:
            self.logger.error(f"Error parsing DAO webhook payload: {str(e)}")
            raise ValueError(f"Invalid DAO webhook payload: {str(e)}")
