"""Base workflow functionality and shared components for all workflow types."""

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union

from langchain.prompts import PromptTemplate
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import Graph, StateGraph

from lib.logger import configure_logger

logger = configure_logger(__name__)


class LangGraphError(Exception):
    """Base exception for LangGraph operations"""

    def __init__(self, message: str, details: Dict = None):
        super().__init__(message)
        self.details = details or {}


class StreamingError(LangGraphError):
    """Raised when streaming operations fail"""

    pass


class ExecutionError(LangGraphError):
    """Raised when graph execution fails"""

    pass


class ValidationError(LangGraphError):
    """Raised when state validation fails"""

    pass


# Base state type for all workflows
StateType = TypeVar("StateType", bound=Dict[str, Any])


class BaseWorkflow(Generic[StateType]):
    """Base class for all LangGraph workflows.

    This class provides common functionality and patterns for all workflows.
    Each workflow should inherit from this class and implement the required
    methods.
    """

    def __init__(
        self,
        model_name: str = "gpt-4o",
        temperature: float = 0.1,
        streaming: bool = True,
        callbacks: Optional[List[Any]] = None,
    ):
        """Initialize the workflow.

        Args:
            model_name: LLM model to use
            temperature: Temperature for LLM generation
            streaming: Whether to enable streaming
            callbacks: Optional callback handlers
        """
        self.llm = ChatOpenAI(
            temperature=temperature,
            model=model_name,
            streaming=streaming,
            callbacks=callbacks or [],
        )
        self.logger = configure_logger(self.__class__.__name__)
        self.required_fields: List[str] = []
        self.model_name = model_name
        self.temperature = temperature

    def _clean_llm_response(self, content: str) -> str:
        """Clean the LLM response content and ensure valid JSON."""
        try:
            # First try to parse as-is in case it's already valid JSON
            json.loads(content)
            return content.strip()
        except json.JSONDecodeError:
            # If not valid JSON, try to extract from markdown blocks
            if "```json" in content:
                json_content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_content = content.split("```")[1].split("```")[0].strip()
            else:
                json_content = content.strip()

            # Replace any Python boolean values with JSON boolean values
            json_content = json_content.replace("True", "true").replace(
                "False", "false"
            )

            # Validate the cleaned JSON
            try:
                json.loads(json_content)
                return json_content
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse JSON after cleaning: {str(e)}")
                raise ValueError(f"Invalid JSON response from LLM: {str(e)}")

    def create_llm_with_callbacks(self, callbacks: List[Any]) -> ChatOpenAI:
        """Create a new LLM instance with specified callbacks.

        This is useful when you need to create a new LLM instance with different
        callbacks or tools.

        Args:
            callbacks: List of callback handlers

        Returns:
            A new ChatOpenAI instance with the specified callbacks
        """
        return ChatOpenAI(
            model=self.model_name,
            temperature=self.temperature,
            streaming=True,
            callbacks=callbacks,
        )

    def _create_prompt(self) -> PromptTemplate:
        """Create the prompt template for this workflow."""
        raise NotImplementedError("Workflow must implement _create_prompt")

    def _create_graph(self) -> Union[Graph, StateGraph]:
        """Create the workflow graph."""
        raise NotImplementedError("Workflow must implement _create_graph")

    def _validate_state(self, state: StateType) -> bool:
        """Validate the workflow state.

        This method checks if all required fields are present in the state.
        Override this method to add custom validation logic.

        Args:
            state: The state to validate

        Returns:
            True if the state is valid, False otherwise
        """
        if not self.required_fields:
            # If no required fields specified, assume validation passes
            return True

        # Check that all required fields are present and have values
        return all(
            field in state and state[field] is not None
            for field in self.required_fields
        )

    def get_missing_fields(self, state: StateType) -> List[str]:
        """Get a list of missing required fields in the state.

        Args:
            state: The state to check

        Returns:
            List of missing field names
        """
        if not self.required_fields:
            return []

        return [
            field
            for field in self.required_fields
            if field not in state or state[field] is None
        ]

    async def execute(self, initial_state: StateType) -> Dict:
        """Execute the workflow.

        Args:
            initial_state: The initial state for the workflow

        Returns:
            The final state after execution

        Raises:
            ValidationError: If the initial state is invalid
            ExecutionError: If the workflow execution fails
        """
        try:
            # Validate state
            is_valid = self._validate_state(initial_state)
            if not is_valid:
                missing_fields = self.get_missing_fields(initial_state)
                error_msg = (
                    f"Invalid initial state. Missing required fields: {missing_fields}"
                )
                self.logger.error(error_msg)
                raise ValidationError(error_msg, {"missing_fields": missing_fields})

            # Create and compile the graph
            graph = self._create_graph()
            if hasattr(graph, "compile"):
                app = graph.compile()
            else:
                # Graph is already compiled
                app = graph

            # Execute the workflow
            self.logger.info(f"Executing workflow {self.__class__.__name__}")
            result = await app.ainvoke(initial_state)
            self.logger.info(f"Workflow {self.__class__.__name__} execution completed")
            return result

        except ValidationError as e:
            # Re-raise validation errors
            raise e
        except Exception as e:
            self.logger.error(f"Workflow execution failed: {str(e)}", exc_info=True)
            raise ExecutionError(f"Workflow execution failed: {str(e)}")


class BaseWorkflowMixin(ABC):
    """Base mixin for adding capabilities to workflows.

    This is an abstract base class that defines the interface for
    workflow capability mixins. Mixins can be combined to create
    workflows with multiple capabilities.
    """

    @abstractmethod
    def integrate_with_graph(self, graph: StateGraph, **kwargs) -> None:
        """Integrate this capability with a graph.

        Args:
            graph: The graph to integrate with
            **kwargs: Additional arguments specific to this capability
        """
        pass


class PlanningCapability(BaseWorkflowMixin):
    """Mixin that adds planning capabilities to a workflow."""

    async def create_plan(self, query: str, **kwargs) -> str:
        """Create a plan based on the user's query.

        Args:
            query: The user's query to plan for
            **kwargs: Additional arguments (callback_handler, etc.)

        Returns:
            The generated plan
        """
        raise NotImplementedError("PlanningCapability must implement create_plan")

    def integrate_with_graph(self, graph: StateGraph, **kwargs) -> None:
        """Integrate planning capability with a graph.

        This adds the planning capability to the graph by modifying
        the entry point to first create a plan.

        Args:
            graph: The graph to integrate with
            **kwargs: Additional arguments specific to planning
        """
        # Implementation depends on specific graph structure
        raise NotImplementedError(
            "PlanningCapability must implement integrate_with_graph"
        )


class VectorRetrievalCapability(BaseWorkflowMixin):
    """Mixin that adds vector retrieval capabilities to a workflow."""

    async def retrieve_from_vector_store(self, query: str, **kwargs) -> List[Any]:
        """Retrieve relevant documents from vector store.

        Args:
            query: The query to search for
            **kwargs: Additional arguments (collection_name, embeddings, etc.)

        Returns:
            List of retrieved documents
        """
        raise NotImplementedError(
            "VectorRetrievalCapability must implement retrieve_from_vector_store"
        )

    def integrate_with_graph(self, graph: StateGraph, **kwargs) -> None:
        """Integrate vector retrieval capability with a graph.

        This adds the vector retrieval capability to the graph.

        Args:
            graph: The graph to integrate with
            **kwargs: Additional arguments specific to vector retrieval
        """
        # Implementation depends on specific graph structure
        raise NotImplementedError(
            "VectorRetrievalCapability must implement integrate_with_graph"
        )
