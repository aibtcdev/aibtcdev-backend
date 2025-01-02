import logging
import sys
import re
from .crews import extract_filtered_content
from .twitter import TwitterService
from .dao_analyzer import DAORequestAnalyzer, DAOAnalysisResult
from backend.models import Profile
from crewai import Agent, Task
from crewai.flow.flow import Flow, listen, router, start
from enum import Enum
from pydantic import BaseModel
from textwrap import dedent
from tools.tools_factory import initialize_tools
from typing import Any, AsyncGenerator, Dict, List, Optional

# Configure logging with console handler
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create console handler with formatting
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)

# Add handler to logger if it doesn't already have handlers
if not logger.handlers:
    logger.addHandler(console_handler)

# Ensure propagation to root logger
logger.propagate = True


# Output schemas for tasks
class TweetType(str, Enum):
    DAO_REQUEST = "dao_request"
    TOOL_REQUEST = "tool_request"
    CONVERSATION = "conversation"
    INVALID = "invalid"


class ToolRequest(BaseModel):
    tool_name: str
    parameters: Dict[str, Any]
    priority: int = 1


class TweetAnalysisOutput(BaseModel):
    worthy: bool
    reason: str
    tweet_type: TweetType
    tool_request: ToolRequest = None
    confidence_score: float


class TweetResponseOutput(BaseModel):
    response: str
    tone: str
    hashtags: List[str]
    mentions: List[str]
    urls: List[str]


class ToolResponseOutput(BaseModel):
    success: bool
    status: str
    message: str
    details: Dict[str, Any]
    input_parameters: Dict[str, Any]


class TweetAnalysisState(BaseModel):
    is_worthy: bool = False
    tweet_type: TweetType = TweetType.INVALID
    tool_request: Optional[ToolRequest] = None
    response_required: bool = False
    tweet_text: str = ""
    filtered_content: str = ""
    analysis_complete: bool = False
    tool_result: str = None
    response: TweetResponseOutput = None
    tool_success: bool = False
    dao_analysis: Optional[DAOAnalysisResult] = None
    user_context: Optional[Dict] = None
    author_id: Optional[str] = None


