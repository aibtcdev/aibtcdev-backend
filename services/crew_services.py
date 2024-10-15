from backend.db.supabase_client import supabase
from crewai import Agent, Task, Crew, Process
from dotenv import load_dotenv
from backend.tools.tools_factory import initialize_tools, get_agent_tools


load_dotenv()
tools_map = initialize_tools()


# CHECK IF THE TOOLS ARE THERE OR NOT (ONLY FOR DEBUGGING)
print("Available tools:", tools_map)


# FUNCTION TO FETCH THE AGENTS AND TASKS FROM THE SUPABASE TABLE
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
    agents_response = supabase.from_('agents').select('*').eq('crew_id', crew_id).execute()
    tasks_response = supabase.from_('tasks').select('*').eq('crew_id', crew_id).execute()
    
    if not agents_response.data or not tasks_response.data:
        raise ValueError("No agents or tasks found for the specified crew.")
    
    return agents_response.data, tasks_response.data


# FUNCTION TO EXECUTE THE CREW
def execute_crew(crew_id: int, input_str: str):
    """
    Execute a crew by fetching agents and tasks for a given crew_id,
    refine the tasks using a hardcoded manager agent, and manage the flow of outputs.
    
    Args:
        crew_id (int): ID of the crew to be executed.
        input_str (str): User input to be incorporated into the initial task.

    Returns:
        str: The result of the crew's execution.
    """
    
    # FETCH AGENTS AND TASKS FROM THE CREW_ID
    agents_data, tasks_data = fetch_crew_data(crew_id)

    # CREATE AGENTS AND INDEX THEM BY AGENT_ID
    agents = {}

    for agent_data in agents_data:
        agent_role = agent_data.get('role')
        agent_goal = agent_data.get('goal')
        agent_backstory = agent_data.get('backstory')
        agent_tool_names = agent_data.get('agent_tools', [])
        
        agent_tools = get_agent_tools(agent_tool_names, tools_map)

        # CREATE THE AGENT WITH THE FETCHED DETAILS
        agent = Agent(
            role=agent_role,
            goal=agent_goal,
            backstory=agent_backstory,
            verbose=True,
            memory=True,
            allow_delegation=False,
            tools=agent_tools  # Assign tools (can be empty)
        )
        agents[agent_data['id']] = agent

    # MANAGER AGENT
    manager_agent = Agent(
        role="Task Manager",
        goal="Refine and manage tasks for the crew and assign them memory with a key to store their output so that the result compiler can access the output and compile the result properly.",
        backstory="You are responsible for optimizing the crew's workflow and ensuring tasks are well-structured.",
        verbose=True,
        memory=True,
        tools=[]  # No special tools needed for the manager
    )

    # CREATE TASKS FROM THE DATABASE AND PASS THEM TO THE MANAGER FOR REFINEMENT
    tasks = []
    task_outputs = {}

    for task_data in tasks_data:
        agent_id = task_data['agent_id']
        
        if agent_id not in agents:
            raise ValueError(f"Agent with id {agent_id} not found for task {task_data['id']}.")
        task_description = task_data.get('description')
        task_expected_output = task_data.get('expected_output')

        # If this is the first task, inject user input into the description
        if not task_outputs:  # If no tasks have been executed yet
            task_description = f"{task_description}\n\nuser_input: {input_str}"

        # Manager refines task descriptions and expected output
        refined_task_description = f"Refined by Manager: {str(task_description)}" 
        refined_task_expected_output = f"Manager's expected outcome: {str(task_expected_output)}" 

        # CREATE THE TASK WITH REFINED DETAILS
        task = Task(
            description=refined_task_description,
            expected_output=refined_task_expected_output,
            agent=agents[agent_id],
            async_execution=False
        )
        tasks.append(task)

    # RESULT COMPILER AGENT
    compiler_agent = Agent(
        role="Result Compiler",
        goal="Compile the results from the crew's memory and create a final report.",
        backstory="You are responsible for gathering the outputs of all the agents and presenting a comprehensive final result.",
        verbose=True,
        memory=True,
        tools=[]  # No special tools needed for the compiler
    )

    # TASK FOR RESULT COMPILER TO COMPILE THE RESULTS
    compile_task = Task(
        description="Access the crew's memory and compile a final report from the outputs of all tasks.",
        expected_output="A final summary report compiled from all task outputs.",
        agent=compiler_agent,
        async_execution=False
    )

    # ADD COMPILER AGENT AND TASK
    agents["result_compiler"] = compiler_agent
    tasks.append(compile_task)

    # CREATE THE CREW WITH ALL AGENTS (INCLUDING THE MANAGER AND COMPILER)
    crew = Crew(
        agents=list(agents.values()),
        tasks=tasks,
        manager_agent=manager_agent,
        process=Process.sequential,  # Ensure sequential execution of tasks
        memory=True
    )
    
    # EXECUTE THE CREW AND RETURN RESULTS
    print("\n--- Crew Execution Started ---")
    
    # Manager overseeing the crew execution and collecting results
    result = crew.kickoff(inputs={'user_input': input_str})

    # The final result will come after all agents finish their tasks
    return result

