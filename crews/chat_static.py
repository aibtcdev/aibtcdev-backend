from crewai import Agent, Task
from lib.crews import AIBTC_Crew
from textwrap import dedent
from crewai_tools import tool, Tool
from services.crew_services import build_all_crews
import inspect
from .trading_analyzer import TokenTradingAnalyzerCrew
from .trading_excecutor import TokenTradingExecutorCrew


class UserChatSpecialistStaticCrew(AIBTC_Crew):
    def __init__(self):
        super().__init__(
            "User Chat Specialist",
            "This crew is responsible for chat interactions with the user and providing support.",
        )

    def setup_agents(self):
        chat_specialist = Agent(
            role="Chat Specialist",
            goal="You are responsible for interacting with the user and translating their query into an action.",
            backstory="You are trained to understand the user's query and provide the information they need with your tools, then analyzing the connection between the user's input and the result.",
            tools=AgentTools.get_all_tools(),
            verbose=True,
            memory=False,
            allow_delegation=True,
        )
        self.add_agent(chat_specialist)

    def setup_tasks(self, user_input):
        review_user_input = Task(
            name="Review User Input",
            description=dedent(
                f"""
                The user is talking to you in chat format. You are tasked with reviewing the user's input and taking 1 of 2 actions:
                1. If the user's input is a question without a task, do not execute a crew and clearly answer the question.
                2. If the user's input is a task, use the appropriate tool to execute the task and summarize the result.
                ### User Input
                {user_input}
                """
            ),
            expected_output="The appropriate action has been taken.",
            agent=self.agents[0],  # chat_specialist
        )
        self.add_task(review_user_input)

    @staticmethod
    def get_task_inputs():
        return ["user_input"]

    @classmethod
    def get_all_tools(cls):
        return AgentTools.get_all_tools()


class AgentTools:
    @staticmethod
    @tool("Execute Trading Analyzer Crew")
    def execute_trading_analyzer_crew(crypto_symbol: str):
        """Execute the Trading Analyzer Crew to give a comprehensive review of a provided trading strategy."""
        try:
            if isinstance(crypto_symbol, dict):
                crypto_symbol = crypto_symbol.get("crypto_symbol", "")
            crew_class = TokenTradingAnalyzerCrew()
            crew_class.setup_agents()
            crew_class.setup_tasks(crypto_symbol)
            crew = crew_class.create_crew()
            crew.planning = True
            result = crew.kickoff()
            return result
        except Exception as e:
            return f"Error executing Trading Analyzer Crew: {e}"

    @staticmethod
    @tool("Execute Trading Executor Crew")
    def execute_trading_executor_crew(analysis_results: str, crypto_symbol: str):
        """Execute the Trading Executor Crew to execute trades based on trading signals provided by the Token Trading Analyzer crew."""
        try:
            crew_class = TokenTradingExecutorCrew()
            crew_class.setup_agents()
            crew_class.setup_tasks(analysis_results, crypto_symbol)
            crew = crew_class.create_crew()
            crew.planning = True
            result = crew.kickoff()
            return result
        except Exception as e:
            return f"Error executing Trading Analyzer Crew: {e}"

    @staticmethod
    @tool("List all available agent tools")
    def get_all_available_tools():
        """Get all available tools you have access to in order to assist the user."""
        # make an array of {name: tool_name, description: tool_description}
        tools = []
        for tool in AgentTools.get_all_tools():
            tools.append({"name": tool.name, "description": tool.description})
        return tools

    @classmethod
    def get_all_tools(cls):
        members = inspect.getmembers(cls)
        tools = [
            member
            for name, member in members
            if isinstance(member, Tool)
            or (hasattr(member, "__wrapped__") and isinstance(member.__wrapped__, Tool))
        ]
        return tools
