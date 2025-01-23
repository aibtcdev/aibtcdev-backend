from backend.models import UUID
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from services.bot import send_message_to_user_sync
from typing import Any, Dict, Optional, Type


class SendTelegramNotificationInput(BaseModel):
    """Input schema for SendTelegramNotification tool."""

    message: str = Field(
        ...,
        description="Notification to send to Telegram",
    )


class SendTelegramNotificationTool(BaseTool):
    name: str = "send_telegram_notification"
    description: str = "Send a telegram notification message to myself"
    args_schema: Type[BaseModel] = SendTelegramNotificationInput
    return_direct: bool = False
    profile_id: Optional[UUID] = None

    def __init__(
        self,
        profile_id: Optional[UUID] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.profile_id = profile_id

    def _deploy(
        self,
        message: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to add a scheduled task."""
        if self.profile_id is None:
            raise ValueError("Profile ID is required")
        try:
            response = send_message_to_user_sync(
                profile_id=self.profile_id, message=message
            )
            return response
        except Exception as e:
            return {"error": str(e)}

    def _run(
        self,
        message: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Sync version of the tool."""
        return self._deploy(message, **kwargs)

    async def _arun(
        self,
        message: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(message, **kwargs)
