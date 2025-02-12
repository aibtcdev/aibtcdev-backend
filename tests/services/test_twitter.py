import pytest
from services.twitter import (
    TweetAnalyzer,
    TweetData,
    TweetRepository,
    TwitterConfig,
    TwitterMentionHandler,
    create_twitter_handler,
)
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_backend():
    with patch("services.twitter.backend") as mock:
        mock.list_x_tweets = AsyncMock()
        mock.create_x_tweet = AsyncMock()
        mock.update_x_tweet = AsyncMock()
        mock.list_x_users = AsyncMock()
        mock.create_x_user = AsyncMock()
        mock.create_queue_message = AsyncMock()
        yield mock


@pytest.fixture
def mock_twitter_service():
    with patch("services.twitter.TwitterService") as mock:
        instance = mock.return_value
        instance._ainitialize = AsyncMock()
        instance.get_mentions_by_user_id = AsyncMock()
        instance._apost_tweet = AsyncMock()
        yield instance


@pytest.fixture
def mock_analyze_tweet():
    with patch("services.twitter.analyze_tweet") as mock:
        mock.return_value = {
            "is_worthy": True,
            "tweet_type": "test_type",
            "confidence_score": 0.9,
            "reason": "test reason",
            "tool_request": {"type": "test_tool"},
        }
        yield mock


@pytest.fixture
def config():
    return TwitterConfig(
        consumer_key="test_key",
        consumer_secret="test_secret",
        client_id="test_client_id",
        client_secret="test_client_secret",
        access_token="test_token",
        access_secret="test_secret",
        user_id="test_user_id",
        whitelisted_authors=["whitelisted_author"],
        whitelist_enabled=True,
    )


@pytest.fixture
def tweet_data():
    return TweetData(
        tweet_id="test_tweet_id",
        author_id="test_author_id",
        text="test tweet text",
        conversation_id="test_conversation_id",
    )


@pytest.fixture
def tweet_repository(mock_backend):
    return TweetRepository()


@pytest.fixture
def tweet_analyzer(tweet_repository):
    return TweetAnalyzer(tweet_repository)


@pytest.fixture
def twitter_handler(config, tweet_repository, tweet_analyzer, mock_twitter_service):
    return TwitterMentionHandler(config, tweet_repository, tweet_analyzer)


class TestTweetRepository:
    @pytest.mark.asyncio
    async def test_store_tweet_new_author(
        self, tweet_repository, tweet_data, mock_backend
    ):
        # Setup
        mock_backend.list_x_users.return_value = []
        mock_backend.create_x_user.return_value = MagicMock(id="test_author_db_id")

        # Execute
        await tweet_repository.store_tweet(tweet_data)

        # Assert
        mock_backend.list_x_users.assert_called_once()
        mock_backend.create_x_user.assert_called_once()
        mock_backend.create_x_tweet.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_tweet_existing_author(
        self, tweet_repository, tweet_data, mock_backend
    ):
        # Setup
        mock_backend.list_x_users.return_value = [MagicMock(id="test_author_db_id")]

        # Execute
        await tweet_repository.store_tweet(tweet_data)

        # Assert
        mock_backend.list_x_users.assert_called_once()
        mock_backend.create_x_user.assert_not_called()
        mock_backend.create_x_tweet.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_tweet_analysis(self, tweet_repository, mock_backend):
        # Setup
        mock_backend.list_x_tweets.return_value = [MagicMock(id="test_tweet_db_id")]

        # Execute
        await tweet_repository.update_tweet_analysis(
            tweet_id="test_tweet_id",
            is_worthy=True,
            tweet_type="test_type",
            confidence_score=0.9,
            reason="test reason",
        )

        # Assert
        mock_backend.list_x_tweets.assert_called_once()
        mock_backend.update_x_tweet.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_conversation_history(self, tweet_repository, mock_backend):
        # Setup
        mock_backend.list_x_tweets.return_value = [
            MagicMock(author_id="user1", message="message1"),
            MagicMock(author_id="test_user_id", message="message2"),
        ]

        # Execute
        history = await tweet_repository.get_conversation_history(
            "test_conversation_id", "test_user_id"
        )

        # Assert
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"


