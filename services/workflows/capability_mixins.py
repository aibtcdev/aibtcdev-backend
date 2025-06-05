"""Standardized mixins for adding capabilities to LangGraph workflows.

This module provides a standardized approach to creating and integrating
capabilities into LangGraph workflows through a mixin system.
"""

import asyncio
import os
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

from langchain.prompts import PromptTemplate
from langchain_core.callbacks import BaseCallbackHandler
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph

from backend.factory import backend
from backend.models import PromptFilter
from lib.logger import configure_logger

logger = configure_logger(__name__)

# Type variable for workflow states
StateType = TypeVar("StateType", bound=Dict[str, Any])


class CapabilityMixin(ABC):
    """Abstract base class for workflow capability mixins.

    All capability mixins should inherit from this class and implement
    the required methods to ensure consistent integration with workflows.
    """

    @abstractmethod
    def initialize(self, **kwargs) -> None:
        """Initialize the capability with necessary configuration.

        Args:
            **kwargs: Arbitrary keyword arguments for configuration
        """
        pass

    @abstractmethod
    def add_to_graph(self, graph: StateGraph, **kwargs) -> None:
        """Add this capability's nodes and edges to a StateGraph.

        Args:
            graph: The StateGraph to add nodes/edges to
            **kwargs: Additional arguments specific to this capability
        """
        pass


class BaseCapabilityMixin(CapabilityMixin):
    """Base implementation of capability mixin with common functionality.

    Provides shared functionality for LLM configuration, state management,
    and graph integration that most capability mixins can leverage.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        state_key: Optional[str] = None,
    ):
        """Initialize the base capability mixin.

        Args:
            config: Configuration dictionary with settings like model_name, temperature
            state_key: Key to use when updating the state dictionary
        """
        self.config = config or {}
        self.state_key = state_key
        self.llm = None
        self.logger = configure_logger(self.__class__.__name__)

    def initialize(self, **kwargs) -> None:
        """Initialize the capability with LLM and other settings.

        Args:
            **kwargs: Additional configuration parameters
        """
        # Update config with any passed kwargs
        if kwargs:
            self.config.update(kwargs)

        # Create the LLM instance
        self.llm = ChatOpenAI(
            model=self.config.get("model_name", "gpt-4.1"),
            temperature=self.config.get("temperature", 0.1),
            streaming=self.config.get("streaming", True),
            callbacks=self.config.get("callbacks", []),
        )

        if "state_key" in kwargs:
            self.state_key = kwargs["state_key"]

        self.logger.info(
            f"Initialized {self.__class__.__name__} with config: {self.config}"
        )

    def configure(self, state_key: str) -> None:
        """Configure the state key for this capability.

        Args:
            state_key: The key to use in the state dictionary
        """
        self.state_key = state_key

    @abstractmethod
    async def process(self, state: StateType) -> Dict[str, Any]:
        """Process the current state and return updated values.

        Args:
            state: Current workflow state

        Returns:
            Dictionary with updated values to be added to the state
        """
        pass

    def add_to_graph(self, graph: StateGraph, **kwargs) -> None:
        """Add this capability as a node to the graph.

        Args:
            graph: StateGraph to add node to
            **kwargs: Additional arguments
        """
        if not self.state_key:
            raise ValueError(f"state_key must be set for {self.__class__.__name__}")

        node_name = kwargs.get("node_name", self.state_key)

        async def node_function(state: StateType) -> StateType:
            """Node function that processes state and updates it.

            Args:
                state: Current workflow state

            Returns:
                Updated workflow state
            """
            try:
                result = await self.process(state)
                # Update state with results
                if isinstance(result, dict):
                    # If returning a dict, merge with state using the state_key
                    state[self.state_key] = result
                elif isinstance(result, list):
                    # If returning a list, set it directly to the state_key
                    state[self.state_key] = result
                elif result is not None:
                    # For any other non-None result, set it directly
                    state[self.state_key] = result
                return state
            except Exception as e:
                self.logger.error(f"Error in node {node_name}: {str(e)}", exc_info=True)
                # Add error to state
                if "errors" not in state:
                    state["errors"] = []
                state["errors"].append(
                    {
                        "node": node_name,
                        "error": str(e),
                        "type": self.__class__.__name__,
                    }
                )
                return state

        # Add the node to the graph
        graph.add_node(node_name, node_function)
        self.logger.info(f"Added node {node_name} to graph")


class ComposableWorkflowMixin(CapabilityMixin):
    """Mixin for creating composable workflows that can be nested.

    This mixin allows workflows to be composed of sub-workflows and
    provides utilities for managing their execution and state sharing.
    """

    def __init__(self, name: str = None):
        """Initialize the composable workflow mixin.

        Args:
            name: Name identifier for this composable workflow
        """
        self.name = name or self.__class__.__name__
        self.sub_workflows = {}
        self.graph = None
        self.logger = configure_logger(self.__class__.__name__)

    def initialize(self, **kwargs) -> None:
        """Initialize the composable workflow.

        Args:
            **kwargs: Configuration parameters
        """
        pass

    def add_sub_workflow(
        self,
        name: str,
        workflow: CapabilityMixin,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a sub-workflow to this composable workflow.

        Args:
            name: Name identifier for the sub-workflow
            workflow: The workflow object to add
            config: Configuration for the sub-workflow
        """
        if config:
            # Apply config to the sub-workflow
            workflow.initialize(**config)
        self.sub_workflows[name] = workflow
        self.logger.info(f"Added sub-workflow {name} to {self.name}")

    def build_graph(self) -> StateGraph:
        """Build and return the composed workflow graph.

        Returns:
            StateGraph: The compiled workflow graph
        """
        raise NotImplementedError("Subclasses must implement build_graph")

    def add_to_graph(self, graph: StateGraph, **kwargs) -> None:
        """Add this composable workflow to a parent graph.

        For composable workflows, this typically involves adding a
        subgraph node that represents the entire nested workflow.

        Args:
            graph: The parent StateGraph
            **kwargs: Additional arguments
        """
        raise NotImplementedError("Subclasses must implement add_to_graph")


