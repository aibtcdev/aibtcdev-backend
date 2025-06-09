"""Enhanced proposal embedding task with advanced RAG strategies."""

from dataclasses import dataclass
from typing import List, Optional

import openai
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from backend.factory import backend
from backend.models import Proposal
from config import config
from lib.logger import configure_logger
from services.runner.base import BaseTask, JobContext, RunnerResult
from services.workflows.chunking_strategies import (
    AdaptiveChunkingStrategy,
    create_chunking_strategy,
)
from services.workflows.enhanced_embeddings import (
    ENHANCED_EMBEDDING_CONFIGS,
    create_embedding_strategy,
)

logger = configure_logger(__name__)

PROPOSAL_COLLECTION_NAME = "proposals"
# Use latest embedding model for better performance
EMBEDDING_MODEL = "text-embedding-3-large"


@dataclass
class ProposalEmbedderResult(RunnerResult):
    """Result of proposal embedding operation."""

    proposals_checked: int = 0
    proposals_embedded: int = 0
    errors: List[str] = None

    def __post_init__(self):
        self.errors = self.errors or []


class ProposalEmbedderTask(BaseTask[ProposalEmbedderResult]):
    """Task runner for embedding DAO proposals into a vector store."""

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate task-specific conditions."""
        if not config.api.openai_api_key:
            logger.warning("OpenAI API key is not configured. Skipping embedding.")
            return False
        if not backend.vecs_client:
            logger.warning("Vector client (vecs) not initialized. Skipping embedding.")
            return False
        # Basic check: Task runs if enabled and dependencies are met.
        # More sophisticated check could compare DB count vs vector store count.
        return True

    def _format_proposal_for_embedding(self, proposal: Proposal) -> Document:
        """Format proposal data into a LangChain Document with rich metadata."""
        # Create comprehensive content
        content_parts = []

        if proposal.title:
            content_parts.append(f"Title: {proposal.title}")

        if proposal.content:
            content_parts.append(f"Content: {proposal.content}")

        if proposal.type:
            content_parts.append(f"Type: {proposal.type.value}")

        if proposal.action:
            content_parts.append(f"Action: {proposal.action}")

        # Add contextual information
        if hasattr(proposal, "dao_id") and proposal.dao_id:
            content_parts.append(f"DAO ID: {proposal.dao_id}")

        content = "\n\n".join(content_parts)

        # Create rich metadata
        metadata = {
            "proposal_id": str(proposal.id),
            "title": proposal.title or "",
            "dao_id": str(proposal.dao_id) if proposal.dao_id else "",
            "type": proposal.type.value if proposal.type else "",
            "content_length": len(proposal.content or ""),
            "has_action": bool(proposal.action),
            "source": "proposal_database",
        }

        # Add timestamp information if available
        if hasattr(proposal, "created_at") and proposal.created_at:
            metadata["created_at"] = proposal.created_at.isoformat()

        return Document(page_content=content, metadata=metadata)

    async def _get_embeddings(self, texts: List[str]) -> Optional[List[List[float]]]:
        """Get embeddings for a list of texts using OpenAI API."""
        try:
            # Instantiate the embeddings model here
            embeddings_model = OpenAIEmbeddings(model=EMBEDDING_MODEL)
            # Use the embed_documents method
            embeddings = await embeddings_model.aembed_documents(texts)
            return embeddings
        except Exception as e:
            logger.error(
                f"Error getting embeddings using Langchain OpenAI: {str(e)}",
                exc_info=True,
            )
            return None

    async def _execute_impl(self, context: JobContext) -> List[ProposalEmbedderResult]:
        """Run the proposal embedding task."""
        logger.info("Starting proposal embedding task...")
        errors: List[str] = []
        proposals_checked = 0
        proposals_embedded = 0

        try:
            # Ensure OpenAI client is configured (Langchain uses this implicitly or explicitly)
            if not config.api.openai_api_key:
                raise ValueError("OpenAI API key not found in configuration.")
            openai.api_key = config.api.openai_api_key

            # Ensure the vector collection exists
            try:
                collection = backend.get_vector_collection(PROPOSAL_COLLECTION_NAME)
            except Exception:
                logger.info(
                    f"Collection '{PROPOSAL_COLLECTION_NAME}' not found, creating..."
                )
                # Assuming default dimensions are okay, or fetch from config/model
                collection = backend.create_vector_collection(PROPOSAL_COLLECTION_NAME)
                # Optionally create an index for better query performance
                backend.create_vector_index(PROPOSAL_COLLECTION_NAME)

            # Get all proposals from the database
            all_proposals = backend.list_proposals()
            proposals_checked = len(all_proposals)
            logger.debug(f"Found {proposals_checked} proposals in the database.")

            if not all_proposals:
                logger.info("No proposals found to embed.")
                return [
                    ProposalEmbedderResult(
                        success=True,
                        message="No proposals found.",
                        proposals_checked=0,
                        proposals_embedded=0,
                    )
                ]

            # Get IDs of proposals already in the vector store
            db_proposal_ids = {str(p.id) for p in all_proposals}
            existing_vector_ids = set()
            try:
                # Fetch existing records - assuming fetch returns tuples (id, vector, metadata)
                # We only need the IDs, fetch minimal data.
                # Note: Fetching potentially large lists of IDs might be inefficient
                # depending on the backend/library implementation.
                fetched_vectors = await backend.fetch_vectors(
                    collection_name=PROPOSAL_COLLECTION_NAME, ids=list(db_proposal_ids)
                )
                existing_vector_ids = {record[0] for record in fetched_vectors}
                logger.debug(
                    f"Found {len(existing_vector_ids)} existing proposal vectors out of {len(db_proposal_ids)} DB proposals."
                )
            except Exception as e:
                logger.warning(
                    f"Could not efficiently fetch existing vector IDs: {str(e)}. Proceeding may re-embed existing items."
                )
                # Fallback or decide how to handle - for now, we'll proceed cautiously
                # If fetch fails, we might end up embedding everything again if existing_vector_ids remains empty.

            # Identify proposals that need embedding
            new_proposal_ids = db_proposal_ids - existing_vector_ids
            if not new_proposal_ids:
                logger.debug("No new proposals found requiring embedding.")
                return [
                    ProposalEmbedderResult(
                        success=True,
                        message="No new proposals to embed.",
                        proposals_checked=proposals_checked,
                        proposals_embedded=0,
                    )
                ]

            logger.debug(f"Identified {len(new_proposal_ids)} new proposals to embed.")

            # Filter proposals to embed only the new ones
            proposals_to_embed = [
                p for p in all_proposals if str(p.id) in new_proposal_ids
            ]

            # Prepare documents for advanced processing
            documents_to_embed = []
            for proposal in proposals_to_embed:
                document = self._format_proposal_for_embedding(proposal)
                documents_to_embed.append(document)

            # Apply advanced chunking strategy
            chunking_strategy = create_chunking_strategy("adaptive")
            chunked_documents = []

            for document in documents_to_embed:
                chunks = chunking_strategy.chunk_document(document)
                chunked_documents.extend(chunks)

            logger.info(
                f"Created {len(chunked_documents)} chunks from {len(documents_to_embed)} proposals"
            )

            # Use enhanced embedding strategy
            embedding_strategy = create_embedding_strategy("adaptive")
            texts_to_embed = [doc.page_content for doc in chunked_documents]
            metadata_list = [doc.metadata for doc in chunked_documents]
            chunk_ids = [
                f"{doc.metadata.get('proposal_id', 'unknown')}_{doc.metadata.get('chunk_index', 0)}"
                for doc in chunked_documents
            ]

            # Get embeddings using the enhanced strategy
            logger.debug(f"Requesting embeddings for {len(texts_to_embed)} chunks.")
            try:
                embeddings_list = embedding_strategy.embed_documents(texts_to_embed)
                logger.debug(
                    f"Successfully retrieved {len(embeddings_list)} embeddings."
                )
            except Exception as e:
                logger.error(f"Failed to get embeddings: {e}")
                embeddings_list = None

            if embeddings_list is None:
                errors.append("Failed to retrieve embeddings.")
            else:
                # Prepare records for upsert
                records_to_upsert = []
                for i, chunk_id in enumerate(chunk_ids):
                    records_to_upsert.append(
                        (
                            chunk_id,  # Use chunk ID as the vector ID
                            embeddings_list[i],  # Use the retrieved embeddings
                            metadata_list[i],
                        )
                    )

                # Upsert into the vector collection
                try:
                    collection.upsert(records=records_to_upsert)
                    chunks_embedded = len(records_to_upsert)
                    proposals_embedded = len(proposals_to_embed)
                    logger.info(
                        f"Successfully upserted {chunks_embedded} chunks from {proposals_embedded} proposals."
                    )
                except Exception as e:
                    error_msg = f"Failed to upsert proposal embeddings: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    errors.append(error_msg)

        except Exception as e:
            error_msg = f"Error during proposal embedding task: {str(e)}"
            logger.error(error_msg, exc_info=True)
            errors.append(error_msg)

        success = not errors
        message = (
            f"Checked {proposals_checked} proposals, embedded/updated {proposals_embedded}."
            if success
            else f"Proposal embedding task failed. Errors: {'; '.join(errors)}"
        )

        return [
            ProposalEmbedderResult(
                success=success,
                message=message,
                proposals_checked=proposals_checked,
                proposals_embedded=proposals_embedded,
                errors=errors,
            )
        ]


# Instantiate the task for use in the registry
proposal_embedder = ProposalEmbedderTask()
