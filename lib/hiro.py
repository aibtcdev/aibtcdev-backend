import aiohttp
import requests
import time
from cachetools import TTLCache, cached
from config import config
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from lib.logger import configure_logger
from typing import Any, Dict, List, Optional, TypedDict, Union

logger = configure_logger(__name__)


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


class BaseHiroApi:
    """Base class for Hiro API clients with shared functionality."""

    # Rate limiting settings
    RATE_LIMIT = 100  # requests per minute
    RATE_LIMIT_WINDOW = 60  # seconds

    # Retry settings
    MAX_RETRIES = 3
    RETRY_DELAY = 1  # seconds

    def __init__(self, base_url: str):
        """Initialize the base API client.

        Args:
            base_url: The base URL for the API
        """
        self.base_url = base_url
        self.api_key = config.api.hiro_api_key
        if not self.api_key:
            raise ValueError("HIRO_API_KEY environment variable is required")

        self._request_times: List[float] = []
        self._cache = TTLCache(maxsize=100, ttl=300)  # Cache with 5-minute TTL
        self._session: Optional[aiohttp.ClientSession] = None
        logger.info("Initialized API client with base URL: %s", self.base_url)

    def _rate_limit(self) -> None:
        """Implement rate limiting."""
        current_time = time.time()
        self._request_times = [
            t for t in self._request_times if current_time - t < self.RATE_LIMIT_WINDOW
        ]

        if len(self._request_times) >= self.RATE_LIMIT:
            sleep_time = self._request_times[0] + self.RATE_LIMIT_WINDOW - current_time
            if sleep_time > 0:
                logger.warning(
                    "Rate limit reached, sleeping for %.2f seconds", sleep_time
                )
                time.sleep(sleep_time)

        self._request_times.append(current_time)

    def _retry_on_error(func):
        """Decorator to retry API calls on transient errors."""

        @wraps(func)
        def wrapper(self, *args, **kwargs):
            for attempt in range(self.MAX_RETRIES):
                try:
                    return func(self, *args, **kwargs)
                except (
                    requests.exceptions.Timeout,
                    requests.exceptions.ConnectionError,
                ) as e:
                    if attempt == self.MAX_RETRIES - 1:
                        logger.error(
                            "Max retries reached for %s: %s", func.__name__, str(e)
                        )
                        raise HiroApiTimeoutError(f"Max retries reached: {str(e)}")
                    logger.warning(
                        "Retry attempt %d for %s: %s",
                        attempt + 1,
                        func.__name__,
                        str(e),
                    )
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
            return None

        return wrapper

    @_retry_on_error
    def _make_request(
        self,
        method: str,
        endpoint: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make an HTTP request with retries and rate limiting.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            headers: Optional request headers
            params: Optional query parameters
            json: Optional JSON body

        Returns:
            Dict containing the response data
        """
        try:
            self._rate_limit()
            url = f"{self.base_url}{endpoint}"
            headers = headers or {"Accept": "application/json"}

            logger.debug("Making %s request to %s", method, url)
            response = requests.request(
                method, url, headers=headers, params=params, json=json
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                logger.error("Rate limit exceeded: %s", str(e))
                raise HiroApiRateLimitError(f"Rate limit exceeded: {str(e)}")
            logger.error("HTTP error occurred: %s", str(e))
            raise HiroApiError(f"HTTP error occurred: {str(e)}")
        except Exception as e:
            logger.error("Unexpected error in request: %s", str(e))
            raise HiroApiError(f"Unexpected error: {str(e)}")

    async def _amake_request(
        self,
        method: str,
        endpoint: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Async version of _make_request."""
        if self._session is None:
            self._session = aiohttp.ClientSession()

        try:
            self._rate_limit()
            url = f"{self.base_url}{endpoint}"
            headers = headers or {"Accept": "application/json"}

            logger.debug("Making async %s request to %s", method, url)
            async with self._session.request(
                method, url, headers=headers, params=params, json=json
            ) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            logger.error("Async request error: %s", str(e))
            raise HiroApiError(f"Async request error: {str(e)}")

    async def close(self) -> None:
        """Close the async session."""
        if self._session:
            await self._session.close()
            self._session = None


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


class HiroApi(BaseHiroApi):
    """Client for interacting with the Hiro API.

    This client provides methods to interact with various Hiro API endpoints,
    organized by category (transactions, blocks, addresses, etc.).
    It includes features like rate limiting, retries, caching, and async support.
    """

    # API endpoint categories
    ENDPOINTS = {
        "transactions": "/extended/v1/tx",
        "blocks": "/extended/v1/block",
        "addresses": "/extended/v1/address",
        "tokens": "/extended/v1/tokens",
        "contracts": "/extended/v1/contract",
        "burnchain": "/extended/v1/burnchain",
        "search": "/extended/v1/search",
        "fee_rate": "/extended/v1/fee_rate",
        "stx_supply": "/extended/v1/stx_supply",
    }

    def __init__(self):
        """Initialize the Hiro API client."""
        super().__init__(config.api.hiro_api_url)

    @cached(lambda self: self._cache)
    def get_token_holders(self, token: str) -> Dict[str, Any]:
        """Retrieve a list of token holders with caching."""
        logger.info("Retrieving token holders for %s", token)
        return self._make_request(
            "GET", f"{self.ENDPOINTS['tokens']}/ft/{token}/holders"
        )

    def get_address_balance(self, addr: str) -> Dict[str, Any]:
        """Retrieve wallet balance for an address."""
        logger.info("Retrieving balance for address %s", addr)
        return self._make_request(
            "GET", f"{self.ENDPOINTS['addresses']}/{addr}/balances"
        )

    # Transaction related endpoints
    def get_transaction(self, tx_id: str) -> Dict[str, Any]:
        """Get transaction details."""
        return self._make_request("GET", f"/extended/v1/tx/{tx_id}")

    def get_raw_transaction(self, tx_id: str) -> Dict[str, Any]:
        """Get raw transaction details."""
        return self._make_request("GET", f"/extended/v1/tx/{tx_id}/raw")

    def get_transactions_by_block(self, block_hash: str) -> Dict[str, Any]:
        """Get transactions in a block."""
        return self._make_request("GET", f"/extended/v1/tx/block/{block_hash}")

    def get_transactions_by_block_height(self, height: int) -> Dict[str, Any]:
        """Get transactions in a block by height."""
        return self._make_request("GET", f"/extended/v1/tx/block_height/{height}")

    def get_mempool_transactions(self) -> Dict[str, Any]:
        """Get pending transactions."""
        return self._make_request("GET", "/extended/v1/tx/mempool")

    def get_dropped_mempool_transactions(self) -> Dict[str, Any]:
        """Get dropped transactions."""
        return self._make_request("GET", "/extended/v1/tx/mempool/dropped")

    def get_mempool_stats(self) -> Dict[str, Any]:
        """Get mempool statistics."""
        return self._make_request("GET", "/extended/v1/tx/mempool/stats")

    # Block related endpoints
    def get_blocks(self) -> Dict[str, Any]:
        """Get recent blocks."""
        return self._make_request("GET", "/extended/v1/block")

    def get_block_by_height(self, height: int) -> Dict[str, Any]:
        """Get block by height."""
        return self._make_request("GET", f"/extended/v1/block/by_height/{height}")

    def get_block_by_hash(self, block_hash: str) -> Dict[str, Any]:
        """Get block by hash."""
        return self._make_request("GET", f"/extended/v1/block/{block_hash}")

    def get_block_by_burn_block_height(self, burn_block_height: int) -> Dict[str, Any]:
        """Get block by burn block height."""
        return self._make_request(
            "GET", f"/extended/v1/block/by_burn_block_height/{burn_block_height}"
        )

    # Address related endpoints
    def get_address_stx_balance(self, principal: str) -> Dict[str, Any]:
        """Get STX balance."""
        return self._make_request("GET", f"/extended/v1/address/{principal}/stx")

    def get_address_transactions(self, principal: str) -> Dict[str, Any]:
        """Get transactions for an address."""
        return self._make_request(
            "GET", f"/extended/v1/address/{principal}/transactions"
        )

    def get_address_transactions_with_transfers(self, principal: str) -> Dict[str, Any]:
        """Get transactions with transfers."""
        return self._make_request(
            "GET", f"/extended/v1/address/{principal}/transactions_with_transfers"
        )

    def get_address_assets(self, principal: str) -> Dict[str, Any]:
        """Get assets owned."""
        return self._make_request("GET", f"/extended/v1/address/{principal}/assets")

    def get_address_mempool(self, principal: str) -> Dict[str, Any]:
        """Get mempool transactions."""
        return self._make_request("GET", f"/extended/v1/address/{principal}/mempool")

    def get_address_nonces(self, principal: str) -> Dict[str, Any]:
        """Get nonce information."""
        return self._make_request("GET", f"/extended/v1/address/{principal}/nonces")

    # Token related endpoints
    def get_nft_holdings(self, **params) -> Dict[str, Any]:
        """Get NFT holdings."""
        return self._make_request(
            "GET", "/extended/v1/tokens/nft/holdings", params=params
        )

    def get_nft_history(self, **params) -> Dict[str, Any]:
        """Get NFT history."""
        return self._make_request(
            "GET", "/extended/v1/tokens/nft/history", params=params
        )

    def get_nft_mints(self, **params) -> Dict[str, Any]:
        """Get NFT mints."""
        return self._make_request("GET", "/extended/v1/tokens/nft/mints", params=params)

    # Contract related endpoints
    def get_contract_by_id(self, contract_id: str) -> Dict[str, Any]:
        """Get contract details."""
        return self._make_request("GET", f"/extended/v1/contract/{contract_id}")

    def get_contract_events(self, contract_id: str) -> Dict[str, Any]:
        """Get contract events."""
        return self._make_request("GET", f"/extended/v1/contract/{contract_id}/events")

    def get_contract_source(
        self, contract_address: str, contract_name: str
    ) -> Dict[str, Any]:
        """Get the source code of a contract.

        Args:
            contract_address: The contract's address
            contract_name: The name of the contract

        Returns:
            Dict containing the contract source code and metadata
        """
        return self._make_request(
            "GET", f"/v2/contracts/source/{contract_address}/{contract_name}"
        )

    # Burnchain related endpoints
    def get_burnchain_rewards(self) -> Dict[str, Any]:
        """Get burnchain rewards."""
        return self._make_request("GET", "/extended/v1/burnchain/rewards")

    def get_address_burnchain_rewards(self, address: str) -> Dict[str, Any]:
        """Get burnchain rewards for an address."""
        return self._make_request("GET", f"/extended/v1/burnchain/rewards/{address}")

    def get_address_total_burnchain_rewards(self, address: str) -> Dict[str, Any]:
        """Get total burnchain rewards."""
        return self._make_request(
            "GET", f"/extended/v1/burnchain/rewards/{address}/total"
        )

    # Utility endpoints
    @cached(lambda self: self._cache)
    def get_fee_rate(self) -> Dict[str, Any]:
        """Get current fee rate with caching."""
        logger.info("Retrieving current fee rate")
        return self._make_request("GET", "/extended/v1/fee_rate")

    @cached(lambda self: self._cache)
    def get_stx_supply(self) -> Dict[str, Any]:
        """Get STX supply with caching."""
        logger.info("Retrieving STX supply")
        return self._make_request("GET", "/extended/v1/stx_supply")

    @cached(lambda self: self._cache)
    def get_stx_price(self) -> float:
        """Get the current STX price with caching."""
        logger.info("Retrieving current STX price")
        response = requests.get(
            "https://explorer.hiro.so/stxPrice", params={"blockBurnTime": "current"}
        )
        response.raise_for_status()
        return response.json()["price"]

    # @cached(lambda self: self._cache)
    def get_current_block_height(self) -> int:
        """Get the current block height"""
        logger.info("Retrieving current block height")
        endpoint = "/extended/v1/block"
        logger.debug(f"Current block height endpoint: {endpoint}")
        response = self._make_request(
            method="GET", endpoint=f"{endpoint}", params={"limit": 1, "offset": 0}
        )
        logger.debug(f"Response: {response}")
        return response["results"][0]["height"]

    def search(self, query_id: str) -> Dict[str, Any]:
        """Search for blocks, transactions, contracts, or addresses."""
        logger.info("Performing search for query: %s", query_id)
        return self._make_request("GET", f"{self.ENDPOINTS['search']}/{query_id}")

    # Async versions of selected methods
    async def aget_token_holders(self, token: str) -> Dict[str, Any]:
        """Async version of get_token_holders."""
        logger.info("Async retrieving token holders for %s", token)
        return await self._amake_request(
            "GET", f"{self.ENDPOINTS['tokens']}/ft/{token}/holders"
        )

    async def aget_address_balance(self, addr: str) -> Dict[str, Any]:
        """Async version of get_address_balance."""
        logger.info("Async retrieving balance for address %s", addr)
        return await self._amake_request(
            "GET", f"{self.ENDPOINTS['addresses']}/{addr}/balances"
        )

    # ... add async versions of other methods as needed ...
