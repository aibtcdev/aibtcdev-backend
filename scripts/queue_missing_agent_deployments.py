#!/usr/bin/env python3
"""
Queue agent account deployments for wallets missing account contracts.

This script:
1. Retrieves all wallets from the database
2. Checks if each wallet's associated agent has an account_contract
3. For agents without account contracts, queues an agent_account_deploy message
4. Reports the number of deployment messages created

Usage:
    python scripts/queue_missing_agent_deployments.py [--dry-run]

Options:
    --dry-run    Show what would be done without actually creating queue messages
"""

import argparse
import os
import sys
from typing import List

# Add the parent directory (root) to the path to import from app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.backend.factory import backend
from app.backend.models import (
    QueueMessageCreate,
    QueueMessageType,
    Wallet,
    Agent,
)
from app.lib.logger import configure_logger

logger = configure_logger(__name__)


class AgentDeploymentQueuer:
    """Utility to queue agent account deployments for missing contracts."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.stats = {
            "total_wallets": 0,
            "wallets_with_agents": 0,
            "agents_with_contracts": 0,
            "agents_missing_contracts": 0,
            "messages_queued": 0,
            "errors": 0,
        }

    def run(self) -> None:
        """Execute the main logic to queue missing agent deployments."""
        logger.info("Starting agent deployment queuing process...")

        if self.dry_run:
            logger.info("DRY RUN MODE - No queue messages will be created")

        try:
            # Get all wallets from the database
            wallets = self._get_all_wallets()
            self.stats["total_wallets"] = len(wallets)
            logger.info(f"Found {len(wallets)} total wallets")

            # Process each wallet
            for wallet in wallets:
                self._process_wallet(wallet)

            # Report results
            self._report_results()

        except Exception as e:
            logger.error(f"Error during execution: {str(e)}", exc_info=True)
            self.stats["errors"] += 1

    def _get_all_wallets(self) -> List[Wallet]:
        """Retrieve all wallets from the database."""
        try:
            wallets = backend.list_wallets()
            return wallets
        except Exception as e:
            logger.error(f"Failed to retrieve wallets: {str(e)}", exc_info=True)
            raise

    def _process_wallet(self, wallet: Wallet) -> None:
        """Process a single wallet to check if it needs agent deployment."""
        try:
            # Skip wallets without an associated agent
            if not wallet.agent_id:
                logger.debug(f"Wallet {wallet.id} has no associated agent, skipping")
                return

            self.stats["wallets_with_agents"] += 1

            # Get the associated agent
            agent = self._get_agent(wallet.agent_id)
            if not agent:
                logger.warning(
                    f"Agent {wallet.agent_id} not found for wallet {wallet.id}"
                )
                return

            # Check if agent already has an account contract
            if agent.account_contract:
                logger.debug(
                    f"Agent {agent.id} already has contract: {agent.account_contract}"
                )
                self.stats["agents_with_contracts"] += 1
                return

            # Agent needs deployment - check if wallet has required addresses
            if not wallet.mainnet_address or not wallet.testnet_address:
                logger.warning(
                    f"Wallet {wallet.id} missing required addresses - "
                    f"mainnet: {wallet.mainnet_address}, testnet: {wallet.testnet_address}"
                )
                return

            # Queue deployment message
            self.stats["agents_missing_contracts"] += 1
            self._queue_deployment_message(wallet)

        except Exception as e:
            logger.error(
                f"Error processing wallet {wallet.id}: {str(e)}", exc_info=True
            )
            self.stats["errors"] += 1

    def _get_agent(self, agent_id) -> Agent:
        """Retrieve an agent by ID."""
        try:
            return backend.get_agent(agent_id)
        except Exception as e:
            logger.error(
                f"Failed to retrieve agent {agent_id}: {str(e)}", exc_info=True
            )
            return None

    def _queue_deployment_message(self, wallet: Wallet) -> None:
        """Create and queue an agent deployment message for the wallet."""
        try:
            # Create the queue message
            queue_message = QueueMessageCreate(
                type=QueueMessageType.get_or_create("agent_account_deploy"),
                message={
                    "agent_mainnet_address": wallet.mainnet_address,
                    "agent_testnet_address": wallet.testnet_address,
                },
                dao_id=None,  # As requested
                wallet_id=None,  # As requested
                is_processed=False,
            )

            if self.dry_run:
                logger.info(
                    f"DRY RUN: Would queue deployment for wallet {wallet.id} "
                    f"(mainnet: {wallet.mainnet_address}, testnet: {wallet.testnet_address})"
                )
            else:
                # Actually create the message
                created_message = backend.create_queue_message(queue_message)
                logger.info(
                    f"Queued deployment message {created_message.id} for wallet {wallet.id} "
                    f"(mainnet: {wallet.mainnet_address}, testnet: {wallet.testnet_address})"
                )

            self.stats["messages_queued"] += 1

        except Exception as e:
            logger.error(
                f"Failed to queue deployment message for wallet {wallet.id}: {str(e)}",
                exc_info=True,
            )
            self.stats["errors"] += 1

    def _report_results(self) -> None:
        """Report the final results of the process."""
        logger.info("=" * 60)
        logger.info("AGENT DEPLOYMENT QUEUING RESULTS")
        logger.info("=" * 60)
        logger.info(f"Total wallets processed: {self.stats['total_wallets']}")
        logger.info(f"Wallets with agents: {self.stats['wallets_with_agents']}")
        logger.info(
            f"Agents with existing contracts: {self.stats['agents_with_contracts']}"
        )
        logger.info(
            f"Agents missing contracts: {self.stats['agents_missing_contracts']}"
        )
        logger.info(f"Deployment messages queued: {self.stats['messages_queued']}")
        logger.info(f"Errors encountered: {self.stats['errors']}")
        logger.info("=" * 60)

        if self.dry_run:
            logger.info("DRY RUN COMPLETE - No actual changes were made")
        else:
            logger.info("PROCESS COMPLETE")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Queue agent account deployments for wallets missing account contracts"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually creating queue messages",
    )

    args = parser.parse_args()

    try:
        queuer = AgentDeploymentQueuer(dry_run=args.dry_run)
        queuer.run()
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
