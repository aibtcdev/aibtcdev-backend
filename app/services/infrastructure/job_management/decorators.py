"""Job registration decorators and metadata system."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union

from app.lib.logger import configure_logger

from .base import BaseTask, JobType

logger = configure_logger(__name__)

T = TypeVar("T", bound=BaseTask)


class JobPriority(Enum):
    """Job execution priority levels."""

    LOW = 1
    NORMAL = 2
    MEDIUM = 3
    HIGH = 4
    CRITICAL = 5

    def __str__(self):
        return self.name.lower()


@dataclass
class JobMetadata:
    """Metadata for job configuration and execution."""

    # Basic job information
    job_type: JobType
    name: str
    description: str = ""
    version: str = "1.0.0"

    # Execution configuration
    enabled: bool = True
    interval_seconds: int = 60
    priority: JobPriority = JobPriority.NORMAL
    max_retries: int = 3
    retry_delay_seconds: int = 30
    timeout_seconds: Optional[int] = None

    # Concurrency settings
    max_concurrent: int = 1
    batch_size: int = 10

    # Dependencies and requirements
    requires_wallet: bool = False
    requires_twitter: bool = False
    requires_discord: bool = False
    requires_blockchain: bool = False
    requires_ai: bool = False
    dependencies: List[str] = field(default_factory=list)

    # Advanced settings
    enable_dead_letter_queue: bool = True
    preserve_order: bool = False
    idempotent: bool = False

    # Configuration overrides
    config_overrides: Dict[str, Any] = field(default_factory=dict)


class JobRegistry:
    """Enhanced job registry with auto-discovery and metadata."""

    _jobs: Dict[JobType, Type[BaseTask]] = {}
    _metadata: Dict[JobType, JobMetadata] = {}
    _instances: Dict[JobType, BaseTask] = {}

    @classmethod
    def register(
        cls,
        job_type: Union[JobType, str],
        metadata: Optional[JobMetadata] = None,
        **kwargs,
    ) -> Callable[[Type[T]], Type[T]]:
        """Decorator to register a job task with metadata.

        Args:
            job_type: The job type enum or string
            metadata: Optional job metadata
            **kwargs: Additional metadata fields

        Returns:
            Decorator function

        Example:
            @JobRegistry.register(
                "new_job_type",  # Can use string - will auto-create JobType
                name="New Job",
                description="Does new job things",
                interval_seconds=120,
                max_concurrent=2
            )
            class NewJobTask(BaseTask[NewJobResult]):
                pass
        """

        def decorator(task_class: Type[T]) -> Type[T]:
            # Convert string to JobType or create new one
            if isinstance(job_type, str):
                job_enum = JobType.get_or_create(job_type)
                logger.info(f"Auto-registered job type: {job_type} -> {job_enum}")
            else:
                job_enum = job_type

            # Create metadata if not provided
            if metadata is None:
                # Extract metadata from kwargs or use defaults
                meta = JobMetadata(
                    job_type=job_enum,
                    name=kwargs.get("name", task_class.__name__),
                    description=kwargs.get("description", task_class.__doc__ or ""),
                    **{
                        k: v
                        for k, v in kwargs.items()
                        if k not in ["name", "description"]
                    },
                )
            else:
                # Update metadata with any additional kwargs
                for key, value in kwargs.items():
                    if hasattr(metadata, key):
                        setattr(metadata, key, value)
                meta = metadata

            # Register the task
            cls._jobs[job_enum] = task_class
            cls._metadata[job_enum] = meta

            logger.info(
                f"Registered job: {job_enum} -> {task_class.__name__} "
                f"(enabled: {meta.enabled}, interval: {meta.interval_seconds}s)"
            )

            return task_class

        return decorator

    @classmethod
    def get_task_class(cls, job_type: JobType) -> Optional[Type[BaseTask]]:
        """Get the task class for a job type."""
        return cls._jobs.get(job_type)

    @classmethod
    def get_metadata(cls, job_type: JobType) -> Optional[JobMetadata]:
        """Get the metadata for a job type."""
        return cls._metadata.get(job_type)

    @classmethod
    def get_instance(cls, job_type: JobType) -> Optional[BaseTask]:
        """Get or create a task instance for a job type."""
        if job_type not in cls._instances:
            task_class = cls.get_task_class(job_type)
            if task_class:
                cls._instances[job_type] = task_class()
        return cls._instances.get(job_type)

    @classmethod
    def list_jobs(cls) -> Dict[JobType, JobMetadata]:
        """List all registered jobs and their metadata."""
        return cls._metadata.copy()

    @classmethod
    def list_enabled_jobs(cls) -> Dict[JobType, JobMetadata]:
        """List only enabled jobs."""
        return {
            job_type: metadata
            for job_type, metadata in cls._metadata.items()
            if metadata.enabled
        }

    @classmethod
    def get_jobs_by_priority(cls, priority: JobPriority) -> Dict[JobType, JobMetadata]:
        """Get jobs filtered by priority."""
        return {
            job_type: metadata
            for job_type, metadata in cls._metadata.items()
            if metadata.priority == priority
        }

    @classmethod
    def clear_registry(cls) -> None:
        """Clear all registered jobs (useful for testing)."""
        cls._jobs.clear()
        cls._metadata.clear()
        cls._instances.clear()

    @classmethod
    def validate_dependencies(cls) -> List[str]:
        """Validate job dependencies and return any issues."""
        issues = []
        all_job_types = set(cls._jobs.keys())

        for job_type, metadata in cls._metadata.items():
            for dep in metadata.dependencies:
                try:
                    dep_type = JobType.get_or_create(dep)
                    if dep_type not in all_job_types:
                        issues.append(
                            f"Job {job_type} depends on unregistered job: {dep}"
                        )
                except Exception:
                    issues.append(f"Job {job_type} has invalid dependency: {dep}")

        return issues

    @classmethod
    def get_all_job_types(cls) -> List[str]:
        """Get all registered job type strings."""
        return [str(job_type) for job_type in cls._jobs.keys()]


# Convenience function for job registration
def job(
    job_type: Union[JobType, str],
    name: Optional[str] = None,
    description: Optional[str] = None,
    **kwargs,
) -> Callable[[Type[T]], Type[T]]:
    """Convenience decorator for job registration.

    Args:
        job_type: The job type (can be string - will auto-create JobType)
        name: Human-readable job name
        description: Job description
        **kwargs: Additional metadata fields

    Example:
        @job("my_new_job", name="My New Job", interval_seconds=30)
        class MyNewJobTask(BaseTask[MyJobResult]):
            pass
    """
    return JobRegistry.register(
        job_type=job_type,
        name=name,
        description=description,
        **kwargs,
    )


# Convenience function for quick job registration with metadata
def scheduled_job(
    job_type: Union[JobType, str],
    interval_seconds: int,
    name: Optional[str] = None,
    **kwargs,
) -> Callable[[Type[T]], Type[T]]:
    """Decorator for scheduled jobs with interval configuration.

    Args:
        job_type: The job type (can be string - will auto-create JobType)
        interval_seconds: How often to run the job
        name: Human-readable job name
        **kwargs: Additional metadata fields

    Example:
        @scheduled_job("my_scheduled_job", 120, name="My Scheduled Job")
        class MyScheduledJobTask(BaseTask[MyJobResult]):
            pass
    """
    return JobRegistry.register(
        job_type=job_type,
        interval_seconds=interval_seconds,
        name=name,
        **kwargs,
    )
