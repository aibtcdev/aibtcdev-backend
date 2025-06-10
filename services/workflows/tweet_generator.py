from typing import Dict, TypedDict

from langchain_core.prompts.chat import ChatPromptTemplate
from langgraph.graph import END, Graph, StateGraph
from pydantic import BaseModel, Field

from lib.logger import configure_logger
from services.workflows.base import BaseWorkflow

logger = configure_logger(__name__)


class TweetGeneratorOutput(BaseModel):
    """Output model for tweet generation."""

    tweet_text: str = Field(description="The generated tweet text")
    confidence_score: float = Field(description="The confidence score for the tweet")


class GeneratorState(TypedDict):
    """State for the tweet generation flow."""

    dao_name: str
    dao_symbol: str
    dao_mission: str
    generated_tweet: str
    confidence_score: float
    dao_id: str


class TweetGeneratorWorkflow(BaseWorkflow[GeneratorState]):
    """Workflow for generating tweets."""

    def _create_chat_messages(
        self, dao_name: str, dao_symbol: str, dao_mission: str, dao_id: str
    ) -> list:
        """Create chat messages for tweet generation.

        Args:
            dao_name: Name of the DAO
            dao_symbol: Symbol of the DAO
            dao_mission: Mission statement of the DAO
            dao_id: ID of the DAO

        Returns:
            List of chat messages
        """
        # System message with guidelines
        system_content = """You are a social media expert specializing in crypto and DAO announcements. Generate exciting, engaging tweets that announce successful DAO deployments while maintaining professionalism and community focus.

Guidelines:
- Keep tweets under 200 characters (not including URL) to leave room for the URL
- Be enthusiastic and welcoming in tone
- Include the DAO symbol with $ prefix
- Mention key aspects of the mission concisely
- Use emojis appropriately but don't overdo it (2-3 max)
- Create content that encourages community engagement
- End with the provided DAO URL

Output Format:
Provide a JSON object with:
- tweet_text: The complete tweet text including the URL
- confidence_score: A float between 0.0 and 1.0 indicating confidence in the tweet quality"""

        # User message with specific DAO details
        user_content = f"""Generate an exciting tweet announcing the successful deployment of a new DAO with the following details:

DAO Name: {dao_name}
Symbol: {dao_symbol}
Mission: {dao_mission}
URL: https://aibtc.dev/daos/{dao_id}

Create a tweet that celebrates this new DAO launch, highlights its unique mission, and invites the community to participate."""

        return [
            ("system", system_content),
            ("human", user_content),
        ]

    def _create_graph(self) -> Graph:
        """Create the generator graph."""

        # Create generation node
        def generate_tweet(state: GeneratorState) -> GeneratorState:
            """Generate the tweet response."""
            # Create chat messages
            messages = self._create_chat_messages(
                dao_name=state["dao_name"],
                dao_symbol=state["dao_symbol"],
                dao_mission=state["dao_mission"],
                dao_id=state["dao_id"],
            )

            # Create chat prompt template
            prompt = ChatPromptTemplate.from_messages(messages)
            formatted_prompt = prompt.format()

            # Get generation from LLM
            structured_output = self.llm.with_structured_output(
                TweetGeneratorOutput,
            )
            result = structured_output.invoke(formatted_prompt)

            # Update state
            state["generated_tweet"] = result.tweet_text
            state["confidence_score"] = result.confidence_score

            return state

        # Create the graph
        workflow = StateGraph(GeneratorState)

        # Add nodes
        workflow.add_node("generate", generate_tweet)

        # Add edges
        workflow.set_entry_point("generate")
        workflow.add_edge("generate", END)

        return workflow.compile()

    def _validate_state(self, state: GeneratorState) -> bool:
        """Validate the workflow state."""
        required_fields = ["dao_name", "dao_symbol", "dao_mission", "dao_id"]
        return all(field in state and state[field] for field in required_fields)


async def generate_dao_tweet(
    dao_name: str, dao_symbol: str, dao_mission: str, dao_id: str
) -> Dict:
    """Generate a tweet announcing a new DAO deployment."""
    # Initialize state
    state = {
        "dao_name": dao_name,
        "dao_symbol": dao_symbol,
        "dao_mission": dao_mission,
        "generated_tweet": "",
        "confidence_score": 0.0,
        "dao_id": dao_id,
    }

    # Create and run workflow
    workflow = TweetGeneratorWorkflow()
    result = await workflow.execute(state)

    return {
        "tweet_text": result["generated_tweet"],
        "confidence_score": result["confidence_score"],
    }
