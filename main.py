import logging
import os
from api import chat, tools, webhooks
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from services.bot import BOT_ENABLED, start_application
from services.runner import execute_runner_job
from services.schedule import sync_schedules
from services.twitter import execute_twitter_job

# Load environment variables first
load_dotenv()

# Configure module logger
logger = logging.getLogger("uvicorn.error")

# Initialize scheduler with environment-controlled settings
scheduler = AsyncIOScheduler()
AIBTC_TWITTER_ENABLED = os.getenv("AIBTC_TWITTER_ENABLED", "false").lower() == "true"
AIBTC_TWITTER_INTERVAL_SECONDS = int(os.getenv("AIBTC_TWITTER_INTERVAL_SECONDS", 120))
AIBTC_SCHEDULE_SYNC_ENABLED = (
    os.getenv("AIBTC_SCHEDULE_SYNC_ENABLED", "false").lower() == "true"
)
AIBTC_SCHEDULE_SYNC_INTERVAL_SECONDS = int(
    os.getenv("AIBTC_SCHEDULE_SYNC_INTERVAL_SECONDS", 60)
)
AIBTC_DAO_RUNNER_ENABLED = (
    os.getenv("AIBTC_DAO_RUNNER_ENABLED", "false").lower() == "true"
)
AIBTC_DAO_RUNNER_INTERVAL_SECONDS = int(
    os.getenv("AIBTC_DAO_RUNNER_INTERVAL_SECONDS", 30)
)

if AIBTC_TWITTER_ENABLED:
    scheduler.add_job(
        execute_twitter_job, "interval", seconds=AIBTC_TWITTER_INTERVAL_SECONDS
    )
    logger.info(
        f"Twitter service started with interval of {AIBTC_TWITTER_INTERVAL_SECONDS} seconds"
    )
else:
    logger.info("Twitter service disabled")

if AIBTC_SCHEDULE_SYNC_ENABLED:
    scheduler.add_job(
        sync_schedules,
        "interval",
        args=[scheduler],
        seconds=AIBTC_SCHEDULE_SYNC_INTERVAL_SECONDS,
    )
    logger.info(
        f"Schedule sync service started with interval of {AIBTC_SCHEDULE_SYNC_INTERVAL_SECONDS} seconds"
    )
else:
    logger.info("Schedule sync service is disabled")

if AIBTC_DAO_RUNNER_ENABLED:
    scheduler.add_job(
        execute_runner_job,
        "interval",
        seconds=AIBTC_DAO_RUNNER_INTERVAL_SECONDS,
    )
    logger.info(
        f"DAO runner service started with interval of {AIBTC_DAO_RUNNER_INTERVAL_SECONDS} seconds"
    )
else:
    logger.info("DAO runner service is disabled")

if AIBTC_TWITTER_ENABLED or AIBTC_SCHEDULE_SYNC_ENABLED or AIBTC_DAO_RUNNER_ENABLED:
    logger.info("Starting scheduler")
    scheduler.start()
    logger.info("Scheduler started")
else:
    logger.info("Scheduler is disabled")

app = FastAPI()

# Setup CORS origins
cors_origins = [
    "https://sprint.aibtc.dev",
    "https://sprint-faster.aibtc.dev",
    "https://*.aibtcdev-frontend.pages.dev",  # Cloudflare preview deployments
    "http://localhost:3000",  # Local development
    "https://staging.aibtc.chat",
    "https://app.aibtc.dev",
    "https://aibtc.dev",
    "https://app-staging.aibtc.dev",
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


app.include_router(tools.router)
app.include_router(chat.router)
app.include_router(webhooks.router)
