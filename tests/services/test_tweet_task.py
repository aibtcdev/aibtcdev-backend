from dataclasses import dataclass
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from services.runner.tasks.tweet_task import TweetProcessingResult, TweetTask


@dataclass
class MockMessage:
    """Mock message for testing."""

    message: Any
    dao_id: Optional[UUID] = UUID("00000000-0000-0000-0000-000000000001")
    tweet_id: Optional[str] = "123456789"
    conversation_id: Optional[str] = None
    id: str = "test-message-id"


@pytest.fixture
def tweet_task():
    """Create a TweetTask instance for testing."""
    task = TweetTask()
    task.twitter_service = MagicMock()
    task.twitter_service._apost_tweet = AsyncMock()
    return task


class TestTweetTask:
    """Tests for the TweetTask class."""

    @pytest.mark.asyncio
    async def test_validate_message_with_valid_format(self, tweet_task):
        """Test validating a message with the correct format."""
        # Arrange
        message = MockMessage(message={"message": "This is a test tweet"})
        original_message = message.message.copy()

        # Act
        result = await tweet_task._validate_message(message)

        # Assert
        assert result is None
        # Message structure should remain unchanged
        assert message.message == original_message

    @pytest.mark.asyncio
    async def test_validate_message_with_empty_message(self, tweet_task):
        """Test validating a message with an empty message field."""
        # Arrange
        message = MockMessage(message=None)

        # Act
        result = await tweet_task._validate_message(message)

        # Assert
        assert result is not None
        assert result.success is False
        assert "empty" in result.message.lower()

    @pytest.mark.asyncio
    async def test_validate_message_with_empty_content(self, tweet_task):
        """Test validating a message with empty content."""
        # Arrange
        message = MockMessage(message={"message": ""})

        # Act
        result = await tweet_task._validate_message(message)

        # Assert
        assert result is not None
        assert result.success is False
        assert "empty" in result.message.lower()

    @pytest.mark.asyncio
    async def test_validate_message_with_invalid_format(self, tweet_task):
        """Test validating a message with an invalid format."""
        # Arrange
        message = MockMessage(message={"wrong_field": "This is a test tweet"})

        # Act
        result = await tweet_task._validate_message(message)

        # Assert
        assert result is not None
        assert result.success is False
        assert "unsupported" in result.message.lower()

    @pytest.mark.asyncio
    async def test_validate_message_with_no_dao_id(self, tweet_task):
        """Test validating a message with no DAO ID."""
        # Arrange
        message = MockMessage(message={"message": "This is a test tweet"}, dao_id=None)

        # Act
        result = await tweet_task._validate_message(message)

        # Assert
        assert result is not None
        assert result.success is False
        assert "dao_id" in result.message.lower()

    @pytest.mark.asyncio
    async def test_validate_message_with_too_long_tweet(self, tweet_task):
        """Test validating a message with a tweet that exceeds the character limit."""
        # Arrange
        long_tweet = "x" * 281  # Twitter's character limit is 280
        message = MockMessage(message={"message": long_tweet})

        # Act
        result = await tweet_task._validate_message(message)

        # Assert
        assert result is not None
        assert result.success is False
        assert "character limit" in result.message.lower()

    @pytest.mark.asyncio
    async def test_process_tweet_message_success(self, tweet_task):
        """Test processing a tweet message successfully."""
        # Arrange
        message = MockMessage(message={"message": "This is a test tweet"})
        tweet_task.twitter_service._apost_tweet.return_value = {
            "id": "987654321",
            "text": "This is a test tweet",
        }

        # Act
        result = await tweet_task._process_tweet_message(message)

        # Assert
        assert result.success is True
        assert result.tweet_id is not None
        tweet_task.twitter_service._apost_tweet.assert_called_once_with(
            text="This is a test tweet",
            reply_in_reply_to_tweet_id="123456789",
            conversation_id=None,
        )

    @pytest.mark.asyncio
    async def test_process_tweet_message_failure(self, tweet_task):
        """Test processing a tweet message with a failure from the Twitter service."""
        # Arrange
        message = MockMessage(message={"message": "This is a test tweet"})
        tweet_task.twitter_service._apost_tweet.return_value = None

        # Act
        result = await tweet_task._process_tweet_message(message)

        # Assert
        assert result.success is False
        assert "failed to send tweet" in result.message.lower()
        tweet_task.twitter_service._apost_tweet.assert_called_once()
