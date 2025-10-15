"""Hiro API client for blockchain data queries and operations."""

import httpx
import time
import asyncio
from typing import Any, Dict

from app.config import config
from app.lib.logger import configure_logger

from .base import BaseHiroApi
from .models import BlockTransactionsResponse, HiroApiInfo

logger = configure_logger(__name__)


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
        "metadata": "/metadata/v1",
    }

    def __init__(self):
        """Initialize the Hiro API client."""
        super().__init__(config.api.hiro_api_url)

    def get_token_holders(
        self, token: str, limit: int = 20, offset: int = 0
    ) -> Dict[str, Any]:
        """Retrieve a list of token holders with caching and pagination support.

        Args:
            token: Token identifier (contract principal or symbol)
            limit: Maximum number of holders to return (default: 20)
            offset: Pagination offset (default: 0)

        Returns:
            Dict containing the response with holders data
        """
        logger.debug(
            "Retrieving token holders for %s with limit %d offset %d",
            token,
            limit,
            offset,
        )
        return self._make_request(
            "GET",
            f"{self.ENDPOINTS['tokens']}/ft/{token}/holders",
            params={"limit": limit, "offset": offset},
        )

    def get_all_token_holders(self, token: str, page_size: int = 20) -> Dict[str, Any]:
        """Get all token holders by paginating through results.

        Args:
            token: Token identifier (contract principal or symbol)
            page_size: Number of holders per page request (default: 20)

        Returns:
            Combined response with all holders
        """
        logger.debug("Getting all token holders for %s", token)

        # Get first page to determine total
        first_page = self.get_token_holders(token, limit=page_size)

        # If we got all holders in the first request, return it
        total_holders = first_page.get("total", 0)
        if total_holders <= page_size:
            return first_page

        # Initialize with first page results
        all_holders = first_page.get("results", []).copy()

        # Paginate through the rest
        remaining = total_holders - page_size
        offset = page_size

        while remaining > 0:
            current_limit = min(page_size, remaining)
            logger.debug(
                "Fetching %d more token holders with offset %d", current_limit, offset
            )

            page = self.get_token_holders(token, limit=current_limit, offset=offset)
            page_results = page.get("results", [])
            all_holders.extend(page_results)

            offset += current_limit
            remaining -= current_limit

            # Space out requests to avoid bursting
            time.sleep(1)

        # Create combined response
        return {
            "total_supply": first_page.get("total_supply"),
            "limit": total_holders,
            "offset": 0,
            "total": total_holders,
            "results": all_holders,
        }

    async def aget_token_holders(
        self, token: str, limit: int = 20, offset: int = 0
    ) -> Dict[str, Any]:
        """Async version of get_token_holders with pagination support.

        Args:
            token: Token identifier (contract principal or symbol)
            limit: Maximum number of holders to return (default: 20)
            offset: Pagination offset (default: 0)

        Returns:
            Dict containing the response with holders data
        """
        logger.debug(
            "Async retrieving token holders for %s with limit %d offset %d",
            token,
            limit,
            offset,
        )
        return await self._amake_request(
            "GET",
            f"{self.ENDPOINTS['tokens']}/ft/{token}/holders",
            params={"limit": limit, "offset": offset},
        )

    async def aget_all_token_holders(
        self, token: str, page_size: int = 20
    ) -> Dict[str, Any]:
        """Async version to get all token holders by paginating through results.

        Args:
            token: Token identifier (contract principal or symbol)
            page_size: Number of holders per page request (default: 20)

        Returns:
            Combined response with all holders
        """
        logger.debug("Async getting all token holders for %s", token)

        # Get first page to determine total
        first_page = await self.aget_token_holders(token, limit=page_size)

        # If we got all holders in the first request, return it
        total_holders = first_page.get("total", 0)
        if total_holders <= page_size:
            return first_page

        # Initialize with first page results
        all_holders = first_page.get("results", []).copy()

        # Paginate through the rest
        remaining = total_holders - page_size
        offset = page_size

        while remaining > 0:
            current_limit = min(page_size, remaining)
            logger.debug(
                "Async fetching %d more token holders with offset %d",
                current_limit,
                offset,
            )

            page = await self.aget_token_holders(
                token, limit=current_limit, offset=offset
            )
            page_results = page.get("results", [])
            all_holders.extend(page_results)

            offset += current_limit
            remaining -= current_limit

            # Space out requests to avoid bursting
            await asyncio.sleep(1)

        # Create combined response
        return {
            "total_supply": first_page.get("total_supply"),
            "limit": total_holders,
            "offset": 0,
            "total": total_holders,
            "results": all_holders,
        }

    def get_token_metadata(self, token: str) -> Dict[str, Any]:
        """Get token metadata from the Hiro metadata API.

        Args:
            token: Token contract principal (e.g., "ST123...ABC.my-token")

        Returns:
            Dict containing token metadata including symbol, name, description, etc.
        """
        logger.debug("Getting token metadata for %s", token)
        return self._make_request(
            "GET",
            f"{self.ENDPOINTS['metadata']}/ft/{token}",
        )

    async def aget_token_metadata(self, token: str) -> Dict[str, Any]:
        """Async version of get_token_metadata.

        Args:
            token: Token contract principal (e.g., "ST123...ABC.my-token")

        Returns:
            Dict containing token metadata including symbol, name, description, etc.
        """
        logger.debug("Async getting token metadata for %s", token)
        return await self._amake_request(
            "GET",
            f"{self.ENDPOINTS['metadata']}/ft/{token}",
        )

    def get_address_balance(self, addr: str) -> Dict[str, Any]:
        """Retrieve wallet balance for an address."""
        logger.debug("Retrieving balance for address %s", addr)
        return self._make_request(
            "GET", f"{self.ENDPOINTS['addresses']}/{addr}/balances"
        )

    async def aget_address_balance(self, addr: str) -> Dict[str, Any]:
        """Async version of get_address_balance."""
        logger.debug("Async retrieving balance for address %s", addr)
        return await self._amake_request(
            "GET", f"{self.ENDPOINTS['addresses']}/{addr}/balances"
        )

    # Transaction related endpoints
    def get_transaction(self, tx_id: str) -> Dict[str, Any]:
        """Get transaction details."""
        return self._make_request("GET", f"/extended/v1/tx/{tx_id}")

    def get_raw_transaction(self, tx_id: str) -> Dict[str, Any]:
        """Get raw transaction details."""
        return self._make_request("GET", f"/extended/v1/tx/{tx_id}/raw")

    def get_transactions_by_block(
        self, block_height: int, limit: int = 50, offset: int = 0
    ) -> BlockTransactionsResponse:
        """Get transactions in a block.

        Args:
            block_height: The height of the block to get transactions for
            limit: The maximum number of transactions to return (default: 50)
            offset: Pagination offset (default: 0)

        Returns:
            Typed response containing transaction data
        """
        logger.debug(
            "Getting transactions for block height %d with limit %d offset %d",
            block_height,
            limit,
            offset,
        )
        response = self._make_request(
            "GET",
            f"/extended/v2/blocks/{block_height}/transactions",
            params={"limit": limit, "offset": offset},
        )

        logger.debug(f"API response type: {type(response)}")
        logger.debug(
            f"API response keys: {response.keys() if isinstance(response, dict) else 'Not a dict'}"
        )

        # For debugging purposes
        if (
            "results" in response
            and response["results"]
            and isinstance(response["results"], list)
        ):
            logger.debug(f"First result type: {type(response['results'][0])}")
            logger.debug(
                f"First result sample keys: {list(response['results'][0].keys())[:5]}"
            )

        # We're getting dictionaries back, so create BlockTransactionsResponse manually
        # This ensures we don't lose the raw data structure if dataclass conversion fails
        try:
            return BlockTransactionsResponse(**response)
        except Exception as e:
            logger.warning(f"Error creating BlockTransactionsResponse: {str(e)}")
            # Fall back to returning a raw dictionary-based response
            return BlockTransactionsResponse(
                limit=response.get("limit", 0),
                offset=response.get("offset", 0),
                total=response.get("total", 0),
                results=response.get("results", []),
            )

    def get_stx_price(self) -> float:
        """Get the current STX price with caching."""
        logger.debug("Retrieving current STX price")
        response = httpx.get(
            "https://explorer.hiro.so/stxPrice", params={"blockBurnTime": "current"}
        )
        response.raise_for_status()
        return response.json()["price"]

    def get_current_block_height(self) -> int:
        """Get the current block height"""
        logger.debug("Retrieving current block height")
        logger.debug(f"Endpoint: {self.ENDPOINTS['blocks']}")
        response = self._make_request(
            method="GET",
            endpoint=self.ENDPOINTS["blocks"],
            params={"limit": 1, "offset": 0},
        )
        logger.debug(f"Response: {response}")
        return response["results"][0]["height"]

    def get_info(self) -> HiroApiInfo:
        """Get Hiro API server information and chain tip.

        Returns:
            Server information including version, status, and current chain tip
        """
        logger.debug("Retrieving Hiro API server info")
        response = self._make_request("GET", "/extended")
        return HiroApiInfo(**response)

    async def aget_info(self) -> HiroApiInfo:
        """Async version of get_info.

        Returns:
            Server information including version, status, and current chain tip
        """
        logger.debug("Async retrieving Hiro API server info")
        response = await self._amake_request("GET", "/extended")
        return HiroApiInfo(**response)

    def search(self, query_id: str) -> Dict[str, Any]:
        """Search for blocks, transactions, contracts, or addresses."""
        logger.debug("Performing search for query: %s", query_id)
        return self._make_request("GET", f"{self.ENDPOINTS['search']}/{query_id}")

    # Additional methods from the original file
    def get_all_transactions_by_block(
        self, block_height: int, page_size: int = 50
    ) -> BlockTransactionsResponse:
        """Get all transactions in a block by paginating through results."""
        logger.debug(f"Getting all transactions for block height {block_height}")

        # Get first page to determine total
        first_page = self.get_transactions_by_block(block_height, limit=page_size)

        # If we got all transactions in the first request, return it
        if first_page.total <= page_size:
            return first_page

        # Initialize with first page results
        all_transactions = first_page.results.copy()

        # Paginate through the rest
        remaining = first_page.total - page_size
        offset = page_size

        while remaining > 0:
            current_limit = min(page_size, remaining)
            logger.debug(
                f"Fetching {current_limit} more transactions with offset {offset}"
            )

            page = self.get_transactions_by_block(
                block_height, limit=current_limit, offset=offset
            )

            all_transactions.extend(page.results)
            offset += current_limit
            remaining -= current_limit

        # Create combined response
        return BlockTransactionsResponse(
            limit=first_page.total,
            offset=0,
            total=first_page.total,
            results=all_transactions,
        )

    def get_transactions_by_block_hash(self, block_hash: str) -> Dict[str, Any]:
        """Get transactions in a block by hash."""
        return self._make_request("GET", f"/extended/v1/tx/block/{block_hash}")

    def get_mempool_transactions(self) -> Dict[str, Any]:
        """Get pending transactions."""
        return self._make_request("GET", "/extended/v1/tx/mempool")

    def get_blocks(self) -> Dict[str, Any]:
        """Get recent blocks."""
        return self._make_request("GET", "/extended/v1/block")

    def get_block_by_height(self, height: int) -> Dict[str, Any]:
        """Get block by height."""
        return self._make_request("GET", f"/extended/v1/block/by_height/{height}")

    def get_contract_by_id(self, contract_id: str) -> Dict[str, Any]:
        """Get contract details."""
        return self._make_request("GET", f"/extended/v1/contract/{contract_id}")

    def get_fee_rate(self) -> Dict[str, Any]:
        """Get current fee rate with caching."""
        logger.debug("Retrieving current fee rate")
        return self._make_request("GET", "/extended/v1/fee_rate")

    def get_stx_supply(self) -> Dict[str, Any]:
        """Get STX supply with caching."""
        logger.debug("Retrieving STX supply")
        return self._make_request("GET", "/extended/v1/stx_supply")
