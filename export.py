from crewai import Agent, Crew, Task
from db.client import supabase
from textwrap import dedent

# Create an analyst agent
analyst_agent = Agent(
    role="Data Analyst",
    goal="Analyze user inputs and identify patterns in usage and intentions",
    backstory=dedent(
        """
        You are an expert data analyst specializing in understanding user behavior 
        and usage patterns. Your goal is to analyze inputs and provide insights 
        about how people are using the system.
    """
    ),
    verbose=True,
    allow_delegation=False,
)

# Fetch jobs from database
jobs_response = (
    supabase.table("jobs")
    .select("input")
    .is_("conversation_id", "null")
    .order("created_at", desc=False)
    .execute()
)

# Prepare inputs for analysis
inputs = list(set(job["input"] for job in jobs_response.data))
inputs_text = "\n".join(f"- {input}" for input in inputs)

# Create analysis task
analysis_task = Task(
    description=f"""
    Analyze the following user inputs and create a comprehensive report:
    
    {inputs_text}
    
    Your report should include:
    1. Common patterns in user requests
    2. Main use cases identified
    3. User intentions and goals
    4. Recommendations for improvement
    
    Be specific and provide examples from the inputs.
    """,
    expected_output="""A detailed analysis report containing:
    - Patterns in user behavior
    - Use case categorization
    - User intention analysis
    - Actionable recommendations
    Format as a structured report with clear sections and examples.""",
    agent=analyst_agent,
)

# Create and run the crew
crew = Crew(agents=[analyst_agent], tasks=[analysis_task], verbose=True)

# Execute the analysis and get the report
result = crew.kickoff()
print("\nAnalysis Report:")
print("---------------")
print(result)
