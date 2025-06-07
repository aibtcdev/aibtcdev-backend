from config import DiscordConfig
from lib.logger import configure_logger
from services.discord.discord_service import DiscordService

logger = configure_logger(__name__)


def create_discord_service(webhook_url=None):
    """
    Create and initialize a Discord service using configuration.

    Args:
        webhook_url (str, optional): Override the webhook URL from config.

    Returns:
        DiscordService or None: Initialized Discord service or None if configuration is missing.
    """
    # If webhook_url is not provided, get it from config (default to passed webhook)
    if webhook_url is None:
        discord_config = DiscordConfig()
        webhook_url = discord_config.webhook_url_passed

    if not webhook_url:
        logger.warning("Discord webhook URL is not configured")
        return None

    try:
        service = DiscordService(
            webhook_url=webhook_url, bot_name="AIBTC Bot", avatar_url=None
        )
        service.initialize()
        logger.info("Discord service created and initialized successfully")
        return service
    except Exception as e:
        logger.error(f"Failed to create Discord service: {str(e)}")
        return None
