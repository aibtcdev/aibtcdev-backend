"""Enhanced embedding strategies for improved RAG performance."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union

import numpy as np
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from lib.logger import configure_logger

logger = configure_logger(__name__)


class EnhancedEmbeddingStrategy(ABC):
    """Abstract base class for enhanced embedding strategies."""

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents."""
        pass

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """Embed a query text."""
        pass


class MultiModelEmbeddingStrategy(EnhancedEmbeddingStrategy):
    """Use multiple embedding models and combine their outputs."""

    def __init__(
        self,
        primary_model: Optional[Embeddings] = None,
        secondary_models: Optional[List[Embeddings]] = None,
        combination_method: str = "average",
    ):
        # Use latest OpenAI embedding models
        self.primary_model = primary_model or OpenAIEmbeddings(
            model="text-embedding-3-large",  # Latest model with 3072 dimensions
            dimensions=1536,  # Can be reduced for better performance
        )

        self.secondary_models = secondary_models or [
            OpenAIEmbeddings(
                model="text-embedding-3-small",  # Smaller, faster model
                dimensions=512,
            )
        ]

        self.combination_method = combination_method

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed documents using multiple models and combine."""
        try:
            # Get embeddings from primary model
            primary_embeddings = self.primary_model.embed_documents(texts)

            if not self.secondary_models:
                return primary_embeddings

            # Get embeddings from secondary models
            all_embeddings = [primary_embeddings]

            for model in self.secondary_models:
                try:
                    secondary_embeddings = model.embed_documents(texts)
                    # Normalize dimensions if needed
                    normalized_embeddings = self._normalize_embeddings(
                        secondary_embeddings, target_dim=len(primary_embeddings[0])
                    )
                    all_embeddings.append(normalized_embeddings)
                except Exception as e:
                    logger.warning(f"Secondary model failed: {e}")
                    continue

            # Combine embeddings
            return self._combine_embeddings(all_embeddings)

        except Exception as e:
            logger.error(f"Multi-model embedding failed: {e}")
            # Fallback to primary model only
            return self.primary_model.embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        """Embed query using the same combination strategy."""
        embeddings = self.embed_documents([text])
        return embeddings[0] if embeddings else []

    def _normalize_embeddings(
        self, embeddings: List[List[float]], target_dim: int
    ) -> List[List[float]]:
        """Normalize embedding dimensions."""
        normalized = []
        for embedding in embeddings:
            if len(embedding) == target_dim:
                normalized.append(embedding)
            elif len(embedding) > target_dim:
                # Truncate
                normalized.append(embedding[:target_dim])
            else:
                # Pad with zeros
                padded = embedding + [0.0] * (target_dim - len(embedding))
                normalized.append(padded)
        return normalized

    def _combine_embeddings(
        self, embedding_lists: List[List[List[float]]]
    ) -> List[List[float]]:
        """Combine embeddings from multiple models."""
        if not embedding_lists:
            return []

        if len(embedding_lists) == 1:
            return embedding_lists[0]

        num_docs = len(embedding_lists[0])
        combined = []

        for doc_idx in range(num_docs):
            doc_embeddings = [emb_list[doc_idx] for emb_list in embedding_lists]

            if self.combination_method == "average":
                combined_embedding = np.mean(doc_embeddings, axis=0).tolist()
            elif self.combination_method == "weighted":
                # Give more weight to primary model
                weights = [0.7] + [0.3 / (len(doc_embeddings) - 1)] * (
                    len(doc_embeddings) - 1
                )
                combined_embedding = np.average(
                    doc_embeddings, axis=0, weights=weights
                ).tolist()
            elif self.combination_method == "concat":
                combined_embedding = []
                for emb in doc_embeddings:
                    combined_embedding.extend(emb)
            else:
                # Default to average
                combined_embedding = np.mean(doc_embeddings, axis=0).tolist()

            combined.append(combined_embedding)

        return combined


class ContextAwareEmbeddingStrategy(EnhancedEmbeddingStrategy):
    """Embeddings that consider document context and metadata."""

    def __init__(
        self,
        base_model: Optional[Embeddings] = None,
        include_metadata: bool = True,
        metadata_weight: float = 0.1,
    ):
        self.base_model = base_model or OpenAIEmbeddings(
            model="text-embedding-3-large",
            dimensions=1536,
        )
        self.include_metadata = include_metadata
        self.metadata_weight = metadata_weight

    def embed_documents_with_context(
        self, documents: List[Document]
    ) -> List[List[float]]:
        """Embed documents with their metadata context."""
        enhanced_texts = []

        for doc in documents:
            text = doc.page_content

            if self.include_metadata and doc.metadata:
                # Add relevant metadata to the text for embedding
                metadata_text = self._extract_metadata_text(doc.metadata)
                if metadata_text:
                    text = f"{text}\n\nContext: {metadata_text}"

            enhanced_texts.append(text)

        return self.base_model.embed_documents(enhanced_texts)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Standard embedding interface."""
        return self.base_model.embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        """Embed query text."""
        return self.base_model.embed_query(text)

    def _extract_metadata_text(self, metadata: Dict[str, Any]) -> str:
        """Extract relevant text from metadata."""
        relevant_fields = ["title", "summary", "keywords", "type", "category"]
        metadata_parts = []

        for field in relevant_fields:
            if field in metadata and metadata[field]:
                value = metadata[field]
                if isinstance(value, list):
                    value = ", ".join(str(v) for v in value)
                metadata_parts.append(f"{field}: {value}")

        return "; ".join(metadata_parts)


