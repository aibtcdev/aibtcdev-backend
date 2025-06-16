"""Centralized model factory for consistent ChatOpenAI configuration across workflows.

This module provides a single place to configure default model settings that can be
easily overridden when needed.
"""

from typing import Any, List, Optional

from langchain_openai import ChatOpenAI

from config import config
from lib.logger import configure_logger

logger = configure_logger(__name__)


class ModelConfig:
    """Configuration class for default model settings."""

    # Default model settings - change these to update all workflows
    DEFAULT_MODEL = "gpt-4.1"
    DEFAULT_TEMPERATURE = 0.9
    DEFAULT_STREAMING = True
    DEFAULT_STREAM_USAGE = True

    @classmethod
    def get_default_model(cls) -> str:
        """Get the default model name.

        Uses ChatLLMConfig.default_model from the configuration.

        Returns:
            Default model name
        """
        return config.chat_llm.default_model or cls.DEFAULT_MODEL

    @classmethod
    def get_default_temperature(cls) -> float:
        """Get the default temperature.

        Uses ChatLLMConfig.default_temperature from the configuration.

        Returns:
            Default temperature
        """
        try:
            return config.chat_llm.default_temperature
        except (ValueError, TypeError, AttributeError):
            logger.warning("Invalid chat LLM temperature configuration, using default")
            return cls.DEFAULT_TEMPERATURE

    @classmethod
    def get_default_base_url(cls) -> str:
        """Get the default OpenAI API base URL.

        Uses ChatLLMConfig.api_base from the configuration.

        Returns:
            Default base URL (empty string if not set)
        """
        return config.chat_llm.api_base or ""

    @classmethod
    def get_default_api_key(cls) -> str:
        """Get the default OpenAI API key.

        Uses ChatLLMConfig.api_key from the configuration.

        Returns:
            Default API key
        """
        return config.chat_llm.api_key

    @classmethod
    def get_reasoning_model(cls) -> str:
        """Get the reasoning model name.

        Uses ChatLLMConfig.reasoning_model from the configuration.

        Returns:
            Reasoning model name
        """
        return config.chat_llm.reasoning_model or "o3-mini"

    @classmethod
    def get_reasoning_temperature(cls) -> float:
        """Get the reasoning temperature.

        Uses ChatLLMConfig.reasoning_temperature from the configuration.

        Returns:
            Reasoning temperature
        """
        try:
            return config.chat_llm.reasoning_temperature
        except (ValueError, TypeError, AttributeError):
            logger.warning("Invalid reasoning temperature configuration, using default")
            return cls.DEFAULT_TEMPERATURE


def create_chat_openai(
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    streaming: Optional[bool] = None,
    stream_usage: Optional[bool] = None,
    callbacks: Optional[List[Any]] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    **kwargs,
) -> ChatOpenAI:
    """Create a ChatOpenAI instance with centralized default configuration.

    Args:
        model: Model name. If None, uses ModelConfig.get_default_model()
        temperature: Temperature. If None, uses ModelConfig.get_default_temperature()
        streaming: Whether to enable streaming. If None, uses DEFAULT_STREAMING
        stream_usage: Whether to stream usage. If None, uses DEFAULT_STREAM_USAGE
        callbacks: Optional callback handlers
        base_url: OpenAI API base URL. If None, uses ModelConfig.get_default_base_url()
        api_key: OpenAI API key. If None, uses ModelConfig.get_default_api_key()
        **kwargs: Additional arguments to pass to ChatOpenAI

    Returns:
        Configured ChatOpenAI instance
    """
    config_dict = {
        "model": model or ModelConfig.get_default_model(),
        "temperature": temperature
        if temperature is not None
        else ModelConfig.get_default_temperature(),
        "streaming": streaming
        if streaming is not None
        else ModelConfig.DEFAULT_STREAMING,
        "stream_usage": stream_usage
        if stream_usage is not None
        else ModelConfig.DEFAULT_STREAM_USAGE,
        "callbacks": callbacks or [],
        **kwargs,
    }

    # Add base_url if specified or if default is set
    default_base_url = base_url or ModelConfig.get_default_base_url()
    if default_base_url:
        config_dict["base_url"] = default_base_url

    # Add api_key if specified or if default is set
    default_api_key = api_key or ModelConfig.get_default_api_key()
    if default_api_key:
        config_dict["api_key"] = default_api_key

    logger.debug(f"Creating ChatOpenAI with config: {config_dict}")
    return ChatOpenAI(**config_dict)


def create_planning_llm(
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    **kwargs,
) -> ChatOpenAI:
    """Create a ChatOpenAI instance specifically for planning operations.

    Uses the same defaults as create_chat_openai but can be customized
    for planning-specific needs.

    Args:
        model: Model name. If None, uses default
        temperature: Temperature. If None, uses default
        **kwargs: Additional arguments

    Returns:
        Configured ChatOpenAI instance for planning
    """
    return create_chat_openai(
        model=model,
        temperature=temperature,
        **kwargs,
    )


def create_reasoning_llm(
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    **kwargs,
) -> ChatOpenAI:
    """Create a ChatOpenAI instance specifically for reasoning operations.

    By default uses the configured reasoning model for reasoning tasks.

    Args:
        model: Model name. If None, uses configured reasoning model
        temperature: Temperature. If None, uses configured reasoning temperature
        **kwargs: Additional arguments

    Returns:
        Configured ChatOpenAI instance for reasoning
    """
    reasoning_model = model or ModelConfig.get_reasoning_model()
    reasoning_temp = (
        temperature
        if temperature is not None
        else ModelConfig.get_reasoning_temperature()
    )

    return create_chat_openai(
        model=reasoning_model,
        temperature=reasoning_temp,
        **kwargs,
    )


# Legacy compatibility functions for backward compatibility
def get_default_model_name() -> str:
    """Get the default model name for backward compatibility.

    Returns:
        Default model name
    """
    return ModelConfig.get_default_model()


def get_default_temperature() -> float:
    """Get the default temperature for backward compatibility.

    Returns:
        Default temperature
    """
    return ModelConfig.get_default_temperature()


def get_default_base_url() -> str:
    """Get the default OpenAI API base URL for backward compatibility.

    Returns:
        Default base URL
    """
    return ModelConfig.get_default_base_url()
