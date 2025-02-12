"""GitHub webhook implementation."""

from .base import WebhookHandler, WebhookParser, WebhookService
from pydantic import BaseModel
from typing import Any, Dict


class GitHubWebhookData(BaseModel):
    """Model for GitHub webhook data."""

    action: str
    repository: Dict[str, Any]
    sender: Dict[str, Any]


class GitHubParser(WebhookParser):
    """Parser for GitHub webhook payloads."""

    def parse(self, raw_data: Dict[str, Any]) -> GitHubWebhookData:
        """Parse GitHub webhook data."""
        return GitHubWebhookData(**raw_data)


class GitHubHandler(WebhookHandler):
    """Handler for GitHub webhook events."""

    async def handle(self, parsed_data: GitHubWebhookData) -> Dict[str, Any]:
        """Handle GitHub webhook data."""
        try:
            self.logger.info(
                f"Processing GitHub webhook with action: {parsed_data.action}"
            )

            # Add your GitHub webhook handling logic here
            # For example, handling repository events, issue events, etc.

            return {
                "success": True,
                "message": f"Successfully processed GitHub webhook action: {parsed_data.action}",
                "data": {
                    "action": parsed_data.action,
                    "repository": parsed_data.repository["full_name"],
                    "sender": parsed_data.sender["login"],
                },
            }

        except Exception as e:
            self.logger.error(f"Error handling GitHub webhook: {str(e)}", exc_info=True)
            raise


class GitHubService(WebhookService):
    """Service for handling GitHub webhooks."""

    def __init__(self):
        super().__init__(parser=GitHubParser(), handler=GitHubHandler())
