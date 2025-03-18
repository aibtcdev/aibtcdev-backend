import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import WebSocket

from lib.logger import configure_logger
from lib.websocket_manager import ConnectionManager

logger = configure_logger(__name__)


@pytest.fixture
def manager() -> ConnectionManager:
    """Fixture providing a ConnectionManager instance with a short TTL for testing."""
    return ConnectionManager(ttl_seconds=1)


@pytest.fixture
def mock_websocket() -> AsyncMock:
    """Fixture providing a mock WebSocket."""
    websocket = AsyncMock(spec=WebSocket)
    return websocket


@pytest.mark.asyncio
async def test_connect_job(
    manager: ConnectionManager, mock_websocket: AsyncMock
) -> None:
    """Test job connection."""
    job_id = "test-job-1"
    await manager.connect_job(mock_websocket, job_id)

    assert job_id in manager.job_connections
    assert len(manager.job_connections[job_id]) == 1
    ws, ts = next(iter(manager.job_connections[job_id]))
    assert ws == mock_websocket
    assert isinstance(ts, float)
    mock_websocket.accept.assert_called_once()


@pytest.mark.asyncio
async def test_connect_thread(
    manager: ConnectionManager, mock_websocket: AsyncMock
) -> None:
    """Test thread connection."""
    thread_id = "test-thread-1"
    await manager.connect_thread(mock_websocket, thread_id)

    assert thread_id in manager.thread_connections
    assert len(manager.thread_connections[thread_id]) == 1
    ws, ts = next(iter(manager.thread_connections[thread_id]))
    assert ws == mock_websocket
    assert isinstance(ts, float)
    mock_websocket.accept.assert_called_once()


@pytest.mark.asyncio
async def test_connect_session(
    manager: ConnectionManager, mock_websocket: AsyncMock
) -> None:
    """Test session connection."""
    session_id = "test-session-1"
    await manager.connect_session(mock_websocket, session_id)

    assert session_id in manager.session_connections
    assert len(manager.session_connections[session_id]) == 1
    ws, ts = next(iter(manager.session_connections[session_id]))
    assert ws == mock_websocket
    assert isinstance(ts, float)
    mock_websocket.accept.assert_called_once()


@pytest.mark.asyncio
async def test_disconnect_job(
    manager: ConnectionManager, mock_websocket: AsyncMock
) -> None:
    """Test job disconnection."""
    job_id = "test-job-1"
    await manager.connect_job(mock_websocket, job_id)
    await manager.disconnect_job(mock_websocket, job_id)

    assert job_id not in manager.job_connections


@pytest.mark.asyncio
async def test_disconnect_thread(
    manager: ConnectionManager, mock_websocket: AsyncMock
) -> None:
    """Test thread disconnection."""
    thread_id = "test-thread-1"
    await manager.connect_thread(mock_websocket, thread_id)
    await manager.disconnect_thread(mock_websocket, thread_id)

    assert thread_id not in manager.thread_connections


@pytest.mark.asyncio
async def test_disconnect_session(
    manager: ConnectionManager, mock_websocket: AsyncMock
) -> None:
    """Test session disconnection."""
    session_id = "test-session-1"
    await manager.connect_session(mock_websocket, session_id)
    await manager.disconnect_session(mock_websocket, session_id)

    assert session_id not in manager.session_connections


@pytest.mark.asyncio
async def test_send_job_message(
    manager: ConnectionManager, mock_websocket: AsyncMock
) -> None:
    """Test sending message to job connection."""
    job_id = "test-job-1"
    message = {"type": "test", "data": "test-data"}

    await manager.connect_job(mock_websocket, job_id)
    await manager.send_job_message(message, job_id)

    mock_websocket.send_json.assert_called_once_with(message)


@pytest.mark.asyncio
async def test_send_thread_message(
    manager: ConnectionManager, mock_websocket: AsyncMock
) -> None:
    """Test sending message to thread connection."""
    thread_id = "test-thread-1"
    message = {"type": "test", "data": "test-data"}

    await manager.connect_thread(mock_websocket, thread_id)
    await manager.send_thread_message(message, thread_id)

    mock_websocket.send_json.assert_called_once_with(message)


