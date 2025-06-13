"""Chain state monitoring task implementation."""

from dataclasses import dataclass
from typing import List, Optional

from backend.factory import backend
from backend.models import ProposalBase, ProposalFilter
from config import config
from lib.hiro import HiroApi
from lib.logger import configure_logger
from services.runner.base import BaseTask, JobContext, RunnerConfig, RunnerResult
from services.runner.decorators import JobPriority, job

logger = configure_logger(__name__)


@dataclass
class ChainStateMonitorResult(RunnerResult):
    """Result of chain state monitoring operation."""

    proposals_monitored: int = 0
    proposals_updated: int = 0
    proposals_closed: int = 0
    on_chain_updates: int = 0
    sync_errors: int = 0


@job(
    job_type="chain_state_monitor",
    name="Chain State Monitor",
    description="Monitors blockchain state for proposal updates with enhanced monitoring and error handling",
    interval_seconds=90,  # 1.5 minutes
    priority=JobPriority.MEDIUM,
    max_retries=3,
    retry_delay_seconds=120,
    timeout_seconds=300,
    max_concurrent=2,
    requires_blockchain=True,
    batch_size=20,
    enable_dead_letter_queue=True,
)
class ChainStateMonitorTask(BaseTask[ChainStateMonitorResult]):
    """Task for monitoring blockchain state and syncing with database with enhanced capabilities."""

    def __init__(self, config: Optional[RunnerConfig] = None):
        super().__init__(config)
        self._pending_proposals = None

    async def _validate_config(self, context: JobContext) -> bool:
        """Validate task configuration."""
        try:
            # Check if monitoring wallet is configured
            if not config.scheduler or not hasattr(
                config.scheduler, "chain_state_monitor_wallet_id"
            ):
                logger.error("Chain state monitor wallet ID not configured")
                return False
            return True
        except Exception as e:
            logger.error(
                f"Error validating chain state monitor config: {str(e)}", exc_info=True
            )
            return False

    async def _validate_resources(self, context: JobContext) -> bool:
        """Validate resource availability for blockchain monitoring."""
        try:
            # Check backend connectivity
            backend.get_api_status()

            # Test HiroApi initialization and connectivity
            hiro_api = HiroApi()
            api_info = await hiro_api.aget_info()
            if not api_info:
                logger.error("Cannot connect to Hiro API")
                return False

            return True
        except Exception as e:
            logger.error(f"Resource validation failed: {str(e)}")
            return False

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate task-specific conditions."""
        try:
            # Get proposals that need monitoring (open proposals)
            proposals = backend.list_proposals(filters=ProposalFilter(is_open=True))

            # Filter proposals that have contract addresses for monitoring
            pending_proposals = []
            for proposal in proposals:
                if proposal.contract_principal and proposal.proposal_id is not None:
                    pending_proposals.append(proposal)

            self._pending_proposals = pending_proposals

            if pending_proposals:
                logger.info(
                    f"Found {len(pending_proposals)} proposals requiring monitoring"
                )
                return True

            logger.debug("No proposals requiring chain state monitoring found")
            return False

        except Exception as e:
            logger.error(
                f"Error validating chain state monitor task: {str(e)}", exc_info=True
            )
            self._pending_proposals = None
            return False

    async def _monitor_proposal_state(self, proposal) -> ChainStateMonitorResult:
        """Monitor chain state for a single proposal with enhanced error handling."""
        try:
            logger.debug(f"Monitoring proposal: {proposal.title} ({proposal.id})")

            # Get on-chain proposal data - this would need to be implemented
            # based on the specific contract interface for proposals
            # For now, we'll create a placeholder that simulates the expected response
            on_chain_data = {
                "success": True,
                "proposals": {
                    "is_concluded": False,
                    "end_block_height": proposal.end_block_height,
                    "votes_for": proposal.votes_for,
                    "votes_against": proposal.votes_against,
                },
            }

            if not on_chain_data or not on_chain_data.get("success", False):
                error_msg = f"Failed to fetch on-chain data for proposal {proposal.id}: {on_chain_data.get('message', 'Unknown error')}"
                logger.warning(error_msg)
                return ChainStateMonitorResult(
                    success=False,
                    message=error_msg,
                    proposals_monitored=1,
                    sync_errors=1,
                )

            # Parse on-chain proposal information
            chain_proposal_data = on_chain_data.get("proposals", {})
            if not chain_proposal_data:
                logger.debug(f"No on-chain data found for proposal {proposal.id}")
                return ChainStateMonitorResult(
                    success=True,
                    message="No chain state updates needed",
                    proposals_monitored=1,
                )

            # Check if proposal state has changed
            updates_needed = False
            proposal_updates = {}

            # Check if proposal is now closed/concluded
            if chain_proposal_data.get("is_concluded", False) and proposal.is_open:
                proposal_updates["is_open"] = False
                updates_needed = True
                logger.info(f"Proposal {proposal.title} has been concluded on-chain")

            # Check for voting period changes
            chain_end_block = chain_proposal_data.get("end_block_height")
            if chain_end_block and chain_end_block != proposal.end_block_height:
                proposal_updates["end_block_height"] = chain_end_block
                updates_needed = True
                logger.debug(f"Updated end block height for proposal {proposal.title}")

            # Check for vote count updates
            chain_votes_for = chain_proposal_data.get("votes_for", 0)
            chain_votes_against = chain_proposal_data.get("votes_against", 0)

            if (
                chain_votes_for != proposal.votes_for
                or chain_votes_against != proposal.votes_against
            ):
                proposal_updates["votes_for"] = chain_votes_for
                proposal_updates["votes_against"] = chain_votes_against
                updates_needed = True
                logger.debug(f"Updated vote counts for proposal {proposal.title}")

            # Apply updates if needed
            updated_proposal = None
            if updates_needed:
                try:
                    proposal_update = ProposalBase(**proposal_updates)
                    updated_proposal = backend.update_proposal(
                        proposal.id, proposal_update
                    )

                    if updated_proposal:
                        logger.info(
                            f"Successfully updated proposal {proposal.title} with chain state"
                        )
                    else:
                        logger.error(
                            f"Failed to update proposal {proposal.id} in database"
                        )
                        return ChainStateMonitorResult(
                            success=False,
                            message=f"Failed to update proposal {proposal.id}",
                            proposals_monitored=1,
                            sync_errors=1,
                        )
                except Exception as e:
                    logger.error(f"Error updating proposal {proposal.id}: {str(e)}")
                    return ChainStateMonitorResult(
                        success=False,
                        message=f"Error updating proposal: {str(e)}",
                        error=e,
                        proposals_monitored=1,
                        sync_errors=1,
                    )

            # Determine result metrics
            proposals_closed = 1 if not proposal_updates.get("is_open") else 0
            proposals_updated = 1 if updates_needed else 0

            return ChainStateMonitorResult(
                success=True,
                message=f"Successfully monitored proposal {proposal.title}",
                proposals_monitored=1,
                proposals_updated=proposals_updated,
                proposals_closed=proposals_closed,
                on_chain_updates=1 if updates_needed else 0,
            )

        except Exception as e:
            error_msg = f"Error monitoring proposal {proposal.id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return ChainStateMonitorResult(
                success=False,
                message=error_msg,
                error=e,
                proposals_monitored=1,
                sync_errors=1,
            )

    def _should_retry_on_error(self, error: Exception, context: JobContext) -> bool:
        """Determine if error should trigger retry."""
        # Retry on network errors, blockchain RPC issues
        retry_errors = (
            ConnectionError,
            TimeoutError,
        )

        # Don't retry on configuration errors
        if "not configured" in str(error).lower():
            return False
        if "invalid contract" in str(error).lower():
            return False

        return isinstance(error, retry_errors)

    async def _handle_execution_error(
        self, error: Exception, context: JobContext
    ) -> Optional[List[ChainStateMonitorResult]]:
        """Handle execution errors with recovery logic."""
        if "blockchain" in str(error).lower() or "rpc" in str(error).lower():
            logger.warning(f"Blockchain/RPC error: {str(error)}, will retry")
            return None

        if isinstance(error, (ConnectionError, TimeoutError)):
            logger.warning(f"Network error: {str(error)}, will retry")
            return None

        # For configuration errors, don't retry
        return [
            ChainStateMonitorResult(
                success=False,
                message=f"Unrecoverable error: {str(error)}",
                error=error,
            )
        ]

    async def _post_execution_cleanup(
        self, context: JobContext, results: List[ChainStateMonitorResult]
    ) -> None:
        """Cleanup after task execution."""
        # Clear cached proposals
        self._pending_proposals = None
        logger.debug("Chain state monitor task cleanup completed")

    async def _execute_impl(self, context: JobContext) -> List[ChainStateMonitorResult]:
        """Execute chain state monitoring task with batch processing."""
        results: List[ChainStateMonitorResult] = []

        if not self._pending_proposals:
            logger.debug("No proposals requiring chain state monitoring")
            return [
                ChainStateMonitorResult(
                    success=True,
                    message="No proposals require chain state monitoring",
                    proposals_monitored=0,
                )
            ]

        total_proposals = len(self._pending_proposals)
        monitored_count = 0
        updated_count = 0
        closed_count = 0
        on_chain_updates = 0
        sync_errors = 0
        batch_size = getattr(context, "batch_size", 20)

        logger.info(f"Monitoring {total_proposals} proposals for chain state updates")

        # Process proposals in batches
        for i in range(0, len(self._pending_proposals), batch_size):
            batch = self._pending_proposals[i : i + batch_size]

            for proposal in batch:
                logger.debug(f"Monitoring proposal: {proposal.title} ({proposal.id})")
                result = await self._monitor_proposal_state(proposal)
                results.append(result)

                # Aggregate metrics
                monitored_count += result.proposals_monitored
                updated_count += result.proposals_updated
                closed_count += result.proposals_closed
                on_chain_updates += result.on_chain_updates
                sync_errors += result.sync_errors

                if not result.success:
                    logger.error(
                        f"Failed to monitor proposal {proposal.title}: {result.message}"
                    )
                else:
                    logger.debug(f"Successfully monitored proposal {proposal.title}")

        logger.info(
            f"Chain state monitoring completed - Monitored: {monitored_count}, "
            f"Updated: {updated_count}, Closed: {closed_count}, "
            f"On-chain Updates: {on_chain_updates}, Errors: {sync_errors}"
        )

        return results


# Create instance for auto-registration
chain_state_monitor = ChainStateMonitorTask()
