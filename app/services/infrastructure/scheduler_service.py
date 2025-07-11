import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from apscheduler.job import Job
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.backend.factory import backend
from app.backend.models import Task, TaskFilter
from app.lib.logger import configure_logger
from app.lib.persona import generate_persona
from app.services.ai.simple_workflows import execute_workflow_stream
from app.tools.tools_factory import exclude_tools_by_names, initialize_tools

logger = configure_logger(__name__)


@dataclass
class ScheduleJobConfig:
    """Configuration for a scheduled job."""

    agent_id: str
    task_id: str
    profile_id: str
    cron_expression: str
    job_id: str


class SchedulerService:
    """Service class to manage scheduled jobs."""

    def __init__(self, scheduler: AsyncIOScheduler):
        self.scheduler = scheduler

    async def execute_job(self, agent_id: str, task_id: str, profile_id: str) -> None:
        """Execute a scheduled job with the given agent and task."""
        try:
            task = await self._get_task(task_id)
            if not task:
                return

            agent = await self._get_agent(agent_id)
            if not agent:
                return

            profile = await self._get_profile(profile_id)
            if not profile:
                return

            job = await self._create_job(task, agent_id, profile_id)
            if not job:
                return

            await self._process_job_stream(job, task, agent, profile)

        except Exception as e:
            logger.error(
                f"Error executing job: agent_id={agent_id}, task_id={task_id}, error={str(e)}"
            )
            raise

    async def sync_schedules(self) -> None:
        """Sync schedules from app.backend and update the scheduler."""
        try:
            schedules = await self._fetch_schedules()
            valid_job_ids = self._get_valid_job_ids(schedules)
            current_jobs = self._get_current_jobs()

            await self._remove_invalid_jobs(current_jobs, valid_job_ids)
            await self._update_or_add_jobs(schedules)

        except Exception as e:
            logger.error(f"Error syncing schedules: {str(e)}")
            raise

    async def _get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID with error handling."""
        try:
            task = backend.get_task(task_id=uuid.UUID(task_id))
            if not task:
                logger.error(f"Task with ID {task_id} not found")
            return task
        except Exception as e:
            logger.error(f"Error getting task {task_id}: {str(e)}")
            return None

    async def _get_agent(self, agent_id: str) -> Optional[Any]:
        """Get agent by ID with error handling."""
        try:
            agent = backend.get_agent(agent_id=uuid.UUID(agent_id))
            if not agent:
                logger.error(f"Agent with ID {agent_id} not found")
            return agent
        except Exception as e:
            logger.error(f"Error getting agent {agent_id}: {str(e)}")
            return None

    async def _get_profile(self, profile_id: str) -> Optional[Any]:
        """Get profile by ID with error handling."""
        try:
            profile = backend.get_profile(profile_id=uuid.UUID(profile_id))
            if not profile:
                logger.error(f"Profile with ID {profile_id} not found")
            return profile
        except Exception as e:
            logger.error(f"Error getting profile {profile_id}: {str(e)}")
            return None

    async def _create_job(
        self, task: Task, agent_id: str, profile_id: str
    ) -> Optional[Any]:
        """Job creation is no longer needed after removing chat functionality."""
        # Return a dummy job-like object with an ID for backward compatibility
        return type("Job", (), {"id": str(task.id)})()

    async def _process_job_stream(
        self, job: Any, task: Task, agent: Any, profile: Any
    ) -> None:
        """Process the job stream and create steps."""
        try:
            history = [
                {
                    "role": "assistant",
                    "content": "Sure, what exactly would you like to know?",
                }
            ]
            persona = generate_persona()
            tools_map = initialize_tools(profile, agent.id)
            tools_map_filtered = exclude_tools_by_names(
                ["db_update_scheduled_task", "db_add_scheduled_task"], tools_map
            )

            stream_generator = execute_workflow_stream(
                history=history,
                input_str=task.prompt,
                persona=persona,
                tools_map=tools_map_filtered,
            )

            async for event in stream_generator:
                await self._handle_stream_event(event, job, agent.id, profile.id)

        except Exception as e:
            logger.error(f"Error processing job stream: {str(e)}")
            raise

    async def _handle_stream_event(
        self, event: Dict[str, Any], job: Any, agent_id: str, profile_id: str
    ) -> None:
        """Handle individual stream events - step creation removed after chat functionality cleanup."""
        # Step and job tracking removed since chat functionality is no longer needed
        logger.debug(f"Processed stream event: {event.get('type', 'unknown')}")
        pass

    async def _fetch_schedules(self) -> List[Task]:
        """Fetch all scheduled tasks."""
        return backend.list_tasks(filters=TaskFilter(is_scheduled=True))

    def _get_valid_job_ids(self, schedules: List[Task]) -> Set[str]:
        """Get set of valid job IDs from schedules."""
        return {f"schedule_{str(schedule.id)}" for schedule in schedules}

    def _get_current_jobs(self) -> Dict[str, Job]:
        """Get dictionary of current scheduled jobs."""
        return {
            job.id: job
            for job in self.scheduler.get_jobs()
            if job.id.startswith("schedule_")
        }

    async def _remove_invalid_jobs(
        self, current_jobs: Dict[str, Job], valid_job_ids: Set[str]
    ) -> None:
        """Remove jobs that are no longer valid."""
        jobs_to_remove = set(current_jobs.keys()) - valid_job_ids
        for job_id in jobs_to_remove:
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed schedule {job_id} as it no longer exists in backend")

    async def _update_or_add_jobs(self, schedules: List[Task]) -> None:
        """Update existing jobs or add new ones."""
        for schedule in schedules:
            config = self._create_job_config(schedule)
            if not config:
                continue

            if not schedule.is_scheduled:
                self._handle_disabled_job(config.job_id)
                continue

            await self._update_or_add_job(config)

    def _create_job_config(self, schedule: Task) -> Optional[ScheduleJobConfig]:
        """Create job configuration from schedule."""
        try:
            return ScheduleJobConfig(
                agent_id=str(schedule.agent_id),
                task_id=str(schedule.id),
                profile_id=str(schedule.profile_id),
                cron_expression=schedule.cron,
                job_id=f"schedule_{str(schedule.id)}",
            )
        except Exception as e:
            logger.error(
                f"Error creating job config for schedule {schedule.id}: {str(e)}"
            )
            return None

    def _handle_disabled_job(self, job_id: str) -> None:
        """Handle disabled job by removing it if it exists."""
        if job_id in self._get_current_jobs():
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed disabled schedule {job_id}")

    async def _update_or_add_job(self, config: ScheduleJobConfig) -> None:
        """Update existing job or add new one."""
        try:
            current_jobs = self._get_current_jobs()

            if config.job_id in current_jobs:
                current_job = current_jobs[config.job_id]
                if str(current_job.trigger) != str(
                    CronTrigger.from_crontab(config.cron_expression)
                ):
                    self._update_job(config)
            else:
                self._add_job(config)

        except Exception as e:
            logger.error(f"Error updating/adding job {config.job_id}: {str(e)}")

    def _update_job(self, config: ScheduleJobConfig) -> None:
        """Update existing job with new configuration."""
        self.scheduler.remove_job(config.job_id)
        self._add_job(config)
        logger.info(f"Updated schedule {config.job_id} with new cron expression")

    def _add_job(self, config: ScheduleJobConfig) -> None:
        """Add new job to scheduler."""
        self.scheduler.add_job(
            self.execute_job,
            CronTrigger.from_crontab(config.cron_expression),
            args=[config.agent_id, config.task_id, config.profile_id],
            misfire_grace_time=60,
            id=config.job_id,
        )
        logger.info(f"Added new schedule {config.job_id}")


# Initialize global scheduler service
_scheduler_service: Optional[SchedulerService] = None


def get_scheduler_service(
    scheduler: Optional[AsyncIOScheduler] = None,
) -> SchedulerService:
    """Get or create the scheduler service singleton."""
    global _scheduler_service
    if _scheduler_service is None and scheduler is not None:
        _scheduler_service = SchedulerService(scheduler)
    elif _scheduler_service is None:
        raise ValueError("Scheduler must be provided when initializing service")
    return _scheduler_service


async def execute_scheduled_job(agent_id: str, task_id: str, profile_id: str) -> None:
    """Execute a scheduled job with the given agent and task."""
    service = get_scheduler_service()
    await service.execute_job(agent_id, task_id, profile_id)


async def sync_schedules(scheduler: AsyncIOScheduler) -> None:
    """Sync schedules from app.backend and update the scheduler."""
    service = get_scheduler_service(scheduler)
    await service.sync_schedules()
