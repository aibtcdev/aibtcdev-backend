import asyncio
import datetime
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TypedDict
from uuid import UUID

from backend.factory import backend
from backend.models import JobBase, JobFilter, Profile, StepCreate, StepFilter
from lib.logger import configure_logger
from lib.persona import generate_persona, generate_static_persona
from services.workflows import execute_preplan_react_stream
from tools.tools_factory import initialize_tools

logger = configure_logger(__name__)


class JobInfo(TypedDict):
    """Information about a running job."""

    queue: asyncio.Queue
    thread_id: UUID
    agent_id: Optional[UUID]
    task: Optional[asyncio.Task]
    connection_active: bool


thread_pool = ThreadPoolExecutor()
running_jobs: Dict[UUID, JobInfo] = {}


@dataclass
class Message:
    content: str
    type: str
    thread_id: str
    tool: Optional[str] = None
    tool_input: Optional[str] = None
    tool_output: Optional[str] = None
    agent_id: Optional[str] = None
    role: str = "assistant"
    status: Optional[str] = None
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


class MessageHandler:
    def process_token_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process a token message and prepare it for streaming."""
        return {
            "type": "token",
            "status": "processing",
            "content": message.get("content", ""),
            "created_at": datetime.datetime.now().isoformat(),
            "role": "assistant",
            "thread_id": message.get("thread_id"),
            "agent_id": message.get("agent_id"),
        }


class ToolExecutionHandler:
    def process_tool_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process a tool execution message."""
        return {
            "role": "assistant",
            "type": "tool",
            "tool": message.get("tool"),
            "tool_input": message.get("input"),
            "tool_output": message.get("output"),
            "created_at": datetime.datetime.now().isoformat(),
            "thread_id": message.get("thread_id"),
            "agent_id": message.get("agent_id"),
        }


