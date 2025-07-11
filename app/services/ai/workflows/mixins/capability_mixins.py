"""Standardized mixins for adding capabilities to LangGraph workflows.

This module provides a standardized approach to creating and integrating
capabilities into LangGraph workflows through a mixin system.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, TypeVar

from langchain_core.prompts.chat import ChatPromptTemplate
from langgraph.graph import StateGraph

from app.backend.factory import backend
from app.services.ai.workflows.utils.model_factory import (
    create_chat_openai,
    ModelConfig,
)
from app.backend.models import PromptFilter
from app.lib.logger import configure_logger

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
        self.llm = create_chat_openai(
            model=self.config.get("model_name"),
            temperature=self.config.get("temperature"),
            streaming=self.config.get("streaming"),
            callbacks=self.config.get("callbacks"),
        )

        if "state_key" in kwargs:
            self.state_key = kwargs["state_key"]

        self.logger.debug(
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

                # Track completion - add this node to completed_steps
                if "completed_steps" not in state:
                    state["completed_steps"] = set()
                state["completed_steps"].add(node_name)

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
                # Even on error, mark as completed to avoid infinite retries
                if "completed_steps" not in state:
                    state["completed_steps"] = set()
                state["completed_steps"].add(node_name)

                return state

        # Add the node to the graph
        graph.add_node(node_name, node_function)
        self.logger.debug(f"Added node {node_name} to graph")


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
        self.logger.debug(f"Added sub-workflow {name} to {self.name}")

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

        Only returns a custom prompt if there's an active agent_id set for the specific DAO.
        Otherwise returns None.

        Args:
            dao_id: DAO ID to check for agent-specific prompts
            agent_id: Agent ID to find agent-specific prompts
            profile_id: Not used in current implementation
            prompt_type: Type of prompt (used in prompt_text search)

        Returns:
            Dictionary containing prompt_text, model, and temperature if agent prompt found
        """
        try:
            # Only proceed if both dao_id and agent_id are provided
            if not dao_id or not agent_id:
                return None

            # Look for active agent-specific prompts only
            agent_filter = PromptFilter(agent_id=agent_id, is_active=True)
            agent_prompts = backend.list_prompts(agent_filter)

            # Filter prompts that might be relevant to this prompt type
            relevant_prompts = []
            for prompt in agent_prompts:
                if prompt.prompt_text and (
                    prompt_type.lower() in prompt.prompt_text.lower()
                    or "evaluation" in prompt.prompt_text.lower()
                    or len(prompt.prompt_text) > 100  # Assume longer prompts are custom
                ):
                    relevant_prompts.append(prompt)

            if relevant_prompts:
                # Use the first relevant prompt found
                best_prompt = relevant_prompts[0]

                self.logger.debug(
                    f"Using custom prompt for {prompt_type} from agent {agent_id}"
                )

                return {
                    "prompt_text": best_prompt.prompt_text,
                    "model": best_prompt.model or ModelConfig.get_default_model(),
                    "temperature": best_prompt.temperature
                    or ModelConfig.get_default_temperature(),
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
                model = custom_prompt_data.get("model")
                temperature = custom_prompt_data.get("temperature")

                if model != getattr(
                    self.llm, "model_name", None
                ) or temperature != getattr(self.llm, "temperature", None):
                    self.llm = create_chat_openai(
                        model=model,
                        temperature=temperature,
                    )
                    self.logger.debug(
                        f"Updated LLM settings: model={model}, temperature={temperature}"
                    )
        except Exception as e:
            self.logger.error(f"Error applying custom prompt settings: {str(e)}")

    def create_chat_prompt_with_custom_injection(
        self,
        default_system_message: str,
        default_user_message: str,
        dao_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        profile_id: Optional[str] = None,
        prompt_type: str = "evaluation",
    ) -> ChatPromptTemplate:
        """Create a chat prompt template, injecting custom prompt at the top if available.

        Args:
            default_system_message: Default system message content
            default_user_message: Default user message content
            dao_id: Optional DAO ID for custom prompt lookup
            agent_id: Optional agent ID for custom prompt lookup
            profile_id: Optional profile ID for custom prompt lookup
            prompt_type: Type of prompt for filtering

        Returns:
            ChatPromptTemplate with custom prompt injected or just default messages
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

            # Inject custom prompt at the top of the system message
            custom_prompt_text = custom_prompt_data["prompt_text"]

            # Add custom prompt section at the top of system message
            enhanced_system_message = f"""IMPORTANT: The following custom instructions are provided by the user and should be treated with HIGHER PRIORITY than all other instructions. These are specific requirements that MUST be followed and should override any conflicting guidance in the default instructions below.

USER CUSTOM INSTRUCTIONS:
{custom_prompt_text}

CRITICAL: Always prioritize and follow the custom instructions above when they conflict with or supplement the default instructions. The user's custom guidance takes precedence.

---

{default_system_message}"""

            self.logger.debug(
                f"Injecting custom prompt at top of {prompt_type} system message"
            )

            messages = [
                ("system", enhanced_system_message),
                ("human", default_user_message),
            ]
        else:
            # Use default messages as-is
            self.logger.debug(f"Using default chat prompt template for {prompt_type}")
            messages = [
                ("system", default_system_message),
                ("human", default_user_message),
            ]

        return ChatPromptTemplate.from_messages(messages)
