"""Hybrid search implementation combining vector and keyword search with reranking."""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings
from rank_bm25 import BM25Okapi

from backend.factory import backend
from lib.logger import configure_logger

logger = configure_logger(__name__)


@dataclass
class SearchResult:
    """Enhanced search result with scoring information."""

    document: Document
    vector_score: float
    keyword_score: float
    combined_score: float
    rank: int


class Reranker(ABC):
    """Abstract base class for reranking strategies."""

    @abstractmethod
    def rerank(
        self, query: str, results: List[SearchResult], **kwargs
    ) -> List[SearchResult]:
        """Rerank search results based on relevance."""
        pass


class SemanticReranker(Reranker):
    """Rerank results based on semantic similarity with the query."""

    def __init__(self, embeddings: Optional[Embeddings] = None):
        self.embeddings = embeddings or OpenAIEmbeddings(model="text-embedding-3-large")

    def rerank(
        self, query: str, results: List[SearchResult], **kwargs
    ) -> List[SearchResult]:
        """Rerank based on semantic similarity."""
        if not results:
            return results

        try:
            # Get query embedding
            query_embedding = self.embeddings.embed_query(query)

            # Get document embeddings
            texts = [result.document.page_content for result in results]
            doc_embeddings = self.embeddings.embed_documents(texts)

            # Calculate semantic similarities
            similarities = []
            for doc_embedding in doc_embeddings:
                similarity = self._cosine_similarity(query_embedding, doc_embedding)
                similarities.append(similarity)

            # Update scores and rerank
            reranked_results = []
            for i, result in enumerate(results):
                semantic_score = similarities[i]
                # Combine with existing score
                new_score = 0.7 * semantic_score + 0.3 * result.combined_score

                reranked_result = SearchResult(
                    document=result.document,
                    vector_score=result.vector_score,
                    keyword_score=result.keyword_score,
                    combined_score=new_score,
                    rank=result.rank,
                )
                reranked_results.append(reranked_result)

            # Sort by new combined score
            reranked_results.sort(key=lambda x: x.combined_score, reverse=True)

            # Update ranks
            for i, result in enumerate(reranked_results):
                result.rank = i + 1

            return reranked_results

        except Exception as e:
            logger.error(f"Semantic reranking failed: {e}")
            return results

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        vec1_np = np.array(vec1)
        vec2_np = np.array(vec2)

        dot_product = np.dot(vec1_np, vec2_np)
        norm1 = np.linalg.norm(vec1_np)
        norm2 = np.linalg.norm(vec2_np)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)


class MetadataReranker(Reranker):
    """Rerank results based on metadata relevance."""

    def __init__(self, metadata_weights: Optional[Dict[str, float]] = None):
        self.metadata_weights = metadata_weights or {
            "title": 0.3,
            "type": 0.2,
            "dao_id": 0.15,
            "keywords": 0.25,
            "recency": 0.1,
        }

    def rerank(
        self, query: str, results: List[SearchResult], **kwargs
    ) -> List[SearchResult]:
        """Rerank based on metadata relevance."""
        if not results:
            return results

        query_lower = query.lower()

        reranked_results = []
        for result in results:
            metadata_score = self._calculate_metadata_score(
                query_lower, result.document.metadata
            )

            # Combine with existing score
            new_score = 0.6 * result.combined_score + 0.4 * metadata_score

            reranked_result = SearchResult(
                document=result.document,
                vector_score=result.vector_score,
                keyword_score=result.keyword_score,
                combined_score=new_score,
                rank=result.rank,
            )
            reranked_results.append(reranked_result)

        # Sort by new combined score
        reranked_results.sort(key=lambda x: x.combined_score, reverse=True)

        # Update ranks
        for i, result in enumerate(reranked_results):
            result.rank = i + 1

        return reranked_results

    def _calculate_metadata_score(self, query: str, metadata: Dict[str, Any]) -> float:
        """Calculate relevance score based on metadata."""
        total_score = 0.0
        total_weight = 0.0

        for field, weight in self.metadata_weights.items():
            if field in metadata and metadata[field]:
                field_score = self._calculate_field_score(query, metadata[field])
                total_score += field_score * weight
                total_weight += weight

        return total_score / total_weight if total_weight > 0 else 0.0

    def _calculate_field_score(self, query: str, field_value: Any) -> float:
        """Calculate score for a specific metadata field."""
        if not field_value:
            return 0.0

        field_text = str(field_value).lower()

        # Simple keyword matching
        query_words = set(query.split())
        field_words = set(field_text.split())

        if not query_words:
            return 0.0

        overlap = query_words.intersection(field_words)
        return len(overlap) / len(query_words)


