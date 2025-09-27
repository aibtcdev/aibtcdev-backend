"""Custom exceptions for the Stacks Chainhook Adapter."""

from typing import Optional, Any, Dict


class StacksChainhookAdapterError(Exception):
    """Base exception for all Stacks Chainhook Adapter errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the exception.

        Args:
            message: Error message
            details: Additional error details
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        """String representation of the exception."""
        if self.details:
            return f"{self.message} (Details: {self.details})"
        return self.message


class APIError(StacksChainhookAdapterError):
    """Exception raised for Stacks API-related errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
        endpoint: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the API error.

        Args:
            message: Error message
            status_code: HTTP status code
            response_body: Response body content
            endpoint: API endpoint that failed
            **kwargs: Additional details
        """
        details = kwargs.copy()
        if status_code is not None:
            details["status_code"] = status_code
        if response_body is not None:
            details["response_body"] = response_body
        if endpoint is not None:
            details["endpoint"] = endpoint

        super().__init__(message, details)
        self.status_code = status_code
        self.response_body = response_body
        self.endpoint = endpoint


class RateLimitError(APIError):
    """Exception raised when API rate limits are exceeded."""

    def __init__(
        self,
        message: str = "API rate limit exceeded",
        retry_after: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the rate limit error.

        Args:
            message: Error message
            retry_after: Seconds to wait before retrying
            **kwargs: Additional details
        """
        if retry_after is not None:
            kwargs["retry_after"] = retry_after

        super().__init__(message, status_code=429, **kwargs)
        self.retry_after = retry_after


class TransformationError(StacksChainhookAdapterError):
    """Exception raised during data transformation from Stacks API to Chainhook format."""

    def __init__(
        self,
        message: str,
        source_data: Optional[Any] = None,
        transformation_stage: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the transformation error.

        Args:
            message: Error message
            source_data: The data that failed to transform
            transformation_stage: Stage where transformation failed
            **kwargs: Additional details
        """
        details = kwargs.copy()
        if source_data is not None:
            # Only store a summary of source data to avoid huge error messages
            if isinstance(source_data, dict):
                details["source_data_keys"] = list(source_data.keys())
                details["source_data_type"] = "dict"
            elif isinstance(source_data, list):
                details["source_data_length"] = len(source_data)
                details["source_data_type"] = "list"
            else:
                details["source_data_type"] = type(source_data).__name__

        if transformation_stage is not None:
            details["transformation_stage"] = transformation_stage

        super().__init__(message, details)
        self.source_data = source_data
        self.transformation_stage = transformation_stage


class ParseError(StacksChainhookAdapterError):
    """Exception raised when parsing Clarity repr format or other structured data."""

    def __init__(
        self,
        message: str,
        raw_data: Optional[str] = None,
        parser_type: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the parse error.

        Args:
            message: Error message
            raw_data: The raw data that failed to parse
            parser_type: Type of parser that failed
            **kwargs: Additional details
        """
        details = kwargs.copy()
        if raw_data is not None:
            # Truncate raw data to prevent huge error messages
            details["raw_data_preview"] = (
                raw_data[:200] + "..." if len(raw_data) > 200 else raw_data
            )
            details["raw_data_length"] = len(raw_data)

        if parser_type is not None:
            details["parser_type"] = parser_type

        super().__init__(message, details)
        self.raw_data = raw_data
        self.parser_type = parser_type


class BlockNotFoundError(APIError):
    """Exception raised when a requested block is not found."""

    def __init__(
        self,
        block_height: int,
        network: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the block not found error.

        Args:
            block_height: The block height that was not found
            network: Network where the block was searched
            **kwargs: Additional details
        """
        message = f"Block {block_height} not found"
        if network:
            message += f" on {network}"

        details = kwargs.copy()
        details["block_height"] = block_height
        if network:
            details["network"] = network

        super().__init__(message, status_code=404, **details)
        self.block_height = block_height
        self.network = network


class TransactionNotFoundError(APIError):
    """Exception raised when a requested transaction is not found."""

    def __init__(
        self,
        transaction_id: str,
        block_height: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the transaction not found error.

        Args:
            transaction_id: The transaction ID that was not found
            block_height: Block height where transaction was expected
            **kwargs: Additional details
        """
        message = f"Transaction {transaction_id} not found"
        if block_height:
            message += f" in block {block_height}"

        details = kwargs.copy()
        details["transaction_id"] = transaction_id
        if block_height:
            details["block_height"] = block_height

        super().__init__(message, status_code=404, **details)
        self.transaction_id = transaction_id
        self.block_height = block_height


class ValidationError(StacksChainhookAdapterError):
    """Exception raised when data validation fails."""

    def __init__(
        self,
        message: str,
        field_name: Optional[str] = None,
        expected_type: Optional[type] = None,
        actual_value: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the validation error.

        Args:
            message: Error message
            field_name: Name of the field that failed validation
            expected_type: Expected data type
            actual_value: The actual value that failed validation
            **kwargs: Additional details
        """
        details = kwargs.copy()
        if field_name is not None:
            details["field_name"] = field_name
        if expected_type is not None:
            details["expected_type"] = expected_type.__name__
        if actual_value is not None:
            details["actual_type"] = type(actual_value).__name__
            details["actual_value"] = str(actual_value)[:100]  # Truncate for safety

        super().__init__(message, details)
        self.field_name = field_name
        self.expected_type = expected_type
        self.actual_value = actual_value


class ConfigurationError(StacksChainhookAdapterError):
    """Exception raised for configuration-related errors."""

    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        config_value: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the configuration error.

        Args:
            message: Error message
            config_key: Configuration key that caused the error
            config_value: Configuration value that caused the error
            **kwargs: Additional details
        """
        details = kwargs.copy()
        if config_key is not None:
            details["config_key"] = config_key
        if config_value is not None:
            details["config_value"] = str(config_value)

        super().__init__(message, details)
        self.config_key = config_key
        self.config_value = config_value
