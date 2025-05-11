#!/usr/bin/env python3
"""Example script for manually running the chain state monitor task.

This script demonstrates how to manually trigger the chain state monitor task
to check for stale chain state and process any missing blocks.

Usage:
    python examples/chain_state_monitor_example.py
"""

import asyncio
import logging
import os
import sys
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))


from backend.factory import backend
from config import config
from lib.logger import configure_logger
from services.runner.base import JobContext, JobType, RunnerConfig
from services.runner.tasks.chain_state_monitor import ChainStateMonitorTask

# Set up logging
logger = configure_logger("chain_state_monitor_example")
logger.setLevel(logging.INFO)


async def main():
    """Run the chain state monitor task once."""
    # Print header
    print("\n======== Chain State Monitor Example ========\n")

    # Create the task
    monitor_task = ChainStateMonitorTask()

    # Create a job context
    context = JobContext(
        job_type=JobType.CHAIN_STATE_MONITOR,
        config=RunnerConfig.from_env(),
        parameters={"force_check": True},  # Optional parameter to force checking
    )

    print(f"Running chain state monitor for network: {config.network.network}")

    # Execute the task
    start_time = datetime.now()
    results = await monitor_task.execute(context)
    duration = (datetime.now() - start_time).total_seconds()

    # Print results
    print(f"\nExecution completed in {duration:.2f} seconds")
    print("\n-------- Results --------\n")

    for result in results:
        print(f"Success: {result.success}")
        print(f"Message: {result.message}")
        print(f"Network: {result.network}")
        print(f"Is Stale: {result.is_stale}")

        if result.last_updated:
            print(f"Last Updated: {result.last_updated}")
            print(f"Elapsed Minutes: {result.elapsed_minutes:.2f}")

        if result.blocks_behind > 0:
            print(f"Blocks Behind: {result.blocks_behind}")
            print(f"Blocks Processed: {len(result.blocks_processed)}")

            # Show block details
            if result.blocks_processed:
                print("\nProcessed Blocks:")
                for block in result.blocks_processed:
                    block_data = backend.get_block(block)
                    if block_data:
                        tx_count = (
                            len(block_data.transactions)
                            if hasattr(block_data, "transactions")
                            else "N/A"
                        )
                        print(f"  - Block {block}: {tx_count} transactions")

    print("\n======== End of Chain State Monitor Example ========\n")


if __name__ == "__main__":
    asyncio.run(main())
