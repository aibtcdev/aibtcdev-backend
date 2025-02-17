import pytest
from lib.logger import configure_logger
from lib.tokenizer import Trimmer
from typing import Any, Dict, List

logger = configure_logger(__name__)


@pytest.fixture
def sample_messages() -> List[Dict[str, Any]]:
    """Fixture providing sample messages for testing."""
    return [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
        {"role": "assistant", "content": "I'm doing well, thank you for asking!"},
        {"role": "user", "content": "That's great to hear!"},
    ]


def test_trimmer_initialization() -> None:
    """Test Trimmer initialization with default and custom parameters."""
    default_trimmer = Trimmer()
    assert default_trimmer.token_model == "gpt-4o"
    assert default_trimmer.maxsize == 50000
    assert default_trimmer.margin == 500

    custom_trimmer = Trimmer(token_model="gpt-3.5-turbo", maxsize=4000, margin=200)
    assert custom_trimmer.token_model == "gpt-3.5-turbo"
    assert custom_trimmer.maxsize == 4000
    assert custom_trimmer.margin == 200


def test_count_tokens(sample_messages: List[Dict[str, Any]]) -> None:
    """Test token counting functionality."""
    trimmer = Trimmer()
    token_count = trimmer.count_tokens(sample_messages)
    assert token_count > 0
    assert isinstance(token_count, int)

    # Test with empty messages
    assert trimmer.count_tokens([]) == 0

    # Test with empty content
    empty_content_messages = [{"role": "user", "content": ""}]
    assert trimmer.count_tokens(empty_content_messages) == 0


def test_trim_messages(sample_messages: List[Dict[str, Any]]) -> None:
    """Test message trimming functionality."""
    # Create a trimmer with a very small maxsize to force trimming
    trimmer = Trimmer(maxsize=50, margin=10)

    # Make a copy of messages to avoid modifying the fixture
    messages = sample_messages.copy()
    original_length = len(messages)

    trimmer.trim_messages(messages)
    assert len(messages) < original_length

    # System message (index 0) and last message should be preserved
    assert messages[0]["role"] == "system"
    assert messages[-1]["content"] == "That's great to hear!"


def test_trim_messages_short_conversation(
    sample_messages: List[Dict[str, Any]]
) -> None:
    """Test trimming with very short conversations."""
    trimmer = Trimmer()

    # Test with just system and one user message
    short_messages = sample_messages[:2]
    original_messages = short_messages.copy()

    trimmer.trim_messages(short_messages)
    assert short_messages == original_messages  # Should not modify messages


def test_trim_messages_no_system_message() -> None:
    """Test trimming messages without a system message."""
    trimmer = Trimmer(maxsize=50, margin=10)
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "How are you?"},
    ]

    trimmer.trim_messages(messages)
    assert len(messages) > 0  # Should still preserve some messages
