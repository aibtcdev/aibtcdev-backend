"""Utility classes and types for Hiro API integration."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, TypedDict


class HiroApiError(Exception):
    """Base exception for Hiro API errors."""

    pass


class HiroApiRateLimitError(HiroApiError):
    """Exception for rate limit errors."""

    pass


class HiroApiTimeoutError(HiroApiError):
    """Exception for timeout errors."""

    pass


class ChainType(str, Enum):
    """Supported blockchain types for chainhooks."""

    STACKS = "stacks"
    BITCOIN = "bitcoin"


class EventScope(str, Enum):
    """Supported event scopes for chainhooks."""

    TXID = "txid"
    CONTRACT_CALL = "contract_call"
    PRINT_EVENT = "print_event"
    FT_EVENT = "ft_event"
    NFT_EVENT = "nft_event"
    STX_EVENT = "stx_event"
    BLOCK_HEIGHT = "block_height"


@dataclass
class WebhookConfig:
    """Configuration for webhook endpoints."""

    url: str
    auth_header: str
    retry_count: int = 3
    timeout: int = 10
    events: List[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert webhook config to dictionary format."""
        return {
            "url": self.url,
            "authorization_header": self.auth_header,
            "retry_count": self.retry_count,
            "timeout": self.timeout,
            "events": self.events,
        }


class ChainHookPredicate(TypedDict):
    """Type definition for chainhook predicates."""

    name: str
    chain: str
    version: int
    networks: Dict[str, Any]


class ChainHookBuilder:
    """Builder class for creating chainhook predicates."""

    def __init__(
        self,
        name: str,
        chain_type: ChainType = ChainType.STACKS,
        network: str = "testnet",
        version: int = 1,
    ):
        """Initialize the chainhook builder.

        Args:
            name: Name of the chainhook
            chain_type: Type of blockchain to monitor
            network: Network to monitor (testnet/mainnet)
            version: API version
        """
        self.name = name
        self.chain_type = chain_type
        self.network = network
        self.version = version
        self.conditions: Dict[str, Any] = {}
        self.start_block: Optional[int] = None
        self.end_block: Optional[int] = None
        self.decode_clarity_values: bool = True
        self.expire_after_occurrence: Optional[int] = None
        self.webhook: Optional[WebhookConfig] = None

    def with_transaction_filter(self, txid: str) -> "ChainHookBuilder":
        """Add transaction ID filter."""
        self.conditions = {"scope": EventScope.TXID, "equals": txid}
        return self

    def with_contract_call_filter(
        self,
        contract_identifier: str,
        method: str,
    ) -> "ChainHookBuilder":
        """Add contract call filter."""
        self.conditions = {
            "scope": EventScope.CONTRACT_CALL,
            "method": method,
            "contract_identifier": contract_identifier,
        }
        return self

    def with_print_event_filter(
        self,
        contract_identifier: str,
        topic: str,
    ) -> "ChainHookBuilder":
        """Add print event filter."""
        self.conditions = {
            "scope": EventScope.PRINT_EVENT,
            "contract_identifier": contract_identifier,
            "topic": topic,
        }
        return self

    def with_ft_event_filter(
        self,
        asset_identifier: str,
        actions: List[str],
    ) -> "ChainHookBuilder":
        """Add fungible token event filter."""
        self.conditions = {
            "scope": EventScope.FT_EVENT,
            "asset_identifier": asset_identifier,
            "actions": actions,
        }
        return self

    def with_nft_event_filter(
        self,
        asset_identifier: str,
        actions: List[str],
    ) -> "ChainHookBuilder":
        """Add non-fungible token event filter."""
        self.conditions = {
            "scope": EventScope.NFT_EVENT,
            "asset_identifier": asset_identifier,
            "actions": actions,
        }
        return self

    def with_stx_event_filter(
        self,
        actions: List[str],
    ) -> "ChainHookBuilder":
        """Add STX event filter."""
        self.conditions = {
            "scope": EventScope.STX_EVENT,
            "actions": actions,
        }
        return self

    def with_block_height_filter(self, higher_than: int) -> "ChainHookBuilder":
        """Add block height filter for monitoring blocks higher than specified height."""
        self.conditions = {
            "scope": EventScope.BLOCK_HEIGHT,
            "higher_than": higher_than,
        }
        return self

    def with_blocks(
        self,
        start_block: Optional[int] = None,
        end_block: Optional[int] = None,
    ) -> "ChainHookBuilder":
        """Set block range."""
        self.start_block = start_block
        self.end_block = end_block
        return self

    def with_webhook(self, webhook: WebhookConfig) -> "ChainHookBuilder":
        """Set webhook configuration."""
        self.webhook = webhook
        return self

    def with_expiration(self, occurrences: int) -> "ChainHookBuilder":
        """Set expiration after number of occurrences."""
        self.expire_after_occurrence = occurrences
        return self

    def build(self) -> ChainHookPredicate:
        """Build the chainhook predicate."""
        if not self.conditions:
            raise ValueError("No conditions set for chainhook")
        if not self.webhook:
            raise ValueError("No webhook configured for chainhook")

        network_config = {
            "if_this": self.conditions,
            "then_that": {"http_post": self.webhook.to_dict()},
            "decode_clarity_values": self.decode_clarity_values,
        }

        if self.start_block is not None:
            network_config["start_block"] = self.start_block
        if self.end_block is not None:
            network_config["end_block"] = self.end_block
        if self.expire_after_occurrence is not None:
            network_config["expire_after_occurrence"] = self.expire_after_occurrence

        return {
            "name": self.name,
            "chain": self.chain_type,
            "version": self.version,
            "networks": {self.network: network_config},
        }
