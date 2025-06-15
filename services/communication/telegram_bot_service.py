import asyncio
from dataclasses import dataclass
from typing import Optional, Set

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from backend.factory import backend
from backend.models import TelegramUserBase, TelegramUserFilter
from config import config
from lib.logger import configure_logger

logger = configure_logger(__name__)


@dataclass
class TelegramBotConfig:
    """Configuration for the Telegram bot."""

    token: str
    admin_ids: Set[int]
    is_enabled: bool

    @classmethod
    def from_env(cls) -> "TelegramBotConfig":
        """Create config from environment variables."""
        return cls(
            token=config.telegram.token,
            admin_ids=set([2051556689]),  # Default admin IDs
            is_enabled=config.telegram.enabled,
        )


class TelegramBotService:
    """Service class for handling Telegram bot operations."""

    def __init__(self, config: TelegramBotConfig):
        self.config = config
        self._app: Optional[Application] = None

    def is_admin(self, user_id: int) -> bool:
        """Check if a user is an admin."""
        return user_id in self.config.admin_ids

    async def start_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle the /start command."""
        if not update.effective_user:
            return

        user = update.effective_user
        user_id = user.id

        try:
            if not context.args:
                await update.message.reply_text(
                    "Please use the registration link provided to start the bot."
                )
                return

            telegram_user_id = context.args[0]
            result = backend.get_telegram_user(telegram_user_id)

            if not result:
                await update.message.reply_text(
                    "Invalid registration link. Please use the correct link to register."
                )
                return

            user_data = TelegramUserBase(
                telegram_user_id=str(user_id),
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                is_registered=True,
            )

            result = backend.update_telegram_user(
                telegram_user_id, update_data=user_data
            )
            is_user_admin = self.is_admin(user_id)
            admin_status = (
                "You are an admin!" if is_user_admin else "You are not an admin."
            )

            await update.message.reply_text(
                f"Hi {user.first_name}!\n"
                f"Your registration has been completed successfully!\n\n"
                f"{admin_status}"
            )

        except Exception as e:
            logger.error(f"Error in start command: {str(e)}")
            await update.message.reply_text(
                "Sorry, there was an error processing your registration. Please try again later."
            )

    async def help_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Show help information about the bot."""
        help_text = """
*Available Commands*

For All Users:
• /start <profile_id> - Start the bot and complete registration
• /help - Show this help message

For Admin Users:
• /send <username> <message> - Send a message to a registered user
• /list - List all registered users
• /list_admins - List all admin users
• /add_admin <user_id> - Add a new admin user
"""
        await update.message.reply_text(help_text, parse_mode="Markdown")

    async def send_message_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle the /send command."""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("You are not authorized to send messages.")
            return

        if len(context.args) < 2:
            await update.message.reply_text(
                "Please provide username and message. Usage: /send <username> <message>"
            )
            return

        username = context.args[0]
        message = " ".join(context.args[1:])

        try:
            result = backend.list_telegram_users(
                filters=TelegramUserFilter(username=username)
            )

            if not result:
                await update.message.reply_text(
                    f"Registered user with username {username} not found."
                )
                return

            chat_id = result[0].telegram_user_id
            if self._app:
                await self._app.bot.send_message(chat_id=chat_id, text=message)
                await update.message.reply_text(
                    f"Message sent to {username} successfully!"
                )
            else:
                await update.message.reply_text("Bot application not initialized.")
        except Exception as e:
            logger.error(f"Error in send_message: {str(e)}")
            await update.message.reply_text(f"Failed to send message: {str(e)}")

    async def list_users_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle the /list command."""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("You are not authorized to list users.")
            return

        try:
            result = backend.list_telegram_users()

            if not result:
                await update.message.reply_text("No registered users found.")
                return

            user_list = "\n".join(
                [
                    f"{user.username or 'No username'}: {user.telegram_user_id}"
                    for user in result
                ]
            )
            await update.message.reply_text(f"Registered users:\n{user_list}")
        except Exception as e:
            logger.error(f"Error in list_users: {str(e)}")
            await update.message.reply_text("Failed to retrieve user list.")

    async def list_admins_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle the /list_admins command."""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("You are not authorized to list admins.")
            return

        admin_list = "\n".join([str(admin_id) for admin_id in self.config.admin_ids])
        await update.message.reply_text(f"Admin users:\n{admin_list}")

    async def add_admin_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle the /add_admin command."""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("You are not authorized to add admins.")
            return

        if not context.args:
            await update.message.reply_text(
                "Please provide a user ID. Usage: /add_admin <user_id>"
            )
            return

        try:
            new_admin_id = int(context.args[0])
            if new_admin_id not in self.config.admin_ids:
                self.config.admin_ids.add(new_admin_id)
                await update.message.reply_text(
                    f"Successfully added user ID {new_admin_id} as admin."
                )
            else:
                await update.message.reply_text("This user is already an admin.")
        except ValueError:
            await update.message.reply_text(
                "Please provide a valid user ID (numbers only)."
            )

    async def send_message_to_user(self, profile_id: str, message: str) -> bool:
        """Send a message to a user by their profile ID."""
        if not self.config.is_enabled:
            logger.info(
                f"Telegram bot disabled. Would have sent to {profile_id}: {message}"
            )
            return False

        try:
            result = backend.list_telegram_users(
                filters=TelegramUserFilter(profile_id=profile_id)
            )

            if not result:
                logger.warning(
                    f"No registered Telegram user found for profile {profile_id}"
                )
                return False

            chat_id = result[0].telegram_user_id
            if self._app:
                await self._app.bot.send_message(chat_id=chat_id, text=message)
                return True
            return False
        except Exception as e:
            logger.error(f"Error in send_message_to_user: {str(e)}")
            return False

    def send_message_to_user_sync(self, profile_id: str, message: str) -> bool:
        """Synchronous version of send_message_to_user."""
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return loop.create_task(self.send_message_to_user(profile_id, message))
        return loop.run_until_complete(self.send_message_to_user(profile_id, message))

    async def initialize(self) -> None:
        """Initialize the bot application."""
        if not self.config.is_enabled:
            logger.info("Telegram bot disabled. Skipping initialization.")
            return

        if self._app is not None:
            return

        self._app = Application.builder().token(self.config.token).build()

        # Add command handlers
        self._app.add_handler(CommandHandler("start", self.start_command))
        self._app.add_handler(CommandHandler("help", self.help_command))
        self._app.add_handler(CommandHandler("send", self.send_message_command))
        self._app.add_handler(CommandHandler("list", self.list_users_command))
        self._app.add_handler(CommandHandler("add_admin", self.add_admin_command))
        self._app.add_handler(CommandHandler("list_admins", self.list_admins_command))

        # Initialize and start the bot
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(allowed_updates=Update.ALL_TYPES)

    async def shutdown(self) -> None:
        """Shutdown the bot application."""
        if self._app:
            await self._app.stop()
            await self._app.shutdown()
            self._app = None


# Global bot instance
_bot_service: Optional[TelegramBotService] = None


def get_bot_service() -> Optional[TelegramBotService]:
    """Get the global bot service instance."""
    global _bot_service
    if _bot_service is None:
        config = TelegramBotConfig.from_env()
        _bot_service = TelegramBotService(config)
    return _bot_service


async def start_application() -> Optional[Application]:
    """Start the Telegram bot application if enabled."""
    try:
        bot_service = get_bot_service()
        if bot_service:
            await bot_service.initialize()
            logger.info("Telegram bot started successfully")
            return bot_service._app
        return None
    except Exception as e:
        logger.error(f"Failed to start Telegram bot: {e}")
        return None
