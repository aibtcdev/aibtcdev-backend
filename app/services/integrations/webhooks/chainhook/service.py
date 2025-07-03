"""Chainhook webhook service implementation."""

from app.lib.logger import configure_logger
from app.services.integrations.webhooks.base import WebhookService
from app.services.integrations.webhooks.chainhook.handler import ChainhookHandler
from app.services.integrations.webhooks.chainhook.parser import ChainhookParser


class ChainhookService(WebhookService):
    """Service for handling Chainhook webhooks.

    This service coordinates parsing and handling of Chainhook webhook payloads.
    """

    def __init__(self):
        """Initialize the Chainhook service with parser and handler components."""
        parser = ChainhookParser()
        handler = ChainhookHandler()
        super().__init__(parser=parser, handler=handler)
        self.logger = configure_logger(self.__class__.__name__)
