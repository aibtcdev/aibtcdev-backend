"""Proposal evaluation workflow."""

import binascii
from typing import Dict, List, Optional, TypedDict

from langchain.prompts import PromptTemplate
from langgraph.graph import END, Graph, StateGraph
from pydantic import BaseModel, Field

from backend.factory import backend
from backend.models import (
    UUID,
    ExtensionFilter,
    Profile,
    PromptFilter,
    ProposalType,
    QueueMessageFilter,
    QueueMessageType,
)
from lib.hiro import HiroApi
from lib.logger import configure_logger
from services.workflows.base import (
    BaseWorkflow,
)
from services.workflows.chat import ChatService
from services.workflows.vector_mixin import VectorRetrievalCapability
from services.workflows.web_search_mixin import WebSearchCapability
from tools.dao_ext_action_proposals import VoteOnActionProposalTool
from tools.tools_factory import filter_tools_by_names, initialize_tools

logger = configure_logger(__name__)


class ProposalEvaluationOutput(BaseModel):
    """Output model for proposal evaluation."""

    approve: bool = Field(
        description="Whether to approve (true) or reject (false) the proposal"
    )
    confidence_score: float = Field(
        description="The confidence score for the evaluation (0.0-1.0)"
    )
    reasoning: str = Field(description="The reasoning behind the evaluation decision")


class EvaluationState(TypedDict):
    """State for the proposal evaluation flow."""

    action_proposals_contract: str
    action_proposals_voting_extension: str
    proposal_id: int
    proposal_data: Dict
    dao_info: Optional[Dict]
    approve: bool
    confidence_score: float
    reasoning: str
    vote_result: Optional[Dict]
    wallet_id: Optional[UUID]
    confidence_threshold: float
    auto_vote: bool
    formatted_prompt: str
    agent_prompts: List[Dict]
    vector_results: Optional[List[Dict]]
    recent_tweets: Optional[List[Dict]]
    web_search_results: Optional[List[Dict]]  # Add field for web search results
    treasury_balance: Optional[float]
    token_usage: Optional[Dict]  # Add field for token usage tracking
    model_info: Optional[Dict]  # Add field for model information


