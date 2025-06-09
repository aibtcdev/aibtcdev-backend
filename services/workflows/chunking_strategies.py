"""Advanced chunking strategies for improved RAG performance."""

import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity

from lib.logger import configure_logger

logger = configure_logger(__name__)


class ChunkingStrategy(ABC):
    """Abstract base class for chunking strategies."""

    @abstractmethod
    def chunk_document(self, document: Document) -> List[Document]:
        """Chunk a document into smaller pieces."""
        pass


class FixedLengthChunkingStrategy(ChunkingStrategy):
    """Fixed-length chunking with configurable overlap."""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: Optional[List[str]] = None,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", ". ", " ", ""]
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=self.separators,
        )

    def chunk_document(self, document: Document) -> List[Document]:
        """Split document into fixed-length chunks."""
        chunks = self.text_splitter.split_documents([document])

        # Add chunk metadata
        for i, chunk in enumerate(chunks):
            chunk.metadata.update(
                {
                    "chunk_index": i,
                    "chunk_count": len(chunks),
                    "chunking_strategy": "fixed_length",
                    "parent_doc_id": document.metadata.get("id", "unknown"),
                }
            )

        return chunks


class SentenceBasedChunkingStrategy(ChunkingStrategy):
    """Sentence-based chunking that preserves logical flow."""

    def __init__(self, max_sentences_per_chunk: int = 10, overlap_sentences: int = 2):
        self.max_sentences_per_chunk = max_sentences_per_chunk
        self.overlap_sentences = overlap_sentences
        # Enhanced sentence boundary detection
        self.sentence_pattern = re.compile(
            r'(?<=[.!?])\s+(?=[A-Z])|(?<=[.!?"])\s+(?=[A-Z])|(?<=\.)\s+(?=\d)'
        )

    def chunk_document(self, document: Document) -> List[Document]:
        """Split document into sentence-based chunks."""
        text = document.page_content
        sentences = self.sentence_pattern.split(text)
        sentences = [s.strip() for s in sentences if s.strip()]

        chunks = []
        for i in range(
            0, len(sentences), self.max_sentences_per_chunk - self.overlap_sentences
        ):
            chunk_sentences = sentences[i : i + self.max_sentences_per_chunk]
            chunk_text = " ".join(chunk_sentences)

            chunk_metadata = document.metadata.copy()
            chunk_metadata.update(
                {
                    "chunk_index": len(chunks),
                    "sentence_start": i,
                    "sentence_end": min(
                        i + self.max_sentences_per_chunk, len(sentences)
                    ),
                    "chunking_strategy": "sentence_based",
                    "parent_doc_id": document.metadata.get("id", "unknown"),
                }
            )

            chunks.append(Document(page_content=chunk_text, metadata=chunk_metadata))

        return chunks


class SemanticChunkingStrategy(ChunkingStrategy):
    """Semantic chunking using embeddings to group related content."""

    def __init__(
        self,
        embeddings_model: Optional[Any] = None,
        similarity_threshold: float = 0.8,
        max_chunk_size: int = 1500,
        min_chunk_size: int = 200,
    ):
        self.embeddings_model = embeddings_model or OpenAIEmbeddings()
        self.similarity_threshold = similarity_threshold
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size
        self.sentence_splitter = SentenceBasedChunkingStrategy(
            max_sentences_per_chunk=3
        )

    def chunk_document(self, document: Document) -> List[Document]:
        """Split document into semantically coherent chunks."""
        # First, split into sentences
        sentence_chunks = self.sentence_splitter.chunk_document(document)

        if len(sentence_chunks) <= 1:
            return sentence_chunks

        # Get embeddings for each sentence chunk
        texts = [chunk.page_content for chunk in sentence_chunks]
        try:
            embeddings = self.embeddings_model.embed_documents(texts)
        except Exception as e:
            logger.warning(f"Failed to get embeddings for semantic chunking: {e}")
            return sentence_chunks

        # Group semantically similar sentences
        semantic_chunks = self._group_by_similarity(sentence_chunks, embeddings)

        # Add metadata
        for i, chunk in enumerate(semantic_chunks):
            chunk.metadata.update(
                {
                    "chunk_index": i,
                    "chunk_count": len(semantic_chunks),
                    "chunking_strategy": "semantic",
                    "parent_doc_id": document.metadata.get("id", "unknown"),
                }
            )

        return semantic_chunks

    def _group_by_similarity(
        self, chunks: List[Document], embeddings: List[List[float]]
    ) -> List[Document]:
        """Group chunks by semantic similarity."""
        if not embeddings:
            return chunks

        embeddings_array = np.array(embeddings)
        similarity_matrix = cosine_similarity(embeddings_array)

        semantic_groups = []
        used_indices = set()

        for i, chunk in enumerate(chunks):
            if i in used_indices:
                continue

            # Start a new semantic group
            group_chunks = [chunk]
            group_indices = {i}
            current_text_length = len(chunk.page_content)

            # Find similar chunks to add to this group
            for j in range(i + 1, len(chunks)):
                if j in used_indices:
                    continue

                similarity = similarity_matrix[i][j]
                next_chunk_length = len(chunks[j].page_content)

                # Add to group if similar and within size limits
                if (
                    similarity >= self.similarity_threshold
                    and current_text_length + next_chunk_length <= self.max_chunk_size
                ):
                    group_chunks.append(chunks[j])
                    group_indices.add(j)
                    current_text_length += next_chunk_length

            # Mark all chunks in this group as used
            used_indices.update(group_indices)

            # Create the combined chunk
            combined_text = " ".join([c.page_content for c in group_chunks])
            combined_metadata = chunks[i].metadata.copy()
            combined_metadata["semantic_group_size"] = len(group_chunks)

            semantic_groups.append(
                Document(page_content=combined_text, metadata=combined_metadata)
            )

        return semantic_groups


