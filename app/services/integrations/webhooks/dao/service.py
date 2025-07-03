"""DAO webhook service implementation."""

from app.lib.logger import configure_logger
from app.services.integrations.webhooks.base import WebhookService
from app.services.integrations.webhooks.dao.handler import DAOHandler
from app.services.integrations.webhooks.dao.parser import DAOParser


class DAOService(WebhookService):
    """Service for handling DAO creation webhooks.

    This service coordinates parsing and handling of DAO webhook payloads
    for creating DAOs, extensions, and tokens.
    """

    def __init__(self):
        """Initialize the DAO service with parser and handler components."""
        parser = DAOParser()
        handler = DAOHandler()
        super().__init__(parser=parser, handler=handler)
        self.logger = configure_logger(self.__class__.__name__)
