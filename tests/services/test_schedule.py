import pytest
import uuid
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from backend.models import Task
from services.schedule import SchedulerService, get_scheduler_service
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_scheduler():
    scheduler = MagicMock(spec=AsyncIOScheduler)
    scheduler.get_jobs.return_value = []
    return scheduler


@pytest.fixture
def scheduler_service(mock_scheduler):
    return SchedulerService(mock_scheduler)


@pytest.fixture
def mock_task():
    return Task(
        id=uuid.uuid4(),
        name="Test Task",
        prompt="Test Prompt",
        agent_id=uuid.uuid4(),
        profile_id=uuid.uuid4(),
        cron="0 * * * *",
        is_scheduled=True,
    )


@pytest.fixture
def mock_backend():
    with patch("services.schedule.backend") as mock:
        mock.get_task = AsyncMock()
        mock.get_agent = AsyncMock()
        mock.get_profile = AsyncMock()
        mock.create_job = AsyncMock()
        mock.create_step = AsyncMock()
        mock.update_job = AsyncMock()
        mock.list_tasks = AsyncMock()
        yield mock


@pytest.mark.asyncio
async def test_execute_job_success(scheduler_service, mock_backend, mock_task):
    # Setup
    agent_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())
    profile_id = str(uuid.uuid4())

    mock_backend.get_task.return_value = mock_task
    mock_backend.get_agent.return_value = {"id": agent_id}
    mock_backend.get_profile.return_value = {"id": profile_id}
    mock_backend.create_job.return_value = {"id": str(uuid.uuid4())}

    with patch("services.schedule.execute_langgraph_stream") as mock_stream:
        mock_stream.return_value = [
            {"type": "tool", "tool": "test_tool", "input": "test_input"},
            {"type": "result", "content": "test_result"},
        ]

        # Execute
        await scheduler_service.execute_job(agent_id, task_id, profile_id)

        # Assert
        mock_backend.get_task.assert_called_once_with(task_id=uuid.UUID(task_id))
        mock_backend.get_agent.assert_called_once_with(agent_id=uuid.UUID(agent_id))
        mock_backend.get_profile.assert_called_once_with(
            profile_id=uuid.UUID(profile_id)
        )
        mock_backend.create_job.assert_called_once()
        assert mock_backend.create_step.call_count == 2


@pytest.mark.asyncio
async def test_execute_job_task_not_found(scheduler_service, mock_backend):
    # Setup
    mock_backend.get_task.return_value = None

    # Execute
    await scheduler_service.execute_job("agent_id", "task_id", "profile_id")

    # Assert
    mock_backend.get_agent.assert_not_called()
    mock_backend.get_profile.assert_not_called()
    mock_backend.create_job.assert_not_called()


@pytest.mark.asyncio
async def test_sync_schedules_add_new_job(scheduler_service, mock_backend, mock_task):
    # Setup
    mock_backend.list_tasks.return_value = [mock_task]

    # Execute
    await scheduler_service.sync_schedules()

    # Assert
    scheduler_service.scheduler.add_job.assert_called_once()
    assert scheduler_service.scheduler.remove_job.call_count == 0


@pytest.mark.asyncio
async def test_sync_schedules_update_job(scheduler_service, mock_backend, mock_task):
    # Setup
    job_id = f"schedule_{mock_task.id}"
    mock_job = MagicMock()
    mock_job.id = job_id
    mock_job.trigger = CronTrigger.from_crontab(
        "*/5 * * * *"
    )  # Different from mock_task.cron

    scheduler_service.scheduler.get_jobs.return_value = [mock_job]
    mock_backend.list_tasks.return_value = [mock_task]

    # Execute
    await scheduler_service.sync_schedules()

    # Assert
    assert scheduler_service.scheduler.remove_job.call_count == 1
    scheduler_service.scheduler.add_job.assert_called_once()


@pytest.mark.asyncio
async def test_sync_schedules_remove_job(scheduler_service, mock_backend):
    # Setup
    job_id = "schedule_old_job"
    mock_job = MagicMock()
    mock_job.id = job_id

    scheduler_service.scheduler.get_jobs.return_value = [mock_job]
    mock_backend.list_tasks.return_value = []  # No tasks in backend

    # Execute
    await scheduler_service.sync_schedules()

    # Assert
    scheduler_service.scheduler.remove_job.assert_called_once_with(job_id)
    assert scheduler_service.scheduler.add_job.call_count == 0


def test_get_scheduler_service():
    # Setup
    scheduler = MagicMock(spec=AsyncIOScheduler)

    # Execute
    service1 = get_scheduler_service(scheduler)
    service2 = get_scheduler_service()

    # Assert
    assert service1 is service2
    assert isinstance(service1, SchedulerService)


def test_get_scheduler_service_no_scheduler():
    # Setup & Execute & Assert
    with pytest.raises(ValueError):
        get_scheduler_service()


@pytest.mark.asyncio
async def test_handle_stream_event(scheduler_service, mock_backend):
    # Setup
    job = {"id": str(uuid.uuid4())}
    agent_id = str(uuid.uuid4())
    profile_id = str(uuid.uuid4())

    # Test tool event
    tool_event = {
        "type": "tool",
        "tool": "test_tool",
        "input": "test_input",
        "output": "test_output",
    }
    await scheduler_service._handle_stream_event(tool_event, job, agent_id, profile_id)
    mock_backend.create_step.assert_called_once()

    # Test result event
    result_event = {"type": "result", "content": "test_result"}
    await scheduler_service._handle_stream_event(
        result_event, job, agent_id, profile_id
    )
    assert mock_backend.create_step.call_count == 2
    mock_backend.update_job.assert_called_once()
