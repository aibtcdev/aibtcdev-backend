import uuid
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from backend.factory import backend
from backend.models import JobBase, JobCreate, StepCreate, TaskFilter
from lib.logger import configure_logger
from lib.persona import generate_persona
from services.langgraph import execute_langgraph_stream
from tools.tools_factory import initialize_tools

logger = configure_logger(__name__)


async def execute_scheduled_job(agent_id: str, task_id: str, profile_id: str):
    """Execute a scheduled job with the given agent and task."""

    task = backend.get_task(task_id=uuid.UUID(task_id))
    if not task:
        logger.error(f"Task with ID {task_id} not found")
        return

    agent = backend.get_agent(agent_id=uuid.UUID(agent_id))
    if not agent:
        logger.error(f"Agent with ID {agent_id} not found")
        return

    profile = backend.get_profile(profile_id=uuid.UUID(profile_id))
    if not profile:
        logger.error(f"Profile with ID {profile_id} not found")
        return

    history = [
        {
            "role": "assistant",
            "content": "Sure, what exactly would you like to know?",
        },
    ]

    persona = generate_persona(agent)

    tools_map = initialize_tools(profile, agent.id)
    # if agent.agent_tools is not None:
    #     tools_map_filtered = filter_tools_by_names(agent.agent_tools, tools_map)
    # else:
    tools_map_filtered = tools_map
    stream_generator = execute_langgraph_stream(
        history=history,
        input_str=task.prompt,
        persona=persona,
        tools_map=tools_map_filtered,
    )
    history = [
        {
            "role": "assistant",
            "content": "Sure, what exactly would you like to know?",
        },
    ]

    job = backend.create_job(
        new_job=JobCreate(
            thread_id=None,
            input=task.prompt,
            agent_id=agent_id,
            task_id=task_id,
            profile_id=profile_id,
        )
    )
    async for event in stream_generator:
        if event["type"] == "tool":
            backend.create_step(
                new_step=StepCreate(
                    job_id=job.id,
                    agent_id=agent_id,
                    role="assistant",
                    tool=event["tool"],
                    tool_input=event["input"],
                    tool_output=event.get("output"),
                    profile_id=profile_id,
                )
            )
        elif event["type"] == "result":
            backend.create_step(
                new_step=StepCreate(
                    job_id=job.id,
                    content=event["content"],
                    role="assistant",
                    agent_id=agent_id,
                    profile_id=profile_id,
                )
            )
            backend.update_job(
                job_id=job.id,
                update_data=JobBase(
                    result=event["content"],
                ),
            )

    logger.info(f"Executing job with agent_id={agent_id} and task_id={task_id}")


async def sync_schedules(scheduler: AsyncIOScheduler):
    """Sync schedules from Supabase and update the scheduler."""
    try:
        schedules = backend.list_tasks(filters=TaskFilter(is_scheduled=True))

        valid_job_ids = {f"schedule_{str(schedule.id)}" for schedule in schedules}

        current_jobs = {
            job.id: job
            for job in scheduler.get_jobs()
            if job.id.startswith("schedule_")
        }

        jobs_to_remove = set(current_jobs.keys()) - valid_job_ids
        for job_id in jobs_to_remove:
            scheduler.remove_job(job_id)
            logger.info(f"Removed schedule {job_id} as it no longer exists in Supabase")

        for schedule in schedules:
            schedule_id = str(schedule.id)
            job_id = f"schedule_{schedule_id}"

            cron_expression = schedule.cron
            agent_id = str(schedule.agent_id)
            task_id = str(schedule.id)
            is_scheduled = schedule.is_scheduled
            profile_id = str(schedule.profile_id)

            if not all([cron_expression, agent_id, task_id]):
                logger.debug(f"Skipping invalid schedule: {schedule}")
                continue

            if not is_scheduled:
                if job_id in current_jobs:
                    scheduler.remove_job(job_id)
                    logger.info(f"Removed disabled schedule {job_id}")
                continue

            if job_id in current_jobs:
                current_job = current_jobs[job_id]

                if str(current_job.trigger) != str(
                    CronTrigger.from_crontab(cron_expression)
                ):
                    scheduler.remove_job(job_id)
                    scheduler.add_job(
                        execute_scheduled_job,
                        CronTrigger.from_crontab(cron_expression),
                        args=[agent_id, task_id, profile_id],
                        misfire_grace_time=60,
                        id=job_id,
                    )
                    logger.info(f"Updated schedule {job_id} with new cron expression")
            else:
                scheduler.add_job(
                    execute_scheduled_job,
                    CronTrigger.from_crontab(cron_expression),
                    args=[agent_id, task_id, profile_id],
                    misfire_grace_time=60,
                    id=job_id,
                )
                logger.info(f"Added new schedule {job_id}")

    except Exception as e:
        logger.error(f"Error syncing schedules: {str(e)}")
