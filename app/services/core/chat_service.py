import asyncio
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.backend.factory import backend
from app.backend.models import JobFilter, Profile, StepFilter
from app.lib.logger import configure_logger
from app.services.processing.chat_processor import ChatProcessor
from app.services.processing.streaming_service import running_jobs

logger = configure_logger(__name__)


class ChatService:
    """Main service for chat processing and management."""

    @staticmethod
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
            job_id: The ID of the job
            thread_id: The ID of the thread
            profile: The user's profile
            agent_id: Optional agent ID
            input_str: The input message
            history: Chat history
            output_queue: Queue for streaming output
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

    @staticmethod
    def get_job_history(thread_id: UUID, profile_id: UUID) -> List[Dict[str, Any]]:
        """Get the chat history for a specific job.

        Args:
            thread_id: The ID of the thread
            profile_id: The ID of the profile

        Returns:
            List of formatted chat messages
        """
        logger.debug(
            f"Fetching job history for thread {thread_id} and profile {profile_id}"
        )
        jobs = backend.list_jobs(filters=JobFilter(thread_id=thread_id))
        formatted_history = []
        for job in jobs:
            if job.profile_id == profile_id:
                # Get all steps first to determine proper timing
                steps = backend.list_steps(filters=StepFilter(job_id=job.id))

                # Create a timeline of all messages per job
                job_messages = []

                # Add user message
                job_messages.append(
                    {
                        "role": "user",
                        "content": job.input,
                        "created_at": job.created_at.isoformat(),
                        "thread_id": str(thread_id),
                        "type": "user",
                    }
                )

                # Add planning steps with original timestamps
                planning_steps = [
                    step
                    for step in steps
                    if step.status == "planning" or step.thought == "Planning Phase"
                ]
                for step in planning_steps:
                    job_messages.append(
                        {
                            "role": "assistant",
                            "content": step.content,
                            "created_at": step.created_at.isoformat(),
                            "thread_id": str(thread_id),
                            "type": "step",
                            "status": "planning",
                            "thought": step.thought,
                        }
                    )

                # Add the final response with correct timestamp
                has_final_result = job.result and job.result.strip()
                if has_final_result:
                    # For the final result, look for its step to get the correct timestamp
                    final_step = None
                    for step in steps:
                        if step.status == "complete" and step.content == job.result:
                            final_step = step
                            break

                    # Use the job's result as the primary response
                    job_messages.append(
                        {
                            "role": "assistant",
                            "content": job.result,
                            "created_at": (
                                final_step.created_at.isoformat()
                                if final_step
                                else job.created_at.isoformat()
                            ),
                            "thread_id": str(thread_id),
                            "type": "token",
                            "status": "complete",
                        }
                    )
                else:
                    # If no job result, look for complete step content
                    final_steps = [
                        step
                        for step in steps
                        if step.status == "complete" and step.content and not step.tool
                    ]

                    if final_steps:
                        # Use the last complete step's content
                        final_step = max(final_steps, key=lambda s: s.created_at)
                        job_messages.append(
                            {
                                "role": "assistant",
                                "content": final_step.content,
                                "created_at": final_step.created_at.isoformat(),
                                "thread_id": str(thread_id),
                                "type": "token",
                                "status": "complete",
                            }
                        )
                    elif steps:
                        # No complete steps with content, use all non-tool steps to reconstruct
                        content_steps = [
                            step
                            for step in steps
                            if step.content
                            and not step.tool
                            and step.status != "planning"
                        ]

                        if content_steps:
                            # Sort by creation time
                            content_steps.sort(key=lambda s: s.created_at)
                            # Use all content joined together
                            combined_content = " ".join(
                                step.content for step in content_steps
                            )

                            job_messages.append(
                                {
                                    "role": "assistant",
                                    "content": combined_content,
                                    "created_at": job.created_at.isoformat(),
                                    "thread_id": str(thread_id),
                                    "type": "token",
                                    "status": "complete",
                                }
                            )

                # Add tool steps with their original timestamps
                for step in steps:
                    if step.tool:
                        tool_msg = {
                            "role": "assistant",
                            "type": "tool",
                            "status": step.status or "complete",
                            "tool": step.tool,
                            "tool_input": step.tool_input,
                            "tool_output": step.tool_output,
                            "created_at": step.created_at.isoformat(),
                            "thread_id": str(thread_id),
                        }
                        if step.agent_id:
                            tool_msg["agent_id"] = str(step.agent_id)
                        job_messages.append(tool_msg)

                # Sort this job's messages by timestamp
                job_messages.sort(key=lambda x: x["created_at"])

                # Add all job messages to the history
                formatted_history.extend(job_messages)

        # Sort the full history again to ensure proper ordering
        formatted_history.sort(key=lambda x: x["created_at"])

        logger.debug(f"Found {len(formatted_history)} messages in job history")
        return formatted_history

    @staticmethod
    def get_thread_history(thread_id: UUID, profile_id: UUID) -> List[Dict[str, Any]]:
        """Get the complete thread history including all steps.

        Args:
            thread_id: The ID of the thread
            profile_id: The ID of the profile

        Returns:
            List of formatted chat messages and steps
        """
        logger.debug(
            f"Fetching thread history for thread {thread_id} and profile {profile_id}"
        )
        thread = backend.get_thread(thread_id=thread_id)
        if thread.profile_id != profile_id:
            logger.warning(
                f"Profile {profile_id} not authorized for thread {thread_id}"
            )
            return []

        jobs = backend.list_jobs(filters=JobFilter(thread_id=thread.id))
        formatted_history = []
        if jobs:
            for job in jobs:
                logger.debug(f"Processing job {job}")
                # Get all steps for this job first to determine proper timing
                steps = backend.list_steps(filters=StepFilter(job_id=job.id))

                # Create a timeline of all messages per job
                job_messages = []

                # Add user input message
                job_messages.append(
                    {
                        "role": "user",
                        "content": job.input,
                        "created_at": job.created_at.isoformat(),
                        "thread_id": str(thread.id),
                        "type": "user",
                    }
                )

                # Add planning steps with their original timestamps
                planning_steps = [
                    step
                    for step in steps
                    if step.status == "planning" or step.thought == "Planning Phase"
                ]
                for step in planning_steps:
                    job_messages.append(
                        {
                            "role": step.role,
                            "content": step.content,
                            "created_at": step.created_at.isoformat(),
                            "thought": step.thought,
                            "thread_id": str(thread.id),
                            "type": "step",
                            "status": "planning",
                        }
                    )

                # Add result or final content with correct timestamp
                has_final_result = job.result and job.result.strip()
                if has_final_result:
                    # For the final result, look for its step to get the correct timestamp
                    final_step = None
                    for step in steps:
                        if step.status == "complete" and step.content == job.result:
                            final_step = step
                            break

                    # Use the job's result
                    job_messages.append(
                        {
                            "role": "assistant",
                            "content": job.result,
                            "created_at": (
                                final_step.created_at.isoformat()
                                if final_step
                                else job.created_at.isoformat()
                            ),
                            "thread_id": str(thread.id),
                            "type": "token",
                            "status": "complete",
                        }
                    )
                else:
                    # No result in job, find the final step's content
                    final_steps = [
                        step
                        for step in steps
                        if step.status == "complete" and step.content and not step.tool
                    ]

                    if final_steps:
                        # Use the last complete step's content
                        final_step = max(final_steps, key=lambda s: s.created_at)
                        job_messages.append(
                            {
                                "role": "assistant",
                                "content": final_step.content,
                                "created_at": final_step.created_at.isoformat(),
                                "thread_id": str(thread.id),
                                "type": "token",
                                "status": "complete",
                            }
                        )

                # Add tool steps with their original timestamps
                for step in steps:
                    if step.tool:
                        tool_msg = {
                            "role": "assistant",
                            "content": step.content if step.content else "",
                            "created_at": step.created_at.isoformat(),
                            "thread_id": str(thread.id),
                            "type": "tool",
                            "status": step.status or "complete",
                            "tool": step.tool,
                            "tool_input": step.tool_input,
                            "tool_output": step.tool_output,
                        }
                        if step.agent_id:
                            tool_msg["agent_id"] = str(step.agent_id)
                        job_messages.append(tool_msg)

                # Sort this job's messages by timestamp
                job_messages.sort(key=lambda x: x["created_at"])

                # Add all job messages to the history
                formatted_history.extend(job_messages)

        logger.debug(f"Found {len(formatted_history)} messages in thread history")
        return formatted_history


# For backward compatibility
process_chat_message = ChatService.process_chat_message
get_job_history = ChatService.get_job_history
get_thread_history = ChatService.get_thread_history
