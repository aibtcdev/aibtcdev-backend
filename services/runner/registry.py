from typing import Any, Dict, List, Optional, Type

from lib.logger import configure_logger

from .base import BaseTask, JobType

logger = configure_logger(__name__)


class JobRegistry:
    """Registry for job runners."""

    _runners: Dict[JobType, Type[BaseTask]] = {}

    @classmethod
    def register(cls, job_type: JobType, runner_class: Type[BaseTask]) -> None:
        """Register a runner for a job type."""
        cls._runners[job_type] = runner_class
        logger.info(
            f"Registered runner {runner_class.__name__} for job type {job_type}"
        )

    @classmethod
    def get_runner(cls, job_type: JobType) -> Optional[Type[BaseTask]]:
        """Get runner for a job type."""
        return cls._runners.get(job_type)

    @classmethod
    def get_all_jobs(cls) -> Dict[str, Type[BaseTask]]:
        """Get all registered jobs."""
        return {str(job_type): runner for job_type, runner in cls._runners.items()}

    @classmethod
    def clear_registry(cls) -> None:
        """Clear all registered jobs (useful for testing)."""
        cls._runners.clear()
        logger.debug("Cleared job registry")


async def execute_runner_job(
    job_type: str, parameters: Optional[Dict[str, str]] = None
) -> List[Any]:
    """Execute a runner job with the specified type and parameters.

    Args:
        job_type: The type of job to execute
        parameters: Optional parameters for the job

    Returns:
        List of processing results
    """
    from .base import JobContext, RunnerConfig

    try:
        # Convert string to JobType enum
        try:
            job_enum = JobType(job_type.lower())
        except ValueError:
            logger.error(f"Unknown job type: {job_type}")
            raise ValueError(f"Unknown job type: {job_type}")

        # Get runner from registry
        runner_class = JobRegistry.get_runner(job_enum)
        if not runner_class:
            logger.error(f"No runner registered for job type: {job_type}")
            raise ValueError(f"No runner registered for job type: {job_type}")

        # Create context
        context = JobContext(
            job_type=job_enum, config=RunnerConfig(), parameters=parameters
        )

        # Create runner instance
        runner = runner_class()

        # Validate and execute
        logger.debug(f"Starting {job_type} runner")
        if await runner.validate(context):
            results = await runner.execute(context)
            logger.debug(f"Completed {job_type} runner")
            return results
        else:
            logger.warning(f"Validation failed for {job_type} runner")
            result_class = runner_class.get_result_class()
            return [
                result_class(
                    success=False, message=f"Validation failed for {job_type} runner"
                )
            ]

    except Exception as e:
        logger.error(f"Error in runner job: {str(e)}", exc_info=True)
        try:
            result_class = runner_class.get_result_class()
            return [
                result_class(
                    success=False, message=f"Error in runner job: {str(e)}", error=e
                )
            ]
        except Exception as inner_e:
            logger.critical(
                f"Could not create result object: {str(inner_e)}", exc_info=True
            )
            # Fallback to basic RunnerResult if all else fails
            from .base import RunnerResult

            return [RunnerResult(success=False, message=f"Critical error: {str(e)}")]
