"""DAO token holders monitoring task implementation."""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from app.backend.factory import backend
from app.backend.models import (
    HolderBase,
    HolderCreate,
    HolderFilter,
    AgentFilter,
    WalletFilter,
)
from app.services.integrations.hiro.hiro_api import HiroApi
from app.lib.logger import configure_logger
from app.services.infrastructure.job_management.base import (
    BaseTask,
    JobContext,
    RunnerConfig,
    RunnerResult,
)
from app.services.infrastructure.job_management.decorators import JobPriority, job

logger = configure_logger(__name__)


@dataclass
class DaoTokenHoldersMonitorResult(RunnerResult):
    """Result of DAO token holders monitoring operation."""

    tokens_processed: int = 0
    holders_created: int = 0
    holders_updated: int = 0
    holders_removed: int = 0
    errors: List[str] = None

    def __post_init__(self):
        """Initialize default values after dataclass creation."""
        if self.errors is None:
            self.errors = []


@job(
    job_type="dao_token_holders_monitor",
    name="DAO Token Holders Monitor",
    description="Monitors and syncs DAO token holders with blockchain data every 5 minutes",
    interval_seconds=300,  # 5 minutes
    priority=JobPriority.MEDIUM,
    max_retries=3,
    retry_delay_seconds=120,
    timeout_seconds=600,  # 10 minutes timeout
    max_concurrent=1,
    requires_blockchain=True,
    batch_size=10,
    enable_dead_letter_queue=True,
)
class DaoTokenHoldersMonitorTask(BaseTask[DaoTokenHoldersMonitorResult]):
    """Task for monitoring and syncing DAO token holders with blockchain data."""

    def __init__(self, config: Optional[RunnerConfig] = None):
        super().__init__(config)
        self.hiro_api = HiroApi()

    async def _validate_config(self, context: JobContext) -> bool:
        """Validate task configuration."""
        try:
            # Token holders monitor doesn't require wallet configuration
            # It only reads from the blockchain and updates database
            return True
        except Exception as e:
            logger.error(
                f"Error validating DAO token holders monitor config: {str(e)}",
                exc_info=True,
            )
            return False

    async def _validate_resources(self, context: JobContext) -> bool:
        """Validate resource availability for blockchain monitoring."""
        try:
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
            # Always valid to run - we want to keep holders data fresh
            return True
        except Exception as e:
            logger.error(
                f"Error validating DAO token holders monitor task: {str(e)}",
                exc_info=True,
            )
            return False

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
        if "invalid token" in str(error).lower():
            return False

        return isinstance(error, retry_errors)

    async def _handle_execution_error(
        self, error: Exception, context: JobContext
    ) -> Optional[List[DaoTokenHoldersMonitorResult]]:
        """Handle execution errors with recovery logic."""
        if "blockchain" in str(error).lower() or "rpc" in str(error).lower():
            logger.warning(f"Blockchain/RPC error: {str(error)}, will retry")
            return None

        if isinstance(error, (ConnectionError, TimeoutError)):
            logger.warning(f"Network error: {str(error)}, will retry")
            return None

        # For configuration errors, don't retry
        return [
            DaoTokenHoldersMonitorResult(
                success=False,
                message=f"Unrecoverable error: {str(error)}",
                error=error,
            )
        ]

    async def _post_execution_cleanup(
        self, context: JobContext, results: List[DaoTokenHoldersMonitorResult]
    ) -> None:
        """Cleanup after task execution."""
        logger.debug("DAO token holders monitor task cleanup completed")

    def _parse_token_identifier(self, token) -> Optional[str]:
        """Parse token identifier for Hiro API call.

        Constructs the proper token identifier format: {contract_principal}::{symbol}
        """
        if not hasattr(token, "contract_principal") or not token.contract_principal:
            logger.warning(f"Token {token.id} has no contract_principal")
            return None

        contract_principal = token.contract_principal

        try:
            # Get token metadata to extract the symbol
            logger.debug(f"Fetching metadata for token {contract_principal}")
            metadata = self.hiro_api.get_token_metadata(contract_principal)

            # Extract symbol from metadata
            symbol = metadata.get("symbol")
            if not symbol:
                logger.warning(
                    f"No symbol found in metadata for token {contract_principal}"
                )
                return None

            # Construct the proper token identifier format
            token_identifier = f"{contract_principal}::{symbol}"
            logger.debug(f"Constructed token identifier: {token_identifier}")
            return token_identifier

        except Exception as e:
            logger.error(
                f"Error fetching metadata for token {contract_principal}: {str(e)}"
            )
            # Fallback to just the contract principal if metadata fails
            logger.warning(
                f"Using contract principal as fallback: {contract_principal}"
            )
            return contract_principal

    def _get_agent_for_contract(self, account_contract: str):
        """Get existing agent for a given account_contract. Returns (agent, wallet) tuple if found, None otherwise."""
        try:
            # Try to find existing agent by account_contract
            agents = backend.list_agents(
                filters=AgentFilter(account_contract=account_contract)
            )
            if agents:
                agent = agents[0]
                # Get the wallet for this agent
                wallets = backend.list_wallets(filters=WalletFilter(agent_id=agent.id))
                wallet = wallets[0] if wallets else None
                return agent, wallet

            # If no agent found, return None
            logger.debug(
                f"No existing agent found for account_contract {account_contract}"
            )
            return None, None

        except Exception as e:
            logger.error(
                f"Error getting agent for account_contract {account_contract}: {str(e)}"
            )
            return None, None

    async def _sync_token_holders(
        self, token, result: DaoTokenHoldersMonitorResult
    ) -> None:
        """Sync holders for a specific token."""
        try:
            token_identifier = self._parse_token_identifier(token)
            if not token_identifier:
                error_msg = f"Could not parse token identifier for token {token.id}"
                logger.error(error_msg)
                result.errors.append(error_msg)
                return

            logger.info(f"Syncing holders for token {token.name} ({token_identifier})")

            # Get all current holders from Hiro API (with pagination)
            try:
                api_holders_response = self.hiro_api.get_all_token_holders(
                    token_identifier
                )
                logger.debug(
                    f"API response for token {token_identifier}: {api_holders_response}"
                )
            except Exception as e:
                error_msg = f"Error fetching holders from API for token {token_identifier}: {str(e)}"
                logger.error(error_msg)
                result.errors.append(error_msg)
                return

            # Parse API response
            api_holders = []
            if (
                isinstance(api_holders_response, dict)
                and "results" in api_holders_response
            ):
                api_holders = api_holders_response["results"]
            elif isinstance(api_holders_response, list):
                api_holders = api_holders_response
            else:
                logger.warning(
                    f"Unexpected API response format for token {token_identifier}"
                )
                return

            logger.info(
                f"Found {len(api_holders)} holders from API for token {token.name}"
            )

            # Get current holders from database
            db_holders = backend.list_holders(HolderFilter(token_id=token.id))
            logger.info(
                f"Found {len(db_holders)} existing holders in database for token {token.name}"
            )

            # Create lookup maps by address+token_id (composite key for matching)
            # This allows the same address to hold tokens for multiple DAOs
            db_holders_by_address_token = {
                (holder.address, holder.token_id): holder for holder in db_holders
            }
            api_holders_by_contract = {}

            # Process API holders
            for api_holder in api_holders:
                try:
                    # Parse holder data from Hiro API response format
                    address = api_holder.get("address")
                    balance = api_holder.get("balance", "0")

                    if not address:
                        logger.warning(
                            f"No address found in API holder data: {api_holder}"
                        )
                        continue

                    if not balance:
                        logger.warning(
                            f"No balance found for address {address}, defaulting to 0"
                        )
                        balance = "0"

                    api_holders_by_contract[address] = balance

                    # Get existing agent and wallet for this account_contract
                    agent, wallet = self._get_agent_for_contract(address)

                    # Check if we already have this holder in the database (by address+token_id)
                    holder_key = (address, token.id)
                    if holder_key in db_holders_by_address_token:
                        # Update existing holder
                        existing_holder = db_holders_by_address_token[holder_key]
                        needs_update = False
                        update_data = HolderBase(
                            amount=str(balance),
                            updated_at=datetime.now(),
                            address=address,
                        )

                        # Check if we need to update agent_id
                        if agent and existing_holder.agent_id != agent.id:
                            update_data.agent_id = agent.id
                            needs_update = True
                        elif not agent and existing_holder.agent_id is not None:
                            update_data.agent_id = None
                            needs_update = True

                        # Check if we need to update wallet_id
                        if wallet and existing_holder.wallet_id != wallet.id:
                            update_data.wallet_id = wallet.id
                            needs_update = True
                        elif not wallet and existing_holder.wallet_id is not None:
                            update_data.wallet_id = None
                            needs_update = True

                        # Check if amount changed
                        if existing_holder.amount != str(balance):
                            needs_update = True

                        # Check if address changed
                        if existing_holder.address != address:
                            needs_update = True

                        if needs_update:
                            logger.info(
                                f"Updating holder {address} for token {token.name}: "
                                f"amount={existing_holder.amount}->{balance}, "
                                f"agent_id={existing_holder.agent_id}->{agent.id if agent else None}, "
                                f"wallet_id={existing_holder.wallet_id}->{wallet.id if wallet else None}"
                            )
                            backend.update_holder(existing_holder.id, update_data)
                            result.holders_updated += 1
                    else:
                        # Create new holder (with or without agent)
                        agent_info = f"agent_id={agent.id}" if agent else "no agent"
                        wallet_info = (
                            f"wallet_id={wallet.id}" if wallet else "no wallet"
                        )
                        logger.info(
                            f"Creating new holder {address} for token {token.name} with balance {balance}, "
                            f"{agent_info}, {wallet_info}"
                        )
                        holder_create = HolderCreate(
                            agent_id=agent.id if agent else None,
                            wallet_id=wallet.id if wallet else None,
                            token_id=token.id,
                            dao_id=token.dao_id,
                            amount=str(balance),
                            updated_at=datetime.now(),
                            address=address,
                        )
                        backend.create_holder(holder_create)
                        result.holders_created += 1

                except Exception as e:
                    error_msg = f"Error processing API holder {api_holder}: {str(e)}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)

            # Check for holders that are no longer in the API response (removed holders)
            # Only check holders for the current token being processed
            for db_holder in db_holders:
                try:
                    # Only process holders for the current token
                    if db_holder.token_id != token.id:
                        continue

                    # Use address for matching since that's what we get from the API
                    if (
                        db_holder.address
                        and db_holder.address not in api_holders_by_contract
                    ):
                        # This holder is no longer holding tokens for this specific token, remove from database
                        logger.info(
                            f"Removing holder {db_holder.address} for token {token.name} (no longer holds tokens)"
                        )
                        backend.delete_holder(db_holder.id)
                        result.holders_removed += 1
                except Exception as e:
                    logger.error(
                        f"Error processing holder {db_holder.id} with address {db_holder.address} for token {token.name}: {str(e)}"
                    )
                    continue

        except Exception as e:
            error_msg = f"Error syncing holders for token {token.id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            result.errors.append(error_msg)

    async def _execute_impl(
        self, context: JobContext
    ) -> List[DaoTokenHoldersMonitorResult]:
        """Execute DAO token holders monitoring task."""
        logger.info("Starting DAO token holders monitoring task")

        result = DaoTokenHoldersMonitorResult(
            success=True, message="DAO token holders sync completed"
        )

        try:
            # Get all tokens from the database
            all_tokens = backend.list_tokens()
            logger.info(f"Found {len(all_tokens)} tokens to process")

            if not all_tokens:
                result.message = "No tokens found to process"
                return [result]

            # Process each token
            for token in all_tokens:
                try:
                    logger.info(f"Processing token: {token.name} (ID: {token.id})")
                    await self._sync_token_holders(token, result)
                    result.tokens_processed += 1

                except Exception as e:
                    error_msg = f"Error processing token {token.id}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    result.errors.append(error_msg)
                    # Continue processing other tokens even if one fails

            # Update result message with summary
            summary = (
                f"Processed {result.tokens_processed} tokens. "
                f"Created {result.holders_created}, updated {result.holders_updated}, "
                f"removed {result.holders_removed} holders."
            )

            if result.errors:
                summary += f" Encountered {len(result.errors)} errors."
                result.success = False

            result.message = summary
            logger.info(summary)

            return [result]

        except Exception as e:
            error_msg = f"Error executing DAO token holders monitoring task: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return [
                DaoTokenHoldersMonitorResult(
                    success=False, message=error_msg, error=e, errors=[error_msg]
                )
            ]


# Create instance for auto-registration
dao_token_holders_monitor = DaoTokenHoldersMonitorTask()
