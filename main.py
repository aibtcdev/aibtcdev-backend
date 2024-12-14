from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from api import crew
from api import chat
from services.cron import execute_cron_job
import os
from services.bot import start_application, BOT_ENABLED
import logging

# Load environment variables first
load_dotenv()

# Configure module logger
logger = logging.getLogger('uvicorn.error')

# Initialize scheduler with environment-controlled cron settings
scheduler = AsyncIOScheduler()
CRON_ENABLED = os.getenv('CRON_ENABLED', 'true').lower() == 'true'
CRON_INTERVAL_SECONDS = int(os.getenv('CRON_INTERVAL_SECONDS', 3600))

if CRON_ENABLED:
    scheduler.add_job(execute_cron_job, "interval", seconds=CRON_INTERVAL_SECONDS)
    scheduler.start()
    logger.info(f"Cron scheduler started with interval of {CRON_INTERVAL_SECONDS} seconds")
else:
    logger.info("Cron scheduler is disabled")

app = FastAPI()

# Setup CORS origins
cors_origins = [
    "https://sprint.aibtc.dev",
    "https://sprint-faster.aibtc.dev",
    "https://*.aibtcdev-frontend.pages.dev" # Cloudflare preview deployments
    "http://localhost:3000",  # Local development
]

# Setup middleware to allow CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=3600,  # Cache preflight requests for 1 hour
)


async def start_bot():
    """Start the Telegram bot in the background."""
    try:
        application = await start_application()
        return application
    except Exception as e:
        logger.error(f"Failed to start Telegram bot: {e}")
        raise


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    try:
        # Start the bot if enabled
        if BOT_ENABLED:
            await start_bot()
            logger.info("Bot started successfully")
        else:
            logger.info("Telegram bot disabled. Skipping initialization.")
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise e


# Lightweight health check endpoint
@app.get("/")
async def health():
    return {"status": "healthy"}


app.include_router(crew.router)
app.include_router(chat.router)
