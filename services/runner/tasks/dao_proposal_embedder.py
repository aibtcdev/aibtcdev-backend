"""DAO proposal embedder task implementation."""

from dataclasses import dataclass
from typing import List, Optional

import openai
from langchain_openai import OpenAIEmbeddings

from backend.factory import backend
from backend.models import Proposal, ProposalBase, ProposalFilter
from config import config
from lib.logger import configure_logger
from services.runner.base import BaseTask, JobContext, RunnerConfig, RunnerResult
from services.runner.decorators import JobPriority, job

logger = configure_logger(__name__)

PROPOSAL_COLLECTION_NAME = "dao_proposals"
EMBEDDING_MODEL = "text-embedding-ada-002"


@dataclass
class DAOProposalEmbeddingResult(RunnerResult):
    """Result of DAO proposal embedding operation."""

    proposals_checked: int = 0
    proposals_embedded: int = 0
    errors: List[str] = None

    def __post_init__(self):
        self.errors = self.errors or []


@job(
    job_type="dao_proposal_embedder",
    name="DAO Proposal Embedder",
    description="Generates embeddings for new DAO proposals using vector store with delta processing",
    interval_seconds=120,  # 2 minutes
    priority=JobPriority.LOW,
    max_retries=3,
    retry_delay_seconds=60,
    timeout_seconds=180,
    max_concurrent=1,
    requires_ai=True,
    batch_size=10,
    enable_dead_letter_queue=True,
)
class DAOProposalEmbedderTask(BaseTask[DAOProposalEmbeddingResult]):
    """Task for generating embeddings for new DAO proposals with vector store storage."""

    def __init__(self, config: Optional[RunnerConfig] = None):
        super().__init__(config)
        self._proposals_to_embed = None

    async def _validate_config(self, context: JobContext) -> bool:
        """Validate DAO proposal embedder task configuration."""
        try:
            if not config.api.openai_api_key:
                logger.error(
                    "OpenAI API key not configured for DAO proposal embeddings"
                )
                return False
            if not backend.vecs_client:
                logger.error(
                    "Vector client (vecs) not initialized for DAO proposal embeddings"
                )
                return False
            return True
        except Exception as e:
            logger.error(
                f"Error validating DAO proposal embedder config: {str(e)}",
                exc_info=True,
            )
            return False

    async def _validate_resources(self, context: JobContext) -> bool:
        """Validate resource availability for DAO proposal embeddings."""
        try:
            # Test OpenAI embeddings
            try:
                embeddings_model = OpenAIEmbeddings(model=EMBEDDING_MODEL)
                test_embedding = await embeddings_model.aembed_query(
                    "test dao proposal"
                )
                if not test_embedding:
                    logger.error("OpenAI embeddings test failed for DAO proposals")
                    return False
            except Exception as e:
                logger.error(
                    f"DAO proposal embeddings service validation failed: {str(e)}"
                )
                return False

            return True
        except Exception as e:
            logger.error(f"DAO proposal embedding resource validation failed: {str(e)}")
            return False

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate DAO proposal embedder task-specific conditions (delta processing)."""
        try:
            # Get DAO proposals that haven't been embedded (delta processing)
            logger.info("Checking for DAO proposals that need embeddings...")
            dao_proposals = backend.list_proposals(
                filters=ProposalFilter(has_embedding=False)
            )

            logger.info(f"Found {len(dao_proposals)} DAO proposals without embeddings")

            # Filter DAO proposals that have actual content to embed
            proposals_to_embed = []
            for proposal in dao_proposals:
                if proposal.content and proposal.content.strip():
                    proposals_to_embed.append(proposal)
                else:
                    logger.debug(
                        f"Skipping DAO proposal {proposal.id} - no content to embed"
                    )

            self._proposals_to_embed = proposals_to_embed

            if proposals_to_embed:
                logger.info(
                    f"Found {len(proposals_to_embed)} DAO proposals with content needing embeddings (delta processing)"
                )
                return True

            logger.info(
                "No DAO proposals needing embeddings found - all are up to date"
            )
            return False

        except Exception as e:
            logger.error(
                f"Error validating DAO proposal embedder task: {str(e)}", exc_info=True
            )
            self._proposals_to_embed = None
            return False

    def _format_proposal_for_embedding(self, proposal: Proposal) -> str:
        """Format proposal data into a string for embedding."""
        parts = [
            f"DAO Proposal Title: {proposal.title or 'N/A'}",
            f"DAO Proposal Content: {proposal.content or 'N/A'}",
            f"DAO Proposal Type: {proposal.type.value if proposal.type else 'N/A'}",
        ]
        if proposal.action:
            parts.append(f"DAO Proposal Action: {proposal.action}")
        if proposal.summary:
            parts.append(f"DAO Proposal Summary: {proposal.summary}")
        return "\n".join(parts)

    async def _get_embeddings(self, texts: List[str]) -> Optional[List[List[float]]]:
        """Get embeddings for a list of texts using OpenAI API."""
        try:
            embeddings_model = OpenAIEmbeddings(model=EMBEDDING_MODEL)
            embeddings = await embeddings_model.aembed_documents(texts)
            return embeddings
        except Exception as e:
            logger.error(
                f"Error getting embeddings for DAO proposals: {str(e)}",
                exc_info=True,
            )
            return None

    def _should_retry_on_error(self, error: Exception, context: JobContext) -> bool:
        """Determine if DAO proposal embedding error should trigger retry."""
        retry_errors = (
            ConnectionError,
            TimeoutError,
        )

        # Don't retry on DAO proposal content validation errors
        if "empty" in str(error).lower() or "no content" in str(error).lower():
            return False
        if "api key" in str(error).lower():
            return False

        return isinstance(error, retry_errors)

    async def _handle_execution_error(
        self, error: Exception, context: JobContext
    ) -> Optional[List[DAOProposalEmbeddingResult]]:
        """Handle DAO proposal embedding execution errors with recovery logic."""
        if "openai" in str(error).lower() or "embedding" in str(error).lower():
            logger.warning(
                f"OpenAI/embedding service error for DAO proposals: {str(error)}, will retry"
            )
            return None

        if isinstance(error, (ConnectionError, TimeoutError)):
            logger.warning(
                f"Network error during DAO proposal embedding: {str(error)}, will retry"
            )
            return None

        return [
            DAOProposalEmbeddingResult(
                success=False,
                message=f"Unrecoverable DAO proposal embedding error: {str(error)}",
                errors=[str(error)],
            )
        ]

    async def _post_execution_cleanup(
        self, context: JobContext, results: List[DAOProposalEmbeddingResult]
    ) -> None:
        """Cleanup after DAO proposal embedding task execution."""
        self._proposals_to_embed = None
        logger.debug("DAO proposal embedder task cleanup completed")

    async def _execute_impl(
        self, context: JobContext
    ) -> List[DAOProposalEmbeddingResult]:
        """Execute DAO proposal embedding task with vector store storage (delta processing only)."""
        logger.info("Starting DAO proposal embedding task...")
        errors: List[str] = []
        proposals_checked = 0
        proposals_embedded = 0

        try:
            if not self._proposals_to_embed:
                logger.info(
                    "No DAO proposals needing embeddings to process - all proposals up to date"
                )
                return [
                    DAOProposalEmbeddingResult(
                        success=True,
                        message="No DAO proposals require embedding generation - all up to date",
                        proposals_checked=0,
                        proposals_embedded=0,
                    )
                ]

            # Ensure OpenAI client is configured
            openai.api_key = config.api.openai_api_key

            # Ensure the vector collection exists
            try:
                collection = backend.get_vector_collection(PROPOSAL_COLLECTION_NAME)
                logger.debug(
                    f"Using existing vector collection: {PROPOSAL_COLLECTION_NAME}"
                )
            except Exception:
                logger.info(
                    f"Collection '{PROPOSAL_COLLECTION_NAME}' not found, creating..."
                )
                collection = backend.create_vector_collection(PROPOSAL_COLLECTION_NAME)
                backend.create_vector_index(PROPOSAL_COLLECTION_NAME)
                logger.info(
                    f"Created new vector collection: {PROPOSAL_COLLECTION_NAME}"
                )

            proposals_to_embed = self._proposals_to_embed
            proposals_checked = len(proposals_to_embed)

            logger.info(
                f"DELTA PROCESSING: Processing {proposals_checked} DAO proposals requiring embeddings (only new/missing ones)"
            )

            # Prepare data for embedding only for new proposals
            texts_to_embed = []
            metadata_list = []
            proposal_ids = []

            for proposal in proposals_to_embed:
                proposal_text = self._format_proposal_for_embedding(proposal)
                texts_to_embed.append(proposal_text)
                metadata_list.append(
                    {
                        "proposal_id": str(proposal.id),
                        "title": proposal.title or "",
                        "dao_id": str(proposal.dao_id) if proposal.dao_id else "",
                        "type": proposal.type.value if proposal.type else "",
                        "created_at": (
                            proposal.created_at.isoformat()
                            if hasattr(proposal, "created_at")
                            else ""
                        ),
                    }
                )
                proposal_ids.append(str(proposal.id))

            # Get embeddings
            logger.info(
                f"Requesting embeddings for {len(texts_to_embed)} NEW DAO proposals"
            )
            embeddings_list = await self._get_embeddings(texts_to_embed)

            if embeddings_list is None:
                errors.append("Failed to retrieve embeddings for DAO proposals")
            else:
                logger.info(
                    f"Successfully retrieved {len(embeddings_list)} embeddings for DAO proposals"
                )

                # Prepare records for upsert
                records_to_upsert = []
                for i, proposal_id in enumerate(proposal_ids):
                    records_to_upsert.append(
                        (
                            proposal_id,  # Use proposal UUID as the vector ID
                            embeddings_list[i],  # Use the retrieved embeddings
                            metadata_list[i],
                        )
                    )

                # Upsert into the vector collection
                try:
                    collection.upsert(records=records_to_upsert)
                    proposals_embedded = len(records_to_upsert)
                    logger.info(
                        f"Successfully upserted {proposals_embedded} DAO proposal embeddings to vector store"
                    )

                    # Update proposals to mark them as embedded
                    for proposal in proposals_to_embed:
                        try:
                            update_data = ProposalBase(has_embedding=True)
                            backend.update_proposal(proposal.id, update_data)
                            logger.debug(
                                f"Marked DAO proposal {proposal.id} as embedded"
                            )
                        except Exception as e:
                            logger.error(
                                f"Failed to update has_embedding flag for proposal {proposal.id}: {str(e)}"
                            )
                            # Don't fail the entire task for this

                except Exception as e:
                    error_msg = f"Failed to upsert DAO proposal embeddings to vector store: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    errors.append(error_msg)

        except Exception as e:
            error_msg = f"Error during DAO proposal embedding task: {str(e)}"
            logger.error(error_msg, exc_info=True)
            errors.append(error_msg)

        success = not errors
        message = (
            f"DELTA PROCESSING COMPLETE - Checked {proposals_checked} DAO proposals, embedded {proposals_embedded} new ones in vector store"
            if success
            else f"DAO proposal embedding task failed. Errors: {'; '.join(errors)}"
        )

        return [
            DAOProposalEmbeddingResult(
                success=success,
                message=message,
                proposals_checked=proposals_checked,
                proposals_embedded=proposals_embedded,
                errors=errors,
            )
        ]


# Create instance for auto-registration
dao_proposal_embedder = DAOProposalEmbedderTask()
