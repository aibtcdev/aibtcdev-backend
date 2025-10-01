"""Base adapter class for data transformations."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ..config import AdapterConfig
from ..exceptions import TransformationError
from ..parsers.base import BaseParser


class BaseAdapter(ABC):
    """Abstract base class for data adapters."""

    def __init__(self, config: Optional[AdapterConfig] = None) -> None:
        """Initialize the adapter.

        Args:
            config: Configuration for the adapter
        """
        self.config = config or AdapterConfig()
        self.logger = self.config.get_logger(self.__class__.__name__)

        # Registry of parsers for different data types
        self._parsers: Dict[str, BaseParser] = {}

        # Initialize default parsers
        self._initialize_parsers()

    def _initialize_parsers(self) -> None:
        """Initialize default parsers."""
        # Subclasses should implement this to register their parsers
        pass

    def register_parser(self, name: str, parser: BaseParser) -> None:
        """Register a parser for a specific data type.

        Args:
            name: Name/identifier for the parser
            parser: Parser instance
        """
        self._parsers[name] = parser
        self.logger.debug(f"Registered parser: {name}")

    def get_parser(self, name: str) -> Optional[BaseParser]:
        """Get a parser by name.

        Args:
            name: Parser name

        Returns:
            Optional[BaseParser]: Parser instance or None if not found
        """
        return self._parsers.get(name)

    def get_available_parsers(self) -> List[str]:
        """Get list of available parser names.

        Returns:
            List[str]: List of parser names
        """
        return list(self._parsers.keys())

    @abstractmethod
    async def transform(self, source_data: Any, **kwargs: Any) -> Any:
        """Transform source data to target format.

        Args:
            source_data: Data to transform
            **kwargs: Additional transformation options

        Returns:
            Any: Transformed data

        Raises:
            TransformationError: If transformation fails
        """
        pass

    def _safe_transform(self, data: Any, transform_func: callable, stage: str) -> Any:
        """Safely execute a transformation function with error handling.

        Args:
            data: Data to transform
            transform_func: Function to apply
            stage: Name of the transformation stage (for error reporting)

        Returns:
            Any: Transformed data

        Raises:
            TransformationError: If transformation fails
        """
        try:
            return transform_func(data)
        except Exception as e:
            raise TransformationError(
                f"Transformation failed at stage '{stage}': {e}",
                source_data=data,
                transformation_stage=stage,
            ) from e
