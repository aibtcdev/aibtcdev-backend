"""Enhanced startup service with auto-discovery and comprehensive monitoring."""

import asyncio
import signal
import sys
from typing import Any, Dict, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import config
from app.lib.logger import configure_logger
from app.services.communication.telegram_bot_service import start_application
from app.services.infrastructure.job_management.auto_discovery import (
    discover_and_register_tasks,
)
from app.services.infrastructure.job_management.job_manager import JobManager
from app.services.infrastructure.job_management.monitoring import (
    MetricsCollector,
    SystemMetrics,
)

logger = configure_logger(__name__)

# Global enhanced job manager instance
job_manager: Optional[JobManager] = None
shutdown_event = asyncio.Event()
metrics_collector = MetricsCollector()
system_metrics = SystemMetrics()


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(
        "Shutdown signal received - initiating graceful shutdown",
        extra={"signal": signum, "event_type": "shutdown_signal"},
    )
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
            self.job_manager = JobManager()

            # Auto-discover and register all jobs (this populates JobRegistry)
            discover_and_register_tasks()

            # Get registered jobs from JobRegistry
            from app.services.infrastructure.job_management.decorators import (
                JobRegistry,
            )

            registered_jobs = JobRegistry.list_jobs()

            logger.info(
                "Enhanced job system initialized",
                extra={
                    "discovered_jobs": len(registered_jobs),
                    "event_type": "job_system_init",
                },
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to initialize enhanced job system",
                extra={"error": str(e), "event_type": "job_system_init_error"},
                exc_info=True,
            )
            return False

    async def start_bot(self) -> Any:
        """Start the Telegram bot in the background."""
        if not config.telegram.enabled:
            logger.info(
                "Telegram bot disabled - skipping initialization",
                extra={"event_type": "bot_disabled"},
            )
            return None

        try:
            self.bot_application = await start_application()
            logger.info(
                "Telegram bot started successfully", extra={"event_type": "bot_started"}
            )
            return self.bot_application
        except Exception as e:
            logger.error(
                "Failed to start Telegram bot",
                extra={"error": str(e), "event_type": "bot_start_error"},
                exc_info=True,
            )
            raise

    async def start_enhanced_job_system(self) -> None:
        """Start the enhanced job system."""
        if not await self.initialize_job_system():
            logger.error(
                "Enhanced job system initialization failed",
                extra={"event_type": "job_system_failed"},
            )
            raise RuntimeError("Job system initialization failed")

        # Schedule jobs with the scheduler
        logger.debug(
            "Attempting to schedule jobs with job manager",
            extra={"event_type": "job_scheduling"},
        )
        any_jobs_scheduled = self.job_manager.schedule_jobs(self.scheduler)
        if any_jobs_scheduled:
            # Start the scheduler
            logger.debug(
                "Starting APScheduler with scheduled jobs",
                extra={"event_type": "scheduler_starting"},
            )
            self.scheduler.start()
            logger.info(
                "Job scheduler started successfully",
                extra={"event_type": "scheduler_started"},
            )

            # Log scheduler status
            jobs = self.scheduler.get_jobs()
            logger.info(
                "APScheduler running with active job schedules",
                extra={"active_jobs": len(jobs), "event_type": "scheduler_status"},
            )
            for job in jobs:
                logger.debug(
                    "Scheduled job details",
                    extra={
                        "job_id": job.id,
                        "next_run": str(job.next_run_time)
                        if job.next_run_time
                        else None,
                        "event_type": "job_schedule_detail",
                    },
                )
        else:
            logger.warning(
                "No jobs were scheduled - scheduler will not be started",
                extra={"event_type": "no_jobs_scheduled"},
            )

        # Start the job executor
        logger.debug(
            "Starting job executor for background processing",
            extra={"event_type": "executor_starting"},
        )
        await self.job_manager.start_executor()
        executor_stats = self.job_manager.get_executor_stats()
        logger.info(
            "Enhanced job executor started",
            extra={
                "worker_count": executor_stats.get("worker_count", 0),
                "event_type": "executor_started",
            },
        )

        # Start system metrics collection
        logger.debug(
            "Starting system metrics monitoring",
            extra={"event_type": "metrics_starting"},
        )
        await system_metrics.start_monitoring()
        logger.info(
            "System metrics monitoring started", extra={"event_type": "metrics_started"}
        )

    async def init_background_tasks(self) -> asyncio.Task:
        """Initialize all enhanced background tasks."""
        logger.info(
            "Starting Enhanced AIBTC Background Services",
            extra={"event_type": "service_startup"},
        )

        try:
            # Start enhanced job system
            await self.start_enhanced_job_system()

            # Start bot if enabled
            await self.start_bot()

            logger.info(
                "All enhanced background services started successfully",
                extra={"event_type": "service_startup_complete"},
            )
            # Return a completed task since we don't have a cleanup task anymore
            return asyncio.create_task(asyncio.sleep(0))

        except Exception as e:
            logger.error(
                "Failed to start background services",
                extra={"error": str(e), "event_type": "service_startup_error"},
                exc_info=True,
            )
            raise

    async def shutdown(self) -> None:
        """Enhanced cleanup and shutdown with graceful task termination."""
        logger.info(
            "Initiating enhanced shutdown sequence",
            extra={"event_type": "shutdown_start"},
        )

        try:
            # Stop system metrics collection
            if system_metrics:
                await system_metrics.stop_monitoring()
                logger.info(
                    "System metrics collection stopped",
                    extra={"event_type": "metrics_stopped"},
                )

            # Stop the scheduler
            if self.scheduler and self.scheduler.running:
                self.scheduler.shutdown()
                logger.info(
                    "Job scheduler stopped", extra={"event_type": "scheduler_stopped"}
                )

            # Gracefully shutdown enhanced job manager
            if self.job_manager:
                logger.debug(
                    "Stopping enhanced job manager",
                    extra={"event_type": "job_manager_stopping"},
                )
                await self.job_manager.stop_executor()
                logger.info(
                    "Enhanced job manager stopped successfully",
                    extra={"event_type": "job_manager_stopped"},
                )

            # Stop bot
            if self.bot_application:
                logger.debug(
                    "Stopping Telegram bot", extra={"event_type": "bot_stopping"}
                )
                # Add any necessary bot shutdown code here
                logger.info("Telegram bot stopped", extra={"event_type": "bot_stopped"})

        except Exception as e:
            logger.error(
                "Error during enhanced shutdown",
                extra={"error": str(e), "event_type": "shutdown_error"},
                exc_info=True,
            )

        logger.info(
            "Enhanced shutdown complete", extra={"event_type": "shutdown_complete"}
        )

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
        health_data = self.job_manager.get_system_health()
        system_health = system_metrics.get_current_metrics()

        return {
            "status": health_data["status"],
            "message": "Enhanced job system running",
            "jobs": {
                "running": health_data["executor"]["running"],
                "registered": health_data["tasks"]["total_registered"],
                "enabled": health_data["tasks"]["enabled"],
                "disabled": health_data["tasks"]["disabled"],
                "total_executions": health_data["metrics"]["total_executions"],
            },
            "system": {
                "cpu_usage": system_health.get("cpu_usage", 0),
                "memory_usage": system_health.get("memory_usage", 0),
                "disk_usage": system_health.get("disk_usage", 0),
            },
            "uptime": health_data.get("uptime_seconds", 0),
            "last_updated": system_health.get("timestamp"),
            "version": "2.0-enhanced",
            "services": {
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

        logger.info(
            "Enhanced AIBTC services running - Press Ctrl+C to stop",
            extra={"event_type": "services_running"},
        )
        return cleanup_task

    except Exception as e:
        logger.error(
            "Failed to start enhanced services",
            extra={"error": str(e), "event_type": "services_start_error"},
            exc_info=True,
        )
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
        logger.info(
            "Received keyboard interrupt", extra={"event_type": "keyboard_interrupt"}
        )
    except Exception as e:
        logger.error(
            "Critical error in standalone mode",
            extra={"error": str(e), "event_type": "critical_error"},
            exc_info=True,
        )
        sys.exit(1)
    finally:
        await shutdown()


if __name__ == "__main__":
    asyncio.run(run_standalone())
