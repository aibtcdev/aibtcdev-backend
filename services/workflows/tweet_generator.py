"""Tweet generator workflow."""

from langchain.prompts import PromptTemplate
from langgraph.graph import END, Graph, StateGraph
from lib.logger import configure_logger
from pydantic import BaseModel, Field
from services.workflows.base import BaseWorkflow
from typing import Dict, TypedDict

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

    def _create_prompt(self) -> PromptTemplate:
        """Create the generator prompt template."""
        return PromptTemplate(
            input_variables=["dao_name", "dao_symbol", "dao_mission", "dao_id"],
            template="""
            Generate an exciting tweet announcing the successful deployment of a new DAO.
            
            DAO Details:
            - Name: {dao_name}
            - Symbol: {dao_symbol}
            - Mission: {dao_mission}

            Requirements:
            1. Must be under 200 characters (not including URL) to leave room for the URL
            2. Should be enthusiastic and welcoming
            3. Include the DAO symbol with $ prefix
            4. Mention key aspects of the mission
            5. Use emojis appropriately but don't overdo it (2-3 max)
            6. REQUIRED: End the tweet with the URL https://aibtc.dev/daos/{dao_id}
            
            Output format:
            {{
                "tweet_text": str,
                "confidence_score": float
            }}
            """,
        )

    def _create_graph(self) -> Graph:
        """Create the generator graph."""
        prompt = self._create_prompt()

        # Create generation node
        def generate_tweet(state: GeneratorState) -> GeneratorState:
            """Generate the tweet response."""
            # Format prompt with state
            formatted_prompt = prompt.format(
                dao_name=state["dao_name"],
                dao_symbol=state["dao_symbol"],
                dao_mission=state["dao_mission"],
                dao_id=state["dao_id"],
            )

            # Get generation from LLM
            structured_output = self.llm.with_structured_output(
                TweetGeneratorOutput,
            )
            result = structured_output.invoke(formatted_prompt)

            # Clean and parse the response
            # content = self._clean_llm_response(result.content)
            # parsed_result = TweetGeneratorOutput.model_validate_json(content)

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