class SlidingWindowChunkingStrategy(ChunkingStrategy):
    """Sliding window chunking with overlap to maintain context."""

    def __init__(
        self,
        window_size: int = 1000,
        step_size: int = 500,
        preserve_sentences: bool = True,
    ):
        self.window_size = window_size
        self.step_size = step_size
        self.preserve_sentences = preserve_sentences

        if preserve_sentences:
            self.sentence_pattern = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")

    def chunk_document(self, document: Document) -> List[Document]:
        """Create overlapping chunks using sliding window."""
        text = document.page_content

        if self.preserve_sentences:
            return self._sliding_window_with_sentences(document, text)
        else:
            return self._sliding_window_character_based(document, text)

    def _sliding_window_with_sentences(
        self, document: Document, text: str
    ) -> List[Document]:
        """Sliding window that respects sentence boundaries."""
        sentences = self.sentence_pattern.split(text)
        sentences = [s.strip() for s in sentences if s.strip()]

        chunks = []
        current_pos = 0

        while current_pos < len(sentences):
            # Build chunk respecting sentence boundaries
            chunk_text = ""
            sentence_count = 0

            for i in range(current_pos, len(sentences)):
                candidate_text = (
                    chunk_text + " " + sentences[i] if chunk_text else sentences[i]
                )

                if len(candidate_text) <= self.window_size:
                    chunk_text = candidate_text
                    sentence_count += 1
                else:
                    break

            if chunk_text:
                chunk_metadata = document.metadata.copy()
                chunk_metadata.update(
                    {
                        "chunk_index": len(chunks),
                        "window_start": current_pos,
                        "window_end": current_pos + sentence_count,
                        "chunking_strategy": "sliding_window_sentences",
                        "parent_doc_id": document.metadata.get("id", "unknown"),
                    }
                )

                chunks.append(
                    Document(page_content=chunk_text, metadata=chunk_metadata)
                )

            # Move window by step size (in sentences)
            step_sentences = max(
                1, self.step_size // 100
            )  # Approximate step in sentences
            current_pos += step_sentences

        return chunks

    def _sliding_window_character_based(
        self, document: Document, text: str
    ) -> List[Document]:
        """Character-based sliding window."""
        chunks = []

        for start in range(0, len(text), self.step_size):
            end = min(start + self.window_size, len(text))
            chunk_text = text[start:end]

            chunk_metadata = document.metadata.copy()
            chunk_metadata.update(
                {
                    "chunk_index": len(chunks),
                    "char_start": start,
                    "char_end": end,
                    "chunking_strategy": "sliding_window_chars",
                    "parent_doc_id": document.metadata.get("id", "unknown"),
                }
            )

            chunks.append(Document(page_content=chunk_text, metadata=chunk_metadata))

        return chunks


