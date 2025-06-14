"""Runner module for executing tasks such as DAO processing and Twitter interactions."""

# Auto-discovery will handle task registration
from services.runner.auto_discovery import discover_and_register_tasks
from services.runner.base import BaseTask, JobContext, JobType
from services.runner.job_manager import JobManager, JobScheduleConfig
from services.runner.registry import JobRegistry, execute_runner_job

# Ensure tasks are discovered and registered when module is imported
discover_and_register_tasks()

__all__ = [
    "BaseTask",
    "JobContext",
    "JobRegistry",
    "JobType",
    "JobScheduleConfig",
    "JobManager",
    "execute_runner_job",
]
