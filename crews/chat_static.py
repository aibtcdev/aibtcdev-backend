from crewai import Agent, Task
from lib.crews import AIBTC_Crew
from textwrap import dedent


class UserChatSpecialistStaticCrew(AIBTC_Crew):
    def __init__(self):
        super().__init__(
            "User Chat Specialist",
            "This crew is responsible for chat interactions with the user and providing support.",
        )

    def setup_agents(self, tools):
        chat_specialist = Agent(
            role="Chat Specialist",
            goal="You are responsible for interacting with the user and translating their query into an action.",
            backstory="You are trained to understand the user's query and provide the information they need with your tools, then analyzing the connection between the user's input and the result.",
            tools=tools,
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
                1. If the user's input is a question without a task, do not execute a tool and clearly answer the question.
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
