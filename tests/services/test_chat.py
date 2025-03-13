import asyncio
import datetime
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID

import pytest

pytest_plugins = ("pytest_asyncio",)

from backend.models import Agent, JobBase, Profile, StepCreate
from services.chat import (
    ChatProcessor,
    MessageHandler,
    ToolExecutionHandler,
    process_chat_message,
)


@pytest.fixture
def mock_profile():
    return Profile(
        id=UUID("12345678-1234-5678-1234-567812345678"),
        name="Test User",
        email="test@example.com",
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now(),
        is_active=True,
        is_verified=True,
        is_admin=False,
        is_superuser=False,
    )


@pytest.fixture
def mock_queue():
    return asyncio.Queue()


@pytest.fixture
def mock_agent():
    return Agent(
        id=UUID("11111111-2222-3333-4444-555555555555"),
        name="Test Agent",
        backstory="Test backstory",
        role="Test role",
        goal="Test goal",
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now(),
    )


@pytest.fixture
def mock_backend(mock_agent):
    backend = Mock()
    backend.get_agent = Mock(return_value=mock_agent)
    backend.create_step = Mock()
    backend.update_job = Mock()
    return backend


class AsyncIterator:
    def __init__(self, items):
        self.items = items

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.items:
            raise StopAsyncIteration
        return self.items.pop(0)


@pytest.fixture
def mock_tools():
    return {
        "search": Mock(),
        "calculator": Mock(),
    }


@pytest.mark.asyncio
async def test_process_chat_message_basic_flow(
    mock_profile, mock_queue, mock_backend, mock_tools
):
    with patch("services.chat.backend", mock_backend):
        with patch("services.chat.execute_langgraph_stream") as mock_execute:
            # Setup mock response from langgraph
            mock_execute.return_value = AsyncIterator(
                [
                    {"type": "token", "content": "Hello"},
                    {"type": "result", "content": "Hello, how can I help?"},
                    {"type": "end", "content": ""},
                ]
            )

            with patch("services.chat.initialize_tools", return_value=mock_tools):
                job_id = UUID("12345678-1234-5678-1234-567812345678")
                thread_id = UUID("87654321-4321-8765-4321-876543210987")
                agent_id = UUID("11111111-2222-3333-4444-555555555555")

                await process_chat_message(
                    job_id=job_id,
                    thread_id=thread_id,
                    profile=mock_profile,
                    agent_id=agent_id,
                    input_str="Hi",
                    history=[],
                    output_queue=mock_queue,
                )

                # Verify backend calls
                mock_backend.create_step.assert_called()
                mock_backend.update_job.assert_called_once()

                # Verify queue output
                messages = []
                while not mock_queue.empty():
                    msg = await mock_queue.get()
                    if msg is not None:
                        messages.append(msg)

                assert len(messages) > 0
                assert any(msg["type"] == "token" for msg in messages)


@pytest.mark.asyncio
async def test_process_chat_message_with_tool_execution(
    mock_profile, mock_queue, mock_backend, mock_tools
):
    with patch("services.chat.backend", mock_backend):
        with patch("services.chat.execute_langgraph_stream") as mock_execute:
            # Setup mock response with tool execution
            mock_execute.return_value = AsyncIterator(
                [
                    {"type": "token", "content": "Let me check that for you"},
                    {
                        "type": "tool",
                        "status": "start",
                        "tool": "search",
                        "input": "query",
                        "output": None,
                    },
                    {
                        "type": "tool",
                        "status": "end",
                        "tool": "search",
                        "input": "query",
                        "output": "result",
                    },
                    {"type": "result", "content": "Here's what I found"},
                    {"type": "end", "content": ""},
                ]
            )

            with patch("services.chat.initialize_tools", return_value=mock_tools):
                job_id = UUID("12345678-1234-5678-1234-567812345678")
                thread_id = UUID("87654321-4321-8765-4321-876543210987")

                await process_chat_message(
                    job_id=job_id,
                    thread_id=thread_id,
                    profile=mock_profile,
                    agent_id=None,
                    input_str="Search for something",
                    history=[],
                    output_queue=mock_queue,
                )

                # Verify tool execution was recorded
                tool_step_calls = [
                    call.kwargs["new_step"].tool
                    for call in mock_backend.create_step.call_args_list
                    if call.kwargs["new_step"].tool is not None
                ]
                assert "search" in tool_step_calls


@pytest.mark.asyncio
async def test_process_chat_message_error_handling(mock_profile, mock_queue):
    with patch("services.chat.execute_langgraph_stream") as mock_execute:
        mock_execute.side_effect = Exception("Test error")

        job_id = UUID("12345678-1234-5678-1234-567812345678")
        thread_id = UUID("87654321-4321-8765-4321-876543210987")

        with pytest.raises(Exception):
            await process_chat_message(
                job_id=job_id,
                thread_id=thread_id,
                profile=mock_profile,
                agent_id=None,
                input_str="This should fail",
                history=[],
                output_queue=mock_queue,
            )


@pytest.mark.asyncio
async def test_message_handler_process_tokens():
    handler = MessageHandler()
    message = {
        "type": "token",
        "content": "test content",
        "thread_id": "test-thread",
        "agent_id": "test-agent",
    }

    processed = handler.process_token_message(message)
    assert processed["type"] == "token"
    assert processed["content"] == "test content"
    assert "created_at" in processed


@pytest.mark.asyncio
async def test_tool_execution_handler():
    handler = ToolExecutionHandler()
    tool_message = {
        "type": "tool",
        "status": "start",
        "tool": "test_tool",
        "input": "test_input",
        "output": "test_output",
        "thread_id": "test-thread",
        "agent_id": "test-agent",
    }

    processed = handler.process_tool_message(tool_message)
    assert processed["type"] == "tool"
    assert processed["tool"] == "test_tool"
    assert "created_at" in processed
