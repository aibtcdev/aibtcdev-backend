import logging
import os
import pytest
from lib.logger import configure_logger
from typing import Generator


@pytest.fixture
def reset_logging() -> Generator[None, None, None]:
    """Reset logging configuration after each test."""
    yield
    logging.getLogger().handlers.clear()
    logging.getLogger().setLevel(logging.NOTSET)


@pytest.fixture
def env_cleanup() -> Generator[None, None, None]:
    """Clean up environment variables after each test."""
    old_level = os.environ.get("LOG_LEVEL")
    yield
    if old_level:
        os.environ["LOG_LEVEL"] = old_level
    else:
        os.environ.pop("LOG_LEVEL", None)


def test_configure_logger_default(reset_logging: None) -> None:
    """Test logger configuration with default settings."""
    logger = configure_logger()
    assert logger.name == "uvicorn.error"
    assert logger.level == logging.INFO


def test_configure_logger_custom_name(reset_logging: None) -> None:
    """Test logger configuration with custom name."""
    logger = configure_logger("test_logger")
    assert logger.name == "test_logger"
    assert logger.level == logging.INFO


def test_configure_logger_custom_level(reset_logging: None, env_cleanup: None) -> None:
    """Test logger configuration with custom log level."""
    os.environ["LOG_LEVEL"] = "DEBUG"
    logger = configure_logger()
    assert logger.level == logging.DEBUG


def test_configure_logger_invalid_level(reset_logging: None, env_cleanup: None) -> None:
    """Test logger configuration with invalid log level."""
    os.environ["LOG_LEVEL"] = "INVALID"
    logger = configure_logger()
    assert logger.level == logging.INFO  # Should default to INFO for invalid levels


def test_configure_logger_case_insensitive(
    reset_logging: None, env_cleanup: None
) -> None:
    """Test logger configuration with case-insensitive log level."""
    os.environ["LOG_LEVEL"] = "debug"
    logger = configure_logger()
    assert logger.level == logging.DEBUG
