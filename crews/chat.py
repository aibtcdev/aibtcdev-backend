from crewai import Agent, Task
from lib.crews import AIBTC_Crew
from textwrap import dedent
from crewai_tools import BaseTool
from services.crew_services import build_all_crews


class UserChatSpecialistCrew(AIBTC_Crew):
    def __init__(self):
        super().__init__(
            "User Chat Specialist",
            "This crew is responsible for chat interactions with the user and providing support.",
        )
        self.crews = build_all_crews()
        self.tools = [cls() for cls in create_crew_tool_classes(self.crews)]
        print(self.tools)

    def setup_agents(self):
        chat_specialist = Agent(
            role="Chat Specialist",
            goal="You are responsible for interacting with the user and translating their query into an action.",
            backstory="You are trained to understand the user's query and provide the information they need with your tools, then analyzing the connection between the user's input and the result.",
            tools=self.tools,
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


def dynamic_class_from_dict(class_name: str, base_classes: tuple, attributes: dict):
    """
    Dynamically creates a class with the given name, base classes, and attributes.

    Args:
        class_name (str): Name of the class.
        base_classes (tuple): Base classes for inheritance.
        attributes (dict): Class-level attributes and methods.

    Returns:
        type: A dynamically generated class.
    """
    return type(class_name, base_classes, attributes)


def create_tool_class(crew):
    """
    Creates a class dynamically using the crew dictionary.
    """
    print(crew)

    def init(self):
        """Class constructor."""
        # Call the superclass constructor.
        super(BaseTool, self).__init__(
            name=crew["name"],
            description=crew["description"],
            args={"user_input": {"type": "string"}},
        )

    def _run(self, user_input):
        """Example run method based on crew logic."""
        try:
            # Dynamically call the crew's kickoff method or similar logic.
            result = crew["crew"]().kickoff()
            return result
        except Exception as e:
            return f"Error executing crew function: {e}"

    # Define the class attributes with the methods created above.
    class_attributes = {
        "__init__": init,
        "_run": _run,
    }

    # Create the dynamic class.
    crew_class = type(crew["name"], (BaseTool,), class_attributes)

    return crew_class


def create_crew_tool_classes(crews):
    """
    Create multiple dynamic tool classes from the given crew list.
    """
    tool_classes = []
    for crew in crews:
        if crew["description"] != None:
            tool_class = create_tool_class(crew)
            tool_classes.append(tool_class)
    return tool_classes
