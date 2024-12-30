import asyncio
import os
from crewai import Agent, Crew, Process, Task
from crewai.agents.parser import AgentAction, AgentFinish
from crewai.tasks.task_output import TaskOutput
from db.factory import db
from dotenv import load_dotenv
from langchain.agents import AgentExecutor, initialize_agent
from langchain.agents.types import AgentType
from langchain.callbacks.base import BaseCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import LLMResult
from langchain_openai import ChatOpenAI
from langgraph.graph import END, Graph
from lib.logger import configure_logger
from lib.models import ProfileInfo
from textwrap import dedent
from tools.tools_factory import (
    convert_to_langchain_tool,
    get_agent_tools,
    initialize_langchain_tools,
    initialize_tools,
)
from typing import Any, Dict, List, Tuple, Union

logger = configure_logger(__name__)

load_dotenv()

AIBTC_CREWAI_VERBOSE = os.getenv("AIBTC_CREWAI_VERBOSE", "false").lower() == "true"

# Common configurations
MANAGER_AGENT_CONFIG = {
    "role": "Task Manager",
    "goal": "Refine and manage tasks for the crew and assign them memory with a key to store their output.",
    "backstory": "You are responsible for optimizing the crew's workflow and ensuring tasks are well-structured.",
    "verbose": AIBTC_CREWAI_VERBOSE,
    "memory": True,
    "tools": [],
}


def create_manager_agent() -> Agent:
    """Create a standard manager agent with common configuration."""
    return Agent(**MANAGER_AGENT_CONFIG)


def create_agent(agent_data: Dict, tools_map: Dict) -> Agent:
    """Create an agent from agent data and tools map."""
    agent_tools = get_agent_tools(agent_data.get("agent_tools", []), tools_map)
    return Agent(
        role=agent_data.get("role"),
        goal=agent_data.get("goal"),
        backstory=agent_data.get("backstory"),
        verbose=AIBTC_CREWAI_VERBOSE,
        memory=True,
        allow_delegation=False,
        tools=agent_tools,
    )


def create_task(task_data: Dict, agent: Agent, input_str: str = None) -> Task:
    """Create a task from task data and agent."""
    task_description = task_data.get("description")
    task_expected_output = task_data.get("expected_output")

    if input_str:
        task_description = f"{task_description}\n\nuser_input: {input_str}"

    refined_task_description = f"Refined by Manager: {str(task_description)}"
    refined_task_expected_output = (
        f"Manager's expected outcome: {str(task_expected_output)}"
    )

    return Task(
        description=refined_task_description,
        expected_output=refined_task_expected_output,
        agent=agent,
        async_execution=False,
    )


def create_crew(agents: List[Agent], tasks: List[Task], **kwargs) -> Crew:
    """Create a crew with common configuration."""
    return Crew(
        agents=agents,
        tasks=tasks,
        manager_agent=create_manager_agent(),
        process=Process.sequential,
        memory=True,
        verbose=AIBTC_CREWAI_VERBOSE,
        **kwargs,
    )


def fetch_crew_data(crew_id: int) -> Tuple[List, List]:
    """Fetch agents and tasks for the specified crew from Supabase."""

    agents_response = db.get_crew_agents(crew_id)
    tasks_response = db.get_crew_tasks(crew_id)
    print(agents_response)
    print(tasks_response)

    if not agents_response or not tasks_response:
        raise ValueError("No agents or tasks found for the specified crew.")
    return agents_response, tasks_response


def build_agents_dict(agents_data: List, tools_map: Dict) -> Dict[int, Agent]:
    """Build a dictionary of agents from agents data."""
    return {
        agent_data["id"]: create_agent(agent_data, tools_map)
        for agent_data in agents_data
    }


def build_tasks_list(
    tasks_data: List, agents: Dict[int, Agent], input_str: str = None
) -> List[Task]:
    """Build a list of tasks from tasks data."""
    tasks = []
    for task_data in tasks_data:
        agent_id = task_data["agent_id"]
        if agent_id not in agents:
            raise ValueError(
                f"Agent with id {agent_id} not found for task {task_data['id']}."
            )
        tasks.append(create_task(task_data, agents[agent_id], input_str))
    return tasks


def extract_filtered_content(history: List) -> str:
    """Extract and filter content from chat history."""
    filtered_content = []
    for message in history:
        if isinstance(message, str):
            filtered_content.append(message)
        elif isinstance(message, dict):
            if message.get("role") == "assistant" and message.get("type") == "result":
                filtered_content.append(message.get("content", ""))
    return "\n".join(filtered_content)


def execute_crew(profile: ProfileInfo, crew_id: int, input_str: str) -> str:
    """Execute a crew synchronously."""
    tools_map = initialize_tools(profile)
    agents_data, tasks_data = fetch_crew_data(crew_id)

    agents = build_agents_dict(agents_data, tools_map)
    tasks = build_tasks_list(tasks_data, agents, input_str)
    crew = create_crew(list(agents.values()), tasks)

    return crew.kickoff(inputs={"user_input": input_str})


