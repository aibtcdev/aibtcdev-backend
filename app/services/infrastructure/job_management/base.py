from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from app.backend.models import QueueMessage
from app.lib.logger import configure_logger

logger = configure_logger(__name__)


@dataclass
class RunnerResult:
    """Base class for runner operation results."""

    success: bool
    message: str
    error: Optional[Exception] = None


T = TypeVar("T", bound=RunnerResult)


@dataclass
class RunnerConfig:
    """Configuration class for runners."""

    max_retries: int = 3


class JobType:
    """Dynamic job types that are registered at runtime via auto-discovery.

    No hardcoded job types - all jobs are discovered and registered dynamically
    using the @job decorator in task files.
    """

    _job_types: Dict[str, "JobType"] = {}

    def __init__(self, value: str):
        self._value = value.lower()
        self._name = value.upper()

    @property
    def value(self) -> str:
        return self._value

    @property
    def name(self) -> str:
        return self._name

    def __str__(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return f"JobType.{self._name}"

    def __eq__(self, other) -> bool:
        if isinstance(other, JobType):
            return self._value == other._value
        if isinstance(other, str):
            return self._value == other.lower()
        return False

    def __hash__(self) -> int:
        return hash(self._value)

    @classmethod
    def get_or_create(cls, job_type: str) -> "JobType":
        """Get existing job type or create new one."""
        normalized = job_type.lower()
        if normalized not in cls._job_types:
            cls._job_types[normalized] = cls(normalized)
        return cls._job_types[normalized]

    @classmethod
    def register(cls, job_type: str) -> "JobType":
        """Register a new job type and return the enum member."""
        return cls.get_or_create(job_type)

    @classmethod
    def get_all_job_types(cls) -> Dict[str, str]:
        """Get all registered job types."""
        return {jt._value: jt._value for jt in cls._job_types.values()}

    @classmethod
    def list_all(cls) -> List["JobType"]:
        """Get all registered job type instances."""
        return list(cls._job_types.values())

    def __call__(self, value: str) -> "JobType":
        """Allow calling like an enum constructor."""
        return self.get_or_create(value)


@dataclass
class JobContext:
    """Context information for job execution."""

    job_type: JobType
    config: RunnerConfig
    parameters: Optional[Dict[str, Any]] = None
    retry_count: int = 0
    max_retries: int = 3

    # Enhanced context fields
    execution_id: Optional[str] = None
    worker_name: Optional[str] = None
    timeout_seconds: Optional[int] = None
    priority: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseTask(ABC, Generic[T]):
    """Base class for all tasks."""

    def __init__(self, config: Optional[RunnerConfig] = None):
        self.config = config or RunnerConfig()
        self._start_time: Optional[float] = None

    def _get_current_retry_count(self, message: QueueMessage) -> int:
        """Retrieve the current retry count from the message's result, defaulting to 0."""
        return message.result.get("retry_count", 0) if message.result else 0

    @property
    def task_name(self) -> str:
        """Get the task name for logging purposes."""
        return self.__class__.__name__

    def _log_task_start(self) -> None:
        """Log task start with standard format."""
        import time

        self._start_time = time.time()
        logger.debug(f"Starting task: {self.task_name}")
        logger.debug(f"{self.task_name}: Configuration - {self.config}")

    def _log_task_completion(self, results: List[T]) -> None:
        """Log task completion with standard format and metrics."""
        import time

        if not self._start_time:
            return

        duration = time.time() - self._start_time
        success_count = len([r for r in results if r.success])
        failure_count = len([r for r in results if not r.success])

        logger.info(
            f"Completed task: {self.task_name} in {duration:.2f}s - "
            f"Success: {success_count}, Failures: {failure_count}"
        )

        if failure_count > 0:
            for result in results:
                if not result.success:
                    logger.error(f"{self.task_name} failure: {result.message}")

    @classmethod
    def get_result_class(cls) -> Type[RunnerResult]:
        """Get the result class for this task."""
        return cls.__orig_bases__[0].__args__[0]  # type: ignore

    async def validate(self, context: JobContext) -> bool:
        """Validate that the task can be executed.

        This method provides a validation pipeline:
        1. Configuration validation
        2. Resource availability validation
        3. Prerequisites validation
        4. Task-specific validation
        """
        try:
            logger.debug(f"Starting validation for {self.task_name}")

            # Step 1: Configuration validation
            if not await self._validate_config(context):
                logger.warning(f"{self.task_name}: Configuration validation failed")
                return False

            # Step 2: Resource availability validation
            if not await self._validate_resources(context):
                logger.debug(f"{self.task_name}: Resource validation failed")
                return False

            # Step 3: Prerequisites validation
            if not await self._validate_prerequisites(context):
                logger.debug(f"{self.task_name}: Prerequisites validation failed")
                return False

            # Step 4: Task-specific validation
            if not await self._validate_task_specific(context):
                logger.debug(f"{self.task_name}: Task-specific validation failed")
                return False

            logger.debug(f"{self.task_name}: All validation checks passed")
            return True
        except Exception as e:
            logger.error(
                f"Error in validation for {self.task_name}: {str(e)}", exc_info=True
            )
            return False

    async def _validate_config(self, context: JobContext) -> bool:
        """Validate task configuration."""
        return True

    async def _validate_prerequisites(self, context: JobContext) -> bool:
        """Validate task prerequisites."""
        return True

    async def _validate_resources(self, context: JobContext) -> bool:
        """Validate resource availability (network, APIs, etc.)."""
        return True

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate task-specific conditions."""
        return True

    async def execute(self, context: JobContext) -> List[T]:
        """Execute the task with given context."""
        self._log_task_start()
        results = []

        try:
            # Validate before execution
            if not await self.validate(context):
                logger.debug(f"{self.task_name}: Validation failed, skipping execution")
                result_class = self.get_result_class()
                return [result_class(success=False, message="Validation failed")]

            # Prepare context
            prepared_context = await self._prepare_context(context)

            # Execute the task implementation
            results = await self._execute_impl(prepared_context)
            self._log_task_completion(results)

        except Exception as e:
            logger.error(f"Error executing {self.task_name}: {str(e)}", exc_info=True)

            # Try custom error handling
            recovery_results = await self._handle_execution_error(e, context)
            if recovery_results is not None:
                results = recovery_results
                logger.info(f"Task {self.task_name} recovered from error: {str(e)}")
            else:
                # Default error handling
                result_class = self.get_result_class()
                results = [
                    result_class(
                        success=False,
                        message=f"Error executing task: {str(e)}",
                        error=e,
                    )
                ]

        finally:
            # Always perform cleanup
            try:
                await self._post_execution_cleanup(context, results)
            except Exception as cleanup_error:
                logger.warning(
                    f"Cleanup error in {self.task_name}: {str(cleanup_error)}"
                )

        return results

    @abstractmethod
    async def _execute_impl(self, context: JobContext) -> List[T]:
        """Implementation of task execution logic.
        This method should be implemented by subclasses."""
        pass

    async def _handle_execution_error(
        self, error: Exception, context: JobContext
    ) -> Optional[List[T]]:
        """Handle execution errors with recovery logic.

        Override this method to implement custom error recovery.
        Return None to use default error handling, or return results
        to continue as if execution succeeded.
        """
        return None

    async def _post_execution_cleanup(
        self, context: JobContext, results: List[T]
    ) -> None:
        """Perform cleanup after task execution.

        This is called after both successful and failed executions.
        Override this method to implement custom cleanup logic.
        """
        pass

    def _should_retry_on_error(self, error: Exception, context: JobContext) -> bool:
        """Determine if a specific error should trigger a retry.

        Override this method to implement custom retry logic based on error type.
        """
        # Default: retry on network errors, API timeouts, temporary failures
        retry_errors = (
            ConnectionError,
            TimeoutError,
            # Add more error types as needed
        )
        return isinstance(error, retry_errors)

    async def _prepare_context(self, context: JobContext) -> JobContext:
        """Prepare and enrich the job context before execution.

        Override this method to add task-specific context data.
        """
        return context
