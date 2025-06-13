"""Proposal embedder task implementation."""

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
class ProposalEmbeddingResult(RunnerResult):
    """Result of proposal embedding operation."""

    proposals_processed: int = 0
    proposals_embedded: int = 0
    embeddings_successful: int = 0
    embeddings_failed: int = 0


@job(
    job_type="proposal_embedder",
    name="Proposal Embedder",
    description="Generates embeddings for new proposals with enhanced monitoring and error handling",
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
class ProposalEmbedderTask(BaseTask[ProposalEmbeddingResult]):
    """Task for generating embeddings for new proposals with enhanced capabilities."""

    def __init__(self, config: Optional[RunnerConfig] = None):
        super().__init__(config)
        self._proposals_without_embeddings = None
        self.embed_service = EmbedService()

    async def _validate_config(self, context: JobContext) -> bool:
        """Validate task configuration."""
        try:
            # Check if embedding service is available
            if not self.embed_service:
                logger.error("Embedding service not available")
                return False
            return True
        except Exception as e:
            logger.error(
                f"Error validating proposal embedder config: {str(e)}", exc_info=True
            )
            return False

    async def _validate_resources(self, context: JobContext) -> bool:
        """Validate resource availability for AI embeddings."""
        try:
            # Check backend connectivity
            backend.get_api_status()

            # Test embedding service
            try:
                test_result = await self.embed_service.embed_text("test")
                if not test_result:
                    logger.error("Embedding service test failed")
                    return False
            except Exception as e:
                logger.error(f"Embedding service validation failed: {str(e)}")
                return False

            return True
        except Exception as e:
            logger.error(f"Resource validation failed: {str(e)}")
            return False

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate task-specific conditions."""
        try:
            # Get proposals without embeddings
            proposals = backend.list_proposals(
                filters=ProposalFilter(has_embedding=False)
            )

            # Filter proposals that have actual content to embed
            proposals_without_embeddings = []
            for proposal in proposals:
                if proposal.description and proposal.description.strip():
                    proposals_without_embeddings.append(proposal)

            self._proposals_without_embeddings = proposals_without_embeddings

            if proposals_without_embeddings:
                logger.info(
                    f"Found {len(proposals_without_embeddings)} proposals needing embeddings"
                )
                return True

            logger.debug("No proposals needing embeddings found")
            return False

        except Exception as e:
            logger.error(
                f"Error validating proposal embedder task: {str(e)}", exc_info=True
            )
            self._proposals_without_embeddings = None
            return False

    async def _generate_embedding_for_proposal(
        self, proposal
    ) -> ProposalEmbeddingResult:
        """Generate embedding for a single proposal with enhanced error handling."""
        try:
            logger.info(
                f"Generating embedding for proposal: {proposal.title} ({proposal.id})"
            )

            # Prepare text content for embedding
            text_content = f"Title: {proposal.title}\n"
            if proposal.description:
                text_content += f"Description: {proposal.description}\n"

            # Additional context if available
            if hasattr(proposal, "summary") and proposal.summary:
                text_content += f"Summary: {proposal.summary}\n"

            logger.debug(
                f"Embedding text content (first 200 chars): {text_content[:200]}..."
            )

            # Generate embedding
            embedding = await self.embed_service.embed_text(text_content)

            if not embedding:
                error_msg = f"Failed to generate embedding for proposal {proposal.id}"
                logger.error(error_msg)
                return ProposalEmbeddingResult(
                    success=False,
                    message=error_msg,
                    proposals_processed=1,
                    proposals_embedded=0,
                    embeddings_failed=1,
                )

            # Update proposal with embedding
            proposal_update = ProposalBase(
                embedding=embedding,
                embedding_model=(
                    self.embed_service.model_name
                    if hasattr(self.embed_service, "model_name")
                    else "unknown"
                ),
            )

            updated_proposal = backend.update_proposal(proposal.id, proposal_update)
            if not updated_proposal:
                error_msg = f"Failed to save embedding for proposal {proposal.id}"
                logger.error(error_msg)
                return ProposalEmbeddingResult(
                    success=False,
                    message=error_msg,
                    proposals_processed=1,
                    proposals_embedded=0,
                    embeddings_failed=1,
                )

            logger.info(
                f"Successfully generated embedding for proposal: {proposal.title}"
            )
            logger.debug(f"Embedding dimension: {len(embedding)}")

            return ProposalEmbeddingResult(
                success=True,
                message=f"Successfully generated embedding for proposal {proposal.title}",
                proposals_processed=1,
                proposals_embedded=1,
                embeddings_successful=1,
            )

        except Exception as e:
            error_msg = (
                f"Error generating embedding for proposal {proposal.id}: {str(e)}"
            )
            logger.error(error_msg, exc_info=True)
            return ProposalEmbeddingResult(
                success=False,
                message=error_msg,
                error=e,
                proposals_processed=1,
                proposals_embedded=0,
                embeddings_failed=1,
            )

    def _should_retry_on_error(self, error: Exception, context: JobContext) -> bool:
        """Determine if error should trigger retry."""
        # Retry on network errors, AI service timeouts
        retry_errors = (
            ConnectionError,
            TimeoutError,
        )

        # Don't retry on content validation errors
        if "empty" in str(error).lower() or "no content" in str(error).lower():
            return False
        if "invalid embedding" in str(error).lower():
            return False

        return isinstance(error, retry_errors)

    async def _handle_execution_error(
        self, error: Exception, context: JobContext
    ) -> Optional[List[ProposalEmbeddingResult]]:
        """Handle execution errors with recovery logic."""
        if "ai" in str(error).lower() or "embedding" in str(error).lower():
            logger.warning(f"AI/embedding service error: {str(error)}, will retry")
            return None

        if isinstance(error, (ConnectionError, TimeoutError)):
            logger.warning(f"Network error: {str(error)}, will retry")
            return None

        # For validation errors, don't retry
        return [
            ProposalEmbeddingResult(
                success=False,
                message=f"Unrecoverable error: {str(error)}",
                error=error,
            )
        ]

    async def _post_execution_cleanup(
        self, context: JobContext, results: List[ProposalEmbeddingResult]
    ) -> None:
        """Cleanup after task execution."""
        # Clear cached proposals
        self._proposals_without_embeddings = None
        logger.debug("Proposal embedder task cleanup completed")

    async def _execute_impl(self, context: JobContext) -> List[ProposalEmbeddingResult]:
        """Execute proposal embedding task with batch processing."""
        results: List[ProposalEmbeddingResult] = []

        if not self._proposals_without_embeddings:
            logger.debug("No proposals needing embeddings to process")
            return [
                ProposalEmbeddingResult(
                    success=True,
                    message="No proposals require embedding generation",
                    proposals_processed=0,
                    proposals_embedded=0,
                )
            ]

        total_proposals = len(self._proposals_without_embeddings)
        processed_count = 0
        successful_embeddings = 0
        failed_embeddings = 0
        batch_size = getattr(context, "batch_size", 10)

        logger.info(f"Processing {total_proposals} proposals requiring embeddings")

        # Process proposals in batches
        for i in range(0, len(self._proposals_without_embeddings), batch_size):
            batch = self._proposals_without_embeddings[i : i + batch_size]

            for proposal in batch:
                logger.debug(
                    f"Generating embedding for proposal: {proposal.title} ({proposal.id})"
                )
                result = await self._generate_embedding_for_proposal(proposal)
                results.append(result)
                processed_count += 1

                if result.success:
                    successful_embeddings += 1
                    logger.debug(f"Successfully embedded proposal {proposal.title}")
                else:
                    failed_embeddings += 1
                    logger.error(
                        f"Failed to embed proposal {proposal.title}: {result.message}"
                    )

        logger.info(
            f"Proposal embedding completed - Processed: {processed_count}, "
            f"Successful: {successful_embeddings}, Failed: {failed_embeddings}"
        )

        return results


# Create instance for auto-registration
proposal_embedder = ProposalEmbedderTask()
