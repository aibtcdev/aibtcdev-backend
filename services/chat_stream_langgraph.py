import asyncio
from backend.factory import backend
from backend.models import Profile
from dotenv import load_dotenv
from langchain.callbacks.base import BaseCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import LLMResult
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages
from lib.logger import configure_logger
from tools.tools_factory import initialize_tools
from typing import Dict, List, Annotated, Literal, TypedDict
from uuid import UUID

logger = configure_logger(__name__)

load_dotenv()


class State(TypedDict):
    """State for the agent."""

    messages: Annotated[list, add_messages]


def extract_filtered_content(history: List) -> List[Dict]:
    """Extract and filter content from chat history."""
    filtered_content = []
    for message in history:
        logger.info(f"Processing message: {message}")
        if message.get("role") == "user":
            filtered_content.append(
                {
                    "role": "user",
                    "content": message.get("content", ""),
                }
            )
        elif message.get("role") == "assistant":
            filtered_content.append(
                {
                    "role": "assistant",
                    "content": message.get("content", ""),
                }
            )
    return filtered_content


async def execute_chat_stream_langgraph(
    profile: Profile, agent_id: UUID, history: List, input_str: str, persona: str = None
):
    """Execute a chat stream using LangGraph."""
    callback_queue = asyncio.Queue()
    tools_map = initialize_tools(profile, agent_id=agent_id, crewai=False)
    filtered_content = extract_filtered_content(history)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    messages = []
    for msg in filtered_content:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))

    if persona:
        messages.append(SystemMessage(content=persona))

    messages.append(HumanMessage(content=input_str))

    callback_handler = StreamingCallbackHandler(
        queue=callback_queue,
        on_llm_new_token=lambda token, **kwargs: asyncio.run_coroutine_threadsafe(
            callback_queue.put({"type": "token", "content": token}), loop
        ),
        on_llm_end=lambda *args, **kwargs: asyncio.run_coroutine_threadsafe(
            callback_queue.put({"type": "end"}), loop
        ),
    )

    chat = ChatOpenAI(
        streaming=True,
        model="gpt-4o",
        callbacks=[callback_handler],
        temperature=0.7,
    ).bind_tools(list(tools_map.values()))

    # Create the tool node
    tool_node = ToolNode(list(tools_map.values()))

    # Define the function that determines whether to continue or not
    def should_continue(state: State) -> str:
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

    # Create the graph
    logger.debug("Creating workflow graph")
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
    logger.debug("Compiling workflow")
    runnable = workflow.compile()

    # Run the graph
    config = {"messages": messages}
    logger.debug("Starting workflow execution")
    task = asyncio.create_task(runnable.ainvoke(config))

    # Stream tokens while waiting for completion
    while not task.done():
        try:
            logger.debug("Waiting for data from callback queue")
            try:
                # Try to get data with a timeout to avoid getting stuck
                data = await asyncio.wait_for(callback_queue.get(), timeout=0.1)
                logger.debug(f"Received data from queue: {data}")
                if data["type"] == "end":
                    yield data
                else:
                    yield data
            except asyncio.TimeoutError:
                # No data available, continue checking if task is done
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
        logger.debug("Getting final result")
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

    def on_tool_start(self, serialized: Dict, input_str: str, **kwargs):
        """Run when tool starts running."""
        self.current_tool = serialized.get("name")
        tool_execution = {
            "type": "tool",
            "tool": self.current_tool,
            "input": input_str,
            "status": "start",
        }
        self._put_to_queue(tool_execution)

    # def on_tool_end(self, output: str, **kwargs):
    #     """Run when tool ends running."""
    #     if self.current_tool:
    #         tool_execution = {
    #             "type": "tool_execution",
    #             "tool": self.current_tool,
    #             "input": None,  # We don't have access to the input here
    #             "output": output,
    #         }
    #         self._put_to_queue(tool_execution)
    #         self.current_tool = None

    def on_tool_error(self, error: Exception, **kwargs):
        """Run when tool errors."""
        if self.current_tool:
            tool_execution = {
                "type": "tool",
                "tool": self.current_tool,
                "input": None,  # We don't have access to the input here
                "output": f"Error: {str(error)}",
            }
            self._put_to_queue(tool_execution)
            self.current_tool = None
        logger.error(f"Tool error: {str(error)}")