class MetadataAugmentedChunkingStrategy(ChunkingStrategy):
    """Chunking strategy that enhances chunks with rich metadata."""

    def __init__(
        self,
        base_strategy: ChunkingStrategy,
        extract_keywords: bool = True,
        extract_entities: bool = True,
        add_summary: bool = True,
    ):
        self.base_strategy = base_strategy
        self.extract_keywords = extract_keywords
        self.extract_entities = extract_entities
        self.add_summary = add_summary

    def chunk_document(self, document: Document) -> List[Document]:
        """Enhance chunks with metadata."""
        base_chunks = self.base_strategy.chunk_document(document)

        enhanced_chunks = []
        for chunk in base_chunks:
            enhanced_metadata = chunk.metadata.copy()
            enhanced_metadata["chunking_strategy"] = "metadata_augmented"

            # Add document structure metadata
            if "title" in document.metadata:
                enhanced_metadata["document_title"] = document.metadata["title"]

            # Extract keywords (simple implementation)
            if self.extract_keywords:
                keywords = self._extract_keywords(chunk.page_content)
                enhanced_metadata["keywords"] = keywords

            # Add chunk summary (simplified)
            if self.add_summary:
                summary = self._create_summary(chunk.page_content)
                enhanced_metadata["summary"] = summary

            # Add text statistics
            enhanced_metadata.update(
                {
                    "char_count": len(chunk.page_content),
                    "word_count": len(chunk.page_content.split()),
                    "sentence_count": len(re.split(r"[.!?]+", chunk.page_content)),
                }
            )

            enhanced_chunks.append(
                Document(page_content=chunk.page_content, metadata=enhanced_metadata)
            )

        return enhanced_chunks

    def _extract_keywords(self, text: str) -> List[str]:
        """Simple keyword extraction."""
        # Remove common words and extract meaningful terms
        import string

        words = text.lower().split()
        words = [w.strip(string.punctuation) for w in words]

        # Simple filtering for meaningful keywords
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "as",
            "is",
            "was",
            "are",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "can",
            "this",
            "that",
            "these",
            "those",
            "i",
            "you",
            "he",
            "she",
            "it",
            "we",
            "they",
        }

        keywords = [w for w in words if len(w) > 3 and w not in stop_words]

        # Return top keywords by frequency
        from collections import Counter

        keyword_counts = Counter(keywords)
        return [word for word, _ in keyword_counts.most_common(10)]

    def _create_summary(self, text: str, max_length: int = 100) -> str:
        """Create a simple summary of the text."""
        sentences = re.split(r"[.!?]+", text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return ""

        # Take first sentence as summary, truncate if too long
        summary = sentences[0]
        if len(summary) > max_length:
            summary = summary[:max_length] + "..."

        return summary


class AdaptiveChunkingStrategy(ChunkingStrategy):
    """Adaptive chunking that chooses strategy based on document characteristics."""

    def __init__(self):
        self.strategies = {
            "short": FixedLengthChunkingStrategy(chunk_size=500, chunk_overlap=50),
            "medium": SemanticChunkingStrategy(),
            "long": SlidingWindowChunkingStrategy(window_size=1500, step_size=750),
            "structured": MetadataAugmentedChunkingStrategy(
                SentenceBasedChunkingStrategy()
            ),
        }

    def chunk_document(self, document: Document) -> List[Document]:
        """Choose and apply the best chunking strategy for the document."""
        text = document.page_content
        doc_length = len(text)

        # Simple heuristics for strategy selection
        if doc_length < 800:
            strategy = self.strategies["short"]
        elif self._is_structured_document(document):
            strategy = self.strategies["structured"]
        elif doc_length > 5000:
            strategy = self.strategies["long"]
        else:
            strategy = self.strategies["medium"]

        chunks = strategy.chunk_document(document)

        # Add adaptive strategy metadata
        for chunk in chunks:
            chunk.metadata["adaptive_strategy_used"] = strategy.__class__.__name__

        return chunks

    def _is_structured_document(self, document: Document) -> bool:
        """Detect if document has clear structure."""
        text = document.page_content

        # Look for structural indicators
        has_headers = bool(re.search(r"^(#+\s|\d+\.\s)", text, re.MULTILINE))
        has_bullets = bool(re.search(r"^[\s]*[-*•]\s", text, re.MULTILINE))
        has_sections = bool(re.search(r"\n\n[A-Z][^.]*:\n", text))

        return has_headers or has_bullets or has_sections


# Factory function for easy strategy creation
def create_chunking_strategy(
    strategy_type: str = "adaptive", **kwargs
) -> ChunkingStrategy:
    """Factory function to create chunking strategies."""

    strategies = {
        "fixed": FixedLengthChunkingStrategy,
        "sentence": SentenceBasedChunkingStrategy,
        "semantic": SemanticChunkingStrategy,
        "sliding": SlidingWindowChunkingStrategy,
        "metadata": lambda **kw: MetadataAugmentedChunkingStrategy(
            FixedLengthChunkingStrategy(**kw)
        ),
        "adaptive": AdaptiveChunkingStrategy,
    }

    if strategy_type not in strategies:
        raise ValueError(f"Unknown strategy type: {strategy_type}")

    strategy_class = strategies[strategy_type]
    return strategy_class(**kwargs)
