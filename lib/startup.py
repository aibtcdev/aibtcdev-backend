import asyncio
import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from lib.logger import configure_logger
from lib.websocket_manager import manager
from services.bot import BOT_ENABLED, start_application
from services.runner import execute_runner_job
from services.schedule import sync_schedules
from services.twitter import execute_twitter_job

logger = configure_logger(__name__)

# Initialize scheduler with environment-controlled settings
scheduler = AsyncIOScheduler()

# Environment variables for services
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
AIBTC_TWEET_RUNNER_ENABLED = (
    os.getenv("AIBTC_TWEET_RUNNER_ENABLED", "false").lower() == "true"
)
AIBTC_TWEET_RUNNER_INTERVAL_SECONDS = int(
    os.getenv("AIBTC_TWEET_RUNNER_INTERVAL_SECONDS", 30)
)


async def start_websocket_cleanup():
    """Start the WebSocket cleanup task."""
    try:
        await manager.start_cleanup_task()
    except Exception as e:
        logger.error(f"Error starting WebSocket cleanup task: {str(e)}")


async def start_bot():
    """Start the Telegram bot in the background."""
    if not BOT_ENABLED:
        logger.info("Telegram bot disabled. Skipping initialization.")
        return None

    try:
        application = await start_application()
        logger.info("Bot started successfully")
        return application
    except Exception as e:
        logger.error(f"Failed to start Telegram bot: {e}")
        raise


def init_scheduler():
    """Initialize and start the scheduler with configured jobs."""
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
            args=["dao"],
        )
        logger.info(
            f"DAO runner service started with interval of {AIBTC_DAO_RUNNER_INTERVAL_SECONDS} seconds"
        )
    else:
        logger.info("DAO runner service is disabled")

    if AIBTC_TWEET_RUNNER_ENABLED:
        scheduler.add_job(
            execute_runner_job,
            "interval",
            seconds=AIBTC_TWEET_RUNNER_INTERVAL_SECONDS,
            args=["tweet"],
        )
        logger.info(
            f"Tweet runner service started with interval of {AIBTC_TWEET_RUNNER_INTERVAL_SECONDS} seconds"
        )
    else:
        logger.info("Tweet runner service is disabled")

    if any(
        [
            AIBTC_TWITTER_ENABLED,
            AIBTC_SCHEDULE_SYNC_ENABLED,
            AIBTC_DAO_RUNNER_ENABLED,
            AIBTC_TWEET_RUNNER_ENABLED,
        ]
    ):
        logger.info("Starting scheduler")
        scheduler.start()
        logger.info("Scheduler started")
    else:
        logger.info("Scheduler is disabled")


async def init_background_tasks():
    """Initialize all background tasks."""
    # Initialize scheduler
    init_scheduler()

    # Start websocket cleanup task
    cleanup_task = asyncio.create_task(start_websocket_cleanup())

    # Start bot if enabled
    await start_bot()

    # Return the cleanup task for management
    return cleanup_task
