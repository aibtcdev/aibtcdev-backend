"""Configuration for the Stacks Chainhook Adapter."""

import logging
import os
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class AdapterConfig:
    """Configuration class for the Stacks Chainhook Adapter.

    This class holds all configuration options for the adapter, including
    API settings, retry policies, and feature flags.

    Attributes:
        api_url: Base URL for the Stacks API
        network: Network identifier ("mainnet" or "testnet")
        max_retries: Maximum number of retry attempts for failed requests
        backoff_factor: Exponential backoff factor for retries
        request_timeout: Timeout in seconds for individual HTTP requests
        max_concurrent_requests: Maximum number of concurrent API requests
        enable_caching: Whether to enable response caching
        cache_ttl: Time-to-live for cached responses in seconds
        log_level: Logging level for the adapter
        custom_headers: Additional headers to send with API requests
        rate_limit_delay: Minimum delay between requests in seconds
        pox_info_cache_ttl: Cache TTL for PoX information in seconds
        enable_metrics: Whether to collect performance metrics
    """

    # API Configuration
    api_url: Optional[str] = None
    network: str = "mainnet"

    # Retry Configuration
    max_retries: int = 5
    backoff_factor: float = 0.5
    request_timeout: float = 30.0

    # Concurrency Configuration
    max_concurrent_requests: int = 5
    rate_limit_delay: float = 0.1

    # Caching Configuration
    enable_caching: bool = False
    cache_ttl: int = 300
    pox_info_cache_ttl: int = 3600

    # Logging Configuration
    log_level: str = "INFO"

    # Advanced Configuration
    custom_headers: Dict[str, str] = field(default_factory=dict)
    enable_metrics: bool = False

    # Hex Decoding Configuration
    enable_hex_decoding: bool = True
    hex_decoder_api_url: str = (
        "https://cache.aibtc.dev/contract-calls/decode-clarity-value"
    )
    hex_decoder_timeout: float = 10.0

    def __post_init__(self) -> None:
        """Post-initialization validation and setup."""
        # Set default API URL based on network
        if self.api_url is None:
            if self.network == "testnet":
                self.api_url = "https://api.testnet.hiro.so"
            else:
                self.api_url = "https://api.mainnet.hiro.so"

        # Validate network
        if self.network not in ("mainnet", "testnet"):
            raise ValueError(
                f"Invalid network: {self.network}. Must be 'mainnet' or 'testnet'"
            )

        # Validate numeric values
        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative")

        if self.backoff_factor < 0:
            raise ValueError("backoff_factor must be non-negative")

        if self.request_timeout <= 0:
            raise ValueError("request_timeout must be positive")

        if self.max_concurrent_requests <= 0:
            raise ValueError("max_concurrent_requests must be positive")

        if self.rate_limit_delay < 0:
            raise ValueError("rate_limit_delay must be non-negative")

        # Validate log level
        valid_log_levels = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        if self.log_level.upper() not in valid_log_levels:
            raise ValueError(
                f"Invalid log_level: {self.log_level}. Must be one of {valid_log_levels}"
            )

        self.log_level = self.log_level.upper()

    @classmethod
    def from_env(cls, **overrides: Any) -> "AdapterConfig":
        """Create configuration from environment variables.

        Environment variables:
            STACKS_API_URL: API base URL
            STACKS_NETWORK: Network identifier
            STACKS_MAX_RETRIES: Maximum retry attempts
            STACKS_BACKOFF_FACTOR: Exponential backoff factor
            STACKS_REQUEST_TIMEOUT: Request timeout in seconds
            STACKS_MAX_CONCURRENT: Maximum concurrent requests
            STACKS_ENABLE_CACHING: Enable caching (true/false)
            STACKS_CACHE_TTL: Cache TTL in seconds
            STACKS_LOG_LEVEL: Logging level
            STACKS_RATE_LIMIT_DELAY: Rate limit delay in seconds
            STACKS_ENABLE_METRICS: Enable metrics collection (true/false)

        Args:
            **overrides: Explicit overrides for configuration values

        Returns:
            AdapterConfig: Configuration instance with values from environment
        """
        config_kwargs = {}

        # Map environment variables to config attributes
        env_mapping = {
            "STACKS_API_URL": "api_url",
            "STACKS_NETWORK": "network",
            "STACKS_MAX_RETRIES": ("max_retries", int),
            "STACKS_BACKOFF_FACTOR": ("backoff_factor", float),
            "STACKS_REQUEST_TIMEOUT": ("request_timeout", float),
            "STACKS_MAX_CONCURRENT": ("max_concurrent_requests", int),
            "STACKS_ENABLE_CACHING": ("enable_caching", lambda x: x.lower() == "true"),
            "STACKS_CACHE_TTL": ("cache_ttl", int),
            "STACKS_LOG_LEVEL": "log_level",
            "STACKS_RATE_LIMIT_DELAY": ("rate_limit_delay", float),
            "STACKS_POX_CACHE_TTL": ("pox_info_cache_ttl", int),
            "STACKS_ENABLE_METRICS": ("enable_metrics", lambda x: x.lower() == "true"),
            "STACKS_ENABLE_HEX_DECODING": (
                "enable_hex_decoding",
                lambda x: x.lower() == "true",
            ),
            "STACKS_HEX_DECODER_API_URL": "hex_decoder_api_url",
            "STACKS_HEX_DECODER_TIMEOUT": ("hex_decoder_timeout", float),
        }

        for env_var, config_key in env_mapping.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                if isinstance(config_key, tuple):
                    key, converter = config_key
                    try:
                        config_kwargs[key] = converter(env_value)
                    except (ValueError, TypeError) as e:
                        raise ValueError(
                            f"Invalid value for {env_var}: {env_value}"
                        ) from e
                else:
                    config_kwargs[config_key] = env_value

        # Apply overrides
        config_kwargs.update(overrides)

        return cls(**config_kwargs)

    def get_logger(self, name: str) -> logging.Logger:
        """Get a configured logger instance.

        Args:
            name: Logger name

        Returns:
            logging.Logger: Configured logger
        """
        logger = logging.getLogger(name)

        # Only configure if not already configured
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(getattr(logging, self.log_level))

        return logger

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary.

        Returns:
            Dict[str, Any]: Configuration as dictionary
        """
        return {
            "api_url": self.api_url,
            "network": self.network,
            "max_retries": self.max_retries,
            "backoff_factor": self.backoff_factor,
            "request_timeout": self.request_timeout,
            "max_concurrent_requests": self.max_concurrent_requests,
            "rate_limit_delay": self.rate_limit_delay,
            "enable_caching": self.enable_caching,
            "cache_ttl": self.cache_ttl,
            "pox_info_cache_ttl": self.pox_info_cache_ttl,
            "log_level": self.log_level,
            "custom_headers": self.custom_headers.copy(),
            "enable_metrics": self.enable_metrics,
            "enable_hex_decoding": self.enable_hex_decoding,
            "hex_decoder_api_url": self.hex_decoder_api_url,
            "hex_decoder_timeout": self.hex_decoder_timeout,
        }

    def __str__(self) -> str:
        """String representation of configuration."""
        return f"AdapterConfig(network={self.network}, api_url={self.api_url})"

    def __repr__(self) -> str:
        """Detailed string representation of configuration."""
        return (
            f"AdapterConfig("
            f"network={self.network}, "
            f"api_url={self.api_url}, "
            f"max_retries={self.max_retries}, "
            f"request_timeout={self.request_timeout}, "
            f"enable_caching={self.enable_caching}"
            f")"
        )
