import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import config
from services.startup import StartupService


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
def mock_job_manager():
    with patch("services.startup.JobManager") as mock:
        mock.schedule_jobs.return_value = True
        yield mock


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
        with patch.object(config.telegram, "enabled", False):
            result = await service.start_bot()
            assert result is None
            mock_bot.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_bot_enabled(self, service, mock_bot):
        """Test bot startup when enabled."""
        with patch.object(config.telegram, "enabled", True):
            await service.start_bot()
            mock_bot.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_bot_failure(self, service, mock_bot):
        """Test bot startup failure."""
        with patch.object(config.telegram, "enabled", True):
            mock_bot.side_effect = Exception("Bot startup failed")

            with pytest.raises(Exception) as exc_info:
                await service.start_bot()
            assert str(exc_info.value) == "Bot startup failed"

    def test_init_scheduler_jobs_enabled(self, service, mock_job_manager):
        """Test scheduler initialization with jobs enabled."""
        mock_job_manager.schedule_jobs.return_value = True

        service.init_scheduler()

        mock_job_manager.schedule_jobs.assert_called_once_with(service.scheduler)
        service.scheduler.start.assert_called_once()

    def test_init_scheduler_all_disabled(self, service, mock_job_manager):
        """Test scheduler initialization with all jobs disabled."""
        mock_job_manager.schedule_jobs.return_value = False

        service.init_scheduler()

        mock_job_manager.schedule_jobs.assert_called_once_with(service.scheduler)
        service.scheduler.start.assert_not_called()

    @pytest.mark.asyncio
    async def test_init_background_tasks(
        self, service, mock_manager, mock_bot, mock_job_manager
    ):
        """Test background tasks initialization."""
        with patch.object(config.telegram, "enabled", True):
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
        from services.startup import init_background_tasks

        await asyncio.create_task(init_background_tasks())
        mock_service.init_background_tasks.assert_called_once()


@pytest.mark.asyncio
async def test_global_shutdown():
    """Test global shutdown function."""
    with patch("services.startup.startup_service") as mock_service:
        mock_service.shutdown = AsyncMock()
        from services.startup import shutdown

        await shutdown()
        mock_service.shutdown.assert_called_once()
