import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from services.workflows import (
    ExecutionError,
    LangGraphService,
    MessageContent,
    MessageProcessor,
    StreamingCallbackHandler,
    StreamingError,
    execute_langgraph_stream,
)


@pytest.fixture
def message_processor():
    return MessageProcessor()


@pytest.fixture
def sample_history():
    return [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
        {"role": "user", "content": "How are you?"},
        {
            "role": "assistant",
            "content": "I'm doing well",
            "tool_calls": [{"type": "function", "function": {"name": "test_tool"}}],
        },
    ]


class TestMessageContent:
    def test_from_dict(self):
        data = {
            "role": "user",
            "content": "test message",
            "tool_calls": [{"type": "function"}],
        }
        content = MessageContent.from_dict(data)
        assert content.role == "user"
        assert content.content == "test message"
        assert content.tool_calls == [{"type": "function"}]

    def test_from_dict_minimal(self):
        data = {"role": "assistant", "content": "response"}
        content = MessageContent.from_dict(data)
        assert content.role == "assistant"
        assert content.content == "response"
        assert content.tool_calls is None


class TestMessageProcessor:
    def test_extract_filtered_content(self, message_processor, sample_history):
        filtered = message_processor.extract_filtered_content(sample_history)
        assert len(filtered) == 4
        assert all(msg["role"] in ["user", "assistant"] for msg in filtered)

    def test_convert_to_langchain_messages(self, message_processor, sample_history):
        filtered = message_processor.extract_filtered_content(sample_history)
        messages = message_processor.convert_to_langchain_messages(
            filtered, "current input", "test persona"
        )

        assert len(messages) == 6  # 4 history + 1 persona + 1 current input
        assert isinstance(messages[0], SystemMessage)
        assert messages[0].content == "test persona"
        assert isinstance(messages[-1], HumanMessage)
        assert messages[-1].content == "current input"

    def test_convert_without_persona(self, message_processor, sample_history):
        filtered = message_processor.extract_filtered_content(sample_history)
        messages = message_processor.convert_to_langchain_messages(
            filtered, "current input"
        )

        assert len(messages) == 5  # 4 history + 1 current input
        assert isinstance(messages[0], HumanMessage)


class TestStreamingCallbackHandler:
    @pytest.fixture
    def queue(self):
        return asyncio.Queue()

    @pytest.fixture
    def handler(self, queue):
        return StreamingCallbackHandler(queue=queue)

    def test_initialization(self, handler):
        assert handler.tokens == []
        assert handler.current_tool is None
        assert handler._loop is None

    @pytest.mark.asyncio
    async def test_queue_operations(self, handler):
        test_item = {"type": "test", "content": "test_content"}

        with pytest.raises(StreamingError):
            # Test with invalid queue operation
            handler.queue = None
            handler._put_to_queue(test_item)

    def test_tool_start(self, handler):
        handler._put_to_queue = MagicMock()
        handler.on_tool_start({"name": "test_tool"}, "test_input")

        assert handler.current_tool == "test_tool"
        handler._put_to_queue.assert_called_once()

    def test_tool_end(self, handler):
        handler._put_to_queue = MagicMock()
        handler.current_tool = "test_tool"
        handler.on_tool_end("test_output")

        assert handler.current_tool is None
        handler._put_to_queue.assert_called_once()

    def test_llm_new_token(self, handler):
        handler.on_llm_new_token("test_token")
        assert "test_token" in handler.tokens

    def test_llm_error(self, handler):
        with pytest.raises(ExecutionError):
            handler.on_llm_error(Exception("test error"))

    def test_tool_error(self, handler):
        handler._put_to_queue = MagicMock()
        handler.current_tool = "test_tool"
        handler.on_tool_error(Exception("test error"))

        assert handler.current_tool is None
        handler._put_to_queue.assert_called_once()


class TestLangGraphService:
    @pytest.fixture
    def service(self):
        return LangGraphService()

    @pytest.fixture
    def mock_chat_model(self):
        with patch("services.workflows.ChatOpenAI") as mock:
            yield mock

    @pytest.fixture
    def mock_tool_node(self):
        with patch("services.workflows.ToolNode") as mock:
            yield mock

    def test_create_chat_model(self, service, mock_chat_model):
        callback_handler = MagicMock()
        tools = [MagicMock()]

        service._create_chat_model(callback_handler, tools)
        mock_chat_model.assert_called_once()

    def test_create_workflow(self, service):
        chat = MagicMock()
        tool_node = MagicMock()

        workflow = service._create_workflow(chat, tool_node)
        assert workflow is not None

    @pytest.mark.asyncio
    async def test_execute_chat_stream_success(
        self, service, sample_history, mock_chat_model
    ):
        # Mock necessary components
        mock_queue = asyncio.Queue()
        await mock_queue.put({"type": "token", "content": "test"})
        await mock_queue.put({"type": "end"})

        mock_chat = MagicMock()
        mock_chat.invoke.return_value = AIMessage(content="test response")
        mock_chat_model.return_value = mock_chat

        # Execute stream
        tools_map = {"test_tool": MagicMock()}
        chunks = []
        async for chunk in service.execute_chat_stream(
            sample_history, "test input", "test persona", tools_map
        ):
            chunks.append(chunk)

        assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_execute_chat_stream_error(self, service, sample_history):
        with pytest.raises(ExecutionError):
            async for _ in service.execute_chat_stream(
                sample_history, "test input", None, None
            ):
                pass


@pytest.mark.asyncio
async def test_facade_function():
    with patch("services.workflows.LangGraphService") as mock_service:
        instance = mock_service.return_value
        instance.execute_chat_stream = AsyncMock()
        instance.execute_chat_stream.return_value = [{"type": "test"}]

        async for chunk in execute_langgraph_stream([], "test", None, None):
            assert chunk["type"] == "test"
