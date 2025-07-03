"""Base API client for Hiro services with rate limiting and error handling."""

import time
from functools import wraps
from typing import Any, ClassVar, Dict, List, Optional

import aiohttp
import httpx
from cachetools import TTLCache

from app.config import config
from app.lib.logger import configure_logger

from .utils import HiroApiError, HiroApiRateLimitError, HiroApiTimeoutError

logger = configure_logger(__name__)


class BaseHiroApi:
    """Base class for Hiro API clients with shared functionality."""

    # Default rate limiting settings (will be updated from API headers)
    DEFAULT_SECOND_LIMIT: ClassVar[int] = 20
    DEFAULT_MINUTE_LIMIT: ClassVar[int] = 50

    # Rate limit tracking (shared across all instances)
    _second_limit: ClassVar[int] = DEFAULT_SECOND_LIMIT
    _minute_limit: ClassVar[int] = DEFAULT_MINUTE_LIMIT
    _second_requests: ClassVar[List[float]] = []
    _minute_requests: ClassVar[List[float]] = []

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

        self._cache = TTLCache(maxsize=100, ttl=300)  # Cache with 5-minute TTL
        self._session: Optional[aiohttp.ClientSession] = None
        logger.debug("Initialized API client with base URL: %s", self.base_url)

    def _update_rate_limits(self, headers: Dict[str, str]) -> None:
        """Update rate limit settings from response headers.

        Args:
            headers: Response headers containing rate limit information
        """
        # Update limits if headers are present
        if "x-ratelimit-limit-second" in headers:
            old_limit = self.__class__._second_limit
            self.__class__._second_limit = int(headers["x-ratelimit-limit-second"])
            logger.debug(
                "Second rate limit updated: %d → %d",
                old_limit,
                self.__class__._second_limit,
            )

        if "x-ratelimit-limit-minute" in headers:
            old_limit = self.__class__._minute_limit
            self.__class__._minute_limit = int(headers["x-ratelimit-limit-minute"])
            logger.debug(
                "Minute rate limit updated: %d → %d",
                old_limit,
                self.__class__._minute_limit,
            )

        # Log remaining rate limit information if available
        if "x-ratelimit-remaining-second" in headers:
            logger.debug(
                "Second rate limit remaining: %s",
                headers["x-ratelimit-remaining-second"],
            )

        if "x-ratelimit-remaining-minute" in headers:
            logger.debug(
                "Minute rate limit remaining: %s",
                headers["x-ratelimit-remaining-minute"],
            )

        logger.debug(
            "Current rate limit state - second: %d/%d, minute: %d/%d",
            len(self.__class__._second_requests),
            self.__class__._second_limit,
            len(self.__class__._minute_requests),
            self.__class__._minute_limit,
        )

    def _rate_limit(self) -> None:
        """Implement rate limiting for both second and minute windows."""
        current_time = time.time()

        # Update second window requests
        old_second_count = len(self.__class__._second_requests)
        self.__class__._second_requests = [
            t for t in self.__class__._second_requests if current_time - t < 1.0
        ]
        new_second_count = len(self.__class__._second_requests)

        if old_second_count != new_second_count:
            logger.debug(
                "Pruned expired second window requests: %d → %d",
                old_second_count,
                new_second_count,
            )

        # Update minute window requests
        old_minute_count = len(self.__class__._minute_requests)
        self.__class__._minute_requests = [
            t for t in self.__class__._minute_requests if current_time - t < 60.0
        ]
        new_minute_count = len(self.__class__._minute_requests)

        if old_minute_count != new_minute_count:
            logger.debug(
                "Pruned expired minute window requests: %d → %d",
                old_minute_count,
                new_minute_count,
            )

        # Check second limit
        if len(self.__class__._second_requests) >= self.__class__._second_limit:
            sleep_time = self.__class__._second_requests[0] + 1.0 - current_time
            if sleep_time > 0:
                logger.warning(
                    "Second rate limit reached (%d/%d), sleeping for %.2f seconds",
                    len(self.__class__._second_requests),
                    self.__class__._second_limit,
                    sleep_time,
                )
                time.sleep(sleep_time)
                # Recalculate current time after sleep
                current_time = time.time()
        else:
            logger.debug(
                "Second rate limit check: %d/%d (%.1f%% of limit)",
                len(self.__class__._second_requests),
                self.__class__._second_limit,
                (len(self.__class__._second_requests) / self.__class__._second_limit)
                * 100,
            )

        # Check minute limit
        if len(self.__class__._minute_requests) >= self.__class__._minute_limit:
            sleep_time = self.__class__._minute_requests[0] + 60.0 - current_time
            if sleep_time > 0:
                logger.warning(
                    "Minute rate limit reached (%d/%d), sleeping for %.2f seconds",
                    len(self.__class__._minute_requests),
                    self.__class__._minute_limit,
                    sleep_time,
                )
                time.sleep(sleep_time)
        else:
            logger.debug(
                "Minute rate limit check: %d/%d (%.1f%% of limit)",
                len(self.__class__._minute_requests),
                self.__class__._minute_limit,
                (len(self.__class__._minute_requests) / self.__class__._minute_limit)
                * 100,
            )

        # Record the new request
        self.__class__._second_requests.append(time.time())
        self.__class__._minute_requests.append(time.time())

        logger.debug(
            "New request recorded: second window now %d/%d, minute window now %d/%d",
            len(self.__class__._second_requests),
            self.__class__._second_limit,
            len(self.__class__._minute_requests),
            self.__class__._minute_limit,
        )

    def _retry_on_error(func):
        """Decorator to retry API calls on transient errors."""

        @wraps(func)
        def wrapper(self, *args, **kwargs):
            for attempt in range(self.MAX_RETRIES):
                try:
                    return func(self, *args, **kwargs)
                except (
                    httpx.TimeoutException,
                    httpx.ConnectError,
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
            headers = headers or {}

            # Set default Accept header if not provided
            if "Accept" not in headers:
                headers["Accept"] = "application/json"

            # Add X-API-Key header if api_key is set
            if self.api_key:
                headers["X-API-Key"] = self.api_key

            logger.debug("Making %s request to %s", method, url)
            response = httpx.request(
                method, url, headers=headers, params=params, json=json
            )

            # Update rate limits from headers
            self._update_rate_limits(response.headers)

            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
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
            headers = headers or {}

            # Set default Accept header if not provided
            if "Accept" not in headers:
                headers["Accept"] = "application/json"

            # Add X-API-Key header if api_key is set
            if self.api_key:
                headers["X-API-Key"] = self.api_key

            logger.debug("Making async %s request to %s", method, url)
            async with self._session.request(
                method, url, headers=headers, params=params, json=json
            ) as response:
                # Update rate limits from headers
                self._update_rate_limits(response.headers)

                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            if isinstance(e, aiohttp.ClientResponseError) and e.status == 429:
                logger.error("Rate limit exceeded in async request: %s", str(e))
                raise HiroApiRateLimitError(f"Rate limit exceeded: {str(e)}")
            logger.error("Async request error: %s", str(e))
            raise HiroApiError(f"Async request error: {str(e)}")

    async def close(self) -> None:
        """Close the async session."""
        if self._session:
            await self._session.close()
            self._session = None
