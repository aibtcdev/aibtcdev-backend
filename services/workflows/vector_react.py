"""Vector-enabled ReAct workflow functionality with Supabase Vecs integration."""

import asyncio
from typing import Any, AsyncGenerator, Dict, List, Optional, TypedDict, Union

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from backend.factory import backend
from lib.logger import configure_logger
from services.workflows.base import (
    BaseWorkflow,
    ExecutionError,
    VectorRetrievalCapability,
)
from services.workflows.react import (
    MessageProcessor,
    ReactState,
    StreamingCallbackHandler,
)

# Remove this import to avoid circular dependencies
# from services.workflows.workflow_service import BaseWorkflowService, WorkflowBuilder

logger = configure_logger(__name__)


class VectorRetrievalState(TypedDict):
    """State for vector retrieval step."""

    query: str
    documents: List[Document]


class VectorReactState(ReactState):
    """State for the Vector ReAct workflow, extending ReactState."""

    vector_results: Optional[List[Document]]


class VectorReactWorkflow(BaseWorkflow[VectorReactState], VectorRetrievalCapability):
    """ReAct workflow with vector store integration."""

    def __init__(
        self,
        callback_handler: StreamingCallbackHandler,
        tools: List[Any],
        collection_name: str,
        embeddings: Optional[Embeddings] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.callback_handler = callback_handler
        self.tools = tools
        self.collection_name = collection_name
        self.embeddings = embeddings or OpenAIEmbeddings()
        self.required_fields = ["messages"]

        # Create a new LLM instance with the callback handler
        self.llm = self.create_llm_with_callbacks([callback_handler]).bind_tools(tools)

    def _create_prompt(self) -> None:
        """Not used in VectorReact workflow."""
        pass

    async def retrieve_from_vector_store(self, query: str, **kwargs) -> List[Document]:
        """Retrieve relevant documents from vector store.

        Args:
            query: The query to search for
            **kwargs: Additional arguments

        Returns:
            List of retrieved documents
        """
        try:
            # Query vectors using the backend
            vector_results = await backend.query_vectors(
                collection_name=self.collection_name,
                query_text=query,
                limit=kwargs.get("limit", 4),
                embeddings=self.embeddings,
            )

            # Convert to LangChain Documents
            documents = [
                Document(
                    page_content=doc.get("page_content", ""),
                    metadata=doc.get("metadata", {}),
                )
                for doc in vector_results
            ]

            logger.info(f"Retrieved {len(documents)} documents from vector store")
            return documents
        except Exception as e:
            logger.error(f"Vector store retrieval failed: {str(e)}")
            return []

    def integrate_with_graph(self, graph: StateGraph, **kwargs) -> None:
        """Integrate vector retrieval capability with a graph.

        Args:
            graph: The graph to integrate with
            **kwargs: Additional arguments
        """
        # Modify the graph to include vector retrieval
        # This is specific to the VectorReactWorkflow
        pass

    def _create_graph(self) -> StateGraph:
        """Create the VectorReact workflow graph."""
        tool_node = ToolNode(self.tools)

        def should_continue(state: VectorReactState) -> str:
            messages = state["messages"]
            last_message = messages[-1]
            result = "tools" if last_message.tool_calls else END
            logger.debug(f"Continue decision: {result}")
            return result

        async def retrieve_from_vector_store(state: VectorReactState) -> Dict:
            """Retrieve relevant documents from vector store."""
            messages = state["messages"]
            # Get the last user message
            last_user_message = None
            for message in reversed(messages):
                if isinstance(message, HumanMessage):
                    last_user_message = message.content
                    break

            if not last_user_message:
                logger.warning("No user message found for vector retrieval")
                return {"vector_results": []}

            documents = await self.retrieve_from_vector_store(query=last_user_message)
            return {"vector_results": documents}

        def call_model_with_context(state: VectorReactState) -> Dict:
            """Call model with additional context from vector store."""
            messages = state["messages"]
            vector_results = state.get("vector_results", [])

            # Add vector context to the system message if available
            context_message = None

            if vector_results:
                # Format the vector results into a context string
                context_str = "\n\n".join([doc.page_content for doc in vector_results])
                context_message = SystemMessage(
                    content=f"Here is additional context that may be helpful:\n\n{context_str}\n\n"
                    "Use this context to inform your response if relevant."
                )
                messages = [context_message] + messages

            logger.debug(
                f"Calling model with {len(messages)} messages and "
                f"{len(vector_results)} retrieved documents"
            )

            response = self.llm.invoke(messages)
            return {"messages": [response]}

        workflow = StateGraph(VectorReactState)
        workflow.add_node("vector_retrieval", retrieve_from_vector_store)
        workflow.add_node("agent", call_model_with_context)
        workflow.add_node("tools", tool_node)

        # Set up the execution flow
        workflow.add_edge(START, "vector_retrieval")
        workflow.add_edge("vector_retrieval", "agent")
        workflow.add_conditional_edges("agent", should_continue)
        workflow.add_edge("tools", "agent")

        return workflow


class VectorLangGraphService:
    """Service for executing VectorReact LangGraph operations"""

    def __init__(self, collection_name: str, embeddings: Optional[Embeddings] = None):
        # Import here to avoid circular imports
        from services.workflows.react import MessageProcessor

        self.collection_name = collection_name
        self.embeddings = embeddings or OpenAIEmbeddings()
        self.message_processor = MessageProcessor()

    def setup_callback_handler(self, queue, loop):
        # Import here to avoid circular dependencies
        from services.workflows.workflow_service import BaseWorkflowService

        # Use the static method instead of instantiating BaseWorkflowService
        return BaseWorkflowService.create_callback_handler(queue, loop)

    async def stream_task_results(self, task, queue):
        # Import here to avoid circular dependencies
        from services.workflows.workflow_service import BaseWorkflowService

        # Use the static method instead of instantiating BaseWorkflowService
        async for chunk in BaseWorkflowService.stream_results_from_task(
            task=task, callback_queue=queue, logger_name=self.__class__.__name__
        ):
            yield chunk

    async def _execute_stream_impl(
        self,
        messages: List[Union[SystemMessage, HumanMessage, AIMessage]],
        input_str: str,
        persona: Optional[str] = None,
        tools_map: Optional[Dict] = None,
        **kwargs,
    ) -> AsyncGenerator[Dict, None]:
        """Execute a Vector React stream implementation.

        Args:
            messages: Processed messages
            input_str: Current user input
            persona: Optional persona to use
            tools_map: Optional tools to use
            **kwargs: Additional arguments

        Returns:
            Async generator of result chunks
        """
        try:
            # Import here to avoid circular dependencies
            from services.workflows.workflow_service import WorkflowBuilder

            # Setup queue and callbacks
            callback_queue = asyncio.Queue()
            loop = asyncio.get_running_loop()

            # Setup callback handler
            callback_handler = self.setup_callback_handler(callback_queue, loop)

            # Create workflow using builder pattern
            workflow = (
                WorkflowBuilder(VectorReactWorkflow)
                .with_callback_handler(callback_handler)
                .with_tools(list(tools_map.values()) if tools_map else [])
                .build(
                    collection_name=self.collection_name,
                    embeddings=self.embeddings,
                )
            )

            # Create graph and compile
            graph = workflow._create_graph()
            runnable = graph.compile()

            # Execute workflow with callbacks config
            config = {"callbacks": [callback_handler]}
            task = asyncio.create_task(
                runnable.ainvoke(
                    {"messages": messages, "vector_results": []}, config=config
                )
            )

            # Stream results
            async for chunk in self.stream_task_results(task, callback_queue):
                yield chunk

        except Exception as e:
            logger.error(
                f"Failed to execute VectorReact stream: {str(e)}", exc_info=True
            )
            raise ExecutionError(f"VectorReact stream execution failed: {str(e)}")

    # Add execute_stream method to maintain the same interface as BaseWorkflowService
    async def execute_stream(
        self,
        history: List[Dict],
        input_str: str,
        persona: Optional[str] = None,
        tools_map: Optional[Dict] = None,
        **kwargs,
    ) -> AsyncGenerator[Dict, None]:
        """Execute a workflow stream.

        This processes the history and delegates to _execute_stream_impl.
        """
        # Process messages
        filtered_content = self.message_processor.extract_filtered_content(history)
        messages = self.message_processor.convert_to_langchain_messages(
            filtered_content, input_str, persona
        )

        # Call the implementation
        async for chunk in self._execute_stream_impl(
            messages=messages,
            input_str=input_str,
            persona=persona,
            tools_map=tools_map,
            **kwargs,
        ):
            yield chunk

    # Keep the old method for backward compatibility
    async def execute_vector_react_stream(
        self,
        history: List[Dict],
        input_str: str,
        persona: Optional[str] = None,
        tools_map: Optional[Dict] = None,
    ) -> AsyncGenerator[Dict, None]:
        """Execute a VectorReact stream using LangGraph."""
        # Call the new method
        async for chunk in self.execute_stream(history, input_str, persona, tools_map):
            yield chunk


# Helper function for adding documents to vector store
async def add_documents_to_vectors(
    collection_name: str,
    documents: List[Document],
    embeddings: Optional[Embeddings] = None,
) -> List[str]:
    """Add documents to vector collection.

    Args:
        collection_name: Name of the collection to add to
        documents: List of LangChain Document objects
        embeddings: Optional embeddings model to use

    Returns:
        List of document IDs
    """
    # Ensure embeddings model is provided
    if embeddings is None:
        raise ValueError(
            "Embeddings model must be provided to add documents to vector store"
        )

    # Ensure collection exists
    try:
        backend.get_vector_collection(collection_name)
    except Exception:
        # Create collection if it doesn't exist
        embed_dim = 1536  # Default for OpenAI embeddings
        if hasattr(embeddings, "embedding_dim"):
            embed_dim = embeddings.embedding_dim
        backend.create_vector_collection(collection_name, dimensions=embed_dim)

    # Extract texts for embedding
    texts = [doc.page_content for doc in documents]

    # Generate embeddings for the texts
    embedding_vectors = embeddings.embed_documents(texts)

    # Prepare documents for storage with embeddings
    docs_for_storage = [
        {"page_content": doc.page_content, "embedding": embedding_vectors[i]}
        for i, doc in enumerate(documents)
    ]

    # Prepare metadata
    metadata_list = [doc.metadata for doc in documents]

    # Add to vector store
    ids = await backend.add_vectors(
        collection_name=collection_name,
        documents=docs_for_storage,
        metadata=metadata_list,
    )

    return ids


# Facade function for backward compatibility
async def execute_vector_langgraph_stream(
    collection_name: str,
    history: List[Dict],
    input_str: str,
    persona: Optional[str] = None,
    tools_map: Optional[Dict] = None,
    embeddings: Optional[Embeddings] = None,
) -> AsyncGenerator[Dict, None]:
    """Execute a VectorReact stream using LangGraph with vector store integration."""
    # Initialize service and run stream
    embeddings = embeddings or OpenAIEmbeddings()
    service = VectorLangGraphService(
        collection_name=collection_name,
        embeddings=embeddings,
    )

    async for chunk in service.execute_stream(history, input_str, persona, tools_map):
        yield chunk
