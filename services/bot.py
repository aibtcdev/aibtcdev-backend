import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from urllib.parse import urlencode
from db.supabase_client import supabase

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

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
        result = supabase.table('telegram_users').select('*').eq('id', telegram_user_id).execute()
        
        if not result.data:
            await update.message.reply_text(
                "Invalid registration link. Please use the correct link to register."
            )
            return
            
        # Update existing record with Telegram user information
        user_data = {
            'telegram_user_id': str(user_id),
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_registered': True
        }
        
        # Update the user data for the existing profile_id
        result = supabase.table('telegram_users').update(user_data).eq('id', telegram_user_id).execute()
        
        is_user_admin = is_admin(user_id)
        admin_status = "You are an admin!" if is_user_admin else "You are not an admin."
        
        await update.message.reply_text(
            f'Hi {user.first_name}!\n'
            f'Your registration has been completed successfully!\n\n'
            f'{admin_status}'
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
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def send_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message to a specific user."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text('You are not authorized to send messages.')
        return

    if len(context.args) < 2:
        await update.message.reply_text('Please provide username and message. Usage: /send <username> <message>')
        return
        
    username = context.args[0]
    message = ' '.join(context.args[1:])
    
    try:
        # Query Supabase for the user
        result = supabase.table('telegram_users').select('telegram_user_id').eq('username', username).eq('is_registered', True).execute()
        
        if not result.data:
            await update.message.reply_text(f'Registered user with username {username} not found.')
            return
            
        chat_id = result.data[0]['telegram_user_id']
        await context.bot.send_message(chat_id=chat_id, text=message)
        await update.message.reply_text(f'Message sent to {username} successfully!')
    except Exception as e:
        logger.error(f"Error in send_message: {str(e)}")
        await update.message.reply_text(f'Failed to send message: {str(e)}')

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all registered users."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text('You are not authorized to list users.')
        return

    try:
        # Query Supabase for all registered users
        result = supabase.table('telegram_users').select('username,telegram_user_id').eq('is_registered', True).execute()
        
        if not result.data:
            await update.message.reply_text('No registered users found.')
            return
            
        user_list = '\n'.join([f"{user['username'] or 'No username'}: {user['telegram_user_id']}" for user in result.data])
        await update.message.reply_text(f'Registered users:\n{user_list}')
    except Exception as e:
        logger.error(f"Error in list_users: {str(e)}")
        await update.message.reply_text('Failed to retrieve user list.')

async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all admin users."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text('You are not authorized to list admins.')
        return

    admin_list = '\n'.join([str(admin_id) for admin_id in ADMIN_IDS])
    await update.message.reply_text(f'Admin users:\n{admin_list}')

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add a new admin user."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text('You are not authorized to add admins.')
        return

    if not context.args:
        await update.message.reply_text('Please provide a user ID. Usage: /add_admin <user_id>')
        return

    try:
        new_admin_id = int(context.args[0])
        if new_admin_id not in ADMIN_IDS:
            ADMIN_IDS.append(new_admin_id)
            await update.message.reply_text(f'Successfully added user ID {new_admin_id} as admin.')
        else:
            await update.message.reply_text('This user is already an admin.')
    except ValueError:
        await update.message.reply_text('Please provide a valid user ID (numbers only).')

async def start_application():
    """Start the bot."""
    # Create the Application and pass it your bot's token
    application = Application.builder().token(os.getenv('TELEGRAM_BOT_TOKEN')).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(CommandHandler("send", send_message))
    application.add_handler(CommandHandler("list", list_users))
    application.add_handler(CommandHandler("add_admin", add_admin))
    application.add_handler(CommandHandler("list_admins", list_admins))

    # Start the Bot
    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    return application