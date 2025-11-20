"""
Stacks Chainhook Adapter

A Python library that transforms Stacks API data into Chainhook-compatible format,
enabling seamless migration from Hiro Chainhooks to direct Stacks API polling.
"""

from typing import Dict, Any, Union
from .adapters.chainhook_adapter import StacksChainhookAdapter
from .client import StacksAPIClient
from .config import AdapterConfig
from .exceptions import (
    StacksChainhookAdapterError,
    APIError,
    TransformationError,
    ParseError,
    BlockNotFoundError,
    TransactionNotFoundError,
    RateLimitError,
    ValidationError,
    ConfigurationError,
)

# Models
from .models.chainhook import (
    ChainHookData,
    Apply,
    BlockIdentifier,
    TransactionWithReceipt,
    TransactionMetadata,
    Receipt,
    Event,
    Operation,
)

# Filters
from .filters.transaction import (
    BaseTransactionFilter,
    ContractCallFilter,
    EventTypeFilter,
    BlockHeightRangeFilter,
)

# Parsers
from .parsers.clarity import ClarityParser

# Utils
from .utils import (
    save_chainhook_data,
    save_chainhook_data_with_template,
    ensure_output_directory,
    create_output_summary,
    detect_transaction_type,
    detect_block_title,
    get_template_manager,
)

__version__ = "1.0.0"
__author__ = "AIBTC Dev Team"
__email__ = "dev@aibtcdev.org"

__all__ = [
    # Main classes
    "StacksChainhookAdapter",
    "StacksAPIClient",
    "AdapterConfig",
    # Exceptions
    "StacksChainhookAdapterError",
    "APIError",
    "TransformationError",
    "ParseError",
    "BlockNotFoundError",
    "TransactionNotFoundError",
    "RateLimitError",
    "ValidationError",
    "ConfigurationError",
    # Models
    "ChainHookData",
    "Apply",
    "BlockIdentifier",
    "TransactionWithReceipt",
    "TransactionMetadata",
    "Receipt",
    "Event",
    "Operation",
    # Filters
    "BaseTransactionFilter",
    "ContractCallFilter",
    "EventTypeFilter",
    "BlockHeightRangeFilter",
    # Parsers
    "ClarityParser",
    # Utils
    "save_chainhook_data",
    "save_chainhook_data_with_template",
    "ensure_output_directory",
    "create_output_summary",
    "detect_transaction_type",
    "detect_block_title",
    "get_template_manager",
    # Metadata
    "__version__",
    "__author__",
    "__email__",
]


# Convenience function for quick usage
async def get_block_chainhook(
    block_height: int,
    network: str = "mainnet",
    api_url: str = None,
    use_template: bool = True,
) -> Union[ChainHookData, Dict[str, Any]]:
    """
    Quick function to get chainhook data for a single block.

    Args:
        block_height: The block height to fetch
        network: Network to use ("mainnet" or "testnet")
        api_url: Custom API URL (optional)
        use_template: Whether to use template-based formatting for exact compatibility

    Returns:
        Dict[str, Any]: Template-formatted chainhook data matching exact webhook format

    Example:
        >>> chainhook_data = await get_block_chainhook(3568390, network="testnet")
        >>> print(
        ...     f"Block has {len(chainhook_data['apply'][0]['transactions'])} transactions"
        ... )
    """
    adapter = StacksChainhookAdapter(network=network, api_url=api_url)
    try:
        return await adapter.get_block_chainhook(
            block_height, use_template=use_template
        )
    finally:
        await adapter.close()


# Version info tuple
VERSION_INFO = tuple(int(part) for part in __version__.split("."))