def build_single_crew(agents_data: List, tasks_data: List) -> Crew:
    """Build a single crew with the given agents and tasks data."""
    profile = ProfileInfo(account_index="", id=0)
    tools_map = initialize_tools(profile)
    agents = build_agents_dict(agents_data, tools_map)
    tasks = build_tasks_list(tasks_data, agents)
    return create_crew(list(agents.values()), tasks)


async def execute_chat_stream(profile: ProfileInfo, history: List, input_str: str):
    """Execute a chat stream with history."""
    callback_queue = asyncio.Queue()
    tools_map = initialize_tools(profile)
    filtered_content = extract_filtered_content(history)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    def chat_step_callback(step: Union[Dict[str, Any], AgentAction, AgentFinish]):
        if isinstance(step, AgentAction):
            asyncio.run_coroutine_threadsafe(
                callback_queue.put(
                    {
                        "type": "step",
                        "role": "assistant",
                        "content": step.thought,
                        "thought": step.thought,
                        "result": step.result,
                        "tool": step.tool,
                        "tool_input": step.tool_input,
                    }
                ),
                loop,
            )
        elif isinstance(step, AgentFinish):
            asyncio.run_coroutine_threadsafe(
                callback_queue.put(
                    {
                        "type": "step",
                        "role": "assistant",
                        "content": step.output,
                        "thought": step.thought,
                        "result": step.output,
                        "tool": None,
                        "tool_input": None,
                    }
                ),
                loop,
            )

    def chat_task_callback(task: TaskOutput):
        asyncio.run_coroutine_threadsafe(
            callback_queue.put(
                {"type": "task", "role": "assistant", "content": task.summary}
            ),
            loop,
        )

    chat_specialist = Agent(
        role="Chat Specialist",
        goal="You are responsible for interacting with the user and translating their query into an action.",
        backstory="You are trained to understand the user's query and provide the information they need with your tools, then analyzing the connection between the user's input and the result.",
        tools=tools_map.values(),
        verbose=AIBTC_CREWAI_VERBOSE,
        memory=False,
        allow_delegation=True,
    )

    task_description = dedent(
        f"""
        Review the user's input and chat history, then respond appropriately.
        
        Chat History:
        {filtered_content}
        
        Current Input:
        {input_str}
        
        Analyze the input and history, then provide a response that:
        1. Addresses the user's current query
        2. Takes into account any relevant context from the chat history
        3. Uses available tools when necessary to gather information or perform actions
        4. Maintains a consistent and helpful tone throughout the interaction
    """
    ).strip()

    review_user_input = Task(
        description=task_description,
        expected_output="A clear and contextually appropriate response to the user's input",
        agent=chat_specialist,
    )

    crew = create_crew(
        [chat_specialist],
        [review_user_input],
        step_callback=chat_step_callback,
        task_callback=chat_task_callback,
    )

    kickoff_future = loop.run_in_executor(None, crew.kickoff)

    while not kickoff_future.done():
        try:
            result = await asyncio.wait_for(callback_queue.get(), timeout=0.1)
            yield result
        except asyncio.TimeoutError:
            continue

    final_result = await kickoff_future
    while not callback_queue.empty():
        yield await callback_queue.get()
    yield {
        "type": "result",
        "content": final_result.raw,
        "tokens": final_result.token_usage.total_tokens,
    }


async def execute_crew_stream(profile: ProfileInfo, crew_id: int, input_str: str):
    """Execute a crew with streaming output."""
    callback_queue = asyncio.Queue()
    tools_map = initialize_tools(profile)

    try:
        agents_data, tasks_data = fetch_crew_data(crew_id)
    except ValueError as e:
        yield {"type": "result", "content": f"Error fetching crew data: {e}"}
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    def crew_step_callback(step: Union[Dict[str, Any], AgentAction, AgentFinish]):
        if isinstance(step, AgentAction):
            asyncio.run_coroutine_threadsafe(
                callback_queue.put(
                    {
                        "type": "step",
                        "role": "assistant",
                        "content": step.thought,
                        "thought": step.thought,
                        "result": step.result,
                        "tool": step.tool,
                        "tool_input": step.tool_input,
                    }
                ),
                loop,
            )
        elif isinstance(step, AgentFinish):
            asyncio.run_coroutine_threadsafe(
                callback_queue.put(
                    {
                        "type": "step",
                        "role": "assistant",
                        "content": step.output,
                        "thought": step.thought,
                        "result": step.output,
                        "tool": None,
                        "tool_input": None,
                    }
                ),
                loop,
            )

    def crew_task_callback(task: TaskOutput):
        asyncio.run_coroutine_threadsafe(
            callback_queue.put(
                {"type": "task", "role": "assistant", "content": task.summary}
            ),
            loop,
        )

    agents = build_agents_dict(agents_data, tools_map)
    tasks = build_tasks_list(tasks_data, agents, input_str)
    crew = create_crew(
        list(agents.values()),
        tasks,
        step_callback=crew_step_callback,
        task_callback=crew_task_callback,
    )

    kickoff_future = loop.run_in_executor(None, crew.kickoff, {"user_input": input_str})

    while not kickoff_future.done():
        try:
            result = await asyncio.wait_for(callback_queue.get(), timeout=0.1)
            yield result
        except asyncio.TimeoutError:
            continue

    final_result = await kickoff_future
    while not callback_queue.empty():
        yield await callback_queue.get()
    yield {
        "type": "result",
        "content": final_result.raw,
        "tokens": final_result.token_usage.total_tokens,
    }


