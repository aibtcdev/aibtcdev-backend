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


class StructuredFormatter(logging.Formatter):
    """Structured formatter that outputs human-readable logs with key filtering capability."""

    def format(self, record):
        timestamp = self.formatTime(record, self.datefmt or "%Y-%m-%d %H:%M:%S")
        level = record.levelname.ljust(8)
        logger_name = record.name.split(".")[-1][:20].ljust(20)
        message = record.getMessage()

        # Base log line
        log_line = f"{timestamp} | {level} | {logger_name} | {message}"

        # Add extra fields if present
        extras = []
        for key, value in record.__dict__.items():
            if (
                key
                not in [
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
                    "taskName",  # Skip this internal field
                ]
                and value is not None
            ):
                if key == "task_name":
                    extras.append(f"task={value}")
                elif key == "event_type":
                    extras.append(f"type={value}")
                elif isinstance(value, dict):
                    # For dict values like request/response, show key info only
                    if key == "request":
                        method = value.get("method", "")
                        path = value.get("path", "")
                        if method and path:
                            extras.append(f"request={method} {path}")
                    elif key == "response":
                        status = value.get("status_code", "")
                        time_ms = value.get("process_time_ms", "")
                        if status:
                            extras.append(f"response={status}")
                        if time_ms:
                            extras.append(f"time={time_ms}ms")
                    else:
                        extras.append(f"{key}={str(value)[:100]}")
                else:
                    extras.append(f"{key}={value}")

        if extras:
            log_line += f" | {' '.join(extras)}"

        # Add exception info if present
        if record.exc_info:
            log_line += f"\n{self.formatException(record.exc_info)}"

        return log_line


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
        formatter = StructuredFormatter()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


def setup_uvicorn_logging():
    """Configure uvicorn and other loggers to use structured formatting."""
    # Disable uvicorn access logging since we handle it with middleware
    logging.getLogger("uvicorn.access").disabled = True

    # Create a structured formatter
    structured_formatter = StructuredFormatter()

    # Get all existing loggers and configure them
    for logger_name in ["uvicorn", "uvicorn.error", "fastapi"]:
        logger = logging.getLogger(logger_name)
        for handler in logger.handlers:
            handler.setFormatter(structured_formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.setFormatter(structured_formatter)

    # Set up a hook to catch any new handlers that get added later
    original_add_handler = logging.Logger.addHandler

    def patched_add_handler(self, hdlr):
        hdlr.setFormatter(structured_formatter)
        return original_add_handler(self, hdlr)

    logging.Logger.addHandler = patched_add_handler