class ChatProcessor:
    def __init__(
        self,
        job_id: UUID,
        thread_id: UUID,
        profile: Profile,
        agent_id: Optional[UUID],
        input_str: str,
        history: List[Dict[str, Any]],
        output_queue: asyncio.Queue,
    ):
        self.job_id = job_id
        self.thread_id = thread_id
        self.profile = profile
        self.agent_id = agent_id
        self.input_str = input_str
        self.history = history
        self.output_queue = output_queue
        self.results: List[Dict[str, Any]] = []
        self.message_handler = MessageHandler()
        self.tool_handler = ToolExecutionHandler()
        self.current_message = self._create_empty_message()
        self.connection_active = True  # Flag to track if WebSocket is still connected

    def _create_empty_message(self) -> Dict[str, Any]:
        """Create an empty message template."""
        return Message(
            content="",
            type="result",
            thread_id=str(self.thread_id),
            agent_id=str(self.agent_id) if self.agent_id else None,
        ).to_dict()

    async def _handle_tool_execution(
        self, tool_name: str, tool_input: str, tool_output: str, tool_phase: str
    ) -> None:
        """Handle tool execution messages."""
        if tool_phase == "end":
            try:
                new_step = StepCreate(
                    profile_id=self.profile.id,
                    job_id=self.job_id,
                    agent_id=self.agent_id,
                    role="assistant",
                    tool=tool_name,
                    tool_input=tool_input,
                    tool_output=tool_output,
                )
                backend.create_step(new_step=new_step)
            except Exception as e:
                logger.error(f"Error creating tool execution step: {e}")
                raise
        elif tool_phase == "start":
            tool_execution = self.tool_handler.process_tool_message(
                {
                    "tool": tool_name,
                    "input": tool_input,
                    "output": tool_output,
                    "thread_id": str(self.thread_id),
                    "agent_id": str(self.agent_id) if self.agent_id else None,
                }
            )
            self.results.append(tool_execution)
            # Only send to the client if the connection is still active
            if self.connection_active:
                await self.output_queue.put(tool_execution)

    async def process_stream(self) -> None:
        """Process the chat stream and handle different message types."""
        try:
            # Add initial user message
            self.results.append(
                {
                    "role": "user",
                    "type": "user",
                    "content": self.input_str,
                    "timestamp": datetime.datetime.now().isoformat(),
                }
            )

            if self.agent_id:
                agent = backend.get_agent(agent_id=self.agent_id)
                if not agent:
                    logger.error(f"Agent with ID {self.agent_id} not found")
                    return
                persona = generate_persona(agent)
            else:
                persona = generate_static_persona()

            tools_map = initialize_tools(self.profile, agent_id=self.agent_id)
            first_end = True

            logger.info(
                f"Starting preplan_react_stream with input: {self.input_str[:50]}..."
            )
            result_count = 0

            async for result in execute_preplan_react_stream(
                self.history, self.input_str, persona, tools_map
            ):
                result_count += 1
                logger.debug(
                    f"Received result #{result_count} of type: {result.get('type')}"
                )
                await self._process_stream_result(result, first_end)
                if result.get("type") == "end" and first_end:
                    first_end = False

            logger.info(f"Processed {result_count} results from preplan_react_stream")
            await self._finalize_processing()

        except Exception as e:
            logger.error(f"Error in chat stream for job {self.job_id}: {str(e)}")
            logger.exception("Full traceback:")
            raise
        finally:
            await self._cleanup()

    async def _process_stream_result(
        self, result: Dict[str, Any], first_end: bool
    ) -> None:
        """Process a single stream result."""
        logger.debug(f"Processing stream result type: {result.get('type')}")

        # Check both local and global connection state
        job_id_str = str(self.job_id)
        is_connected = self.connection_active and (
            job_id_str not in running_jobs
            or running_jobs[job_id_str]["connection_active"]
        )

        if not is_connected:
            # Skip sending to output queue if connection is no longer active
            logger.debug(
                f"Skipping output for disconnected client on job {self.job_id}"
            )
            if result.get("type") == "token":
                # Skip token messages entirely for disconnected clients
                return

        if result.get("type") == "end":
            if not first_end and is_connected:
                try:
                    await self.output_queue.put(
                        Message(
                            type="token",
                            status="end",
                            content="",
                            thread_id=str(self.thread_id),
                            role="assistant",
                            agent_id=str(self.agent_id) if self.agent_id else None,
                            created_at=datetime.datetime.now().isoformat(),
                        ).to_dict()
                    )
                except Exception as e:
                    logger.debug(
                        f"Failed to send end token to disconnected client: {e}"
                    )
                    self.connection_active = False
                    if job_id_str in running_jobs:
                        running_jobs[job_id_str]["connection_active"] = False
            return

        if result.get("type") == "token" and not result.get("content"):
            return

        if result.get("type") == "tool":
            await self._handle_tool_execution(
                str(result.get("tool", "")),
                str(result.get("input", "")),
                str(result.get("output", "")),
                str(result.get("status", "")),
            )
            self.current_message = self._create_empty_message()
            return

        if result.get("content"):
            if result.get("type") == "token" and is_connected:
                try:
                    stream_message = self.message_handler.process_token_message(
                        {
                            "content": result.get("content", ""),
                            "thread_id": str(self.thread_id),
                            "agent_id": str(self.agent_id) if self.agent_id else None,
                        }
                    )
                    await self.output_queue.put(stream_message)
                except Exception as e:
                    logger.debug(f"Failed to send token to disconnected client: {e}")
                    self.connection_active = False
                    if job_id_str in running_jobs:
                        running_jobs[job_id_str]["connection_active"] = False
            elif result.get("type") == "result":
                logger.info(
                    f"Received result message with content length: {len(result.get('content', ''))}"
                )
                self.current_message["content"] = result.get("content", "")

                # Create step in the database
                logger.info(f"Creating step in database for job {self.job_id}")
                backend.create_step(
                    new_step=StepCreate(
                        profile_id=self.profile.id,
                        job_id=self.job_id,
                        agent_id=self.agent_id,
                        role="assistant",
                        content=self.current_message["content"],
                        tool=None,
                        tool_input=None,
                        thought=None,
                        tool_output=None,
                    )
                )

                # Add to results
                self.results.append(
                    {
                        **self.current_message,
                        "timestamp": datetime.datetime.now().isoformat(),
                    }
                )

    async def _finalize_processing(self) -> None:
        """Finalize the chat processing and update the job."""
        logger.info(f"Finalizing processing for job {self.job_id}")
        logger.debug(f"Results count: {len(self.results)}")

        final_result = None
        for result in reversed(self.results):
            if result.get("content"):
                final_result = result
                break

        final_result_content = final_result.get("content", "") if final_result else ""
        logger.info(f"Final result content length: {len(final_result_content)}")

        logger.info(f"Updating job {self.job_id} in database")
        backend.update_job(
            job_id=self.job_id,
            update_data=JobBase(
                profile_id=self.profile.id,
                thread_id=self.thread_id,
                input=self.input_str,
                result=final_result_content,
            ),
        )
        logger.info(f"Chat job {self.job_id} completed and stored")

    async def _cleanup(self) -> None:
        """Clean up resources after processing."""
        logger.debug(f"Cleaning up job {self.job_id}")
        await self.output_queue.put(None)
        if self.job_id in running_jobs:
            del running_jobs[self.job_id]