async def execute_chat_stream_langgraph(
    profile: ProfileInfo, history: List, input_str: str
):
    """Execute a chat stream using LangGraph."""
    logger.debug("Starting execute_chat_stream_langgraph")
    callback_queue = asyncio.Queue()
    tools_map = initialize_langchain_tools(profile)  # Use LangChain tools
    filtered_content = extract_filtered_content(history)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    logger.debug(f"Converting history to messages, history length: {len(history)}")
    # Convert history to LangChain message format
    messages = []
    for msg in filtered_content:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))

    # Add the current input
    messages.append(HumanMessage(content=input_str))
    logger.debug(f"Final messages length: {len(messages)}")

    # Create the chat model with streaming
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
        temperature=0.7,  # Add some temperature for more natural responses
    )

    # Define the tool selection node
    async def tool_selection_node(state):
        logger.debug("Entering tool_selection_node")
        logger.debug(f"Current state messages: {len(state['messages'])}")

        try:
            if should_use_tool(state):
                logger.debug("Tool usage detected, initializing agent")
                # Convert tools list to LangChain format
                tools = list(tools_map.values())
                logger.debug(f"Using {len(tools)} tools")

                # Configure the agent with tools
                agent = initialize_agent(
                    tools=tools,
                    llm=chat,
                    agent=AgentType.OPENAI_FUNCTIONS,  # More flexible agent type
                    verbose=True,
                    handle_parsing_errors=True,
                    max_iterations=3,  # Limit iterations to prevent infinite loops
                    return_intermediate_steps=True,  # Get intermediate steps for streaming
                )

                try:
                    logger.debug("Running agent with tools")
                    # Get the last message content
                    last_message = (
                        state["messages"][-1].content if state["messages"] else ""
                    )

                    # Run the agent with proper async handling
                    agent_result = await agent.ainvoke(
                        {"input": last_message},
                        config={"callbacks": [callback_handler]},
                    )

                    # Stream intermediate steps
                    if "intermediate_steps" in agent_result:
                        for step in agent_result["intermediate_steps"]:
                            if hasattr(step[0], "tool"):
                                # Stream tool execution
                                await callback_queue.put(
                                    {
                                        "type": "tool_execution",
                                        "tool": step[0].tool,
                                        "input": step[0].tool_input,
                                        "output": (
                                            step[1] if step[1] is not None else ""
                                        ),
                                    }
                                )

                    # Get final response
                    response_content = agent_result.get("output", "")
                    logger.debug(
                        f"Agent response received: {response_content[:100]}..."
                    )

                    return {
                        "messages": state["messages"]
                        + [AIMessage(content=response_content)],
                        "response": response_content,
                    }
                except Exception as e:
                    logger.error(f"Error in tool execution: {str(e)}")
                    # Fallback to regular chat if tool execution fails
                    logger.debug("Falling back to regular chat after tool error")

            # Use regular chat without tools (either by choice or after tool failure)
            logger.debug("Using regular chat without tools")
            messages = state["messages"]
            response = await chat.ainvoke(messages)
            response_content = (
                response.content if hasattr(response, "content") else str(response)
            )
            logger.debug(f"Chat response received: {response_content[:100]}...")
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
    while True:
        try:
            logger.debug("Waiting for data from callback queue")
            data = await callback_queue.get()
            logger.debug(f"Received data from queue: {data}")
            if data["type"] == "end":
                break
            yield data
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

    def on_llm_start(self, *args, **kwargs) -> None:
        """Run when LLM starts running."""
        self.tokens = []

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        """Run on new token. Only available when streaming is enabled."""
        self.tokens.append(token)
        if self._on_llm_new_token:
            self._on_llm_new_token(token, **kwargs)

    def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        """Run when LLM ends running."""
        if self._on_llm_end:
            self._on_llm_end(response, **kwargs)

    def on_llm_error(self, error: Exception, **kwargs) -> None:
        """Run when LLM errors."""
        logger.error(f"LLM error: {str(error)}")


def should_use_tool(state):
    """Determine if a tool should be used based on the current state."""
    messages = state["messages"]
    last_message = messages[-1].content if messages else ""

    # Add your conditional logic here
    # Example conditions:
    if any(
        keyword in last_message.lower()
        for keyword in ["price", "balance", "transaction", "wallet"]
    ):
        return True
    if "get" in last_message.lower() and any(
        resource in last_message.lower()
        for resource in ["token", "contract", "address"]
    ):
        return True
    return False
