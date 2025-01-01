import asyncio
import datetime
import os
from backend.factory import backend
from backend.models import UUID, JobBase, Profile, StepCreate
from concurrent.futures import ThreadPoolExecutor
from lib.logger import configure_logger
from services.crews import execute_chat_stream, execute_chat_stream_langgraph

# Configure logger
logger = configure_logger(__name__)

# Configure chat settings
USE_LANGGRAPH = os.getenv("AIBTC_USE_LANGGRAPH", "false").lower() == "true"

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
        logger.debug(
            f"Using {'langgraph' if USE_LANGGRAPH else 'standard'} implementation"
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
        stream_func = (
            execute_chat_stream_langgraph if USE_LANGGRAPH else execute_chat_stream
        )

        if USE_LANGGRAPH:
            # For langgraph, accumulate tokens and only save complete messages
            current_message = {
                "content": "",
                "type": "result",
                "tool": None,
                "tool_input": None,
                "result": None,
                "thought": None,
            }

            logger.debug("Starting to process stream")
            async for result in stream_func(profile, history, input_str):
                logger.debug(
                    f"Processing stream result - "
                    f"type: {result.get('type', 'unknown')}, "
                    f"content: {bool(result.get('content'))}, "
                    f"tool: {bool(result.get('tool'))}, "
                    f"input: {bool(result.get('input'))}, "
                    f"output: {bool(result.get('output'))}, "
                    f"raw: {result}"
                )

                # Handle end message first to ensure we capture subsequent tool execution
                if result.get("type") == "end":
                    logger.debug("Processing end message")
                    # Only stream the end message, don't save or reset yet
                    stream_message = {
                        "type": "stream",
                        "stream_type": "end",
                        "content": "",
                        "timestamp": datetime.datetime.now().isoformat(),
                        "job_started_at": datetime.datetime.now().isoformat(),
                        "role": "assistant",
                    }
                    logger.debug("Putting end message in output queue")
                    await output_queue.put(stream_message)
                    continue

                # Skip empty content for token messages
                if result.get("type") == "token" and not result.get("content"):
                    logger.debug("Skipping empty token message")
                    continue

                # Handle tool execution
                if result.get("type") == "tool_execution":
                    logger.debug(
                        f"Tool execution detected - "
                        f"tool: {result.get('tool')}, "
                        f"input: {result.get('input')}, "
                        f"output: {result.get('output')}, "
                        f"raw: {result}"
                    )
                    
                    # Ensure all values are strings
                    tool_name = str(result.get("tool", ""))
                    tool_input = str(result.get("input", ""))
                    tool_output = str(result.get("output", ""))
                    
                    logger.debug(f"Processed tool values - name: {tool_name}, input: {tool_input}, output: {tool_output}")
                    
                    # Save any accumulated content first
                    if current_message["content"]:
                        logger.debug(f"Saving accumulated content: {current_message}")
                        try:
                            backend.create_step(
                                new_step=StepCreate(
                                    profile_id=profile.id,
                                    job_id=job_id,
                                    role="assistant",
                                    content=current_message["content"],
                                    tool=None,
                                    tool_input=None,
                                    thought=None,
                                    result=None,
                                )
                            )
                            logger.debug("Successfully saved accumulated content")
                        except Exception as e:
                            logger.error(f"Error saving accumulated content: {e}")
                        
                        results.append(
                            {
                                **current_message,
                                "timestamp": datetime.datetime.now().isoformat(),
                            }
                        )

                    # Create a new step for the tool execution
                    logger.debug("Creating tool execution step")
                    try:
                        new_step = StepCreate(
                            profile_id=profile.id,
                            job_id=job_id,
                            role="assistant",
                            content="",  # Content will be in the result
                            tool=tool_name,
                            tool_input=tool_input,
                            thought=None,
                            result=tool_output
                        )
                        logger.debug(f"Created StepCreate object: {new_step}")
                        created_step = backend.create_step(new_step=new_step)
                        logger.debug(f"Successfully created tool execution step: {created_step}")
                    except Exception as e:
                        logger.error(f"Error creating tool execution step: {e}")
                    
                    # Add to results for streaming
                    results.append({
                        "role": "assistant",
                        "type": "tool",
                        "tool": tool_name,
                        "tool_input": tool_input,
                        "result": tool_output,
                        "timestamp": datetime.datetime.now().isoformat(),
                    })
                    
                    # Reset current message
                    current_message = {
                        "content": "",
                        "type": "result",
                        "tool": None,
                        "tool_input": None,
                        "result": None,
                        "thought": None,
                    }
                    continue

                # Handle regular content
                if result.get("content"):
                    # Stream message to the client
                    stream_message = {
                        "type": "stream",
                        "stream_type": result.get("type", "token"),
                        "content": result.get("content", ""),
                        "timestamp": datetime.datetime.now().isoformat(),
                        "job_started_at": datetime.datetime.now().isoformat(),
                        "role": "assistant",
                    }
                    logger.debug(
                        f"Putting message in output queue - type: {stream_message['stream_type']}"
                    )
                    await output_queue.put(stream_message)

                    # Accumulate content
                    current_message["content"] += result.get("content", "")
                    logger.debug(
                        f"Accumulated content length: {len(current_message['content'])}"
                    )

            # After the loop, save any remaining content
            if current_message["content"]:
                logger.debug(
                    f"Saving final content - length: {len(current_message['content'])}"
                )
                backend.create_step(
                    new_step=StepCreate(
                        profile_id=profile.id,
                        job_id=job_id,
                        role="assistant",
                        content=current_message["content"],
                        tool=None,
                        tool_input=None,
                        thought=None,
                        result=None,
                    )
                )
                results.append(
                    {
                        **current_message,
                        "timestamp": datetime.datetime.now().isoformat(),
                    }
                )
        else:
            # Standard implementation - save each message as it comes
            async for result in stream_func(profile, history, input_str):
                # Add to the output queue for WebSocket streaming
                logger.debug(
                    f"Processing stream result of type: {result.get('type', 'unknown')}"
                )
                stream_message = {
                    "type": "stream",
                    "stream_type": result.get(
                        "type", "result"
                    ),  # step, task, or result
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
        # Get the final result from the last non-empty message
        final_result = None
        for result in reversed(results):
            if result.get("content"):
                final_result = result
                break

        final_result_content = final_result.get("content", "") if final_result else ""
        logger.debug(f"Final result content length: {len(final_result_content)}")

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
