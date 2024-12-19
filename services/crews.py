import asyncio
import os
from crewai import Agent, Crew, Process, Task
from crewai.agents.parser import AgentAction, AgentFinish
from crewai.tasks.task_output import TaskOutput
from db.factory import db
from dotenv import load_dotenv
from lib.logger import configure_logger
from textwrap import dedent
from tools.tools_factory import get_agent_tools, initialize_tools
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


def execute_crew(account_index: str, crew_id: int, input_str: str) -> str:
    """Execute a crew synchronously."""
    tools_map = initialize_tools(account_index)
    agents_data, tasks_data = fetch_crew_data(crew_id)

    agents = build_agents_dict(agents_data, tools_map)
    tasks = build_tasks_list(tasks_data, agents, input_str)
    crew = create_crew(list(agents.values()), tasks)

    return crew.kickoff(inputs={"user_input": input_str})


def build_single_crew(agents_data: List, tasks_data: List) -> Crew:
    """Build a single crew with the given agents and tasks data."""
    tools_map = initialize_tools("0")
    agents = build_agents_dict(agents_data, tools_map)
    tasks = build_tasks_list(tasks_data, agents)
    return create_crew(list(agents.values()), tasks)


async def execute_crew_stream(account_index: str, crew_id: int, input_str: str):
    """Execute a crew with streaming output."""
    callback_queue = asyncio.Queue()
    tools_map = initialize_tools(account_index)

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


async def execute_chat_stream(account_index: str, history: List, input_str: str):
    """Execute a chat stream with history."""
    callback_queue = asyncio.Queue()
    tools_map = initialize_tools(account_index)
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
