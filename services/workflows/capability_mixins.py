"""Standardized mixins for adding capabilities to LangGraph workflows.

This module provides a standardized approach to creating and integrating
capabilities into LangGraph workflows through a mixin system.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

from langchain_core.callbacks import BaseCallbackHandler
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph

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
