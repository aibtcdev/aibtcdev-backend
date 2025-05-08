import asyncio
import base64
from typing import Any, Dict, List, Optional, TypedDict

import httpx
from langchain.prompts import PromptTemplate
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
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
from lib.utils import (
    calculate_token_cost,
    extract_image_urls,
)
from services.workflows.base import (
    BaseWorkflow,
)
from services.workflows.chat import ChatService, StreamingCallbackHandler
from services.workflows.planning_mixin import PlanningCapability
from services.workflows.vector_mixin import VectorRetrievalCapability
from services.workflows.web_search_mixin import WebSearchCapability
from tools.dao_ext_action_proposals import VoteOnActionProposalTool
from tools.tools_factory import filter_tools_by_names, initialize_tools

logger = configure_logger(__name__)


class ProposalEvaluationOutput(BaseModel):
    """Output model for proposal evaluation."""

    approve: bool = Field(
        description="Decision: true to approve (vote FOR), false to reject (vote AGAINST)"
    )
    confidence_score: float = Field(
        description="Confidence score for the decision (0.0-1.0)"
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
    web_search_results: Optional[List[Dict]]
    treasury_balance: Optional[float]
    contract_source: Optional[str]
    proposal_images: Optional[List[Dict]]  # Store encoded images for LLM
    # Token usage tracking per step
    web_search_token_usage: Optional[Dict]
    evaluation_token_usage: Optional[Dict]
    # Model info for cost calculation
    evaluation_model_info: Optional[Dict]
    web_search_model_info: Optional[Dict]


class ProposalEvaluationWorkflow(
    BaseWorkflow[EvaluationState],
    VectorRetrievalCapability,
    WebSearchCapability,
    PlanningCapability,
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
        # Initialize planning LLM
        planning_llm = ChatOpenAI(
            model="o4-mini",
            stream_usage=True,
            streaming=True,
        )

        # Create callback handler for planning with queue
        callback_handler = StreamingCallbackHandler(queue=asyncio.Queue())

        # Initialize all parent classes including PlanningCapability
        super().__init__(model_name=model_name, temperature=temperature, **kwargs)
        PlanningCapability.__init__(
            self,
            callback_handler=callback_handler,
            planning_llm=planning_llm,
            persona="You are a DAO proposal evaluation planner, focused on creating structured evaluation plans.",
        )

        self.collection_names = collection_names or [
            "knowledge_collection",
            "proposals",
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
            You are a skeptical and hard-to-convince DAO proposal evaluator. Your primary goal is rigorous analysis. Your task is to analyze the proposal and determine whether to vote FOR or AGAINST it based on verifiable evidence and alignment with DAO principles.

            <instructions>
            <high_priority_instructions importance="critical">
            {agent_prompts}
            </high_priority_instructions>
            <default_instructions>
            If no agent-specific instructions are provided, apply these DEFAULT instructions:
            - Approve ONLY if the proposal provides verifiable evidence (URL, transaction hash, IPFS CID for screenshots/documents) for its claims OR if it's a purely logistical matter (e.g., scheduling reminder).
            - All other proposals lacking verifiable evidence for claims should be REJECTED (vote AGAINST) with LOW confidence (0.3-0.4 band).
            - Reject proposals making promises about future DAO actions or events unless they provide on-chain evidence of a corresponding approved governance decision or multisig transaction proposal.
            - CRITICAL: You MUST evaluate all proposal content (text, images, links) as ONE COHESIVE UNIT. If ANY image or attachment doesn't align with or support the proposal, contains misleading information, or is inappropriate, you MUST reject the entire proposal.
            </default_instructions>
            You MUST explain how each specific instruction (agent-provided or default) influenced your decision, especially if it led to rejection.
            </instructions>

            <evaluation_criteria>
            <core_proposals>
                <security_criteria>
                    <criterion>Verify smart contract security measures</criterion>
                    <criterion>Check for potential vulnerabilities in contract logic</criterion>
                    <criterion>Assess potential attack vectors</criterion>
                    <criterion>Evaluate access control mechanisms</criterion>
                </security_criteria>
                <alignment_criteria>
                    <criterion>Analyze alignment with DAO mission statement</criterion>
                    <criterion>Verify compatibility with existing DAO infrastructure</criterion>
                    <criterion>Check adherence to DAO's established governance principles</criterion>
                </alignment_criteria>
                <impact_criteria>
                    <criterion>Evaluate potential risks vs. rewards</criterion>
                    <criterion>Assess short-term and long-term implications</criterion>
                    <criterion>Consider effects on DAO reputation and stakeholders</criterion>
                </impact_criteria>
            </core_proposals>
            <action_proposals>
                <validation_criteria>
                    <criterion>Validate all proposed parameters against acceptable ranges</criterion>
                    <criterion>Verify parameter compatibility with existing systems</criterion>
                    <criterion>Check for realistic implementation timelines</criterion>
                </validation_criteria>
                <resource_criteria>
                    <criterion>Assess treasury impact and funding requirements</criterion>
                    <criterion>Evaluate operational resource needs</criterion>
                    <criterion>Consider opportunity costs against other initiatives</criterion>
                </resource_criteria>
                <security_criteria>
                    <criterion>Identify potential security implications of the action</criterion>
                    <criterion>Check for unintended system vulnerabilities</criterion>
                </security_criteria>
                <evidence_criteria>
                    <criterion importance="critical">**Evidence Verification:** All claims MUST be backed by verifiable sources (URLs, transaction hashes, IPFS CIDs)</criterion>
                    <criterion importance="critical">**Future Commitments:** Any promises about future actions require on-chain proof of approved governance decisions</criterion>
                    <criterion importance="critical">**Content Cohesion:** All components (text, images, links) must form a cohesive, aligned whole supporting the proposal's intent</criterion>
                </evidence_criteria>
            </action_proposals>
            </evaluation_criteria>

            <proposal_content>
            <proposal_data>
            {proposal_data}
            </proposal_data>
            <proposal_instructions>
            Note: If any images are provided with the proposal, they will be shown after this prompt.
            You should analyze any provided images in the context of the proposal and include your observations
            in your evaluation. Consider aspects such as:
            - Image content and relevance to the proposal
            - Any visual evidence supporting or contradicting the proposal
            - Quality and authenticity of the images
            - Potential security or privacy concerns in the images

            IMPORTANT: Images and text must form a cohesive whole. If any image:
            - Doesn't clearly support or relate to the proposal text
            - Contains misleading or contradictory information
            - Is of poor quality making verification impossible
            - Contains inappropriate content
            - Appears manipulated or false
            Then you MUST reject the entire proposal, regardless of the quality of the text portion.
            </proposal_instructions>
            </proposal_content>
            <additional_context>
            <vector_context>
            {vector_context}
            </vector_context>
            <recent_tweets>
            {recent_tweets}
            </recent_tweets>
            <web_search_results>
            {web_search_results}
            </web_search_results>
            </additional_context>

            <dao_context>
            <dao_info>
            {dao_info}
            </dao_info>
            <treasury_balance>
            {treasury_balance}
            </treasury_balance>
            <aibtc_charter>
            Core Values: Curiosity, Truth Maximizing, Humanity's Best Interests, Transparency, Resilience, Collaboration
            Mission: Elevate human potential through Autonomous Intelligence on Bitcoin
            Guardrails: Decentralized Governance, Smart Contract accountability
            </aibtc_charter>
            </dao_context>

            <technical_details>
            <contract_source>
            {contract_source}
            </contract_source>
            </technical_details>

            <confidence_scoring>
            <confidence_bands>
            You MUST choose one of these confidence bands:
            - **0.9-1.0 (Very High Confidence - Strong Approve):** All criteria met excellently. Clear alignment with DAO mission/values, strong verifiable evidence provided for all claims, minimal/no security risks identified, significant positive impact expected, and adheres strictly to all instructions (including future promise verification). All images directly support the proposal with high quality and authenticity.
            - **0.7-0.8 (High Confidence - Approve):** Generally meets criteria well. Good alignment, sufficient verifiable evidence provided, risks identified but deemed manageable/acceptable, likely positive impact. Passes core checks (evidence, future promises). Minor reservations might exist but don't fundamentally undermine the proposal. Images support the proposal appropriately.
            - **0.5-0.6 (Moderate Confidence - Borderline/Weak Approve):** Meets minimum criteria but with notable reservations. Alignment is present but perhaps weak or indirect, evidence meets minimum verification but might be incomplete or raise minor questions, moderate risks identified requiring monitoring, impact is unclear or modest. *Could apply to simple logistical proposals with no major claims.* Any included images are relevant though may not provide strong support.
            - **0.3-0.4 (Low Confidence - Reject):** Fails one or more key criteria. Significant misalignment, **lacks required verifiable evidence** for claims (triggering default rejection), unacceptable risks identified, potential negative impact, or **contains unsubstantiated future promises**. Images may be missing where needed, irrelevant, or only weakly supportive. *This is the default band for rejections due to lack of evidence or unproven future commitments.*
            - **0.0-0.2 (Extremely Low Confidence - Strong Reject):** Fails multiple critical criteria. Clear violation of DAO principles/guardrails, major security flaws identified, evidence is demonstrably false or misleading, significant negative impact is highly likely or certain. Any included images may be misleading, manipulated, inappropriate, or contradictory to the proposal.
            </confidence_bands>
            </confidence_scoring>

            <quality_standards>
            Your evaluation must uphold clarity, reasoning, and respect for the DAO's voice:
            • Be clear and specific — avoid vagueness or filler
            • Use a consistent tone, but reflect the DAO's personality if known
            • Avoid casual throwaway phrases, sarcasm, or hype
            • Don't hedge — take a position and justify it clearly
            • Make every point logically sound and backed by facts or context
            • Cite relevant parts of the proposal, DAO mission, or prior actions
            • Use terms accurately — don't fake precision
            • Keep structure clean and easy to follow
            • Include analysis of any provided images and their implications
            • Specifically address image-text cohesion in your analysis
            • If rejecting, CLEARLY state the specific reason(s) based on the instructions or evaluation criteria (e.g., "Rejected due to lack of verifiable source for claim X", "Rejected because future promise lacks on-chain evidence", "Rejected because included image contradicts proposal text").
            </quality_standards>

            <output_format>
            Provide your evaluation in this exact JSON format:
            ```json
            {{
                "approve": boolean,  // true for FOR, false for AGAINST
                "confidence_score": float,  // MUST be from the confidence bands above
                "reasoning": string  // Brief, professional explanation addressing:
                                   // 1. How agent/default instructions were applied (state which).
                                   // 2. Specific reason for rejection if applicable, referencing the unmet criteria or instruction.
                                   // 3. How DAO context influenced decision.
                                   // 4. How AIBTC Charter alignment was considered.
                                   // 5. Key factors in confidence score selection.
                                   // 6. Analysis of any provided images and their cohesion with proposal text.
                                   // Must be clear, precise, and well-structured.
            }}
            ```
            </output_format>
            """,
        )

    def _create_graph(self) -> Graph:
        """Create the evaluation graph."""
        prompt = self._create_prompt()

        async def fetch_context(state: EvaluationState) -> EvaluationState:
            """Fetch context including web search, vector results, tweets, and contract source."""
            try:
                # --- Fetch Core Data --- #
                proposal_id = state["proposal_id"]
                dao_id = state.get("dao_id")
                agent_id = state.get("agent_id")

                # Get proposal data
                proposal_data = backend.get_proposal(proposal_id)
                if not proposal_data:
                    raise ValueError(f"Proposal {proposal_id} not found")

                image_urls = extract_image_urls(proposal_data.parameters)

                # Process and encode images
                proposal_images = []
                for url in image_urls:
                    try:
                        async with httpx.AsyncClient() as client:
                            response = await client.get(url, timeout=10.0)
                            if response.status_code == 200:
                                image_data = base64.b64encode(response.content).decode(
                                    "utf-8"
                                )
                                # Determine MIME type based on URL extension
                                mime_type = (
                                    "image/jpeg"
                                    if url.lower().endswith((".jpg", ".jpeg"))
                                    else (
                                        "image/png"
                                        if url.lower().endswith(".png")
                                        else (
                                            "image/gif"
                                            if url.lower().endswith(".gif")
                                            else (
                                                "image/webp"
                                                if url.lower().endswith(".webp")
                                                else "image/png"
                                            )
                                        )
                                    )  # default to PNG if unknown
                                )
                                proposal_images.append(
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:{mime_type};base64,{image_data}"
                                        },
                                    }
                                )
                            else:
                                logger.warning(
                                    f"Failed to fetch image: {url} (status {response.status_code})"
                                )
                    except Exception as e:
                        logger.error(
                            f"Error fetching image {url}: {str(e)}", exc_info=True
                        )

                state["proposal_images"] = proposal_images

                # Convert proposal data to dictionary
                proposal_dict = {
                    "proposal_id": proposal_data.proposal_id,
                    "parameters": proposal_data.parameters,
                    "action": proposal_data.action,
                    "caller": proposal_data.caller,
                    "contract_principal": proposal_data.contract_principal,
                    "creator": proposal_data.creator,
                    "created_at_block": proposal_data.created_at_block,
                    "end_block": proposal_data.end_block,
                    "start_block": proposal_data.start_block,
                    "liquid_tokens": proposal_data.liquid_tokens,
                    "type": proposal_data.type,
                    "proposal_contract": proposal_data.proposal_contract,
                }
                state["proposal_data"] = proposal_dict  # Update state with full data

                # Get DAO info (if dao_id wasn't passed explicitly, use proposal's)
                if not dao_id and proposal_data.dao_id:
                    dao_id = proposal_data.dao_id
                    state["dao_id"] = dao_id  # Update state if derived

                dao_info = None
                if dao_id:
                    dao_info = backend.get_dao(dao_id)
                if not dao_info:
                    raise ValueError(f"DAO Information not found for ID: {dao_id}")
                state["dao_info"] = dao_info.model_dump()

                # Get agent prompts
                agent_prompts_text = []
                if agent_id:
                    try:
                        prompts = backend.list_prompts(
                            PromptFilter(
                                agent_id=agent_id,
                                dao_id=dao_id,
                                is_active=True,
                            )
                        )
                        agent_prompts_text = [p.prompt_text for p in prompts]
                    except Exception as e:
                        self.logger.error(
                            f"Failed to get agent prompts: {str(e)}", exc_info=True
                        )
                state["agent_prompts"] = agent_prompts_text

                # Get treasury balance
                treasury_balance = None
                try:
                    treasury_extensions = backend.list_extensions(
                        ExtensionFilter(dao_id=dao_info.id, type="EXTENSIONS_TREASURY")
                    )
                    if treasury_extensions:
                        hiro_api = HiroApi()
                        treasury_balance = hiro_api.get_address_balance(
                            treasury_extensions[0].contract_principal
                        )
                    else:
                        self.logger.warning(
                            f"No treasury extension for DAO {dao_info.id}"
                        )
                except Exception as e:
                    self.logger.error(
                        f"Failed to get treasury balance: {str(e)}", exc_info=True
                    )
                state["treasury_balance"] = treasury_balance
                # --- End Fetch Core Data --- #

                # Use mixin capabilities for web search and vector retrieval
                web_search_query = f"DAO proposal {proposal_dict.get('type', 'unknown')} - {proposal_dict.get('parameters', '')}"

                # Fetch web search results and token usage
                web_search_results, web_search_token_usage = await self.search_web(
                    query=web_search_query,
                    search_context_size="medium",
                )
                state["web_search_results"] = web_search_results
                state["web_search_token_usage"] = web_search_token_usage
                # Store web search model info (assuming gpt-4.1 as used in mixin)
                state["web_search_model_info"] = {
                    "name": "gpt-4.1",
                    "temperature": None,
                }

                vector_search_query = f"Proposal type: {proposal_dict.get('type')} - {proposal_dict.get('parameters', '')}"
                state["vector_results"] = await self.retrieve_from_vector_store(
                    query=vector_search_query, limit=5
                )

                # Fetch recent tweets
                recent_tweets = []
                if dao_id:
                    try:
                        self.logger.debug(f"Fetching tweets for DAO ID: {dao_id}")
                        queue_messages = backend.list_queue_messages(
                            QueueMessageFilter(
                                type=QueueMessageType.TWEET,
                                dao_id=dao_id,
                                is_processed=True,
                            )
                        )
                        sorted_messages = sorted(
                            queue_messages, key=lambda x: x.created_at, reverse=True
                        )[:5]
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
                    except Exception as e:
                        self.logger.error(
                            f"Failed to fetch tweets: {str(e)}", exc_info=True
                        )
                state["recent_tweets"] = recent_tweets

                # Fetch contract source for core proposals
                contract_source = ""
                if proposal_dict.get("type") == ProposalType.CORE and proposal_dict.get(
                    "proposal_contract"
                ):
                    parts = proposal_dict["proposal_contract"].split(".")
                    if len(parts) >= 2:
                        try:
                            api = HiroApi()
                            result = api.get_contract_source(parts[0], parts[1])
                            contract_source = result.get("source", "")
                        except Exception as e:
                            self.logger.error(
                                f"Failed to fetch contract source: {str(e)}",
                                exc_info=True,
                            )
                    else:
                        self.logger.warning(
                            f"Invalid contract format: {proposal_dict['proposal_contract']}"
                        )
                state["contract_source"] = contract_source

                # Validate proposal data structure (moved from entry point)
                proposal_type = proposal_dict.get("type")
                if proposal_type == ProposalType.ACTION and not proposal_dict.get(
                    "parameters"
                ):
                    raise ValueError("Action proposal missing parameters")
                if proposal_type == ProposalType.CORE and not proposal_dict.get(
                    "proposal_contract"
                ):
                    raise ValueError("Core proposal missing proposal_contract")

                return state
            except Exception as e:
                self.logger.error(f"Error in fetch_context: {str(e)}", exc_info=True)
                state["reasoning"] = f"Error fetching context: {str(e)}"
                # Propagate error state
                return state

        async def format_evaluation_prompt(state: EvaluationState) -> EvaluationState:
            """Format the evaluation prompt using the fetched context."""
            if "reasoning" in state and "Error" in state["reasoning"]:
                return state  # Skip if context fetching failed
            try:
                # Extract data from state for easier access
                proposal_data = state["proposal_data"]
                dao_info = state.get("dao_info", {})
                treasury_balance = state.get("treasury_balance")
                contract_source = state.get("contract_source", "")
                agent_prompts = state.get("agent_prompts", [])
                vector_results = state.get("vector_results", [])
                recent_tweets = state.get("recent_tweets", [])
                web_search_results = state.get("web_search_results", [])

                # Format agent prompts
                agent_prompts_str = "No agent-specific instructions available."
                if agent_prompts:
                    if isinstance(agent_prompts, list):
                        agent_prompts_str = "\n\n".join(agent_prompts)
                    else:
                        self.logger.warning(
                            f"Invalid agent prompts: {type(agent_prompts)}"
                        )

                # Format web search results
                web_search_content = "No relevant web search results found."
                if web_search_results:
                    # Create structured XML format for each web search result
                    web_search_items = []
                    for i, res in enumerate(web_search_results):
                        source_url = (
                            res.get("metadata", {})
                            .get("source_urls", [{}])[0]
                            .get("url", "Unknown")
                        )
                        web_search_items.append(
                            f"<search_result>\n<result_number>{i+1}</result_number>\n<content>{res.get('page_content', '')}</content>\n<source>{source_url}</source>\n</search_result>"
                        )
                    web_search_content = "\n".join(web_search_items)

                # Format vector context
                vector_context = "No additional context available from vector store."
                if vector_results:
                    # Create structured XML format for each vector result
                    vector_items = []
                    for i, doc in enumerate(vector_results):
                        vector_items.append(
                            f"<vector_item>\n<item_number>{i+1}</item_number>\n<content>{doc.page_content}</content>\n</vector_item>"
                        )
                    vector_context = "\n".join(vector_items)

                # Format recent tweets
                tweets_content = "No recent DAO tweets found."
                if recent_tweets:
                    # Create structured XML format for each tweet
                    tweet_items = []
                    for i, tweet in enumerate(recent_tweets):
                        tweet_items.append(
                            f"<tweet>\n<tweet_number>{i+1}</tweet_number>\n<date>{tweet['created_at']}</date>\n<message>{tweet['message']}</message>\n</tweet>"
                        )
                    tweets_content = "\n".join(tweet_items)

                # Convert JSON objects to formatted text
                # Format proposal_data
                proposal_data_str = "No proposal data available."
                if proposal_data:
                    proposal_data_str = "\n".join(
                        [
                            f"Proposal ID: {proposal_data.get('proposal_id', 'Unknown')}",
                            f"Type: {proposal_data.get('type', 'Unknown')}",
                            f"Action: {proposal_data.get('action', 'Unknown')}",
                            f"Parameters: {proposal_data.get('parameters', 'None')}",
                            f"Creator: {proposal_data.get('creator', 'Unknown')}",
                            f"Contract Principal: {proposal_data.get('contract_principal', 'Unknown')}",
                            f"Start Block: {proposal_data.get('start_block', 'Unknown')}",
                            f"End Block: {proposal_data.get('end_block', 'Unknown')}",
                            f"Created at Block: {proposal_data.get('created_at_block', 'Unknown')}",
                            f"Liquid Tokens: {proposal_data.get('liquid_tokens', 'Unknown')}",
                        ]
                    )

                    # Add proposal contract info if it exists
                    if proposal_data.get("proposal_contract"):
                        proposal_data_str += f"\nProposal Contract: {proposal_data.get('proposal_contract')}"

                # Format dao_info
                dao_info_str = "No DAO information available."
                if dao_info:
                    dao_info_str = "\n".join(
                        [
                            f"DAO Name: {dao_info.get('name', 'Unknown')}",
                            f"DAO Mission: {dao_info.get('mission', 'Unknown')}",
                            f"DAO Description: {dao_info.get('description', 'Unknown')}",
                        ]
                    )

                # Format treasury_balance
                treasury_balance_str = "Treasury balance information not available."
                if treasury_balance is not None:
                    treasury_balance_str = (
                        f"Current DAO Treasury Balance: {treasury_balance} STX"
                    )

                formatted_prompt = prompt.format(
                    proposal_data=proposal_data_str,
                    dao_info=dao_info_str,
                    treasury_balance=treasury_balance_str,
                    contract_source=contract_source,
                    agent_prompts=agent_prompts_str,
                    vector_context=vector_context,
                    recent_tweets=tweets_content,
                    web_search_results=web_search_content,
                )
                state["formatted_prompt"] = formatted_prompt
                return state
            except Exception as e:
                self.logger.error(f"Error formatting prompt: {str(e)}", exc_info=True)
                state["reasoning"] = f"Error formatting prompt: {str(e)}"
                return state

        async def call_evaluation_llm(state: EvaluationState) -> EvaluationState:
            """Call the LLM with the formatted prompt for evaluation."""
            if "reasoning" in state and "Error" in state["reasoning"]:
                return state  # Skip if previous steps failed
            try:
                # Prepare message content with text and images
                message_content = [{"type": "text", "text": state["formatted_prompt"]}]

                # Add any proposal images if they exist
                if state.get("proposal_images"):
                    message_content.extend(state["proposal_images"])

                # Create the message for the LLM
                message = HumanMessage(content=message_content)

                structured_output = self.llm.with_structured_output(
                    ProposalEvaluationOutput, include_raw=True
                )
                result: Dict[str, Any] = await structured_output.ainvoke([message])

                parsed_result = result.get("parsed")
                if not isinstance(parsed_result, ProposalEvaluationOutput):
                    # Attempt to handle cases where parsing might return the raw dict
                    if isinstance(parsed_result, dict):
                        parsed_result = ProposalEvaluationOutput(**parsed_result)
                    else:
                        raise TypeError(
                            f"Expected ProposalEvaluationOutput or dict, got {type(parsed_result)}"
                        )

                model_info = {"name": self.model_name, "temperature": self.temperature}
                token_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

                raw_response = result.get("raw")
                if raw_response:
                    if hasattr(raw_response, "usage_metadata"):
                        token_usage = raw_response.usage_metadata
                    else:
                        self.logger.warning("Raw response missing usage_metadata")
                else:
                    self.logger.warning("LLM result missing raw response data")

                state["approve"] = parsed_result.approve
                state["confidence_score"] = parsed_result.confidence_score
                state["reasoning"] = parsed_result.reasoning
                state["evaluation_token_usage"] = token_usage
                state["evaluation_model_info"] = model_info

                self.logger.debug(
                    f"Evaluation step complete: Decision={'APPROVE' if parsed_result.approve else 'REJECT'} | Confidence={parsed_result.confidence_score:.2f}"
                )
                self.logger.debug(f"Full reasoning: {parsed_result.reasoning}")

                return state
            except Exception as e:
                self.logger.error(f"Error calling LLM: {str(e)}", exc_info=True)
                state["approve"] = False
                state["confidence_score"] = 0.0
                state["reasoning"] = f"Error during LLM evaluation: {str(e)}"
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
                # Check if wallet_id is available
                if not state.get("wallet_id"):
                    self.logger.warning(
                        "No wallet_id provided for voting, skipping vote"
                    )
                    state["vote_result"] = {
                        "success": False,
                        "error": "No wallet_id provided for voting",
                    }
                    return state

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
        workflow.add_node("fetch_context", fetch_context)
        workflow.add_node("format_prompt", format_evaluation_prompt)
        workflow.add_node("evaluate", call_evaluation_llm)
        workflow.add_node("vote", vote_on_proposal)
        workflow.add_node("skip_vote", skip_voting)

        # Set up the conditional branching
        workflow.set_entry_point("fetch_context")  # Start with fetching context
        workflow.add_edge("fetch_context", "format_prompt")
        workflow.add_edge("format_prompt", "evaluate")
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
        # Only validate minimal required fields for initial state
        # Other fields like proposal_data are fetched within the workflow
        required_fields = ["proposal_id"]

        # Log the state for debugging
        self.logger.debug(
            f"Validating initial state: proposal_id={state.get('proposal_id')}"
        )

        # Check all fields and log problems
        for field in required_fields:
            if field not in state:
                self.logger.error(f"Missing required field: {field}")
                return False
            elif not state[field]:
                self.logger.error(f"Empty required field: {field}")
                return False

        # Note: Detailed validation of proposal_data happens in fetch_context node
        self.logger.debug("Initial state validation successful")
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


async def evaluate_and_vote_on_proposal(
    proposal_id: UUID,
    wallet_id: Optional[UUID] = None,
    agent_id: Optional[UUID] = None,
    auto_vote: bool = True,
    confidence_threshold: float = 0.7,
    dao_id: Optional[UUID] = None,
) -> Dict:
    """Evaluate a proposal and automatically vote based on the evaluation.

    Args:
        proposal_id: The ID of the proposal to evaluate and vote on
        wallet_id: Optional wallet ID to use for voting
        agent_id: Optional agent ID to use for retrieving prompts
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
        # Determine effective agent ID
        effective_agent_id = agent_id
        if not effective_agent_id and wallet_id:
            wallet = backend.get_wallet(wallet_id)
            if wallet and wallet.agent_id:
                effective_agent_id = wallet.agent_id
                logger.debug(
                    f"Using agent ID {effective_agent_id} from wallet {wallet_id}"
                )

        # Fetch the primary prompt to determine model and temperature settings
        # Note: Actual prompt text fetching happens inside the workflow now.
        model_name = "gpt-4.1"  # Default model
        temperature = 0.1  # Default temperature
        if effective_agent_id:
            try:
                # We only need one active prompt to get settings
                prompts = backend.list_prompts(
                    PromptFilter(
                        agent_id=effective_agent_id,
                        dao_id=dao_id,  # Assuming dao_id is available, might need refinement
                        is_active=True,
                        limit=1,
                    )
                )
                if prompts:
                    first_prompt = prompts[0]
                    model_name = first_prompt.model or model_name
                    temperature = (
                        first_prompt.temperature
                        if first_prompt.temperature is not None
                        else temperature
                    )
                    logger.debug(
                        f"Using model settings from agent {effective_agent_id}: {model_name} (temp={temperature})"
                    )
                else:
                    logger.warning(
                        f"No active prompts found for agent {effective_agent_id} to determine settings."
                    )
            except Exception as e:
                logger.error(
                    f"Failed to get agent prompt settings: {str(e)}", exc_info=True
                )

        # Initialize state (minimal initial data)
        state = {
            "proposal_id": proposal_id,
            "dao_id": dao_id,  # Pass DAO ID to the workflow
            "agent_id": effective_agent_id,  # Pass Agent ID for prompt loading
            "wallet_id": wallet_id,  # Pass wallet ID for voting tool
            "approve": False,
            "confidence_score": 0.0,
            "reasoning": "",
            "vote_result": None,
            "confidence_threshold": confidence_threshold,
            "auto_vote": auto_vote,
            "vector_results": None,
            "recent_tweets": None,
            "web_search_results": None,
            "token_usage": None,
            "model_info": None,
            "web_search_token_usage": None,
            "evaluation_token_usage": None,
            "evaluation_model_info": None,
            "web_search_model_info": None,
        }

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
                "approve": result.get("approve", False),
                "confidence_score": result.get("confidence_score", 0.0),
                "reasoning": result.get(
                    "reasoning", "Evaluation failed or not available"
                ),
            },
            "vote_result": result.get("vote_result"),
            "auto_voted": auto_vote
            and result.get("confidence_score", 0.0) >= confidence_threshold,
            "tx_id": tx_id,
            "formatted_prompt": result.get(
                "formatted_prompt", "Formatted prompt not available"
            ),
            "vector_results": result.get("vector_results"),
            "recent_tweets": result.get("recent_tweets"),
            "web_search_results": result.get("web_search_results"),
            "treasury_balance": result.get("treasury_balance"),
            "web_search_token_usage": result.get("web_search_token_usage"),
            "evaluation_token_usage": result.get("evaluation_token_usage"),
            "evaluation_model_info": result.get("evaluation_model_info"),
            "web_search_model_info": result.get("web_search_model_info"),
        }

        # --- Aggregate Token Usage and Calculate Costs --- #
        total_token_usage_by_model = {}
        total_cost_by_model = {}
        total_overall_cost = 0.0

        steps = [
            (
                "web_search",
                result.get("web_search_token_usage"),
                result.get("web_search_model_info"),
            ),
            (
                "evaluation",
                result.get("evaluation_token_usage"),
                result.get("evaluation_model_info"),
            ),
        ]

        for step_name, usage, model_info in steps:
            if usage and model_info and model_info.get("name") != "unknown":
                model_name = model_info["name"]

                # Aggregate usage per model
                if model_name not in total_token_usage_by_model:
                    total_token_usage_by_model[model_name] = {
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "total_tokens": 0,
                    }
                total_token_usage_by_model[model_name]["input_tokens"] += usage.get(
                    "input_tokens", 0
                )
                total_token_usage_by_model[model_name]["output_tokens"] += usage.get(
                    "output_tokens", 0
                )
                total_token_usage_by_model[model_name]["total_tokens"] += usage.get(
                    "total_tokens", 0
                )

                # Calculate cost for this step/model
                step_cost = calculate_token_cost(usage, model_name)

                # Aggregate cost per model
                if model_name not in total_cost_by_model:
                    total_cost_by_model[model_name] = 0.0
                total_cost_by_model[model_name] += step_cost["total_cost"]
                total_overall_cost += step_cost["total_cost"]
            else:
                logger.warning(
                    f"Skipping cost calculation for step '{step_name}' due to missing usage or model info."
                )

        final_result["total_token_usage_by_model"] = total_token_usage_by_model
        final_result["total_cost_by_model"] = total_cost_by_model
        final_result["total_overall_cost"] = total_overall_cost
        # --- End Aggregation --- #

        # Updated Logging
        logger.debug(
            f"Proposal evaluation completed: Success={final_result['success']} | "
            f"Decision={'APPROVE' if final_result['evaluation']['approve'] else 'REJECT'} | "
            f"Confidence={final_result['evaluation']['confidence_score']:.2f} | "
            f"Auto-voted={final_result['auto_voted']} | Transaction={tx_id or 'None'} | "
            f"Total Cost (USD)=${total_overall_cost:.4f}"
        )
        logger.debug(f"Cost Breakdown: {total_cost_by_model}")
        logger.debug(f"Token Usage Breakdown: {total_token_usage_by_model}")
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
    agent_id: Optional[UUID] = None,
    dao_id: Optional[UUID] = None,
) -> Dict:
    """Evaluate a proposal without voting.

    Args:
        proposal_id: The ID of the proposal to evaluate
        wallet_id: Optional wallet ID to use for retrieving proposal data
        agent_id: Optional agent ID associated with the evaluation
        dao_id: Optional DAO ID associated with the proposal

    Returns:
        Dictionary containing the evaluation results
    """
    logger.debug(f"Starting proposal-only evaluation: proposal_id={proposal_id}")

    # Determine effective agent ID (same logic as evaluate_and_vote)
    effective_agent_id = agent_id
    if not effective_agent_id and wallet_id:
        wallet = backend.get_wallet(wallet_id)
        if wallet and wallet.agent_id:
            effective_agent_id = wallet.agent_id

    result = await evaluate_and_vote_on_proposal(
        proposal_id=proposal_id,
        wallet_id=wallet_id,
        agent_id=effective_agent_id,
        dao_id=dao_id,
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