class PromptCapability:
    """Mixin that provides custom prompt functionality for agents."""

    def __init__(self):
        """Initialize the prompt capability."""
        if not hasattr(self, "logger"):
            self.logger = configure_logger(self.__class__.__name__)

    def get_custom_prompt(
        self,
        dao_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        profile_id: Optional[str] = None,
        prompt_type: str = "evaluation",
    ) -> Optional[Dict[str, Any]]:
        """Fetch custom prompt for the given context.

        Args:
            dao_id: Optional DAO ID to find DAO-specific prompts
            agent_id: Optional agent ID to find agent-specific prompts
            profile_id: Optional profile ID to find user-specific prompts
            prompt_type: Type of prompt (used in prompt_text search)

        Returns:
            Dictionary containing prompt_text, model, and temperature if found
        """
        try:
            # Create filter based on available IDs, prioritizing specificity
            filters = PromptFilter(is_active=True)

            # Try to find prompts in order of specificity:
            # 1. Agent-specific prompts
            # 2. DAO-specific prompts
            # 3. Profile-specific prompts

            prompt_candidates = []

            if agent_id:
                agent_filter = PromptFilter(agent_id=agent_id, is_active=True)
                agent_prompts = backend.list_prompts(agent_filter)
                prompt_candidates.extend(
                    [(prompt, "agent") for prompt in agent_prompts]
                )

            if dao_id:
                dao_filter = PromptFilter(dao_id=dao_id, is_active=True)
                dao_prompts = backend.list_prompts(dao_filter)
                prompt_candidates.extend([(prompt, "dao") for prompt in dao_prompts])

            if profile_id:
                profile_filter = PromptFilter(profile_id=profile_id, is_active=True)
                profile_prompts = backend.list_prompts(profile_filter)
                prompt_candidates.extend(
                    [(prompt, "profile") for prompt in profile_prompts]
                )

            # Filter prompts that might be relevant to this prompt type
            relevant_prompts = []
            for prompt, source in prompt_candidates:
                if prompt.prompt_text and (
                    prompt_type.lower() in prompt.prompt_text.lower()
                    or "evaluation" in prompt.prompt_text.lower()
                    or len(prompt.prompt_text) > 100  # Assume longer prompts are custom
                ):
                    relevant_prompts.append((prompt, source))

            if relevant_prompts:
                # Use the most specific prompt (agent > dao > profile)
                priority_order = {"agent": 1, "dao": 2, "profile": 3}
                best_prompt = min(relevant_prompts, key=lambda x: priority_order[x[1]])[
                    0
                ]

                self.logger.info(
                    f"Using custom prompt for {prompt_type} from {best_prompt.dao_id or best_prompt.agent_id or best_prompt.profile_id}"
                )

                return {
                    "prompt_text": best_prompt.prompt_text,
                    "model": best_prompt.model or "gpt-4o",
                    "temperature": best_prompt.temperature or 0.1,
                }

        except Exception as e:
            self.logger.error(f"Error fetching custom prompt: {str(e)}")

        return None

    def apply_custom_prompt_settings(self, custom_prompt_data: Dict[str, Any]):
        """Apply custom model and temperature settings if available.

        Args:
            custom_prompt_data: Dictionary containing model and temperature settings
        """
        try:
            if hasattr(self, "llm") and custom_prompt_data:
                # Update LLM with custom settings
                model = custom_prompt_data.get("model", "gpt-4.1")
                temperature = custom_prompt_data.get("temperature", 0.1)

                if model != self.llm.model_name or temperature != self.llm.temperature:
                    self.llm = ChatOpenAI(
                        model=model,
                        temperature=temperature,
                        api_key=os.getenv("OPENAI_API_KEY"),
                    )
                    self.logger.info(
                        f"Updated LLM settings: model={model}, temperature={temperature}"
                    )
        except Exception as e:
            self.logger.error(f"Error applying custom prompt settings: {str(e)}")

    def create_prompt_with_custom_injection(
        self,
        default_template: str,
        input_variables: List[str],
        dao_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        profile_id: Optional[str] = None,
        prompt_type: str = "evaluation",
    ) -> PromptTemplate:
        """Create a prompt template, injecting custom prompt at the top if available.

        Args:
            default_template: Default template to use
            input_variables: List of input variable names for the template
            dao_id: Optional DAO ID for custom prompt lookup
            agent_id: Optional agent ID for custom prompt lookup
            profile_id: Optional profile ID for custom prompt lookup
            prompt_type: Type of prompt for filtering

        Returns:
            PromptTemplate with custom prompt injected at top or just default template
        """
        # Try to get custom prompt
        custom_prompt_data = self.get_custom_prompt(
            dao_id=dao_id,
            agent_id=agent_id,
            profile_id=profile_id,
            prompt_type=prompt_type,
        )

        if custom_prompt_data:
            # Apply custom model/temperature settings
            self.apply_custom_prompt_settings(custom_prompt_data)

            # Inject custom prompt at the top of the default template
            custom_prompt_text = custom_prompt_data["prompt_text"]

            # Add custom prompt section at the top
            enhanced_template = f"""<custom_instructions>
{custom_prompt_text}
</custom_instructions>

{default_template}"""

            self.logger.info(
                f"Injecting custom prompt at top of {prompt_type} template"
            )
            return PromptTemplate(
                input_variables=input_variables, template=enhanced_template
            )
        else:
            # Use default template as-is
            self.logger.debug(f"Using default prompt template for {prompt_type}")
            return PromptTemplate(
                input_variables=input_variables, template=default_template
            )