async def process_chat_message(
    job_id: UUID,
    thread_id: UUID,
    profile: Profile,
    agent_id: Optional[UUID],
    input_str: str,
    history: List[Dict[str, Any]],
    output_queue: asyncio.Queue,
) -> None:
    """Process a chat message.

    Args:
        job_id (UUID): The ID of the job
        thread_id (UUID): The ID of the thread
        profile (Profile): The user's profile information
        agent_id (Optional[UUID]): The ID of the agent
        input_str (str): The input string for the chat job
        history (List[Dict[str, Any]]): The thread history
        output_queue (asyncio.Queue): The output queue for WebSocket streaming

    Raises:
        Exception: If the chat message cannot be processed
    """
    # Initialize job info in running_jobs
    job_id_str = str(job_id)
    running_jobs[job_id_str] = {
        "queue": output_queue,
        "thread_id": thread_id,
        "agent_id": agent_id,
        "task": None,
        "connection_active": True,
    }

    processor = ChatProcessor(
        job_id=job_id,
        thread_id=thread_id,
        profile=profile,
        agent_id=agent_id,
        input_str=input_str,
        history=history,
        output_queue=output_queue,
    )

    try:
        await processor.process_stream()
    except Exception as e:
        logger.error(f"Error processing chat message: {e}")
        raise
    finally:
        # Clean up job info
        if job_id_str in running_jobs:
            del running_jobs[job_id_str]


def get_job_history(thread_id: UUID, profile_id: UUID) -> List[Dict[str, Any]]:
    """Get the chat history for a specific job.

    Args:
        thread_id (UUID): The ID of the thread
        profile_id (UUID): The ID of the profile

    Returns:
        List[Dict[str, Any]]: List of formatted chat messages
    """
    logger.debug(
        f"Fetching job history for thread {thread_id} and profile {profile_id}"
    )
    jobs = backend.list_jobs(filters=JobFilter(thread_id=thread_id))
    formatted_history = []
    for job in jobs:
        if job.profile_id == profile_id:
            formatted_history.append(
                {
                    "role": "user",
                    "content": job.input,
                    "created_at": job.created_at.isoformat(),
                    "thread_id": str(thread_id),
                }
            )
            formatted_history.append(
                {
                    "role": "assistant",
                    "content": job.result,
                    "created_at": job.created_at.isoformat(),
                    "thread_id": str(thread_id),
                }
            )
    logger.debug(f"Found {len(formatted_history)} messages in job history")
    return formatted_history


def get_thread_history(thread_id: UUID, profile_id: UUID) -> List[Dict[str, Any]]:
    """Get the complete thread history including all steps.

    Args:
        thread_id (UUID): The ID of the thread
        profile_id (UUID): The ID of the profile

    Returns:
        List[Dict[str, Any]]: List of formatted chat messages and steps
    """
    logger.debug(
        f"Fetching thread history for thread {thread_id} and profile {profile_id}"
    )
    thread = backend.get_thread(thread_id=thread_id)
    if thread.profile_id != profile_id:
        logger.warning(f"Profile {profile_id} not authorized for thread {thread_id}")
        return []

    jobs = backend.list_jobs(filters=JobFilter(thread_id=thread.id))
    formatted_history = []
    if jobs:
        for job in jobs:
            logger.debug(f"Processing job {job}")
            # Add user input message
            formatted_history.append(
                {
                    "role": "user",
                    "content": job.input,
                    "created_at": job.created_at.isoformat(),
                    "thread_id": str(thread.id),
                    "type": "user",
                }
            )

            steps = backend.list_steps(filters=StepFilter(job_id=job.id))
            if not steps:
                continue
            for step in steps:
                type = "tool" if step.tool else "step"
                formatted_msg = {
                    "role": step.role,
                    "content": step.content,
                    "created_at": step.created_at.isoformat(),
                    "tool": step.tool,
                    "tool_input": step.tool_input,
                    "tool_output": step.tool_output,
                    "agent_id": str(step.agent_id),
                    "thread_id": str(thread.id),
                    "type": type,
                }
                formatted_history.append(formatted_msg)

        # Sort messages by timestamp
        formatted_history.sort(key=lambda x: x["created_at"])

    logger.debug(f"Found {len(formatted_history)} messages in thread history")
    return formatted_history


def mark_job_disconnected(job_id: UUID) -> None:
    """Mark a job as having its WebSocket connection disconnected.

    Args:
        job_id (UUID): The ID of the job to mark as disconnected
    """
    job_id_str = str(job_id)
    if job_id_str in running_jobs:
        logger.info(f"Marking job {job_id} as disconnected")
        running_jobs[job_id_str]["connection_active"] = False
