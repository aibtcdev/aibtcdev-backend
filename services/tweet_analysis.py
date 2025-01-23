import os
from backend.factory import backend
from backend.models import QueueMessageCreate, QueueMessageFilter, TweetType, XTweetBase
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import END, Graph, StateGraph
from lib.logger import configure_logger
from pydantic import BaseModel
from tools.daos import ContractDAODeployInput
from typing import Dict, Optional, TypedDict

logger = configure_logger(__name__)


class ToolRequest(BaseModel):
    tool_name: str = "contract_dao_deploy"
    parameters: ContractDAODeployInput
    priority: int = 1


class TweetAnalysisOutput(BaseModel):
    worthy: bool
    reason: str
    tweet_type: TweetType
    tool_request: Optional[ToolRequest] = None
    confidence_score: float


class AnalysisState(TypedDict):
    """State for the analysis flow."""

    tweet_text: str
    filtered_content: str
    is_worthy: bool
    tweet_type: TweetType
    tool_request: Optional[ToolRequest]
    confidence_score: float
    reason: str


def create_analysis_prompt() -> PromptTemplate:
    """Create the analysis prompt template."""
    return PromptTemplate(
        input_variables=[
            "tweet_text",
            "filtered_content",
            "account_name",
            "token_symbols",
        ],
        template="""
        Your name is {account_name} on twitter.

        Analyze this tweet to determine:
        1. If it's worthy of processing (contains a valid DAO deployment request)
        2. What type of tweet it is (tool_request, thread, or invalid)
        3. If it's a tool request, extract the following required parameters:
           - token_symbol: The symbol for the token (e.g., 'HUMAN')
           - token_name: The name of the token (e.g., 'Human')
           - token_description: Description of the token (e.g., 'The Human Token')
           - token_max_supply: Initial supply (default: 1000000000)
           - token_decimals: Number of decimals (default: 6)
           - mission: The mission statement of the DAO serves as the unifying purpose and guiding principle of an AI DAO. It defines its goals, values, and desired impact, aligning participants and AI resources to achieve a shared outcome.
        
        Tweet History:
        {filtered_content}
        
        Current Tweet:
        {tweet_text}
        
        If the text is determined to be a general conversation, unrelated to creating or deploying a DAO, or if it appears to be promotional content, set Worthiness determination to False.

        Exclude tweets that are purely promotional and lack actionable parameters. If the tweet includes both praise and actionable details describing deploying a DAO, proceed with DAO deployment.

        Only craft the parameters for the tool contract_dao_deploy.
                        
        Requirements:
        1. Expand upon any missing details in the request for a dao to be deployed to meet the needs of the tool parameters
        2. If the tweet is a general conversation, unrelated to creating or deploying a DAO, or if it appears to be promotional content, set Worthiness determination to False.
        3. Don't execute the tool contract_dao_deploy as your sole purpose is to generate the parameters for the tool.
        4. Make sure the DAO symbol is not already taken. If it is already taken, choose a new symbol for the parameters.
        5. Only craft the parameters for the tool contract_dao_deploy if Worthiness determination is True.
        
        Worthiness criteria:
        - We welcome creativity—funny or edgy ideas are always welcome
        - Concepts must avoid harmful or unethical themes
        - While we're flexible on ethics, there's a clear line against promoting harm
        - Worth depends on substance and alignment with basic principles

        Current DAO Symbols already taken:
        {token_symbols}

        Output format:
        {{
            "worthy": bool,
            "reason": str,
            "tweet_type": "tool_request" | "thread" | "invalid",
            "tool_request": {{
                "tool_name": "contract_dao_deploy",
                "parameters": {{
                    "token_symbol": str,
                    "token_name": str,
                    "token_description": str,
                    "token_max_supply": str,
                    "token_decimals": str,
                    "mission": str
                }},
                "priority": int
            }} if worthy and tweet_type == "tool_request" else None,
            "confidence_score": float
        }}
        """,
    )


def create_analysis_graph(account_name: str = "@aibtcdevagent") -> Graph:
    """Create the analysis graph."""
    # Create LLM
    llm = ChatOpenAI(temperature=0, model="gpt-4o")

    # Create prompt
    prompt = create_analysis_prompt()

    # Create analysis node
    def analyze_tweet(state: AnalysisState) -> AnalysisState:
        """Analyze the tweet and determine if it's worthy of processing."""
        tokens = backend.list_tokens()
        token_symbols_in_db = [token.symbol for token in tokens]
        queued_messages = backend.list_queue_messages(
            filters=QueueMessageFilter(type="daos", is_processed=False)
        )
        token_symbols_in_queue = [
            message.message["parameters"]["token_symbol"] for message in queued_messages
        ]

        # make alist of token symbols in queue and token symbols in db
        token_symbols = list(set(token_symbols_in_db + token_symbols_in_queue))

        # Format prompt with state
        formatted_prompt = prompt.format(
            tweet_text=state["tweet_text"],
            filtered_content=state["filtered_content"],
            account_name=account_name,
            token_symbols=token_symbols,
        )

        # Get analysis from LLM
        result = llm.invoke(formatted_prompt)

        # Clean the content from markdown and get just the JSON
        content = result.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        # Parse the cleaned JSON
        parsed_result = TweetAnalysisOutput.model_validate_json(content)

        # Update state
        state["is_worthy"] = parsed_result.worthy
        state["tweet_type"] = parsed_result.tweet_type
        state["tool_request"] = parsed_result.tool_request
        state["confidence_score"] = parsed_result.confidence_score
        state["reason"] = parsed_result.reason

        return state

    # Create the graph
    workflow = StateGraph(AnalysisState)

    # Add nodes
    workflow.add_node("analyze", analyze_tweet)

    # Add edges
    workflow.set_entry_point("analyze")
    workflow.add_edge("analyze", END)

    return workflow.compile()


async def analyze_tweet(tweet_text: str, filtered_content: str) -> Dict:
    """Analyze a tweet and determine if it's worthy of processing."""
    # Initialize state
    state = {
        "tweet_text": tweet_text,
        "filtered_content": filtered_content,
        "is_worthy": False,
        "tweet_type": TweetType.INVALID,
        "tool_request": None,
        "confidence_score": 0.0,
        "reason": "",
    }

    # Create and run graph
    graph = create_analysis_graph()
    result = await graph.ainvoke(state)

    return result
