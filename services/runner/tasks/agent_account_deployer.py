"""Agent account deployment task implementation."""

from dataclasses import dataclass
from typing import List, Optional

from backend.factory import backend
from backend.models import (
    WalletCreate,
    WalletFilter,
)
from lib.logger import configure_logger
from services.runner.base import BaseTask, JobContext, RunnerConfig, RunnerResult
from services.runner.decorators import JobPriority, job
from tools.agent_account import AgentAccountDeployTool

logger = configure_logger(__name__)


@dataclass
class AgentAccountDeploymentResult(RunnerResult):
    """Result of agent account deployment operation."""

    agents_processed: int = 0
    wallets_created: int = 0
    wallets_successful: int = 0
    wallets_failed: int = 0


@job(
    job_type="agent_account_deployer",
    name="Agent Account Deployer",
    description="Deploys wallet accounts for new agents with enhanced monitoring and error handling",
    interval_seconds=300,  # 5 minutes
    priority=JobPriority.MEDIUM,
    max_retries=2,
    retry_delay_seconds=180,
    timeout_seconds=120,
    max_concurrent=1,
    requires_blockchain=True,
    batch_size=5,
    enable_dead_letter_queue=True,
)
class AgentAccountDeployerTask(BaseTask[AgentAccountDeploymentResult]):
    """Task for deploying wallet accounts for new agents with enhanced capabilities."""

    def __init__(self, config: Optional[RunnerConfig] = None):
        super().__init__(config)
        self._agents_without_wallets = None

    async def _validate_config(self, context: JobContext) -> bool:
        """Validate task configuration."""
        try:
            # Check if wallet generation tool is available
            return True
        except Exception as e:
            logger.error(
                f"Error validating agent account deployer config: {str(e)}",
                exc_info=True,
            )
            return False

    async def _validate_resources(self, context: JobContext) -> bool:
        """Validate resource availability."""
        try:
            # Check backend connectivity
            backend.get_api_status()

            # Test wallet generator tool initialization
            tool = AgentAccountDeployTool()
            if not tool:
                logger.error("Cannot initialize WalletGeneratorTool")
                return False

            return True
        except Exception as e:
            logger.error(f"Resource validation failed: {str(e)}")
            return False

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate task-specific conditions."""
        try:
            # Get agents without wallets
            agents = backend.list_agents()
            agents_without_wallets = []

            for agent in agents:
                # Check if agent already has a wallet
                wallets = backend.list_wallets(filters=WalletFilter(agent_id=agent.id))
                if not wallets:
                    agents_without_wallets.append(agent)

            self._agents_without_wallets = agents_without_wallets

            if agents_without_wallets:
                logger.info(
                    f"Found {len(agents_without_wallets)} agents without wallets"
                )
                return True

            logger.debug("No agents without wallets found")
            return False

        except Exception as e:
            logger.error(
                f"Error validating agent deployer task: {str(e)}", exc_info=True
            )
            self._agents_without_wallets = None
            return False

    async def _create_wallet_for_agent(self, agent) -> AgentAccountDeploymentResult:
        """Create a wallet for a single agent with enhanced error handling."""
        try:
            logger.info(f"Creating wallet for agent: {agent.name} ({agent.id})")

            # Initialize wallet generator tool
            wallet_tool = AgentAccountDeployTool()

            # Generate wallet
            wallet_result = await wallet_tool._arun()

            if not wallet_result.get("success", False):
                error_msg = f"Failed to generate wallet for agent {agent.id}: {wallet_result.get('message', 'Unknown error')}"
                logger.error(error_msg)
                return AgentAccountDeploymentResult(
                    success=False,
                    message=error_msg,
                    agents_processed=1,
                    wallets_created=0,
                    wallets_failed=1,
                )

            # Extract wallet data from result
            wallet_data = wallet_result.get("wallet")
            if not wallet_data:
                error_msg = f"No wallet data returned for agent {agent.id}"
                logger.error(error_msg)
                return AgentAccountDeploymentResult(
                    success=False,
                    message=error_msg,
                    agents_processed=1,
                    wallets_created=0,
                    wallets_failed=1,
                )

            # Create wallet record in database
            wallet_create = WalletCreate(
                agent_id=agent.id,
                profile_id=agent.profile_id,
                name=f"{agent.name}_wallet",
                mainnet_address=wallet_data.get("mainnet_address"),
                testnet_address=wallet_data.get("testnet_address"),
                mnemonic=wallet_data.get("mnemonic"),
                private_key=wallet_data.get("private_key"),
                public_key=wallet_data.get("public_key"),
                stacks_address=wallet_data.get("stacks_address"),
                btc_address=wallet_data.get("btc_address"),
            )

            created_wallet = backend.create_wallet(wallet_create)
            if not created_wallet:
                error_msg = f"Failed to save wallet to database for agent {agent.id}"
                logger.error(error_msg)
                return AgentAccountDeploymentResult(
                    success=False,
                    message=error_msg,
                    agents_processed=1,
                    wallets_created=0,
                    wallets_failed=1,
                )

            logger.info(
                f"Successfully created wallet {created_wallet.id} for agent {agent.name}"
            )
            logger.debug(
                f"Wallet addresses - Mainnet: {wallet_data.get('mainnet_address')}, "
                f"Testnet: {wallet_data.get('testnet_address')}"
            )

            return AgentAccountDeploymentResult(
                success=True,
                message=f"Successfully created wallet for agent {agent.name}",
                agents_processed=1,
                wallets_created=1,
                wallets_successful=1,
            )

        except Exception as e:
            error_msg = f"Error creating wallet for agent {agent.id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return AgentAccountDeploymentResult(
                success=False,
                message=error_msg,
                error=e,
                agents_processed=1,
                wallets_created=0,
                wallets_failed=1,
            )

    def _should_retry_on_error(self, error: Exception, context: JobContext) -> bool:
        """Determine if error should trigger retry."""
        # Retry on network errors, temporary blockchain issues
        retry_errors = (
            ConnectionError,
            TimeoutError,
        )

        # Don't retry on wallet generation errors or database issues
        if "database" in str(error).lower():
            return False
        if "mnemonic" in str(error).lower():
            return False

        return isinstance(error, retry_errors)

    async def _handle_execution_error(
        self, error: Exception, context: JobContext
    ) -> Optional[List[AgentAccountDeploymentResult]]:
        """Handle execution errors with recovery logic."""
        if "blockchain" in str(error).lower() or "wallet" in str(error).lower():
            logger.warning(f"Blockchain/wallet error: {str(error)}, will retry")
            return None

        if isinstance(error, (ConnectionError, TimeoutError)):
            logger.warning(f"Network error: {str(error)}, will retry")
            return None

        # For database/validation errors, don't retry
        return [
            AgentAccountDeploymentResult(
                success=False,
                message=f"Unrecoverable error: {str(error)}",
                error=error,
            )
        ]

    async def _post_execution_cleanup(
        self, context: JobContext, results: List[AgentAccountDeploymentResult]
    ) -> None:
        """Cleanup after task execution."""
        # Clear cached agents
        self._agents_without_wallets = None
        logger.debug("Agent account deployer task cleanup completed")

    async def _execute_impl(
        self, context: JobContext
    ) -> List[AgentAccountDeploymentResult]:
        """Execute agent account deployment task with batch processing."""
        results: List[AgentAccountDeploymentResult] = []

        if not self._agents_without_wallets:
            logger.debug("No agents without wallets to process")
            return [
                AgentAccountDeploymentResult(
                    success=True,
                    message="No agents require wallet deployment",
                    agents_processed=0,
                    wallets_created=0,
                )
            ]

        total_agents = len(self._agents_without_wallets)
        processed_count = 0
        successful_deployments = 0
        failed_deployments = 0
        batch_size = getattr(context, "batch_size", 5)

        logger.info(f"Processing {total_agents} agents requiring wallet deployment")

        # Process agents in batches
        for i in range(0, len(self._agents_without_wallets), batch_size):
            batch = self._agents_without_wallets[i : i + batch_size]

            for agent in batch:
                logger.debug(f"Creating wallet for agent: {agent.name} ({agent.id})")
                result = await self._create_wallet_for_agent(agent)
                results.append(result)
                processed_count += 1

                if result.success:
                    successful_deployments += 1
                    logger.debug(f"Successfully deployed wallet for agent {agent.name}")
                else:
                    failed_deployments += 1
                    logger.error(
                        f"Failed to deploy wallet for agent {agent.name}: {result.message}"
                    )

        logger.info(
            f"Agent account deployment completed - Processed: {processed_count}, "
            f"Successful: {successful_deployments}, Failed: {failed_deployments}"
        )

        return results


# Create instance for auto-registration
agent_account_deployer = AgentAccountDeployerTask()