class HybridSearchEngine:
    """Hybrid search engine combining vector and keyword search."""

    def __init__(
        self,
        collection_names: List[str],
        embeddings: Optional[Embeddings] = None,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
    ):
        self.collection_names = collection_names
        self.embeddings = embeddings or OpenAIEmbeddings(model="text-embedding-3-large")
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight

    async def hybrid_search(
        self, query: str, limit: int = 10, **kwargs
    ) -> List[SearchResult]:
        """Perform hybrid search combining vector and keyword search."""
        logger.info(f"Performing hybrid search for query: '{query[:50]}...'")

        # Perform vector search
        vector_results = await self._vector_search(query, limit * 2)

        # For now, we'll use vector search as the primary method
        # Keyword search can be added later with BM25 or Elasticsearch

        # Convert to SearchResult format
        search_results = []
        for i, (doc, score) in enumerate(vector_results):
            search_result = SearchResult(
                document=doc,
                vector_score=score,
                keyword_score=0.0,  # TODO: Implement keyword scoring
                combined_score=score,
                rank=i + 1,
            )
            search_results.append(search_result)

        return search_results[:limit]

    async def _vector_search(
        self, query: str, limit: int
    ) -> List[Tuple[Document, float]]:
        """Perform vector similarity search."""
        all_results = []

        for collection_name in self.collection_names:
            try:
                results = await backend.query_vectors(
                    collection_name=collection_name,
                    query_text=query,
                    limit=limit // len(self.collection_names),
                    embeddings=self.embeddings,
                )

                for result in results:
                    doc = Document(
                        page_content=result.get("page_content", ""),
                        metadata={
                            **result.get("metadata", {}),
                            "collection_source": collection_name,
                        },
                    )
                    # Default score if not available
                    score = result.get("similarity", 0.5)
                    all_results.append((doc, score))

            except Exception as e:
                logger.error(
                    f"Vector search failed for collection {collection_name}: {e}"
                )
                continue

        return all_results

    def get_search_stats(self) -> Dict[str, Any]:
        """Get statistics about the search engine."""
        stats = {
            "collections": len(self.collection_names),
            "total_indexed_documents": 0,
            "collection_stats": {},
        }

        for collection_name in self.collection_names:
            docs_count = 0
            has_bm25 = False

            stats["collection_stats"][collection_name] = {
                "document_count": docs_count,
                "has_keyword_index": has_bm25,
            }

        return stats


# Factory function
def create_hybrid_search_engine(
    collection_names: List[str],
    embeddings: Optional[Embeddings] = None,
    search_config: Optional[Dict[str, Any]] = None,
) -> HybridSearchEngine:
    """Factory function to create a hybrid search engine."""

    config = search_config or {}

    # Create embeddings if not provided
    if embeddings is None:
        embeddings = OpenAIEmbeddings(
            model=config.get("embedding_model", "text-embedding-3-large"),
            dimensions=config.get("embedding_dimensions", 1536),
        )

    return HybridSearchEngine(
        collection_names=collection_names,
        embeddings=embeddings,
        vector_weight=config.get("vector_weight", 0.7),
        keyword_weight=config.get("keyword_weight", 0.3),
    )
