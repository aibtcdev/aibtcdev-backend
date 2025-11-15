"""DAO proposal embedder task implementation."""

from dataclasses import dataclass
from typing import List, Optional

import openai

from app.backend.factory import backend
from app.backend.models import Proposal, ProposalBase, ProposalFilter
from app.config import config
from app.lib.logger import configure_logger
from app.services.ai.simple_workflows.evaluation import create_embedding_model
from app.services.infrastructure.job_management.base import (
    BaseTask,
    JobContext,
    RunnerConfig,
    RunnerResult,
)
from app.services.infrastructure.job_management.decorators import JobPriority, job

logger = configure_logger(__name__)

PROPOSAL_COLLECTION_NAME = "dao_proposals"


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
            if not config.embedding.api_key:
                logger.error(
                    "Embedding API key not configured",
                    extra={"validation": "config"},
                )
                return False
            if not backend.vecs_client:
                logger.error(
                    "Vector client not initialized",
                    extra={"validation": "config"},
                )
                return False
            return True
        except Exception as e:
            logger.error(
                "Config validation failed",
                extra={"error": str(e)},
                exc_info=True,
            )
            return False

    async def _validate_resources(self, context: JobContext) -> bool:
        """Validate resource availability for DAO proposal embeddings."""
        try:
            # Test embeddings using configured model
            try:
                embeddings_model = create_embedding_model()
                test_embedding = await embeddings_model.aembed_query(
                    "test dao proposal"
                )
                if not test_embedding:
                    logger.error(
                        "Embeddings test failed",
                    )
                    return False
            except Exception as e:
                logger.error(
                    "Embeddings service validation failed",
                    extra={"error": str(e)},
                )
                return False

            return True
        except Exception as e:
            logger.error(
                "Resource validation failed",
                extra={"error": str(e)},
            )
            return False

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate DAO proposal embedder task-specific conditions (delta processing)."""
        try:
            # Get DAO proposals that haven't been embedded (delta processing)
            logger.debug(
                "Checking for proposals that need embeddings",
            )
            dao_proposals = backend.list_proposals(
                filters=ProposalFilter(has_embedding=False)
            )

            logger.debug(
                "Found proposals without embeddings",
                extra={"count": len(dao_proposals)},
            )

            # Filter DAO proposals that have actual content to embed
            proposals_to_embed = []
            for proposal in dao_proposals:
                if proposal.content and proposal.content.strip():
                    proposals_to_embed.append(proposal)
                else:
                    logger.debug(
                        "Skipping proposal - no content to embed",
                        extra={
                            "proposal_id": str(proposal.id),
                        },
                    )

            self._proposals_to_embed = proposals_to_embed

            if proposals_to_embed:
                logger.debug(
                    "Found proposals needing embeddings",
                    extra={
                        "count": len(proposals_to_embed),
                    },
                )
                return True

            logger.debug(
                "No proposals needing embeddings found",
            )
            return False

        except Exception as e:
            logger.error(
                "Error validating task",
                extra={"error": str(e)},
                exc_info=True,
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
        """Get embeddings for a list of texts using configured embedding model."""
        try:
            embeddings_model = create_embedding_model()
            embeddings = await embeddings_model.aembed_documents(texts)
            return embeddings
        except Exception as e:
            logger.error(
                "Error getting embeddings",
                extra={"error": str(e)},
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
                "OpenAI/embedding service error, will retry",
                extra={"error": str(error)},
            )
            return None

        if isinstance(error, (ConnectionError, TimeoutError)):
            logger.warning(
                "Network error, will retry",
                extra={"error": str(error)},
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
        logger.debug("Task cleanup completed")

    async def _execute_impl(
        self, context: JobContext
    ) -> List[DAOProposalEmbeddingResult]:
        """Execute DAO proposal embedding task with vector store storage (delta processing only)."""
        logger.debug(
            "Starting DAO proposal embedding task",
        )
        errors: List[str] = []
        proposals_checked = 0
        proposals_embedded = 0

        try:
            if not self._proposals_to_embed:
                logger.debug(
                    "No proposals needing embeddings to process",
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
            openai.api_key = config.embedding.api_key

            # Ensure the vector collection exists
            try:
                collection = backend.get_vector_collection(PROPOSAL_COLLECTION_NAME)
                logger.debug(
                    "Using existing vector collection",
                    extra={
                        "collection": PROPOSAL_COLLECTION_NAME,
                    },
                )
            except Exception:
                logger.info(
                    "Collection not found, creating",
                    extra={
                        "collection": PROPOSAL_COLLECTION_NAME,
                    },
                )
                collection = backend.create_vector_collection(
                    PROPOSAL_COLLECTION_NAME, dimensions=config.embedding.dimensions
                )
                backend.create_vector_index(PROPOSAL_COLLECTION_NAME)
                logger.info(
                    "Created new vector collection",
                    extra={
                        "collection": PROPOSAL_COLLECTION_NAME,
                    },
                )

            proposals_to_embed = self._proposals_to_embed
            proposals_checked = len(proposals_to_embed)

            logger.info(
                "Processing proposals requiring embeddings",
                extra={"count": proposals_checked},
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
                "Requesting embeddings for proposals",
                extra={
                    "count": len(texts_to_embed),
                    "model": config.embedding.default_model,
                },
            )
            embeddings_list = await self._get_embeddings(texts_to_embed)

            if embeddings_list is None:
                errors.append("Failed to retrieve embeddings for DAO proposals")
            else:
                logger.info(
                    "Successfully retrieved embeddings",
                    extra={
                        "count": len(embeddings_list),
                    },
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
                        "Successfully upserted embeddings to vector store",
                        extra={
                            "count": proposals_embedded,
                        },
                    )

                    # Update proposals to mark them as embedded
                    for proposal in proposals_to_embed:
                        try:
                            update_data = ProposalBase(has_embedding=True)
                            backend.update_proposal(proposal.id, update_data)
                            logger.debug(
                                "Marked proposal as embedded",
                                extra={
                                    "proposal_id": str(proposal.id),
                                },
                            )
                        except Exception as e:
                            logger.error(
                                "Failed to update has_embedding flag",
                                extra={
                                    "proposal_id": str(proposal.id),
                                    "error": str(e),
                                },
                            )
                            # Don't fail the entire task for this

                except Exception as e:
                    error_msg = f"Failed to upsert DAO proposal embeddings to vector store: {str(e)}"
                    logger.error(
                        "Failed to upsert embeddings to vector store",
                        extra={"error": str(e)},
                        exc_info=True,
                    )
                    errors.append(error_msg)

        except Exception as e:
            error_msg = f"Error during DAO proposal embedding task: {str(e)}"
            logger.error(
                "Error during embedding task",
                extra={"error": str(e)},
                exc_info=True,
            )
            errors.append(error_msg)

        success = not errors
        message = (
            f"Checked {proposals_checked} proposals, embedded {proposals_embedded} new ones"
            if success
            else f"Embedding task failed. Errors: {'; '.join(errors)}"
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
