"""Simplified LLM wrapper utilities.

This module provides a clean interface for LLM operations without the complexity
of the mixin system. It contains all necessary model factory functions.
"""

from typing import Any, Dict, List, Optional, Union

from langchain_core.messages import BaseMessage
from langchain_core.prompts.chat import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.config import config
from app.lib.logger import configure_logger

logger = configure_logger(__name__)


def get_default_model() -> str:
    """Get the default model name from configuration."""
    return config.chat_llm.default_model or "gpt-4.1"


def get_default_temperature() -> float:
    """Get the default temperature from configuration."""
    try:
        return config.chat_llm.default_temperature
    except (ValueError, TypeError, AttributeError):
        logger.warning("Invalid chat LLM temperature configuration, using default")
        return 0.9


def get_default_base_url() -> str:
    """Get the default OpenAI API base URL from configuration."""
    return config.chat_llm.api_base or ""


def get_default_api_key() -> str:
    """Get the default OpenAI API key from configuration."""
    return config.chat_llm.api_key


def get_reasoning_model() -> str:
    """Get the reasoning model name from configuration."""
    return config.chat_llm.reasoning_model or "o3-mini"


def get_reasoning_temperature() -> float:
    """Get the reasoning temperature from configuration."""
    try:
        return config.chat_llm.reasoning_temperature
    except (ValueError, TypeError, AttributeError):
        logger.warning("Invalid reasoning temperature configuration, using default")
        return 0.9


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
        model: Model name. If None, uses get_default_model()
        temperature: Temperature. If None, uses get_default_temperature()
        streaming: Whether to enable streaming. If None, uses True
        stream_usage: Whether to stream usage. If None, uses True
        callbacks: Optional callback handlers
        base_url: OpenAI API base URL. If None, uses get_default_base_url()
        api_key: OpenAI API key. If None, uses get_default_api_key()
        **kwargs: Additional arguments to pass to ChatOpenAI

    Returns:
        Configured ChatOpenAI instance
    """
    config_dict = {
        "model": model or get_default_model(),
        "temperature": temperature
        if temperature is not None
        else get_default_temperature(),
        "streaming": streaming if streaming is not None else True,
        "stream_usage": stream_usage if stream_usage is not None else True,
        "callbacks": callbacks or [],
        "timeout": kwargs.get("timeout", 300),  # 5 minutes total timeout
        "max_retries": kwargs.get("max_retries", 3),
        **kwargs,
    }

    # Add base_url if specified or if default is set
    default_base_url = base_url or get_default_base_url()
    if default_base_url:
        config_dict["base_url"] = default_base_url

    # Add api_key if specified or if default is set
    default_api_key = api_key or get_default_api_key()
    if default_api_key:
        config_dict["api_key"] = default_api_key

    logger.debug(f"Creating ChatOpenAI with config: {config_dict}")
    return ChatOpenAI(**config_dict)


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
    return create_chat_openai(
        model=model or get_reasoning_model(),
        temperature=temperature
        if temperature is not None
        else get_reasoning_temperature(),
        **kwargs,
    )


def create_llm(
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    streaming: Optional[bool] = None,
    callbacks: Optional[List[Any]] = None,
    **kwargs,
) -> ChatOpenAI:
    """Create a ChatOpenAI instance with simplified configuration.

    Args:
        model: Model name (defaults to configured default)
        temperature: Temperature (defaults to configured default)
        streaming: Enable streaming (defaults to configured default)
        callbacks: Optional callback handlers
        **kwargs: Additional arguments to pass to ChatOpenAI

    Returns:
        Configured ChatOpenAI instance
    """
    return create_chat_openai(
        model=model,
        temperature=temperature,
        streaming=streaming,
        callbacks=callbacks,
        **kwargs,
    )


def create_reasoning_model(
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    **kwargs,
) -> ChatOpenAI:
    """Create a ChatOpenAI instance for reasoning tasks.

    Args:
        model: Model name (defaults to reasoning model)
        temperature: Temperature (defaults to reasoning temperature)
        **kwargs: Additional arguments

    Returns:
        Configured ChatOpenAI instance for reasoning
    """
    return create_reasoning_llm(
        model=model,
        temperature=temperature,
        **kwargs,
    )


async def invoke_llm(
    messages: Union[List[BaseMessage], ChatPromptTemplate],
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    callbacks: Optional[List[Any]] = None,
    **kwargs,
) -> Any:
    """Invoke an LLM with the given messages.

    Args:
        messages: Messages to send to the LLM (BaseMessage list or ChatPromptTemplate)
        model: Model name (defaults to configured default)
        temperature: Temperature (defaults to configured default)
        callbacks: Optional callback handlers
        **kwargs: Additional arguments

    Returns:
        LLM response
    """
    llm = create_llm(
        model=model,
        temperature=temperature,
        callbacks=callbacks,
        **kwargs,
    )

    # Handle ChatPromptTemplate
    if isinstance(messages, ChatPromptTemplate):
        formatted_messages = messages.format()
        return await llm.ainvoke(formatted_messages)

    # Handle list of BaseMessage
    return await llm.ainvoke(messages)


async def invoke_structured(
    messages: Union[List[BaseMessage], ChatPromptTemplate],
    output_schema: type[BaseModel],
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    callbacks: Optional[List[Any]] = None,
    **kwargs,
) -> BaseModel:
    """Invoke an LLM with structured output.

    Args:
        messages: Messages to send to the LLM
        output_schema: Pydantic model class for structured output
        model: Model name (defaults to configured default)
        temperature: Temperature (defaults to configured default)
        callbacks: Optional callback handlers
        **kwargs: Additional arguments

    Returns:
        Structured output as instance of output_schema
    """
    llm = create_llm(
        model=model,
        temperature=temperature,
        callbacks=callbacks,
        **kwargs,
    )

    structured_llm = llm.with_structured_output(output_schema)

    # Handle ChatPromptTemplate
    if isinstance(messages, ChatPromptTemplate):
        formatted_messages = messages.format()
        return await structured_llm.ainvoke(formatted_messages)

    # Handle list of BaseMessage
    return await structured_llm.ainvoke(messages)


async def invoke_reasoning(
    messages: Union[List[BaseMessage], ChatPromptTemplate],
    output_schema: Optional[type[BaseModel]] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    callbacks: Optional[List[Any]] = None,
    **kwargs,
) -> Union[Any, BaseModel]:
    """Invoke a reasoning model (o3-mini by default).

    Args:
        messages: Messages to send to the LLM
        output_schema: Optional Pydantic model class for structured output
        model: Model name (defaults to reasoning model)
        temperature: Temperature (defaults to reasoning temperature)
        callbacks: Optional callback handlers
        **kwargs: Additional arguments

    Returns:
        LLM response or structured output if output_schema provided
    """
    llm = create_reasoning_model(
        model=model,
        temperature=temperature,
        **kwargs,
    )

    # Add callbacks if provided
    if callbacks:
        llm = create_reasoning_model(
            model=model,
            temperature=temperature,
            callbacks=callbacks,
            **kwargs,
        )

    # Handle structured output
    if output_schema:
        structured_llm = llm.with_structured_output(output_schema)
        if isinstance(messages, ChatPromptTemplate):
            formatted_messages = messages.format()
            return await structured_llm.ainvoke(formatted_messages)
        return await structured_llm.ainvoke(messages)

    # Handle regular output
    if isinstance(messages, ChatPromptTemplate):
        formatted_messages = messages.format()
        return await llm.ainvoke(formatted_messages)

    return await llm.ainvoke(messages)


def get_model_config() -> Dict[str, Any]:
    """Get the current model configuration.

    Returns:
        Dictionary with current model configuration
    """
    return {
        "default_model": get_default_model(),
        "default_temperature": get_default_temperature(),
        "default_base_url": get_default_base_url(),
        "reasoning_model": get_reasoning_model(),
        "reasoning_temperature": get_reasoning_temperature(),
    }
