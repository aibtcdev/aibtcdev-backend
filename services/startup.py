"""Enhanced startup service with auto-discovery and comprehensive monitoring."""

import asyncio
import signal
import sys
from typing import Any, Dict, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import config
from lib.logger import configure_logger
from services.bot import start_application
from services.runner.auto_discovery import discover_and_register_jobs
from services.runner.job_manager import JobManager
from services.runner.monitoring import JobMetrics, SystemMetrics
from services.websocket import websocket_manager

logger = configure_logger(__name__)

# Global enhanced job manager instance
job_manager: Optional[JobManager] = None
shutdown_event = asyncio.Event()
metrics_collector = JobMetrics()
system_metrics = SystemMetrics()


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_event.set()


class EnhancedStartupService:
    """Enhanced service to manage application startup with auto-discovery and monitoring."""

    def __init__(self, scheduler: Optional[AsyncIOScheduler] = None):
        self.scheduler = scheduler or AsyncIOScheduler()
        self.cleanup_task: Optional[asyncio.Task] = None
        self.bot_application: Optional[Any] = None
        self.job_manager: Optional[JobManager] = None

    async def initialize_job_system(self):
        """Initialize the enhanced job system with auto-discovery."""
        try:
            # Initialize enhanced job manager
            self.job_manager = JobManager(
                metrics_collector=metrics_collector, system_metrics=system_metrics
            )

            # Auto-discover and register all jobs
            discovered_jobs = await discover_and_register_jobs()

            for job_type, job_class in discovered_jobs.items():
                try:
                    # Create job instance
                    job_instance = job_class()
                    self.job_manager.register_task(job_instance)
                    logger.info(f"Registered job: {job_type} ({job_class.__name__})")
                except Exception as e:
                    logger.error(
                        f"Failed to register job {job_type}: {e}", exc_info=True
                    )

            logger.info(
                f"Enhanced job system initialized with {len(discovered_jobs)} jobs"
            )
            return True

        except Exception as e:
            logger.error(
                f"Failed to initialize enhanced job system: {e}", exc_info=True
            )
            return False

    async def start_websocket_cleanup(self) -> None:
        """Start the WebSocket cleanup task."""
        try:
            await websocket_manager.start_cleanup_task()
            logger.info("WebSocket cleanup task started")
        except Exception as e:
            logger.error(f"Error starting WebSocket cleanup task: {str(e)}")
            raise

    async def start_bot(self) -> Any:
        """Start the Telegram bot in the background."""
        if not config.telegram.enabled:
            logger.info("Telegram bot disabled. Skipping initialization.")
            return None

        try:
            self.bot_application = await start_application()
            logger.info("Telegram bot started successfully")
            return self.bot_application
        except Exception as e:
            logger.error(f"Failed to start Telegram bot: {e}")
            raise

    async def start_enhanced_job_system(self) -> None:
        """Start the enhanced job system."""
        if not await self.initialize_job_system():
            logger.error("Failed to initialize enhanced job system")
            raise RuntimeError("Job system initialization failed")

        # Start the enhanced job manager with monitoring
        await self.job_manager.start()
        logger.info("Enhanced job manager started successfully")
        logger.info(f"Registered {len(self.job_manager.task_registry)} tasks")

        # Start system metrics collection
        await system_metrics.start_monitoring()
        logger.info("System metrics monitoring started")

    async def init_background_tasks(self) -> asyncio.Task:
        """Initialize all enhanced background tasks."""
        logger.info("Starting Enhanced AIBTC Background Services...")

        try:
            # Start enhanced job system
            await self.start_enhanced_job_system()

            # Start websocket cleanup task
            self.cleanup_task = asyncio.create_task(self.start_websocket_cleanup())

            # Start bot if enabled
            await self.start_bot()

            logger.info("All enhanced background services started successfully")
            return self.cleanup_task

        except Exception as e:
            logger.error(f"Failed to start background services: {e}", exc_info=True)
            raise

    async def shutdown(self) -> None:
        """Enhanced cleanup and shutdown with graceful task termination."""
        logger.info("Initiating enhanced shutdown sequence...")

        try:
            # Stop system metrics collection
            if system_metrics:
                await system_metrics.stop_monitoring()
                logger.info("System metrics collection stopped")

            # Gracefully shutdown enhanced job manager
            if self.job_manager:
                logger.info("Stopping enhanced job manager...")
                await self.job_manager.stop()
                logger.info("Enhanced job manager stopped successfully")

                # Log final metrics
                final_metrics = self.job_manager.get_comprehensive_metrics()
                logger.info(f"Final job metrics: {final_metrics}")

            # Stop websocket cleanup
            if self.cleanup_task:
                self.cleanup_task.cancel()
                try:
                    await self.cleanup_task
                except asyncio.CancelledError:
                    pass
                logger.info("WebSocket cleanup task stopped")

            # Stop bot
            if self.bot_application:
                logger.info("Stopping Telegram bot...")
                # Add any necessary bot shutdown code here
                logger.info("Telegram bot stopped")

        except Exception as e:
            logger.error(f"Error during enhanced shutdown: {e}", exc_info=True)

        logger.info("Enhanced shutdown complete")

    def get_health_status(self) -> Dict:
        """Get comprehensive health status of the enhanced startup service."""
        if not self.job_manager:
            return {
                "status": "unhealthy",
                "message": "Enhanced job manager not initialized",
                "jobs": {"running": 0, "registered": 0, "failed": 0},
                "system": {},
                "uptime": 0,
            }

        # Get comprehensive health data
        health_data = self.job_manager.get_health_status()
        system_health = system_metrics.get_current_metrics()

        return {
            "status": health_data["status"],
            "message": health_data["message"],
            "jobs": {
                "running": health_data["running_jobs"],
                "registered": health_data["registered_tasks"],
                "failed": health_data.get("failed_jobs", 0),
                "completed": health_data.get("completed_jobs", 0),
                "total_executions": health_data.get("total_executions", 0),
            },
            "system": {
                "cpu_usage": system_health.get("cpu_usage", 0),
                "memory_usage": system_health.get("memory_usage", 0),
                "disk_usage": system_health.get("disk_usage", 0),
            },
            "uptime": health_data.get("uptime", 0),
            "last_updated": health_data.get("last_updated"),
            "version": "2.0-enhanced",
            "services": {
                "websocket_cleanup": self.cleanup_task is not None
                and not self.cleanup_task.done(),
                "telegram_bot": self.bot_application is not None,
                "job_manager": self.job_manager is not None
                and self.job_manager.is_running,
            },
        }

    def get_job_metrics(self) -> Dict:
        """Get detailed job execution metrics."""
        if not self.job_manager:
            return {"error": "Enhanced job manager not available"}

        return self.job_manager.get_comprehensive_metrics()

    def get_system_metrics(self) -> Dict:
        """Get current system performance metrics."""
        return system_metrics.get_current_metrics()

    def trigger_job(self, job_type: str) -> Dict:
        """Manually trigger a specific job type."""
        if not self.job_manager:
            return {"error": "Enhanced job manager not available"}

        return self.job_manager.trigger_job(job_type)