class TestTweetAnalyzer:
    @pytest.mark.asyncio
    async def test_analyze_tweet_content(
        self, tweet_analyzer, tweet_data, mock_analyze_tweet
    ):
        # Setup
        history = [{"role": "user", "content": "previous message"}]

        # Execute
        result = await tweet_analyzer.analyze_tweet_content(tweet_data, history)

        # Assert
        assert result["is_worthy"] is True
        assert result["tweet_type"] == "test_type"
        assert result["confidence_score"] == 0.9
        mock_analyze_tweet.assert_called_once()


class TestTwitterMentionHandler:
    @pytest.mark.asyncio
    async def test_process_mentions_no_mentions(self, twitter_handler):
        # Setup
        twitter_handler.twitter_service.get_mentions_by_user_id.return_value = []

        # Execute
        await twitter_handler.process_mentions()

        # Assert
        twitter_handler.twitter_service._ainitialize.assert_called_once()
        twitter_handler.twitter_service.get_mentions_by_user_id.assert_called_once_with(
            "test_user_id"
        )

    @pytest.mark.asyncio
    async def test_handle_mention_existing_tweet(self, twitter_handler, mock_backend):
        # Setup
        mention = MagicMock(
            id="test_tweet_id",
            author_id="test_author_id",
            text="test text",
            conversation_id="test_conv_id",
        )
        mock_backend.list_x_tweets.return_value = [MagicMock()]

        # Execute
        await twitter_handler._handle_mention(mention)

        # Assert
        mock_backend.list_x_tweets.assert_called_once()
        mock_backend.create_x_tweet.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_mention_whitelisted_author(
        self, twitter_handler, mock_backend, mock_analyze_tweet
    ):
        # Setup
        mention = MagicMock(
            id="test_tweet_id",
            author_id="whitelisted_author",
            text="test text",
            conversation_id="test_conv_id",
        )
        mock_backend.list_x_tweets.return_value = []
        mock_backend.list_x_users.return_value = [MagicMock(id="test_author_db_id")]

        # Execute
        await twitter_handler._handle_mention(mention)

        # Assert
        mock_backend.create_x_tweet.assert_called_once()
        mock_analyze_tweet.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_mention_non_whitelisted_author(
        self, twitter_handler, mock_backend, mock_analyze_tweet
    ):
        # Setup
        mention = MagicMock(
            id="test_tweet_id",
            author_id="non_whitelisted_author",
            text="test text",
            conversation_id="test_conv_id",
        )
        mock_backend.list_x_tweets.return_value = []

        # Execute
        await twitter_handler._handle_mention(mention)

        # Assert
        mock_backend.create_x_tweet.assert_called_once()
        mock_analyze_tweet.assert_not_called()


def test_create_twitter_handler():
    with patch("services.twitter.load_dotenv"), patch.dict(
        "os.environ",
        {
            "AIBTC_TWITTER_CONSUMER_KEY": "test_key",
            "AIBTC_TWITTER_CONSUMER_SECRET": "test_secret",
            "AIBTC_TWITTER_CLIENT_ID": "test_client_id",
            "AIBTC_TWITTER_CLIENT_SECRET": "test_client_secret",
            "AIBTC_TWITTER_ACCESS_TOKEN": "test_token",
            "AIBTC_TWITTER_ACCESS_SECRET": "test_secret",
            "AIBTC_TWITTER_AUTOMATED_USER_ID": "test_user_id",
            "AIBTC_TWITTER_WHITELISTED": "whitelisted_author",
        },
    ):
        handler = create_twitter_handler()
        assert isinstance(handler, TwitterMentionHandler)
        assert handler.config.consumer_key == "test_key"
        assert handler.config.user_id == "test_user_id"
        assert handler.config.whitelisted_authors == ["whitelisted_author"]
