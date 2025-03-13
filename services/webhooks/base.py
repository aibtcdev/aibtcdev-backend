"""Base classes for webhook handling."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, TypeVar

from pydantic import BaseModel

from lib.logger import configure_logger

T = TypeVar("T")


class WebhookParser(ABC):
    """Base class for webhook payload parsers."""

    def __init__(self):
        self.logger = configure_logger(self.__class__.__name__)

    @abstractmethod
    def parse(self, raw_data: Dict[str, Any]) -> Any:
        """Parse the raw webhook data into a structured format.

        Args:
            raw_data: The raw webhook payload

        Returns:
            Parsed data in the appropriate format
        """
        pass


class WebhookHandler(ABC):
    """Base class for webhook handlers."""

    def __init__(self):
        self.logger = configure_logger(self.__class__.__name__)

    @abstractmethod
    async def handle(self, parsed_data: Any) -> Dict[str, Any]:
        """Handle the parsed webhook data.

        Args:
            parsed_data: The parsed webhook data

        Returns:
            Dict containing the result of handling the webhook
        """
        pass


class WebhookResponse(BaseModel):
    """Base response model for webhook endpoints."""

    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


class WebhookService:
    """Base webhook service that coordinates parsing and handling."""

    def __init__(self, parser: WebhookParser, handler: WebhookHandler):
        self.parser = parser
        self.handler = handler
        self.logger = configure_logger(self.__class__.__name__)

    async def process(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a webhook request.

        Args:
            raw_data: The raw webhook payload

        Returns:
            Dict containing the result of processing the webhook
        """
        try:
            parsed_data = self.parser.parse(raw_data)
            result = await self.handler.handle(parsed_data)
            return result
        except Exception as e:
            self.logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
            raise
