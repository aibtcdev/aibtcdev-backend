"""Platform API client for Hiro chainhook management."""

from typing import Any, Dict, List, Optional

from config import config

from .base import BaseHiroApi
from .utils import ChainHookBuilder, ChainHookPredicate, WebhookConfig


class PlatformApi(BaseHiroApi):
    """Client for interacting with the Hiro Platform API."""

    def __init__(self):
        """Initialize the Platform API client."""
        super().__init__(config.api.platform_base_url)
        self.default_webhook = WebhookConfig(
            url=config.api.webhook_url, auth_header=config.api.webhook_auth
        )

    def create_chainhook(self, predicate: ChainHookPredicate) -> Dict[str, Any]:
        """Create a new chainhook.

        Args:
            predicate: The chainhook predicate configuration

        Returns:
            Dict containing the response from the API
        """
        return self._make_request(
            "POST",
            f"/v1/ext/{self.api_key}/chainhooks",
            headers={"Content-Type": "application/json"},
            json=predicate,
        )

    async def acreate_chainhook(self, predicate: ChainHookPredicate) -> Dict[str, Any]:
        """Async version of create_chainhook."""
        return await self._amake_request(
            "POST",
            f"/v1/ext/{self.api_key}/chainhooks",
            headers={"Content-Type": "application/json"},
            json=predicate,
        )

    def create_transaction_hook(
        self,
        txid: str,
        name: str = "tx-monitor",
        start_block: Optional[int] = None,
        network: str = "testnet",
        webhook: Optional[WebhookConfig] = None,
        expire_after_occurrence: int = 1,
    ) -> Dict[str, Any]:
        """Create a chainhook for monitoring specific transactions."""
        predicate = (
            ChainHookBuilder(name, network=network)
            .with_transaction_filter(txid)
            .with_blocks(start_block)
            .with_webhook(webhook or self.default_webhook)
            .with_expiration(expire_after_occurrence)
            .build()
        )
        return self.create_chainhook(predicate)

    def create_contract_call_hook(
        self,
        contract_identifier: str,
        method: str,
        name: str = "contract-call-monitor",
        start_block: Optional[int] = None,
        network: str = "testnet",
        webhook: Optional[WebhookConfig] = None,
        end_block: Optional[int] = None,
        expire_after_occurrence: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a chainhook for monitoring contract calls."""
        builder = (
            ChainHookBuilder(name, network=network)
            .with_contract_call_filter(contract_identifier, method)
            .with_blocks(start_block, end_block)
            .with_webhook(webhook or self.default_webhook)
        )

        if expire_after_occurrence is not None:
            builder.with_expiration(expire_after_occurrence)

        return self.create_chainhook(builder.build())

    def create_ft_event_hook(
        self,
        asset_identifier: str,
        actions: List[str],
        name: str = "ft-event-monitor",
        start_block: Optional[int] = None,
        network: str = "testnet",
        webhook: Optional[WebhookConfig] = None,
        end_block: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a chainhook for monitoring fungible token events."""
        predicate = (
            ChainHookBuilder(name, network=network)
            .with_ft_event_filter(asset_identifier, actions)
            .with_blocks(start_block, end_block)
            .with_webhook(webhook or self.default_webhook)
            .build()
        )
        return self.create_chainhook(predicate)

    def create_nft_event_hook(
        self,
        asset_identifier: str,
        actions: List[str],
        name: str = "nft-event-monitor",
        start_block: Optional[int] = None,
        network: str = "testnet",
        webhook: Optional[WebhookConfig] = None,
        end_block: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a chainhook for monitoring non-fungible token events."""
        predicate = (
            ChainHookBuilder(name, network=network)
            .with_nft_event_filter(asset_identifier, actions)
            .with_blocks(start_block, end_block)
            .with_webhook(webhook or self.default_webhook)
            .build()
        )
        return self.create_chainhook(predicate)

    def create_stx_event_hook(
        self,
        actions: List[str],
        name: str = "stx-event-monitor",
        start_block: Optional[int] = None,
        network: str = "testnet",
        webhook: Optional[WebhookConfig] = None,
        end_block: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a chainhook for monitoring STX events."""
        predicate = (
            ChainHookBuilder(name, network=network)
            .with_stx_event_filter(actions)
            .with_blocks(start_block, end_block)
            .with_webhook(webhook or self.default_webhook)
            .build()
        )
        return self.create_chainhook(predicate)

    def create_print_event_hook(
        self,
        contract_identifier: str,
        topic: str,
        name: str = "print-event-monitor",
        start_block: Optional[int] = None,
        network: str = "testnet",
        webhook: Optional[WebhookConfig] = None,
        end_block: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a chainhook for monitoring print events."""
        predicate = (
            ChainHookBuilder(name, network=network)
            .with_print_event_filter(contract_identifier, topic)
            .with_blocks(start_block, end_block)
            .with_webhook(webhook or self.default_webhook)
            .build()
        )
        return self.create_chainhook(predicate)

    def create_contract_deployment_hook(
        self,
        txid: str,
        name: str = "contract-deployment-monitor",
        start_block: Optional[int] = 75996,
        network: str = "testnet",
        end_block: Optional[int] = None,
        expire_after_occurrence: int = 1,
        webhook: Optional[WebhookConfig] = None,
    ) -> Dict[str, Any]:
        """Create a chainhook for monitoring contract deployments."""
        predicate = (
            ChainHookBuilder(name, network=network)
            .with_transaction_filter(txid)
            .with_blocks(start_block, end_block)
            .with_webhook(webhook or self.default_webhook)
            .with_expiration(expire_after_occurrence)
            .build()
        )
        return self.create_chainhook(predicate)

    def create_dao_x_linkage_hook(
        self,
        contract_identifier: str,
        method: str = "send",
        name: str = "dao-x-linkage",
        start_block: int = 601924,
        network: str = "mainnet",
        end_block: Optional[int] = None,
        webhook: Optional[WebhookConfig] = None,
    ) -> Dict[str, Any]:
        """Create a chainhook for monitoring DAO X linkage."""
        predicate = (
            ChainHookBuilder(name, network=network)
            .with_contract_call_filter(contract_identifier, method)
            .with_blocks(start_block, end_block)
            .with_webhook(webhook or self.default_webhook)
            .build()
        )
        return self.create_chainhook(predicate)

    # Async versions of the hook creation methods
    async def acreate_transaction_hook(
        self,
        txid: str,
        name: str = "tx-monitor",
        start_block: Optional[int] = None,
        network: str = "testnet",
        webhook: Optional[WebhookConfig] = None,
        expire_after_occurrence: int = 1,
    ) -> Dict[str, Any]:
        """Async version of create_transaction_hook."""
        predicate = (
            ChainHookBuilder(name, network=network)
            .with_transaction_filter(txid)
            .with_blocks(start_block)
            .with_webhook(webhook or self.default_webhook)
            .with_expiration(expire_after_occurrence)
            .build()
        )
        return await self.acreate_chainhook(predicate)

    async def acreate_contract_call_hook(
        self,
        contract_identifier: str,
        method: str,
        name: str = "contract-call-monitor",
        start_block: Optional[int] = None,
        network: str = "testnet",
        webhook: Optional[WebhookConfig] = None,
        end_block: Optional[int] = None,
        expire_after_occurrence: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Async version of create_contract_call_hook."""
        builder = (
            ChainHookBuilder(name, network=network)
            .with_contract_call_filter(contract_identifier, method)
            .with_blocks(start_block, end_block)
            .with_webhook(webhook or self.default_webhook)
        )

        if expire_after_occurrence is not None:
            builder.with_expiration(expire_after_occurrence)

        return await self.acreate_chainhook(builder.build())

    async def acreate_dao_x_linkage_hook(
        self,
        contract_identifier: str,
        method: str = "send",
        name: str = "dao-x-linkage",
        start_block: int = 601924,
        network: str = "mainnet",
        end_block: Optional[int] = None,
        webhook: Optional[WebhookConfig] = None,
    ) -> Dict[str, Any]:
        """Async version of create_dao_x_linkage_hook."""
        predicate = (
            ChainHookBuilder(name, network=network)
            .with_contract_call_filter(contract_identifier, method)
            .with_blocks(start_block, end_block)
            .with_webhook(webhook or self.default_webhook)
            .build()
        )
        return await self.acreate_chainhook(predicate)
