from typing import Any, Dict, Union
from crewai import Agent, Task, Crew, Process
from db.supabase_client import supabase
from tools.tools_factory import initialize_tools, get_agent_tools
from dotenv import load_dotenv
import asyncio
from crewai.agents.parser import AgentAction
from crewai.tasks.task_output import TaskOutput

load_dotenv()


def fetch_all_crews():
    """
    Fetch all crews and their respective agents and tasks from Supabase.

    Returns:
        dict: A dictionary where each key is a crew ID, and the value is a nested
              dictionary with 'name', 'description', 'agents', and 'tasks'.
    Raises:
        ValueError: If no crews are found in the database.
    """
    crews_response = supabase.from_("crews").select("id, name, description").execute()

    if not crews_response.data:
        raise ValueError("No crews found in the database.")

    crews_data = {}  # Dictionary to hold all crew data

    for crew in crews_response.data:
        crew_id = crew["id"]
        try:
            agents, tasks = fetch_crew_data(crew_id)
            crews_data[crew_id] = {
                "id": crew_id,
                "name": crew["name"],
                "description": crew["description"],
                "agents": agents,
                "tasks": tasks,
            }
        except ValueError as e:
            print(f"Skipping crew {crew_id}: {e}")

    return crews_data


def fetch_crew_data(crew_id: int):
    """
    Fetch agents and tasks for the specified crew from Supabase.
    Args:
        crew_id (int): ID of the crew whose agents and tasks are to be fetched.
    Returns:
        Tuple: A tuple containing a list of agents and a list of tasks.
    Raises:
        ValueError: If no agents or tasks are found for the specified crew.
    """
    agents_response = (
        supabase.from_("agents").select("*").eq("crew_id", crew_id).execute()
    )
    tasks_response = (
        supabase.from_("tasks").select("*").eq("crew_id", crew_id).execute()
    )

    if not agents_response.data or not tasks_response.data:
        raise ValueError("No agents or tasks found for the specified crew.")

    return agents_response.data, tasks_response.data


def execute_crew(account_index: str, crew_id: int, input_str: str):
    """
    Execute a crew by fetching agents and tasks for a given crew_id,
    refine the tasks using a hardcoded manager agent, and manage the flow of outputs.

    Args:
        crew_id (int): ID of the crew to be executed.
        input_str (str): User input to be incorporated into the initial task.

    Returns:
        str: The result of the crew's execution.
    """
    tools_map = initialize_tools(account_index)

    agents_data, tasks_data = fetch_crew_data(crew_id)
    agents = {}

    for agent_data in agents_data:
        agent_role = agent_data.get("role")
        agent_goal = agent_data.get("goal")
        agent_backstory = agent_data.get("backstory")
        agent_tool_names = agent_data.get("agent_tools", [])

        agent_tools = get_agent_tools(agent_tool_names, tools_map)

        agent = Agent(
            role=agent_role,
            goal=agent_goal,
            backstory=agent_backstory,
            verbose=True,
            memory=True,
            allow_delegation=False,
            tools=agent_tools,
        )
        agents[agent_data["id"]] = agent

    manager_agent = Agent(
        role="Task Manager",
        goal="Refine and manage tasks for the crew and assign them memory with a key to store their output.",
        backstory="You are responsible for optimizing the crew's workflow and ensuring tasks are well-structured.",
        verbose=True,
        memory=True,
        tools=[],
    )

    tasks = []
    task_outputs = {}

    for task_data in tasks_data:
        agent_id = task_data["agent_id"]

        if agent_id not in agents:
            raise ValueError(
                f"Agent with id {agent_id} not found for task {task_data['id']}."
            )
        task_description = task_data.get("description")
        task_expected_output = task_data.get("expected_output")

        if not task_outputs:
            task_description = f"{task_description}\n\nuser_input: {input_str}"

        refined_task_description = f"Refined by Manager: {str(task_description)}"
        refined_task_expected_output = (
            f"Manager's expected outcome: {str(task_expected_output)}"
        )

        task = Task(
            description=refined_task_description,
            expected_output=refined_task_expected_output,
            agent=agents[agent_id],
            async_execution=False,
        )
        tasks.append(task)

    crew = Crew(
        agents=list(agents.values()),
        tasks=tasks,
        manager_agent=manager_agent,
        process=Process.sequential,
        memory=True,
    )

    print("\n--- Crew Execution Started ---")
    result = crew.kickoff(inputs={"user_input": input_str})
    return result


def build_all_crews():
    """
    Build all the crews to be ready to execute.

    Args:
        input_str (str): User input to be incorporated into the initial task.

    Returns:
        str: The result of the crew's execution.
    """
    try:
        crews_data = fetch_all_crews()
    except ValueError as e:
        print(f"Error fetching crews: {e}")

    built_crews = [
        {
            "id": k,
            "name": v["name"],
            "description": v["description"],
            "crew": build_single_crew(v["agents"], v["tasks"]),
        }
        for k, v in crews_data.items()
    ]
    return built_crews


