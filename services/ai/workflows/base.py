import asyncio
import datetime
import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts.chat import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import Graph, StateGraph

from lib.logger import configure_logger

logger = configure_logger(__name__)


class LangGraphError(Exception):
    """Base exception for LangGraph operations"""

    def __init__(self, message: str, details: Dict = None):
        super().__init__(message)
        self.details = details or {}


class StreamingError(LangGraphError):
    """Raised when streaming operations fail"""

    pass


class ExecutionError(LangGraphError):
    """Raised when graph execution fails"""

    pass


class ValidationError(LangGraphError):
    """Raised when state validation fails"""

    pass


# Base state type for all workflows
StateType = TypeVar("StateType", bound=Dict[str, Any])


class BaseWorkflow(Generic[StateType]):
    """Base class for all LangGraph workflows.

    This class provides common functionality and patterns for all workflows.
    Each workflow should inherit from this class and implement the required
    methods.
    """

    def __init__(
        self,
        model_name: str = "gpt-4.1",
        temperature: Optional[float] = 0.9,
        streaming: bool = True,
        callbacks: Optional[List[Any]] = None,
    ):
        """Initialize the workflow.

        Args:
            model_name: LLM model to use
            temperature: Temperature for LLM generation, can be a float or None
            streaming: Whether to enable streaming
            callbacks: Optional callback handlers
        """
        self.llm = ChatOpenAI(
            temperature=temperature,
            model=model_name,
            streaming=streaming,
            stream_usage=True,
            callbacks=callbacks or [],
        )
        self.logger = configure_logger(self.__class__.__name__)
        self.required_fields: List[str] = []
        self.model_name = model_name
        self.temperature = temperature

    def _clean_llm_response(self, content: str) -> str:
        """Clean the LLM response content and ensure valid JSON."""
        try:
            # First try to parse as-is in case it's already valid JSON
            json.loads(content)
            return content.strip()
        except json.JSONDecodeError:
            # If not valid JSON, try to extract from markdown blocks
            if "```json" in content:
                json_content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_content = content.split("```")[1].split("```")[0].strip()
            else:
                json_content = content.strip()

            # Replace any Python boolean values with JSON boolean values
            json_content = json_content.replace("True", "true").replace(
                "False", "false"
            )

            # Validate the cleaned JSON
            try:
                json.loads(json_content)
                return json_content
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse JSON after cleaning: {str(e)}")
                raise ValueError(f"Invalid JSON response from LLM: {str(e)}")

    def create_llm_with_callbacks(self, callbacks: List[Any]) -> ChatOpenAI:
        """Create a new LLM instance with specified callbacks.

        This is useful when you need to create a new LLM instance with different
        callbacks or tools.

        Args:
            callbacks: List of callback handlers

        Returns:
            A new ChatOpenAI instance with the specified callbacks
        """
        return ChatOpenAI(
            model=self.model_name,
            temperature=self.temperature,
            streaming=True,
            stream_usage=True,
            callbacks=callbacks,
        )

    def _create_prompt(self) -> ChatPromptTemplate:
        """Create the chat prompt template for this workflow."""
        raise NotImplementedError("Workflow must implement _create_prompt")

    def _create_graph(self) -> Union[Graph, StateGraph]:
        """Create the workflow graph."""
        raise NotImplementedError("Workflow must implement _create_graph")

    def _validate_state(self, state: StateType) -> bool:
        """Validate the workflow state.

        This method checks if all required fields are present in the state.
        Override this method to add custom validation logic.

        Args:
            state: The state to validate

        Returns:
            True if the state is valid, False otherwise
        """
        if not self.required_fields:
            # If no required fields specified, assume validation passes
            return True

        # Check that all required fields are present and have values
        return all(
            field in state and state[field] is not None
            for field in self.required_fields
        )

    def get_missing_fields(self, state: StateType) -> List[str]:
        """Get a list of missing required fields in the state.

        Args:
            state: The state to check

        Returns:
            List of missing field names
        """
        if not self.required_fields:
            return []

        return [
            field
            for field in self.required_fields
            if field not in state or state[field] is None
        ]

    async def execute(self, initial_state: StateType) -> Dict:
        """Execute the workflow with the given initial state.

        Args:
            initial_state: Initial state for the workflow

        Returns:
            Final state after workflow execution
        """
        # Validate state
        if not self._validate_state(initial_state):
            error_message = f"Invalid initial state: {initial_state}"
            self.logger.error(error_message)
            missing = self.get_missing_fields(initial_state)
            if missing:
                error_message += f" Missing fields: {', '.join(missing)}"
            raise ValidationError(error_message)

        # Create runtime workflow
        app = self._create_graph()

        self.logger.debug(
            f"[DEBUG:Workflow:{self.__class__.__name__}] State before ain_invoke: {json.dumps(initial_state, indent=2, default=str)}"
        )
        try:
            # Execute the workflow
            result = await app.ainvoke(initial_state)
            self.logger.debug(
                f"[DEBUG:Workflow:{self.__class__.__name__}] State after ain_invoke: {json.dumps(result, indent=2, default=str)}"
            )
            return result
        except Exception as e:
            error_message = f"Workflow execution failed: {str(e)}"
            self.logger.error(error_message)
            raise ExecutionError(error_message) from e