class HierarchicalEmbeddingStrategy(EnhancedEmbeddingStrategy):
    """Multi-level embeddings for different granularities."""

    def __init__(
        self,
        sentence_model: Optional[Embeddings] = None,
        paragraph_model: Optional[Embeddings] = None,
        document_model: Optional[Embeddings] = None,
    ):
        self.sentence_model = sentence_model or OpenAIEmbeddings(
            model="text-embedding-3-small", dimensions=512
        )
        self.paragraph_model = paragraph_model or OpenAIEmbeddings(
            model="text-embedding-3-large", dimensions=1024
        )
        self.document_model = document_model or OpenAIEmbeddings(
            model="text-embedding-3-large", dimensions=1536
        )

    def embed_hierarchical(
        self, documents: List[Document], level: str = "paragraph"
    ) -> List[List[float]]:
        """Embed at specified hierarchical level."""
        texts = [doc.page_content for doc in documents]

        if level == "sentence":
            return self.sentence_model.embed_documents(texts)
        elif level == "paragraph":
            return self.paragraph_model.embed_documents(texts)
        elif level == "document":
            return self.document_model.embed_documents(texts)
        else:
            raise ValueError(f"Unknown level: {level}")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Default to paragraph level."""
        return self.paragraph_model.embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        """Embed query at appropriate level based on length."""
        if len(text.split()) < 10:
            return self.sentence_model.embed_query(text)
        elif len(text.split()) < 50:
            return self.paragraph_model.embed_query(text)
        else:
            return self.document_model.embed_query(text)


class AdaptiveEmbeddingStrategy(EnhancedEmbeddingStrategy):
    """Adaptively choose embedding strategy based on content."""

    def __init__(self):
        self.multi_model = MultiModelEmbeddingStrategy()
        self.context_aware = ContextAwareEmbeddingStrategy()
        self.hierarchical = HierarchicalEmbeddingStrategy()

        # Cache for performance
        self._cache = {}

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Choose best embedding strategy based on content characteristics."""
        strategy = self._choose_strategy(texts)

        cache_key = f"{strategy.__class__.__name__}_{hash(tuple(texts))}"
        if cache_key in self._cache:
            logger.debug("Using cached embeddings")
            return self._cache[cache_key]

        embeddings = strategy.embed_documents(texts)
        self._cache[cache_key] = embeddings

        return embeddings

    def embed_query(self, text: str) -> List[float]:
        """Embed query using adaptive strategy."""
        strategy = self._choose_strategy([text])
        return strategy.embed_query(text)

    def _choose_strategy(self, texts: List[str]) -> EnhancedEmbeddingStrategy:
        """Choose the best embedding strategy for the given texts."""
        if not texts:
            return self.multi_model

        avg_length = sum(len(text.split()) for text in texts) / len(texts)
        has_structure = any(self._has_structure(text) for text in texts)

        if has_structure:
            return self.context_aware
        elif avg_length > 200:
            return self.hierarchical
        else:
            return self.multi_model

    def _has_structure(self, text: str) -> bool:
        """Detect if text has structural elements."""
        import re

        # Look for structural indicators
        has_headers = bool(re.search(r"^(#+\s|\d+\.\s)", text, re.MULTILINE))
        has_bullets = bool(re.search(r"^[\s]*[-*•]\s", text, re.MULTILINE))
        has_sections = bool(re.search(r"\n\n[A-Z][^.]*:\n", text))

        return has_headers or has_bullets or has_sections


# Factory function
def create_embedding_strategy(
    strategy_type: str = "adaptive", **kwargs
) -> EnhancedEmbeddingStrategy:
    """Factory function to create embedding strategies."""

    strategies = {
        "multi_model": MultiModelEmbeddingStrategy,
        "context_aware": ContextAwareEmbeddingStrategy,
        "hierarchical": HierarchicalEmbeddingStrategy,
        "adaptive": AdaptiveEmbeddingStrategy,
    }

    if strategy_type not in strategies:
        raise ValueError(f"Unknown strategy type: {strategy_type}")

    strategy_class = strategies[strategy_type]
    return strategy_class(**kwargs)


# Enhanced embedding models configuration
ENHANCED_EMBEDDING_CONFIGS = {
    "latest_openai": {
        "model": "text-embedding-3-large",
        "dimensions": 1536,
        "description": "Latest OpenAI embedding model with best performance",
    },
    "fast_openai": {
        "model": "text-embedding-3-small",
        "dimensions": 512,
        "description": "Faster OpenAI model for real-time applications",
    },
    "legacy_openai": {
        "model": "text-embedding-ada-002",
        "dimensions": 1536,
        "description": "Legacy model for compatibility",
    },
}
