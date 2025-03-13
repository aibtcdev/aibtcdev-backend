"""Tests for the job manager module."""

from unittest.mock import MagicMock, patch

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from services.runner.job_manager import JobManager


class TestJobManager:
    """Test cases for JobManager class."""

    def test_get_all_jobs(self):
        """Test that get_all_jobs returns a list of job configurations."""
        with patch("services.runner.job_manager.config") as mock_config:
            # Set up mock config
            mock_config.twitter.enabled = True
            mock_config.twitter.interval_seconds = 60
            mock_config.scheduler.sync_enabled = True
            mock_config.scheduler.sync_interval_seconds = 120
            mock_config.scheduler.dao_runner_enabled = True
            mock_config.scheduler.dao_runner_interval_seconds = 30
            mock_config.scheduler.tweet_runner_enabled = False

            # Call the method
            jobs = JobManager.get_all_jobs()

            # Verify results
            assert len(jobs) >= 5  # At least 5 jobs should be returned

            # Verify some specific jobs
            twitter_job = next((j for j in jobs if j.name == "Twitter Service"), None)
            assert twitter_job is not None
            assert twitter_job.enabled is True
            assert twitter_job.seconds == 60

            dao_job = next((j for j in jobs if j.name == "DAO Runner Service"), None)
            assert dao_job is not None
            assert dao_job.enabled is True
            assert dao_job.seconds == 30

            tweet_job = next(
                (j for j in jobs if j.name == "Tweet Runner Service"), None
            )
            assert tweet_job is not None
            assert tweet_job.enabled is False

    def test_schedule_jobs(self):
        """Test scheduling jobs."""
        # Create mock scheduler
        mock_scheduler = MagicMock(spec=AsyncIOScheduler)

        with (
            patch(
                "services.runner.job_manager.JobManager.get_all_jobs"
            ) as mock_get_jobs,
            patch(
                "services.runner.job_manager.execute_twitter_job"
            ) as mock_twitter_func,
            patch("services.runner.job_manager.sync_schedules") as mock_sync_func,
        ):
            # Create mock jobs
            mock_jobs = [
                MagicMock(
                    name="Twitter Service",
                    enabled=True,
                    func=mock_twitter_func,
                    seconds=60,
                    args=None,
                    job_id="twitter_service",
                ),
                MagicMock(
                    name="Disabled Service",
                    enabled=False,
                    func=MagicMock(),
                    seconds=30,
                    args=None,
                    job_id="disabled_service",
                ),
            ]
            mock_get_jobs.return_value = mock_jobs

            # Call the method
            result = JobManager.schedule_jobs(mock_scheduler)

            # Verify results
            assert result is True  # At least one job was enabled
            mock_scheduler.add_job.assert_called_once()

            # Verify the job was added with the correct parameters
            args, kwargs = mock_scheduler.add_job.call_args
            assert args[0] == mock_twitter_func
            assert kwargs["seconds"] == 60
            assert kwargs["id"] == "twitter_service"
