"""DAO proposal embedder task implementation."""

from dataclasses import dataclass
from typing import List, Optional

from backend.factory import backend
from backend.models import ProposalBase, ProposalFilter
from lib.logger import configure_logger
from services.llm.embed import EmbedService
from services.runner.base import BaseTask, JobContext, RunnerConfig, RunnerResult
from services.runner.decorators import JobPriority, job

logger = configure_logger(__name__)


@dataclass
class DAOProposalEmbeddingResult(RunnerResult):
    """Result of DAO proposal embedding operation."""

    dao_proposals_processed: int = 0
    dao_proposals_embedded: int = 0
    embeddings_successful: int = 0
    embeddings_failed: int = 0


@job(
    job_type="dao_proposal_embedder",
    name="DAO Proposal Embedder",
    description="Generates embeddings for new DAO proposals with enhanced monitoring and error handling",
    interval_seconds=120,  # 2 minutes
    priority=JobPriority.LOW,
    max_retries=3,
    retry_delay_seconds=60,
    timeout_seconds=180,
    max_concurrent=3,
    requires_ai=True,
    batch_size=10,
    enable_dead_letter_queue=True,
)
class DAOProposalEmbedderTask(BaseTask[DAOProposalEmbeddingResult]):
    """Task for generating embeddings for new DAO proposals with enhanced capabilities."""

    def __init__(self, config: Optional[RunnerConfig] = None):
        super().__init__(config)
        self._dao_proposals_without_embeddings = None
        self.embed_service = EmbedService()

    async def _validate_config(self, context: JobContext) -> bool:
        """Validate DAO proposal embedder task configuration."""
        try:
            # Check if embedding service is available for DAO proposals
            if not self.embed_service:
                logger.error("Embedding service not available for DAO proposals")
                return False
            return True
        except Exception as e:
            logger.error(
                f"Error validating DAO proposal embedder config: {str(e)}",
                exc_info=True,
            )
            return False

    async def _validate_resources(self, context: JobContext) -> bool:
        """Validate resource availability for DAO proposal AI embeddings."""
        try:
            # Check backend connectivity
            backend.get_api_status()

            # Test embedding service for DAO proposals
            try:
                test_result = await self.embed_service.embed_text("test dao proposal")
                if not test_result:
                    logger.error("Embedding service test failed for DAO proposals")
                    return False
            except Exception as e:
                logger.error(
                    f"DAO proposal embedding service validation failed: {str(e)}"
                )
                return False

            return True
        except Exception as e:
            logger.error(f"DAO proposal embedding resource validation failed: {str(e)}")
            return False

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate DAO proposal embedder task-specific conditions."""
        try:
            # Get DAO proposals without embeddings
            dao_proposals = backend.list_proposals(
                filters=ProposalFilter(has_embedding=False)
            )

            # Filter DAO proposals that have actual content to embed
            dao_proposals_without_embeddings = []
            for proposal in dao_proposals:
                if proposal.description and proposal.description.strip():
                    dao_proposals_without_embeddings.append(proposal)

            self._dao_proposals_without_embeddings = dao_proposals_without_embeddings

            if dao_proposals_without_embeddings:
                logger.info(
                    f"Found {len(dao_proposals_without_embeddings)} DAO proposals needing embeddings"
                )
                return True

            logger.debug("No DAO proposals needing embeddings found")
            return False

        except Exception as e:
            logger.error(
                f"Error validating DAO proposal embedder task: {str(e)}", exc_info=True
            )
            self._dao_proposals_without_embeddings = None
            return False

    async def _generate_embedding_for_dao_proposal(
        self, dao_proposal
    ) -> DAOProposalEmbeddingResult:
        """Generate embedding for a single DAO proposal with enhanced error handling."""
        try:
            logger.info(
                f"Generating embedding for DAO proposal: {dao_proposal.title} ({dao_proposal.id})"
            )

            # Prepare text content for DAO proposal embedding
            text_content = f"DAO Proposal Title: {dao_proposal.title}\n"
            if dao_proposal.description:
                text_content += (
                    f"DAO Proposal Description: {dao_proposal.description}\n"
                )

            # Additional context if available for DAO proposal
            if hasattr(dao_proposal, "summary") and dao_proposal.summary:
                text_content += f"DAO Proposal Summary: {dao_proposal.summary}\n"

            logger.debug(
                f"DAO proposal embedding text content (first 200 chars): {text_content[:200]}..."
            )

            # Generate embedding for DAO proposal
            dao_proposal_embedding = await self.embed_service.embed_text(text_content)

            if not dao_proposal_embedding:
                error_msg = (
                    f"Failed to generate embedding for DAO proposal {dao_proposal.id}"
                )
                logger.error(error_msg)
                return DAOProposalEmbeddingResult(
                    success=False,
                    message=error_msg,
                    dao_proposals_processed=1,
                    dao_proposals_embedded=0,
                    embeddings_failed=1,
                )

            # Update DAO proposal with embedding
            dao_proposal_update = ProposalBase(
                embedding=dao_proposal_embedding,
                embedding_model=(
                    self.embed_service.model_name
                    if hasattr(self.embed_service, "model_name")
                    else "unknown"
                ),
            )

            updated_dao_proposal = backend.update_proposal(
                dao_proposal.id, dao_proposal_update
            )
            if not updated_dao_proposal:
                error_msg = (
                    f"Failed to save embedding for DAO proposal {dao_proposal.id}"
                )
                logger.error(error_msg)
                return DAOProposalEmbeddingResult(
                    success=False,
                    message=error_msg,
                    dao_proposals_processed=1,
                    dao_proposals_embedded=0,
                    embeddings_failed=1,
                )

            logger.info(
                f"Successfully generated embedding for DAO proposal: {dao_proposal.title}"
            )
            logger.debug(
                f"DAO proposal embedding dimension: {len(dao_proposal_embedding)}"
            )

            return DAOProposalEmbeddingResult(
                success=True,
                message=f"Successfully generated embedding for DAO proposal {dao_proposal.title}",
                dao_proposals_processed=1,
                dao_proposals_embedded=1,
                embeddings_successful=1,
            )

        except Exception as e:
            error_msg = f"Error generating embedding for DAO proposal {dao_proposal.id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return DAOProposalEmbeddingResult(
                success=False,
                message=error_msg,
                error=e,
                dao_proposals_processed=1,
                dao_proposals_embedded=0,
                embeddings_failed=1,
            )

    def _should_retry_on_error(self, error: Exception, context: JobContext) -> bool:
        """Determine if DAO proposal embedding error should trigger retry."""
        # Retry on network errors, AI service timeouts
        retry_errors = (
            ConnectionError,
            TimeoutError,
        )

        # Don't retry on DAO proposal content validation errors
        if "empty" in str(error).lower() or "no content" in str(error).lower():
            return False
        if "invalid embedding" in str(error).lower():
            return False

        return isinstance(error, retry_errors)

    async def _handle_execution_error(
        self, error: Exception, context: JobContext
    ) -> Optional[List[DAOProposalEmbeddingResult]]:
        """Handle DAO proposal embedding execution errors with recovery logic."""
        if "ai" in str(error).lower() or "embedding" in str(error).lower():
            logger.warning(
                f"AI/embedding service error for DAO proposals: {str(error)}, will retry"
            )
            return None

        if isinstance(error, (ConnectionError, TimeoutError)):
            logger.warning(
                f"Network error during DAO proposal embedding: {str(error)}, will retry"
            )
            return None

        # For DAO proposal validation errors, don't retry
        return [
            DAOProposalEmbeddingResult(
                success=False,
                message=f"Unrecoverable DAO proposal embedding error: {str(error)}",
                error=error,
            )
        ]

    async def _post_execution_cleanup(
        self, context: JobContext, results: List[DAOProposalEmbeddingResult]
    ) -> None:
        """Cleanup after DAO proposal embedding task execution."""
        # Clear cached DAO proposals
        self._dao_proposals_without_embeddings = None
        logger.debug("DAO proposal embedder task cleanup completed")

    async def _execute_impl(
        self, context: JobContext
    ) -> List[DAOProposalEmbeddingResult]:
        """Execute DAO proposal embedding task with batch processing."""
        results: List[DAOProposalEmbeddingResult] = []

        if not self._dao_proposals_without_embeddings:
            logger.debug("No DAO proposals needing embeddings to process")
            return [
                DAOProposalEmbeddingResult(
                    success=True,
                    message="No DAO proposals require embedding generation",
                    dao_proposals_processed=0,
                    dao_proposals_embedded=0,
                )
            ]

        total_dao_proposals = len(self._dao_proposals_without_embeddings)
        processed_count = 0
        successful_embeddings = 0
        failed_embeddings = 0
        batch_size = getattr(context, "batch_size", 10)

        logger.info(
            f"Processing {total_dao_proposals} DAO proposals requiring embeddings"
        )

        # Process DAO proposals in batches
        for i in range(0, len(self._dao_proposals_without_embeddings), batch_size):
            batch = self._dao_proposals_without_embeddings[i : i + batch_size]

            for dao_proposal in batch:
                logger.debug(
                    f"Generating embedding for DAO proposal: {dao_proposal.title} ({dao_proposal.id})"
                )
                result = await self._generate_embedding_for_dao_proposal(dao_proposal)
                results.append(result)
                processed_count += 1

                if result.success:
                    successful_embeddings += 1
                    logger.debug(
                        f"Successfully embedded DAO proposal {dao_proposal.title}"
                    )
                else:
                    failed_embeddings += 1
                    logger.error(
                        f"Failed to embed DAO proposal {dao_proposal.title}: {result.message}"
                    )

        logger.info(
            f"DAO proposal embedding completed - Processed: {processed_count}, "
            f"Successful: {successful_embeddings}, Failed: {failed_embeddings}"
        )

        return results


# Create instance for auto-registration
dao_proposal_embedder = DAOProposalEmbedderTask()
