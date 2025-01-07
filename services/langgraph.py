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


def should_use_tool(state: Dict) -> bool:
    """
    Simple logic to decide if a tool is needed. Customize as you like.
    """
    messages = state["messages"]
    last_message = messages[-1].content if messages else ""

    if any(
        keyword in last_message.lower()
        for keyword in ["price", "balance", "transaction", "wallet"]
    ):
        return True
    if "get" in last_message.lower() and any(
        res in last_message.lower() for res in ["token", "contract", "address"]
    ):
        return True
    return False


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
            # For roles other than 'user' (like 'assistant', 'system', etc.), treat them as AI messages
            # Adjust if you want to handle system messages separately.
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
    )

    # The node (function) that decides whether to call tools or do a direct chat
    async def tool_selection_node(state: Dict):
        logger.debug("Entering tool_selection_node")
        logger.debug(f"Current state messages: {len(state['messages'])}")

        try:
            if should_use_tool(state):
                logger.debug("Tool usage detected, initializing agent")
                tools = list(tools_map.values())
                logger.debug(f"Using {len(tools)} tools")

                agent = initialize_agent(
                    tools=tools,
                    llm=chat,
                    agent=AgentType.OPENAI_FUNCTIONS,
                    verbose=True,
                    handle_parsing_errors=True,
                    max_iterations=3,
                    return_intermediate_steps=True,
                )

                try:
                    last_message = (
                        state["messages"][-1].content if state["messages"] else ""
                    )
                    logger.debug(
                        f"Invoking agent with last user message: {last_message[:100]}"
                    )

                    agent_result = await agent.ainvoke(
                        {"input": last_message},
                        config={
                            "callbacks": [callback_handler],
                            "run_name": "tool_execution",
                        },
                    )

                    # Process intermediate steps
                    for step in agent_result.get("intermediate_steps", []):
                        action, output = step
                        tool_input = action.tool_input
                        if isinstance(tool_input, dict):
                            tool_input = str(tool_input)

                        tool_execution = {
                            "type": "tool_execution",
                            "tool": action.tool,
                            "input": tool_input,
                            "output": str(output),
                        }
                        await callback_queue.put(tool_execution)

                    response_content = agent_result.get("output", "")
                    logger.debug(f"Agent response content: {response_content[:100]}")

                    return {
                        "messages": state["messages"]
                        + [AIMessage(content=response_content)],
                        "response": response_content,
                    }
                except Exception as e:
                    logger.error(f"Error in tool execution: {str(e)}")
                    logger.debug("Falling back to regular chat after tool error")

            logger.debug("Using regular chat without tools")
            messages_ = state["messages"]
            response = await chat.ainvoke(messages_)
            response_content = (
                response.content if hasattr(response, "content") else str(response)
            )
            logger.debug(f"Chat response received: {response_content[:100]}")

            return {
                "messages": messages_ + [AIMessage(content=response_content)],
                "response": response_content,
            }
        except Exception as e:
            logger.error(f"Error in tool_selection_node: {str(e)}")
            raise

    # Create the graph
    workflow = Graph()
    workflow.add_node("chat", tool_selection_node)
    workflow.set_entry_point("chat")
    workflow.add_edge("chat", END)

    # Compile the graph into a runnable
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
        "content": result["response"],
        "tokens": None,  # or any other metadata you'd like to add
    }
