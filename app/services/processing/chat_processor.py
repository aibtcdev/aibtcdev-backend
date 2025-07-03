import asyncio
import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.backend.factory import backend
from app.backend.models import JobBase, Profile, StepCreate
from app.lib.logger import configure_logger
from app.lib.persona import generate_persona, generate_static_persona
from app.services.communication.websocket_service import websocket_manager
from app.services.ai.workflows import execute_workflow_stream
from app.services.processing.message_handler import (
    Message,
    MessageHandler,
    StepMessageHandler,
    ToolExecutionHandler,
)
from app.services.processing.streaming_service import running_jobs
from app.tools.tools_factory import initialize_tools

logger = configure_logger(__name__)


class ChatProcessor:
    """Processes chat messages and manages streaming responses."""

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
        """Initialize the chat processor.

        Args:
            job_id: The ID of the job
            thread_id: The ID of the thread
            profile: The user's profile
            agent_id: Optional agent ID
            input_str: The input message
            history: Chat history
            output_queue: Queue for streaming output
        """
        self.job_id = job_id
        self.thread_id = thread_id
        self.profile = profile
        self.agent_id = agent_id
        self.input_str = input_str
        self.history = history
        self.output_queue = output_queue
        self.results: List[Dict[str, Any]] = []
        self.message_handler = MessageHandler()
        self.step_handler = StepMessageHandler()
        self.tool_handler = ToolExecutionHandler()
        self.current_message = self._create_empty_message()
        self.connection_active = True  # Flag to track if WebSocket is still connected

        # Buffer for aggregating tokens
        self.token_buffer = ""
        self.last_token_time = None

    def _create_empty_message(self) -> Dict[str, Any]:
        """Create an empty message template."""
        return Message(
            content="",
            type="result",
            status="complete",  # Add default status
            thread_id=str(self.thread_id),
            agent_id=str(self.agent_id) if self.agent_id else None,
        ).to_dict()

    async def _safe_send_message(self, message: Dict[str, Any]) -> bool:
        """Safely send a message through the output queue.

        Args:
            message: The message to send

        Returns:
            bool: True if message was sent successfully, False if connection is inactive
        """
        job_id_str = str(self.job_id)
        if not self.connection_active or (
            job_id_str in running_jobs
            and not running_jobs[job_id_str]["connection_active"]
        ):
            logger.debug(
                f"Skipping message send for disconnected client on job {self.job_id}"
            )
            return False

        try:
            await asyncio.wait_for(
                self.output_queue.put(message), timeout=1.0
            )  # Add 1 second timeout
            return True
        except (asyncio.TimeoutError, Exception) as e:
            logger.debug(f"Failed to send message to client: {e}")
            self.connection_active = False
            if job_id_str in running_jobs:
                running_jobs[job_id_str]["connection_active"] = False
            return False

    async def _handle_tool_execution(
        self, tool_name: str, tool_input: str, tool_output: str, tool_phase: str
    ) -> None:
        """Handle tool execution messages.

        Args:
            tool_name: The name of the tool being executed
            tool_input: The input provided to the tool
            tool_output: The output returned by the tool (empty for start phase)
            tool_phase: The phase of tool execution: always "processing" for both start/end
        """
        # Determine if this is start or end phase based on tool_output
        # Empty output indicates start phase, non-empty indicates end phase
        is_start_phase = not bool(tool_output)
        is_error = "error" in tool_phase.lower()

        # Set appropriate database status based on the phase we determined
        if is_error:
            status = "error"
        elif is_start_phase:
            status = "processing"  # Start phase always maps to processing
        else:
            status = "complete"  # End phase (with output) maps to complete

        # Create a step in the database for every tool phase
        try:
            new_step = StepCreate(
                profile_id=self.profile.id,
                job_id=self.job_id,
                agent_id=self.agent_id,
                role="assistant",
                tool=tool_name,
                tool_input=tool_input,
                tool_output=tool_output,
                status=status,
            )
            backend.create_step(new_step=new_step)
            phase_type = (
                "start" if is_start_phase else "end" if not is_error else "error"
            )
            logger.info(
                f"Created tool execution step for {tool_name}, phase: {phase_type}, with status: {status}"
            )
        except Exception as e:
            logger.error(f"Error creating tool execution step: {e}")
            raise

        # Send message to client for tool visualization
        tool_execution = self.tool_handler.process_tool_message(
            {
                "tool": tool_name,
                "input": tool_input,
                "output": tool_output,
                "thread_id": str(self.thread_id),
                "agent_id": str(self.agent_id) if self.agent_id else None,
                "status": tool_phase,  # Use the original status for client-side display
            }
        )
        self.results.append(tool_execution)
        await self._safe_send_message(tool_execution)

    async def _process_stream_result(
        self, result: Dict[str, Any], first_end: bool
    ) -> None:
        """Process a single stream result."""
        logger.debug(
            f"Processing stream result type: {result.get('type')}, status: {result.get('status')}"
        )

        # Early return for token messages if disconnected
        if not self.connection_active and result.get("type") == "token":
            return

        if result.get("type") == "end":
            # If we have accumulated tokens, save them as a complete step before ending
            # Only do this if we haven't received a final result message yet
            if self.token_buffer and not self.current_message.get("content"):
                logger.info(
                    f"Saving token buffer at end, length: {len(self.token_buffer)}"
                )
                backend.create_step(
                    new_step=StepCreate(
                        profile_id=self.profile.id,
                        job_id=self.job_id,
                        agent_id=self.agent_id,
                        role="assistant",
                        content=self.token_buffer.strip(),
                        tool=None,
                        tool_input=None,
                        thought=None,
                        tool_output=None,
                        status="complete",  # Mark as complete since we're at the end
                    )
                )
                # Update current message to prevent duplicate saves
                self.current_message["content"] = self.token_buffer.strip()
                self.token_buffer = ""  # Clear the buffer

            if not first_end:
                message = Message(
                    type="token",
                    status="complete",
                    content="",
                    thread_id=str(self.thread_id),
                    role="assistant",
                    agent_id=str(self.agent_id) if self.agent_id else None,
                    created_at=datetime.datetime.now().isoformat(),
                ).to_dict()
                await self._safe_send_message(message)
            return

        if result.get("type") == "token" and not result.get("content"):
            return

        if result.get("type") == "step":
            # Handle planning step messages - these are already complete steps
            step_message = self.step_handler.process_step_message(
                {
                    "content": result.get("content", ""),
                    "thought": result.get("thought"),
                    "thread_id": str(self.thread_id),
                    "agent_id": str(self.agent_id) if self.agent_id else None,
                    "created_at": result.get(
                        "created_at", datetime.datetime.now().isoformat()
                    ),
                }
            )

            # Save planning steps directly to database - these are not streamed tokens
            backend.create_step(
                new_step=StepCreate(
                    profile_id=self.profile.id,
                    job_id=self.job_id,
                    agent_id=self.agent_id,
                    role="assistant",
                    content=result.get("content", ""),
                    tool=None,
                    tool_input=None,
                    thought="Planning Phase",  # Consistently use "Planning Phase" as thought for planning steps
                    tool_output=None,
                    status="planning",  # Store planning status explicitly
                )
            )

            # Add to results and send to client
            self.results.append(step_message)
            await self._safe_send_message(step_message)

            # Don't create an additional token message for this plan content
            # as it would duplicate in the UI
            return

        if result.get("type") == "tool":
            # If we have tokens in the buffer when a tool is called, save them first
            if self.token_buffer:
                backend.create_step(
                    new_step=StepCreate(
                        profile_id=self.profile.id,
                        job_id=self.job_id,
                        agent_id=self.agent_id,
                        role="assistant",
                        content=self.token_buffer.strip(),
                        tool=None,
                        tool_input=None,
                        thought=None,
                        tool_output=None,
                        status="processing",  # Mark as processing since we're in the middle
                    )
                )
                self.token_buffer = ""  # Clear the buffer

            await self._handle_tool_execution(
                str(result.get("tool", "")),
                str(result.get("input", "")),
                str(result.get("output", "")),
                str(result.get("status", "")),
            )
            self.current_message = self._create_empty_message()
            return

        if result.get("content"):
            if result.get("type") == "token":
                # Skip token messages if they're part of planning content that's already been sent
                if result.get("planning_only", False):
                    logger.debug(
                        "Skipping planning token that's already been sent as a step"
                    )
                    return

                # Set the status explicitly for processing tokens
                status = result.get("status", "processing")

                # Create a stream message for real-time display to the user
                stream_message = self.message_handler.process_token_message(
                    {
                        "content": result.get("content", ""),
                        "status": status,
                        "thread_id": str(self.thread_id),
                        "agent_id": str(self.agent_id) if self.agent_id else None,
                    }
                )

                # Add token to buffer instead of saving each one to the database
                content = result.get("content", "")
                if content:
                    self.token_buffer += content
                    self.last_token_time = datetime.datetime.now()

                # Send the token to the user for streaming
                await self._safe_send_message(stream_message)

            elif result.get("type") == "result":
                # This is the final result message - save it directly
                logger.info(
                    f"Received result message with content length: {len(result.get('content', ''))}"
                )
                content = result.get("content", "")

                # Make sure content is properly formatted - no joined words
                # (this is likely unnecessary but added as a safeguard)
                if content and len(content) > 100:  # Only for longer content
                    logger.debug("Ensuring proper formatting of result content")

                # Clear any token buffer since we have a final result - we won't need it
                # since we're saving the whole result directly
                self.token_buffer = ""

                # Only save if this is different from what we already have
                if content != self.current_message.get("content"):
                    self.current_message["content"] = content
                    self.current_message["status"] = (
                        "complete"  # Final message is complete
                    )

                    # Create step in the database with the final result
                    logger.info(
                        f"Creating final result step in database for job {self.job_id}"
                    )
                    backend.create_step(
                        new_step=StepCreate(
                            profile_id=self.profile.id,
                            job_id=self.job_id,
                            agent_id=self.agent_id,
                            role="assistant",
                            content=content,
                            tool=None,
                            tool_input=None,
                            thought=None,
                            tool_output=None,
                            status="complete",  # Explicitly set status for completion
                        )
                    )

                    # Add to results
                    self.results.append(
                        {
                            **self.current_message,
                            "timestamp": datetime.datetime.now().isoformat(),
                        }
                    )
                else:
                    logger.info(
                        "Skipping duplicate result save - content already saved"
                    )

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
                persona = generate_persona()
            else:
                persona = generate_static_persona()

            tools_map = initialize_tools(self.profile, agent_id=self.agent_id)
            first_end = True

            # Determine vector collections
            vector_collections = None
            if self.agent_id:
                agent_config = (
                    agent.config if agent and hasattr(agent, "config") else {}
                )
                vector_collections = (
                    agent_config.get("vector_collections") if agent_config else None
                )

            if not vector_collections:
                vector_collections = ["dao_collection", "knowledge_collection"]
                logger.info(
                    f"No vector collections configured, defaulting to: {vector_collections}"
                )

            workflow_type = "vector_preplan"
            logger.info(
                f"Starting {workflow_type} workflow with collections: {vector_collections}"
            )

            logger.info(
                f"Starting {workflow_type} workflow with input: {self.input_str[:50]}..."
            )
            result_count = 0

            # Use the unified workflow interface
            async for result in execute_workflow_stream(
                workflow_type=workflow_type,
                history=self.history,
                input_str=self.input_str,
                persona=persona,
                tools_map=tools_map,
                vector_collections=vector_collections,  # Use the new parameter name
            ):
                result_count += 1
                logger.debug(
                    f"Received result #{result_count} of type: {result.get('type')}"
                )
                await self._process_stream_result(result, first_end)
                if result.get("type") == "end" and first_end:
                    first_end = False

            logger.info(
                f"Processed {result_count} results from {workflow_type} workflow"
            )

            # If we have any tokens remaining in the buffer AND we haven't received a final result
            # message, save the buffer contents as the final response
            if (
                self.token_buffer
                and self.token_buffer.strip()
                and not self.current_message.get("content")
            ):
                logger.info(
                    f"Saving remaining token buffer as final step, length: {len(self.token_buffer)}"
                )
                backend.create_step(
                    new_step=StepCreate(
                        profile_id=self.profile.id,
                        job_id=self.job_id,
                        agent_id=self.agent_id,
                        role="assistant",
                        content=self.token_buffer.strip(),
                        tool=None,
                        tool_input=None,
                        thought=None,
                        tool_output=None,
                        status="complete",  # Mark as complete since we're at the end
                    )
                )
                # Update current message so it's included in the job result
                self.current_message["content"] = self.token_buffer.strip()
                self.token_buffer = ""  # Clear the buffer

            await self._finalize_processing()

        except Exception as e:
            logger.error(f"Error in chat stream for job {self.job_id}: {str(e)}")
            logger.exception("Full traceback:")
            raise
        finally:
            await self._cleanup()

    async def _finalize_processing(self) -> None:
        """Finalize the chat processing and update the job."""
        logger.info(f"Finalizing processing for job {self.job_id}")
        logger.debug(f"Results count: {len(self.results)}")

        # First try to use the current_message content if it exists
        final_result_content = self.current_message.get("content", "")

        # If we don't have content in the current_message, search through results
        if not final_result_content:
            # Look for results with content, excluding planning steps
            content_results = [
                result
                for result in self.results
                if result.get("content")
                and result.get("type") != "step"
                and result.get("status") != "planning"
            ]

            # Sort by most recent content first (to get the last message)
            if content_results:
                content_results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
                final_result = content_results[0]
                final_result_content = final_result.get("content", "")
                logger.info(
                    f"Found final content in results list with length: {len(final_result_content)}"
                )
            else:
                logger.warning("No content results found in results list")
        else:
            logger.info(
                f"Using current_message content with length: {len(final_result_content)}"
            )

        # As a fallback, retrieve steps from the database to find the final content
        if not final_result_content:
            logger.info("No final content found in memory, checking database steps")
            from app.backend.models import StepFilter

            steps = backend.list_steps(filters=StepFilter(job_id=self.job_id))

            # Filter to complete steps that aren't planning or tool steps
            final_steps = [
                step
                for step in steps
                if step.status == "complete"
                and step.content
                and not step.tool
                and (not step.thought or step.thought != "Planning Phase")
            ]

            if final_steps:
                # Use the most recent complete step
                final_step = max(final_steps, key=lambda s: s.created_at)
                final_result_content = final_step.content
                logger.info(
                    f"Found final content in database with length: {len(final_result_content)}"
                )

        # Log the final content length
        logger.info(f"Final result content length: {len(final_result_content)}")

        # Update job with the final result
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

        # Send final completion message through WebSocket
        await websocket_manager.send_message(
            {
                "type": "completion",
                "status": "complete",
                "message": "Processing complete",
                "thread_id": str(self.thread_id),
                "agent_id": str(self.agent_id) if self.agent_id else None,
            },
            str(self.job_id),
        )

    async def _cleanup(self) -> None:
        """Clean up resources after processing."""
        logger.debug(f"Cleaning up job {self.job_id}")
        job_id_str = str(self.job_id)

        # Only try to send None if connection is still active
        if (
            self.connection_active
            and job_id_str in running_jobs
            and running_jobs[job_id_str]["connection_active"]
        ):
            try:
                await self.output_queue.put(None)
            except Exception as e:
                logger.debug(f"Failed to send cleanup message: {e}")
                # Don't raise the exception, just log it

        # Always clean up the running jobs entry
        if job_id_str in running_jobs:
            del running_jobs[job_id_str]
