"""ReAct workflow functionality."""

import asyncio
import datetime
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
from services.workflows.workflow_service import BaseWorkflowService, WorkflowBuilder

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
        self.current_tool = None
        self.tool_inputs = {}  # Store tool inputs by tool name
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
            logger.warning("No running event loop found. Creating a new one.")
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
        self.current_tool = serialized.get("name")

        # Store the input for this tool
        if self.current_tool:
            self.tool_inputs[self.current_tool] = input_str

        logger.info(
            f"Tool started: {self.current_tool} with input: {input_str[:100]}..."
        )

    def on_tool_end(self, output: str, **kwargs) -> None:
        """Run when tool ends running."""
        if self.current_tool:
            if hasattr(output, "content"):
                output = output.content

            # Retrieve the stored input for this tool
            tool_input = self.tool_inputs.get(self.current_tool, "")

            self._put_to_queue(
                {
                    "type": "tool",
                    "tool": self.current_tool,
                    "input": tool_input,  # Use the stored input instead of None
                    "output": str(output),
                    "status": "processing",  # Use "processing" status for tool end
                    "created_at": datetime.datetime.now().isoformat(),
                }
            )
            logger.info(
                f"Tool {self.current_tool} completed with output length: {len(str(output))}"
            )
            self.current_tool = None

    def on_llm_start(self, *args, **kwargs) -> None:
        """Run when LLM starts running."""
        logger.info("LLM processing started")

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        """Run on new token."""
        # Check if we have planning_only in the kwargs
        planning_only = kwargs.get("planning_only", False)

        if self.custom_on_llm_new_token:
            self.custom_on_llm_new_token(token, **kwargs)

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

        if self.custom_on_llm_end:
            self.custom_on_llm_end(response, **kwargs)

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

    def on_tool_error(self, error: Exception, **kwargs) -> None:
        """Run when tool errors."""
        if self.current_tool:
            # Retrieve the stored input for this tool
            tool_input = self.tool_inputs.get(self.current_tool, "")

            self._put_to_queue(
                {
                    "type": "tool",
                    "tool": self.current_tool,
                    "input": tool_input,  # Use the stored input instead of None
                    "output": f"Error: {str(error)}",
                    "status": "error",  # Keep "error" status for error conditions
                    "created_at": datetime.datetime.now().isoformat(),
                }
            )
            logger.error(
                f"Tool {self.current_tool} failed with error: {str(error)}",
                exc_info=True,
            )
            self.current_tool = None


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


class LangGraphService(BaseWorkflowService):
    """Service for executing LangGraph operations"""

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
