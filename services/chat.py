import asyncio
import datetime
from backend.factory import backend
from backend.models import UUID, JobBase, Profile, StepCreate
from concurrent.futures import ThreadPoolExecutor
from lib.logger import configure_logger
from lib.persona import generate_persona, generate_static_persona
from services.langgraph import execute_langgraph_stream
from tools.tools_factory import initialize_tools
from typing import Optional

logger = configure_logger(__name__)

thread_pool = ThreadPoolExecutor()
running_jobs = {}


async def process_chat_message(
    job_id: UUID,
    thread_id: UUID,
    profile: Profile,
    agent_id: Optional[UUID],
    input_str: str,
    history: list,
    output_queue: asyncio.Queue,
):
    """Process a chat message.

    Args:
        job_id (UUID): The ID of the job
        thread_id (UUID): The ID of the thread
        profile (Profile): The user's profile information
        input_str (str): The input string for the chat job
        history (list): The thread history
        output_queue (asyncio.Queue): The output queue for WebSocket streaming

    Raises:
        Exception: If the chat message cannot be processed
    """
    try:
        results = []
        first_end = True

        # Add initial user message
        results.append(
            {
                "role": "user",
                "type": "user",
                "content": input_str,
                "timestamp": datetime.datetime.now().isoformat(),
            }
        )

        # For langgraph, accumulate tokens and only save complete messages
        current_message = {
            "content": "",
            "type": "result",
            "thread_id": str(thread_id),
            "tool": None,
            "tool_input": None,
            "tool_output": None,
            "agent_id": str(agent_id) if agent_id else None,
        }

        if agent_id:
            agent = backend.get_agent(agent_id=agent_id)
            if not agent:
                logger.error(f"Agent with ID {agent_id} not found")
                return
            persona = generate_persona(agent)
        else:
            persona = generate_static_persona()

        tools_map = initialize_tools(profile, agent_id=agent_id, crewai=False)

        async for result in execute_langgraph_stream(
            history, input_str, persona, tools_map
        ):

            # Handle end message first to ensure we capture subsequent tool execution
            if result.get("type") == "end":
                if first_end:
                    first_end = False
                    continue

                # Only stream the end message, don't save or reset yet
                stream_message = {
                    "type": "token",
                    "thread_id": str(thread_id),
                    "status": "end",
                    "content": "",
                    "created_at": datetime.datetime.now().isoformat(),
                    "role": "assistant",
                    "agent_id": str(agent_id) if agent_id else None,
                }
                await output_queue.put(stream_message)
                continue

            # Skip empty content for token messages
            if result.get("type") == "token" and not result.get("content"):
                continue

            # Handle tool execution
            if result.get("type") == "tool":
                # Ensure all values are strings
                tool_name = str(result.get("tool", ""))
                tool_input = str(result.get("input", ""))
                tool_output = str(result.get("output", ""))
                tool_phase = str(result.get("status", ""))

                # check if tools, inputs and outputs are keys in result
                if tool_phase == "end":
                    # Create a new step for the tool execution
                    logger.debug("Creating tool execution step")
                    try:
                        new_step = StepCreate(
                            profile_id=profile.id,
                            job_id=job_id,
                            agent_id=agent_id,
                            role="assistant",
                            tool=tool_name,
                            tool_input=tool_input,
                            tool_output=tool_output,
                        )
                        backend.create_step(new_step=new_step)
                    except Exception as e:
                        logger.error(f"Error creating tool execution step: {e}")
                elif tool_phase == "start":
                    # Add to results for streaming
                    tool_execution = {
                        "role": "assistant",
                        "type": "tool",
                        "tool": tool_name,
                        "tool_input": tool_input,
                        "tool_output": tool_output,
                        "created_at": datetime.datetime.now().isoformat(),
                        "thread_id": str(thread_id),
                        "agent_id": str(agent_id) if agent_id else None,
                    }
                    results.append(tool_execution)
                    await output_queue.put(tool_execution)

                # Reset current message
                current_message = {
                    "content": "",
                    "type": "result",
                    "tool": None,
                    "tool_input": None,
                    "tool_output": None,
                    "thread_id": str(thread_id),
                    "agent_id": str(agent_id) if agent_id else None,
                }
                continue

            if result.get("content"):
                if result.get("type") == "token":
                    stream_message = {
                        "agent_id": str(agent_id) if agent_id else None,
                        "role": "assistant",
                        "type": "token",
                        "status": "processing",
                        "content": result.get("content", ""),
                        "created_at": datetime.datetime.now().isoformat(),
                        "thread_id": str(thread_id),
                    }
                    await output_queue.put(stream_message)
                elif result.get("type") == "result":
                    current_message["content"] = result.get("content", "")
                    backend.create_step(
                        new_step=StepCreate(
                            profile_id=profile.id,
                            job_id=job_id,
                            agent_id=agent_id,
                            role="assistant",
                            content=current_message["content"],
                            tool=None,
                            tool_input=None,
                            thought=None,
                            tool_output=None,
                        )
                    )
                    results.append(
                        {
                            **current_message,
                            "timestamp": datetime.datetime.now().isoformat(),
                        }
                    )

        final_result = None
        for result in reversed(results):
            if result.get("content"):
                final_result = result
                break

        final_result_content = final_result.get("content", "") if final_result else ""

        backend.update_job(
            job_id=job_id,
            update_data=JobBase(
                profile_id=profile.id,
                thread_id=thread_id,
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