class ProposalEvaluationWorkflow(
    BaseWorkflow[EvaluationState], VectorRetrievalCapability, WebSearchCapability
):
    """Workflow for evaluating DAO proposals and voting automatically."""

    def __init__(
        self,
        collection_names: Optional[List[str]] = None,
        model_name: str = "gpt-4.1",
        temperature: Optional[float] = 0.1,
        **kwargs,
    ):
        """Initialize the workflow.

        Args:
            collection_names: Optional list of collection names to search
            model_name: The model to use for evaluation
            temperature: Optional temperature setting for the model
            **kwargs: Additional arguments passed to parent
        """
        super().__init__(model_name=model_name, temperature=temperature, **kwargs)
        self.collection_names = collection_names or [
            "knowledge_collection",
            "dao_collection",
        ]
        self.required_fields = ["proposal_id", "proposal_data"]
        self.logger.debug(
            f"Initialized workflow: collections={self.collection_names} | model={model_name} | temperature={temperature}"
        )

    def _create_prompt(self) -> PromptTemplate:
        """Create the evaluation prompt template."""
        return PromptTemplate(
            input_variables=[
                "proposal_data",
                "dao_info",
                "treasury_balance",
                "contract_source",
                "agent_prompts",
                "vector_context",
                "recent_tweets",
                "web_search_results",
            ],
            template="""
            You are a DAO proposal evaluator. Your task is to analyze the proposal and determine whether to vote FOR or AGAINST it.

            # 1. AGENT-SPECIFIC INSTRUCTIONS (HIGHEST PRIORITY)
            {agent_prompts}

            If no agent-specific instructions are provided, explicitly state: "No agent-specific instructions provided."
            You MUST explain how each instruction influenced your decision.

            # 2. PROPOSAL INFORMATION
            {proposal_data}

            # 3. DAO CONTEXT
            {dao_info}

            # 4. TREASURY INFORMATION
            {treasury_balance}

            # 5. AIBTC CHARTER
            Core Values: Curiosity, Truth Maximizing, Humanity's Best Interests, Transparency, Resilience, Collaboration
            Mission: Elevate human potential through Autonomous Intelligence on Bitcoin
            Guardrails: Decentralized Governance, Smart Contract accountability

            # 6. CONTRACT SOURCE (for core proposals)
            {contract_source}

            # 7. EVALUATION CRITERIA
            For Core Proposals:
            - Security implications
            - Mission alignment
            - Vulnerability assessment
            - Impact analysis

            For Action Proposals:
            - Parameter validation
            - Resource implications
            - Security considerations
            - Alignment with DAO goals

            # 8. CONFIDENCE SCORING RUBRIC
            You MUST choose one of these confidence bands:
            - 0.0-0.2: Extremely low confidence (major red flags or insufficient information)
            - 0.3-0.4: Low confidence (significant concerns or unclear implications)
            - 0.5-0.6: Moderate confidence (some concerns but manageable)
            - 0.7-0.8: High confidence (minor concerns if any)
            - 0.9-1.0: Very high confidence (clear positive alignment)

            # 9. QUALITY STANDARDS
            Your evaluation must uphold clarity, reasoning, and respect for the DAO's voice:
            • Be clear and specific — avoid vagueness or filler
            • Use a consistent tone, but reflect the DAO's personality if known
            • Avoid casual throwaway phrases, sarcasm, or hype
            • Don't hedge — take a position and justify it clearly
            • Make every point logically sound and backed by facts or context
            • Cite relevant parts of the proposal, DAO mission, or prior actions
            • Use terms accurately — don't fake precision
            • Keep structure clean and easy to follow

            # 10. VECTOR CONTEXT
            {vector_context}

            # 11. RECENT DAO TWEETS
            {recent_tweets}

            # 12. WEB SEARCH RESULTS
            {web_search_results}

            # OUTPUT FORMAT
            Provide your evaluation in this exact JSON format:
            {{
                "approve": boolean,  // true for FOR, false for AGAINST
                "confidence_score": float,  // MUST be from the confidence bands above
                "reasoning": string  // Brief, professional explanation addressing:
                                   // 1. How agent instructions were applied
                                   // 2. How DAO context influenced decision
                                   // 3. How AIBTC Charter alignment was considered
                                   // 4. Key factors in confidence score selection
                                   // Must be clear, precise, and well-structured
            }}
            """,
        )

    def _create_graph(self) -> Graph:
        """Create the evaluation graph."""
        prompt = self._create_prompt()

        # Create evaluation node
        async def evaluate_proposal(state: EvaluationState) -> EvaluationState:
            """Evaluate the proposal and determine how to vote."""
            try:
                # Get proposal data from state
                proposal_data = state["proposal_data"]
                dao_id = state.get("dao_info", {}).get("id")

                # Perform web search for relevant context
                try:
                    # Create search query from proposal data
                    web_search_query = f"DAO proposal {proposal_data.get('type', 'unknown')} - {proposal_data.get('parameters', '')}"

                    # Use web search capability
                    web_search_results = await self.search_web(
                        query=web_search_query,
                        search_context_size="medium",  # Use medium context size for balanced results
                    )

                    # Update state with web search results
                    state["web_search_results"] = web_search_results
                    self.logger.debug(
                        f"Web search query: {web_search_query} | Results count: {len(web_search_results)}"
                    )
                    self.logger.debug(
                        f"Retrieved {len(web_search_results)} web search results"
                    )
                except Exception as e:
                    self.logger.error(
                        f"Failed to perform web search: {str(e)}", exc_info=True
                    )
                    state["web_search_results"] = []

                # Fetch recent tweets from queue if dao_id exists
                recent_tweets = []
                if dao_id:
                    try:
                        # Add debug logging for dao_id
                        self.logger.debug(f"Fetching tweets for DAO ID: {dao_id}")

                        queue_messages = backend.list_queue_messages(
                            QueueMessageFilter(
                                type=QueueMessageType.TWEET,
                                dao_id=dao_id,
                                is_processed=True,
                            )
                        )
                        # Log the number of messages found
                        self.logger.debug(f"Found {len(queue_messages)} queue messages")

                        # Sort by created_at and take last 5
                        sorted_messages = sorted(
                            queue_messages, key=lambda x: x.created_at, reverse=True
                        )[:5]
                        self.logger.debug(
                            f"After sorting, have {len(sorted_messages)} messages"
                        )

                        recent_tweets = [
                            {
                                "created_at": msg.created_at,
                                "message": (
                                    msg.message.get("message", "No text available")
                                    if isinstance(msg.message, dict)
                                    else msg.message
                                ),
                                "tweet_id": msg.tweet_id,
                            }
                            for msg in sorted_messages
                        ]
                        self.logger.debug(f"Retrieved tweets: {recent_tweets}")
                        self.logger.debug(
                            f"Found {len(recent_tweets)} recent tweets for DAO {dao_id}"
                        )
                    except Exception as e:
                        self.logger.error(
                            f"Failed to fetch recent tweets: {str(e)}", exc_info=True
                        )
                        recent_tweets = []

                # Update state with recent tweets
                state["recent_tweets"] = recent_tweets

                # If this is a core proposal, fetch the contract source
                contract_source = ""
                if proposal_data.get("type") == "core" and proposal_data.get(
                    "proposal_contract"
                ):
                    # Split contract address into parts
                    parts = proposal_data["proposal_contract"].split(".")
                    if len(parts) >= 2:
                        contract_address = parts[0]
                        contract_name = parts[1]

                        # Use HiroApi to fetch contract source
                        try:
                            api = HiroApi()
                            result = api.get_contract_source(
                                contract_address, contract_name
                            )
                            if "source" in result:
                                contract_source = result["source"]
                                self.logger.debug(
                                    f"Retrieved contract source for {contract_address}.{contract_name}"
                                )
                            else:
                                self.logger.warning(
                                    f"Contract source not found in API response: {result}"
                                )
                        except Exception as e:
                            self.logger.error(
                                f"Failed to fetch contract source: {str(e)}",
                                exc_info=True,
                            )
                    else:
                        self.logger.warning(
                            f"Invalid contract address format: {proposal_data['proposal_contract']}"
                        )

                # Retrieve relevant context from vector store
                try:
                    # Create search query from proposal data
                    search_query = f"Proposal type: {proposal_data.get('type')} - {proposal_data.get('parameters', '')}"

                    # Use vector retrieval capability
                    vector_results = await self.retrieve_from_vector_store(
                        query=search_query, limit=5  # Get top 5 most relevant documents
                    )

                    # Update state with vector results
                    state["vector_results"] = vector_results
                    self.logger.debug(
                        f"Searching vector store with query: {search_query} | Collection count: {len(self.collection_names)}"
                    )
                    self.logger.debug(f"Vector search results: {vector_results}")
                    self.logger.debug(
                        f"Retrieved {len(vector_results)} relevant documents from vector store"
                    )

                    # Format vector context for prompt
                    vector_context = "\n\n".join(
                        [
                            f"Related Context {i+1}:\n{doc.page_content}"
                            for i, doc in enumerate(vector_results)
                        ]
                    )
                except Exception as e:
                    self.logger.error(
                        f"Failed to retrieve from vector store: {str(e)}", exc_info=True
                    )
                    vector_context = (
                        "No additional context available from vector store."
                    )

                # Format prompt with state
                self.logger.debug("Preparing evaluation prompt...")

                # Format agent prompts as a string
                agent_prompts_str = "No agent-specific instructions available."
                if state.get("agent_prompts"):
                    self.logger.debug(f"Raw agent prompts: {state['agent_prompts']}")
                    if (
                        isinstance(state["agent_prompts"], list)
                        and state["agent_prompts"]
                    ):
                        # Just use the prompt text directly since that's what we're storing
                        agent_prompts_str = "\n\n".join(state["agent_prompts"])
                        self.logger.debug(
                            f"Formatted agent prompts: {agent_prompts_str}"
                        )
                    else:
                        self.logger.warning(
                            f"Invalid agent prompts format: {type(state['agent_prompts'])}"
                        )
                else:
                    self.logger.debug("No agent prompts found in state")

                # Format web search results for prompt
                web_search_content = "No relevant web search results found."
                if state.get("web_search_results"):
                    web_search_content = "\n\n".join(
                        [
                            f"Web Result {i+1}:\n{result['page_content']}\nSource: {result['metadata']['source_urls'][0]['url'] if result['metadata']['source_urls'] else 'Unknown'}"
                            for i, result in enumerate(state["web_search_results"])
                        ]
                    )

                # Update formatted prompt with web search results
                formatted_prompt = self._create_prompt().format(
                    proposal_data=proposal_data,
                    dao_info=state.get(
                        "dao_info", "No additional DAO information available."
                    ),
                    treasury_balance=state.get("treasury_balance"),
                    contract_source=contract_source,
                    agent_prompts=agent_prompts_str,
                    vector_context=vector_context,
                    recent_tweets=(
                        "\n".join(
                            [
                                f"Tweet {i+1} ({tweet['created_at']}): {tweet['message']}"
                                for i, tweet in enumerate(recent_tweets)
                            ]
                        )
                        if recent_tweets
                        else "No recent tweets available."
                    ),
                    web_search_results=web_search_content,
                )

                # Get evaluation from LLM
                self.logger.debug("Starting LLM evaluation...")
                structured_output = self.llm.with_structured_output(
                    ProposalEvaluationOutput,
                    include_raw=True,  # Include raw response to get token usage
                )

                # Invoke LLM with formatted prompt
                result = structured_output.invoke(formatted_prompt)

                # Extract the parsed result and token usage from raw response
                self.logger.debug(
                    f"Raw LLM result structure: {type(result).__name__} | Has parsed: {'parsed' in result if isinstance(result, dict) else False}"
                )
                parsed_result = result["parsed"] if isinstance(result, dict) else result
                model_info = {"name": self.model_name, "temperature": self.temperature}

                if isinstance(result, dict) and "raw" in result:
                    raw_msg = result["raw"]
                    # Extract token usage
                    if hasattr(raw_msg, "usage_metadata"):
                        token_usage = raw_msg.usage_metadata
                        self.logger.debug(
                            f"Token usage details: input={token_usage.get('input_tokens', 0)} | output={token_usage.get('output_tokens', 0)} | total={token_usage.get('total_tokens', 0)}"
                        )
                    else:
                        self.logger.warning("No usage_metadata found in raw response")
                        token_usage = {
                            "input_tokens": 0,
                            "output_tokens": 0,
                            "total_tokens": 0,
                        }
                else:
                    self.logger.warning("No raw response available")
                    token_usage = {
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "total_tokens": 0,
                    }

                self.logger.debug(f"Parsed evaluation result: {parsed_result}")

                # Update state
                state["formatted_prompt"] = formatted_prompt
                state["approve"] = parsed_result.approve
                state["confidence_score"] = parsed_result.confidence_score
                state["reasoning"] = parsed_result.reasoning
                state["token_usage"] = token_usage
                state["model_info"] = model_info

                # Calculate token costs
                token_costs = calculate_token_cost(token_usage, model_info["name"])

                # Log final evaluation summary
                self.logger.debug(
                    f"Evaluation complete: Decision={'APPROVE' if parsed_result.approve else 'REJECT'} | Confidence={parsed_result.confidence_score:.2f} | Model={model_info['name']} (temp={model_info['temperature']}) | Tokens={token_usage} | Cost=${token_costs['total_cost']:.4f}"
                )
                self.logger.debug(f"Full reasoning: {parsed_result.reasoning}")

                return state
            except Exception as e:
                self.logger.error(
                    f"Error in evaluate_proposal: {str(e)}", exc_info=True
                )
                state["approve"] = False
                state["confidence_score"] = 0.0
                state["reasoning"] = f"Error during evaluation: {str(e)}"
                return state

        # Create decision node
        async def should_vote(state: EvaluationState) -> str:
            """Decide whether to vote based on confidence threshold."""
            try:
                self.logger.debug(
                    f"Deciding vote: auto_vote={state['auto_vote']} | confidence={state['confidence_score']} | threshold={state['confidence_threshold']}"
                )

                if not state["auto_vote"]:
                    self.logger.debug("Auto-vote is disabled, skipping vote")
                    return "skip_vote"

                if state["confidence_score"] >= state["confidence_threshold"]:
                    self.logger.debug(
                        f"Confidence score {state['confidence_score']} meets threshold {state['confidence_threshold']}, proceeding to vote"
                    )
                    return "vote"
                else:
                    self.logger.debug(
                        f"Confidence score {state['confidence_score']} below threshold {state['confidence_threshold']}, skipping vote"
                    )
                    return "skip_vote"
            except Exception as e:
                self.logger.error(f"Error in should_vote: {str(e)}", exc_info=True)
                return "skip_vote"

        # Create voting node using VectorReact workflow
        async def vote_on_proposal(state: EvaluationState) -> EvaluationState:
            """Vote on the proposal using VectorReact workflow."""
            try:
                self.logger.debug(
                    f"Setting up VectorReact workflow: proposal_id={state['proposal_id']} | vote={state['approve']}"
                )

                # Set up the voting tool
                vote_tool = VoteOnActionProposalTool(wallet_id=state["wallet_id"])
                tools_map = {"dao_action_vote_on_proposal": vote_tool}

                # Create a user input message that instructs the LLM what to do
                vote_instruction = f"I need you to vote on a DAO proposal with ID {state['proposal_id']} in the contract {state['action_proposals_contract']}. Please vote {'FOR' if state['approve'] else 'AGAINST'} the proposal. Use the dao_action_vote_on_proposal tool to submit the vote."

                # Create VectorLangGraph service with collections
                service = ChatService(
                    collection_names=self.collection_names,
                )

                # History with system message only
                history = [
                    {
                        "role": "system",
                        "content": "You are a helpful assistant tasked with voting on DAO proposals. Follow the instructions precisely.",
                    }
                ]

                self.logger.debug("Executing VectorReact workflow for voting...")

                # Collect response chunks
                response_chunks = []
                vote_result = None

                # Execute the VectorReact workflow
                async for chunk in service.execute_stream(
                    history=history,
                    input_str=vote_instruction,
                    tools_map=tools_map,
                ):
                    response_chunks.append(chunk)
                    self.logger.debug(f"VectorReact chunk: {chunk}")

                    # Extract tool results
                    if (
                        chunk.get("type") == "tool"
                        and chunk.get("tool") == "dao_action_vote_on_proposal"
                    ):
                        if "output" in chunk:
                            vote_result = chunk.get("output")
                            self.logger.debug(f"Vote result: {vote_result}")

                # Update state with vote result and vector results
                state["vote_result"] = {
                    "success": vote_result is not None,
                    "output": vote_result,
                }
                state["vector_results"] = [
                    chunk.get("vector_results", [])
                    for chunk in response_chunks
                    if chunk.get("vector_results")
                ]

                return state
            except Exception as e:
                self.logger.error(f"Error in vote_on_proposal: {str(e)}", exc_info=True)
                state["vote_result"] = {
                    "success": False,
                    "error": f"Error during voting: {str(e)}",
                }
                return state

        # Create skip voting node
        async def skip_voting(state: EvaluationState) -> EvaluationState:
            """Skip voting and just return the evaluation."""
            try:
                self.logger.debug("Vote skipped: reason=threshold_or_setting")
                state["vote_result"] = {
                    "success": True,
                    "message": "Voting skipped due to confidence threshold or auto_vote setting",
                    "data": None,
                }
                return state
            except Exception as e:
                self.logger.error(f"Error in skip_voting: {str(e)}", exc_info=True)
                state["vote_result"] = {
                    "success": True,
                    "message": f"Voting skipped (with error: {str(e)})",
                    "data": None,
                }
                return state

        # Create the graph
        workflow = StateGraph(EvaluationState)

        # Add nodes
        workflow.add_node("evaluate", evaluate_proposal)
        workflow.add_node("vote", vote_on_proposal)
        workflow.add_node("skip_vote", skip_voting)

        # Set up the conditional branching
        workflow.set_entry_point("evaluate")
        workflow.add_conditional_edges(
            "evaluate",
            should_vote,
            {
                "vote": "vote",
                "skip_vote": "skip_vote",
            },
        )
        workflow.add_edge("vote", END)
        workflow.add_edge("skip_vote", END)

        return workflow.compile()

    def _validate_state(self, state: EvaluationState) -> bool:
        """Validate the workflow state."""
        required_fields = ["proposal_id", "proposal_data"]

        # Log the state for debugging
        self.logger.debug(
            f"Validating state: proposal_id={state.get('proposal_id')} | proposal_type={state.get('proposal_data', {}).get('type', 'unknown')}"
        )

        # Check all fields and log problems
        for field in required_fields:
            if field not in state:
                self.logger.error(f"Missing required field: {field}")
                return False
            elif not state[field]:
                self.logger.error(f"Empty required field: {field}")
                return False

        # Get proposal type
        proposal_type = state["proposal_data"].get("type", ProposalType.ACTION)

        # Validate based on proposal type
        if proposal_type == ProposalType.ACTION:
            # Action proposals require action_proposals_contract and parameters
            if not state.get("action_proposals_contract"):
                self.logger.error(
                    "Missing action_proposals_contract for action proposal"
                )
                return False
            if not state["proposal_data"].get("parameters"):
                self.logger.error("No parameters field in action proposal data")
                return False
        elif proposal_type == ProposalType.CORE:
            # Core proposals require proposal_contract
            if not state["proposal_data"].get("proposal_contract"):
                self.logger.error("Missing proposal_contract for core proposal")
                return False
        else:
            self.logger.error(f"Invalid proposal type: {proposal_type}")
            return False

        self.logger.debug("State validation successful")
        return True


