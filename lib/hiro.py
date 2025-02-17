import aiohttp
import requests
import time
from cachetools import TTLCache, cached
from config import config
from functools import wraps
from lib.logger import configure_logger
from typing import Any, Dict, List, Optional

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


class HiroApi:
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

    # Rate limiting settings
    RATE_LIMIT = 100  # requests per minute
    RATE_LIMIT_WINDOW = 60  # seconds

    # Retry settings
    MAX_RETRIES = 3
    RETRY_DELAY = 1  # seconds

    def __init__(self):
        """Initialize the Hiro API client."""
        self.base_url = config.api.hiro_api_url
        self._request_times: List[float] = []
        self._cache = TTLCache(maxsize=100, ttl=300)  # Cache with 5-minute TTL
        self._session = None
        logger.info("Initialized Hiro API client with base URL: %s", self.base_url)

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
    def _get(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make a GET request to the Hiro API with rate limiting and retries."""
        try:
            self._rate_limit()
            url = self.base_url + endpoint
            headers = {"Accept": "application/json"}

            logger.debug("Making GET request to %s with params %s", url, params)
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()

            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                logger.error("Rate limit exceeded: %s", str(e))
                raise HiroApiRateLimitError(f"Rate limit exceeded: {str(e)}")
            logger.error("HTTP error occurred: %s", str(e))
            raise HiroApiError(f"HTTP error occurred: {str(e)}")
        except Exception as e:
            logger.error("Unexpected error in GET request: %s", str(e))
            raise HiroApiError(f"Unexpected error: {str(e)}")

    async def _aget(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Async version of _get."""
        if self._session is None:
            self._session = aiohttp.ClientSession()

        try:
            self._rate_limit()
            url = self.base_url + endpoint
            headers = {"Accept": "application/json"}

            logger.debug("Making async GET request to %s with params %s", url, params)
            async with self._session.get(
                url, headers=headers, params=params
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

    @cached(lambda self: self._cache)
    def get_token_holders(self, token: str) -> Dict[str, Any]:
        """Retrieve a list of token holders with caching."""
        logger.info("Retrieving token holders for %s", token)
        return self._get(f"{self.ENDPOINTS['tokens']}/ft/{token}/holders")

    def get_address_balance(self, addr: str) -> Dict[str, Any]:
        """Retrieve wallet balance for an address."""
        logger.info("Retrieving balance for address %s", addr)
        return self._get(f"{self.ENDPOINTS['addresses']}/{addr}/balances")

    # Transaction related endpoints
    def get_transaction(self, tx_id: str) -> dict:
        """Get transaction details."""
        return self._get(f"/extended/v1/tx/{tx_id}")

    def get_raw_transaction(self, tx_id: str) -> dict:
        """Get raw transaction details."""
        return self._get(f"/extended/v1/tx/{tx_id}/raw")

    def get_transactions_by_block(self, block_hash: str) -> dict:
        """Get transactions in a block."""
        return self._get(f"/extended/v1/tx/block/{block_hash}")

    def get_transactions_by_block_height(self, height: int) -> dict:
        """Get transactions in a block by height."""
        return self._get(f"/extended/v1/tx/block_height/{height}")

    def get_mempool_transactions(self) -> dict:
        """Get pending transactions."""
        return self._get("/extended/v1/tx/mempool")

    def get_dropped_mempool_transactions(self) -> dict:
        """Get dropped transactions."""
        return self._get("/extended/v1/tx/mempool/dropped")

    def get_mempool_stats(self) -> dict:
        """Get mempool statistics."""
        return self._get("/extended/v1/tx/mempool/stats")

    # Block related endpoints
    def get_blocks(self) -> dict:
        """Get recent blocks."""
        return self._get("/extended/v1/block")

    def get_block_by_height(self, height: int) -> dict:
        """Get block by height."""
        return self._get(f"/extended/v1/block/by_height/{height}")

    def get_block_by_hash(self, block_hash: str) -> dict:
        """Get block by hash."""
        return self._get(f"/extended/v1/block/{block_hash}")

    def get_block_by_burn_block_height(self, burn_block_height: int) -> dict:
        """Get block by burn block height."""
        return self._get(f"/extended/v1/block/by_burn_block_height/{burn_block_height}")

    # Address related endpoints
    def get_address_stx_balance(self, principal: str) -> dict:
        """Get STX balance."""
        return self._get(f"/extended/v1/address/{principal}/stx")

    def get_address_transactions(self, principal: str) -> dict:
        """Get transactions for an address."""
        return self._get(f"/extended/v1/address/{principal}/transactions")

    def get_address_transactions_with_transfers(self, principal: str) -> dict:
        """Get transactions with transfers."""
        return self._get(
            f"/extended/v1/address/{principal}/transactions_with_transfers"
        )

    def get_address_assets(self, principal: str) -> dict:
        """Get assets owned."""
        return self._get(f"/extended/v1/address/{principal}/assets")

    def get_address_mempool(self, principal: str) -> dict:
        """Get mempool transactions."""
        return self._get(f"/extended/v1/address/{principal}/mempool")

    def get_address_nonces(self, principal: str) -> dict:
        """Get nonce information."""
        return self._get(f"/extended/v1/address/{principal}/nonces")

    # Token related endpoints
    def get_nft_holdings(self, **params) -> dict:
        """Get NFT holdings."""
        return self._get("/extended/v1/tokens/nft/holdings", params=params)

    def get_nft_history(self, **params) -> dict:
        """Get NFT history."""
        return self._get("/extended/v1/tokens/nft/history", params=params)

    def get_nft_mints(self, **params) -> dict:
        """Get NFT mints."""
        return self._get("/extended/v1/tokens/nft/mints", params=params)

    # Contract related endpoints
    def get_contract_by_id(self, contract_id: str) -> dict:
        """Get contract details."""
        return self._get(f"/extended/v1/contract/{contract_id}")

    def get_contract_events(self, contract_id: str) -> dict:
        """Get contract events."""
        return self._get(f"/extended/v1/contract/{contract_id}/events")

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
        response = self._get(f"/v2/contracts/source/{contract_address}/{contract_name}")
        return response.json()

    # Burnchain related endpoints
    def get_burnchain_rewards(self) -> dict:
        """Get burnchain rewards."""
        return self._get("/extended/v1/burnchain/rewards")

    def get_address_burnchain_rewards(self, address: str) -> dict:
        """Get burnchain rewards for an address."""
        return self._get(f"/extended/v1/burnchain/rewards/{address}")

    def get_address_total_burnchain_rewards(self, address: str) -> dict:
        """Get total burnchain rewards."""
        return self._get(f"/extended/v1/burnchain/rewards/{address}/total")

    # Utility endpoints
    @cached(lambda self: self._cache)
    def get_fee_rate(self) -> dict:
        """Get current fee rate with caching."""
        logger.info("Retrieving current fee rate")
        return self._get("/extended/v1/fee_rate")

    @cached(lambda self: self._cache)
    def get_stx_supply(self) -> dict:
        """Get STX supply with caching."""
        logger.info("Retrieving STX supply")
        return self._get("/extended/v1/stx_supply")

    @cached(lambda self: self._cache)
    def get_stx_price(self) -> float:
        """Get the current STX price with caching."""
        try:
            logger.info("Retrieving current STX price")
            url = "https://explorer.hiro.so/stxPrice"
            params = {"blockBurnTime": "current"}
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()["price"]
        except Exception as e:
            logger.error("Failed to get STX price: %s", str(e))
            raise HiroApiError(f"Failed to get STX price: {str(e)}")

    @cached(lambda self: self._cache)
    def get_current_block_height(self) -> int:
        """Get the current block height with caching."""
        try:
            logger.info("Retrieving current block height")
            response = self._get(
                f"{self.ENDPOINTS['blocks']}/v2", params={"limit": 1, "offset": 0}
            )
            return response["results"][0]["height"]
        except Exception as e:
            logger.error("Failed to get current block height: %s", str(e))
            raise HiroApiError(f"Failed to get current block height: {str(e)}")

    def search(self, query_id: str) -> dict:
        """Search for blocks, transactions, contracts, or addresses."""
        logger.info("Performing search for query: %s", query_id)
        return self._get(f"{self.ENDPOINTS['search']}/{query_id}")

    # Add async versions of methods
    async def aget_token_holders(self, token: str) -> Dict[str, Any]:
        """Async version of get_token_holders."""
        logger.info("Async retrieving token holders for %s", token)
        return await self._aget(f"{self.ENDPOINTS['tokens']}/ft/{token}/holders")

    async def aget_address_balance(self, addr: str) -> Dict[str, Any]:
        """Async version of get_address_balance."""
        logger.info("Async retrieving balance for address %s", addr)
        return await self._aget(f"{self.ENDPOINTS['addresses']}/{addr}/balances")

    # ... add async versions of other methods as needed ...
