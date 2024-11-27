import asyncio
import json
import datetime
from db.helpers import add_job, get_enabled_crons_expanded
from services.crew_services import execute_crew_stream
from services.bot import send_message_to_user

# Define the maximum number of concurrent tasks
MAX_CONCURRENT_TASKS = 5


async def execute_cron_job():
    # log the cron
    print("Executing cron job")
    # Create a semaphore with the defined maximum concurrency
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)

    # Get all crons
    crons = get_enabled_crons_expanded()

    # For each cron, execute the task
    tasks = []
    for cron in crons:
        # Generate a unique task ID
        task = execute_single_wrapper(
            cron["profiles"]["id"],
            str(cron["profiles"]["account_index"]),
            cron["crew_id"],
            cron["input"],
            semaphore,
        )
        tasks.append(task)

    # Wait for all tasks to complete
    await asyncio.gather(*tasks)
    print("Cron job completed")


async def execute_single_wrapper(
    profile_id, account_index, crew_id, input_str, semaphore
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
            async for result in execute_crew_stream(account_index, crew_id, input_str):
                await output_queue.put(result)
                result["crew_id"] = crew_id
                result["timestamp"] = datetime.datetime.now().isoformat()
                results_array.append(json.dumps(result))
                
                # Send message about the result
                message = f"🤖 Crew Stream Result:\n\nInput: {input_str}\nResult: {result}"
                await send_message_to_user(profile_id, message)
                
            await output_queue.put(None)  # Signal completion
        except Exception as e:
            # Send error message
            error_message = f"❌ Crew Stream Failed:\n\nInput: {input_str}\nError: {str(e)}"
            await send_message_to_user(profile_id, error_message)
            raise e
        finally:
            add_job(
                profile_id,
                None,
                crew_id,
                input_str,
                "",
                results_array,
            )

    async with semaphore:
        await task_wrapper()
