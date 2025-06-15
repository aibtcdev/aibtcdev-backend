"""Hiro API integration module.

This module provides clients for interacting with the Hiro API and Platform API,
including blockchain operations, chainhook management, and token queries.
"""

from .hiro_api import HiroApi
from .models import BlockTransactionsResponse, HiroApiInfo
from .platform_api import PlatformApi
from .utils import (
    ChainHookBuilder,
    ChainType,
    EventScope,
    HiroApiError,
    HiroApiRateLimitError,
    HiroApiTimeoutError,
    WebhookConfig,
)

__all__ = [
    "HiroApi",
    "PlatformApi",
    "ChainHookBuilder",
    "ChainType",
    "EventScope",
    "HiroApiError",
    "HiroApiRateLimitError",
    "HiroApiTimeoutError",
    "WebhookConfig",
    "BlockTransactionsResponse",
    "HiroApiInfo",
]
