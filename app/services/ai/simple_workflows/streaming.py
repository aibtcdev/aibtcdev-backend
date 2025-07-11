"""Simplified streaming callback handler.

This module provides a minimal streaming interface that preserves the existing
queue-based streaming API while removing unnecessary complexity.
"""

import asyncio
import datetime
import uuid
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.callbacks import BaseCallbackHandler

from app.lib.logger import configure_logger

logger = configure_logger(__name__)


class StreamingError(Exception):
    """Raised when streaming operations fail."""

    def __init__(self, message: str, details: Dict = None):
        super().__init__(message)
        self.details = details or {}


class SimpleStreamingCallbackHandler(BaseCallbackHandler):
    """Simplified streaming callback handler that maintains queue interface."""

    def __init__(
        self,
        queue: asyncio.Queue,
        on_llm_new_token: Optional[callable] = None,
        on_llm_end: Optional[callable] = None,
    ):
        """Initialize the callback handler with a queue.

        Args:
            queue: Asyncio queue for streaming messages
            on_llm_new_token: Optional custom token handler
            on_llm_end: Optional custom end handler
        """
        self.queue = queue
        self.tool_states = {}  # Store tool states by invocation ID
        self.tool_inputs = {}  # Store tool inputs by invocation ID
        self.active_tools = {}  # Track active tools by name for fallback
        self.custom_on_llm_new_token = on_llm_new_token
        self.custom_on_llm_end = on_llm_end
        self.current_phase = "processing"  # Default phase is processing

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        """Get the current event loop or create a new one if necessary."""
        try:
            loop = asyncio.get_running_loop()
            return loop
        except RuntimeError:
            logger.debug("No running event loop found. Creating a new one.")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop

    async def _async_put_to_queue(self, item: Dict) -> None:
        """Put an item in the queue asynchronously."""
        try:
            await self.queue.put(item)
        except Exception as e:
            logger.error(f"Failed to put item in queue: {str(e)}")
            raise StreamingError(f"Queue operation failed: {str(e)}")

    def _put_to_queue(self, item: Dict) -> None:
        """Put an item in the queue, handling event loop considerations."""
        try:
            loop = self._ensure_loop()
            if loop.is_running():
                future = asyncio.run_coroutine_threadsafe(
                    self._async_put_to_queue(item), loop
                )
                future.result()
            else:
                loop.run_until_complete(self._async_put_to_queue(item))
        except Exception as e:
            logger.error(f"Failed to put item in queue: {str(e)}")
            raise StreamingError(f"Queue operation failed: {str(e)}")

    def _get_tool_info(
        self, invocation_id: Optional[str], tool_name: Optional[str] = None
    ) -> Optional[tuple]:
        """Get tool information using either invocation_id or tool_name.

        Returns:
            Optional[tuple]: (tool_name, tool_input, invocation_id) if found, None otherwise
        """
        if invocation_id and invocation_id in self.tool_states:
            return (
                self.tool_states[invocation_id],
                self.tool_inputs.get(invocation_id, ""),
                invocation_id,
            )
        elif tool_name and tool_name in self.active_tools:
            active_info = self.active_tools[tool_name]
            return (tool_name, active_info["input"], active_info["invocation_id"])
        return None

    async def process_step(
        self, content: str, role: str = "assistant", thought: Optional[str] = None
    ) -> None:
        """Process a planning step and queue it with the planning status.

        Args:
            content: The planning step content
            role: The role associated with the step (usually assistant)
            thought: Optional thought process notes
        """
        try:
            # Create step message with explicit planning status
            current_time = datetime.datetime.now().isoformat()
            step_message = {
                "type": "step",
                "status": "planning",  # Explicitly mark as planning phase
                "content": content,
                "role": role,
                "thought": thought or "Planning Phase",
                "created_at": current_time,
                "planning_only": True,  # Mark this content as planning-only
            }

            logger.debug(f"Queuing planning step message with length: {len(content)}")
            await self._async_put_to_queue(step_message)
        except Exception as e:
            logger.error(f"Failed to process planning step: {str(e)}")
            raise StreamingError(f"Planning step processing failed: {str(e)}")

    def on_tool_start(self, serialized: Dict, input_str: str, **kwargs) -> None:
        """Run when tool starts running."""
        tool_name = serialized.get("name")
        if not tool_name:
            logger.warning("Tool start called without tool name")
            return

        invocation_id = kwargs.get("invocation_id", str(uuid.uuid4()))

        # Store in both tracking systems
        self.tool_states[invocation_id] = tool_name
        self.tool_inputs[invocation_id] = input_str
        self.active_tools[tool_name] = {
            "invocation_id": invocation_id,
            "input": input_str,
            "start_time": datetime.datetime.now(),
        }

        logger.info(
            f"Tool started: {tool_name} (ID: {invocation_id}) with input: {input_str[:100]}..."
        )

    def on_tool_end(self, output: str, **kwargs) -> None:
        """Run when tool ends running."""
        invocation_id = kwargs.get("invocation_id")
        tool_name = kwargs.get("name")  # Try to get tool name from kwargs

        # Try to get tool info from either source
        tool_info = self._get_tool_info(invocation_id, tool_name)

        if tool_info:
            tool_name, tool_input, used_invocation_id = tool_info
            if hasattr(output, "content"):
                output = output.content

            self._put_to_queue(
                {
                    "type": "tool",
                    "tool": tool_name,
                    "input": tool_input,
                    "output": str(output),
                    "status": "processing",  # Use "processing" status for tool end
                    "created_at": datetime.datetime.now().isoformat(),
                }
            )
            logger.info(
                f"Tool {tool_name} (ID: {used_invocation_id}) completed with output length: {len(str(output))}"
            )

            # Clean up tracking
            if used_invocation_id in self.tool_states:
                del self.tool_states[used_invocation_id]
                del self.tool_inputs[used_invocation_id]
            if tool_name in self.active_tools:
                del self.active_tools[tool_name]
        else:
            logger.warning(
                f"Tool end called with unknown invocation ID: {invocation_id} and tool name: {tool_name}"
            )

    def on_tool_error(self, error: Exception, **kwargs) -> None:
        """Run when tool errors."""
        invocation_id = kwargs.get("invocation_id")
        tool_name = kwargs.get("name")  # Try to get tool name from kwargs

        # Try to get tool info from either source
        tool_info = self._get_tool_info(invocation_id, tool_name)

        if tool_info:
            tool_name, tool_input, used_invocation_id = tool_info
            self._put_to_queue(
                {
                    "type": "tool",
                    "tool": tool_name,
                    "input": tool_input,
                    "output": f"Error: {str(error)}",
                    "status": "error",
                    "created_at": datetime.datetime.now().isoformat(),
                }
            )
            logger.error(
                f"Tool {tool_name} (ID: {used_invocation_id}) failed with error: {str(error)}",
                exc_info=True,
            )

            # Clean up tracking
            if used_invocation_id in self.tool_states:
                del self.tool_states[used_invocation_id]
                del self.tool_inputs[used_invocation_id]
            if tool_name in self.active_tools:
                del self.active_tools[tool_name]
        else:
            logger.warning(
                f"Tool error called with unknown invocation ID: {invocation_id} and tool name: {tool_name}"
            )

    def on_llm_start(self, *args, **kwargs) -> None:
        """Run when LLM starts running."""
        logger.info("LLM processing started")

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        """Run on new token."""
        # Check if we have planning_only in the kwargs
        planning_only = kwargs.get("planning_only", False)

        # Handle custom token processing if provided
        if self.custom_on_llm_new_token:
            try:
                # Check if it's a coroutine function and handle accordingly
                if asyncio.iscoroutinefunction(self.custom_on_llm_new_token):
                    # For coroutines, we need to schedule it to run without awaiting
                    loop = self._ensure_loop()
                    # Create the coroutine object without calling it
                    coro = self.custom_on_llm_new_token(token, **kwargs)
                    # Schedule it to run in the event loop
                    asyncio.run_coroutine_threadsafe(coro, loop)
                else:
                    # Regular function call
                    self.custom_on_llm_new_token(token, **kwargs)
            except Exception as e:
                logger.error(f"Error in custom token handler: {str(e)}", exc_info=True)

        # Log token information with phase information
        phase = "planning" if planning_only else "processing"
        logger.debug(f"Received new token (length: {len(token)}, phase: {phase})")

    def on_llm_end(self, response, **kwargs) -> None:
        """Run when LLM ends running."""
        logger.info("LLM processing completed")

        # Queue an end message with complete status
        try:
            self._put_to_queue(
                {
                    "type": "token",
                    "status": "complete",
                    "content": "",
                    "created_at": datetime.datetime.now().isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Failed to queue completion message: {str(e)}")

        # Handle custom end processing if provided
        if self.custom_on_llm_end:
            try:
                # Check if it's a coroutine function and handle accordingly
                if asyncio.iscoroutinefunction(self.custom_on_llm_end):
                    # For coroutines, we need to schedule it to run without awaiting
                    loop = self._ensure_loop()
                    # Create the coroutine object without calling it
                    coro = self.custom_on_llm_end(response, **kwargs)
                    # Schedule it to run in the event loop
                    asyncio.run_coroutine_threadsafe(coro, loop)
                else:
                    # Regular function call
                    self.custom_on_llm_end(response, **kwargs)
            except Exception as e:
                logger.error(f"Error in custom end handler: {str(e)}", exc_info=True)

    def on_llm_error(self, error: Exception, **kwargs) -> None:
        """Run when LLM errors."""
        logger.error(f"LLM error occurred: {str(error)}", exc_info=True)

        # Send error status
        try:
            self._put_to_queue(
                {
                    "type": "token",
                    "status": "error",
                    "content": f"Error: {str(error)}",
                    "created_at": datetime.datetime.now().isoformat(),
                }
            )
        except Exception:
            pass  # Don't raise another error if this fails

        raise StreamingError("LLM processing failed", {"error": str(error)})


def create_streaming_setup() -> Tuple[SimpleStreamingCallbackHandler, asyncio.Queue]:
    """Create a streaming callback handler and queue.

    Returns:
        Tuple of (callback_handler, queue)
    """
    queue = asyncio.Queue()
    callback_handler = SimpleStreamingCallbackHandler(queue)
    return callback_handler, queue


def create_streaming_callback(
    queue: asyncio.Queue,
    on_llm_new_token: Optional[callable] = None,
    on_llm_end: Optional[callable] = None,
) -> SimpleStreamingCallbackHandler:
    """Create a streaming callback handler with custom handlers.

    Args:
        queue: Asyncio queue for streaming messages
        on_llm_new_token: Optional custom token handler
        on_llm_end: Optional custom end handler

    Returns:
        Configured callback handler
    """
    return SimpleStreamingCallbackHandler(
        queue=queue,
        on_llm_new_token=on_llm_new_token,
        on_llm_end=on_llm_end,
    )


async def stream_results(
    queue: asyncio.Queue,
    timeout: float = 30.0,
) -> List[Dict[str, Any]]:
    """Stream results from the queue until completion.

    Args:
        queue: Queue to stream from
        timeout: Timeout in seconds for each queue get

    Returns:
        List of all streamed messages
    """
    results = []

    while True:
        try:
            # Wait for next message with timeout
            message = await asyncio.wait_for(queue.get(), timeout=timeout)
            results.append(message)

            # Check if this is a completion message
            if message.get("type") == "token" and message.get("status") == "complete":
                break

        except asyncio.TimeoutError:
            logger.warning(f"Streaming timeout after {timeout} seconds")
            break
        except Exception as e:
            logger.error(f"Error streaming results: {str(e)}")
            break

    return results
