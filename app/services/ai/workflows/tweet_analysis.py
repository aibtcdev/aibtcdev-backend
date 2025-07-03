from typing import Dict, Optional, TypedDict

from langchain_core.prompts.chat import ChatPromptTemplate
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from app.backend.factory import backend
from app.backend.models import QueueMessageFilter, TweetType
from app.lib.logger import configure_logger
from app.services.ai.workflows.base import BaseWorkflow
from app.tools.dao_deployments import ContractDAODeployInput

logger = configure_logger(__name__)


class ToolRequest(BaseModel):
    tool_name: str = Field(
        description="The name of the tool to be executed its always contract_deploy_dao"
    )
    parameters: ContractDAODeployInput = Field(
        description="The parameters for the tool"
    )
    priority: int = Field(description="The priority of the tool request")


class TweetAnalysisOutput(BaseModel):
    worthy: bool = Field(description="Whether the tweet is worthy of processing")
    reason: str = Field(description="The reason for the worthy determination")
    tweet_type: TweetType = Field(description="The type of tweet")
    tool_request: Optional[ToolRequest] = Field(
        description="The tool request to be executed if the tweet is worthy"
    )
    confidence_score: float = Field(
        description="The confidence score for the worthy determination"
    )


class AnalysisState(TypedDict):
    """State for the analysis flow."""

    tweet_text: str
    filtered_content: str
    is_worthy: bool
    tweet_type: TweetType
    tool_request: Optional[ToolRequest]
    confidence_score: float
    reason: str


class TweetAnalysisWorkflow(BaseWorkflow[AnalysisState]):
    """Workflow for analyzing tweets."""

    def __init__(self, account_name: str = "@aibtcdevagent", **kwargs):
        super().__init__(**kwargs)
        self.account_name = account_name

    def _create_chat_messages(
        self,
        tweet_text: str,
        filtered_content: str,
        account_name: str,
        token_symbols: list,
    ) -> list:
        """Create chat messages for tweet analysis.

        Args:
            tweet_text: The current tweet text to analyze
            filtered_content: Filtered content from tweet history
            account_name: The account name analyzing tweets
            token_symbols: List of token symbols already taken

        Returns:
            List of chat messages
        """
        # System message with analysis guidelines
        system_content = f"""You are {account_name}, a specialized DAO deployment analysis agent. Your role is to analyze tweets to determine if they contain valid DAO deployment requests and extract the necessary parameters.

Analysis Guidelines:
1. Determine if the tweet is worthy of processing (contains a valid DAO deployment request)
2. Classify the tweet type: tool_request, thread, or invalid
3. For tool requests, extract required parameters for contract_deploy_dao tool:
   - token_symbol: Symbol for the token (e.g., 'HUMAN')
   - token_name: Name of the token (e.g., 'Human')
   - token_description: Description of the token
   - token_max_supply: Initial supply (default: 1000000000)
   - token_decimals: Number of decimals (default: 6)
   - origin_address: Address of the DAO creator
   - mission: Mission statement serving as the unifying purpose and guiding principle
   - tweet_id: ID of the tweet

Worthiness Criteria:
- Welcome creativity—funny or edgy ideas are encouraged
- Concepts must avoid harmful or unethical themes
- While flexible on ethics, there's a clear line against promoting harm
- Worth depends on substance and alignment with basic principles
- General conversations unrelated to DAO creation should be marked as not worthy
- Purely promotional content without actionable details should be marked as not worthy

Token Symbol Rules:
- Ensure the DAO symbol is not already taken from the provided list
- If taken, choose a new unique symbol for the parameters
- Only craft parameters if worthiness determination is True

Note: Your sole purpose is to analyze and generate parameters, not to execute the contract_deploy_dao tool.

Output Format:
Provide a JSON object with:
- worthy: Boolean indicating if tweet is worthy of processing
- reason: Explanation for the worthy determination
- tweet_type: Classification as "tool_request", "thread", or "invalid"
- tool_request: Object with tool_name "contract_deploy_dao", parameters, and priority (only if worthy and tool_request type)
- confidence_score: Float between 0.0 and 1.0 for confidence in determination"""

        # User message with the specific analysis request
        user_content = f"""Please analyze the following tweet information:

Current Tweet:
{tweet_text}

Tweet History Context:
{filtered_content}

Current DAO Symbols Already Taken:
{", ".join(token_symbols) if token_symbols else "None"}

Based on this information, determine if this tweet contains a valid DAO deployment request and extract the necessary parameters if applicable."""

        return [
            ("system", system_content),
            ("human", user_content),
        ]

    def _create_graph(self) -> StateGraph:
        """Create the analysis graph."""

        # Create analysis node
        def analyze_tweet(state: AnalysisState) -> AnalysisState:
            """Analyze the tweet and determine if it's worthy of processing."""
            tokens = backend.list_tokens()
            token_symbols_in_db = [token.symbol for token in tokens]
            queued_messages = backend.list_queue_messages(
                filters=QueueMessageFilter(type="daos", is_processed=False)
            )
            token_symbols_in_queue = [
                message.message["parameters"]["token_symbol"]
                for message in queued_messages
            ]

            # make a list of token symbols in queue and token symbols in db
            token_symbols = list(set(token_symbols_in_db + token_symbols_in_queue))

            # Create chat messages
            messages = self._create_chat_messages(
                tweet_text=state["tweet_text"],
                filtered_content=state["filtered_content"],
                account_name=self.account_name,
                token_symbols=token_symbols,
            )

            # Create chat prompt template
            prompt = ChatPromptTemplate.from_messages(messages)
            formatted_prompt = prompt.format()

            structured_output = self.llm.with_structured_output(
                TweetAnalysisOutput,
            )
            # Get analysis from LLM
            result = structured_output.invoke(formatted_prompt)

            # Update state
            state["is_worthy"] = result.worthy
            state["tweet_type"] = result.tweet_type
            state["tool_request"] = result.tool_request
            state["confidence_score"] = result.confidence_score
            state["reason"] = result.reason

            return state

        # Create the graph
        workflow = StateGraph(AnalysisState)

        # Add nodes
        workflow.add_node("analyze", analyze_tweet)

        # Add edges
        workflow.set_entry_point("analyze")
        workflow.add_edge("analyze", END)

        return workflow.compile()

    def _validate_state(self, state: AnalysisState) -> bool:
        """Validate the workflow state."""
        required_fields = ["tweet_text", "filtered_content"]
        return all(field in state and state[field] for field in required_fields)


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

    # Create and run workflow
    workflow = TweetAnalysisWorkflow()
    result = await workflow.execute(state)

    return result