def get_proposal_evaluation_tools(
    profile: Optional[Profile] = None, agent_id: Optional[UUID] = None
):
    """Get the tools needed for proposal evaluation.

    Args:
        profile: Optional user profile
        agent_id: Optional agent ID

    Returns:
        Dictionary of filtered tools for proposal evaluation
    """
    # Initialize all tools
    all_tools = initialize_tools(profile=profile, agent_id=agent_id)
    logger.debug(f"Available tools: {', '.join(all_tools.keys())}")

    # Filter to only include the tools we need
    required_tools = [
        "dao_action_get_proposal",
        "dao_action_vote_on_proposal",
        "dao_action_get_voting_power",
        "dao_action_get_voting_configuration",
        "database_get_dao_get_by_name",  # Try old name
        "dao_search",  # Try new name
    ]

    filtered_tools = filter_tools_by_names(required_tools, all_tools)
    logger.debug(f"Using tools: {', '.join(filtered_tools.keys())}")

    return filtered_tools


def decode_hex_parameters(hex_string: Optional[str]) -> Optional[str]:
    """Decodes a hexadecimal-encoded string if valid."""
    if not hex_string:
        return None
    if hex_string.startswith("0x"):
        hex_string = hex_string[2:]  # Remove "0x" prefix
    try:
        decoded_bytes = binascii.unhexlify(hex_string)
        decoded_string = decoded_bytes.decode(
            "utf-8", errors="ignore"
        )  # Decode as UTF-8
        logger.debug(f"Successfully decoded hex string: {hex_string[:20]}...")
        return decoded_string
    except (binascii.Error, UnicodeDecodeError) as e:
        logger.warning(f"Failed to decode hex string: {str(e)}")
        return None  # Return None if decoding fails