def build_single_crew(agents_data, tasks_data):
    """
    Build a single crew with the given agents and tasks data.
    """
    tools_map = initialize_tools("0")
    agents = {}

    for agent_data in agents_data:
        agent_role = agent_data.get("role")
        agent_goal = agent_data.get("goal")
        agent_backstory = agent_data.get("backstory")
        agent_tool_names = agent_data.get("agent_tools", [])

        agent_tools = get_agent_tools(agent_tool_names, tools_map)

        agent = Agent(
            role=agent_role,
            goal=agent_goal,
            backstory=agent_backstory,
            verbose=True,
            memory=True,
            allow_delegation=False,
            tools=agent_tools,
        )
        agents[agent_data["id"]] = agent

    manager_agent = Agent(
        role="Task Manager",
        goal="Refine and manage tasks for the crew and assign them memory with a key to store their output.",
        backstory="You are responsible for optimizing the crew's workflow and ensuring tasks are well-structured.",
        verbose=True,
        memory=True,
        tools=[],
    )

    tasks = []
    task_outputs = {}

    for task_data in tasks_data:
        agent_id = task_data["agent_id"]

        if agent_id not in agents:
            raise ValueError(
                f"Agent with id {agent_id} not found for task {task_data['id']}."
            )
        task_description = task_data.get("description")
        task_expected_output = task_data.get("expected_output")

        if not task_outputs:
            task_description = f"{task_description}\n\nuser_input: {{input_str}}"

        refined_task_description = f"Refined by Manager: {str(task_description)}"
        refined_task_expected_output = (
            f"Manager's expected outcome: {str(task_expected_output)}"
        )

        task = Task(
            description=refined_task_description,
            expected_output=refined_task_expected_output,
            agent=agents[agent_id],
            async_execution=False,
        )
        tasks.append(task)

    crew = Crew(
        agents=list(agents.values()),
        tasks=tasks,
        manager_agent=manager_agent,
        process=Process.sequential,
        memory=True,
    )

    return crew


async def execute_crew_stream(account_index: str, crew_id: int, input_str: str):
    tools_map = initialize_tools(account_index)
    agents_data, tasks_data = fetch_crew_data(crew_id)
    agents = {}

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    callback_queue = asyncio.Queue()

    def crew_step_callback(step: Union[Dict[str, Any], "AgentAction"]):
        asyncio.run_coroutine_threadsafe(
            callback_queue.put({"type": "step", "content": step.thought}), loop
        )

    def crew_task_callback(task: "TaskOutput"):
        asyncio.run_coroutine_threadsafe(
            callback_queue.put({"type": "task", "content": task.summary}), loop
        )

    for agent_data in agents_data:
        agent_role = agent_data.get("role")
        agent_goal = agent_data.get("goal")
        agent_backstory = agent_data.get("backstory")
        agent_tool_names = agent_data.get("agent_tools", [])
        agent_tools = get_agent_tools(agent_tool_names, tools_map)
        agent = Agent(
            role=agent_role,
            goal=agent_goal,
            backstory=agent_backstory,
            verbose=True,
            memory=True,
            allow_delegation=False,
            tools=agent_tools,
        )
        agents[agent_data["id"]] = agent

    manager_agent = Agent(
        role="Task Manager",
        goal="Refine and manage tasks for the crew and assign them memory with a key to store their output.",
        backstory="You are responsible for optimizing the crew's workflow and ensuring tasks are well-structured.",
        verbose=True,
        memory=True,
        tools=[],
    )

    tasks = []
    task_outputs = {}

    for task_data in tasks_data:
        agent_id = task_data["agent_id"]
        if agent_id not in agents:
            raise ValueError(
                f"Agent with id {agent_id} not found for task {task_data['id']}."
            )
        task_description = task_data.get("description")
        task_expected_output = task_data.get("expected_output")

        if not task_outputs:
            task_description = f"{task_description}\n\nuser_input: {input_str}"

        refined_task_description = f"Refined by Manager: {str(task_description)}"
        refined_task_expected_output = (
            f"Manager's expected outcome: {str(task_expected_output)}"
        )

        task = Task(
            description=refined_task_description,
            expected_output=refined_task_expected_output,
            agent=agents[agent_id],
            async_execution=False,
        )
        tasks.append(task)

    crew = Crew(
        agents=list(agents.values()),
        tasks=tasks,
        manager_agent=manager_agent,
        process=Process.sequential,
        memory=True,
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
        result = await callback_queue.get()
        yield result

    if final_result:
        yield {"type": "result", "content": final_result.raw}