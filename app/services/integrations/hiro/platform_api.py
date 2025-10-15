"""Platform API client for Hiro chainhook management."""

from typing import Any, Dict, List, Optional, cast

from app.config import config
from app.backend.factory import backend

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
            json=cast(Dict[str, Any], predicate),
        )

    async def acreate_chainhook(self, predicate: ChainHookPredicate) -> Dict[str, Any]:
        """Async version of create_chainhook."""
        return await self._amake_request(
            "POST",
            f"/v1/ext/{self.api_key}/chainhooks",
            headers={"Content-Type": "application/json"},
            json=cast(Dict[str, Any], predicate),
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

    def create_block_height_hook(
        self,
        name: str = "mainnet",
        network: str = "mainnet",
        webhook: Optional[WebhookConfig] = None,
        end_block: Optional[int] = None,
        expire_after_occurrence: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a chainhook that monitors blocks starting from the latest recorded block height.

        This function retrieves the latest block height from the chain_states table
        and creates a chainhook that monitors blocks higher than that height.

        Args:
            name: Name for the chainhook (default: "mainnet")
            network: Network to monitor (default: "mainnet")
            webhook: Webhook configuration (uses default if not provided)
            end_block: Optional end block for monitoring
            expire_after_occurrence: Optional expiration after number of occurrences

        Returns:
            Dict containing the response from the API
        """
        latest_chain_state = backend.get_latest_chain_state(network)

        if latest_chain_state is None or latest_chain_state.block_height is None:
            raise ValueError(f"No chain state found for network {network}")

        start_block = latest_chain_state.block_height

        builder = (
            ChainHookBuilder(name, network=network)
            .with_block_height_filter(start_block)
            .with_blocks(start_block, end_block)
            .with_webhook(webhook or self.default_webhook)
        )

        if expire_after_occurrence is not None:
            builder.with_expiration(expire_after_occurrence)

        return self.create_chainhook(builder.build())

    async def acreate_block_height_hook(
        self,
        name: str = "mainnet",
        network: str = "mainnet",
        webhook: Optional[WebhookConfig] = None,
        end_block: Optional[int] = None,
        expire_after_occurrence: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Async version of create_block_height_hook."""
        latest_chain_state = backend.get_latest_chain_state(network)

        if latest_chain_state is None or latest_chain_state.block_height is None:
            raise ValueError(f"No chain state found for network {network}")

        start_block = latest_chain_state.block_height

        builder = (
            ChainHookBuilder(name, network=network)
            .with_block_height_filter(start_block)
            .with_blocks(start_block, end_block)
            .with_webhook(webhook or self.default_webhook)
        )

        if expire_after_occurrence is not None:
            builder.with_expiration(expire_after_occurrence)

        return await self.acreate_chainhook(builder.build())

    def get_chainhook(self, chainhook_uuid: str) -> Dict[str, Any]:
        """Get a specific chainhook by UUID.

        Args:
            chainhook_uuid: The UUID of the chainhook to retrieve

        Returns:
            Dict containing the chainhook details
        """
        return self._make_request(
            "GET", f"/v1/ext/{self.api_key}/chainhooks/{chainhook_uuid}"
        )

    async def aget_chainhook(self, chainhook_uuid: str) -> Dict[str, Any]:
        """Async version of get_chainhook."""
        return await self._amake_request(
            "GET", f"/v1/ext/{self.api_key}/chainhooks/{chainhook_uuid}"
        )

    def list_chainhooks(self) -> List[Dict[str, Any]]:
        """Get all chainhooks for this API key.

        Returns:
            List of chainhook dictionaries
        """
        result = self._make_request("GET", f"/v1/ext/{self.api_key}/chainhooks")
        # The API returns a list, but _make_request has Dict return type
        # Cast to list since we know this endpoint returns an array
        if isinstance(result, list):
            return result
        return []

    async def alist_chainhooks(self) -> List[Dict[str, Any]]:
        """Async version of list_chainhooks."""
        result = await self._amake_request("GET", f"/v1/ext/{self.api_key}/chainhooks")
        # The API returns a list, but _amake_request has Dict return type
        # Cast to list since we know this endpoint returns an array
        if isinstance(result, list):
            return result
        return []

    def update_chainhook(
        self, chainhook_uuid: str, predicate: ChainHookPredicate
    ) -> Dict[str, Any]:
        """Update an existing chainhook.

        Args:
            chainhook_uuid: The UUID of the chainhook to update
            predicate: The new chainhook predicate configuration

        Returns:
            Dict containing the response from the API
        """
        return self._make_request(
            "PUT",
            f"/v1/ext/{self.api_key}/chainhooks/{chainhook_uuid}",
            headers={"Content-Type": "application/json"},
            json=cast(Dict[str, Any], predicate),
        )

    async def aupdate_chainhook(
        self, chainhook_uuid: str, predicate: ChainHookPredicate
    ) -> Dict[str, Any]:
        """Async version of update_chainhook."""
        return await self._amake_request(
            "PUT",
            f"/v1/ext/{self.api_key}/chainhooks/{chainhook_uuid}",
            headers={"Content-Type": "application/json"},
            json=cast(Dict[str, Any], predicate),
        )

    def delete_chainhook(self, chainhook_uuid: str) -> Dict[str, Any]:
        """Delete a chainhook.

        Args:
            chainhook_uuid: The UUID of the chainhook to delete

        Returns:
            Dict containing the response from the API
        """
        return self._make_request(
            "DELETE", f"/v1/ext/{self.api_key}/chainhooks/{chainhook_uuid}"
        )

    async def adelete_chainhook(self, chainhook_uuid: str) -> Dict[str, Any]:
        """Async version of delete_chainhook."""
        return await self._amake_request(
            "DELETE", f"/v1/ext/{self.api_key}/chainhooks/{chainhook_uuid}"
        )

    def get_chainhook_status(self, chainhook_uuid: str) -> Dict[str, Any]:
        """Get the status of a specific chainhook.

        Args:
            chainhook_uuid: The UUID of the chainhook to get status for

        Returns:
            Dict containing the chainhook status information
        """
        return self._make_request(
            "GET", f"/v1/ext/{self.api_key}/chainhooks/{chainhook_uuid}/status"
        )

    async def aget_chainhook_status(self, chainhook_uuid: str) -> Dict[str, Any]:
        """Async version of get_chainhook_status."""
        return await self._amake_request(
            "GET", f"/v1/ext/{self.api_key}/chainhooks/{chainhook_uuid}/status"
        )
