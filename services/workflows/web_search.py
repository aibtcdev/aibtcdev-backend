"""Web search workflow implementation using OpenAI Assistant API."""

import asyncio
import json
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import StateGraph
from openai import OpenAI
from openai.types.beta.assistant import Assistant
from openai.types.beta.thread import Thread
from openai.types.beta.threads.thread_message import ThreadMessage

from lib.logger import configure_logger
from services.workflows.base import BaseWorkflow, WebSearchCapability
from services.workflows.vector import VectorRetrievalCapability

logger = configure_logger(__name__)


class WebSearchWorkflow(BaseWorkflow, WebSearchCapability, VectorRetrievalCapability):
    """Workflow that combines web search with vector retrieval capabilities using OpenAI Assistant."""

    def __init__(self, **kwargs):
        """Initialize the workflow.

        Args:
            **kwargs: Additional arguments passed to parent classes
        """
        super().__init__(**kwargs)
        self.search_results_cache = {}
        self.client = OpenAI()
        # Create an assistant with web browsing capability
        self.assistant: Assistant = self.client.beta.assistants.create(
            name="Web Search Assistant",
            description="Assistant that helps with web searches",
            model="gpt-4-turbo-preview",
            tools=[{"type": "retrieval"}, {"type": "web_browser"}],
            instructions="""You are a web search assistant. Your primary task is to:
            1. Search the web for relevant information
            2. Extract key information from web pages
            3. Provide detailed, accurate responses with source URLs
            4. Format responses as structured data with content and metadata
            Always include source URLs in your responses.""",
        )

    async def search_web(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Search the web using OpenAI Assistant API.

        Args:
            query: The search query
            **kwargs: Additional search parameters

        Returns:
            List of search results with content and metadata
        """
        try:
            # Check cache first
            if query in self.search_results_cache:
                logger.info(f"Using cached results for query: {query}")
                return self.search_results_cache[query]

            # Create a new thread for this search
            thread: Thread = self.client.beta.threads.create()

            # Add the user's message to the thread
            self.client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=f"Search the web for: {query}. Please provide detailed information with source URLs.",
            )

            # Run the assistant
            run = self.client.beta.threads.runs.create(
                thread_id=thread.id, assistant_id=self.assistant.id
            )

            # Wait for completion
            while True:
                run_status = self.client.beta.threads.runs.retrieve(
                    thread_id=thread.id, run_id=run.id
                )
                if run_status.status == "completed":
                    break
                elif run_status.status in ["failed", "cancelled", "expired"]:
                    raise Exception(
                        f"Assistant run failed with status: {run_status.status}"
                    )
                await asyncio.sleep(1)  # Wait before checking again

            # Get the assistant's response
            messages: List[ThreadMessage] = self.client.beta.threads.messages.list(
                thread_id=thread.id
            )

            # Process the response into our document format
            documents = []
            for message in messages:
                if message.role == "assistant":
                    for content in message.content:
                        if content.type == "text":
                            # Extract URLs from annotations if available
                            urls = []
                            if message.metadata and "citations" in message.metadata:
                                urls = [
                                    cite["url"]
                                    for cite in message.metadata["citations"]
                                ]

                            # Create document with content and metadata
                            doc = {
                                "page_content": content.text,
                                "metadata": {
                                    "type": "web_search_result",
                                    "source_urls": urls,
                                    "query": query,
                                    "timestamp": message.created_at,
                                },
                            }
                            documents.append(doc)

            # Cache the results
            self.search_results_cache[query] = documents

            logger.info(f"Web search completed with {len(documents)} results")
            return documents

        except Exception as e:
            logger.error(f"Web search failed: {str(e)}")
            return []

    async def execute(self, query: str, **kwargs) -> Dict[str, Any]:
        """Execute the web search workflow.

        This workflow:
        1. Searches the web for relevant information
        2. Processes and stores the results
        3. Combines with vector retrieval if available

        Args:
            query: The search query
            **kwargs: Additional execution arguments

        Returns:
            Dict containing search results and any additional data
        """
        try:
            # Perform web search
            web_results = await self.search_web(query, **kwargs)

            # Cache results
            self.search_results_cache[query] = web_results

            # Combine with vector retrieval if available
            combined_results = web_results
            try:
                vector_results = await self.retrieve_from_vectorstore(query, **kwargs)
                combined_results.extend(vector_results)
            except Exception as e:
                logger.warning(
                    f"Vector retrieval failed, using only web results: {str(e)}"
                )

            return {
                "query": query,
                "results": combined_results,
                "source": "web_search_workflow",
                "metadata": {
                    "num_web_results": len(web_results),
                    "has_vector_results": (
                        bool(vector_results) if "vector_results" in locals() else False
                    ),
                },
            }

        except Exception as e:
            logger.error(f"Web search workflow execution failed: {str(e)}")
            raise

    def integrate_with_graph(self, graph: StateGraph, **kwargs) -> None:
        """Integrate web search workflow with a graph.

        Args:
            graph: The graph to integrate with
            **kwargs: Additional integration arguments
        """
        # Add web search node
        graph.add_node("web_search", self.search_web)

        # Add vector retrieval node if available
        try:
            graph.add_node("vector_retrieval", self.retrieve_from_vectorstore)

            # Connect nodes
            graph.add_edge("web_search", "vector_retrieval")
        except Exception as e:
            logger.warning(f"Vector retrieval integration failed: {str(e)}")

        # Add result processing node
        graph.add_node("process_results", self._process_results)
        graph.add_edge("vector_retrieval", "process_results")

    async def _process_results(
        self,
        web_results: List[Dict[str, Any]],
        vector_results: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Process and combine search results.

        Args:
            web_results: Results from web search
            vector_results: Optional results from vector retrieval

        Returns:
            Processed and combined results
        """
        combined_results = web_results.copy()
        if vector_results:
            combined_results.extend(vector_results)

        # Deduplicate results based on content similarity
        seen_contents = set()
        unique_results = []
        for result in combined_results:
            content = result.get("page_content", "")
            content_hash = hash(content)
            if content_hash not in seen_contents:
                seen_contents.add(content_hash)
                unique_results.append(result)

        return {
            "results": unique_results,
            "metadata": {
                "num_web_results": len(web_results),
                "num_vector_results": len(vector_results) if vector_results else 0,
                "num_unique_results": len(unique_results),
            },
        }
