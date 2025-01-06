import asyncio
from backend.factory import backend
from backend.models import Profile
from dotenv import load_dotenv
from langchain.agents import AgentExecutor, initialize_agent
from langchain.agents.types import AgentType
from langchain.callbacks.base import BaseCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import LLMResult
from langchain_openai import ChatOpenAI
from langgraph.graph import END, Graph
from lib.logger import configure_logger
from tools.tools_factory import initialize_tools
from typing import Dict, List
from uuid import UUID

logger = configure_logger(__name__)

load_dotenv()


def extract_filtered_content(history: List) -> str:
    """Extract and filter content from chat history."""
    filtered_content = []
    for message in history:
        logger.info(f"Processing message: {message}")
        if isinstance(message, str):
            filtered_content.append(message)
        elif isinstance(message, dict):

            if message.get("role") == "assistant" and message.get("type") == "result":
                filtered_content.append(message.get("content", ""))
    return "\n".join(filtered_content)


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
    )

    async def tool_selection_node(state):
        try:
            if should_use_tool(state):
                logger.debug("Tool usage detected, initializing agent")
                tools = list(tools_map.values())

                agent = initialize_agent(
                    tools=tools,
                    llm=chat,
                    agent=AgentType.OPENAI_MULTI_FUNCTIONS,
                    verbose=True,
                    handle_parsing_errors=True,
                    max_iterations=3,
                    return_intermediate_steps=True,
                )

                try:
                    last_message = (
                        state["messages"][-1].content if state["messages"] else ""
                    )
                    agent_result = await agent.ainvoke(
                        {"input": last_message},
                        config={
                            "callbacks": [callback_handler],
                            "run_name": "tool_execution",
                        },
                    )
                    for step in agent_result.get("intermediate_steps", []):
                        action, output = step
                        tool_input = action.tool_input
                        if isinstance(tool_input, dict):
                            tool_input = str(tool_input)

                        tool_execution = {
                            "type": "tool",
                            "tool": action.tool,
                            "input": tool_input,
                            "output": str(output),  # Ensure output is string
                            "status": "end",
                        }
                        await callback_queue.put(tool_execution)

                    # Get final response
                    response_content = agent_result.get("output", "")

                    return {
                        "messages": state["messages"]
                        + [AIMessage(content=response_content)],
                        "response": response_content,
                    }
                except Exception as e:
                    logger.error(f"Error in tool execution: {str(e)}")

            messages = state["messages"]
            response = await chat.ainvoke(messages)
            response_content = (
                response.content if hasattr(response, "content") else str(response)
            )
            return {
                "messages": messages + [AIMessage(content=response_content)],
                "response": response_content,
            }
        except Exception as e:
            logger.error(f"Error in tool_selection_node: {str(e)}")
            raise

    # Create the graph
    logger.debug("Creating workflow graph")
    workflow = Graph()
    workflow.add_node("chat", tool_selection_node)
    workflow.set_entry_point("chat")
    workflow.add_edge("chat", END)

    # Compile the graph into a runnable
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
        "content": result["response"],
        "tokens": None,  # LangGraph doesn't provide token count directly
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


def should_use_tool(state):
    """Determine if a tool should be used based on the current state."""
    messages = state["messages"]
    last_message = messages[-1].content if messages else ""
    last_message_lower = last_message.lower()

    # Financial and market-related keywords
    financial_keywords = [
        "price",
        "balance",
        "transaction",
        "wallet",
        "market",
        "trade",
        "swap",
        "volume",
        "history",
        "bid",
        "ask",
        "order",
        "book",
        "pending",
        "buy",
        "sell",
        "bonding",
        "token",
        "stx",
        "bitcoin",
        "btc",
        "crypto",
        "price",
    ]

    # Contract and technical keywords
    technical_keywords = [
        "contract",
        "deploy",
        "address",
        "sip10",
        "collective",
        "dao",
        "capability",
        "schedule",
        "task",
        "status",
        "metadata",
        "search",
    ]

    # Action keywords that often indicate tool usage
    action_verbs = [
        "get",
        "check",
        "list",
        "show",
        "find",
        "create",
        "cancel",
        "submit",
        "execute",
        "deploy",
        "schedule",
    ]

    # Check for financial and market-related queries
    if any(keyword in last_message_lower for keyword in financial_keywords):
        return True

    # Check for technical and contract-related queries
    if any(keyword in last_message_lower for keyword in technical_keywords):
        return True

    # Check for action verbs combined with relevant context
    if any(verb in last_message_lower for verb in action_verbs):
        # Additional context checks for action verbs
        contexts = [
            "token",
            "contract",
            "address",
            "market",
            "order",
            "collective",
            "dao",
        ]
        if any(context in last_message_lower for context in contexts):
            return True

    return False
