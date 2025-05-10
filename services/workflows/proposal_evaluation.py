import asyncio
import base64
import operator
import uuid
from typing import Annotated, Any, Dict, List, Optional, TypedDict, Union

import httpx
from langchain.prompts import PromptTemplate
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.channels import LastValue
from langgraph.graph import END, Graph, StateGraph
from pydantic import BaseModel, Field

from backend.factory import backend
from backend.models import (
    UUID,
    ExtensionFilter,
    Profile,
    PromptFilter,
    ProposalBase,
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
from services.workflows.capability_mixins import BaseCapabilityMixin
from services.workflows.chat import ChatService, StreamingCallbackHandler
from services.workflows.hierarchical_workflows import (
    HierarchicalTeamWorkflow,
    append_list_fn,
    merge_dict_fn,
)
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


def no_update_reducer(current: Any, new: List[Any]) -> Any:
    """Reducer that prevents updates after initial value is set."""
    # Treat initial empty string for str types as if it were None for accepting the first value
    is_initial_empty_string = isinstance(current, str) and current == ""

    # If current is genuinely set (not None and not initial empty string), keep it.
    if current is not None and not is_initial_empty_string:
        return current

    # Current is None or an initial empty string. Try to set it from new.
    processed_new_values = (
        new if isinstance(new, list) else [new]
    )  # Ensure 'new' is a list
    for n_val in processed_new_values:
        if n_val is not None:
            return n_val

    # If current was None/initial empty string and new is all None or empty, return current (which is None or '')
    return current


def merge_dicts(current: Optional[Dict], updates: List[Optional[Dict]]) -> Dict:
    """Merge multiple dictionary updates into the current dictionary."""
    # Initialize current if it's None
    if current is None:
        current = {}

    # Handle case where updates is None
    if updates is None:
        return current

    # Process updates if it's a list
    if isinstance(updates, list):
        for update in updates:
            if update and isinstance(update, dict):
                current.update(update)
    # Handle case where updates is a single dictionary, not a list
    elif isinstance(updates, dict):
        current.update(updates)

    return current


def set_once(current: Any, updates: List[Any]) -> Any:
    """Set the value once and prevent further updates."""
    # If current already has a value, return it unchanged
    if current is not None:
        return current

    # Handle case where updates is None instead of a list
    if updates is None:
        return None

    # Process updates if it's a list
    if isinstance(updates, list):
        for update in updates:
            if update is not None:
                return update
    # Handle case where updates is a single value, not a list
    elif updates is not None:
        return updates

    return current


class ProposalEvaluationState(TypedDict):
    """Type definition for the proposal evaluation state."""

    proposal_id: Annotated[str, no_update_reducer]
    proposal_data: Annotated[str, no_update_reducer]
    core_score: Annotated[Optional[Dict[str, Any]], set_once]
    historical_score: Annotated[Optional[Dict[str, Any]], set_once]
    financial_score: Annotated[Optional[Dict[str, Any]], set_once]
    social_score: Annotated[Optional[Dict[str, Any]], set_once]
    final_score: Annotated[Optional[Dict[str, Any]], set_once]
    flags: Annotated[List[str], append_list_fn]  # Correctly appends lists
    summaries: Annotated[Dict[str, str], merge_dicts]  # Properly merges dictionaries
    decision: Annotated[Optional[str], set_once]
    halt: Annotated[bool, operator.or_]
    token_usage: Annotated[
        Dict[str, Dict[str, int]], merge_dicts
    ]  # Properly merges dictionaries
    core_agent_invocations: Annotated[int, operator.add]
    proposal_images: Annotated[Optional[List[Dict]], set_once]


class AgentOutput(BaseModel):
    """Output model for agent evaluations."""

    score: int = Field(description="Score from 0-100")
    flags: List[str] = Field(description="Critical issues flagged")
    summary: str = Field(description="Summary of findings")


class FinalOutput(BaseModel):
    """Output model for the final evaluation decision."""

    score: int = Field(description="Final evaluation score")
    decision: str = Field(description="Approve or Reject")
    explanation: str = Field(description="Reasoning for decision")


def update_state_with_agent_result(
    state: ProposalEvaluationState, agent_result: Dict[str, Any], agent_name: str
):
    """Helper function to update state with agent result including summaries and flags."""
    # Simplified logging - just log once with relevant details
    logger.debug(
        f"[DEBUG:update_state:{agent_name}] Updating state with {agent_name}_score (score: {agent_result.get('score', 'N/A')})"
    )

    # Update agent score in state
    if agent_name in ["core", "historical", "financial", "social", "final"]:
        # Make a copy of agent_result to avoid modifying the original
        score_dict = dict(agent_result)
        # Don't pass token_usage through this path to avoid duplication
        if "token_usage" in score_dict:
            del score_dict["token_usage"]

        # Directly assign the dictionary to the state key
        state[f"{agent_name}_score"] = score_dict

    # Update summaries
    if "summaries" not in state:
        state["summaries"] = {}

    if "summary" in agent_result and agent_result["summary"]:
        state["summaries"][f"{agent_name}_score"] = agent_result["summary"]

    # Update flags
    if "flags" not in state:
        state["flags"] = []

    if "flags" in agent_result and isinstance(agent_result["flags"], list):
        state["flags"].extend(agent_result["flags"])

    # Note: Token usage is already directly handled by each agent via state["token_usage"]["{agent_name}_agent"]
    # So we don't need to do anything with token usage here

    return state


class CoreContextAgent(BaseCapabilityMixin, VectorRetrievalCapability):
    """Core Context Agent evaluates proposals against DAO mission and standards."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Core Context Agent."""
        BaseCapabilityMixin.__init__(self, config=config, state_key="core_score")
        VectorRetrievalCapability.__init__(self)
        self.initialize()
        self._initialize_vector_capability()

    def _initialize_vector_capability(self):
        """Initialize the vector retrieval functionality."""
        if not hasattr(self, "retrieve_from_vector_store"):
            self.retrieve_from_vector_store = (
                VectorRetrievalCapability.retrieve_from_vector_store.__get__(
                    self, self.__class__
                )
            )
            self.logger.info(
                "Initialized vector retrieval capability for CoreContextAgent"
            )

    async def process(self, state: ProposalEvaluationState) -> Dict[str, Any]:
        """Evaluate the proposal against DAO core mission and standards."""
        self._initialize_vector_capability()

        proposal_id = state.get("proposal_id", "unknown")
        proposal_content = state.get("proposal_data", "")

        dao_mission_text = self.config.get("dao_mission", "")
        if not dao_mission_text:
            try:
                self.logger.debug(
                    f"[DEBUG:CoreAgent:{proposal_id}] Attempting to retrieve DAO mission from vector store"
                )
                dao_mission = await self.retrieve_from_vector_store(
                    query="DAO mission statement and values",
                    collection_name=self.config.get(
                        "mission_collection", "dao_documents"
                    ),
                    limit=3,
                )
                dao_mission_text = "\n".join([doc.page_content for doc in dao_mission])
                self.logger.debug(
                    f"[DEBUG:CoreAgent:{proposal_id}] Retrieved DAO mission, length: {len(dao_mission_text)}"
                )
            except Exception as e:
                self.logger.error(
                    f"[DEBUG:CoreAgent:{proposal_id}] Error retrieving DAO mission: {str(e)}",
                    exc_info=True,
                )
                dao_mission_text = "Elevate human potential through AI on Bitcoin"
                self.logger.debug(
                    f"[DEBUG:CoreAgent:{proposal_id}] Using default DAO mission: {dao_mission_text}"
                )

        prompt = PromptTemplate(
            input_variables=["proposal_data", "dao_mission"],
            template="""Evaluate the following proposal against the DAO's mission and values.\\n            
Proposal: {proposal_data}\\nDAO Mission: {dao_mission}\\n
Assess whether this proposal aligns with the DAO's core mission and values.\\nConsider:\\n1. Mission Alignment: Does it directly support the stated mission?\\n2. Quality Standards: Does it meet quality requirements?\\n3. Innovation: Does it bring new ideas aligned with our vision?\\n4. Impact: How significant is its potential contribution?\\n
# ADDED: Image processing instructions
**Image Analysis Instructions:**
If images are provided with this proposal (they will appear after this text), you MUST analyze them as an integral part of the proposal.
- Relevance: Does each image directly relate to and support the proposal's text?
- Evidence: Do the images provide visual evidence for claims made in the proposal?
- Authenticity & Quality: Are the images clear, authentic, and not misleading or manipulated?
- Cohesion: The images and text MUST form a cohesive and consistent whole. If any image contradicts the text, is irrelevant, misleading, of very poor quality, or inappropriate, you should consider this a significant flaw in the proposal.

Provide a score from 0-100, flag any critical issues (including image-related ones), and summarize your findings, explicitly mentioning your image analysis if images were present.\\
            """,
        )

        try:
            self.logger.debug(
                f"[DEBUG:CoreAgent:{proposal_id}] Formatting prompt for evaluation"
            )
            formatted_prompt_text = prompt.format(
                proposal_data=proposal_content,
                dao_mission=dao_mission_text
                or "Elevate human potential through AI on Bitcoin",
            )
            debug_level = self.config.get("debug_level", 0)
            if debug_level >= 2:
                self.logger.debug(
                    f"[PROPOSAL_DEBUG:CoreAgent] FULL EVALUATION PROMPT:\n{formatted_prompt_text}"
                )
            else:
                self.logger.debug(
                    f"[PROPOSAL_DEBUG:CoreAgent] Generated evaluation prompt: {formatted_prompt_text}"
                )
        except Exception as e:
            self.logger.error(
                f"[DEBUG:CoreAgent:{proposal_id}] Error formatting prompt: {str(e)}",
                exc_info=True,
            )
            formatted_prompt_text = f"Evaluate proposal: {proposal_content}"

        try:
            self.logger.debug(
                f"[DEBUG:CoreAgent:{proposal_id}] Invoking LLM for core evaluation"
            )

            # ADDED: Image handling
            proposal_images_list = state.get("proposal_images", [])
            if not isinstance(proposal_images_list, list):
                self.logger.warning(
                    f"[DEBUG:CoreAgent:{proposal_id}] proposal_images is not a list: {type(proposal_images_list)}. Defaulting to empty list."
                )
                proposal_images_list = []

            message_content_list = [{"type": "text", "text": formatted_prompt_text}]
            if proposal_images_list:
                self.logger.debug(
                    f"[DEBUG:CoreAgent:{proposal_id}] Adding {len(proposal_images_list)} images to LLM input."
                )
                message_content_list.extend(proposal_images_list)

            llm_input_message = HumanMessage(content=message_content_list)

            result = await self.llm.with_structured_output(AgentOutput).ainvoke(
                [llm_input_message]
            )
            self.logger.debug(
                f"[DEBUG:CoreAgent:{proposal_id}] LLM returned core evaluation with score: {result.score}"
            )
            self.logger.info(
                f"[DEBUG:CoreAgent:{proposal_id}] SCORE={result.score}/100 | FLAGS={result.flags} | SUMMARY={result.summary}"
            )

            # Track token usage - extract directly from LLM if available
            token_usage_data = {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
            }

            # Use the Annotated operator.add feature by assigning 1 to increment
            # This is safe with concurrent execution
            state["core_agent_invocations"] = 1

            # Try to extract token usage directly from LLM response
            if (
                hasattr(self.llm, "_last_prompt_id")
                and hasattr(self.llm, "client")
                and hasattr(self.llm.client, "usage_by_prompt_id")
            ):
                last_prompt_id = self.llm._last_prompt_id
                if last_prompt_id in self.llm.client.usage_by_prompt_id:
                    usage = self.llm.client.usage_by_prompt_id[last_prompt_id]
                    token_usage_data = {
                        "input_tokens": usage.get("prompt_tokens", 0),
                        "output_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0),
                    }
                    self.logger.debug(
                        f"[DEBUG:CoreAgent:{proposal_id}] Extracted token usage from LLM: {token_usage_data}"
                    )
            # Fallback to estimation
            if token_usage_data["total_tokens"] == 0:
                # Get model name from LLM
                llm_model_name = getattr(self.llm, "model_name", "gpt-4.1")
                # First calculate token count from the text
                token_count = len(formatted_prompt_text) // 4  # Simple estimation
                # Create token usage dictionary for calculate_token_cost
                token_usage_dict = {"input_tokens": token_count}
                # Calculate cost
                cost_result = calculate_token_cost(token_usage_dict, llm_model_name)
                token_usage_data = {
                    "input_tokens": token_count,
                    "output_tokens": len(result.model_dump_json())
                    // 4,  # rough estimate
                    "total_tokens": token_count + len(result.model_dump_json()) // 4,
                    "model_name": llm_model_name,  # Include model name
                }
                self.logger.debug(
                    f"[DEBUG:CoreAgent:{proposal_id}] Estimated token usage: {token_usage_data}"
                )

            # Add token usage to state
            if "token_usage" not in state:
                state["token_usage"] = {}
            state["token_usage"]["core_agent"] = token_usage_data

            result_dict = result.model_dump()
            # Add token usage to result_dict so it's properly processed
            result_dict["token_usage"] = token_usage_data

            # Remove verbose debug logs and simply update state
            update_state_with_agent_result(state, result_dict, "core")

            return result_dict
        except Exception as e:
            self.logger.error(
                f"[DEBUG:CoreAgent:{proposal_id}] Error in core evaluation: {str(e)}",
                exc_info=True,
            )
            fallback_score_dict = {
                "score": 50,
                "flags": [f"Error: {str(e)}"],
                "summary": "Evaluation failed due to error",
            }
            self.logger.info(
                f"[DEBUG:CoreAgent:{proposal_id}] ERROR_SCORE=50/100 | FLAGS=[{str(e)}] | SUMMARY=Evaluation failed"
            )
            return fallback_score_dict


class HistoricalContextAgent(BaseCapabilityMixin, VectorRetrievalCapability):
    """Historical Context Agent examines past proposals and patterns."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        BaseCapabilityMixin.__init__(self, config=config, state_key="historical_score")
        VectorRetrievalCapability.__init__(self)
        self.initialize()
        self._initialize_vector_capability()

    def _initialize_vector_capability(self):
        if not hasattr(self, "retrieve_from_vector_store"):
            self.retrieve_from_vector_store = (
                VectorRetrievalCapability.retrieve_from_vector_store.__get__(
                    self, self.__class__
                )
            )
            self.logger.info(
                "Initialized vector retrieval capability for HistoricalContextAgent"
            )

    async def process(self, state: ProposalEvaluationState) -> Dict[str, Any]:
        proposal_id = state.get("proposal_id", "unknown")
        self._initialize_vector_capability()
        proposal_content = state.get("proposal_data", "")

        historical_text = ""
        try:
            self.logger.debug(
                f"[DEBUG:HistoricalAgent:{proposal_id}] Searching for similar proposals: {proposal_content[:50]}..."
            )
            similar_proposals = await self.retrieve_from_vector_store(
                query=f"Proposals similar to: {proposal_content}",
                collection_name=self.config.get(
                    "proposals_collection", "past_proposals"
                ),
                limit=5,
            )
            historical_text = "\n".join([doc.page_content for doc in similar_proposals])
            self.logger.debug(
                f"[DEBUG:HistoricalAgent:{proposal_id}] Found {len(similar_proposals)} similar proposals"
            )
        except Exception as e:
            self.logger.error(
                f"[DEBUG:HistoricalAgent:{proposal_id}] Error retrieving historical proposals: {str(e)}",
                exc_info=True,
            )
            historical_text = "No similar historical proposals found."
        prompt = PromptTemplate(
            input_variables=["proposal_data", "historical_proposals"],
            template="""Analyze this proposal in the context of historical patterns and similar past proposals.\\n            
Current Proposal: {proposal_data}\\nSimilar Past Proposals: {historical_proposals}\\n
Evaluate:\\n1. Precedent: Have similar proposals been approved or rejected?\\n2. Cross-DAO Similarities: How does this compare to proposals in similar DAOs?\\n3. Learning from Past: Does it address issues from past proposals?\\n4. Uniqueness: Is this novel or repeating past ideas?\\n
# ADDED: Image processing instructions
**Image Analysis Instructions:**
If images are provided with this proposal (they will appear after this text), you MUST analyze them as an integral part of the proposal.
- Relevance: Does each image directly relate to and support the proposal's text?
- Evidence: Do the images provide visual evidence for claims made in the proposal?
- Authenticity & Quality: Are the images clear, authentic, and not misleading or manipulated?
- Cohesion: The images and text MUST form a cohesive and consistent whole. If any image contradicts the text, is irrelevant, misleading, of very poor quality, or inappropriate, you should consider this a significant flaw in the proposal.

Provide a score from 0-100, flag any critical issues (including image-related ones), and summarize your findings, explicitly mentioning your image analysis if images were present.\\
            """,
        )
        try:
            self.logger.debug(
                f"[DEBUG:HistoricalAgent:{proposal_id}] Formatting prompt"
            )
            formatted_prompt_text = prompt.format(
                proposal_data=proposal_content,
                historical_proposals=historical_text
                or "No similar historical proposals found.",
            )
        except Exception as e:
            self.logger.error(
                f"[DEBUG:HistoricalAgent:{proposal_id}] Error formatting prompt: {str(e)}",
                exc_info=True,
            )
            formatted_prompt_text = f"Analyze proposal: {proposal_content}"
        try:
            self.logger.debug(
                f"[DEBUG:HistoricalAgent:{proposal_id}] Invoking LLM for historical evaluation"
            )

            # ADDED: Image handling
            proposal_images_list = state.get("proposal_images", [])
            if not isinstance(proposal_images_list, list):
                self.logger.warning(
                    f"[DEBUG:HistoricalAgent:{proposal_id}] proposal_images is not a list: {type(proposal_images_list)}. Defaulting to empty list."
                )
                proposal_images_list = []

            message_content_list = [{"type": "text", "text": formatted_prompt_text}]
            if proposal_images_list:
                self.logger.debug(
                    f"[DEBUG:HistoricalAgent:{proposal_id}] Adding {len(proposal_images_list)} images to LLM input."
                )
                message_content_list.extend(proposal_images_list)

            llm_input_message = HumanMessage(content=message_content_list)

            result = await self.llm.with_structured_output(AgentOutput).ainvoke(
                [llm_input_message]
            )
            self.logger.info(
                f"[DEBUG:HistoricalAgent:{proposal_id}] SCORE={result.score}/100 | FLAGS={result.flags} | SUMMARY={result.summary}"
            )

            # Track token usage - extract directly from LLM if available
            token_usage_data = {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
            }

            # Try to extract token usage directly from LLM response
            if (
                hasattr(self.llm, "_last_prompt_id")
                and hasattr(self.llm, "client")
                and hasattr(self.llm.client, "usage_by_prompt_id")
            ):
                last_prompt_id = self.llm._last_prompt_id
                if last_prompt_id in self.llm.client.usage_by_prompt_id:
                    usage = self.llm.client.usage_by_prompt_id[last_prompt_id]
                    token_usage_data = {
                        "input_tokens": usage.get("prompt_tokens", 0),
                        "output_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0),
                    }
                    self.logger.debug(
                        f"[DEBUG:HistoricalAgent:{proposal_id}] Extracted token usage from LLM: {token_usage_data}"
                    )
            # Fallback to estimation
            if token_usage_data["total_tokens"] == 0:
                # Get model name from LLM
                llm_model_name = getattr(self.llm, "model_name", "gpt-4.1")
                # First calculate token count from the text
                token_count = len(formatted_prompt_text) // 4  # Simple estimation
                # Create token usage dictionary for calculate_token_cost
                token_usage_dict = {"input_tokens": token_count}
                # Calculate cost
                cost_result = calculate_token_cost(token_usage_dict, llm_model_name)
                token_usage_data = {
                    "input_tokens": token_count,
                    "output_tokens": len(result.model_dump_json())
                    // 4,  # rough estimate
                    "total_tokens": token_count + len(result.model_dump_json()) // 4,
                    "model_name": llm_model_name,  # Include model name
                }
                self.logger.debug(
                    f"[DEBUG:HistoricalAgent:{proposal_id}] Estimated token usage: {token_usage_data}"
                )

            # Add token usage to state
            if "token_usage" not in state:
                state["token_usage"] = {}
            state["token_usage"]["historical_agent"] = token_usage_data

            result_dict = result.model_dump()
            # Add token usage to result_dict so it's properly processed
            result_dict["token_usage"] = token_usage_data

            # Update state with the result
            update_state_with_agent_result(state, result_dict, "historical")
            return result_dict
        except Exception as e:
            self.logger.error(
                f"[DEBUG:HistoricalAgent:{proposal_id}] Error in historical evaluation: {str(e)}",
                exc_info=True,
            )
            fallback_score_dict = {
                "score": 50,
                "flags": [f"Error: {str(e)}"],
                "summary": "Evaluation failed due to error",
            }
            self.logger.info(
                f"[DEBUG:HistoricalAgent:{proposal_id}] ERROR_SCORE=50/100 | FLAGS=[{str(e)}] | SUMMARY=Evaluation failed"
            )
            return fallback_score_dict


class FinancialContextAgent(BaseCapabilityMixin):
    """Financial Context Agent evaluates treasury impact and financial viability."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config=config, state_key="financial_score")
        self.initialize()

    async def process(self, state: ProposalEvaluationState) -> Dict[str, Any]:
        proposal_id = state.get("proposal_id", "unknown")
        treasury_balance = state.get(
            "treasury_balance", self.config.get("treasury_balance", 1000000)
        )
        proposal_content = state.get("proposal_data", "")

        prompt = PromptTemplate(
            input_variables=["proposal_data", "treasury_balance"],
            template="""Assess the financial aspects of this proposal.\\n            
Proposal: {proposal_data}\\nCurrent Treasury Balance: {treasury_balance}\\n
Evaluate:\\n1. Cost-Benefit Analysis: Is the ROI reasonable?\\n2. Treasury Impact: What percentage of treasury would this use?\\n3. Budget Alignment: Does it align with budget priorities?\\n4. Projected Impact: What's the expected financial outcome?\\n5. Risk Assessment: What financial risks might arise?\\n
# ADDED: Image processing instructions
**Image Analysis Instructions:**
If images are provided with this proposal (they will appear after this text), you MUST analyze them as an integral part of the proposal.
- Relevance: Does each image directly relate to and support the proposal's text?
- Evidence: Do the images provide visual evidence for claims made in the proposal (e.g., screenshots of transactions, diagrams of financial models if applicable)?
- Authenticity & Quality: Are the images clear, authentic, and not misleading or manipulated?
- Cohesion: The images and text MUST form a cohesive and consistent whole. If any image contradicts the text, is irrelevant, misleading, of very poor quality, or inappropriate, you should consider this a significant flaw in the proposal.

Provide a score from 0-100, flag any critical issues (including image-related ones), and summarize your findings, explicitly mentioning your image analysis if images were present.\\
            """,
        )
        try:
            self.logger.debug(
                f"[DEBUG:FinancialAgent:{proposal_id}] Formatting prompt for financial evaluation"
            )
            formatted_prompt_text = prompt.format(
                proposal_data=proposal_content,
                treasury_balance=treasury_balance,
            )
        except Exception as e:
            self.logger.error(
                f"[DEBUG:FinancialAgent:{proposal_id}] Error formatting prompt: {str(e)}",
                exc_info=True,
            )
            formatted_prompt_text = (
                f"Assess financial aspects of proposal: {proposal_content}"
            )
        try:
            self.logger.debug(
                f"[DEBUG:FinancialAgent:{proposal_id}] Invoking LLM for financial evaluation"
            )

            # ADDED: Image handling
            proposal_images = state.get("proposal_images", [])
            message_content_list = [{"type": "text", "text": formatted_prompt_text}]
            if proposal_images:
                logger.debug(
                    f"[DEBUG:FinancialAgent:{proposal_id}] Adding {len(proposal_images)} images to LLM input."
                )
                message_content_list.extend(proposal_images)

            llm_input_message = HumanMessage(content=message_content_list)

            result = await self.llm.with_structured_output(AgentOutput).ainvoke(
                [llm_input_message]
            )
            self.logger.info(
                f"[DEBUG:FinancialAgent:{proposal_id}] SCORE={result.score}/100 | FLAGS={result.flags} | SUMMARY={result.summary}"
            )

            # Track token usage - extract directly from LLM if available
            token_usage_data = {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
            }

            # Try to extract token usage directly from LLM response
            if (
                hasattr(self.llm, "_last_prompt_id")
                and hasattr(self.llm, "client")
                and hasattr(self.llm.client, "usage_by_prompt_id")
            ):
                last_prompt_id = self.llm._last_prompt_id
                if last_prompt_id in self.llm.client.usage_by_prompt_id:
                    usage = self.llm.client.usage_by_prompt_id[last_prompt_id]
                    token_usage_data = {
                        "input_tokens": usage.get("prompt_tokens", 0),
                        "output_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0),
                    }
                    self.logger.debug(
                        f"[DEBUG:FinancialAgent:{proposal_id}] Extracted token usage from LLM: {token_usage_data}"
                    )
            # Fallback to estimation
            if token_usage_data["total_tokens"] == 0:
                # Get model name from LLM
                llm_model_name = getattr(self.llm, "model_name", "gpt-4.1")
                # First calculate token count from the text
                token_count = len(formatted_prompt_text) // 4  # Simple estimation
                # Create token usage dictionary for calculate_token_cost
                token_usage_dict = {"input_tokens": token_count}
                # Calculate cost
                cost_result = calculate_token_cost(token_usage_dict, llm_model_name)
                token_usage_data = {
                    "input_tokens": token_count,
                    "output_tokens": len(result.model_dump_json())
                    // 4,  # rough estimate
                    "total_tokens": token_count + len(result.model_dump_json()) // 4,
                    "model_name": llm_model_name,  # Include model name
                }
                self.logger.debug(
                    f"[DEBUG:FinancialAgent:{proposal_id}] Estimated token usage: {token_usage_data}"
                )

            # Add token usage to state
            if "token_usage" not in state:
                state["token_usage"] = {}
            state["token_usage"]["financial_agent"] = token_usage_data

            result_dict = result.model_dump()
            # Add token usage to result_dict so it's properly processed
            result_dict["token_usage"] = token_usage_data

            # Update state with the result
            update_state_with_agent_result(state, result_dict, "financial")
            return result_dict
        except Exception as e:
            self.logger.error(
                f"[DEBUG:FinancialAgent:{proposal_id}] Error in financial evaluation: {str(e)}",
                exc_info=True,
            )
            fallback_score_dict = {
                "score": 50,
                "flags": [f"Error: {str(e)}"],
                "summary": "Evaluation failed due to error",
            }
            self.logger.info(
                f"[DEBUG:FinancialAgent:{proposal_id}] ERROR_SCORE=50/100 | FLAGS=[{str(e)}] | SUMMARY=Evaluation failed"
            )
            return fallback_score_dict


class ImageProcessingNode(BaseCapabilityMixin):
    """A workflow node to process proposal images: extract URLs, download, and base64 encode."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config=config, state_key="proposal_images")
        self.initialize()

    async def process(self, state: ProposalEvaluationState) -> List[Dict[str, Any]]:
        """The core logic for processing images, returns the list of processed image dicts directly."""
        proposal_id = state.get("proposal_id", "unknown")
        proposal_data_str = state.get("proposal_data", "")

        if not proposal_data_str:
            self.logger.info(
                f"[ImageProcessorNode:{proposal_id}] No proposal_data string, skipping image processing."
            )
            return []  # Return empty list, not None

        self.logger.info(
            f"[ImageProcessorNode:{proposal_id}] Starting image processing."
        )
        image_urls = extract_image_urls(proposal_data_str)

        if not image_urls:
            self.logger.info(
                f"[ImageProcessorNode:{proposal_id}] No image URLs found in proposal data."
            )
            return []  # Return empty list, not None

        self.logger.info(
            f"[ImageProcessorNode:{proposal_id}] Found {len(image_urls)} image URLs: {image_urls}"
        )

        processed_images = []
        async with httpx.AsyncClient() as client:
            for url in image_urls:
                try:
                    self.logger.debug(
                        f"[ImageProcessorNode:{proposal_id}] Downloading image from {url}"
                    )
                    response = await client.get(url, timeout=10.0)
                    response.raise_for_status()
                    image_data = base64.b64encode(response.content).decode("utf-8")
                    mime_type = "image/jpeg"
                    if url.lower().endswith((".jpg", ".jpeg")):
                        mime_type = "image/jpeg"
                    elif url.lower().endswith(".png"):
                        mime_type = "image/png"
                    elif url.lower().endswith(".gif"):
                        mime_type = "image/gif"
                    elif url.lower().endswith(".webp"):
                        mime_type = "image/webp"

                    processed_images.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_data}"
                            },
                        }
                    )
                    self.logger.debug(
                        f"[ImageProcessorNode:{proposal_id}] Successfully processed image from {url}"
                    )
                except httpx.HTTPStatusError as e:
                    self.logger.error(
                        f"[ImageProcessorNode:{proposal_id}] HTTP error for {url}: {e.response.status_code}",
                        exc_info=False,
                    )
                except httpx.RequestError as e:
                    self.logger.error(
                        f"[ImageProcessorNode:{proposal_id}] Request error for {url}: {str(e)}",
                        exc_info=False,
                    )
                except Exception as e:
                    self.logger.error(
                        f"[ImageProcessorNode:{proposal_id}] Generic error for {url}: {str(e)}",
                        exc_info=True,
                    )

        self.logger.info(
            f"[ImageProcessorNode:{proposal_id}] Finished. {len(processed_images)} images processed."
        )
        return processed_images  # This will be a list, possibly empty


class SocialContextAgent(BaseCapabilityMixin, WebSearchCapability):
    """Social Context Agent gauges community sentiment and social impact."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        BaseCapabilityMixin.__init__(self, config=config, state_key="social_score")
        WebSearchCapability.__init__(self)
        self.initialize()
        self._initialize_web_search_capability()

    def _initialize_web_search_capability(self):
        if not hasattr(self, "search_web"):
            self.search_web = WebSearchCapability.search_web.__get__(
                self, self.__class__
            )
            self.logger.info("Initialized web search capability for SocialContextAgent")

    async def process(self, state: ProposalEvaluationState) -> Dict[str, Any]:
        proposal_id = state.get("proposal_id", "unknown")
        self._initialize_web_search_capability()
        proposal_content = state.get("proposal_data", "")

        social_context = ""
        if self.config.get("enable_web_search", True):
            try:
                search_query = (
                    f"Community sentiment {proposal_content[:50]} cryptocurrency DAO"
                )
                self.logger.debug(
                    f"[DEBUG:SocialAgent:{proposal_id}] Performing web search: {search_query}"
                )
                search_results, web_search_token_usage = await self.search_web(
                    query=search_query,
                    num_results=3,
                )
                social_context = "\n".join(
                    [f"{r.get('page_content', '')}" for r in search_results]
                )
                self.logger.debug(
                    f"[DEBUG:SocialAgent:{proposal_id}] Found {len(search_results)} web search results"
                )

                # Store web search token usage
                if "token_usage" not in state:
                    state["token_usage"] = {}
                state["token_usage"]["social_web_search"] = web_search_token_usage

            except Exception as e:
                logger.error(
                    f"[DEBUG:SocialAgent:{proposal_id}] Web search failed: {str(e)}",
                    exc_info=True,
                )
                social_context = "Web search unavailable."
        prompt = PromptTemplate(
            input_variables=["proposal_data", "social_context"],
            template="""Gauge the community sentiment and social impact of this proposal.\\n            
Proposal: {proposal_data}\\nSocial Context: {social_context}\\n
Evaluate:\\n1. Community Sentiment: How might members perceive this?\\n2. Social Media Presence: Any discussions online about this?\\n3. Engagement Potential: Will this engage the community?\\n4. Cross-Platform Analysis: How does sentiment vary across platforms?\\n5. Social Risk: Any potential for controversy or division?\\n
# ADDED: Image processing instructions
**Image Analysis Instructions:**
If images are provided with this proposal (they will appear after this text), you MUST analyze them as an integral part of the proposal.
- Relevance: Does each image directly relate to and support the proposal's text or the community/social aspects being discussed?
- Evidence: Do the images provide visual evidence for claims made (e.g., screenshots of community discussions, mockups of social impact visuals)?
- Authenticity & Quality: Are the images clear, authentic, and not misleading or manipulated?
- Cohesion: The images and text MUST form a cohesive and consistent whole. If any image contradicts the text, is irrelevant, misleading, of very poor quality, or inappropriate, you should consider this a significant flaw in the proposal.

Provide a score from 0-100, flag any critical issues (including image-related ones), and summarize your findings, explicitly mentioning your image analysis if images were present.\\
            """,
        )
        try:
            self.logger.debug(
                f"[DEBUG:SocialAgent:{proposal_id}] Formatting prompt for social evaluation"
            )
            formatted_prompt_text = prompt.format(
                proposal_data=proposal_content,
                social_context=social_context,
            )
        except Exception as e:
            self.logger.error(
                f"[DEBUG:SocialAgent:{proposal_id}] Error formatting prompt: {str(e)}",
                exc_info=True,
            )
            formatted_prompt_text = (
                f"Gauge social impact of proposal: {proposal_content}"
            )
        try:
            self.logger.debug(
                f"[DEBUG:SocialAgent:{proposal_id}] Invoking LLM for social evaluation"
            )

            # ADDED: Image handling
            proposal_images_list = state.get("proposal_images", [])
            if not isinstance(proposal_images_list, list):
                self.logger.warning(
                    f"[DEBUG:SocialAgent:{proposal_id}] proposal_images is not a list: {type(proposal_images_list)}. Defaulting to empty list."
                )
                proposal_images_list = []

            message_content_list = [{"type": "text", "text": formatted_prompt_text}]
            if proposal_images_list:
                self.logger.debug(
                    f"[DEBUG:SocialAgent:{proposal_id}] Adding {len(proposal_images_list)} images to LLM input."
                )
                message_content_list.extend(proposal_images_list)

            llm_input_message = HumanMessage(content=message_content_list)

            result = await self.llm.with_structured_output(AgentOutput).ainvoke(
                [llm_input_message]
            )
            self.logger.info(
                f"[DEBUG:SocialAgent:{proposal_id}] SCORE={result.score}/100 | FLAGS={result.flags} | SUMMARY={result.summary}"
            )

            # Track token usage - extract directly from LLM if available
            token_usage_data = {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
            }

            # Try to extract token usage directly from LLM response
            if (
                hasattr(self.llm, "_last_prompt_id")
                and hasattr(self.llm, "client")
                and hasattr(self.llm.client, "usage_by_prompt_id")
            ):
                last_prompt_id = self.llm._last_prompt_id
                if last_prompt_id in self.llm.client.usage_by_prompt_id:
                    usage = self.llm.client.usage_by_prompt_id[last_prompt_id]
                    token_usage_data = {
                        "input_tokens": usage.get("prompt_tokens", 0),
                        "output_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0),
                    }
                    self.logger.debug(
                        f"[DEBUG:SocialAgent:{proposal_id}] Extracted token usage from LLM: {token_usage_data}"
                    )
            # Fallback to estimation
            if token_usage_data["total_tokens"] == 0:
                # Get model name from LLM
                llm_model_name = getattr(self.llm, "model_name", "gpt-4.1")
                # First calculate token count from the text
                token_count = len(formatted_prompt_text) // 4  # Simple estimation
                # Create token usage dictionary for calculate_token_cost
                token_usage_dict = {"input_tokens": token_count}
                # Calculate cost
                cost_result = calculate_token_cost(token_usage_dict, llm_model_name)
                token_usage_data = {
                    "input_tokens": token_count,
                    "output_tokens": len(result.model_dump_json())
                    // 4,  # rough estimate
                    "total_tokens": token_count + len(result.model_dump_json()) // 4,
                    "model_name": llm_model_name,  # Include model name
                }
                self.logger.debug(
                    f"[DEBUG:SocialAgent:{proposal_id}] Estimated token usage: {token_usage_data}"
                )

            # Add token usage to state
            if "token_usage" not in state:
                state["token_usage"] = {}
            state["token_usage"]["social_agent"] = token_usage_data

            result_dict = result.model_dump()
            # Add token usage to result_dict so it's properly processed
            result_dict["token_usage"] = token_usage_data

            # Update state with the result
            update_state_with_agent_result(state, result_dict, "social")
            return result_dict
        except Exception as e:
            self.logger.error(
                f"[DEBUG:SocialAgent:{proposal_id}] Error in social evaluation: {str(e)}",
                exc_info=True,
            )
            fallback_score_dict = {
                "score": 50,
                "flags": [f"Error: {str(e)}"],
                "summary": "Evaluation failed due to error",
            }
            self.logger.info(
                f"[DEBUG:SocialAgent:{proposal_id}] ERROR_SCORE=50/100 | FLAGS=[{str(e)}] | SUMMARY=Evaluation failed"
            )
            return fallback_score_dict


class ReasoningAgent(BaseCapabilityMixin, PlanningCapability):
    """Configuration & Reasoning Agent synthesizes evaluations and makes decisions."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Reasoning Agent."""
        BaseCapabilityMixin.__init__(self, config=config, state_key="final_score")
        self.initialize()
        planning_queue = asyncio.Queue()
        callback_handler = self.config.get(
            "callback_handler"
        ) or StreamingCallbackHandler(planning_queue)
        PlanningCapability.__init__(
            self,
            callback_handler=callback_handler,
            planning_llm=ChatOpenAI(
                model=self.config.get("planning_model", "gpt-4.1-mini")
            ),
            persona="DAO Proposal Evaluator",
        )
        self._initialize_planning_capability()

    def _initialize_planning_capability(self):
        """Initialize planning capability methods."""
        if not hasattr(self, "create_plan"):
            self.create_plan = PlanningCapability.create_plan.__get__(
                self, self.__class__
            )
            self.logger.info("Initialized planning capability for ReasoningAgent")

    def integrate_with_graph(self, graph: StateGraph, **kwargs) -> None:
        """Integrate planning capability with the graph."""
        pass

    async def process(self, state: ProposalEvaluationState) -> Dict[str, Any]:
        proposal_id = state.get("proposal_id", "unknown")
        self._initialize_planning_capability()
        proposal_content = state.get("proposal_data", "")
        self.logger.debug(
            f"[DEBUG:ReasoningAgent:{proposal_id}] Beginning final evaluation processing with proposal_content (length: {len(proposal_content)})"
        )

        def safe_get_score(value, default=0):
            if isinstance(value, dict) and "score" in value:
                return value.get("score", default)
            elif isinstance(value, int):
                return value
            return default

        core_score = state.get("core_score", {})
        historical_score = state.get("historical_score", {})
        financial_score = state.get("financial_score", {})
        social_score = state.get("social_score", {})

        core_score_val = safe_get_score(core_score)
        historical_score_val = safe_get_score(historical_score)
        financial_score_val = safe_get_score(financial_score)
        social_score_val = safe_get_score(social_score)

        self.logger.debug(
            f"[DEBUG:ReasoningAgent:{proposal_id}] Input scores: Core={core_score_val}, Historical={historical_score_val}, Financial={financial_score_val}, Social={social_score_val}"
        )

        scores = {
            "Core Context": core_score_val,
            "Historical Context": historical_score_val,
            "Financial Context": financial_score_val,
            "Social Context": social_score_val,
        }
        summaries = state.get("summaries", {})
        flags = state.get("flags", [])

        self.logger.debug(
            f"[DEBUG:ReasoningAgent:{proposal_id}] Summaries: {summaries}"
        )

        self.logger.debug(f"[DEBUG:ReasoningAgent:{proposal_id}] Flags raised: {flags}")

        # Update the summaries with the content from each agent's evaluation
        if isinstance(core_score, dict) and "summary" in core_score:
            summaries["core_score"] = core_score["summary"]
        if isinstance(historical_score, dict) and "summary" in historical_score:
            summaries["historical_score"] = historical_score["summary"]
        if isinstance(financial_score, dict) and "summary" in financial_score:
            summaries["financial_score"] = financial_score["summary"]
        if isinstance(social_score, dict) and "summary" in social_score:
            summaries["social_score"] = social_score["summary"]

        # Update flags
        for score_obj in [core_score, historical_score, financial_score, social_score]:
            if (
                isinstance(score_obj, dict)
                and "flags" in score_obj
                and isinstance(score_obj["flags"], list)
            ):
                flags.extend(score_obj["flags"])

        prompt = PromptTemplate(
            input_variables=["proposal_data", "scores", "summaries", "flags"],
            template="""Synthesize all evaluations and make a final decision on this proposal.\\n            
Proposal: {proposal_data}\\n
Evaluations:\\n- Core Context (Score: {scores[Core Context]}): {summaries[core_score]}\\n- Historical Context (Score: {scores[Historical Context]}): {summaries[historical_score]}\\n- Financial Context (Score: {scores[Financial Context]}): {summaries[financial_score]}\\n- Social Context (Score: {scores[Social Context]}): {summaries[social_score]}\\n
Flags Raised: {flags}\\n
Synthesize these evaluations to:\\n1. Weigh the importance of each context\\n2. Calibrate confidence based on available information\\n3. Consider the implications of the flags raised\\n4. Make a final decision: Approve or Reject\\n5. Calculate an overall score\\n
Provide a final score, decision (Approve/Reject), and detailed explanation.\\n            
            """,
        )

        try:
            for key in [
                "core_score",
                "historical_score",
                "financial_score",
                "social_score",
            ]:
                if key not in summaries:
                    summaries[key] = "No evaluation available"

            self.logger.debug(
                f"[DEBUG:ReasoningAgent:{proposal_id}] Formatting final evaluation prompt"
            )
            formatted_prompt_text = prompt.format(
                proposal_data=proposal_content,
                scores=scores,
                summaries=summaries,
                flags=", ".join(flags) if flags else "None",
            )
        except Exception as e:
            self.logger.error(
                f"[DEBUG:ReasoningAgent:{proposal_id}] Error formatting prompt: {str(e)}",
                exc_info=True,
            )
            formatted_prompt_text = f"""Synthesize evaluations for proposal: {proposal_content}
Scores: {scores}
Flags: {flags}
Provide a final score, decision (Approve/Reject), and explanation."""

        try:
            self.logger.debug(
                f"[DEBUG:ReasoningAgent:{proposal_id}] Invoking LLM for final decision"
            )
            result = await self.llm.with_structured_output(FinalOutput).ainvoke(
                [formatted_prompt_text]
            )

            self.logger.info(
                f"[DEBUG:ReasoningAgent:{proposal_id}] FINAL DECISION: {result.decision} | SCORE={result.score}/100 | EXPLANATION={result.explanation}"
            )

            # Track token usage - extract directly from LLM if available
            token_usage_data = {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
            }

            # Try to extract token usage directly from LLM response
            if (
                hasattr(self.llm, "_last_prompt_id")
                and hasattr(self.llm, "client")
                and hasattr(self.llm.client, "usage_by_prompt_id")
            ):
                last_prompt_id = self.llm._last_prompt_id
                if last_prompt_id in self.llm.client.usage_by_prompt_id:
                    usage = self.llm.client.usage_by_prompt_id[last_prompt_id]
                    token_usage_data = {
                        "input_tokens": usage.get("prompt_tokens", 0),
                        "output_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0),
                    }
                    self.logger.debug(
                        f"[DEBUG:ReasoningAgent:{proposal_id}] Extracted token usage from LLM: {token_usage_data}"
                    )
            # Fallback to estimation
            if token_usage_data["total_tokens"] == 0:
                # Get model name from LLM
                llm_model_name = getattr(self.llm, "model_name", "gpt-4.1")
                # First calculate token count from the text
                token_count = len(formatted_prompt_text) // 4  # Simple estimation
                # Create token usage dictionary for calculate_token_cost
                token_usage_dict = {"input_tokens": token_count}
                # Calculate cost
                cost_result = calculate_token_cost(token_usage_dict, llm_model_name)
                token_usage_data = {
                    "input_tokens": token_count,
                    "output_tokens": len(result.model_dump_json())
                    // 4,  # rough estimate
                    "total_tokens": token_count + len(result.model_dump_json()) // 4,
                    "model_name": llm_model_name,  # Include model name
                }
                self.logger.debug(
                    f"[DEBUG:ReasoningAgent:{proposal_id}] Estimated token usage: {token_usage_data}"
                )

            # Add token usage to state
            if "token_usage" not in state:
                state["token_usage"] = {}
            state["token_usage"]["reasoning_agent"] = token_usage_data

            result_dict = result.model_dump()
            # Add token usage to result_dict so it's properly processed
            result_dict["token_usage"] = token_usage_data

            # Update state with the result
            update_state_with_agent_result(state, result_dict, "reasoning")
            return result_dict
        except Exception as e:
            self.logger.error(
                f"[DEBUG:ReasoningAgent:{proposal_id}] Error in final evaluation: {str(e)}",
                exc_info=True,
            )
            self.logger.info(
                f"[DEBUG:ReasoningAgent:{proposal_id}] ERROR_SCORE=50/100 | DECISION=Pending | REASON=Error: {str(e)}"
            )
            return {
                "score": 50,
                "decision": "Pending",
                "explanation": f"Unable to make final decision due to error: {str(e)}",
            }


class ProposalEvaluationWorkflow(BaseWorkflow[ProposalEvaluationState]):
    """Main workflow for evaluating DAO proposals using a hierarchical team."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the proposal evaluation workflow."""
        super().__init__()
        self.config = config or {}
        self.hierarchical_workflow = HierarchicalTeamWorkflow(
            name="ProposalEvaluation",
            config={
                "state_type": ProposalEvaluationState,
                "recursion_limit": self.config.get("recursion_limit", 20),
            },
        )

        # Instantiate and add the new ImageProcessingNode
        image_processor_agent = ImageProcessingNode(
            config=self.config
        )  # Use self.config
        self.hierarchical_workflow.add_sub_workflow(
            "image_processor", image_processor_agent
        )

        core_agent = CoreContextAgent(self.config)
        historical_agent = HistoricalContextAgent(self.config)
        financial_agent = FinancialContextAgent(self.config)
        social_agent = SocialContextAgent(self.config)
        reasoning_agent = ReasoningAgent(self.config)

        self.hierarchical_workflow.add_sub_workflow("core_agent", core_agent)
        self.hierarchical_workflow.add_sub_workflow(
            "historical_agent", historical_agent
        )
        self.hierarchical_workflow.add_sub_workflow("financial_agent", financial_agent)
        self.hierarchical_workflow.add_sub_workflow("social_agent", social_agent)
        self.hierarchical_workflow.add_sub_workflow("reasoning_agent", reasoning_agent)

        self.hierarchical_workflow.set_entry_point("image_processor")

        def supervisor_logic(state: ProposalEvaluationState) -> Union[str, List[str]]:
            """Determine the next step in the workflow."""
            proposal_id = state.get("proposal_id", "unknown")

            # Debugging current state view for supervisor
            logger.debug(
                f"[DEBUG:Supervisor:{proposal_id}] Evaluating next step. State keys: {list(state.keys())}. "
                f"proposal_images set: {'proposal_images' in state}, "
                f"core_score set: {state.get('core_score') is not None}, "
                f"historical_score set: {state.get('historical_score') is not None}, "
                f"financial_score set: {state.get('financial_score') is not None}, "
                f"social_score set: {state.get('social_score') is not None}, "
                f"final_score set: {state.get('final_score') is not None}"
            )

            if state.get("halt", False):
                logger.debug(
                    f"[DEBUG:Supervisor:{proposal_id}] Halt condition met, returning END"
                )
                return END

            # After image_processor (entry point), if core_score isn't set, go to core_agent.
            # The image_processor node output (even if empty list for images) should be in state.
            if state.get("core_score") is None:
                # This will be the first check after image_processor completes as it's the entry point.
                current_core_invocations = state.get("core_agent_invocations", 0)
                if current_core_invocations > 3:
                    logger.error(
                        f"[DEBUG:Supervisor:{proposal_id}] Core agent invoked too many times ({current_core_invocations}), halting."
                    )
                    return END

                # Do not manually increment core_agent_invocations - the langgraph framework will handle this
                # with the Annotated type we restored

                logger.debug(
                    f"[DEBUG:Supervisor:{proposal_id}] Routing to core_agent (core_score is None, invocation #{current_core_invocations})."
                )
                return "core_agent"

            if state.get("historical_score") is None:
                logger.debug(
                    f"[DEBUG:Supervisor:{proposal_id}] Routing to historical_agent."
                )
                return "historical_agent"

            if (
                state.get("financial_score") is None
                or state.get("social_score") is None
            ):
                parallel_nodes = []
                if state.get("financial_score") is None:
                    parallel_nodes.append("financial_agent")
                if state.get("social_score") is None:
                    parallel_nodes.append("social_agent")
                logger.debug(
                    f"[DEBUG:Supervisor:{proposal_id}] Initiating parallel execution of {parallel_nodes}"
                )
                return parallel_nodes

            if state.get("final_score") is None:
                logger.debug(
                    f"[DEBUG:Supervisor:{proposal_id}] All scores available but final score is None, routing to reasoning_agent"
                )
                return "reasoning_agent"

            logger.debug(
                f"[DEBUG:Supervisor:{proposal_id}] All scores completed, returning END"
            )
            return END

        self.hierarchical_workflow.set_supervisor_logic(supervisor_logic)

        def halt_condition(state: ProposalEvaluationState) -> bool:
            """Check if workflow should halt."""
            proposal_id = state.get("proposal_id", "unknown")

            if state.get("halt", False):
                logger.debug(
                    f"[DEBUG:HaltCondition:{proposal_id}] Halting workflow due to explicit halt flag"
                )
                return True

            # Check for excessive core agent invocations
            if state.get("core_agent_invocations", 0) > 3:
                logger.debug(
                    f"[DEBUG:HaltCondition:{proposal_id}] Halting workflow due to excessive core agent invocations: {state.get('core_agent_invocations', 0)}"
                )
                return True

            recursion_count = state.get("recursion_count", 0)
            if recursion_count > 8:
                logger.debug(
                    f"[DEBUG:HaltCondition:{proposal_id}] Halting workflow - possible loop detected after {recursion_count} iterations"
                )
                return True

            if (
                state.get("core_score") is not None
                and state.get("historical_score") is not None
                and state.get("financial_score") is not None
                and state.get("social_score") is not None
                and state.get("final_score") is None
                and recursion_count > 3
            ):
                logger.debug(
                    f"[DEBUG:HaltCondition:{proposal_id}] Halting workflow - reasoning agent appears to be failing after {recursion_count} attempts"
                )
                return True

            state["recursion_count"] = recursion_count + 1
            logger.debug(
                f"[DEBUG:HaltCondition:{proposal_id}] Incrementing recursion counter to {state['recursion_count']}"
            )

            return False

        self.hierarchical_workflow.set_halt_condition(halt_condition)
        self.required_fields = ["proposal_id", "proposal_data"]

    def _create_prompt(self) -> PromptTemplate:
        """Create the main workflow prompt."""
        return PromptTemplate(
            input_variables=["proposal_data"],
            template="Evaluate the DAO proposal: {proposal_data}",
        )

    def _create_graph(self) -> StateGraph:
        """Create the workflow graph."""
        return self.hierarchical_workflow.build_graph()

    def _validate_state(self, state: ProposalEvaluationState) -> bool:
        """Validate the workflow state."""
        if not super()._validate_state(state):
            return False

        if "flags" not in state:
            state["flags"] = []
        elif state["flags"] is None:
            state["flags"] = []

        if "summaries" not in state:
            state["summaries"] = {}
        elif state["summaries"] is None:
            state["summaries"] = {}

        if "halt" not in state:
            state["halt"] = False

        if "token_usage" not in state:
            state["token_usage"] = {}
        elif state["token_usage"] is None:
            state["token_usage"] = {}

        return True


async def evaluate_proposal(
    proposal_id: str,
    proposal_data: str,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Evaluate a proposal using the hierarchical team workflow."""
    logger.info(f"[DEBUG:Workflow:{proposal_id}] Starting evaluation workflow")

    debug_level = 0
    if config and "debug_level" in config:
        debug_level = config.get("debug_level", 0)
        if debug_level > 0:
            logger.debug(f"[PROPOSAL_DEBUG] Using debug_level: {debug_level}")

    if not proposal_data:
        logger.warning(
            f"[PROPOSAL_DEBUG] proposal_data is empty or None! This will cause evaluation failure."
        )

    state = {
        "proposal_id": proposal_id,
        "proposal_data": proposal_data,
        "flags": [],
        "summaries": {},
        "halt": False,
        "token_usage": {},
        "core_score": None,
        "historical_score": None,
        "financial_score": None,
        "social_score": None,
        "final_score": None,
        "decision": None,
        "core_agent_invocations": 0,
        "recursion_count": 0,
    }

    try:
        workflow = ProposalEvaluationWorkflow(config or {})
        logger.info(
            f"[DEBUG:Workflow:{proposal_id}] Executing hierarchical team workflow"
        )
        result = await workflow.execute(state)
        logger.info(
            f"[DEBUG:Workflow:{proposal_id}] Workflow execution completed with decision: {result.get('decision', 'Unknown')}"
        )

        # Only output detailed debug info at higher debug levels
        if debug_level >= 2:
            logger.debug(
                f"[DEBUG:Workflow:{proposal_id}] RESULT STRUCTURE: {list(result.keys())}"
            )
            logger.debug(f"[DEBUG:Workflow:{proposal_id}] RESULT SCORES TYPES:")
            logger.debug(
                f"[DEBUG:Workflow:{proposal_id}] - Core: {type(result.get('core_score'))} = {repr(result.get('core_score'))[:100]+'...' if len(repr(result.get('core_score'))) > 100 else repr(result.get('core_score'))}"
            )
            logger.debug(
                f"[DEBUG:Workflow:{proposal_id}] - Historical: {type(result.get('historical_score'))} = {repr(result.get('historical_score'))[:100]+'...' if len(repr(result.get('historical_score'))) > 100 else repr(result.get('historical_score'))}"
            )
            logger.debug(
                f"[DEBUG:Workflow:{proposal_id}] - Financial: {type(result.get('financial_score'))} = {repr(result.get('financial_score'))[:100]+'...' if len(repr(result.get('financial_score'))) > 100 else repr(result.get('financial_score'))}"
            )
            logger.debug(
                f"[DEBUG:Workflow:{proposal_id}] - Social: {type(result.get('social_score'))} = {repr(result.get('social_score'))[:100]+'...' if len(repr(result.get('social_score'))) > 100 else repr(result.get('social_score'))}"
            )
            logger.debug(
                f"[DEBUG:Workflow:{proposal_id}] - Final: {type(result.get('final_score'))} = {repr(result.get('final_score'))[:100]+'...' if len(repr(result.get('final_score'))) > 100 else repr(result.get('final_score'))}"
            )
            logger.debug(
                f"[DEBUG:Workflow:{proposal_id}] - Decision: {type(result.get('decision'))} = {repr(result.get('decision'))}"
            )

        if result is None:
            logger.error(
                f"[DEBUG:Workflow:{proposal_id}] Workflow returned None result, using default values"
            )
            return {
                "proposal_id": proposal_id,
                "score": 0,
                "decision": "Error",
                "explanation": "Evaluation failed: Workflow returned empty result",
                "component_scores": {
                    "core": 0,
                    "historical": 0,
                    "financial": 0,
                    "social": 0,
                },
                "flags": ["Workflow error: Empty result"],
                "token_usage": {},
            }

        def safe_extract_score(value, default=0):
            if isinstance(value, dict) and "score" in value:
                return value.get("score", default)
            elif isinstance(value, int):
                return value
            elif isinstance(value, str):
                try:
                    return int(value)
                except ValueError:
                    pass  # If string is not int, will fall through to default
            return default

        final_score_val = result.get("final_score")
        final_score_dict = {}
        if isinstance(final_score_val, dict):
            final_score_dict = final_score_val

        component_scores = {
            "core": safe_extract_score(result.get("core_score")),
            "historical": safe_extract_score(result.get("historical_score")),
            "financial": safe_extract_score(result.get("financial_score")),
            "social": safe_extract_score(result.get("social_score")),
        }

        # This is a useful log to keep even at lower debug levels
        logger.debug(
            f"[DEBUG:Workflow:{proposal_id}] EXTRACTED COMPONENT SCORES: {component_scores}"
        )

        explanation = ""
        if isinstance(final_score_dict, dict) and "explanation" in final_score_dict:
            explanation = final_score_dict.get("explanation", "")
        elif isinstance(final_score_val, str):
            explanation = final_score_val

        # Log the explanation to help debug
        logger.debug(
            f"[DEBUG:Workflow:{proposal_id}] Explanation extracted: {explanation[:100]}..."
        )

        final_score = 0
        if isinstance(final_score_dict, dict) and "score" in final_score_dict:
            final_score = final_score_dict.get("score", 0)
        else:
            final_score = safe_extract_score(final_score_val)

        decision = result.get("decision")
        if decision is None:
            if isinstance(final_score_dict, dict) and "decision" in final_score_dict:
                decision = final_score_dict.get("decision")
            else:
                decision = "Reject"

        logger.debug(
            f"[DEBUG:Workflow:{proposal_id}] Final decision: {decision}, score: {final_score}"
        )

        total_token_usage = result.get("token_usage", {})
        total_input_tokens = 0
        total_output_tokens = 0
        total_tokens = 0

        # Aggregate tokens from all agent steps
        # Assuming model_name is consistent across all steps for this aggregation, or we use the primary model_name
        # If each agent could use a different model, this would need more detailed per-model tracking
        logger.debug(f"Token usage entries in result: {list(total_token_usage.keys())}")
        for agent_key, usage_data in total_token_usage.items():
            if isinstance(usage_data, dict):
                total_input_tokens += usage_data.get("input_tokens", 0)
                total_output_tokens += usage_data.get("output_tokens", 0)
                total_tokens += usage_data.get("total_tokens", 0)
                logger.debug(f"Token usage for {agent_key}: {usage_data}")
            else:
                logger.warning(
                    f"Unexpected format for token_usage data for agent {agent_key}: {usage_data}"
                )

        # Extract component summaries for detailed reporting
        component_summaries = {}
        if isinstance(result.get("summaries"), dict):
            component_summaries = result.get("summaries")

        # Extract and aggregate flags
        all_flags = result.get("flags", [])
        if not isinstance(all_flags, list):
            all_flags = []

        # Placeholder for web search specific token usage if it were tracked separately
        # In the original, these seemed to be fixed placeholders.
        web_search_input_tokens = 0
        web_search_output_tokens = 0
        web_search_total_tokens = 0

        # Initialize total token usage by model
        total_token_usage_by_model = {}

        # Extract token usage by model from token_usage data
        for agent_name, agent_usage in total_token_usage.items():
            if isinstance(agent_usage, dict) and agent_usage.get("total_tokens", 0) > 0:
                # Get model name from config, or use default
                model_name = config.get(
                    "model_name", "gpt-4.1"
                )  # Use configured model name

                # Extract model name from each agent usage if available
                # This would require each agent to include model info in their token usage
                if "model_name" in agent_usage:
                    model_name = agent_usage["model_name"]

                # Initialize the model entry if needed
                if model_name not in total_token_usage_by_model:
                    total_token_usage_by_model[model_name] = {
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "total_tokens": 0,
                    }

                # Add token usage for this agent to the model's tally
                total_token_usage_by_model[model_name][
                    "input_tokens"
                ] += agent_usage.get("input_tokens", 0)
                total_token_usage_by_model[model_name][
                    "output_tokens"
                ] += agent_usage.get("output_tokens", 0)
                total_token_usage_by_model[model_name][
                    "total_tokens"
                ] += agent_usage.get("total_tokens", 0)

        # Fallback if no token usage was recorded
        if not total_token_usage_by_model:
            total_token_usage_by_model["gpt-4.1"] = {
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "total_tokens": total_tokens,
            }

        # Improved cost calculation by model
        cost_per_thousand = {
            "gpt-4.1": 0.01,  # $0.01 per 1K tokens
            "gpt-4.1-mini": 0.005,  # $0.005 per 1K tokens
            "gpt-4.1-32k": 0.03,  # $0.03 per 1K tokens
            "gpt-4": 0.03,  # $0.03 per 1K tokens
            "gpt-4-32k": 0.06,  # $0.06 per 1K tokens
            "gpt-3.5-turbo": 0.0015,  # $0.0015 per 1K tokens
            "default": 0.01,  # default fallback
        }

        # Calculate costs for each model
        total_cost_by_model = {}
        total_overall_cost = 0.0
        for model_name, usage in total_token_usage_by_model.items():
            # Get cost per 1K tokens for this model
            model_cost_per_k = cost_per_thousand.get(
                model_name, cost_per_thousand["default"]
            )
            # Calculate cost for this model's usage
            model_cost = usage["total_tokens"] * (model_cost_per_k / 1000)
            total_cost_by_model[model_name] = model_cost
            total_overall_cost += model_cost

        if not total_cost_by_model:
            # Fallback if no models were recorded
            model_name = "gpt-4.1"  # Default model name
            total_cost_by_model[model_name] = total_tokens * (
                cost_per_thousand["default"] / 1000
            )
            total_overall_cost = total_cost_by_model[model_name]

        final_result = {
            "success": True,
            "evaluation": {
                "approve": decision == "Approve",
                "confidence_score": final_score / 100.0 if final_score else 0.0,
                "reasoning": explanation,
            },
            "decision": decision,
            "score": final_score,
            "explanation": explanation,
            "component_scores": component_scores,
            "component_summaries": component_summaries,  # Include component summaries
            "flags": all_flags,
            "token_usage": total_token_usage,  # Include all token usage details
            "web_search_results": [],
            "treasury_balance": None,
            "web_search_token_usage": {
                "input_tokens": web_search_input_tokens,
                "output_tokens": web_search_output_tokens,
                "total_tokens": web_search_total_tokens,
            },
            "evaluation_token_usage": {
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "total_tokens": total_tokens,
            },
            "evaluation_model_info": {
                "name": config.get("model_name", "gpt-4.1"),
                "temperature": config.get("temperature", 0.1),
            },
            "web_search_model_info": {
                "name": config.get("model_name", "gpt-4.1"),
                "temperature": config.get("temperature", 0.1),
            },
            "total_token_usage_by_model": total_token_usage_by_model,
            "total_cost_by_model": total_cost_by_model,
            "total_overall_cost": total_overall_cost,
        }

        logger.debug(
            f"Proposal evaluation completed: Success={final_result['success']} | Decision={'APPROVE' if decision == 'Approve' else 'REJECT'} | Confidence={final_result['evaluation']['confidence_score']:.2f} | Auto-voted={decision == 'Approve'}"
        )
        return final_result
    except Exception as e:
        logger.error(f"Error in workflow execution: {str(e)}", exc_info=True)
        return {
            "proposal_id": proposal_id,
            "score": 0,
            "decision": "Error",
            "explanation": f"Evaluation failed: {str(e)}",
            "component_scores": {
                "core": 0,
                "historical": 0,
                "financial": 0,
                "social": 0,
            },
            "flags": [f"Workflow error: {str(e)}"],
            "token_usage": {},
        }


def get_proposal_evaluation_tools(
    profile: Optional[Profile] = None, agent_id: Optional[UUID] = None
):
    """Get the tools needed for proposal evaluation."""
    all_tools = initialize_tools(profile=profile, agent_id=agent_id)
    logger.debug(f"Available tools: {', '.join(all_tools.keys())}")
    required_tools = [
        "dao_action_get_proposal",
        "dao_action_vote_on_proposal",
        "dao_action_get_voting_power",
        "dao_action_get_voting_configuration",
        "database_get_dao_get_by_name",
        "dao_search",
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
    debug_level: int = 0,  # 0=normal, 1=verbose, 2=very verbose
) -> Dict:
    """Evaluate a proposal and automatically vote based on the evaluation."""
    logger.debug(
        f"Starting proposal evaluation: proposal_id={proposal_id} | auto_vote={auto_vote} | confidence_threshold={confidence_threshold} | debug_level={debug_level}"
    )
    try:
        effective_agent_id = agent_id
        if not effective_agent_id and wallet_id:
            wallet = backend.get_wallet(wallet_id)
            if wallet and wallet.agent_id:
                effective_agent_id = wallet.agent_id
                logger.debug(
                    f"Using agent ID {effective_agent_id} from wallet {wallet_id}"
                )

        model_name = "gpt-4.1"
        temperature = 0.1
        if effective_agent_id:
            try:
                prompts = backend.list_prompts(
                    PromptFilter(
                        agent_id=effective_agent_id,
                        dao_id=dao_id,
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
                        f"No active prompts found for agent {effective_agent_id}."
                    )
            except Exception as e:
                logger.error(
                    f"Failed to get agent prompt settings: {str(e)}", exc_info=True
                )

        logger.debug(
            f"[PROPOSAL_DEBUG] Fetching proposal data from backend for ID: {proposal_id}"
        )
        proposal_data = backend.get_proposal(proposal_id)
        if not proposal_data:
            logger.error(
                f"[PROPOSAL_DEBUG] No proposal data found for ID: {proposal_id}"
            )
            raise ValueError(f"Proposal {proposal_id} not found")

        logger.debug(f"[PROPOSAL_DEBUG] Raw proposal data: {proposal_data}")

        proposal_content = proposal_data.parameters or ""
        if not proposal_content:
            logger.warning(f"[PROPOSAL_DEBUG] Proposal parameters/content is empty!")

        config = {
            "model_name": model_name,
            "temperature": temperature,
            "mission_collection": "knowledge_collection",
            "proposals_collection": "proposals",
            "enable_web_search": True,
            "planning_model": "gpt-4.1-mini",
        }

        if debug_level > 0:
            config["debug_level"] = debug_level
            logger.debug(f"[PROPOSAL_DEBUG] Setting debug_level to {debug_level}")

        if not dao_id and proposal_data.dao_id:
            dao_id = proposal_data.dao_id
        dao_info = None
        if dao_id:
            dao_info = backend.get_dao(dao_id)
            if dao_info:
                config["dao_mission"] = dao_info.mission

        treasury_balance = None
        try:
            if dao_id:
                treasury_extensions = backend.list_extensions(
                    ExtensionFilter(dao_id=dao_id, type="EXTENSIONS_TREASURY")
                )
                if treasury_extensions:
                    hiro_api = HiroApi()
                    treasury_balance = hiro_api.get_address_balance(
                        treasury_extensions[0].contract_principal
                    )
        except Exception as e:
            logger.error(f"Failed to get treasury balance: {str(e)}", exc_info=True)

        logger.debug("Starting hierarchical evaluation workflow...")
        eval_result = await evaluate_proposal(
            proposal_id=str(proposal_id),
            proposal_data=proposal_data.parameters,
            config=config,
        )

        decision = eval_result.get("decision")
        if decision is None:
            decision = "Reject"
            logger.warning(
                f"No decision found in evaluation results, defaulting to '{decision}'"
            )

        score = eval_result.get("score", 0)
        confidence_score = score / 100.0 if score else 0.0

        approve = False
        if isinstance(decision, str) and decision.lower() == "approve":
            approve = True

        should_vote = auto_vote and confidence_score >= confidence_threshold

        vote_result = None
        tx_id = None
        if should_vote and wallet_id:
            try:
                vote_tool = VoteOnActionProposalTool(wallet_id=wallet_id)
                if proposal_data.type == ProposalType.ACTION:
                    contract_info = proposal_data.contract_principal
                    if "." in contract_info:
                        parts = contract_info.split(".")
                        if len(parts) >= 2:
                            action_proposals_contract = parts[0]
                            action_proposals_voting_extension = parts[1]
                            result = await vote_tool.vote_on_proposal(
                                contract_principal=action_proposals_contract,
                                extension_name=action_proposals_voting_extension,
                                proposal_id=proposal_data.proposal_id,
                                vote=approve,
                            )
                            vote_result = {
                                "success": result is not None,
                                "output": result,
                            }
                            if (
                                result
                                and isinstance(result, str)
                                and "txid:" in result.lower()
                            ):
                                for line in result.split("\n"):
                                    if "txid:" in line.lower():
                                        parts = line.split(":")
                                        if len(parts) > 1:
                                            tx_id = parts[1].strip()
                                            break
                    else:
                        logger.warning(
                            f"Invalid contract principal format: {contract_info}"
                        )
                else:
                    logger.warning(
                        f"Cannot vote on non-action proposal type: {proposal_data.type}"
                    )
            except Exception as e:
                logger.error(f"Error executing vote: {str(e)}", exc_info=True)
                vote_result = {
                    "success": False,
                    "error": f"Error during voting: {str(e)}",
                }
        elif not should_vote:
            vote_result = {
                "success": True,
                "message": "Voting skipped due to confidence threshold or auto_vote setting",
                "data": None,
            }

        # Get token usage data from eval_result
        total_token_usage = eval_result.get("token_usage", {})
        total_input_tokens = 0
        total_output_tokens = 0
        total_tokens = 0

        # Aggregate tokens from all agent steps - no need to log duplicates here
        for agent_key, usage_data in total_token_usage.items():
            if isinstance(usage_data, dict):
                total_input_tokens += usage_data.get("input_tokens", 0)
                total_output_tokens += usage_data.get("output_tokens", 0)
                total_tokens += usage_data.get("total_tokens", 0)

        # Initialize total_token_usage_by_model using data from eval_result
        total_token_usage_by_model = eval_result.get("total_token_usage_by_model", {})
        if not total_token_usage_by_model:
            # Use the default model name from settings or default to gpt-4.1
            default_model = model_name or "gpt-4.1"
            # Add total token counts to the model
            total_token_usage_by_model[default_model] = {
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "total_tokens": total_tokens,
            }

        # Get cost calculations from eval_result if available
        total_cost_by_model = eval_result.get("total_cost_by_model", {})
        total_overall_cost = eval_result.get("total_overall_cost", 0.0)

        # If cost data is missing, calculate it
        if not total_cost_by_model:
            # Improved cost calculation by model
            cost_per_thousand = {
                "gpt-4.1": 0.01,  # $0.01 per 1K tokens
                "gpt-4.1-mini": 0.005,  # $0.005 per 1K tokens
                "gpt-4.1-32k": 0.03,  # $0.03 per 1K tokens
                "gpt-4": 0.03,  # $0.03 per 1K tokens
                "gpt-4-32k": 0.06,  # $0.06 per 1K tokens
                "gpt-3.5-turbo": 0.0015,  # $0.0015 per 1K tokens
                "default": 0.01,  # default fallback
            }

            # Calculate costs for each model
            total_cost_by_model = {}
            total_overall_cost = 0.0
            for model_key, usage in total_token_usage_by_model.items():
                # Get cost per 1K tokens for this model
                model_cost_per_k = cost_per_thousand.get(
                    model_key, cost_per_thousand["default"]
                )
                # Calculate cost for this model's usage
                model_cost = usage["total_tokens"] * (model_cost_per_k / 1000)
                total_cost_by_model[model_key] = model_cost
                total_overall_cost += model_cost

        # Construct final result with voting information added
        final_result = {
            "success": True,
            "evaluation": {
                "approve": approve,
                "confidence_score": confidence_score,
                "reasoning": eval_result.get("explanation", ""),
            },
            "vote_result": vote_result,
            "auto_voted": should_vote,
            "tx_id": tx_id,
            "vector_results": [],
            "recent_tweets": [],
            "web_search_results": eval_result.get("web_search_results", []),
            "treasury_balance": treasury_balance,
            "component_scores": eval_result.get("component_scores", {}),
            "component_summaries": eval_result.get("component_summaries", {}),
            "flags": eval_result.get("flags", []),
            "token_usage": total_token_usage,
            "web_search_token_usage": eval_result.get(
                "web_search_token_usage",
                {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                },
            ),
            "evaluation_token_usage": {
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "total_tokens": total_tokens,
            },
            "evaluation_model_info": {"name": model_name, "temperature": temperature},
            "web_search_model_info": {"name": model_name, "temperature": temperature},
            "total_token_usage_by_model": total_token_usage_by_model,
            "total_cost_by_model": total_cost_by_model,
            "total_overall_cost": total_overall_cost,
        }

        # Single log entry about the final result instead of duplicating token usage logs
        logger.debug(
            f"Proposal evaluation completed with voting: Decision={'APPROVE' if approve else 'REJECT'} | Confidence={confidence_score:.2f} | Auto-voted={should_vote} | Transaction={tx_id or 'None'}"
        )
        return final_result
    except Exception as e:
        error_msg = f"Unexpected error in evaluate_and_vote_on_proposal: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"success": False, "error": error_msg}


async def evaluate_proposal_only(
    proposal_id: UUID,
    wallet_id: Optional[UUID] = None,
    agent_id: Optional[UUID] = None,
    dao_id: Optional[UUID] = None,
) -> Dict:
    """Evaluate a proposal without voting."""
    logger.debug(f"Starting proposal-only evaluation: proposal_id={proposal_id}")
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

    # Simplified logging - no need to duplicate what evaluate_and_vote_on_proposal already logged
    logger.debug("Removing vote-related fields from response")
    if "vote_result" in result:
        del result["vote_result"]
    if "auto_voted" in result:
        del result["auto_voted"]
    if "tx_id" in result:
        del result["tx_id"]

    logger.debug("Proposal-only evaluation completed")
    return result
