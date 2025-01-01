import asyncio
import datetime
from backend.factory import backend
from backend.models import UUID, JobBase, Profile, StepCreate
from concurrent.futures import ThreadPoolExecutor
from lib.logger import configure_logger
from services.crews import execute_chat_stream, execute_chat_stream_langgraph

# Configure logger
logger = configure_logger(__name__)


# Create a thread pool executor for running sync functions
thread_pool = ThreadPoolExecutor()
running_jobs = {}


async def process_chat_message(
    job_id: UUID,
    conversation_id: UUID,
    profile: Profile,
    input_str: str,
    history: list,
    output_queue: asyncio.Queue,
):
    """Process a chat message.

    Args:
        job_id (UUID): The ID of the job
        conversation_id (UUID): The ID of the conversation
        profile (Profile): The user's profile information
        input_str (str): The input string for the chat job
        history (list): The conversation history
        output_queue (asyncio.Queue): The output queue for WebSocket streaming

    Raises:
        Exception: If the chat message cannot be processed
    """
    try:
        results = []
        logger.debug(f"Starting chat stream for job {job_id}")
        logger.debug(
            f"Input parameters - job_id: {job_id}, conversation_id: {conversation_id}, profile_id: {profile.id}"
        )

        # Add initial user message
        logger.debug("Adding initial user message to results")
        results.append(
            {
                "role": "user",
                "type": "user",
                "content": input_str,
                "timestamp": datetime.datetime.now().isoformat(),
            }
        )

        logger.debug("Starting chat stream execution")
        async for result in execute_chat_stream(profile, history, input_str):
            # Add to the output queue for WebSocket streaming
            logger.debug(
                f"Processing stream result of type: {result.get('type', 'unknown')}"
            )
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
            logger.debug("Putting message in output queue")
            await output_queue.put(stream_message)

            logger.debug("Creating step in backend")
            backend.create_step(
                new_step=StepCreate(
                    profile_id=profile.id,
                    job_id=job_id,
                    role="assistant",
                    content=stream_message["content"],
                    tool=stream_message["tool"],
                    tool_input=stream_message["tool_input"],
                    thought=stream_message["thought"],
                    result=stream_message["result"],
                )
            )
            # Build object in memory for later storage in db
            logger.debug("Adding result to results array")
            result_with_timestamp = {
                **result,
                "timestamp": datetime.datetime.now().isoformat(),
            }
            results.append(result_with_timestamp)

        # Store results in database
        logger.debug("Processing final results")
        # Get the final result from the last message
        final_result = results[-1] if results else None
        final_result_content = final_result.get("content", "") if final_result else ""

        logger.debug("Updating job in backend")
        backend.update_job(
            job_id=job_id,
            update_data=JobBase(
                profile_id=profile.id,
                conversation_id=conversation_id,
                input=input_str,
                result=final_result_content,
            ),
        )
        logger.info(f"Chat job {job_id} completed and stored")

    except Exception as e:
        logger.error(f"Error in chat stream for job {job_id}: {str(e)}")
        logger.exception("Full traceback:")
        raise
    finally:
        # Signal completion
        logger.debug(f"Cleaning up job {job_id}")
        await output_queue.put(None)
        if job_id in running_jobs:
            del running_jobs[job_id]
