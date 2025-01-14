import logging
from dotenv import load_dotenv
from typing import Optional

# Load environment variables from a .env file
load_dotenv()

# Map string log levels to logging constants
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def configure_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Configure and return a logger instance with consistent formatting and level.

    Args:
        name (Optional[str]): Logger name. If None, returns the root logger

    Returns:
        logging.Logger: Configured logger instance
    """
    # Get the logger
    # logger = logging.getLogger(name)
    # Configure module logger
    logger = logging.getLogger("uvicorn.error")

    return logger
