"""Base workflow functionality."""

from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import Graph
from lib.logger import configure_logger
from typing import Any, Dict, Generic, TypeVar

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


StateType = TypeVar("StateType", bound=Dict[str, Any])


class BaseWorkflow(Generic[StateType]):
    """Base class for all LangGraph workflows."""

    def __init__(self, model_name: str = "gpt-4", temperature: float = 0.7):
        """Initialize the workflow."""
        self.llm = ChatOpenAI(
            temperature=temperature,
            model=model_name,
            streaming=True,
        )
        self.logger = configure_logger(self.__class__.__name__)

    def _clean_llm_response(self, content: str) -> str:
        """Clean the LLM response content."""
        if "```json" in content:
            return content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            return content.split("```")[1].split("```")[0].strip()
        return content.strip()

    def _create_prompt(self) -> PromptTemplate:
        """Create the prompt template for this workflow."""
        raise NotImplementedError("Workflow must implement _create_prompt")

    def _create_graph(self) -> Graph:
        """Create the workflow graph."""
        raise NotImplementedError("Workflow must implement _create_graph")

    def _validate_state(self, state: StateType) -> bool:
        """Validate the workflow state."""
        raise NotImplementedError("Workflow must implement _validate_state")

    async def execute(self, initial_state: StateType) -> Dict:
        """Execute the workflow."""
        try:
            if not self._validate_state(initial_state):
                raise ValueError("Invalid initial state")

            graph = self._create_graph()
            app = graph.compile()
            result = await app.ainvoke(initial_state)
            return result

        except Exception as e:
            self.logger.error(f"Workflow execution failed: {str(e)}", exc_info=True)
            raise ExecutionError(f"Workflow execution failed: {str(e)}")
