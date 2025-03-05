import asyncio
from typing import Any, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import config
from lib.logger import configure_logger
from lib.websocket_manager import manager
from services.bot import start_application
from services.runner import execute_runner_job
from services.runner.job_manager import JobManager
from services.schedule import sync_schedules
from services.twitter import execute_twitter_job

logger = configure_logger(__name__)


class StartupService:
    """Service to manage application startup and background tasks."""

    def __init__(self, scheduler: Optional[AsyncIOScheduler] = None):
        self.scheduler = scheduler or AsyncIOScheduler()
        self.cleanup_task: Optional[asyncio.Task] = None

    async def start_websocket_cleanup(self) -> None:
        """Start the WebSocket cleanup task."""
        try:
            await manager.start_cleanup_task()
        except Exception as e:
            logger.error(f"Error starting WebSocket cleanup task: {str(e)}")
            raise

    async def start_bot(self) -> Any:
        """Start the Telegram bot in the background."""
        if not config.telegram.enabled:
            logger.info("Telegram bot disabled. Skipping initialization.")
            return None

        try:
            application = await start_application()
            logger.info("Bot started successfully")
            return application
        except Exception as e:
            logger.error(f"Failed to start Telegram bot: {e}")
            raise

    def init_scheduler(self) -> None:
        """Initialize and start the scheduler with configured jobs."""
        # Use the JobManager to schedule all enabled jobs
        any_enabled = JobManager.schedule_jobs(self.scheduler)

        # Start the scheduler if any jobs are enabled
        if any_enabled:
            logger.info("Starting scheduler")
            self.scheduler.start()
            logger.info("Scheduler started")
        else:
            logger.info("Scheduler is disabled")

    async def init_background_tasks(self) -> asyncio.Task:
        """Initialize all background tasks."""
        # Initialize scheduler
        self.init_scheduler()

        # Start websocket cleanup task
        self.cleanup_task = asyncio.create_task(self.start_websocket_cleanup())

        # Start bot if enabled
        await self.start_bot()

        # Return the cleanup task for management
        return self.cleanup_task

    async def shutdown(self) -> None:
        """Shutdown all services gracefully."""
        logger.info("Shutting down services...")

        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler shutdown complete")

        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("Cleanup task shutdown complete")


# Global instance for convenience
startup_service = StartupService()


# Convenience functions that use the global instance
async def init_background_tasks() -> asyncio.Task:
    """Initialize all background tasks using the global startup service."""
    return await startup_service.init_background_tasks()


async def shutdown() -> None:
    """Shutdown all services using the global startup service."""
    await startup_service.shutdown()
