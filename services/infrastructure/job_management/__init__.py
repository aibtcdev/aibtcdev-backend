"""Job management system for the aibtcdev backend.

This module provides a comprehensive job management system with:
- Auto-discovery of job tasks
- Priority-based job execution
- Retry mechanisms with exponential backoff
- Dead letter queue for failed jobs
- Metrics collection and monitoring
- Concurrent job execution with semaphore control
"""

from .auto_discovery import discover_and_register_tasks, get_task_summary, reload_tasks
from .base import BaseTask, JobContext, JobType, RunnerConfig, RunnerResult
from .decorators import JobMetadata, JobPriority, JobRegistry, job, scheduled_job
from .executor import JobExecutor, get_executor
from .monitoring import (
    MetricsCollector,
    PerformanceMonitor,
    SystemMetrics,
    get_metrics_collector,
    get_performance_monitor,
    reset_metrics_collector,
)
from .registry import execute_runner_job

__all__ = [
    # Core classes
    "BaseTask",
    "JobContext",
    "JobType",
    "RunnerConfig",
    "RunnerResult",
    # Decorators and metadata
    "JobMetadata",
    "JobPriority",
    "JobRegistry",
    "job",
    "scheduled_job",
    # Execution
    "JobExecutor",
    "get_executor",
    "execute_runner_job",
    # Monitoring
    "MetricsCollector",
    "PerformanceMonitor",
    "SystemMetrics",
    "get_metrics_collector",
    "get_performance_monitor",
    "reset_metrics_collector",
    # Auto-discovery
    "discover_and_register_tasks",
    "get_task_summary",
    "reload_tasks",
]
