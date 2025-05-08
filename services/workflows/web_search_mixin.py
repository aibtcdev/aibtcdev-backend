from typing import Any, Dict, List, Tuple

from langgraph.graph import StateGraph
from openai import OpenAI

from lib.logger import configure_logger
from services.workflows.base import BaseWorkflowMixin

logger = configure_logger(__name__)


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

    async def search_web(
        self, query: str, **kwargs
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Search the web using OpenAI Responses API.

        Args:
            query: The search query
            **kwargs: Additional search parameters like user_location and search_context_size

        Returns:
            Tuple containing list of search results and token usage dict.
        """
        try:
            # Ensure initialization
            self._init_web_search()

            # Check cache first
            if query in self.search_results_cache:
                logger.info(f"Using cached results for query: {query}")
                return self.search_results_cache[query], {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                }

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

            # Extract token usage
            token_usage = getattr(response, "usage", {})
            standardized_usage = {
                "input_tokens": getattr(token_usage, "input_tokens", 0),
                "output_tokens": getattr(token_usage, "output_tokens", 0),
                "total_tokens": getattr(token_usage, "total_tokens", 0),
            }
            logger.debug(f"Web search token_usage: {standardized_usage}")

            # Extract output text
            text_content = None
            if hasattr(response, "output") and isinstance(response.output, list):
                try:
                    first_output = response.output[0]
                    if (
                        isinstance(first_output, dict)
                        and "content" in first_output
                        and isinstance(first_output["content"], list)
                        and len(first_output["content"]) > 0
                        and "text" in first_output["content"][0]
                    ):
                        text_content = first_output["content"][0]["text"]
                except Exception as e:
                    logger.warning(f"Failed to extract output text: {e}")

            if not text_content:
                text_content = "No output text available."

            # Defensive citation extraction (if present)
            source_urls = []
            if hasattr(response, "citations"):
                try:
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
                except Exception as e:
                    logger.warning(f"Failed to extract citations: {e}")

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
            documents = [doc]

            # Cache the results
            self.search_results_cache[query] = documents

            logger.info(f"Web search completed with {len(documents)} results")
            return documents, standardized_usage

        except Exception as e:
            logger.error(f"Web search failed: {str(e)}")
            # Return empty list and zero usage on error
            error_doc = [
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
            return error_doc, {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

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