def calculate_token_cost(
    token_usage: Dict[str, int], model_name: str
) -> Dict[str, float]:
    """Calculate the cost of token usage based on current pricing.

    Args:
        token_usage: Dictionary containing input_tokens and output_tokens
        model_name: Name of the model used

    Returns:
        Dictionary containing cost breakdown and total cost
    """
    # Current pricing per million tokens (as of August 2024)
    MODEL_PRICES = {
        "gpt-4o": {
            "input": 2.50,  # $2.50 per million input tokens
            "output": 10.00,  # $10.00 per million output tokens
        },
        "gpt-4.1": {
            "input": 2.00,  # $2.00 per million input tokens
            "output": 8.00,  # $8.00 per million output tokens
        },
        "gpt-4.1-mini": {
            "input": 0.40,  # $0.40 per million input tokens
            "output": 1.60,  # $1.60 per million output tokens
        },
        "gpt-4.1-nano": {
            "input": 0.10,  # $0.10 per million input tokens
            "output": 0.40,  # $0.40 per million output tokens
        },
        # Default to gpt-4.1 pricing if model not found
        "default": {
            "input": 2.00,
            "output": 8.00,
        },
    }

    # Get pricing for the model, default to gpt-4.1 pricing if not found
    model_prices = MODEL_PRICES.get(model_name.lower(), MODEL_PRICES["default"])

    # Extract token counts, ensuring we get integers and handle None values
    try:
        input_tokens = int(token_usage.get("input_tokens", 0))
        output_tokens = int(token_usage.get("output_tokens", 0))
    except (TypeError, ValueError) as e:
        logger.error(f"Error converting token counts to integers: {str(e)}")
        input_tokens = 0
        output_tokens = 0

    # Calculate costs with more precision
    input_cost = (input_tokens / 1_000_000.0) * model_prices["input"]
    output_cost = (output_tokens / 1_000_000.0) * model_prices["output"]
    total_cost = input_cost + output_cost

    # Create detailed token usage breakdown
    token_details = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "model_name": model_name,
        "input_price_per_million": model_prices["input"],
        "output_price_per_million": model_prices["output"],
    }

    # Add token details if available
    if "input_token_details" in token_usage:
        token_details["input_token_details"] = token_usage["input_token_details"]
    if "output_token_details" in token_usage:
        token_details["output_token_details"] = token_usage["output_token_details"]

    # Debug logging with more detail
    logger.debug(
        f"Cost calculation details: Model={model_name} | Input={input_tokens} tokens * ${model_prices['input']}/1M = ${input_cost:.6f} | Output={output_tokens} tokens * ${model_prices['output']}/1M = ${output_cost:.6f} | Total=${total_cost:.6f} | Token details={token_details}"
    )

    return {
        "input_cost": round(input_cost, 6),
        "output_cost": round(output_cost, 6),
        "total_cost": round(total_cost, 6),
        "currency": "USD",
        "details": token_details,
    }


