from typing import Any, Dict, List, Optional
from unittest.mock import Mock, patch

import pytest
from pytwitter.models import Tweet, User

from lib.logger import configure_logger
from lib.twitter import TwitterService

logger = configure_logger(__name__)


@pytest.fixture
def twitter_credentials() -> Dict[str, str]:
    """Fixture providing test Twitter credentials."""
    return {
        "consumer_key": "test_consumer_key",
        "consumer_secret": "test_consumer_secret",
        "access_token": "test_access_token",
        "access_secret": "test_access_secret",
        "client_id": "test_client_id",
        "client_secret": "test_client_secret",
    }


@pytest.fixture
def twitter_service(twitter_credentials: Dict[str, str]) -> TwitterService:
    """Fixture providing a TwitterService instance."""
    service = TwitterService(**twitter_credentials)
    return service


@pytest.fixture
def mock_tweet() -> Tweet:
    """Fixture providing a mock Tweet."""
    tweet = Mock(spec=Tweet)
    tweet.id = "123456789"
    tweet.text = "Test tweet"
    return tweet


@pytest.fixture
def mock_user() -> User:
    """Fixture providing a mock User."""
    user = Mock(spec=User)
    user.id = "987654321"
    user.username = "test_user"
    return user


def test_initialization(twitter_service: TwitterService) -> None:
    """Test TwitterService initialization."""
    assert twitter_service.consumer_key == "test_consumer_key"
    assert twitter_service.consumer_secret == "test_consumer_secret"
    assert twitter_service.access_token == "test_access_token"
    assert twitter_service.access_secret == "test_access_secret"
    assert twitter_service.client_id == "test_client_id"
    assert twitter_service.client_secret == "test_client_secret"
    assert twitter_service.client is None


def test_initialize_success(twitter_service: TwitterService) -> None:
    """Test successful Twitter client initialization."""
    with patch("pytwitter.Api") as mock_api:
        twitter_service.initialize()

        mock_api.assert_called_once_with(
            client_id=twitter_service.client_id,
            client_secret=twitter_service.client_secret,
            consumer_key=twitter_service.consumer_key,
            consumer_secret=twitter_service.consumer_secret,
            access_token=twitter_service.access_token,
            access_secret=twitter_service.access_secret,
            application_only_auth=False,
        )
        assert twitter_service.client is not None


def test_initialize_failure(twitter_service: TwitterService) -> None:
    """Test Twitter client initialization failure."""
    with patch("pytwitter.Api", side_effect=Exception("API Error")):
        with pytest.raises(Exception, match="API Error"):
            twitter_service.initialize()
        assert twitter_service.client is None


@pytest.mark.asyncio
async def test_ainitialize(twitter_service: TwitterService) -> None:
    """Test asynchronous initialization."""
    with patch.object(twitter_service, "initialize") as mock_initialize:
        await twitter_service._ainitialize()
        mock_initialize.assert_called_once()


def test_post_tweet_success(twitter_service: TwitterService, mock_tweet: Tweet) -> None:
    """Test successful tweet posting."""
    twitter_service.client = Mock()
    twitter_service.client.create_tweet.return_value = mock_tweet

    result = twitter_service.post_tweet("Test message")

    assert result == mock_tweet
    twitter_service.client.create_tweet.assert_called_once_with(
        text="Test message", reply_in_reply_to_tweet_id=None
    )


def test_post_tweet_with_reply(
    twitter_service: TwitterService, mock_tweet: Tweet
) -> None:
    """Test tweet posting with reply."""
    twitter_service.client = Mock()
    twitter_service.client.create_tweet.return_value = mock_tweet

    result = twitter_service.post_tweet(
        "Test reply", reply_in_reply_to_tweet_id="987654321"
    )

    assert result == mock_tweet
    twitter_service.client.create_tweet.assert_called_once_with(
        text="Test reply", reply_in_reply_to_tweet_id="987654321"
    )


def test_post_tweet_client_not_initialized(twitter_service: TwitterService) -> None:
    """Test tweet posting with uninitialized client."""
    result = twitter_service.post_tweet("Test message")
    assert result is None


def test_post_tweet_failure(twitter_service: TwitterService) -> None:
    """Test tweet posting failure."""
    twitter_service.client = Mock()
    twitter_service.client.create_tweet.side_effect = Exception("API Error")

    result = twitter_service.post_tweet("Test message")
    assert result is None


@pytest.mark.asyncio
async def test_get_user_by_username_success(
    twitter_service: TwitterService, mock_user: User
) -> None:
    """Test successful user retrieval by username."""
    twitter_service.client = Mock()
    twitter_service.client.get_user.return_value = mock_user

    result = await twitter_service.get_user_by_username("test_user")

    assert result == mock_user
    twitter_service.client.get_user.assert_called_once_with(username="test_user")


@pytest.mark.asyncio
async def test_get_user_by_username_failure(twitter_service: TwitterService) -> None:
    """Test user retrieval failure by username."""
    twitter_service.client = Mock()
    twitter_service.client.get_user.side_effect = Exception("API Error")

    result = await twitter_service.get_user_by_username("test_user")
    assert result is None


@pytest.mark.asyncio
async def test_get_user_by_user_id_success(
    twitter_service: TwitterService, mock_user: User
) -> None:
    """Test successful user retrieval by user ID."""
    twitter_service.client = Mock()
    twitter_service.client.get_user.return_value = mock_user

    result = await twitter_service.get_user_by_user_id("123456789")

    assert result == mock_user
    twitter_service.client.get_user.assert_called_once_with(user_id="123456789")


@pytest.mark.asyncio
async def test_get_mentions_success(
    twitter_service: TwitterService, mock_tweet: Tweet
) -> None:
    """Test successful mentions retrieval."""
    twitter_service.client = Mock()
    mock_response = Mock()
    mock_response.data = [mock_tweet]
    twitter_service.client.get_mentions.return_value = mock_response

    result = await twitter_service.get_mentions_by_user_id("123456789")

    assert result == [mock_tweet]
    twitter_service.client.get_mentions.assert_called_once()
    args, kwargs = twitter_service.client.get_mentions.call_args
    assert kwargs["user_id"] == "123456789"
    assert kwargs["max_results"] == 100
    assert "tweet_fields" in kwargs
    assert "expansions" in kwargs
    assert "user_fields" in kwargs
    assert "media_fields" in kwargs
    assert "place_fields" in kwargs
    assert "poll_fields" in kwargs


@pytest.mark.asyncio
async def test_get_mentions_failure(twitter_service: TwitterService) -> None:
    """Test mentions retrieval failure."""
    twitter_service.client = Mock()
    twitter_service.client.get_mentions.side_effect = Exception("API Error")

    result = await twitter_service.get_mentions_by_user_id("123456789")
    assert result == []


@pytest.mark.asyncio
async def test_apost_tweet(twitter_service: TwitterService) -> None:
    """Test asynchronous tweet posting."""
    with patch.object(twitter_service, "post_tweet") as mock_post_tweet:
        mock_post_tweet.return_value = Mock(spec=Tweet)
        result = await twitter_service._apost_tweet("Test message", "987654321")

        mock_post_tweet.assert_called_once_with("Test message", "987654321")
        assert isinstance(result, Mock)  # Mock of Tweet