class BaseWorkflowMixin(ABC):
    """Base mixin for adding capabilities to workflows.

    This is an abstract base class that defines the interface for
    workflow capability mixins. Mixins can be combined to create
    workflows with multiple capabilities.
    """

    @abstractmethod
    def integrate_with_graph(self, graph: StateGraph, **kwargs) -> None:
        """Integrate this capability with a graph.

        Args:
            graph: The graph to integrate with
            **kwargs: Additional arguments specific to this capability
        """
        pass


@dataclass
class MessageContent:
    """Data class for message content"""

    role: str
    content: str
    tool_calls: Optional[List[Dict]] = None

    @classmethod
    def from_dict(cls, data: Dict) -> "MessageContent":
        """Create MessageContent from dictionary"""
        return cls(
            role=data.get("role", ""),
            content=data.get("content", ""),
            tool_calls=data.get("tool_calls"),
        )


class MessageProcessor:
    """Processor for messages"""

    @staticmethod
    def extract_filtered_content(history: List[Dict]) -> List[Dict]:
        """Extract and filter content from message history."""
        logger.debug(
            f"Starting content extraction from history with {len(history)} messages"
        )
        filtered_content = []

        for message in history:
            logger.debug(f"Processing message type: {message.get('role')}")
            if message.get("role") in ["user", "assistant"]:
                filtered_content.append(MessageContent.from_dict(message).__dict__)

        logger.debug(
            f"Finished filtering content, extracted {len(filtered_content)} messages"
        )
        return filtered_content

    @staticmethod
    def convert_to_langchain_messages(
        filtered_content: List[Dict],
        current_input: str,
        persona: Optional[str] = None,
    ) -> List[Union[SystemMessage, HumanMessage, AIMessage]]:
        """Convert filtered content to LangChain message format."""
        messages = []

        # Add decisiveness instruction
        decisiveness_instruction = "Be decisive and action-oriented. When the user requests something, execute it immediately without asking for confirmation."

        if persona:
            logger.debug("Adding persona message with decisiveness instruction")
            # Add the decisiveness instruction to the persona
            enhanced_persona = f"{persona}\n\n{decisiveness_instruction}"
            messages.append(SystemMessage(content=enhanced_persona))
        else:
            # If no persona, add the decisiveness instruction as a system message
            logger.debug("Adding decisiveness instruction as system message")
            messages.append(SystemMessage(content=decisiveness_instruction))

        for msg in filtered_content:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            else:
                content = msg.get("content") or ""
                if msg.get("tool_calls"):
                    messages.append(
                        AIMessage(content=content, tool_calls=msg["tool_calls"])
                    )
                else:
                    messages.append(AIMessage(content=content))

        messages.append(HumanMessage(content=current_input))
        logger.debug(f"Prepared message chain with {len(messages)} total messages")
        return messages


class StreamingCallbackHandler(BaseCallbackHandler):
    """Handle callbacks from LangChain and stream results to a queue."""

    def __init__(
        self,
        queue: asyncio.Queue,
        on_llm_new_token: Optional[callable] = None,
        on_llm_end: Optional[callable] = None,
    ):
        """Initialize the callback handler with a queue."""
        self.queue = queue
        self.tool_states = {}  # Store tool states by invocation ID
        self.tool_inputs = {}  # Store tool inputs by invocation ID
        self.active_tools = {}  # Track active tools by name for fallback
        self.custom_on_llm_new_token = on_llm_new_token
        self.custom_on_llm_end = on_llm_end
        # Track the current execution phase
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
                "thought": thought
                or "Planning Phase",  # Default to Planning Phase if thought is not provided
                "created_at": current_time,
                "planning_only": True,  # Mark this content as planning-only to prevent duplication
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

        raise ExecutionError("LLM processing failed", {"error": str(error)})