# Global enhanced instance for convenience
startup_service = EnhancedStartupService()


# Enhanced convenience functions that use the global instance
async def run() -> asyncio.Task:
    """Initialize all enhanced background tasks using the global startup service."""
    global job_manager

    # Setup signal handlers for standalone mode
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        cleanup_task = await startup_service.init_background_tasks()
        job_manager = startup_service.job_manager

        logger.info("Enhanced AIBTC services running. Press Ctrl+C to stop.")
        return cleanup_task

    except Exception as e:
        logger.error(f"Failed to start enhanced services: {e}", exc_info=True)
        raise


async def shutdown() -> None:
    """Shutdown all enhanced services using the global startup service."""
    await startup_service.shutdown()


# Enhanced health check functions
def get_health_status() -> Dict:
    """Get comprehensive health status."""
    return startup_service.get_health_status()


def get_job_metrics() -> Dict:
    """Get detailed job execution metrics."""
    return startup_service.get_job_metrics()


def get_system_metrics() -> Dict:
    """Get current system performance metrics."""
    return startup_service.get_system_metrics()


def trigger_job(job_type: str) -> Dict:
    """Manually trigger a specific job type."""
    return startup_service.trigger_job(job_type)


# Enhanced standalone mode for direct execution
async def run_standalone():
    """Run the enhanced startup service in standalone mode."""
    try:
        await run()

        # Wait for shutdown signal
        await shutdown_event.wait()

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Critical error in standalone mode: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await shutdown()


if __name__ == "__main__":
    asyncio.run(run_standalone())
