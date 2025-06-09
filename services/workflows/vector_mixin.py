from typing import Any, Dict, List, Optional

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langgraph.graph import StateGraph

from backend.factory import backend
from lib.logger import configure_logger
from services.workflows.base import BaseWorkflowMixin
from services.workflows.enhanced_embeddings import create_embedding_strategy
from services.workflows.hybrid_search import HybridSearchEngine, SearchResult

logger = configure_logger(__name__)


class VectorRetrievalCapability(BaseWorkflowMixin):
    """Mixin that adds vector retrieval capabilities to a workflow."""

    def __init__(self, *args, **kwargs):
        """Initialize the vector retrieval capability."""
        super().__init__(*args, **kwargs) if hasattr(super(), "__init__") else None
        self._init_vector_retrieval()

    def _init_vector_retrieval(self) -> None:
        """Initialize vector retrieval attributes if not already initialized."""
        if not hasattr(self, "collection_names"):
            self.collection_names = [
                "knowledge_collection",
                "dao_collection",
                "proposals",
            ]
        if not hasattr(self, "embeddings"):
            # Use enhanced embedding strategy
            self.embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
            self.embedding_strategy = create_embedding_strategy("adaptive")
        if not hasattr(self, "vector_results_cache"):
            self.vector_results_cache = {}
        if not hasattr(self, "hybrid_search_engine"):
            self.hybrid_search_engine = HybridSearchEngine(
                collection_names=self.collection_names,
                embeddings=self.embeddings,
                vector_weight=0.7,
                keyword_weight=0.3,
            )

    async def retrieve_from_vector_store(self, query: str, **kwargs) -> List[Document]:
        """Retrieve relevant documents from multiple vector stores.

        Args:
            query: The query to search for
            **kwargs: Additional arguments (collection_name, embeddings, etc.)

        Returns:
            List of retrieved documents
        """
        try:
            self._init_vector_retrieval()
            if query in self.vector_results_cache:
                logger.debug(f"Using cached vector results for query: {query}")
                return self.vector_results_cache[query]
            all_documents = []
            limit_per_collection = kwargs.get("limit", 4)
            logger.debug(
                f"Searching vector store: query={query} | limit_per_collection={limit_per_collection}"
            )
            for collection_name in self.collection_names:
                try:
                    vector_results = await backend.query_vectors(
                        collection_name=collection_name,
                        query_text=query,
                        limit=limit_per_collection,
                        embeddings=self.embeddings,
                    )
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
                    continue
            logger.debug(
                f"Retrieved total of {len(all_documents)} documents from all collections"
            )
            self.vector_results_cache[query] = all_documents
            return all_documents
        except Exception as e:
            logger.error(f"Vector store retrieval failed: {str(e)}", exc_info=True)
            return []

    async def hybrid_retrieve(self, query: str, **kwargs) -> List[Document]:
        """Retrieve documents using hybrid search (vector + keyword)."""
        try:
            self._init_vector_retrieval()

            # Check cache first
            cache_key = f"hybrid_{query}"
            if cache_key in self.vector_results_cache:
                logger.debug(f"Using cached hybrid results for query: {query}")
                return self.vector_results_cache[cache_key]

            limit = kwargs.pop("limit", 10)

            # Perform hybrid search
            search_results = await self.hybrid_search_engine.hybrid_search(
                query=query, limit=limit, **kwargs
            )

            # Convert SearchResult objects back to Documents
            documents = [result.document for result in search_results]

            # Add search metadata to documents
            for i, (doc, result) in enumerate(zip(documents, search_results)):
                doc.metadata.update(
                    {
                        "search_rank": result.rank,
                        "vector_score": result.vector_score,
                        "keyword_score": result.keyword_score,
                        "combined_score": result.combined_score,
                        "search_method": "hybrid",
                    }
                )

            # Cache results
            self.vector_results_cache[cache_key] = documents

            logger.debug(f"Hybrid search returned {len(documents)} documents")
            return documents

        except Exception as e:
            logger.error(f"Hybrid search failed: {str(e)}", exc_info=True)
            # Fallback to regular vector search
            return await self.retrieve_from_vector_store(query, **kwargs)

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
        graph.add_node("vector_search", self.retrieve_from_vector_store)
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


async def add_documents_to_vectors(
    collection_name: str,
    documents: List[Document],
    embeddings: Optional[Any] = None,
) -> Dict[str, List[str]]:
    """Add documents to a vector collection.

    Args:
        collection_name: Name of the collection to add to
        documents: List of LangChain Document objects
        embeddings: Optional embeddings model to use

    Returns:
        Dictionary mapping collection name to list of document IDs
    """
    if embeddings is None:
        raise ValueError(
            "Embeddings model must be provided to add documents to vector store"
        )
    collection_doc_ids = {}
    try:
        try:
            backend.get_vector_collection(collection_name)
        except Exception:
            embed_dim = 1536
            if hasattr(embeddings, "embedding_dim"):
                embed_dim = embeddings.embedding_dim
            backend.create_vector_collection(collection_name, dimensions=embed_dim)
        texts = [doc.page_content for doc in documents]
        embedding_vectors = embeddings.embed_documents(texts)
        docs_for_storage = [
            {"page_content": doc.page_content, "embedding": embedding_vectors[i]}
            for i, doc in enumerate(documents)
        ]
        metadata_list = [doc.metadata for doc in documents]
        ids = await backend.add_vectors(
            collection_name=collection_name,
            documents=docs_for_storage,
            metadata=metadata_list,
        )
        collection_doc_ids[collection_name] = ids
        logger.info(f"Added {len(ids)} documents to collection {collection_name}")
    except Exception as e:
        logger.error(
            f"Failed to add documents to collection {collection_name}: {str(e)}"
        )
        collection_doc_ids[collection_name] = []
    return collection_doc_ids
