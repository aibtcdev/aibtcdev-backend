import logging
import sys
from .chat_stream_langgraph import extract_filtered_content
from .twitter import TwitterService
from backend.models import Profile
from crewai import Agent, Task
from crewai.flow.flow import Flow, listen, router, start
from datetime import datetime
from enum import Enum
from pydantic import BaseModel
from textwrap import dedent
from tools.tools_factory import filter_crewai_tools_by_names, initialize_tools
from typing import Any, AsyncGenerator, Dict, List, Optional
from uuid import UUID

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
    TOOL_REQUEST = "tool_request"
    CONVERSATION = "thread"
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
    has_feedback: bool = False


class TweetProcessingFlow(Flow[TweetAnalysisState]):
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

    def __init__(self, twitter_service: TwitterService):
        super().__init__()
        self.twitter_service = twitter_service
        self.tools_map_all = initialize_tools(
            Profile(
                id=UUID("ff163ed8-b084-4fb3-899c-c7d5e483afaf"),
                created_at=datetime.now(),
            ),
            agent_id=UUID("01ee34a3-a38c-44df-97be-b857a1bd9843"),
            crewai=True,
        )
        self.tools_map = filter_crewai_tools_by_names(
            ["contract_dao_deploy"], self.tools_map_all
        )
        logger.info(f"Initialized tools_map with {len(self.tools_map)} tools")
        self.analyzer_agent = self._create_analyzer_agent()
        self.tool_agent = self._create_tool_agent()
        self.response_agent = self._create_response_agent()
        self.account_name = "@aibtcdevagent"
        logger.info(f"TweetProcessingFlow initialized with account {self.account_name}")

    @start()
    def analyze_tweet(self):
        logger.info("Starting tweet analysis")
        analysis_task = Task(
            name="tweet_analysis",
            description=dedent(
                f"""
                Your name is {self.account_name} on twitter.

                Analyze this tweet to determine:
                1. Generate appropriate response for the tooling
                2. Use the DAO deployment tool
                
                Tweet History:
                {self.state.filtered_content}
                
                Current Tweet:
                {self.state.tweet_text}

                Only craft the parameters for the tool contract_dao_deploy.

                Don't execute the tool contract_dao_deploy as your sole purpose is to generate the parameters for the tool.
                                
                Requirements:
                1. Expand upon any missing details in the request for a dao to be deployed to meet the needs of the tool parameterss 
                
                Worthiness criteria:
                We welcome creativity—funny or edgy ideas are always welcome. 
                However, concepts must avoid harmful or unethical themes. 
                While we’re flexible on ethics, there’s a clear line against promoting harm. 
                We’ll help refine ideas, but their worth depends on substance and alignment with basic principles.

                Provide confidence score and detailed reasoning.
            """
            ),
            expected_output=dedent(
                """
                Structured analysis with:
                - Worthiness determination (boolean)
                - Tweet type classification
                    - "tool_request"
                    - "thread"
                    - "invalid"
                - Tool request details
                - Confidence score (0-1)
                - Detailed reasoning

                Output format:
                {
                    "worthy": bool,
                    "reason": str,
                    "tweet_type": TweetType,
                    "tool_request": ToolRequest,
                    "confidence_score": float
                }

                TweetType enum:
                - "tool_request"
                - "thread"
                - "invalid"

                ToolRequest:
                {
                    "tool_name": str,
                    "parameters": Dict[str, Any],
                    "priority": int
                }

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

        logger.info(f"Tweet worthiness: {result.pydantic.worthy}")
        logger.info(f"Tweet type: {result.pydantic.tweet_type}")
        logger.info(
            f"Tool request: {result.pydantic.tool_request}"
            if result.pydantic.tool_request
            else "Tool request: None"
        )
        logger.info(f"Confidence score: {result.pydantic.confidence_score}")

        # if result.pydantic.tweet_type == TweetType.TOOL_REQUEST:
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
        if self.state.tweet_type == TweetType.TOOL_REQUEST:
            return "execute_tool"
        return "generate_response"

    @listen("execute_tool") ## NOT RUNNING / SKIP
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
        logger.info("Starting response generation")
        response_task = Task(
            name="response_generation",
            description=dedent(
                f"""
                Your name is {self.account_name} on twitter.

                Generate an appropriate response tweet:
                
                Tweet History:
                {self.state.filtered_content}
                
                Current Tweet:
                {self.state.tweet_text}
                
                Context:
                - Tweet Type: {self.state.tweet_type}
                - Tool Execution: {self.state.tool_request is not None}
                - Tool Result: {self.state.tool_result if hasattr(self.state, 'tool_result') else 'None'}
                
                Make a post like congrats to the user for the dao deployment.
                
                Requirements:
                1. Maximum 220 characters (leave 40 chars for URL)
                2. Include: Name, Token Amount, Symbol, and Description
                3. Maintain professional yet engaging tone thats witty
                4. Include relevant hashtags
                5. Reference tool execution results if applicable
                6. Avoid financial advice
                7. Use appropriate mentions
                8. REQUIRED: Include 2-3 relevant emojis to make the response engaging and friendly
                9. IMPORTANT: Your response MUST be 220 characters or less to leave room for the URL
                10. DO NOT include the URL in your response - it will be automatically appended

                Note: The URL https://aibtc.dev/ will be automatically added to the end of your tweet.
                Ensure your response is no more than 220 characters to leave room for this.
            """
            ),
            expected_output=dedent(
                """
                A well-crafted tweet response with:
                - Main message (≤220 chars, URL will be added automatically)
                - Appropriate tone
                - Relevant hashtags
                - Necessary mentions
                - Don't Congrats to @aibtcdevagent in the tweet
                - Response must leave exactly 40 characters for the URL
                
                The URL https://aibtc.dev/ will be added automatically after your response.
                DO NOT include the URL in your response.
            """
            ),
            agent=self.response_agent,
            output_pydantic=TweetResponseOutput,
        )

        logger.info("Executing response generation task")
        result = response_task.execute_sync()
        logger.info(f"Response generation result: {result.pydantic if result else 'None'}")
        
        # Ensure URL is added to the response
        if result and result.pydantic and result.pydantic.response:
            result.pydantic.response = f"{result.pydantic.response.strip()} https://aibtc.dev/"
        
        self.state.response = result.pydantic if result else None
        return "complete"

    @listen("skip")
    def handle_skip(self):
        logger.info(f"Skipping tweet. Type: {self.state.tweet_type}")
        if not self.state.is_worthy:
            feedback_task = Task(
                name="feedback_generation",
                description=dedent(
                    f"""
                    Your name is {self.account_name} on twitter.
                    
                    Generate constructive feedback for an unworthy tweet:
                    
                    
                    Tweet:
                    {self.state.tweet_text}

                    "You are receiving this because your DAO creation request was missing key information, such as a description, mission, name, and symbol. While providing a name is a great start, we’ll need a bit more detail to proceed."
                    
                    Requirements:
                    1. Be constructive and encouraging
                    2. Explain what information would make the proposal better
                    3. Maximum 200 characters
                    4. Maintain professional yet friendly tone
                    5. Include relevant hashtags
                    6. Use appropriate mentions

                    7. Gently Incomplete:
                        "Appreciate it! What does this DAO aim to accomplish?"

                    8. Need More Details:
                        "Looking good! Add goals, token use, and target community."

                    9. Mission Missing:
                        "Great start! Let’s clarify the purpose before deployment."

                    10. Add Some Flavor:
                        "Love it! What’s the unique twist to grab attention?"

                    11. One-Liner to Next Level:
                        "Almost there! Add more vision or strategy for impact."
                    
                    """
                ),
                expected_output=dedent(
                    """
                    A constructive feedback response with:
                    - Main message (≤200 chars)
                    - Appropriate tone
                    - Relevant hashtags
                    - Necessary mentions
                    """
                ),
                agent=self.response_agent,
                output_pydantic=TweetResponseOutput,
            )
            
            logger.info("Generating feedback for unworthy tweet")
            result = feedback_task.execute_sync()
            if result and result.pydantic:
                self.state.response = result.pydantic
                self.state.has_feedback = True
                logger.info("Feedback generated successfully")
            else:
                logger.warning("Failed to generate feedback")
        
        return "complete"

    async def kickoff_async(self) -> Dict[str, Any]:
        logger.info("Starting async kickoff")
        await super().kickoff_async()
        result = {
            "tool_result": self.state.tool_result,
            "response": self.state.response.dict() if self.state.response else None,
            "has_feedback": self.state.has_feedback
        }
        logger.info(f"Kickoff result: {result}")
        return result

    async def execute_twitter_stream(
        self, twitter_service: Any, history: List, input_str: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute a chat stream with history using conditional tasks.

        Args:
            twitter_service: Twitter service instance
            history: List of previous thread messages
            input_str: Current tweet text to process

        Yields:
            Dict containing step information or final results
        """
        try:
            logger.info(f"Starting tweet stream processing for input: {input_str[:50]}...")
            filtered_content = extract_filtered_content(history)
            logger.info(f"Extracted filtered content length: {len(filtered_content)}")

            self.state.tweet_text = input_str
            self.state.filtered_content = filtered_content

            logger.info("Starting flow execution")
            result = await self.kickoff_async()
            logger.info(f"Flow execution completed. Result: {result}")

            if not self.state.is_worthy and not self.state.has_feedback:
                logger.info("Tweet not worthy of processing and no feedback generated")
                yield {
                    "type": "result",
                    "reason": "Tweet not worthy of processing",
                    "content": None,
                }
                return

            if self.state.tweet_type == TweetType.TOOL_REQUEST and self.state.tool_request:
                logger.info(
                    f"Yielding tool execution step for tool: {self.state.tool_request.tool_name}"
                )
                yield {
                    "type": "step",
                    "role": "assistant",
                    "content": f"Executing tool: {self.state.tool_request.tool_name}",
                    "thought": "Tool execution required",
                    "tool": self.state.tool_request.tool_name,
                    "tool_input": self.state.tool_request.parameters,
                    "result": self.state.tool_result,
                }

            logger.info(f"Final state - Response: {self.state.response}")
            if self.state.response and self.state.response.response:
                logger.info("Yielding final response")
                yield {"type": "result", "content": self.state.response.response}
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

async def execute_twitter_stream(
    twitter_service: Any, history: List, input_str: str
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Execute a chat stream with history using conditional tasks.

    Args:
        twitter_service: Twitter service instance
        history: List of previous thread messages
        input_str: Current tweet text to process

    Yields:
        Dict containing step information or final results
    """
    try:
        logger.info(f"Starting tweet stream processing for input: {input_str[:50]}...")
        filtered_content = extract_filtered_content(history)
        logger.info(f"Extracted filtered content length: {len(filtered_content)}")

        flow = TweetProcessingFlow(twitter_service)
        flow.state.tweet_text = input_str
        flow.state.filtered_content = filtered_content

        logger.info("Starting flow execution")
        result = await flow.kickoff_async()
        logger.info(f"Flow execution completed. Result: {result}")

        if not flow.state.is_worthy and not flow.state.has_feedback:
            logger.info("Tweet not worthy of processing and no feedback generated")
            yield {
                "type": "result",
                "reason": "Tweet not worthy of processing",
                "content": None,
            }
            return

        if flow.state.tweet_type == TweetType.TOOL_REQUEST and flow.state.tool_request:
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
