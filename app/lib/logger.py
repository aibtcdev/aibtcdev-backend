import json
import logging
import os
from typing import Optional

# Map string log levels to logging constants
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class JSONFormatter(logging.Formatter):
    """JSON formatter that outputs single-line structured logs."""

    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        for key, value in record.__dict__.items():
            if key not in [
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
            ]:
                log_entry[key] = value

        return json.dumps(log_entry, ensure_ascii=False)


def configure_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Configure and return a logger instance with consistent formatting and level.

    Args:
        name (Optional[str]): Logger name. If None, returns the root logger

    Returns:
        logging.Logger: Configured logger instance
    """
    # Get the logger with the provided name
    logger = logging.getLogger(name if name else __name__)

    # Set log level from environment variable, default to INFO if not set
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = LOG_LEVELS.get(log_level_str, logging.INFO)
    logger.setLevel(log_level)

    # Add console handler if none exists
    if not logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        formatter = JSONFormatter()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


def setup_uvicorn_logging():
    """Configure uvicorn and other loggers to use JSON formatting."""
    # Disable uvicorn access logging since we handle it with middleware
    logging.getLogger("uvicorn.access").disabled = True

    # Create a JSON formatter
    json_formatter = JSONFormatter()

    # Get all existing loggers and configure them
    for logger_name in ["uvicorn", "uvicorn.error", "fastapi"]:
        logger = logging.getLogger(logger_name)
        for handler in logger.handlers:
            handler.setFormatter(json_formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.setFormatter(json_formatter)

    # Set up a hook to catch any new handlers that get added later
    original_add_handler = logging.Logger.addHandler

    def patched_add_handler(self, hdlr):
        hdlr.setFormatter(json_formatter)
        return original_add_handler(self, hdlr)

    logging.Logger.addHandler = patched_add_handler
