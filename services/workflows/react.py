"""ReAct workflow functionality."""

import asyncio
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
            logger.debug(f"Adding persona message with decisiveness instruction")
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
    """Callback handler for streaming tokens."""

    def __init__(
        self,
        queue: asyncio.Queue,
        on_llm_new_token: Optional[callable] = None,
        on_llm_end: Optional[callable] = None,
    ):
        """Initialize the callback handler."""
        super().__init__()
        self.queue = queue
        self._on_llm_new_token = on_llm_new_token
        self._on_llm_end = on_llm_end
        self.tokens: List[str] = []
        self.current_tool: Optional[str] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        logger.debug("Initialized StreamingCallbackHandler")

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        """Ensure we have a valid event loop."""
        if not self._loop:
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                logger.warning("No event loop found, creating new one")
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        return self._loop

    async def _async_put_to_queue(self, item: Dict) -> None:
        """Asynchronously put items in queue."""
        try:
            await self.queue.put(item)
            logger.debug(
                f"Successfully queued item of type: {item.get('type', 'unknown')}"
            )
        except Exception as e:
            logger.error(f"Failed to put item in queue: {str(e)}")
            raise StreamingError(f"Queue operation failed: {str(e)}")

    def _put_to_queue(self, item: Dict) -> None:
        """Helper method to put items in queue."""
        loop = self._ensure_loop()
        try:
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

    def on_tool_start(self, serialized: Dict, input_str: str, **kwargs) -> None:
        """Run when tool starts running."""
        self.current_tool = serialized.get("name")
        self._put_to_queue(
            {
                "type": "tool",
                "tool": self.current_tool,
                "input": input_str,
                "status": "start",
            }
        )
        logger.info(
            f"Tool started: {self.current_tool} with input: {input_str[:100]}..."
        )

    def on_tool_end(self, output: str, **kwargs) -> None:
        """Run when tool ends running."""
        if self.current_tool:
            if hasattr(output, "content"):
                output = output.content

            self._put_to_queue(
                {
                    "type": "tool",
                    "tool": self.current_tool,
                    "input": None,
                    "output": str(output),
                    "status": "end",
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
        if self._on_llm_new_token:
            self._on_llm_new_token(token, **kwargs)
        self.tokens.append(token)
        logger.debug(f"Received new token (length: {len(token)})")

    def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        """Run when LLM ends running."""
        logger.info("LLM processing completed")
        if self._on_llm_end:
            self._on_llm_end(response, **kwargs)

    def on_llm_error(self, error: Exception, **kwargs) -> None:
        """Run when LLM errors."""
        logger.error(f"LLM error occurred: {str(error)}", exc_info=True)
        raise ExecutionError("LLM processing failed", {"error": str(error)})

    def on_tool_error(self, error: Exception, **kwargs) -> None:
        """Run when tool errors."""
        if self.current_tool:
            self._put_to_queue(
                {
                    "type": "tool",
                    "tool": self.current_tool,
                    "input": None,
                    "output": f"Error: {str(error)}",
                    "status": "error",
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
        self.llm = ChatOpenAI(
            model=self.llm.model_name,
            temperature=self.llm.temperature,
            streaming=True,
            callbacks=[callback_handler],
        ).bind_tools(tools)

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
        self.message_processor = MessageProcessor()

    async def execute_react_stream(
        self,
        history: List[Dict],
        input_str: str,
        persona: Optional[str] = None,
        tools_map: Optional[Dict] = None,
    ) -> AsyncGenerator[Dict, None]:
        """Execute a ReAct stream using LangGraph."""
        logger.info("Starting new LangGraph ReAct stream execution")
        logger.debug(
            f"Input parameters - History length: {len(history)}, "
            f"Persona present: {bool(persona)}, "
            f"Tools count: {len(tools_map) if tools_map else 0}"
        )

        try:
            callback_queue = asyncio.Queue()
            loop = asyncio.get_running_loop()

            # Process messages
            filtered_content = self.message_processor.extract_filtered_content(history)
            messages = self.message_processor.convert_to_langchain_messages(
                filtered_content, input_str, persona
            )

            # Setup callback handler
            callback_handler = StreamingCallbackHandler(
                queue=callback_queue,
                on_llm_new_token=lambda token, **kwargs: asyncio.run_coroutine_threadsafe(
                    callback_queue.put({"type": "token", "content": token}), loop
                ),
                on_llm_end=lambda *args, **kwargs: asyncio.run_coroutine_threadsafe(
                    callback_queue.put({"type": "end"}), loop
                ),
            )

            # Create workflow
            workflow = ReactWorkflow(
                callback_handler=callback_handler,
                tools=list(tools_map.values()) if tools_map else [],
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
            while not task.done():
                try:
                    data = await asyncio.wait_for(callback_queue.get(), timeout=0.1)
                    if data:
                        yield data
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    logger.error("Task cancelled unexpectedly")
                    task.cancel()
                    raise ExecutionError("Task cancelled unexpectedly")
                except Exception as e:
                    logger.error(f"Error in streaming loop: {str(e)}", exc_info=True)
                    raise ExecutionError(f"Streaming error: {str(e)}")

            # Get final result
            result = await task
            logger.info("Workflow execution completed successfully")
            logger.debug(
                f"Final result content length: {len(result['messages'][-1].content)}"
            )

            yield {
                "type": "result",
                "content": result["messages"][-1].content,
                "tokens": None,
            }

        except Exception as e:
            logger.error(f"Failed to execute ReAct stream: {str(e)}", exc_info=True)
            raise ExecutionError(f"ReAct stream execution failed: {str(e)}")


# Facade function for backward compatibility
async def execute_langgraph_stream(
    history: List[Dict],
    input_str: str,
    persona: Optional[str] = None,
    tools_map: Optional[Dict] = None,
) -> AsyncGenerator[Dict, None]:
    """Execute a ReAct stream using LangGraph with optional persona."""
    service = LangGraphService()
    async for chunk in service.execute_react_stream(
        history, input_str, persona, tools_map
    ):
        yield chunk
