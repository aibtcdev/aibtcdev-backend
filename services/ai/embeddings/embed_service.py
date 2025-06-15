"""Embedding service implementation."""

from typing import List, Optional

from langchain_openai import OpenAIEmbeddings

from config import config
from lib.logger import configure_logger

logger = configure_logger(__name__)

EMBEDDING_MODEL = "text-embedding-ada-002"


class EmbedService:
    """Service for generating text embeddings using OpenAI."""

    def __init__(self, model_name: str = EMBEDDING_MODEL):
        """Initialize the embedding service.

        Args:
            model_name: The OpenAI embedding model to use
        """
        self.model_name = model_name
        self._embeddings_client: Optional[OpenAIEmbeddings] = None

    @property
    def embeddings_client(self) -> OpenAIEmbeddings:
        """Get or create the OpenAI embeddings client."""
        if self._embeddings_client is None:
            if not config.api.openai_api_key:
                raise ValueError("OpenAI API key not configured")

            self._embeddings_client = OpenAIEmbeddings(
                model=self.model_name, openai_api_key=config.api.openai_api_key
            )
        return self._embeddings_client

    async def embed_text(self, text: str) -> Optional[List[float]]:
        """Generate embedding for a single text.

        Args:
            text: The text to embed

        Returns:
            List of floats representing the embedding, or None if failed
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return None

        try:
            logger.debug(f"Generating embedding for text (length: {len(text)})")
            embedding = await self.embeddings_client.aembed_query(text)
            logger.debug(f"Generated embedding with dimension: {len(embedding)}")
            return embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding: {str(e)}", exc_info=True)
            return None

    async def embed_documents(self, texts: List[str]) -> Optional[List[List[float]]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embeddings, or None if failed
        """
        if not texts:
            logger.warning("Empty text list provided for embedding")
            return None

        # Filter out empty texts
        valid_texts = [text for text in texts if text and text.strip()]
        if not valid_texts:
            logger.warning("No valid texts found for embedding")
            return None

        try:
            logger.debug(f"Generating embeddings for {len(valid_texts)} texts")
            embeddings = await self.embeddings_client.aembed_documents(valid_texts)
            logger.debug(f"Generated {len(embeddings)} embeddings")
            return embeddings
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {str(e)}", exc_info=True)
            return None

    def is_available(self) -> bool:
        """Check if the embedding service is available.

        Returns:
            True if the service is properly configured and available
        """
        try:
            return bool(config.api.openai_api_key)
        except Exception as e:
            logger.error(f"Error checking embedding service availability: {str(e)}")
            return False

    async def test_connection(self) -> bool:
        """Test the embedding service connection.

        Returns:
            True if the service is working correctly
        """
        try:
            test_embedding = await self.embed_text("test")
            return test_embedding is not None and len(test_embedding) > 0
        except Exception as e:
            logger.error(f"Embedding service test failed: {str(e)}")
            return False
