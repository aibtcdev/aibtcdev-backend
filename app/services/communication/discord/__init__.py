"""
Discord service package for sending messages to Discord channels via webhooks.
"""

from app.services.communication.discord.discord_factory import create_discord_service
from app.services.communication.discord.discord_service import DiscordService

__all__ = ["DiscordService", "create_discord_service"]