async def evaluate_and_vote_on_proposal(
    proposal_id: UUID,
    wallet_id: Optional[UUID] = None,
    auto_vote: bool = True,
    confidence_threshold: float = 0.7,
    dao_id: Optional[UUID] = None,
) -> Dict:
    """Evaluate a proposal and automatically vote based on the evaluation.

    Args:
        proposal_id: The ID of the proposal to evaluate and vote on
        wallet_id: Optional wallet ID to use for voting
        auto_vote: Whether to automatically vote based on the evaluation
        confidence_threshold: Minimum confidence score required to auto-vote (0.0-1.0)
        dao_id: Optional DAO ID to explicitly pass to the workflow

    Returns:
        Dictionary containing the evaluation results and voting outcome
    """
    logger.debug(
        f"Starting proposal evaluation: proposal_id={proposal_id} | auto_vote={auto_vote} | confidence_threshold={confidence_threshold}"
    )

    try:
        # Get proposal data directly from the database
        proposal_data = backend.get_proposal(proposal_id)
        if not proposal_data:
            error_msg = f"Proposal {proposal_id} not found in database"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        # Decode parameters if they exist
        decoded_parameters = decode_hex_parameters(proposal_data.parameters)
        if decoded_parameters:
            logger.debug(
                f"Decoded proposal parameters: length={len(decoded_parameters) if decoded_parameters else 0}"
            )

        # Convert proposal data to dictionary and ensure parameters exist
        proposal_dict = {
            "proposal_id": proposal_data.proposal_id,
            "parameters": decoded_parameters
            or proposal_data.parameters,  # Use decoded if available
            "action": proposal_data.action,
            "caller": proposal_data.caller,
            "contract_principal": proposal_data.contract_principal,
            "creator": proposal_data.creator,
            "created_at_block": proposal_data.created_at_block,
            "end_block": proposal_data.end_block,
            "start_block": proposal_data.start_block,
            "liquid_tokens": proposal_data.liquid_tokens,
            "type": proposal_data.type,  # Add proposal type
            "proposal_contract": proposal_data.proposal_contract,  # Add proposal contract for core proposals
        }

        # For action proposals, parameters are required
        if proposal_data.type == ProposalType.ACTION and not proposal_dict.get(
            "parameters"
        ):
            error_msg = "No parameters found in action proposal data"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        # For core proposals, proposal_contract is required
        if proposal_data.type == ProposalType.CORE and not proposal_dict.get(
            "proposal_contract"
        ):
            error_msg = "No proposal contract found in core proposal data"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        # Get DAO info based on provided dao_id or from proposal
        dao_info = None
        if dao_id:
            logger.debug(
                f"Using provided DAO ID: {dao_id} | Found={dao_info is not None}"
            )
            dao_info = backend.get_dao(dao_id)
            if not dao_info:
                logger.warning(
                    f"Provided DAO ID {dao_id} not found, falling back to proposal's DAO ID"
                )

        # If dao_info is still None, try to get it from proposal's dao_id
        if not dao_info and proposal_data.dao_id:
            logger.debug(
                f"Using proposal's DAO ID: {proposal_data.dao_id} | Found={dao_info is not None}"
            )
            dao_info = backend.get_dao(proposal_data.dao_id)

        if not dao_info:
            error_msg = "Could not find DAO information"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        # Get the treasury extension for the DAO
        treasury_extension = None
        try:
            treasury_extensions = backend.list_extensions(
                ExtensionFilter(dao_id=dao_info.id, type="EXTENSIONS_TREASURY")
            )
            if treasury_extensions:
                treasury_extension = treasury_extensions[0]
                logger.debug(
                    f"Found treasury extension: contract_principal={treasury_extension.contract_principal}"
                )

                # Get treasury balance from Hiro API
                hiro_api = HiroApi()
                treasury_balance = hiro_api.get_address_balance(
                    treasury_extension.contract_principal
                )
                logger.debug(f"Treasury balance retrieved: balance={treasury_balance}")
            else:
                logger.warning(f"No treasury extension found for DAO {dao_info.id}")
                treasury_balance = None
        except Exception as e:
            logger.error(f"Failed to get treasury balance: {str(e)}", exc_info=True)
            treasury_balance = None

        logger.debug(
            f"Processing proposal for DAO: {dao_info.name} (ID: {dao_info.id})"
        )

        # Get the wallet and agent information if available
        agent_id = None
        if wallet_id:
            wallet = backend.get_wallet(wallet_id)
            if wallet and wallet.agent_id:
                agent_id = wallet.agent_id
                logger.debug(f"Using agent ID {agent_id} for wallet {wallet_id}")

        # Get agent prompts
        agent_prompts = []
        model_name = "gpt-4.1"  # Default model
        temperature = 0.1  # Default temperature
        try:
            logger.debug(
                f"Fetching prompts for agent_id={agent_id}, dao_id={proposal_data.dao_id}"
            )
            prompts = backend.list_prompts(
                PromptFilter(
                    agent_id=agent_id,
                    dao_id=proposal_data.dao_id,
                    is_active=True,
                )
            )
            logger.debug(f"Retrieved prompts: {prompts}")

            # Store the full Prompt objects and get model settings from first prompt
            agent_prompts = prompts
            if agent_prompts:
                first_prompt = agent_prompts[0]
                model_name = first_prompt.model or model_name
                temperature = (
                    first_prompt.temperature
                    if first_prompt.temperature is not None
                    else temperature
                )
                logger.debug(
                    f"Using model configuration: {model_name} (temperature={temperature})"
                )
            else:
                logger.warning(
                    f"No active prompts found for agent_id={agent_id}, dao_id={proposal_data.dao_id}"
                )
        except Exception as e:
            logger.error(f"Failed to get agent prompts: {str(e)}", exc_info=True)

        # Initialize state
        state = {
            "action_proposals_contract": proposal_dict["contract_principal"],
            "action_proposals_voting_extension": proposal_dict["action"],
            "proposal_id": proposal_dict["proposal_id"],
            "proposal_data": proposal_dict,
            "dao_info": dao_info.model_dump() if dao_info else {},
            "treasury_balance": treasury_balance,
            "agent_prompts": (
                [p.prompt_text for p in agent_prompts] if agent_prompts else []
            ),
            "approve": False,
            "confidence_score": 0.0,
            "reasoning": "",
            "vote_result": None,
            "wallet_id": wallet_id,
            "confidence_threshold": confidence_threshold,
            "auto_vote": auto_vote,
            "vector_results": None,
            "recent_tweets": None,
            "web_search_results": None,
            "token_usage": None,
            "model_info": {
                "name": "unknown",
                "temperature": None,
            },
        }

        logger.debug(
            f"Agent prompts count: {len(state['agent_prompts'] or [])} | Has prompts: {bool(state['agent_prompts'])}"
        )

        # Create and run workflow with model settings from prompt
        workflow = ProposalEvaluationWorkflow(
            model_name=model_name, temperature=temperature
        )
        if not workflow._validate_state(state):
            error_msg = "Invalid workflow state"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
            }

        logger.debug("Starting workflow execution...")
        result = await workflow.execute(state)
        logger.debug("Workflow execution completed")

        # Extract transaction ID from vote result if available
        tx_id = None
        if result.get("vote_result") and result["vote_result"].get("output"):
            # Try to extract tx_id from the output
            output = result["vote_result"]["output"]
            if isinstance(output, str) and "txid:" in output.lower():
                # Extract the transaction ID from the output
                for line in output.split("\n"):
                    if "txid:" in line.lower():
                        parts = line.split(":")
                        if len(parts) > 1:
                            tx_id = parts[1].strip()
                            logger.debug(f"Transaction ID extracted: {tx_id}")
                            break

        # Prepare final result
        final_result = {
            "success": True,
            "evaluation": {
                "approve": result["approve"],
                "confidence_score": result["confidence_score"],
                "reasoning": result["reasoning"],
            },
            "vote_result": result["vote_result"],
            "auto_voted": auto_vote
            and result["confidence_score"] >= confidence_threshold,
            "tx_id": tx_id,
            "formatted_prompt": result["formatted_prompt"],
            "vector_results": result["vector_results"],
            "recent_tweets": result["recent_tweets"],
            "web_search_results": result["web_search_results"],
            "treasury_balance": result.get("treasury_balance"),
            "token_usage": result.get(
                "token_usage",
                {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            ),
            "model_info": result.get(
                "model_info", {"name": "unknown", "temperature": None}
            ),
        }

        # Calculate token costs
        token_costs = calculate_token_cost(
            final_result["token_usage"], final_result["model_info"]["name"]
        )
        final_result["token_costs"] = token_costs

        # For the example token usage shown:
        # Input: 7425 tokens * ($2.50/1M) = $0.0186
        # Output: 312 tokens * ($10.00/1M) = $0.0031
        # Total: $0.0217

        logger.debug(
            f"Proposal evaluation completed: Success={final_result['success']} | Decision={'APPROVE' if final_result['evaluation']['approve'] else 'REJECT'} | Confidence={final_result['evaluation']['confidence_score']:.2f} | Auto-voted={final_result['auto_voted']} | Transaction={tx_id or 'None'} | Model={final_result['model_info']['name']} | Token Usage={final_result['token_usage']} | Cost (USD)=${token_costs['total_cost']:.4f} (Input=${token_costs['input_cost']:.4f} for {token_costs['details']['input_tokens']} tokens, Output=${token_costs['output_cost']:.4f} for {token_costs['details']['output_tokens']} tokens)"
        )
        logger.debug(f"Full evaluation result: {final_result}")

        return final_result
    except Exception as e:
        error_msg = f"Unexpected error in evaluate_and_vote_on_proposal: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "success": False,
            "error": error_msg,
        }


async def evaluate_proposal_only(
    proposal_id: UUID,
    wallet_id: Optional[UUID] = None,
) -> Dict:
    """Evaluate a proposal without voting.

    Args:
        proposal_id: The ID of the proposal to evaluate
        wallet_id: Optional wallet ID to use for retrieving proposal data

    Returns:
        Dictionary containing the evaluation results
    """
    logger.debug(f"Starting proposal-only evaluation: proposal_id={proposal_id}")

    result = await evaluate_and_vote_on_proposal(
        proposal_id=proposal_id,
        wallet_id=wallet_id,
        auto_vote=False,
    )

    # Remove vote-related fields from the response
    logger.debug("Removing vote-related fields from response")
    if "vote_result" in result:
        del result["vote_result"]
    if "auto_voted" in result:
        del result["auto_voted"]
    if "tx_id" in result:
        del result["tx_id"]

    logger.debug("Proposal-only evaluation completed")
    return result
