"""Base workflow functionality and shared components for all workflow types."""

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union

from langchain.prompts import PromptTemplate
from langchain.schema import Document
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langgraph.graph import Graph, StateGraph
from openai import OpenAI

from backend.factory import backend
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
        model_name: str = "gpt-4.1",
        temperature: Optional[float] = 0.1,
        streaming: bool = True,
        callbacks: Optional[List[Any]] = None,
    ):
        """Initialize the workflow.

        Args:
            model_name: LLM model to use
            temperature: Temperature for LLM generation, can be a float or None
            streaming: Whether to enable streaming
            callbacks: Optional callback handlers
        """
        self.llm = ChatOpenAI(
            temperature=temperature,
            model=model_name,
            streaming=streaming,
            stream_usage=True,
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
            stream_usage=True,
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

    def __init__(self, *args, **kwargs):
        """Initialize the vector retrieval capability."""
        # Initialize parent class if it exists
        super().__init__(*args, **kwargs) if hasattr(super(), "__init__") else None
        # Initialize our attributes
        self._init_vector_retrieval()

    def _init_vector_retrieval(self) -> None:
        """Initialize vector retrieval attributes if not already initialized."""
        if not hasattr(self, "collection_names"):
            self.collection_names = ["knowledge_collection", "dao_collection"]
        if not hasattr(self, "embeddings"):
            self.embeddings = OpenAIEmbeddings()
        if not hasattr(self, "vector_results_cache"):
            self.vector_results_cache = {}

    async def retrieve_from_vector_store(self, query: str, **kwargs) -> List[Document]:
        """Retrieve relevant documents from multiple vector stores.

        Args:
            query: The query to search for
            **kwargs: Additional arguments (collection_name, embeddings, etc.)

        Returns:
            List of retrieved documents
        """
        try:
            # Ensure initialization
            self._init_vector_retrieval()

            # Check cache first
            if query in self.vector_results_cache:
                logger.debug(f"Using cached vector results for query: {query}")
                return self.vector_results_cache[query]

            all_documents = []
            limit_per_collection = kwargs.get("limit", 4)
            logger.debug(
                f"Searching vector store: query={query} | limit_per_collection={limit_per_collection}"
            )

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
                    logger.debug(
                        f"Retrieved {len(documents)} documents from collection {collection_name}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to retrieve from collection {collection_name}: {str(e)}",
                        exc_info=True,
                    )
                    continue  # Continue with other collections if one fails

            logger.debug(
                f"Retrieved total of {len(all_documents)} documents from all collections"
            )

            # Cache the results
            self.vector_results_cache[query] = all_documents

            return all_documents
        except Exception as e:
            logger.error(f"Vector store retrieval failed: {str(e)}", exc_info=True)
            return []

    def integrate_with_graph(self, graph: StateGraph, **kwargs) -> None:
        """Integrate vector retrieval capability with a graph.

        This adds the vector retrieval capability to the graph by adding a node
        that can perform vector searches when needed.

        Args:
            graph: The graph to integrate with
            **kwargs: Additional arguments specific to vector retrieval including:
                     - collection_names: List of collection names to search
                     - limit_per_collection: Number of results per collection
        """
        # Add vector search node
        graph.add_node("vector_search", self.retrieve_from_vector_store)

        # Add result processing node if needed
        if "process_vector_results" not in graph.nodes:
            graph.add_node("process_vector_results", self._process_vector_results)
            graph.add_edge("vector_search", "process_vector_results")

    async def _process_vector_results(
        self, vector_results: List[Document], **kwargs
    ) -> Dict[str, Any]:
        """Process vector search results.

        Args:
            vector_results: Results from vector search
            **kwargs: Additional processing arguments

        Returns:
            Processed results with metadata
        """
        return {
            "results": vector_results,
            "metadata": {
                "num_vector_results": len(vector_results),
                "collection_sources": list(
                    set(
                        doc.metadata.get("collection_source", "unknown")
                        for doc in vector_results
                    )
                ),
            },
        }


class WebSearchCapability(BaseWorkflowMixin):
    """Mixin that adds web search capabilities to a workflow using OpenAI Responses API."""

    def __init__(self, *args, **kwargs):
        """Initialize the web search capability."""
        # Initialize parent class if it exists
        super().__init__(*args, **kwargs) if hasattr(super(), "__init__") else None
        # Initialize our attributes
        self._init_web_search()

    def _init_web_search(self) -> None:
        """Initialize web search attributes if not already initialized."""
        if not hasattr(self, "search_results_cache"):
            self.search_results_cache = {}
        if not hasattr(self, "client"):
            self.client = OpenAI()

    async def search_web(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Search the web using OpenAI Responses API.

        Args:
            query: The search query
            **kwargs: Additional search parameters like user_location and search_context_size

        Returns:
            List of search results with content and metadata
        """
        try:
            # Ensure initialization
            self._init_web_search()

            # Check cache first
            if query in self.search_results_cache:
                logger.info(f"Using cached results for query: {query}")
                return self.search_results_cache[query]

            # Configure web search tool
            tool_config = {
                "type": "web_search_preview",
                "search_context_size": kwargs.get("search_context_size", "medium"),
            }

            # Add user location if provided
            if "user_location" in kwargs:
                tool_config["user_location"] = kwargs["user_location"]

            # Make the API call
            response = self.client.responses.create(
                model="gpt-4.1", tools=[tool_config], input=query
            )

            logger.debug(f"Web search response: {response}")
            # Process the response into our document format
            documents = []

            # Access the output text directly
            if hasattr(response, "output_text"):
                text_content = response.output_text
                source_urls = []

                # Try to extract citations if available
                if hasattr(response, "citations"):
                    source_urls = [
                        {
                            "url": citation.url,
                            "title": getattr(citation, "title", ""),
                            "start_index": getattr(citation, "start_index", 0),
                            "end_index": getattr(citation, "end_index", 0),
                        }
                        for citation in response.citations
                        if hasattr(citation, "url")
                    ]

                # Ensure we always have at least one URL entry
                if not source_urls:
                    source_urls = [
                        {
                            "url": "No source URL available",
                            "title": "Generated Response",
                            "start_index": 0,
                            "end_index": len(text_content),
                        }
                    ]

                # Create document with content
                doc = {
                    "page_content": text_content,
                    "metadata": {
                        "type": "web_search_result",
                        "source_urls": source_urls,
                        "query": query,
                        "timestamp": None,
                    },
                }
                documents.append(doc)

            # Cache the results
            self.search_results_cache[query] = documents

            logger.info(f"Web search completed with {len(documents)} results")
            return documents

        except Exception as e:
            logger.error(f"Web search failed: {str(e)}")
            # Return a list with one empty result to prevent downstream errors
            return [
                {
                    "page_content": "Web search failed to return results.",
                    "metadata": {
                        "type": "web_search_result",
                        "source_urls": [
                            {
                                "url": "Error occurred during web search",
                                "title": "Error",
                                "start_index": 0,
                                "end_index": 0,
                            }
                        ],
                        "query": query,
                        "timestamp": None,
                    },
                }
            ]

    def integrate_with_graph(self, graph: StateGraph, **kwargs) -> None:
        """Integrate web search capability with a graph.

        This adds the web search capability to the graph by adding a node
        that can perform web searches when needed.

        Args:
            graph: The graph to integrate with
            **kwargs: Additional arguments specific to web search including:
                     - search_context_size: "low", "medium", or "high"
                     - user_location: dict with type, country, city, region
        """
        # Add web search node
        graph.add_node("web_search", self.search_web)

        # Add result processing node if needed
        if "process_results" not in graph.nodes:
            graph.add_node("process_results", self._process_results)
            graph.add_edge("web_search", "process_results")

    async def _process_results(
        self, web_results: List[Dict[str, Any]], **kwargs
    ) -> Dict[str, Any]:
        """Process web search results.

        Args:
            web_results: Results from web search
            **kwargs: Additional processing arguments

        Returns:
            Processed results with metadata
        """
        return {
            "results": web_results,
            "metadata": {
                "num_web_results": len(web_results),
                "source_types": ["web_search"],
            },
        }
