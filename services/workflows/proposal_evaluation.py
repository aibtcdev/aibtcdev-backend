"""Proposal evaluation workflow."""

import binascii
from typing import Dict, List, Optional, TypedDict

from langchain.prompts import PromptTemplate
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langgraph.graph import END, Graph, StateGraph
from pydantic import BaseModel, Field

from backend.factory import backend
from backend.models import (
    UUID,
    Profile,
    PromptFilter,
    ProposalType,
)
from lib.hiro import HiroApi
from lib.logger import configure_logger
from services.workflows.base import BaseWorkflow, VectorRetrievalCapability
from services.workflows.vector_react import VectorLangGraphService, VectorReactState
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
    vector_results: Optional[List[Dict]]  # Add vector results to state


class ProposalEvaluationWorkflow(
    BaseWorkflow[EvaluationState], VectorRetrievalCapability
):
    """Workflow for evaluating DAO proposals and voting automatically."""

    def __init__(
        self,
        collection_names: Optional[List[str]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.collection_names = collection_names or [
            "knowledge_collection",
            "dao_collection",
        ]
        self.required_fields = ["proposal_id", "proposal_data"]
        # Initialize embeddings
        self.embeddings = OpenAIEmbeddings()

    async def retrieve_from_vector_store(self, query: str, **kwargs) -> List[Document]:
        """Retrieve relevant documents from multiple vector stores.

        Args:
            query: The query to search for
            **kwargs: Additional arguments

        Returns:
            List of retrieved documents
        """
        try:
            all_documents = []
            limit_per_collection = kwargs.get(
                "limit", 4
            )  # Get 4 results from each collection

            # Query each collection and gather results
            for collection_name in self.collection_names:
                try:
                    # Query vectors using the backend
                    vector_results = await backend.query_vectors(
                        collection_name=collection_name,
                        query_text=query,
                        limit=limit_per_collection,
                        embeddings=self.embeddings,
                    )

                    # Convert to LangChain Documents and add collection source
                    documents = [
                        Document(
                            page_content=doc.get("page_content", ""),
                            metadata={
                                **doc.get("metadata", {}),
                                "collection_source": collection_name,
                            },
                        )
                        for doc in vector_results
                    ]

                    all_documents.extend(documents)
                    logger.info(
                        f"Retrieved {len(documents)} documents from collection {collection_name}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to retrieve from collection {collection_name}: {str(e)}"
                    )
                    continue  # Continue with other collections if one fails

            logger.info(
                f"Retrieved total of {len(all_documents)} documents from all collections"
            )
            return all_documents
        except Exception as e:
            logger.error(f"Vector store retrieval failed: {str(e)}")
            return []

    def _create_prompt(self) -> PromptTemplate:
        """Create the evaluation prompt template."""
        return PromptTemplate(
            input_variables=[
                "proposal_data",
                "dao_info",
                "contract_source",
                "agent_prompts",
                "vector_context",
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

            # 4. AIBTC CHARTER
            Core Values: Curiosity, Truth Maximizing, Humanity's Best Interests, Transparency, Resilience, Collaboration
            Mission: Elevate human potential through Autonomous Intelligence on Bitcoin
            Guardrails: Decentralized Governance, Smart Contract accountability

            # 5. CONTRACT SOURCE (for core proposals)
            {contract_source}

            # 6. EVALUATION CRITERIA
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

            # 7. CONFIDENCE SCORING RUBRIC
            You MUST choose one of these confidence bands:
            - 0.0-0.2: Extremely low confidence (major red flags or insufficient information)
            - 0.3-0.4: Low confidence (significant concerns or unclear implications)
            - 0.5-0.6: Moderate confidence (some concerns but manageable)
            - 0.7-0.8: High confidence (minor concerns if any)
            - 0.9-1.0: Very high confidence (clear positive alignment)

            # 8. QUALITY STANDARDS
            Your evaluation must uphold clarity, reasoning, and respect for the DAO's voice:
            • Be clear and specific — avoid vagueness or filler
            • Use a consistent tone, but reflect the DAO's personality if known
            • Avoid casual throwaway phrases, sarcasm, or hype
            • Don't hedge — take a position and justify it clearly
            • Make every point logically sound and backed by facts or context
            • Cite relevant parts of the proposal, DAO mission, or prior actions
            • Use terms accurately — don't fake precision
            • Keep structure clean and easy to follow

            # 9. VECTOR CONTEXT
            {vector_context}

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
                            else:
                                logger.warning(
                                    f"Could not find source code in API response: {result}"
                                )
                        except Exception as e:
                            logger.error(f"Error fetching contract source: {str(e)}")
                    else:
                        logger.warning(
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
                    logger.info(
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
                    logger.error(f"Error retrieving from vector store: {str(e)}")
                    vector_context = (
                        "No additional context available from vector store."
                    )

                # Format prompt with state
                self.logger.debug("Formatting evaluation prompt...")

                # Format agent prompts as a string
                agent_prompts_str = "No agent-specific instructions available."
                if state.get("agent_prompts"):
                    logger.debug(
                        f"Raw agent prompts from state: {state['agent_prompts']}"
                    )
                    if (
                        isinstance(state["agent_prompts"], list)
                        and state["agent_prompts"]
                    ):
                        # Just use the prompt text directly since that's what we're storing
                        agent_prompts_str = "\n\n".join(state["agent_prompts"])
                        logger.debug(
                            f"Formatted agent prompts string: {agent_prompts_str}"
                        )
                    else:
                        logger.warning(
                            f"Invalid agent prompts format in state: {type(state['agent_prompts'])}"
                        )
                else:
                    logger.warning("No agent prompts found in state")

                formatted_prompt = self._create_prompt().format(
                    proposal_data=proposal_data,
                    dao_info=state.get(
                        "dao_info", "No additional DAO information available."
                    ),
                    contract_source=contract_source,
                    agent_prompts=agent_prompts_str,
                    vector_context=vector_context,  # Add vector context to prompt
                )

                # Get evaluation from LLM
                self.logger.debug("Invoking LLM for evaluation...")
                structured_output = self.llm.with_structured_output(
                    ProposalEvaluationOutput,
                )
                result = structured_output.invoke(formatted_prompt)
                self.logger.debug(f"LLM evaluation result: {result}")

                # Update state
                state["formatted_prompt"] = formatted_prompt
                state["approve"] = result.approve
                state["confidence_score"] = result.confidence_score
                state["reasoning"] = result.reasoning
                self.logger.info(
                    f"Evaluation complete: approve={result.approve}, confidence={result.confidence_score}"
                )

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
                    f"Deciding whether to vote: auto_vote={state['auto_vote']}, confidence={state['confidence_score']}, threshold={state['confidence_threshold']}"
                )

                if not state["auto_vote"]:
                    self.logger.info("Auto-vote is disabled, skipping vote")
                    return "skip_vote"

                if state["confidence_score"] >= state["confidence_threshold"]:
                    self.logger.info(
                        f"Confidence score {state['confidence_score']} meets threshold {state['confidence_threshold']}, proceeding to vote"
                    )
                    return "vote"
                else:
                    self.logger.info(
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
                    f"Setting up VectorReact workflow to vote on proposal {state['proposal_id']}, vote={state['approve']}"
                )

                # Set up the voting tool
                vote_tool = VoteOnActionProposalTool(wallet_id=state["wallet_id"])
                tools_map = {"dao_action_vote_on_proposal": vote_tool}

                # Create a user input message that instructs the LLM what to do
                vote_instruction = f"""
                I need you to vote on a DAO proposal with ID {state['proposal_id']} in the contract {state['action_proposals_contract']}.
                
                Please vote {"FOR" if state['approve'] else "AGAINST"} the proposal.
                
                Use the dao_action_vote_on_proposal tool to submit the vote.
                """

                # Create VectorLangGraph service with collections
                service = VectorLangGraphService(
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
                            self.logger.info(f"Vote result: {vote_result}")

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
                self.logger.debug("Skipping voting step")
                state["vote_result"] = {
                    "success": True,
                    "message": "Voting skipped due to confidence threshold or auto_vote setting",
                    "data": None,
                }
                self.logger.info("Vote skipped as requested")
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
        self.logger.debug(f"Validating state: {state}")

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

    # Log all available tools for debugging
    logger.debug(f"All available tools: {', '.join(all_tools.keys())}")

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
    logger.debug(f"Filtered tools: {', '.join(filtered_tools.keys())}")

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
        return decoded_string
    except (binascii.Error, UnicodeDecodeError):
        return None  # Return None if decoding fails


async def evaluate_and_vote_on_proposal(
    proposal_id: UUID,
    wallet_id: Optional[UUID] = None,
    auto_vote: bool = True,
    confidence_threshold: float = 0.1,
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
    logger.info(f"Starting proposal evaluation for proposal {proposal_id}")

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
            logger.debug(f"Decoded parameters: {decoded_parameters}")

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
            logger.debug(f"Using provided DAO ID: {dao_id}")
            dao_info = backend.get_dao(dao_id)
            if not dao_info:
                logger.warning(
                    f"Provided DAO ID {dao_id} not found, falling back to proposal's DAO ID"
                )

        # If dao_info is still None, try to get it from proposal's dao_id
        if not dao_info and proposal_data.dao_id:
            logger.debug(f"Using proposal's DAO ID: {proposal_data.dao_id}")
            dao_info = backend.get_dao(proposal_data.dao_id)

        if not dao_info:
            error_msg = "Could not find DAO information"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        logger.debug(f"Using DAO: {dao_info.name} (ID: {dao_info.id})")

        # Get the wallet and agent information if available
        agent_id = None
        if wallet_id:
            wallet = backend.get_wallet(wallet_id)
            if wallet and wallet.agent_id:
                agent_id = wallet.agent_id
                logger.debug(f"Found agent ID {agent_id} for wallet {wallet_id}")

        # Get agent prompts
        agent_prompts = []
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
            logger.debug(f"Raw prompts from database: {prompts}")

            # Extract prompt texts
            agent_prompts = [p.prompt_text for p in prompts if p.prompt_text]
            logger.debug(f"Extracted agent prompts: {agent_prompts}")

            logger.info(
                f"Found {len(agent_prompts)} active prompts for agent {agent_id}"
            )
            if not agent_prompts:
                logger.warning(
                    f"No active prompts found for agent_id={agent_id}, dao_id={proposal_data.dao_id}"
                )
        except Exception as e:
            logger.error(f"Error getting agent prompts: {e}", exc_info=True)

        # Initialize state
        state = {
            "action_proposals_contract": proposal_dict["contract_principal"],
            "action_proposals_voting_extension": proposal_dict["action"],
            "proposal_id": proposal_dict["proposal_id"],
            "proposal_data": proposal_dict,
            "dao_info": dao_info.model_dump() if dao_info else {},
            "agent_prompts": agent_prompts,  # Add agent prompts to state
            "approve": False,
            "confidence_score": 0.0,
            "reasoning": "",
            "vote_result": None,
            "wallet_id": wallet_id,
            "confidence_threshold": confidence_threshold,
            "auto_vote": auto_vote,
            "vector_results": None,  # Initialize vector results
        }

        logger.debug(f"State agent_prompts: {state['agent_prompts']}")

        # Create and run workflow
        workflow = ProposalEvaluationWorkflow()
        if not workflow._validate_state(state):
            return {
                "success": False,
                "error": "Invalid workflow state",
            }

        result = await workflow.execute(state)

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
                            break

        return {
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
        }
    except Exception as e:
        logger.error(f"Error in evaluate_and_vote_on_proposal: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
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
    result = await evaluate_and_vote_on_proposal(
        proposal_id=proposal_id,
        wallet_id=wallet_id,
        auto_vote=True,
    )

    # Remove vote_result from the response
    if "vote_result" in result:
        del result["vote_result"]
    if "auto_voted" in result:
        del result["auto_voted"]

    return result


async def debug_proposal_evaluation_workflow():
    """Debug function to test the workflow with a mock state."""
    logger.setLevel("DEBUG")

    # Create a mock state with valid required fields
    mock_state = {
        "action_proposals_contract": "test-contract",
        "action_proposals_voting_extension": "test-voting-extension",
        "proposal_id": 1,
        "proposal_data": {"title": "Test Proposal", "description": "Test Description"},
        "dao_info": {"name": "Test DAO"},
        "approve": False,
        "confidence_score": 0.0,
        "reasoning": "",
        "vote_result": None,
        "wallet_id": None,
        "confidence_threshold": 0.7,
        "auto_vote": False,
        "vector_results": None,  # Initialize vector results
    }

    # Create the workflow and validate the state
    workflow = ProposalEvaluationWorkflow()
    is_valid = workflow._validate_state(mock_state)
    logger.info(f"Mock state validation result: {is_valid}")

    # Try to execute with the mock state
    if is_valid:
        try:
            result = await workflow.execute(mock_state)
            logger.info(f"Workflow execution result: {result}")
        except Exception as e:
            logger.error(f"Workflow execution failed: {str(e)}", exc_info=True)

    return is_valid
