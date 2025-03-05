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
            job_type=job_enum, config=RunnerConfig.from_env(), parameters=parameters
        )

        # Create runner instance
        runner = runner_class(context.config)

        # Validate and execute
        logger.info(f"Starting {job_type} runner")
        if await runner.validate(context):
            results = await runner.execute(context)
            logger.info(f"Completed {job_type} runner")
            return results
        else:
            logger.warning(f"Validation failed for {job_type} runner")
            return [
                runner_class.get_result_class()(
                    success=False, message=f"Validation failed for {job_type} runner"
                )
            ]

    except Exception as e:
        logger.error(f"Error in runner job: {str(e)}", exc_info=True)
        return [
            runner_class.get_result_class()(
                success=False, message=f"Error in runner job: {str(e)}", error=e
            )
        ]
