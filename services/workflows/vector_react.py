"""Vector-enabled ReAct workflow functionality with Supabase Vecs integration."""

import asyncio
from typing import Any, AsyncGenerator, Dict, List, Optional, TypedDict

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from backend.factory import backend
from lib.logger import configure_logger
from services.workflows.base import BaseWorkflow, ExecutionError
from services.workflows.react import (
    MessageProcessor,
    ReactState,
    StreamingCallbackHandler,
)

logger = configure_logger(__name__)


class VectorRetrievalState(TypedDict):
    """State for vector retrieval step."""

    query: str
    documents: List[Document]


class VectorReactState(ReactState):
    """State for the Vector ReAct workflow, extending ReactState."""

    vector_results: Optional[List[Document]]


class VectorReactWorkflow(BaseWorkflow[VectorReactState]):
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

        # Create a new LLM instance with the callback handler
        self.llm = ChatOpenAI(
            model=self.llm.model_name,
            temperature=self.llm.temperature,
            streaming=True,
            callbacks=[callback_handler],
        ).bind_tools(tools)

    def _create_prompt(self) -> None:
        """Not used in VectorReact workflow."""
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

            try:
                # Query vectors using the backend
                vector_results = await backend.query_vectors(
                    collection_name=self.collection_name,
                    query_text=last_user_message,
                    limit=4,
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
                return {"vector_results": documents}
            except Exception as e:
                logger.error(f"Vector store retrieval failed: {str(e)}")
                return {"vector_results": []}

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
        self.message_processor = MessageProcessor()
        self.collection_name = collection_name
        self.embeddings = embeddings or OpenAIEmbeddings()

    async def execute_vector_react_stream(
        self,
        history: List[Dict],
        input_str: str,
        persona: Optional[str] = None,
        tools_map: Optional[Dict] = None,
    ) -> AsyncGenerator[Dict, None]:
        """Execute a VectorReact stream using LangGraph."""
        logger.info("Starting new LangGraph VectorReact stream execution")
        logger.debug(
            f"Input parameters - History length: {len(history)}, "
            f"Persona present: {bool(persona)}, "
            f"Tools count: {len(tools_map) if tools_map else 0}"
        )

        try:
            callback_queue = asyncio.Queue()
            loop = asyncio.get_running_loop()

            # Process messages
            filtered_content = self.message_processor.extract_filtered_content(history)
            messages = self.message_processor.convert_to_langchain_messages(
                filtered_content, input_str, persona
            )

            # Setup callback handler
            callback_handler = StreamingCallbackHandler(
                queue=callback_queue,
                on_llm_new_token=lambda token, **kwargs: asyncio.run_coroutine_threadsafe(
                    callback_queue.put({"type": "token", "content": token}), loop
                ),
                on_llm_end=lambda *args, **kwargs: asyncio.run_coroutine_threadsafe(
                    callback_queue.put({"type": "end"}), loop
                ),
            )

            # Create workflow
            workflow = VectorReactWorkflow(
                callback_handler=callback_handler,
                tools=list(tools_map.values()) if tools_map else [],
                collection_name=self.collection_name,
                embeddings=self.embeddings,
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
            while not task.done():
                try:
                    data = await asyncio.wait_for(callback_queue.get(), timeout=0.1)
                    if data:
                        yield data
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    logger.error("Task cancelled unexpectedly")
                    task.cancel()
                    raise ExecutionError("Task cancelled unexpectedly")
                except Exception as e:
                    logger.error(f"Error in streaming loop: {str(e)}", exc_info=True)
                    raise ExecutionError(f"Streaming error: {str(e)}")

            # Get final result
            result = await task
            logger.info("Workflow execution completed successfully")
            logger.debug(
                f"Final result content length: {len(result['messages'][-1].content)}"
            )

            yield {
                "type": "result",
                "content": result["messages"][-1].content,
                "tokens": None,
            }

        except Exception as e:
            logger.error(
                f"Failed to execute VectorReact stream: {str(e)}", exc_info=True
            )
            raise ExecutionError(f"VectorReact stream execution failed: {str(e)}")


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
    except:
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


# Facade function for use
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

    async for chunk in service.execute_vector_react_stream(
        history, input_str, persona, tools_map
    ):
        yield chunk
