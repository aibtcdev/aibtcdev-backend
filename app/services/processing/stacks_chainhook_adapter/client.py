"""Stacks API client with rate limiting and retry logic."""

import asyncio
import random
from typing import Dict, Any, Optional
import httpx

from app.config import config
from .config import AdapterConfig
from .exceptions import APIError, RateLimitError, BlockNotFoundError


class StacksAPIClient:
    """
    Asynchronous client for interacting with the Stacks API.

    Features:
    - Rate limiting with exponential backoff
    - Automatic retry logic for failed requests
    - Comprehensive error handling
    - Support for mainnet and testnet
    - Caching support (optional)
    - Metrics collection (optional)
    """

    def __init__(self, config: Optional[AdapterConfig] = None) -> None:
        """Initialize the Stacks API client.

        Args:
            config: Configuration for the client. If None, uses default config.
        """
        self.config = config or AdapterConfig()
        self.logger = self.config.get_logger(self.__class__.__name__)

        # HTTP client with connection pooling
        self.client = httpx.AsyncClient(
            base_url=self.config.api_url,
            timeout=self.config.request_timeout,
            limits=httpx.Limits(
                max_keepalive_connections=10,
                max_connections=self.config.max_concurrent_requests * 2,
            ),
            headers=self._build_headers(),
        )

        # Semaphore for controlling concurrent requests
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)

        # Simple in-memory cache (if enabled)
        self._cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, float] = {}

        self.logger.info(
            f"Initialized StacksAPIClient for {self.config.network} ({self.config.api_url})"
        )

    def _build_headers(self) -> Dict[str, str]:
        """Build HTTP headers for requests."""
        headers = {
            "User-Agent": "stacks-chainhook-adapter/0.1.0",
            "Accept": "application/json",
        }

        # Add Hiro API key if available
        if config.api.hiro_api_key:
            headers["x-api-key"] = config.api.hiro_api_key

        headers.update(self.config.custom_headers)
        return headers

    async def _get_with_retry(self, path: str, **kwargs) -> httpx.Response:
        """Make HTTP GET request with retry logic.

        Args:
            path: API path to request
            **kwargs: Additional arguments for httpx.get()

        Returns:
            httpx.Response: Successful response

        Raises:
            APIError: For non-recoverable API errors
            RateLimitError: For rate limit errors after all retries exhausted
        """
        async with self._semaphore:
            for attempt in range(self.config.max_retries + 1):
                try:
                    # Add rate limiting delay
                    if self.config.rate_limit_delay > 0:
                        await asyncio.sleep(self.config.rate_limit_delay)

                    response = await self.client.get(path, **kwargs)
                    response.raise_for_status()

                    self.logger.debug(f"Successfully fetched {path}")
                    return response

                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 404:
                        # Don't retry 404 errors
                        raise APIError(
                            f"Resource not found: {path}",
                            status_code=404,
                            endpoint=path,
                            response_body=e.response.text[:500],
                        ) from e

                    if e.response.status_code == 429:
                        # Rate limited - use exponential backoff
                        if attempt < self.config.max_retries:
                            sleep_time = self._calculate_backoff(attempt)
                            self.logger.warning(
                                f"Rate limited by Stacks API. Retrying in {sleep_time:.2f}s... "
                                f"(Attempt {attempt + 1}/{self.config.max_retries + 1})"
                            )
                            await asyncio.sleep(sleep_time)
                            continue
                        else:
                            # Exhausted retries
                            raise RateLimitError(
                                "Rate limit exceeded and retries exhausted",
                                endpoint=path,
                            ) from e

                    # For other HTTP errors, retry with backoff
                    if attempt < self.config.max_retries:
                        sleep_time = self._calculate_backoff(attempt)
                        self.logger.warning(
                            f"HTTP error {e.response.status_code} for {path}. "
                            f"Retrying in {sleep_time:.2f}s... "
                            f"(Attempt {attempt + 1}/{self.config.max_retries + 1})"
                        )
                        await asyncio.sleep(sleep_time)
                        continue

                    # Exhausted retries
                    raise APIError(
                        f"HTTP {e.response.status_code} error for {path}",
                        status_code=e.response.status_code,
                        endpoint=path,
                        response_body=e.response.text[:500],
                    ) from e

                except httpx.RequestError as e:
                    if attempt < self.config.max_retries:
                        sleep_time = self._calculate_backoff(attempt)
                        self.logger.warning(
                            f"Request error for {path}: {e}. "
                            f"Retrying in {sleep_time:.2f}s... "
                            f"(Attempt {attempt + 1}/{self.config.max_retries + 1})"
                        )
                        await asyncio.sleep(sleep_time)
                        continue

                    raise APIError(
                        f"Request failed for {path}: {e}", endpoint=path
                    ) from e

            # Should not reach here
            raise APIError(
                f"Failed to get {path} after {self.config.max_retries + 1} attempts"
            )

    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff delay.

        Args:
            attempt: Current attempt number (0-based)

        Returns:
            float: Delay in seconds
        """
        base_delay = self.config.backoff_factor * (2**attempt)
        jitter = random.uniform(0, 1)  # Add jitter to prevent thundering herd
        return base_delay + jitter

    def _get_cache_key(self, method: str, *args) -> str:
        """Generate cache key for method and arguments."""
        return f"{method}:{':'.join(str(arg) for arg in args)}"

    def _is_cache_valid(self, key: str, ttl: int) -> bool:
        """Check if cached entry is still valid."""
        if not self.config.enable_caching:
            return False

        if key not in self._cache or key not in self._cache_timestamps:
            return False

        import time

        return (time.time() - self._cache_timestamps[key]) < ttl

    def _cache_set(self, key: str, value: Any) -> None:
        """Set cache entry."""
        if not self.config.enable_caching:
            return

        import time

        self._cache[key] = value
        self._cache_timestamps[key] = time.time()

    async def get_block_by_height(self, block_height: int) -> Dict[str, Any]:
        """Get complete block data by height.

        Args:
            block_height: Block height to fetch

        Returns:
            Dict[str, Any]: Complete block data with full transaction details

        Raises:
            BlockNotFoundError: If block is not found
            APIError: For other API errors
        """
        cache_key = self._get_cache_key("block", block_height)

        # Check cache first
        if self._is_cache_valid(cache_key, self.config.cache_ttl):
            self.logger.debug(f"Cache hit for block {block_height}")
            return self._cache[cache_key]

        try:
            self.logger.debug(
                f"Fetching complete block data for height {block_height}..."
            )
            # Use v2 endpoint for better metadata (includes parent_index_block_hash)
            v2_response = await self._get_with_retry(
                f"/extended/v2/blocks/{block_height}"
            )
            block_data = v2_response.json()

            # Log burn block height from v2 endpoint
            v2_burn_height = block_data.get("burn_block_height", "MISSING")
            v2_burn_hash = block_data.get("burn_block_hash", "MISSING")
            self.logger.info(
                f"V2 API - Block {block_height}: burn_block_height={v2_burn_height}, "
                f"burn_block_hash={v2_burn_hash[:20] if v2_burn_hash != 'MISSING' else 'MISSING'}..."
            )

            # Get transaction IDs from v1 endpoint (v2 doesn't include txs field)
            v1_response = await self._get_with_retry(
                f"/extended/v1/block/by_height/{block_height}"
            )
            v1_data = v1_response.json()

            # Log burn block height from v1 endpoint
            v1_burn_height = v1_data.get("burn_block_height", "MISSING")
            v1_burn_hash = v1_data.get("burn_block_hash", "MISSING")
            self.logger.info(
                f"V1 API - Block {block_height}: burn_block_height={v1_burn_height}, "
                f"burn_block_hash={v1_burn_hash[:20] if v1_burn_hash != 'MISSING' else 'MISSING'}..."
            )

            # Add transaction IDs from v1 to v2 data
            tx_ids = v1_data.get("txs", [])
            block_data["txs"] = tx_ids
            self.logger.debug(
                f"Block {block_height} has {len(tx_ids)} transaction IDs, fetching full details..."
            )

            # Fetch full transaction details
            full_transactions = []
            for tx_id in tx_ids:
                if isinstance(tx_id, str):
                    tx_details = await self.get_transaction(tx_id)
                    if tx_details:
                        full_transactions.append(tx_details)
                else:
                    # Already a full transaction object
                    full_transactions.append(tx_id)

            # Replace transaction IDs with full transaction data
            block_data["txs"] = full_transactions

            self.logger.info(
                f"Block {block_height} retrieved: {len(full_transactions)} full transactions"
            )

            # Cache the result
            self._cache_set(cache_key, block_data)

            return block_data

        except APIError as e:
            if e.status_code == 404:
                raise BlockNotFoundError(block_height, self.config.network) from e
            raise

    async def get_transaction(self, tx_id: str) -> Optional[Dict[str, Any]]:
        """Get transaction by ID.

        Args:
            tx_id: Transaction ID to fetch

        Returns:
            Optional[Dict[str, Any]]: Transaction data or None if not found
        """
        cache_key = self._get_cache_key("tx", tx_id)

        # Check cache first
        if self._is_cache_valid(cache_key, self.config.cache_ttl):
            self.logger.debug(f"Cache hit for transaction {tx_id[:8]}...")
            return self._cache[cache_key]

        try:
            self.logger.debug(f"Fetching transaction {tx_id[:8]}...")
            response = await self._get_with_retry(f"/extended/v1/tx/{tx_id}")
            tx_data = response.json()

            # Cache the result
            self._cache_set(cache_key, tx_data)

            return tx_data

        except APIError as e:
            if e.status_code == 404:
                self.logger.warning(f"Transaction {tx_id[:8]}... not found")
                return None
            self.logger.error(f"Error fetching transaction {tx_id[:8]}...: {e}")
            return None

    async def get_latest_block_height(self) -> int:
        """Get the latest block height.

        Returns:
            int: Latest block height

        Raises:
            APIError: For API errors
        """
        cache_key = self._get_cache_key("latest_height")

        # Use shorter cache TTL for latest height
        if self._is_cache_valid(cache_key, 30):  # 30 second cache
            return self._cache[cache_key]

        try:
            self.logger.debug("Fetching latest block height...")
            response = await self._get_with_retry("/extended/v1/block")

            data = response.json()
            results = data.get("results", [])

            if not results:
                raise APIError(
                    "No blocks found in API response", endpoint="/extended/v1/block"
                )

            # Get height from the first (latest) block
            latest_block = results[0]
            height = latest_block.get("height", 0)

            self.logger.debug(f"Latest block height: {height}")

            # Cache the result
            self._cache_set(cache_key, height)

            return height

        except Exception as e:
            raise APIError(f"Failed to get latest block height: {e}") from e

    async def get_pox_info(self) -> Dict[str, Any]:
        """Get PoX cycle information.

        Returns:
            Dict[str, Any]: PoX information
        """
        cache_key = self._get_cache_key("pox_info")

        # PoX info changes slowly, use longer cache
        if self._is_cache_valid(cache_key, self.config.pox_info_cache_ttl):
            return self._cache[cache_key]

        try:
            self.logger.debug("Fetching PoX cycle information...")
            response = await self._get_with_retry("/v2/pox")
            pox_info = response.json()

            self.logger.debug(
                f"PoX info retrieved: cycle {pox_info.get('current_cycle', {}).get('id', 'unknown')}"
            )

            # Cache the result
            self._cache_set(cache_key, pox_info)

            return pox_info

        except Exception as e:
            self.logger.error(f"Failed to get PoX info: {e}")
            return {}

    async def get_network_info(self) -> Dict[str, Any]:
        """Get network information.

        Returns:
            Dict[str, Any]: Network information
        """
        cache_key = self._get_cache_key("network_info")

        if self._is_cache_valid(cache_key, self.config.cache_ttl):
            return self._cache[cache_key]

        try:
            self.logger.debug("Fetching network information...")
            response = await self._get_with_retry("/v2/info")
            network_info = response.json()

            self.logger.debug(
                f"Network info retrieved for network: {network_info.get('network_id', 'unknown')}"
            )

            # Cache the result
            self._cache_set(cache_key, network_info)

            return network_info

        except Exception as e:
            self.logger.error(f"Failed to get network info: {e}")
            return {}

    async def get_block_signer_info(self, block_hash: str) -> Dict[str, Any]:
        """Try to get signer information for a block.

        Args:
            block_hash: Block hash to get signer info for

        Returns:
            Dict[str, Any]: Signer information if available
        """
        cache_key = self._get_cache_key("signer_info", block_hash)

        if self._is_cache_valid(cache_key, self.config.cache_ttl):
            return self._cache[cache_key]

        try:
            self.logger.debug(
                f"Attempting to fetch signer info for block {block_hash[:16]}..."
            )
            response = await self._get_with_retry(f"/extended/v2/blocks/{block_hash}")
            signer_data = response.json()

            # Extract signer fields if they exist
            signer_info = {
                "signer_bitvec": signer_data.get("signer_bitvec", ""),
                "signer_public_keys": signer_data.get("signer_public_keys", []),
                "signer_signature": signer_data.get("signer_signature", []),
            }

            if any(signer_info.values()):
                self.logger.debug(f"Found signer info for block {block_hash[:16]}")
            else:
                self.logger.debug(
                    f"No signer info available for block {block_hash[:16]}"
                )

            # Cache the result
            self._cache_set(cache_key, signer_info)

            return signer_info

        except APIError as e:
            if e.status_code == 404:
                self.logger.debug(
                    f"Signer info endpoint not found for block {block_hash[:16]}"
                )
            else:
                self.logger.warning(f"Error fetching signer info: {e}")
            return {}
        except Exception as e:
            self.logger.debug(
                f"Failed to get signer info for block {block_hash[:16]}: {e}"
            )
            return {}

    async def decode_clarity_hex(self, hex_value: str) -> Optional[Dict[str, Any]]:
        """Decode a clarity hex value using external API.

        Args:
            hex_value: Hex string to decode (with or without 0x prefix)

        Returns:
            Optional[Dict[str, Any]]: Decoded value or None if decoding fails
        """
        if not self.config.enable_hex_decoding:
            self.logger.debug("Hex decoding disabled, skipping")
            return None

        # Ensure hex value starts with 0x
        if not hex_value.startswith("0x"):
            hex_value = "0x" + hex_value

        cache_key = self._get_cache_key("hex_decode", hex_value)

        # Use shorter cache TTL for hex decoding (decoded values rarely change)
        if self._is_cache_valid(cache_key, 3600):  # 1 hour cache
            self.logger.debug(f"Cache hit for hex decode {hex_value[:20]}...")
            return self._cache[cache_key]

        try:
            self.logger.debug(f"Decoding hex value {hex_value[:20]}...")

            # Create a separate client for the decoder API with custom timeout
            async with httpx.AsyncClient(
                timeout=self.config.hex_decoder_timeout
            ) as decoder_client:
                response = await decoder_client.post(
                    self.config.hex_decoder_api_url,
                    json={"clarityValue": hex_value},
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()

                result = response.json()

                # Check if the API returned success
                if (
                    result.get("success")
                    and "data" in result
                    and "decoded" in result["data"]
                ):
                    decoded_value = result["data"]["decoded"]
                    self.logger.debug("Successfully decoded hex value")

                    # Post-process the decoded value to convert string integers to actual integers
                    processed_value = self._process_decoded_value(decoded_value)

                    # Cache the processed result
                    self._cache_set(cache_key, processed_value)

                    return processed_value
                else:
                    self.logger.warning(
                        f"Hex decoder API returned unsuccessful result: {result}"
                    )
                    return None

        except httpx.HTTPStatusError as e:
            self.logger.warning(
                f"HTTP error decoding hex value: {e.response.status_code}"
            )
            return None
        except httpx.RequestError as e:
            self.logger.warning(f"Request error decoding hex value: {e}")
            return None
        except Exception as e:
            self.logger.debug(f"Failed to decode hex value {hex_value[:20]}...: {e}")
            return None

    def _process_decoded_value(self, value: Any) -> Any:
        """
        Recursively process decoded values to convert string integers to actual integers.

        Args:
            value: The decoded value from the hex decoder API

        Returns:
            Any: Processed value with string integers converted to int
        """
        if isinstance(value, dict):
            # Recursively process dictionary values
            return {key: self._process_decoded_value(val) for key, val in value.items()}
        elif isinstance(value, list):
            # Recursively process list items
            return [self._process_decoded_value(item) for item in value]
        elif isinstance(value, str):
            # Check if string represents an integer
            if self._is_string_integer(value):
                try:
                    return int(value)
                except ValueError:
                    # If conversion fails, return original string
                    return value
            else:
                return value
        else:
            # Return other types as-is (int, float, bool, None, etc.)
            return value

    def _is_string_integer(self, s: str) -> bool:
        """
        Check if a string represents an integer (including negative numbers).

        Args:
            s: String to check

        Returns:
            bool: True if string represents an integer
        """
        if not s:
            return False

        # Handle negative numbers
        if s.startswith("-"):
            return s[1:].isdigit() and len(s) > 1

        # Handle positive numbers (including those without + sign)
        if s.startswith("+"):
            return s[1:].isdigit() and len(s) > 1

        return s.isdigit()

    async def close(self) -> None:
        """Close the HTTP client and clean up resources."""
        await self.client.aclose()
        self._cache.clear()
        self._cache_timestamps.clear()
        self.logger.info("StacksAPIClient closed")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