@pytest.mark.asyncio
async def test_send_session_message(
    manager: ConnectionManager, mock_websocket: AsyncMock
) -> None:
    """Test sending message to session connection."""
    session_id = "test-session-1"
    message = {"type": "test", "data": "test-data"}

    await manager.connect_session(mock_websocket, session_id)
    await manager.send_session_message(message, session_id)

    mock_websocket.send_json.assert_called_once_with(message)


@pytest.mark.asyncio
async def test_send_message_to_dead_connection(
    manager: ConnectionManager, mock_websocket: AsyncMock
) -> None:
    """Test sending message to dead connection."""
    job_id = "test-job-1"
    message = {"type": "test", "data": "test-data"}

    mock_websocket.send_json.side_effect = Exception("Connection closed")

    await manager.connect_job(mock_websocket, job_id)
    await manager.send_job_message(message, job_id)

    assert job_id not in manager.job_connections


@pytest.mark.asyncio
async def test_cleanup_expired_connections(
    manager: ConnectionManager, mock_websocket: AsyncMock
) -> None:
    """Test cleanup of expired connections."""
    job_id = "test-job-1"
    thread_id = "test-thread-1"
    session_id = "test-session-1"

    # Connect to all types
    await manager.connect_job(mock_websocket, job_id)
    await manager.connect_thread(mock_websocket, thread_id)
    await manager.connect_session(mock_websocket, session_id)

    # Wait for TTL to expire
    await asyncio.sleep(1.1)

    # Run cleanup
    await manager.cleanup_expired_connections()

    assert job_id not in manager.job_connections
    assert thread_id not in manager.thread_connections
    assert session_id not in manager.session_connections
    mock_websocket.close.assert_called()


@pytest.mark.asyncio
async def test_broadcast_errors(
    manager: ConnectionManager, mock_websocket: AsyncMock
) -> None:
    """Test broadcasting error messages."""
    job_id = "test-job-1"
    thread_id = "test-thread-1"
    session_id = "test-session-1"
    error_message = "Test error"

    # Connect to all types
    await manager.connect_job(mock_websocket, job_id)
    await manager.connect_thread(mock_websocket, thread_id)
    await manager.connect_session(mock_websocket, session_id)

    # Broadcast errors
    await manager.broadcast_job_error(error_message, job_id)
    await manager.broadcast_thread_error(error_message, thread_id)
    await manager.broadcast_session_error(error_message, session_id)

    expected_message = {"type": "error", "message": error_message}
    assert mock_websocket.send_json.call_count == 3
    mock_websocket.send_json.assert_called_with(expected_message)


@pytest.mark.asyncio
async def test_multiple_connections(manager: ConnectionManager) -> None:
    """Test managing multiple connections."""
    job_id = "test-job-1"
    mock_websocket1 = AsyncMock(spec=WebSocket)
    mock_websocket2 = AsyncMock(spec=WebSocket)

    # Connect two websockets
    await manager.connect_job(mock_websocket1, job_id)
    await manager.connect_job(mock_websocket2, job_id)

    assert len(manager.job_connections[job_id]) == 2

    # Send a message
    message = {"type": "test", "data": "test-data"}
    await manager.send_job_message(message, job_id)

    mock_websocket1.send_json.assert_called_once_with(message)
    mock_websocket2.send_json.assert_called_once_with(message)

    # Disconnect one
    await manager.disconnect_job(mock_websocket1, job_id)
    assert len(manager.job_connections[job_id]) == 1

    # Send another message
    await manager.send_job_message(message, job_id)
    mock_websocket1.send_json.assert_called_once()  # Still only called once
    assert mock_websocket2.send_json.call_count == 2  # Called twice


@pytest.mark.asyncio
async def test_cleanup_task(manager: ConnectionManager) -> None:
    """Test the cleanup task."""
    with patch.object(manager, "cleanup_expired_connections") as mock_cleanup:
        # Start the cleanup task
        cleanup_task = asyncio.create_task(manager.start_cleanup_task())

        # Wait a bit to allow the task to run
        await asyncio.sleep(0.1)

        # Cancel the task
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass

        # Verify cleanup was called
        mock_cleanup.assert_called()
