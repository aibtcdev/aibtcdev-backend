"""Base API client for Hiro services with rate limiting and error handling."""

import time
from functools import wraps
from typing import Any, Callable, ClassVar, Dict, List, Mapping, Optional

import aiohttp
import asyncio
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
        logger.info("Hiro API client initialized", extra={"base_url": self.base_url})

    def _update_rate_limits(self, headers: Mapping[str, str]) -> None:
        """Update rate limit settings from response headers.

        Args:
            headers: Response headers containing rate limit information
        """
        # Update limits if headers are present
        updated_limits = {}
        if "x-ratelimit-limit-stacks-second" in headers:
            old_limit = self.__class__._second_limit
            self.__class__._second_limit = int(
                headers["x-ratelimit-limit-stacks-second"]
            )
            if old_limit != self.__class__._second_limit:
                updated_limits["second"] = self.__class__._second_limit

        if "x-ratelimit-limit-stacks-minute" in headers:
            old_limit = self.__class__._minute_limit
            self.__class__._minute_limit = int(
                headers["x-ratelimit-limit-stacks-minute"]
            )
            if old_limit != self.__class__._minute_limit:
                updated_limits["minute"] = self.__class__._minute_limit

        if updated_limits:
            logger.info("Rate limits updated", extra={"limits": updated_limits})

        # Track remaining limits for monitoring
        remaining = {}
        if "x-ratelimit-remaining-stacks-second" in headers:
            remaining["second"] = int(headers["x-ratelimit-remaining-stacks-second"])
        if "x-ratelimit-remaining-stacks-minute" in headers:
            remaining["minute"] = int(headers["x-ratelimit-remaining-stacks-minute"])

        if remaining:
            # Only log if we're getting close to limits (< 20% remaining)
            second_pct = (
                remaining.get("second", 0) / self.__class__._second_limit
                if self.__class__._second_limit > 0
                else 1
            )
            minute_pct = (
                remaining.get("minute", 0) / self.__class__._minute_limit
                if self.__class__._minute_limit > 0
                else 1
            )

            if second_pct < 0.2 or minute_pct < 0.2:
                logger.warning(
                    "Rate limit capacity low",
                    extra={
                        "remaining": remaining,
                        "limits": {
                            "second": self.__class__._second_limit,
                            "minute": self.__class__._minute_limit,
                        },
                    },
                )

    def _rate_limit(self) -> None:
        """Implement rate limiting for both second and minute windows."""
        current_time = time.time()

        # Clean up expired requests from tracking windows
        self.__class__._second_requests = [
            t for t in self.__class__._second_requests if current_time - t < 1.0
        ]
        self.__class__._minute_requests = [
            t for t in self.__class__._minute_requests if current_time - t < 60.0
        ]

        # Check and enforce rate limits
        second_count = len(self.__class__._second_requests)
        minute_count = len(self.__class__._minute_requests)

        # Check second limit
        if second_count >= self.__class__._second_limit:
            sleep_time = self.__class__._second_requests[0] + 1.0 - current_time
            if sleep_time > 0:
                logger.warning(
                    "Rate limit reached, waiting before next request",
                    extra={
                        "rate_limit_type": "second",
                        "current_count": second_count,
                        "limit": self.__class__._second_limit,
                        "wait_time_seconds": round(sleep_time, 2),
                    },
                )
                time.sleep(sleep_time)
                current_time = time.time()

        # Check minute limit
        if minute_count >= self.__class__._minute_limit:
            sleep_time = self.__class__._minute_requests[0] + 60.0 - current_time
            if sleep_time > 0:
                logger.warning(
                    "Rate limit reached, waiting before next request",
                    extra={
                        "rate_limit_type": "minute",
                        "current_count": minute_count,
                        "limit": self.__class__._minute_limit,
                        "wait_time_seconds": round(sleep_time, 2),
                    },
                )
                time.sleep(sleep_time)

        # Record the new request
        self.__class__._second_requests.append(time.time())
        self.__class__._minute_requests.append(time.time())

    @staticmethod
    def _retry_on_error(func: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator to retry API calls on transient errors."""

        @wraps(func)
        def wrapper(self, *args, **kwargs):
            for attempt in range(self.MAX_RETRIES):
                try:
                    return func(self, *args, **kwargs)
                except (
                    httpx.TimeoutException,
                    httpx.ConnectError,
                    HiroApiRateLimitError,
                ) as e:
                    if attempt == self.MAX_RETRIES - 1:
                        logger.error(
                            "Request failed after all retry attempts",
                            extra={
                                "function": func.__name__,
                                "max_retries": self.MAX_RETRIES,
                                "error": str(e),
                            },
                        )
                        if isinstance(e, HiroApiRateLimitError):
                            raise
                        raise HiroApiTimeoutError(f"Max retries reached: {str(e)}")

                    retry_delay = self.RETRY_DELAY * (2**attempt)  # Exponential backoff
                    if (
                        isinstance(e, HiroApiRateLimitError)
                        and "retry-after" in e.response.headers
                    ):
                        retry_delay = max(
                            retry_delay, int(e.response.headers["retry-after"])
                        )
                    logger.warning(
                        "Request failed, retrying",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt + 1,
                            "max_retries": self.MAX_RETRIES,
                            "retry_delay_seconds": retry_delay,
                            "error": str(e),
                        },
                    )
                    time.sleep(retry_delay)
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

            logger.debug(
                "API request initiated",
                extra={"request": {"method": method, "endpoint": endpoint, "url": url}},
            )

            response = httpx.request(
                method, url, headers=headers, params=params, json=json
            )

            # Update rate limits from headers
            self._update_rate_limits(response.headers)

            response.raise_for_status()

            logger.debug(
                "API request completed successfully",
                extra={
                    "request": {"method": method, "endpoint": endpoint},
                    "response": {"status_code": response.status_code},
                },
            )

            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.error(
                    "API rate limit exceeded",
                    extra={
                        "request": {"method": method, "endpoint": endpoint},
                        "response": {"status_code": e.response.status_code},
                        "error": str(e),
                    },
                )
                raise HiroApiRateLimitError(f"Rate limit exceeded: {str(e)}") from e

            logger.error(
                "API request failed with HTTP error",
                extra={
                    "request": {"method": method, "endpoint": endpoint},
                    "response": {"status_code": e.response.status_code},
                    "error": str(e),
                },
            )
            raise HiroApiError(f"HTTP error occurred: {str(e)}")
        except Exception as e:
            logger.error(
                "API request failed with unexpected error",
                extra={
                    "request": {"method": method, "endpoint": endpoint},
                    "error": str(e),
                },
            )
            raise HiroApiError(f"Unexpected error: {str(e)}")

    @staticmethod
    async def _aretry_on_error(func):
        """Async decorator to retry API calls on transient errors."""

        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            for attempt in range(self.MAX_RETRIES):
                try:
                    return await func(self, *args, **kwargs)
                except (
                    aiohttp.ClientTimeout,
                    aiohttp.ClientConnectionError,
                    HiroApiRateLimitError,
                ) as e:
                    if attempt == self.MAX_RETRIES - 1:
                        logger.error(
                            "Async request failed after all retry attempts",
                            extra={
                                "function": func.__name__,
                                "max_retries": self.MAX_RETRIES,
                                "error": str(e),
                            },
                        )
                        if isinstance(e, HiroApiRateLimitError):
                            raise
                        raise HiroApiTimeoutError(f"Max retries reached: {str(e)}")

                    retry_delay = self.RETRY_DELAY * (2**attempt)  # Exponential backoff
                    if (
                        isinstance(e, HiroApiRateLimitError)
                        and "retry-after" in e.response.headers
                    ):
                        retry_delay = max(
                            retry_delay, int(e.response.headers["retry-after"])
                        )
                    logger.warning(
                        "Async request failed, retrying",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt + 1,
                            "max_retries": self.MAX_RETRIES,
                            "retry_delay_seconds": retry_delay,
                            "error": str(e),
                        },
                    )
                    await asyncio.sleep(retry_delay)
            return None

        return wrapper

    @_aretry_on_error
    async def _amake_request(
        self,
        method: str,
        endpoint: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Async version of _make_request."""
        # Create session if it doesn't exist or is closed
        if self._session is None or self._session.closed:
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

            logger.debug(
                "Async API request initiated",
                extra={"request": {"method": method, "endpoint": endpoint, "url": url}},
            )

            async with self._session.request(
                method, url, headers=headers, params=params, json=json
            ) as response:
                # Update rate limits from headers
                self._update_rate_limits(response.headers)

                response.raise_for_status()

                logger.debug(
                    "Async API request completed successfully",
                    extra={
                        "request": {"method": method, "endpoint": endpoint},
                        "response": {"status_code": response.status},
                    },
                )

                return await response.json()
        except aiohttp.ClientResponseError as e:
            if e.status == 429:
                logger.error(
                    "Async API rate limit exceeded",
                    extra={
                        "request": {"method": method, "endpoint": endpoint},
                        "response": {"status_code": e.status},
                        "error": str(e),
                    },
                )
                raise HiroApiRateLimitError(f"Rate limit exceeded: {str(e)}") from e

            logger.error(
                "Async API request failed with client error",
                extra={
                    "request": {"method": method, "endpoint": endpoint},
                    "error": str(e),
                },
            )
            raise HiroApiError(f"Async request error: {str(e)}")
        except Exception as e:
            logger.error(
                "Async API request failed with unexpected error",
                extra={
                    "request": {"method": method, "endpoint": endpoint},
                    "error": str(e),
                },
            )
            raise HiroApiError(f"Unexpected error: {str(e)}")

    async def close(self) -> None:
        """Close the async session."""
        if self._session:
            logger.debug("Closing Hiro API async session")
            await self._session.close()
            self._session = None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - ensures session cleanup."""
        await self.close()
        return False
