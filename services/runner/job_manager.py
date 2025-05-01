"""Job management utilities for the runner service."""

from dataclasses import dataclass
from typing import Any, Callable, List, Optional, cast

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import config
from lib.logger import configure_logger

from .base import JobType
from .registry import execute_runner_job

logger = configure_logger(__name__)


@dataclass
class JobConfig:
    """Configuration for a scheduled job."""

    name: str
    enabled: bool
    func: Callable
    seconds: int
    args: Optional[List[Any]] = None
    job_id: Optional[str] = None


class JobManager:
    """Manager for scheduled jobs."""

    @staticmethod
    def get_all_jobs() -> List[JobConfig]:
        """Get configurations for all available jobs.

        Returns:
            List of job configurations
        """
        # Static configurations for built-in jobs
        jobs = [
            JobConfig(
                name="Twitter Service",
                enabled=config.twitter.enabled,
                func=cast(
                    Callable, "execute_twitter_job"
                ),  # Import at runtime to avoid circular imports
                seconds=config.twitter.interval_seconds,
                job_id="twitter_service",
            ),
            JobConfig(
                name="Schedule Sync Service",
                enabled=config.scheduler.sync_enabled,
                func=cast(
                    Callable, "sync_schedules"
                ),  # Import at runtime to avoid circular imports
                seconds=config.scheduler.sync_interval_seconds,
                args=[
                    "scheduler"
                ],  # Special case - will be replaced with actual scheduler
                job_id="schedule_sync_service",
            ),
        ]

        # Add runner jobs (could be extended with more job types)
        runner_jobs = [
            (
                "DAO Runner Service",
                config.scheduler.dao_runner_enabled,
                config.scheduler.dao_runner_interval_seconds,
                JobType.DAO.value,
            ),
            (
                "DAO Tweet Runner Service",
                config.scheduler.dao_tweet_runner_enabled,
                config.scheduler.dao_tweet_runner_interval_seconds,
                JobType.DAO_TWEET.value,
            ),
            (
                "Tweet Runner Service",
                config.scheduler.tweet_runner_enabled,
                config.scheduler.tweet_runner_interval_seconds,
                JobType.TWEET.value,
            ),
            (
                "DAO Proposal Vote Runner Service",
                config.scheduler.dao_proposal_vote_runner_enabled,
                config.scheduler.dao_proposal_vote_runner_interval_seconds,
                JobType.DAO_PROPOSAL_VOTE.value,
            ),
            (
                "DAO Proposal Conclude Runner Service",
                config.scheduler.dao_proposal_conclude_runner_enabled,
                config.scheduler.dao_proposal_conclude_runner_interval_seconds,
                JobType.DAO_PROPOSAL_CONCLUDE.value,
            ),
            (
                "DAO Proposal Evaluation Runner Service",
                config.scheduler.dao_proposal_evaluation_runner_enabled,
                config.scheduler.dao_proposal_evaluation_runner_interval_seconds,
                JobType.DAO_PROPOSAL_EVALUATION.value,
            ),
            (
                "Agent Account Deploy Runner Service",
                config.scheduler.agent_account_deploy_runner_enabled,
                config.scheduler.agent_account_deploy_runner_interval_seconds,
                JobType.AGENT_ACCOUNT_DEPLOY.value,
            ),
        ]

        # Add all runner jobs with common structure
        for name, enabled, seconds, job_type in runner_jobs:
            jobs.append(
                JobConfig(
                    name=name,
                    enabled=enabled,
                    func=execute_runner_job,
                    seconds=seconds,
                    args=[job_type],
                    job_id=f"{job_type}_runner",
                )
            )

        return jobs

    @staticmethod
    def schedule_jobs(scheduler: AsyncIOScheduler) -> bool:
        """Schedule all enabled jobs.

        Args:
            scheduler: The scheduler to add jobs to

        Returns:
            True if any jobs were scheduled, False otherwise
        """
        # Import at runtime to avoid circular imports
        from services.schedule import sync_schedules
        from services.twitter import execute_twitter_job

        # Get all job configurations
        jobs = JobManager.get_all_jobs()

        # Map function names to actual functions
        func_map = {
            "execute_twitter_job": execute_twitter_job,
            "sync_schedules": sync_schedules,
        }

        # Add enabled jobs to the scheduler
        any_enabled = False
        for job in jobs:
            if job.enabled:
                any_enabled = True

                # Handle special cases
                job_func = job.func
                if isinstance(job_func, str):
                    job_func = func_map.get(job_func, job_func)

                job_args = {}
                if job.args:
                    # Special case for scheduler argument
                    if "scheduler" in job.args:
                        job_args["args"] = [scheduler]
                    else:
                        job_args["args"] = job.args

                # Add the job with a specific ID for easier management
                job_id = job.job_id or f"{job.name.lower().replace(' ', '_')}"
                scheduler.add_job(
                    job_func, "interval", seconds=job.seconds, id=job_id, **job_args
                )
                logger.info(
                    f"{job.name} started with interval of {job.seconds} seconds"
                )
            else:
                logger.info(f"{job.name} is disabled")

        return any_enabled
