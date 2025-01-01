import asyncio
import datetime
import json
import os
from backend.factory import backend
from backend.models import CronFilter, Profile, StepCreate
from lib.logger import configure_logger
from services.bot import send_message_to_user
from services.crews import execute_crew_stream

# Configure logger
logger = configure_logger(__name__)

# Get the maximum number of concurrent cron tasks from environment variables
AIBTC_CRON_MAX_CONCURRENT_TASKS = int(os.getenv("AIBTC_CRON_MAX_CONCURRENT_TASKS", 5))


async def execute_cron_job():
    # log the cron
    logger.info("Executing cron job")
    # Create a semaphore with the defined maximum concurrency
    semaphore = asyncio.Semaphore(AIBTC_CRON_MAX_CONCURRENT_TASKS)

    # Get all crons
    crons = backend.list_crons(filters=CronFilter(is_enabled=True))

    # For each cron, execute the task
    tasks = []
    for cron in crons:
        # Generate a unique task ID
        profile = backend.get_profile(cron.profile_id)

        profile = Profile(
            account_index=profile.account_index,
            id=cron.profile_id,
        )
        task = execute_single_wrapper(
            profile,
            cron.crew_id,
            cron.input,
            semaphore,
        )
        tasks.append(task)

    # Wait for all tasks to complete
    await asyncio.gather(*tasks)
    logger.info("Cron job completed")


async def execute_single_wrapper(
    profile: Profile, crew_id: str, input_str: str, semaphore: asyncio.Semaphore
):
    output_queue = asyncio.Queue()
    results_array = []

    results_array.append(
        json.dumps(
            {
                "role": "user",
                "type": "user",
                "content": input_str,
                "timestamp": datetime.datetime.now().isoformat(),
            }
        )
    )

    async def task_wrapper():
        try:
            # Run the actual crew stream task, yielding output to the queue
            async for result in execute_crew_stream(profile, crew_id, input_str):
                await output_queue.put(result)
                result["crew_id"] = crew_id
                result["timestamp"] = datetime.datetime.now().isoformat()
                results_array.append(json.dumps(result))

                # Send message about the result
                message = (
                    f"🤖 Crew Stream Result:\n\nInput: {input_str}\nResult: {result}"
                )
                await send_message_to_user(profile.id, message)
                logger.debug(f"Crew stream result sent for crew_id={crew_id}")

            await output_queue.put(None)  # Signal completion
            logger.info(f"Crew stream completed successfully for crew_id={crew_id}")
        except Exception as e:
            # Log the error
            logger.error(f"Crew stream failed for crew_id={crew_id}: {str(e)}")
            # Send error message
            error_message = (
                f"❌ Crew Stream Failed:\n\nInput: {input_str}\nError: {str(e)}"
            )
            await send_message_to_user(profile.id, error_message)
            raise e
        finally:
            logger.debug(f"Saving chat results for job {job_id}")

            final_result = json.loads(results_array[-1]) if results_array else None
            final_result_content = (
                final_result.get("content", "") if final_result else ""
            )

            job_object = backend.create_job(
                profile_id=profile.id,
                crew_id=crew_id,
                input=input_str,
                result=final_result_content,
            )
            if job_object:
                for message in results_array:
                    backend.create_step(
                        new_step=StepCreate(
                            profile_id=profile.id,
                            job_id=job_object.id,
                            role="assistant",
                            content=message,
                        )
                    )
            logger.debug(f"Job added to history for crew_id={crew_id}")

    async with semaphore:
        await task_wrapper()
