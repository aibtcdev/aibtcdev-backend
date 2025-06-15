"""Worker mode entrypoint for running background services without the web server."""

import asyncio
import sys

from config import config
from lib.logger import configure_logger
from services.infrastructure.startup_service import run_standalone

# Configure module logger
logger = configure_logger(__name__)

# Load configuration
_ = config


async def main():
    """Main worker function that runs all background services."""
    logger.info("Starting AI BTC Dev Backend in worker mode...")
    logger.info("Worker mode - Web server disabled, running background services only")

    try:
        # Run the startup service in standalone mode
        # This includes:
        # - Enhanced job system with auto-discovery
        # - Telegram bot (if enabled)
        # - WebSocket cleanup tasks
        # - System metrics monitoring
        await run_standalone()

    except KeyboardInterrupt:
        logger.info("Worker mode interrupted by user")
    except Exception as e:
        logger.error(f"Critical error in worker mode: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Worker mode shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