class TweetProcessingFlow(Flow[TweetAnalysisState]):
    def __init__(self, twitter_service: TwitterService, profile: Profile):
        super().__init__()
        self.twitter_service = twitter_service
        self.profile = profile
        self.tools_map = initialize_tools(profile)
        self.dao_analyzer = DAORequestAnalyzer()
        logger.info(f"Initialized tools_map with {len(self.tools_map)} tools")
        self.analyzer_agent = self._create_analyzer_agent()
        self.tool_agent = self._create_tool_agent()
        self.response_agent = self._create_response_agent()
        self.account_name = "@aibtcdevagent"
        logger.info(f"TweetProcessingFlow initialized with account {self.account_name}")

    async def _gather_user_context(self, user_id: str) -> Dict:
        """Gather context about the user from their Twitter history."""
        try:
            # Get user's recent tweets
            tweets = await self.twitter_service.get_user_tweets(user_id)
            
            # Get user's profile
            profile = await self.twitter_service.get_user_profile(user_id)
            
            # Get pinned tweet if available
            pinned_tweet = await self.twitter_service.get_pinned_tweet(user_id)
            
            return {
                "tweets": tweets,
                "profile": profile,
                "pinned_tweet": pinned_tweet
            }
        except Exception as e:
            logger.error(f"Error gathering user context: {str(e)}")
            return {"tweets": [], "profile": None, "pinned_tweet": None}

    @start()
    async def analyze_tweet(self):
        """Analyze tweet with priority on DAO creation."""
        logger.info("🔄 Starting tweet analysis with DAO priority")

        # First gather user context
        logger.info("👤 Gathering user context...")
        user_context = await self._gather_user_context(self.state.author_id)
        self.state.user_context = user_context
        logger.info(f"📊 User context gathered: {len(user_context.get('tweets', [])) if user_context else 0} tweets")

        # Check for DAO creation request first
        logger.info("🔍 Analyzing for DAO creation request...")
        dao_analysis = await self.dao_analyzer.analyze_request(
            tweet_text=self.state.tweet_text,
            user_id=self.state.author_id,
            user_tweets=user_context["tweets"],
            user_profile=user_context["profile"]
        )
        self.state.dao_analysis = dao_analysis

        # If this is a valid DAO request, prioritize it
        if dao_analysis.is_valid:
            logger.info("✨ Valid DAO creation request detected!")
            logger.info(f"  Name: {dao_analysis.parameters.token_name}")
            logger.info(f"  Symbol: {dao_analysis.parameters.token_symbol}")
            logger.info(f"  Supply: {dao_analysis.parameters.token_max_supply}")
            
            self.state.is_worthy = True
            self.state.tweet_type = TweetType.DAO_REQUEST
            self.state.tool_request = ToolRequest(
                tool_name="contract_collective_deploy",
                parameters=dao_analysis.parameters.dict(),
                priority=1
            )
            return "execute_tool"

        # If not a DAO request, check for other patterns
        if re.search(r"@\w+\s+create\s+dao", self.state.tweet_text.lower()):
            logger.info("⚠️ Invalid DAO request format detected")
            self.state.is_worthy = True
            self.state.tweet_type = TweetType.DAO_REQUEST
            self.state.response_required = True
            return "generate_response"

        # If not a DAO request, proceed with regular analysis
        analysis_task = Task(
            name="tweet_analysis",
            description=dedent(
                f"""
                Your name is {self.account_name} on twitter.

                Analyze this tweet to determine:
                1. If it's worthy of processing
                2. If it's a tool request or conversation
                3. Required action priority
                
                Primary Focus:
                - Look for DAO creation intent first
                - Suggest DAO creation if relevant to user's query
                
                Tweet History:
                {self.state.filtered_content}
                
                Current Tweet:
                {self.state.tweet_text}
                
                Criteria for worthiness:
                - Relevance to Stacks/Bitcoin ecosystem
                - Technical merit and substance
                - Community value
                - Authenticity (not spam)
                
                Available Tools:
                - contract_collective_deploy (Primary: DAO Creation)
                - wallet_balance
                - transaction_status
                - price_history
                """
            ),
            agent=self.analyzer_agent,
            output_pydantic=TweetAnalysisOutput,
        )

        logger.info("Executing analysis task")
        result = analysis_task.execute_sync()
        logger.info(f"Analysis result: {result.pydantic}")

        self.state.is_worthy = result.pydantic.worthy
        self.state.tweet_type = result.pydantic.tweet_type
        self.state.tool_request = result.pydantic.tool_request
        self.state.analysis_complete = True

        if result.pydantic.tweet_type == TweetType.TOOL_REQUEST:
            logger.info("Routing to tool execution")
            return "execute_tool"
        elif result.pydantic.worthy:
            logger.info("Routing to response generation")
            return "generate_response"
        logger.info("Routing to skip")
        return "skip"

    @router(analyze_tweet)
    def route_tweet_processing(self):
        logger.info(
            f"Routing tweet processing. Worthy: {self.state.is_worthy}, Type: {self.state.tweet_type}"
        )
        if not self.state.is_worthy:
            return "skip"
        if self.state.tweet_type == TweetType.DAO_REQUEST:
            return "execute_tool"
        if self.state.tweet_type == TweetType.TOOL_REQUEST:
            return "execute_tool"
        return "generate_response"

    @listen("execute_tool")
    def handle_tool_execution(self):
        if not self.state.tool_request:
            logger.warning("Tool execution called but no tool request in state")
            return "generate_response"

        logger.info(f"Executing tool: {self.state.tool_request.tool_name}")
        tool_task = Task(
            name="tool_execution",
            description=dedent(
                f"""
                Execute the requested tool operation based on this tweet:
                
                Tweet History:
                {self.state.filtered_content}
                
                Current Tweet:
                {self.state.tweet_text}
                
                Tool Request:
                Tool: {self.state.tool_request.tool_name}
                Parameters: {self.state.tool_request.parameters}
                
                Requirements:
                1. Validate all required parameters
                2. Handle errors gracefully
                3. Provide detailed execution status
                4. Return results in structured format
            """
            ),
            expected_output="""
            Detailed tool execution results with status and output data

            Output format:
            {
                "success": bool,
                "status": str,
                "message": str,
                "details": Dict[str, Any],
                "input_parameters": Dict[str, Any]
            }

            """,
            agent=self.tool_agent,
            output_pydantic=ToolResponseOutput,
        )

        logger.info("Starting tool execution")
        result = tool_task.execute_sync()
        logger.info(f"Tool execution result: {result.raw if result else 'None'}")
        self.state.tool_result = result.raw if result else None
        self.state.tool_success = result.pydantic.success
        return "generate_response"

    @router(handle_tool_execution)
    def route_tweet_generation(self):
        logger.info(
            f"Routing tweet generation. Worthy: {self.state.is_worthy}, Type: {self.state.tweet_type}"
        )
        if self.state.tool_success:
            return "generate_response"
        return "skip"

    @listen("generate_response")
    def generate_tweet_response(self):
        """Generate response with DAO creation focus."""
        logger.info("💭 Starting response generation")
        
        # Special handling for DAO creation responses
        if (self.state.dao_analysis and self.state.dao_analysis.is_valid and 
            self.state.tool_success):
            logger.info("🎉 Generating successful DAO creation response")
            dao_params = self.state.dao_analysis.parameters
            response = dedent(f"""
                🎉 Your {dao_params.token_name} DAO is now live!
                🌐 Visit: https://daos.btc.us/{dao_params.token_symbol.lower()}
                📜 Contract: {self.state.tool_result.get('contract_address', 'N/A')}
                💰 ${dao_params.token_symbol} | {int(dao_params.token_max_supply):,} Supply

                {dao_params.mission}

                #StacksBlockchain #Web3 #DAO
            """).strip()

            logger.info(f"📝 Response generated ({len(response)} chars)")
            self.state.response = TweetResponseOutput(
                response=response,
                tone="enthusiastic",
                hashtags=["StacksBlockchain", "Web3", "DAO"],
                mentions=[],
                urls=[f"https://daos.btc.us/{dao_params.token_symbol.lower()}"]
            )
            return "complete"

        # Handle invalid DAO request format
        if self.state.tweet_type == TweetType.DAO_REQUEST:
            response = dedent("""
                🔧 To create a DAO, use one of these formats:

                1️⃣ Simple:
                @aibtcdevagent create dao MyDAO

                2️⃣ Detailed:
                @aibtcdevagent create dao
                name: My DAO
                symbol: DAO
                supply: 500M
                mission: Your mission

                Need help? Check our guide: https://daos.btc.us/guide
                #StacksBlockchain #DAO
            """).strip()

            self.state.response = TweetResponseOutput(
                response=response,
                tone="helpful",
                hashtags=["StacksBlockchain", "DAO"],
                mentions=[],
                urls=["https://daos.btc.us/guide"]
            )
            return "complete"

        # Regular response generation for other cases
        response_task = Task(
            name="response_generation",
            description=dedent(
                f"""
                Your name is {self.account_name} on twitter.

                Generate an appropriate response tweet.
                
                Primary Focus:
                - Suggest DAO creation if relevant
                - Guide users toward DAO functionality
                
                Tweet History:
                {self.state.filtered_content}
                
                Current Tweet:
                {self.state.tweet_text}
                
                Context:
                - Tweet Type: {self.state.tweet_type}
                - Tool Result: {self.state.tool_result if hasattr(self.state, 'tool_result') else 'None'}
                
                Requirements:
                1. Maximum 280 characters
                2. Professional yet engaging tone
                3. Include relevant hashtags
                4. Reference tool results if applicable
                5. Avoid financial advice
                6. Include relevant URLs
                7. Suggest DAO creation if appropriate
                """
            ),
            agent=self.response_agent,
            output_pydantic=TweetResponseOutput,
        )

        result = response_task.execute_sync()
        self.state.response = result.pydantic
        return "complete"

    @listen("skip")
    def handle_skip(self):
        logger.info(f"Skipping tweet. Type: {self.state.tweet_type}")
        return "complete"

    async def kickoff_async(self) -> Dict[str, Any]:
        logger.info("Starting async kickoff")
        await super().kickoff_async()
        result = {
            "tool_result": self.state.tool_result,
            "response": self.state.response.dict() if self.state.response else None,
        }
        logger.info(f"Kickoff result: {result}")
        return result

    def _create_analyzer_agent(self):
        # Give analyzer read-only access to all tools for awareness
        return Agent(
            role="Social Media Content Analyst",
            goal="Accurately analyze tweets for processing requirements",
            backstory=dedent(
                """
                Expert at analyzing social media content, particularly crypto-related tweets.
                Deep understanding of the Stacks ecosystem and blockchain technology.
                Skilled at detecting spam, trolling, and identifying valuable discussions.
                Capable of recognizing technical requests and tool execution needs.
                Can identify which tools would be needed but CANNOT execute them.
            """
            ),
            tools=list(self.tools_map.values()),
        )

    def _create_tool_agent(self):
        # Give tool agent access to all tools
        return Agent(
            role="Blockchain Tool Specialist",
            goal="Execute blockchain-related tools accurately and safely",
            backstory=dedent(
                """
                Specialized in executing blockchain operations like token deployment and DAO creation.
                Expert in parameter validation and security best practices.
                Extensive experience with Stacks smart contracts and token standards.
                Focused on safe and efficient tool execution.
                Has full access to execute all available tools.
            """
            ),
            tools=list(self.tools_map.values()),
        )

    def _create_response_agent(self):
        # Response agent gets no tools
        return Agent(
            role="Community Engagement Specialist",
            goal="Create engaging and appropriate tweet responses",
            backstory=dedent(
                """
                Expert communicator combining technical accuracy with engaging style.
                Deep knowledge of crypto Twitter etiquette and best practices.
                Skilled at crafting responses that educate and inspire.
                Maintains professional tone while being approachable and helpful.
                Creates responses based on analysis and tool execution results.
            """
            ),
            tools=[],  # No tools for response agent
        )


