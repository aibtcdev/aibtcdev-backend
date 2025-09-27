"""Enhanced Job Manager using the new job queue system."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from app.backend.factory import backend

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import config
from app.lib.logger import configure_logger

from .auto_discovery import get_task_summary
from .decorators import JobMetadata, JobRegistry
from .executor import get_executor
from .monitoring import get_metrics_collector, get_performance_monitor

logger = configure_logger(__name__)


@dataclass
class JobScheduleConfig:
    """Enhanced configuration for scheduled jobs."""

    job_type: str
    metadata: JobMetadata
    enabled: bool
    scheduler_id: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "job_type": self.job_type,
            "name": self.metadata.name,
            "description": self.metadata.description,
            "enabled": self.enabled,
            "interval_seconds": self.metadata.interval_seconds,
            "priority": str(self.metadata.priority),
            "max_retries": self.metadata.max_retries,
            "max_concurrent": self.metadata.max_concurrent,
            "requires_twitter": self.metadata.requires_twitter,
            "requires_discord": self.metadata.requires_discord,
            "requires_wallet": self.metadata.requires_wallet,
            "scheduler_id": self.scheduler_id,
        }


class JobManager:
    """Enhanced manager for scheduled jobs using the new system."""

    def __init__(self):
        self._scheduler: Optional[AsyncIOScheduler] = None
        self._executor = get_executor()
        self._metrics = get_metrics_collector()
        self._performance_monitor = get_performance_monitor()
        self._is_running = False

    @property
    def is_running(self) -> bool:
        """Check if the job manager is running."""
        return self._is_running

    def get_all_jobs(self) -> List[JobScheduleConfig]:
        """Get configurations for all registered jobs."""
        configs = []

        # Get all registered jobs from the new system
        registered_jobs = JobRegistry.list_jobs()

        for job_type, metadata in registered_jobs.items():
            # Check if job is enabled (can be overridden by config)
            enabled = self._is_job_enabled(job_type, metadata)

            config_item = JobScheduleConfig(
                job_type=str(job_type),
                metadata=metadata,
                enabled=enabled,
                scheduler_id=f"{job_type.value}_scheduler",
            )
            configs.append(config_item)

        return configs

    def _is_job_enabled(self, job_type, metadata: JobMetadata) -> bool:
        """Check if a job is enabled based on metadata and config overrides."""
        # First check the metadata default
        if not metadata.enabled:
            return False

        # Check for config overrides using dynamic approach
        job_type_str = str(job_type).lower()

        # Try config override with standard naming pattern
        config_attr = f"{job_type_str}_enabled"
        if hasattr(config.scheduler, config_attr):
            return getattr(config.scheduler, config_attr, metadata.enabled)

        # Try alternative naming pattern for backwards compatibility
        alt_config_attr = f"{job_type_str}_runner_enabled"
        if hasattr(config.scheduler, alt_config_attr):
            return getattr(config.scheduler, alt_config_attr, metadata.enabled)

        # Use metadata default if no config override found
        return metadata.enabled

    def _get_job_interval(self, job_type, metadata: JobMetadata) -> int:
        """Get job interval, checking config overrides."""
        job_type_str = str(job_type).lower()

        # Try config override with standard naming pattern
        config_attr = f"{job_type_str}_interval_seconds"
        if hasattr(config.scheduler, config_attr):
            return getattr(config.scheduler, config_attr, metadata.interval_seconds)

        # Try alternative naming pattern for backwards compatibility
        alt_config_attr = f"{job_type_str}_runner_interval_seconds"
        if hasattr(config.scheduler, alt_config_attr):
            return getattr(config.scheduler, alt_config_attr, metadata.interval_seconds)

        # Use metadata default if no config override found
        return metadata.interval_seconds

    async def _execute_job_via_executor(self, job_type: str) -> None:
        """Execute a job through the enhanced executor system with proper concurrency control."""
        logger.info(
            "Scheduled execution triggered",
            extra={"job_type": job_type, "event_type": "scheduled_trigger"},
        )
        try:
            from app.backend.models import QueueMessage, QueueMessageType

            from .base import JobType
            from .decorators import JobRegistry

            # Convert job_type string to JobType enum
            job_type_enum = JobType.get_or_create(job_type)
            logger.debug(
                "Job type converted to enum",
                extra={"job_type": job_type, "job_type_enum": str(job_type_enum)},
            )

            logger.debug(
                "Checking for available work",
                extra={"job_type": job_type, "event_type": "work_check"},
            )

            # Get job metadata to check if it should run
            metadata = JobRegistry.get_metadata(job_type_enum)
            if not metadata:
                logger.error(
                    "Job metadata not found",
                    extra={"job_type": job_type, "event_type": "metadata_error"},
                )
                return

            # For jobs that process messages, check if there are pending messages first
            # This prevents unnecessary job executions when there's no work
            if job_type in ["tweet", "discord", "stx_transfer"]:
                from app.backend.models import QueueMessageFilter

                pending_messages = backend.list_queue_messages(
                    filters=QueueMessageFilter(
                        type=QueueMessageType.get_or_create(job_type),
                        is_processed=False,
                    )
                )

                if not pending_messages:
                    logger.debug(
                        "Skipping execution - no pending messages",
                        extra={"job_type": job_type, "event_type": "skip_no_work"},
                    )
                    return

                logger.debug(
                    "Found pending messages",
                    extra={
                        "job_type": job_type,
                        "pending_count": len(pending_messages),
                        "event_type": "work_found",
                    },
                )

            # Create a synthetic queue message for scheduled execution
            # This allows the job to go through the proper executor pipeline with concurrency control
            synthetic_message = QueueMessage(
                id=uuid.uuid4(),
                type=QueueMessageType.get_or_create(job_type),
                message={
                    "scheduled_execution": True,
                    "triggered_at": str(datetime.now()),
                },
                dao_id=None,
                wallet_id=None,
                is_processed=False,
                result=None,
                created_at=datetime.now(),
            )

            # Enqueue the synthetic message with the job's priority
            logger.debug(
                "Enqueuing job to executor",
                extra={
                    "job_type": job_type,
                    "priority": str(metadata.priority),
                    "event_type": "enqueue",
                },
            )
            job_id = await self._executor.priority_queue.enqueue(
                synthetic_message, metadata.priority
            )

            logger.info(
                "Scheduled job enqueued successfully",
                extra={
                    "job_type": job_type,
                    "job_id": str(job_id),
                    "priority": str(metadata.priority),
                    "event_type": "enqueue_success",
                },
            )

        except Exception as e:
            logger.error(
                "Failed to enqueue scheduled job",
                extra={
                    "job_type": job_type,
                    "error": str(e),
                    "event_type": "enqueue_error",
                },
                exc_info=True,
            )

    def schedule_jobs(self, scheduler: AsyncIOScheduler) -> bool:
        """Schedule all enabled jobs using the new system."""
        self._scheduler = scheduler

        # Get all job configurations
        jobs = self.get_all_jobs()

        # Schedule enabled jobs
        any_enabled = False
        scheduled_count = 0

        for job_config in jobs:
            if job_config.enabled:
                any_enabled = True

                # Get the actual interval (might be overridden by config)
                interval_seconds = self._get_job_interval(
                    job_config.job_type, job_config.metadata
                )

                # Schedule the job
                scheduler.add_job(
                    self._execute_job_via_executor,
                    "interval",
                    seconds=interval_seconds,
                    id=job_config.scheduler_id,
                    args=[job_config.job_type],
                    max_instances=1,  # Prevent overlapping executions
                    misfire_grace_time=60,
                    replace_existing=True,  # Allow replacing existing jobs
                )

                scheduled_count += 1
                logger.info(
                    "Job scheduled successfully",
                    extra={
                        "job_name": job_config.metadata.name,
                        "job_type": job_config.job_type,
                        "priority": str(job_config.metadata.priority),
                        "interval_seconds": interval_seconds,
                        "max_concurrent": job_config.metadata.max_concurrent,
                        "event_type": "schedule_success",
                    },
                )
            else:
                logger.info(
                    "Job disabled - skipping scheduling",
                    extra={
                        "job_name": job_config.metadata.name,
                        "job_type": job_config.job_type,
                        "event_type": "job_disabled",
                    },
                )

        if scheduled_count > 0:
            logger.info(
                "Job scheduling completed",
                extra={
                    "scheduled_count": scheduled_count,
                    "event_type": "scheduling_complete",
                },
            )

        return any_enabled

    async def start_executor(self, num_workers: int = 5) -> None:
        """Start the job executor."""
        await self._executor.start(num_workers)
        self._is_running = True
        logger.info(
            "Job executor started",
            extra={"worker_count": num_workers, "event_type": "executor_start"},
        )

    async def stop_executor(self) -> None:
        """Stop the job executor."""
        await self._executor.stop()
        self._is_running = False
        logger.info("Job executor stopped", extra={"event_type": "executor_stop"})

    def get_executor_stats(self) -> Dict[str, Any]:
        """Get executor statistics."""
        return self._executor.get_stats()

    def get_job_metrics(self, job_type: Optional[str] = None) -> Dict[str, Any]:
        """Get job execution metrics."""
        from .base import JobType

        job_type_enum = None
        if job_type:
            try:
                job_type_enum = JobType(job_type)
            except ValueError:
                pass

        metrics = self._metrics.get_metrics(job_type_enum)
        return {
            str(jt): {
                "total_executions": m.total_executions,
                "successful_executions": m.successful_executions,
                "failed_executions": m.failed_executions,
                "retried_executions": m.retried_executions,
                "dead_letter_executions": m.dead_letter_executions,
                "avg_execution_time": m.avg_execution_time,
                "min_execution_time": m.min_execution_time,
                "max_execution_time": m.max_execution_time,
                "current_running": m.current_running,
                "max_concurrent_reached": m.max_concurrent_reached,
                "last_execution": (
                    m.last_execution.isoformat() if m.last_execution else None
                ),
                "last_success": m.last_success.isoformat() if m.last_success else None,
                "last_failure": m.last_failure.isoformat() if m.last_failure else None,
            }
            for jt, m in metrics.items()
        }

    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health status."""
        system_metrics = self._metrics.get_system_metrics()
        health_status = self._metrics.get_health_status()
        performance_summary = self._performance_monitor.get_performance_summary()
        task_summary = get_task_summary()
        executor_stats = self.get_executor_stats()

        return {
            "status": health_status["status"],
            "uptime_seconds": system_metrics["uptime_seconds"],
            "executor": {
                "running": executor_stats["running"],
                "worker_count": executor_stats["worker_count"],
                "dead_letter_count": executor_stats["dead_letter_count"],
                "active_jobs": executor_stats["active_jobs"],
            },
            "metrics": {
                "total_executions": system_metrics["total_executions"],
                "success_rate": system_metrics["success_rate"],
                "total_dead_letter": system_metrics["total_dead_letter"],
            },
            "tasks": {
                "total_registered": task_summary["total_tasks"],
                "enabled": task_summary["enabled_tasks"],
                "disabled": task_summary["disabled_tasks"],
                "dependency_issues": len(task_summary["dependency_issues"]),
            },
            "performance": {
                "system_health": performance_summary.get("system_health", "unknown"),
                "healthy_job_types": performance_summary.get("healthy_job_types", 0),
                "problematic_job_types": performance_summary.get(
                    "problematic_job_types", []
                ),
            },
            "issues": health_status["issues"],
            "alerts": performance_summary.get("alerts", []),
        }

    def get_job_details(self, job_type: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific job type."""
        try:
            from .base import JobType

            job_type_enum = JobType(job_type)

            metadata = JobRegistry.get_metadata(job_type_enum)
            if not metadata:
                return None

            # Get metrics for this job
            metrics = self._metrics.get_metrics(job_type_enum)
            job_metrics = metrics.get(job_type_enum)

            # Get recent events
            recent_events = self._metrics.get_recent_events(job_type_enum, limit=10)

            return {
                "job_type": job_type,
                "metadata": {
                    "name": metadata.name,
                    "description": metadata.description,
                    "version": metadata.version,
                    "enabled": metadata.enabled,
                    "interval_seconds": metadata.interval_seconds,
                    "priority": str(metadata.priority),
                    "max_retries": metadata.max_retries,
                    "retry_delay_seconds": metadata.retry_delay_seconds,
                    "timeout_seconds": metadata.timeout_seconds,
                    "max_concurrent": metadata.max_concurrent,
                    "batch_size": metadata.batch_size,
                    "requires_wallet": metadata.requires_wallet,
                    "requires_twitter": metadata.requires_twitter,
                    "requires_discord": metadata.requires_discord,
                    "dependencies": metadata.dependencies,
                    "enable_dead_letter_queue": metadata.enable_dead_letter_queue,
                    "preserve_order": metadata.preserve_order,
                    "idempotent": metadata.idempotent,
                },
                "metrics": {
                    "total_executions": (
                        job_metrics.total_executions if job_metrics else 0
                    ),
                    "successful_executions": (
                        job_metrics.successful_executions if job_metrics else 0
                    ),
                    "failed_executions": (
                        job_metrics.failed_executions if job_metrics else 0
                    ),
                    "retried_executions": (
                        job_metrics.retried_executions if job_metrics else 0
                    ),
                    "dead_letter_executions": (
                        job_metrics.dead_letter_executions if job_metrics else 0
                    ),
                    "avg_execution_time": (
                        job_metrics.avg_execution_time if job_metrics else 0
                    ),
                    "min_execution_time": (
                        job_metrics.min_execution_time if job_metrics else None
                    ),
                    "max_execution_time": (
                        job_metrics.max_execution_time if job_metrics else None
                    ),
                    "current_running": (
                        job_metrics.current_running if job_metrics else 0
                    ),
                    "max_concurrent_reached": (
                        job_metrics.max_concurrent_reached if job_metrics else 0
                    ),
                    "last_execution": (
                        job_metrics.last_execution.isoformat()
                        if job_metrics and job_metrics.last_execution
                        else None
                    ),
                    "last_success": (
                        job_metrics.last_success.isoformat()
                        if job_metrics and job_metrics.last_success
                        else None
                    ),
                    "last_failure": (
                        job_metrics.last_failure.isoformat()
                        if job_metrics and job_metrics.last_failure
                        else None
                    ),
                },
                "recent_events": [
                    {
                        "execution_id": str(event.execution_id),
                        "event_type": event.event_type,
                        "timestamp": event.timestamp.isoformat(),
                        "duration": event.duration,
                        "error": event.error,
                        "attempt": event.attempt,
                        "metadata": event.metadata,
                    }
                    for event in recent_events
                ],
            }

        except ValueError:
            return None

    async def trigger_job_execution(self, job_type: str) -> Dict[str, Any]:
        """Manually trigger execution of a specific job type."""
        try:
            await self._execute_job_via_executor(job_type)
            return {
                "success": True,
                "message": f"Triggered execution for job type: {job_type}",
                "job_type": job_type,
            }
        except Exception as e:
            logger.error(
                "Failed to trigger job execution",
                extra={
                    "job_type": job_type,
                    "error": str(e),
                    "event_type": "trigger_error",
                },
                exc_info=True,
            )
            return {
                "success": False,
                "message": f"Failed to trigger job: {str(e)}",
                "job_type": job_type,
                "error": str(e),
            }
