"""Base parser class for extensible parsing functionality."""

from abc import ABC, abstractmethod
from typing import Any, Optional
import logging


class BaseParser(ABC):
    """Abstract base class for data parsers."""

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        """Initialize the parser.

        Args:
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def parse(self, data: Any) -> Any:
        """Parse the given data.

        Args:
            data: Raw data to parse

        Returns:
            Any: Parsed data

        Raises:
            ParseError: If parsing fails
        """
        pass

    def can_parse(self, data: Any) -> bool:
        """Check if this parser can handle the given data.

        Args:
            data: Data to check

        Returns:
            bool: True if this parser can handle the data
        """
        return True  # Default implementation accepts all data

    def get_parser_name(self) -> str:
        """Get the name of this parser.

        Returns:
            str: Parser name
        """
        return self.__class__.__name__
