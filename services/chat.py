import asyncio
import datetime
from concurrent.futures import ThreadPoolExecutor
from db.factory import db
from lib.logger import configure_logger
from lib.models import ProfileInfo
from services.crews import execute_chat_stream

# Configure logger
logger = configure_logger(__name__)


# Create a thread pool executor for running sync functions
thread_pool = ThreadPoolExecutor()
running_jobs = {}


async def process_chat_message(
    job_id: str,
    conversation_id: str,
    profile: ProfileInfo,
    input_str: str,
    history: list,
    output_queue: asyncio.Queue,
):
    """Process a chat message.

    Args:
        job_id (str): The ID of the job
        conversation_id (str): The ID of the conversation
        profile (ProfileInfo): The user's profile information
        input_str (str): The input string for the chat job
        history (list): The conversation history
        output_queue (asyncio.Queue): The output queue for WebSocket streaming

    Raises:
        Exception: If the chat message cannot be processed
    """
    try:
        results = []
        logger.debug(f"Starting chat stream for job {job_id}")

        # Add initial user message
        results.append(
            {
                "role": "user",
                "type": "user",
                "content": input_str,
                "timestamp": datetime.datetime.now().isoformat(),
            }
        )

        async for result in execute_chat_stream(profile, history, input_str):
            # Add to the output queue for WebSocket streaming
            stream_message = {
                "type": "stream",
                "stream_type": result.get("type", "result"),  # step, task, or result
                "content": result.get("content", ""),
                "tool": result.get("tool", None),
                "tool_input": result.get("tool_input", None),
                "result": result.get("result", None),
                "thought": result.get("thought", None),
                "timestamp": datetime.datetime.now().isoformat(),
                "job_started_at": datetime.datetime.now().isoformat(),
                "role": "assistant",
            }
            await output_queue.put(stream_message)

            # Build object in memory for later storage in db
            result_with_timestamp = {
                **result,
                "timestamp": datetime.datetime.now().isoformat(),
            }
            results.append(result_with_timestamp)

        # Store results in database
        # Get the final result from the last message
        final_result = results[-1] if results else None
        final_result_content = final_result.get("content", "") if final_result else ""

        db.add_job(
            profile_id=profile.id,
            conversation_id=conversation_id,
            crew_id=None,  # Default crew ID for chat specialist
            input_data=input_str,
            tokens=final_result.get("tokens", 0) if final_result else 0,
            result=final_result_content,
            messages=results,
        )
        logger.info(f"Chat job {job_id} completed and stored")

    except Exception as e:
        logger.error(f"Error in chat stream for job {job_id}: {str(e)}")
        raise
    finally:
        # Signal completion
        await output_queue.put(None)
        if job_id in running_jobs:
            del running_jobs[job_id]
