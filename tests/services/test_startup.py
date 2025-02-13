import asyncio
import os
import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from services.startup import ServiceConfig, StartupService
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_scheduler():
    scheduler = MagicMock(spec=AsyncIOScheduler)
    scheduler.running = True
    return scheduler


@pytest.fixture
def service(mock_scheduler):
    return StartupService(scheduler=mock_scheduler)


@pytest.fixture
def mock_manager():
    with patch("services.startup.manager") as mock:
        mock.start_cleanup_task = AsyncMock()
        yield mock


@pytest.fixture
def mock_bot():
    with patch("services.startup.start_application") as mock:
        mock.return_value = AsyncMock()
        yield mock


@pytest.fixture
def mock_jobs():
    with patch.multiple(
        "services.startup",
        execute_twitter_job=MagicMock(),
        sync_schedules=MagicMock(),
        execute_runner_job=MagicMock(),
    ) as mocks:
        yield mocks


class TestServiceConfig:
    def test_default_config(self):
        """Test default configuration values."""
        config = ServiceConfig()
        assert isinstance(config.twitter_enabled, bool)
        assert isinstance(config.twitter_interval, int)
        assert isinstance(config.schedule_sync_enabled, bool)
        assert isinstance(config.schedule_sync_interval, int)
        assert isinstance(config.dao_runner_enabled, bool)
        assert isinstance(config.dao_runner_interval, int)
        assert isinstance(config.tweet_runner_enabled, bool)
        assert isinstance(config.tweet_runner_interval, int)

    def test_config_from_env(self, monkeypatch):
        """Test configuration values from environment variables."""
        env_vars = {
            "AIBTC_TWITTER_ENABLED": "true",
            "AIBTC_TWITTER_INTERVAL_SECONDS": "300",
            "AIBTC_SCHEDULE_SYNC_ENABLED": "true",
            "AIBTC_SCHEDULE_SYNC_INTERVAL_SECONDS": "120",
            "AIBTC_DAO_RUNNER_ENABLED": "true",
            "AIBTC_DAO_RUNNER_INTERVAL_SECONDS": "60",
            "AIBTC_TWEET_RUNNER_ENABLED": "true",
            "AIBTC_TWEET_RUNNER_INTERVAL_SECONDS": "45",
        }

        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)

        config = ServiceConfig()
        assert config.twitter_enabled is True
        assert config.twitter_interval == 300
        assert config.schedule_sync_enabled is True
        assert config.schedule_sync_interval == 120
        assert config.dao_runner_enabled is True
        assert config.dao_runner_interval == 60
        assert config.tweet_runner_enabled is True
        assert config.tweet_runner_interval == 45


class TestStartupService:
    @pytest.mark.asyncio
    async def test_start_websocket_cleanup_success(self, service, mock_manager):
        """Test successful websocket cleanup start."""
        await service.start_websocket_cleanup()
        mock_manager.start_cleanup_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_websocket_cleanup_failure(self, service, mock_manager):
        """Test websocket cleanup start failure."""
        mock_manager.start_cleanup_task.side_effect = Exception("Cleanup failed")

        with pytest.raises(Exception) as exc_info:
            await service.start_websocket_cleanup()
        assert str(exc_info.value) == "Cleanup failed"

    @pytest.mark.asyncio
    async def test_start_bot_disabled(self, service, mock_bot):
        """Test bot startup when disabled."""
        with patch("services.startup.BOT_ENABLED", False):
            result = await service.start_bot()
            assert result is None
            mock_bot.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_bot_enabled(self, service, mock_bot):
        """Test bot startup when enabled."""
        with patch("services.startup.BOT_ENABLED", True):
            await service.start_bot()
            mock_bot.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_bot_failure(self, service, mock_bot):
        """Test bot startup failure."""
        with patch("services.startup.BOT_ENABLED", True):
            mock_bot.side_effect = Exception("Bot startup failed")

            with pytest.raises(Exception) as exc_info:
                await service.start_bot()
            assert str(exc_info.value) == "Bot startup failed"

    def test_init_scheduler_all_enabled(self, service, mock_jobs):
        """Test scheduler initialization with all services enabled."""
        service.config.twitter_enabled = True
        service.config.schedule_sync_enabled = True
        service.config.dao_runner_enabled = True
        service.config.tweet_runner_enabled = True

        service.init_scheduler()

        assert service.scheduler.add_job.call_count == 4
        service.scheduler.start.assert_called_once()

    def test_init_scheduler_all_disabled(self, service, mock_jobs):
        """Test scheduler initialization with all services disabled."""
        service.config.twitter_enabled = False
        service.config.schedule_sync_enabled = False
        service.config.dao_runner_enabled = False
        service.config.tweet_runner_enabled = False

        service.init_scheduler()

        service.scheduler.add_job.assert_not_called()
        service.scheduler.start.assert_not_called()

    @pytest.mark.asyncio
    async def test_init_background_tasks(self, service, mock_manager, mock_bot):
        """Test background tasks initialization."""
        with patch("services.startup.BOT_ENABLED", True):
            cleanup_task = await service.init_background_tasks()

            assert isinstance(cleanup_task, asyncio.Task)
            assert service.cleanup_task is cleanup_task
            mock_manager.start_cleanup_task.assert_called_once()
            mock_bot.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown(self, service):
        """Test service shutdown."""
        # Create a mock cleanup task
        mock_task = AsyncMock()
        service.cleanup_task = mock_task

        await service.shutdown()

        service.scheduler.shutdown.assert_called_once()
        mock_task.cancel.assert_called_once()


@pytest.mark.asyncio
async def test_global_init_background_tasks():
    """Test global init_background_tasks function."""
    with patch("services.startup.startup_service") as mock_service:
        mock_service.init_background_tasks = AsyncMock()
        await asyncio.create_task(init_background_tasks())
        mock_service.init_background_tasks.assert_called_once()


@pytest.mark.asyncio
async def test_global_shutdown():
    """Test global shutdown function."""
    with patch("services.startup.startup_service") as mock_service:
        mock_service.shutdown = AsyncMock()
        await shutdown()
        mock_service.shutdown.assert_called_once()
