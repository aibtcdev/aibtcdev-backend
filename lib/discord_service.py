# discord.py
import logging
import requests
from typing import Dict, Optional, Any
from lib.logger import configure_logger

# Configure logger
logger = configure_logger(__name__)


class DiscordService:
    def __init__(self, webhook_url: str, bot_name: Optional[str] = None, avatar_url: Optional[str] = None):
        """Initialize the Discord service with webhook URL and optional customization."""
        self.webhook_url = webhook_url
        self.bot_name = bot_name
        self.avatar_url = avatar_url
        self.initialized = False

    async def _ainitialize(self) -> None:
        self.initialize()

    def initialize(self) -> None:
        """Initialize the Discord service."""
        try:
            # Validate webhook URL
            if not self.webhook_url or not self.webhook_url.startswith("https://discord.com/api/webhooks/"):
                raise ValueError("Invalid Discord webhook URL")
            
            # Test the webhook with a simple request
            test_response = requests.get(self.webhook_url)
            if test_response.status_code != 200:
                raise Exception(f"Webhook validation failed with status code: {test_response.status_code}")
            
            self.initialized = True
            logger.info("Discord service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Discord service: {str(e)}")
            raise

    async def _asend_message(
        self, 
        content: str, 
        embeds: Optional[list] = None,
        tts: bool = False
    ) -> Dict[str, Any]:
        """
        Async wrapper for send_message method.
        
        Args:
            content: The message content
            embeds: Optional list of embed objects
            tts: Whether to send as text-to-speech message
            
        Returns:
            Response data if successful, error details if failed
        """
        return self.send_message(content, embeds, tts)

    def send_message(
        self, 
        content: str, 
        embeds: Optional[list] = None,
        tts: bool = False
    ) -> Dict[str, Any]:
        """
        Send a message to Discord via webhook.
        
        Args:
            content: The message content
            embeds: Optional list of embed objects
            tts: Whether to send as text-to-speech message
            
        Returns:
            Response data if successful, error details if failed
        """
        try:
            if not self.initialized:
                raise Exception("Discord service is not initialized")
            
            # Prepare payload
            payload = {
                "content": content,
                "tts": tts
            }
            
            # Add optional parameters if provided
            if self.bot_name:
                payload["username"] = self.bot_name
            
            if self.avatar_url:
                payload["avatar_url"] = self.avatar_url
                
            if embeds:
                payload["embeds"] = embeds
            
            # Send the message
            response = requests.post(self.webhook_url, json=payload)
            
            # Discord returns 204 No Content on success
            if response.status_code == 204:
                logger.info(f"Successfully sent Discord message: {content[:20]}...")
                return {"success": True, "status_code": 204}
            else:
                error_msg = f"Failed to send Discord message. Status code: {response.status_code}"
                if response.text:
                    error_msg += f", Response: {response.text}"
                logger.error(error_msg)
                return {
                    "success": False, 
                    "status_code": response.status_code,
                    "error": response.text if response.text else "Unknown error"
                }
                
        except Exception as e:
            logger.error(f"Error sending Discord message: {str(e)}")
            return {"success": False, "error": str(e)}