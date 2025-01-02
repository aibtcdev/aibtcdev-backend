from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from backend.factory import backend
from backend.models import TaskFilter
from datetime import datetime
from lib.logger import configure_logger

logger = configure_logger(__name__)


async def execute_scheduled_job(agent_id: str, task_id: str):
    """Execute a scheduled job with the given agent and task."""
    logger.info(
        f"Would have executed job with agent_id={agent_id} and task_id={task_id} at {datetime.now()}"
    )


async def sync_schedules(scheduler: AsyncIOScheduler):
    """Sync schedules from Supabase and update the scheduler."""
    try:
        # Fetch all schedules from Supabase
        schedules = backend.list_tasks(filters=TaskFilter(is_scheduled=True))

        # Create a set of valid schedule IDs from Supabase
        valid_job_ids = {f"schedule_{str(schedule.id)}" for schedule in schedules}

        # Get all current jobs from the scheduler that start with "schedule_"
        current_jobs = {
            job.id: job
            for job in scheduler.get_jobs()
            if job.id.startswith("schedule_")
        }

        # Remove jobs that don't exist in Supabase anymore
        jobs_to_remove = set(current_jobs.keys()) - valid_job_ids
        for job_id in jobs_to_remove:
            scheduler.remove_job(job_id)
            logger.info(f"Removed schedule {job_id} as it no longer exists in Supabase")

        # Process each schedule from Supabase
        for schedule in schedules:
            logger.debug(f"Processing schedule: {schedule}")
            schedule_id = str(schedule.id)
            job_id = f"schedule_{schedule_id}"

            # Parse the schedule data
            cron_expression = schedule.cron
            agent_id = str(schedule.agent_id)
            task_id = str(schedule.id)
            is_scheduled = schedule.is_scheduled

            if not all([cron_expression, agent_id, task_id]):
                logger.debug(f"Skipping invalid schedule: {schedule}")
                continue

            # Skip disabled schedules and remove their jobs if they exist
            if not is_scheduled:
                if job_id in current_jobs:
                    scheduler.remove_job(job_id)
                    logger.info(f"Removed disabled schedule {job_id}")
                continue

            # If job exists, update it if needed
            if job_id in current_jobs:
                current_job = current_jobs[job_id]

                # Check if we need to update the job
                if str(current_job.trigger) != str(
                    CronTrigger.from_crontab(cron_expression)
                ):
                    scheduler.remove_job(job_id)
                    scheduler.add_job(
                        execute_scheduled_job,
                        CronTrigger.from_crontab(cron_expression),
                        args=[agent_id, task_id],
                        id=job_id,
                    )
                    logger.info(f"Updated schedule {job_id} with new cron expression")
            else:
                # Add new job
                scheduler.add_job(
                    execute_scheduled_job,
                    CronTrigger.from_crontab(cron_expression),
                    args=[agent_id, task_id],
                    id=job_id,
                )
                logger.info(f"Added new schedule {job_id}")

    except Exception as e:
        logger.error(f"Error syncing schedules: {str(e)}")
