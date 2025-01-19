from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import END, Graph, StateGraph
from lib.logger import configure_logger
from pydantic import BaseModel
from typing import Dict, TypedDict

logger = configure_logger(__name__)


class TweetGeneratorOutput(BaseModel):
    """Output model for tweet generation."""

    tweet_text: str
    confidence_score: float


class GeneratorState(TypedDict):
    """State for the tweet generation flow."""

    dao_name: str
    dao_symbol: str
    dao_mission: str
    generated_tweet: str
    confidence_score: float


def create_generator_prompt() -> PromptTemplate:
    """Create the generator prompt template."""
    return PromptTemplate(
        input_variables=["dao_name", "dao_symbol", "dao_mission"],
        template="""
        Generate an exciting tweet announcing the successful deployment of a new DAO.
        
        DAO Details:
        - Name: {dao_name}
        - Symbol: {dao_symbol}
        - Mission: {dao_mission}
        
        Requirements:
        1. Must be under 280 characters
        2. Should be enthusiastic and welcoming
        3. Include the DAO symbol with $ prefix
        4. Mention key aspects of the mission
        5. Use emojis appropriately but don't overdo it
        
        Output format:
        {{
            "tweet_text": str,
            "confidence_score": float
        }}
        """,
    )


def create_generator_graph() -> Graph:
    """Create the generator graph."""
    # Create LLM
    llm = ChatOpenAI(temperature=0.7, model="gpt-4")

    # Create prompt
    prompt = create_generator_prompt()

    # Create generation node
    def generate_tweet(state: GeneratorState) -> GeneratorState:
        """Generate the tweet response."""
        # Format prompt with state
        formatted_prompt = prompt.format(
            dao_name=state["dao_name"],
            dao_symbol=state["dao_symbol"],
            dao_mission=state["dao_mission"],
        )

        # Get generation from LLM
        result = llm.invoke(formatted_prompt)

        # Clean the content from markdown and get just the JSON
        content = result.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        # Parse the cleaned JSON
        parsed_result = TweetGeneratorOutput.model_validate_json(content)

        # Update state
        state["generated_tweet"] = parsed_result.tweet_text
        state["confidence_score"] = parsed_result.confidence_score

        return state

    # Create the graph
    workflow = StateGraph(GeneratorState)

    # Add nodes
    workflow.add_node("generate", generate_tweet)

    # Add edges
    workflow.set_entry_point("generate")
    workflow.add_edge("generate", END)

    return workflow.compile()


async def generate_dao_tweet(dao_name: str, dao_symbol: str, dao_mission: str) -> Dict:
    """Generate a tweet announcing a new DAO deployment."""
    # Initialize state
    state = {
        "dao_name": dao_name,
        "dao_symbol": dao_symbol,
        "dao_mission": dao_mission,
        "generated_tweet": "",
        "confidence_score": 0.0,
    }

    # Create and run graph
    graph = create_generator_graph()
    result = await graph.ainvoke(state)

    return {
        "tweet_text": result["generated_tweet"],
        "confidence_score": result["confidence_score"],
    }
