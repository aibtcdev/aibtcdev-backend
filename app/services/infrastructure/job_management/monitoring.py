"""Job monitoring and observability system."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.lib.logger import configure_logger

from .base import JobType

logger = configure_logger(__name__)


@dataclass
class JobMetrics:
    """Metrics for job execution."""

    job_type: JobType
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    retried_executions: int = 0
    dead_letter_executions: int = 0

    # Timing metrics
    total_execution_time: float = 0.0
    min_execution_time: Optional[float] = None
    max_execution_time: Optional[float] = None
    avg_execution_time: float = 0.0

    # Recent metrics (last hour)
    recent_executions: int = 0
    recent_failures: int = 0
    recent_avg_time: float = 0.0

    # Concurrency metrics
    current_running: int = 0
    max_concurrent_reached: int = 0

    last_execution: Optional[datetime] = None
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None


@dataclass
class ExecutionEvent:
    """Individual execution event for detailed tracking."""

    execution_id: UUID
    job_type: JobType
    event_type: str  # started, completed, failed, retried, dead_letter
    timestamp: datetime
    duration: Optional[float] = None
    error: Optional[str] = None
    attempt: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)


class MetricsCollector:
    """Collects and aggregates job execution metrics."""

    def __init__(self, max_events: int = 10000):
        self._metrics: Dict[JobType, JobMetrics] = {}
        self._events: List[ExecutionEvent] = []
        self._max_events = max_events
        self._start_time = datetime.now()

    def record_execution_start(self, execution: Any, worker_name: str = "") -> None:
        """Record the start of a job execution."""
        job_type = execution.job_type

        # Initialize metrics if needed
        if job_type not in self._metrics:
            self._metrics[job_type] = JobMetrics(job_type=job_type)

        metrics = self._metrics[job_type]
        metrics.total_executions += 1
        metrics.current_running += 1
        metrics.max_concurrent_reached = max(
            metrics.max_concurrent_reached, metrics.current_running
        )
        metrics.last_execution = datetime.now()

        # Record event
        event = ExecutionEvent(
            execution_id=execution.id,
            job_type=job_type,
            event_type="started",
            timestamp=datetime.now(),
            attempt=execution.attempt,
            metadata={"worker": worker_name},
        )
        self._add_event(event)

        logger.debug(f"Started tracking execution {execution.id} ({job_type})")

    def record_execution_completion(self, execution: Any, duration: float) -> None:
        """Record the completion of a job execution."""
        job_type = execution.job_type
        metrics = self._metrics.get(job_type)

        if not metrics:
            logger.warning(f"No metrics found for job type {job_type}")
            return

        metrics.current_running = max(0, metrics.current_running - 1)
        metrics.successful_executions += 1
        metrics.last_success = datetime.now()

        # Update timing metrics
        self._update_timing_metrics(metrics, duration)

        # Record event
        event = ExecutionEvent(
            execution_id=execution.id,
            job_type=job_type,
            event_type="completed",
            timestamp=datetime.now(),
            duration=duration,
            attempt=execution.attempt,
        )
        self._add_event(event)

        logger.debug(
            f"Completed execution {execution.id} ({job_type}) in {duration:.2f}s"
        )

    def record_execution_failure(
        self, execution: Any, error: str, duration: float
    ) -> None:
        """Record a job execution failure."""
        job_type = execution.job_type
        metrics = self._metrics.get(job_type)

        if not metrics:
            logger.warning(f"No metrics found for job type {job_type}")
            return

        metrics.current_running = max(0, metrics.current_running - 1)
        metrics.failed_executions += 1
        metrics.last_failure = datetime.now()

        # Update timing metrics (even for failures)
        self._update_timing_metrics(metrics, duration)

        # Record event
        event = ExecutionEvent(
            execution_id=execution.id,
            job_type=job_type,
            event_type="failed",
            timestamp=datetime.now(),
            duration=duration,
            error=error,
            attempt=execution.attempt,
        )
        self._add_event(event)

        logger.debug(
            f"Failed execution {execution.id} ({job_type}) after {duration:.2f}s: {error}"
        )

    def record_execution_retry(self, execution: Any) -> None:
        """Record a job execution retry."""
        job_type = execution.job_type
        metrics = self._metrics.get(job_type)

        if not metrics:
            logger.warning(f"No metrics found for job type {job_type}")
            return

        metrics.retried_executions += 1

        # Record event
        event = ExecutionEvent(
            execution_id=execution.id,
            job_type=job_type,
            event_type="retried",
            timestamp=datetime.now(),
            attempt=execution.attempt,
        )
        self._add_event(event)

        logger.debug(
            f"Retrying execution {execution.id} ({job_type}), attempt {execution.attempt}"
        )

    def record_dead_letter(self, execution: Any) -> None:
        """Record a job being moved to dead letter queue."""
        job_type = execution.job_type
        metrics = self._metrics.get(job_type)

        if not metrics:
            logger.warning(f"No metrics found for job type {job_type}")
            return

        metrics.dead_letter_executions += 1

        # Record event
        event = ExecutionEvent(
            execution_id=execution.id,
            job_type=job_type,
            event_type="dead_letter",
            timestamp=datetime.now(),
            error=getattr(execution, "error", None),
            attempt=execution.attempt,
        )
        self._add_event(event)

        logger.warning(
            f"Dead letter execution {execution.id} ({job_type}) after {execution.attempt} attempts"
        )

    def _update_timing_metrics(self, metrics: JobMetrics, duration: float) -> None:
        """Update timing metrics with new execution duration."""
        # Update min/max
        if metrics.min_execution_time is None or duration < metrics.min_execution_time:
            metrics.min_execution_time = duration
        if metrics.max_execution_time is None or duration > metrics.max_execution_time:
            metrics.max_execution_time = duration

        # Update average
        total_time = metrics.total_execution_time + duration
        total_count = metrics.successful_executions + metrics.failed_executions

        metrics.total_execution_time = total_time
        if total_count > 0:
            metrics.avg_execution_time = total_time / total_count

    def _add_event(self, event: ExecutionEvent) -> None:
        """Add an event to the event log."""
        self._events.append(event)

        # Trim events if we exceed max
        if len(self._events) > self._max_events:
            # Remove oldest 20% to avoid frequent trimming
            trim_count = int(self._max_events * 0.2)
            self._events = self._events[trim_count:]

    def get_metrics(
        self, job_type: Optional[JobType] = None
    ) -> Dict[JobType, JobMetrics]:
        """Get metrics for all job types or a specific type."""
        if job_type:
            return {
                job_type: self._metrics.get(job_type, JobMetrics(job_type=job_type))
            }
        return self._metrics.copy()

    def get_recent_events(
        self, job_type: Optional[JobType] = None, limit: int = 100
    ) -> List[ExecutionEvent]:
        """Get recent execution events."""
        events = self._events

        if job_type:
            events = [e for e in events if e.job_type == job_type]

        # Return most recent events
        return sorted(events, key=lambda e: e.timestamp, reverse=True)[:limit]

    def get_system_metrics(self) -> Dict[str, Any]:
        """Get overall system metrics."""
        total_executions = sum(m.total_executions for m in self._metrics.values())
        total_successful = sum(m.successful_executions for m in self._metrics.values())
        total_failed = sum(m.failed_executions for m in self._metrics.values())
        total_dead_letter = sum(
            m.dead_letter_executions for m in self._metrics.values()
        )

        success_rate = (
            (total_successful / total_executions) if total_executions > 0 else 0
        )

        return {
            "uptime_seconds": (datetime.now() - self._start_time).total_seconds(),
            "total_executions": total_executions,
            "total_successful": total_successful,
            "total_failed": total_failed,
            "total_dead_letter": total_dead_letter,
            "success_rate": success_rate,
            "active_job_types": len(self._metrics),
            "total_events": len(self._events),
        }

    def get_health_status(self) -> Dict[str, Any]:
        """Get system health status."""
        now = datetime.now()
        health = {"status": "healthy", "issues": []}

        for job_type, metrics in self._metrics.items():
            # Check failure rate
            if metrics.total_executions > 10:
                failure_rate = metrics.failed_executions / metrics.total_executions
                if failure_rate > 0.5:  # More than 50% failures
                    health["issues"].append(
                        f"{job_type}: High failure rate ({failure_rate:.1%})"
                    )

            # Check if job hasn't run recently (if it should be running)
            if metrics.last_execution:
                time_since_last = now - metrics.last_execution
                if time_since_last > timedelta(hours=2):
                    health["issues"].append(
                        f"{job_type}: No executions in {time_since_last}"
                    )

        if health["issues"]:
            health["status"] = "degraded" if len(health["issues"]) < 3 else "unhealthy"

        return health

    def reset_metrics(self, job_type: Optional[JobType] = None) -> None:
        """Reset metrics for a job type or all types."""
        if job_type:
            if job_type in self._metrics:
                self._metrics[job_type] = JobMetrics(job_type=job_type)
        else:
            self._metrics.clear()
            self._events.clear()

        logger.info(f"Reset metrics for {job_type or 'all job types'}")

    # Legacy compatibility methods for the new executor
    def get_job_metrics(self, job_type: Optional[str] = None) -> Dict[str, Any]:
        """Get job metrics in the format expected by the new executor."""
        if job_type:
            job_type_enum = JobType.get_or_create(job_type)
            metrics = self._metrics.get(job_type_enum)
            if metrics:
                return {
                    "job_type": str(metrics.job_type),
                    "total_executions": metrics.total_executions,
                    "successful_executions": metrics.successful_executions,
                    "failed_executions": metrics.failed_executions,
                    "success_rate": (
                        metrics.successful_executions / metrics.total_executions
                        if metrics.total_executions > 0
                        else 0.0
                    ),
                    "average_duration_seconds": metrics.avg_execution_time,
                    "min_duration_seconds": metrics.min_execution_time or 0.0,
                    "max_duration_seconds": metrics.max_execution_time or 0.0,
                    "last_execution": (
                        metrics.last_execution.isoformat()
                        if metrics.last_execution
                        else None
                    ),
                    "last_success": (
                        metrics.last_success.isoformat()
                        if metrics.last_success
                        else None
                    ),
                    "last_failure": (
                        metrics.last_failure.isoformat()
                        if metrics.last_failure
                        else None
                    ),
                    "retry_count": metrics.retried_executions,
                    "dead_letter_count": metrics.dead_letter_executions,
                }
            else:
                return {"error": f"No metrics found for job type: {job_type}"}
        else:
            # Return all job metrics
            return {
                str(job_type): {
                    "job_type": str(metrics.job_type),
                    "total_executions": metrics.total_executions,
                    "successful_executions": metrics.successful_executions,
                    "failed_executions": metrics.failed_executions,
                    "success_rate": (
                        metrics.successful_executions / metrics.total_executions
                        if metrics.total_executions > 0
                        else 0.0
                    ),
                    "average_duration_seconds": metrics.avg_execution_time,
                    "min_duration_seconds": metrics.min_execution_time or 0.0,
                    "max_duration_seconds": metrics.max_execution_time or 0.0,
                    "last_execution": (
                        metrics.last_execution.isoformat()
                        if metrics.last_execution
                        else None
                    ),
                    "last_success": (
                        metrics.last_success.isoformat()
                        if metrics.last_success
                        else None
                    ),
                    "last_failure": (
                        metrics.last_failure.isoformat()
                        if metrics.last_failure
                        else None
                    ),
                    "retry_count": metrics.retried_executions,
                    "dead_letter_count": metrics.dead_letter_executions,
                }
                for job_type, metrics in self._metrics.items()
            }


class SystemMetrics:
    """System-wide metrics collector for monitoring system resources."""

    def __init__(self):
        self.monitoring_active = False

    async def start_monitoring(self) -> None:
        """Start system monitoring."""
        self.monitoring_active = True
        logger.info("System metrics monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop system monitoring."""
        self.monitoring_active = False
        logger.info("System metrics monitoring stopped")

    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current system metrics."""
        try:
            import psutil

            return {
                "cpu_usage": psutil.cpu_percent(interval=1),
                "memory_usage": psutil.virtual_memory().percent,
                "disk_usage": psutil.disk_usage("/").percent,
                "timestamp": datetime.now().isoformat(),
                "monitoring_active": self.monitoring_active,
            }
        except ImportError:
            logger.warning("psutil not available, returning basic metrics")
            return {
                "cpu_usage": 0,
                "memory_usage": 0,
                "disk_usage": 0,
                "timestamp": datetime.now().isoformat(),
                "monitoring_active": self.monitoring_active,
            }


class PerformanceMonitor:
    """Monitors job execution performance and provides alerts."""

    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics = metrics_collector
        self._thresholds = {
            "max_failure_rate": 0.3,  # 30%
            "max_avg_execution_time": 300.0,  # 5 minutes
            "max_dead_letter_rate": 0.1,  # 10%
        }

    def check_performance_issues(self) -> List[str]:
        """Check for performance issues and return alerts."""
        alerts = []

        for job_type, metrics in self.metrics.get_metrics().items():
            if metrics.total_executions < 5:
                continue  # Skip jobs with insufficient data

            # Check failure rate
            failure_rate = metrics.failed_executions / metrics.total_executions
            if failure_rate > self._thresholds["max_failure_rate"]:
                alerts.append(
                    f"HIGH FAILURE RATE: {job_type} has {failure_rate:.1%} failure rate"
                )

            # Check average execution time
            if metrics.avg_execution_time > self._thresholds["max_avg_execution_time"]:
                alerts.append(
                    f"SLOW EXECUTION: {job_type} average time is {metrics.avg_execution_time:.1f}s"
                )

            # Check dead letter rate
            dead_letter_rate = metrics.dead_letter_executions / metrics.total_executions
            if dead_letter_rate > self._thresholds["max_dead_letter_rate"]:
                alerts.append(
                    f"HIGH DEAD LETTER RATE: {job_type} has {dead_letter_rate:.1%} dead letter rate"
                )

        return alerts

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get a performance summary across all job types."""
        metrics_data = self.metrics.get_metrics()

        if not metrics_data:
            return {"message": "No job execution data available"}

        # Calculate overall statistics
        total_jobs = len(metrics_data)
        healthy_jobs = 0
        problematic_jobs = []

        for job_type, metrics in metrics_data.items():
            if metrics.total_executions < 5:
                continue

            failure_rate = metrics.failed_executions / metrics.total_executions
            dead_letter_rate = metrics.dead_letter_executions / metrics.total_executions

            is_healthy = (
                failure_rate <= self._thresholds["max_failure_rate"]
                and metrics.avg_execution_time
                <= self._thresholds["max_avg_execution_time"]
                and dead_letter_rate <= self._thresholds["max_dead_letter_rate"]
            )

            if is_healthy:
                healthy_jobs += 1
            else:
                problematic_jobs.append(str(job_type))

        return {
            "total_job_types": total_jobs,
            "healthy_job_types": healthy_jobs,
            "problematic_job_types": problematic_jobs,
            "system_health": (
                "good" if len(problematic_jobs) == 0 else "needs_attention"
            ),
            "alerts": self.check_performance_issues(),
        }


# Global metrics collector
_metrics_collector: Optional[MetricsCollector] = None
_performance_monitor: Optional[PerformanceMonitor] = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance."""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor(get_metrics_collector())
    return _performance_monitor


def reset_metrics_collector() -> None:
    """Reset the global metrics collector (useful for testing)."""
    global _metrics_collector
    _metrics_collector = MetricsCollector()
