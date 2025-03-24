"""ReAct workflow functionality."""

import asyncio
import datetime
import uuid
from dataclasses import dataclass
from typing import (
    Annotated,
    Any,
    AsyncGenerator,
    Dict,
    List,
    Optional,
    TypedDict,
    Union,
)

from langchain.callbacks.base import BaseCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import LLMResult
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from lib.logger import configure_logger
from services.workflows.base import BaseWorkflow, ExecutionError, StreamingError

# Remove this import to avoid circular dependencies
# from services.workflows.workflow_service import BaseWorkflowService, WorkflowBuilder

logger = configure_logger(__name__)


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

    def on_llm_end(self, response: LLMResult, **kwargs) -> None:
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


class ReactState(TypedDict):
    """State for the ReAct workflow."""

    messages: Annotated[list, add_messages]


class ReactWorkflow(BaseWorkflow[ReactState]):
    """ReAct workflow implementation."""

    def __init__(
        self,
        callback_handler: StreamingCallbackHandler,
        tools: List[Any],
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.callback_handler = callback_handler
        self.tools = tools
        # Create a new LLM instance with the callback handler
        self.llm = self.create_llm_with_callbacks([callback_handler]).bind_tools(tools)
        self.required_fields = ["messages"]

    def _create_prompt(self) -> None:
        """Not used in ReAct workflow."""
        pass

    def _create_graph(self) -> StateGraph:
        """Create the ReAct workflow graph."""
        tool_node = ToolNode(self.tools)

        def should_continue(state: ReactState) -> str:
            messages = state["messages"]
            last_message = messages[-1]
            result = "tools" if last_message.tool_calls else END
            logger.debug(f"Continue decision: {result}")
            return result

        def call_model(state: ReactState) -> Dict:
            logger.debug("Calling model with current state")
            messages = state["messages"]
            response = self.llm.invoke(messages)
            logger.debug("Received model response")
            return {"messages": [response]}

        workflow = StateGraph(ReactState)
        workflow.add_node("agent", call_model)
        workflow.add_node("tools", tool_node)
        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges("agent", should_continue)
        workflow.add_edge("tools", "agent")

        return workflow


class LangGraphService:
    """Service for executing LangGraph operations"""

    def __init__(self):
        """Initialize the service."""
        self.message_processor = MessageProcessor()

    async def _execute_stream_impl(
        self,
        messages: List[Union[SystemMessage, HumanMessage, AIMessage]],
        input_str: str,
        persona: Optional[str] = None,
        tools_map: Optional[Dict] = None,
        **kwargs,
    ) -> AsyncGenerator[Dict, None]:
        """Execute a ReAct stream using LangGraph.

        Args:
            messages: Processed messages ready for the LLM
            input_str: Current user input
            persona: Optional persona to use
            tools_map: Optional tools to use
            **kwargs: Additional arguments

        Returns:
            Async generator of result chunks
        """
        try:
            # Import here to avoid circular dependencies
            from services.workflows.workflow_service import (
                BaseWorkflowService,
                WorkflowBuilder,
            )

            # Setup queue and callbacks
            callback_queue = asyncio.Queue()
            loop = asyncio.get_running_loop()

            # Setup callback handler
            callback_handler = self.setup_callback_handler(callback_queue, loop)

            # Create workflow using builder pattern
            workflow = (
                WorkflowBuilder(ReactWorkflow)
                .with_callback_handler(callback_handler)
                .with_tools(list(tools_map.values()) if tools_map else [])
                .build()
            )

            # Create graph and compile
            graph = workflow._create_graph()
            runnable = graph.compile()

            # Execute workflow with callbacks config
            config = {"callbacks": [callback_handler]}
            task = asyncio.create_task(
                runnable.ainvoke({"messages": messages}, config=config)
            )

            # Stream results
            async for chunk in self.stream_task_results(task, callback_queue):
                yield chunk

        except Exception as e:
            logger.error(f"Failed to execute ReAct stream: {str(e)}", exc_info=True)
            raise ExecutionError(f"ReAct stream execution failed: {str(e)}")

    def setup_callback_handler(self, queue, loop):
        # Import here to avoid circular dependencies
        from services.workflows.workflow_service import BaseWorkflowService

        # Use the static method instead of instantiating BaseWorkflowService
        return BaseWorkflowService.create_callback_handler(queue, loop)

    async def stream_task_results(self, task, queue):
        # Import here to avoid circular dependencies
        from services.workflows.workflow_service import BaseWorkflowService

        # Use the static method instead of instantiating BaseWorkflowService
        async for chunk in BaseWorkflowService.stream_results_from_task(
            task=task, callback_queue=queue, logger_name=self.__class__.__name__
        ):
            yield chunk

    # Keep the old method for backward compatibility
    async def execute_react_stream(
        self,
        history: List[Dict],
        input_str: str,
        persona: Optional[str] = None,
        tools_map: Optional[Dict] = None,
    ) -> AsyncGenerator[Dict, None]:
        """Execute a ReAct stream using LangGraph."""
        # Process messages for backward compatibility
        filtered_content = self.message_processor.extract_filtered_content(history)
        messages = self.message_processor.convert_to_langchain_messages(
            filtered_content, input_str, persona
        )

        # Call the new implementation
        async for chunk in self._execute_stream_impl(
            messages=messages,
            input_str=input_str,
            persona=persona,
            tools_map=tools_map,
        ):
            yield chunk

    # Add execute_stream as alias for consistency across services
    async def execute_stream(
        self,
        history: List[Dict],
        input_str: str,
        persona: Optional[str] = None,
        tools_map: Optional[Dict] = None,
        **kwargs,
    ) -> AsyncGenerator[Dict, None]:
        """Execute a workflow stream.

        This is an alias for execute_react_stream to maintain consistent API
        across different workflow services.
        """
        async for chunk in self.execute_react_stream(
            history=history,
            input_str=input_str,
            persona=persona,
            tools_map=tools_map,
        ):
            yield chunk


# Facade function for backward compatibility
async def execute_langgraph_stream(
    history: List[Dict],
    input_str: str,
    persona: Optional[str] = None,
    tools_map: Optional[Dict] = None,
) -> AsyncGenerator[Dict, None]:
    """Execute a ReAct stream using LangGraph with optional persona."""
    service = LangGraphService()
    async for chunk in service.execute_stream(history, input_str, persona, tools_map):
        yield chunk