async def execute_twitter_stream(
    twitter_service: Any, profile: Profile, history: List, input_str: str, author_id: str
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Execute a chat stream with history using conditional tasks.

    Args:
        twitter_service: Twitter service instance
        profile: Profile instance containing account_index
        history: List of previous conversation messages
        input_str: Current tweet text to process
        author_id: ID of the tweet author

    Yields:
        Dict containing step information or final results
    """
    try:
        logger.info(f"Starting tweet stream processing for input: {input_str[:50]}...")
        filtered_content = extract_filtered_content(history)
        logger.info(f"Extracted filtered content length: {len(filtered_content)}")

        flow = TweetProcessingFlow(twitter_service, profile)
        flow.state.tweet_text = input_str
        flow.state.filtered_content = filtered_content
        flow.state.author_id = author_id  # Set the author_id in state

        logger.info("Starting flow execution")
        result = await flow.kickoff_async()
        logger.info(f"Flow execution completed. Result: {result}")

        if not flow.state.is_worthy:
            logger.info("Tweet not worthy of processing")
            yield {
                "type": "result",
                "reason": "Tweet not worthy of processing",
                "content": None,
            }
            return

        if flow.state.tweet_type == TweetType.DAO_REQUEST and flow.state.tool_request:
            logger.info(
                f"Yielding tool execution step for tool: {flow.state.tool_request.tool_name}"
            )
            yield {
                "type": "step",
                "role": "assistant",
                "content": f"Executing tool: {flow.state.tool_request.tool_name}",
                "thought": "Tool execution required",
                "tool": flow.state.tool_request.tool_name,
                "tool_input": flow.state.tool_request.parameters,
                "result": flow.state.tool_result,
            }

        logger.info(f"Final state - Response: {flow.state.response}")
        if flow.state.response and flow.state.response.response:
            logger.info("Yielding final response")
            yield {"type": "result", "content": flow.state.response.response}
        else:
            logger.warning("No response generated")
            yield {"type": "result", "reason": "No response generated", "content": None}

    except Exception as e:
        logger.error(f"Error in execute_twitter_stream: {str(e)}", exc_info=True)
        yield {
            "type": "result",
            "reason": f"Error processing tweet: {str(e)}",
            "content": None,
        }
