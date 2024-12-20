import os
from db.factory import db
from dotenv import load_dotenv
from lib.logger import configure_logger
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Load environment variables
load_dotenv()

# Configure logger
logger = configure_logger(__name__)

# List of admin user IDs (you can add Telegram user IDs here)
ADMIN_IDS = [
    2051556689,
]


def is_admin(user_id: int) -> bool:
    """Check if a user is an admin."""
    return user_id in ADMIN_IDS


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    user_id = update.effective_user.id

    try:
        # Get profile_id from command arguments
        if not context.args:
            await update.message.reply_text(
                "Please use the registration link provided to start the bot."
            )
            return

        telegram_user_id = context.args[0]

        # Check if user exists with this profile_id
        result = db.get_telegram_user(telegram_user_id)

        if not result.data:
            await update.message.reply_text(
                "Invalid registration link. Please use the correct link to register."
            )
            return

        # Update existing record with Telegram user information
        user_data = {
            "telegram_user_id": str(user_id),
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_registered": True,
        }

        # Update the user data for the existing profile_id
        result = db.update_telegram_user(telegram_user_id, user_data)

        is_user_admin = is_admin(user_id)
        admin_status = "You are an admin!" if is_user_admin else "You are not an admin."

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


async def help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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


async def send_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message to a specific user."""
    if not is_admin(update.effective_user.id):
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
        # Query for the user
        result = db.get_telegram_user_by_username(username)

        if not result.data:
            await update.message.reply_text(
                f"Registered user with username {username} not found."
            )
            return

        chat_id = result.data[0]["telegram_user_id"]
        bot_app = await get_bot()
        if bot_app:
            await bot_app.bot.send_message(chat_id=chat_id, text=message)
            await update.message.reply_text(f"Message sent to {username} successfully!")
        else:
            await update.message.reply_text("Failed to send message.")
    except Exception as e:
        logger.error(f"Error in send_message: {str(e)}")
        await update.message.reply_text(f"Failed to send message: {str(e)}")


async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all registered users."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to list users.")
        return

    try:
        # Query for all registered users
        result = db.get_all_registered_telegram_users()

        if not result.data:
            await update.message.reply_text("No registered users found.")
            return

        user_list = "\n".join(
            [
                f"{user['username'] or 'No username'}: {user['telegram_user_id']}"
                for user in result.data
            ]
        )
        await update.message.reply_text(f"Registered users:\n{user_list}")
    except Exception as e:
        logger.error(f"Error in list_users: {str(e)}")
        await update.message.reply_text("Failed to retrieve user list.")


async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all admin users."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to list admins.")
        return

    admin_list = "\n".join([str(admin_id) for admin_id in ADMIN_IDS])
    await update.message.reply_text(f"Admin users:\n{admin_list}")


async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add a new admin user."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to add admins.")
        return

    if not context.args:
        await update.message.reply_text(
            "Please provide a user ID. Usage: /add_admin <user_id>"
        )
        return

    try:
        new_admin_id = int(context.args[0])
        if new_admin_id not in ADMIN_IDS:
            ADMIN_IDS.append(new_admin_id)
            await update.message.reply_text(
                f"Successfully added user ID {new_admin_id} as admin."
            )
        else:
            await update.message.reply_text("This user is already an admin.")
    except ValueError:
        await update.message.reply_text(
            "Please provide a valid user ID (numbers only)."
        )


# Global bot instance and settings
_bot_app = None
BOT_ENABLED = os.getenv("AIBTC_TELEGRAM_BOT_ENABLED", "false").lower() == "true"


async def get_bot():
    """Get the global bot instance."""
    if not BOT_ENABLED:
        return None

    global _bot_app
    if _bot_app is None:
        _bot_app = (
            Application.builder().token(os.getenv("AIBTC_TELEGRAM_BOT_TOKEN")).build()
        )
        await _bot_app.initialize()
        await _bot_app.start()
    return _bot_app


async def send_message_to_user(profile_id: str, message: str) -> bool:
    """Send a message to a user by their profile ID."""
    if not BOT_ENABLED:
        logger.info(
            f"Telegram bot disabled. Would have sent to {profile_id}: {message}"
        )
        return False

    try:
        # Query for the user
        result = db.get_telegram_user_by_profile(profile_id)

        if not result.data:
            logger.warning(
                f"No registered Telegram user found for profile {profile_id}"
            )
            return False

        chat_id = result.data[0]["telegram_user_id"]
        bot_app = await get_bot()
        if bot_app:
            await bot_app.bot.send_message(chat_id=chat_id, text=message)
            return True
        return False
    except Exception as e:
        logger.error(f"Error in send_message_to_user: {str(e)}")
        return False


async def start_application():
    """Start the bot."""
    if not BOT_ENABLED:
        logger.info("Telegram bot disabled. Skipping initialization.")
        return None

    global _bot_app
    if _bot_app is not None:
        return _bot_app

    # Create the Application and pass it your bot's token
    _bot_app = (
        Application.builder().token(os.getenv("AIBTC_TELEGRAM_BOT_TOKEN")).build()
    )

    # Add command handlers
    _bot_app.add_handler(CommandHandler("start", start))
    _bot_app.add_handler(CommandHandler("help", help))
    _bot_app.add_handler(CommandHandler("send", send_message))
    _bot_app.add_handler(CommandHandler("list", list_users))
    _bot_app.add_handler(CommandHandler("add_admin", add_admin))
    _bot_app.add_handler(CommandHandler("list_admins", list_admins))

    # Initialize and start the bot
    await _bot_app.initialize()
    await _bot_app.start()

    # Start polling
    await _bot_app.updater.start_polling(allowed_updates=Update.ALL_TYPES)

    return _bot_app
