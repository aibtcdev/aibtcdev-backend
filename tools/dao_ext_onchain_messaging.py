from typing import Any, Dict, Optional, Type
from uuid import UUID

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from tools.bun import BunScriptRunner


class SendMessageInput(BaseModel):
    """Input schema for sending an onchain message."""

    messaging_contract: str = Field(
        ...,
        description="Contract principal of the messaging contract for the DAO",
        example="ST3YT0XW92E6T2FE59B2G5N2WNNFSBZ6MZKQS5D18.dao-onchain-messaging",
    )
    message: str = Field(..., description="Message to send")


class SendMessageTool(BaseTool):
    name: str = "dao_messaging_send"
    description: str = (
        "Send a message through the DAO's onchain messaging system. "
        "Messages are stored permanently on the blockchain and can be viewed by anyone."
    )
    args_schema: Type[BaseModel] = SendMessageInput
    return_direct: bool = False
    wallet_id: Optional[UUID] = None

    def __init__(self, wallet_id: Optional[UUID] = None, **kwargs):
        super().__init__(**kwargs)
        self.wallet_id = wallet_id

    def _deploy(
        self,
        messaging_contract: str,
        message: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to send a message."""
        if self.wallet_id is None:
            return {"success": False, "message": "Wallet ID is required", "data": None}

        args = [
            messaging_contract,
            message,
        ]

        return BunScriptRunner.bun_run(
            self.wallet_id,
            "aibtc-dao/extensions/onchain-messaging/public",
            "send-message.ts",
            *args,
        )

    def _run(
        self,
        messaging_contract: str,
        message: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the tool to send a message."""
        return self._deploy(messaging_contract, message, **kwargs)

    async def _arun(
        self,
        messaging_contract: str,
        message: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async version of the tool."""
        return self._deploy(messaging_contract, message, **kwargs)
