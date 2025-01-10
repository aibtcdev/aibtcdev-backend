import asyncio
from backend.models import Profile
from langchain.agents import AgentType, initialize_agent
from langchain.callbacks.base import BaseCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import LLMResult
from langchain_openai import ChatOpenAI
from langgraph.graph import END, Graph
from lib.logger import configure_logger
from tools.tools_factory import initialize_tools
from typing import Dict, List, Optional
from typing import Annotated, Literal, TypedDict
from langchain_core.tools import BaseTool
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from lib.logger import configure_logger
from tools.tools_factory import initialize_tools
from typing import Dict, List, Optional

# -----------------------------------------------------
# Example placeholders - adapt these to your environment
# -----------------------------------------------------

logger = configure_logger(__name__)


def extract_filtered_content(history: List[Dict]) -> List[Dict]:
    """
    Stub for filtering thread history. Replace or remove as needed.
    For now, just returns the original history.
    """
    return history


# -----------------------------------------------------
# Streaming Callback Handler
# -----------------------------------------------------


class StreamingCallbackHandler(BaseCallbackHandler):
    """Callback handler for streaming tokens."""

    def __init__(self, queue: asyncio.Queue, on_llm_new_token=None, on_llm_end=None):
        """Initialize the callback handler with a queue and optional callbacks."""
        super().__init__()
        self.queue = queue
        self._on_llm_new_token = on_llm_new_token
        self._on_llm_end = on_llm_end
        self.tokens = []
        self.current_tool = None
        self._loop = None

    def _ensure_loop(self):
        """Ensure we have a valid event loop."""
        try:
            self._loop = asyncio.get_event_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        return self._loop

    def _put_to_queue(self, item):
        """Helper method to put items in queue."""
        loop = self._ensure_loop()
        if loop.is_running():
            future = asyncio.run_coroutine_threadsafe(self.queue.put(item), loop)
            future.result()  # Wait for it to complete
        else:
            loop.run_until_complete(self.queue.put(item))

    def on_llm_start(self, *args, **kwargs):
        """Run when LLM starts running."""
        logger.debug("LLM started")

    def on_llm_new_token(self, token: str, **kwargs):
        """Run on new token. Only available when streaming is enabled."""
        # If there's a custom on_llm_new_token callback, call it
        if self._on_llm_new_token:
            self._on_llm_new_token(token, **kwargs)
        self.tokens.append(token)

    def on_llm_end(self, response: LLMResult, **kwargs):
        """Run when LLM ends running."""
        logger.debug("LLM ended")
        if self._on_llm_end:
            self._on_llm_end(response, **kwargs)

    def on_llm_error(self, error: Exception, **kwargs):
        """Run when LLM errors."""
        logger.error(f"LLM error: {str(error)}")

    def on_tool_error(self, error: Exception, **kwargs):
        """Run when tool errors."""
        if self.current_tool:
            tool_execution = {
                "type": "tool_execution",
                "tool": self.current_tool,
                "input": None,
                "output": f"Error: {str(error)}",
            }
            self._put_to_queue(tool_execution)
            self.current_tool = None
        logger.error(f"Tool error: {str(error)}")


# -----------------------------------------------------
# Main function to execute chat with streaming
# -----------------------------------------------------


class State(TypedDict):
    """State for the agent."""

    messages: Annotated[list, add_messages]


async def execute_langgraph_stream(
    history: List[Dict],
    input_str: str,
    persona: Optional[str] = None,
    tools_map: Optional[Dict] = None,
):
    """
    Execute a chat stream using LangGraph with optional persona.
    :param profile: Custom Profile object, used for tool setup or personalization.
    :param history: List of message dicts, e.g. [{"role": "user", "content": "..."}]
    :param input_str: The current user input.
    :param persona: Optional system-level message to define persona or style.
    """
    logger.debug("Starting execute_chat_stream_langgraph")
    callback_queue = asyncio.Queue()

    # Filter the history if needed
    filtered_content = extract_filtered_content(history)

    # Ensure there's an event loop
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    logger.debug(
        f"Converting history to messages, history length: {len(filtered_content)}"
    )

    # Convert thread history to LangChain message format
    messages = []

    # 1. Optionally add the persona as a SystemMessage
    if persona:
        logger.debug("Adding persona as a SystemMessage")
        messages.append(SystemMessage(content=persona))

    # 2. Convert existing thread
    for msg in filtered_content:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))

    # 3. Add the current user input
    messages.append(HumanMessage(content=input_str))
    logger.debug(f"Final messages length (including persona if any): {len(messages)}")

    # Create a streaming callback handler
    callback_handler = StreamingCallbackHandler(
        queue=callback_queue,
        on_llm_new_token=lambda token, **kwargs: asyncio.run_coroutine_threadsafe(
            callback_queue.put({"type": "token", "content": token}), loop
        ),
        on_llm_end=lambda *args, **kwargs: asyncio.run_coroutine_threadsafe(
            callback_queue.put({"type": "end"}), loop
        ),
    )

    # Create the chat model with streaming
    chat = ChatOpenAI(
        streaming=True,
        model="gpt-4o",  # Replace with your desired model
        callbacks=[callback_handler],
        temperature=0.7,
    ).bind_tools(list(tools_map.values()))

    # Create the tool node
    tool_node = ToolNode(list(tools_map.values()))

    # Define the function that determines whether to continue or not
    def should_continue(state: State) -> Literal["tools", "END"]:
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools"
        return END

    # Define the function that calls the model
    def call_model(state: State):
        messages = state["messages"]
        response = chat.invoke(messages)
        return {"messages": [response]}

    # Define the graph
    workflow = StateGraph(State)

    # Define the nodes we will cycle between
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", tool_node)

    # Set the entrypoint as 'agent'
    workflow.add_edge(START, "agent")

    # Add conditional edges
    workflow.add_conditional_edges(
        "agent",
        should_continue,
    )

    # Add edge from tools to agent
    workflow.add_edge("tools", "agent")

    # Compile the graph
    runnable = workflow.compile()

    # Run the graph
    config = {"messages": messages}
    task = asyncio.create_task(runnable.ainvoke(config))

    # Stream tokens while waiting for completion
    while not task.done():
        try:
            data = await asyncio.wait_for(callback_queue.get(), timeout=0.1)
            if data["type"] == "end":
                yield data
            else:
                yield data
        except asyncio.TimeoutError:
            continue
        except asyncio.CancelledError:
            logger.error("Task cancelled")
            task.cancel()
            raise
        except Exception as e:
            logger.error(f"Error in streaming loop: {str(e)}")
            raise

    # Get final result
    try:
        result = await task
        logger.debug(f"Final result received: {result}")
    except Exception as e:
        logger.error(f"Error getting final result: {str(e)}")
        raise

    yield {
        "type": "result",
        "content": result["messages"][-1].content,
        "tokens": None,
    }
