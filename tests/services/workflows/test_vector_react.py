"""Tests for the Vector React workflow."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.documents import Document

from services.workflows.vector_react import (
    VectorLangGraphService,
    VectorReactWorkflow,
    add_documents_to_vectors,
)


class TestVectorOperations(unittest.TestCase):
    """Tests for the vector store operations."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_backend = MagicMock()
        self.mock_collection = MagicMock()
        self.mock_backend.get_vector_collection.return_value = self.mock_collection
        self.mock_backend.query_vectors = AsyncMock(
            return_value=[
                {
                    "id": "1",
                    "page_content": "test content",
                    "metadata": {"source": "test"},
                }
            ]
        )
        self.mock_backend.add_vectors = AsyncMock(return_value=["1"])
        self.mock_backend.create_vector_collection.return_value = self.mock_collection

        # Patch backend
        self.backend_patch = patch(
            "services.workflows.vector_react.backend", self.mock_backend
        )
        self.backend_patch.start()

    def tearDown(self):
        """Tear down test fixtures."""
        self.backend_patch.stop()

    async def test_add_documents_to_vectors(self):
        """Test adding documents to vector store."""
        # Setup
        documents = [Document(page_content="test content", metadata={"source": "test"})]

        # Execute
        result = await add_documents_to_vectors(
            collection_name="test_collection", documents=documents
        )

        # Verify
        self.mock_backend.get_vector_collection.assert_called_once_with(
            "test_collection"
        )
        self.mock_backend.add_vectors.assert_called_once()
        self.assertEqual(result, ["1"])

    async def test_add_documents_creates_collection_if_not_exists(self):
        """Test that collection is created if it doesn't exist."""
        # Setup
        documents = [Document(page_content="test content", metadata={"source": "test"})]
        self.mock_backend.get_vector_collection.side_effect = [
            ValueError,
            self.mock_collection,
        ]

        # Execute
        result = await add_documents_to_vectors(
            collection_name="new_collection", documents=documents
        )

        # Verify
        self.mock_backend.create_vector_collection.assert_called_once_with(
            "new_collection", dimensions=1536
        )
        self.mock_backend.add_vectors.assert_called_once()
        self.assertEqual(result, ["1"])


class TestVectorReactWorkflow(unittest.TestCase):
    """Tests for the VectorReactWorkflow class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_callback_handler = MagicMock()
        self.mock_tools = []
        self.mock_backend = MagicMock()
        self.mock_backend.query_vectors = AsyncMock(
            return_value=[
                {
                    "id": "1",
                    "page_content": "test content",
                    "metadata": {"source": "test"},
                }
            ]
        )
        self.backend_patch = patch(
            "services.workflows.vector_react.backend", self.mock_backend
        )
        self.backend_patch.start()

        self.mock_llm = MagicMock()
        self.mock_llm.invoke = MagicMock()

    def tearDown(self):
        """Tear down test fixtures."""
        self.backend_patch.stop()

    @patch("services.workflows.vector_react.ChatOpenAI")
    def test_create_graph(self, mock_chat_openai):
        """Test creating the workflow graph."""
        # Setup
        mock_chat_openai.return_value.bind_tools.return_value = self.mock_llm
        workflow = VectorReactWorkflow(
            callback_handler=self.mock_callback_handler,
            tools=self.mock_tools,
            collection_name="test_collection",
            llm=self.mock_llm,
        )

        # Execute
        graph = workflow._create_graph()

        # Verify
        self.assertIsNotNone(graph)
        # Check that the graph has the expected nodes
        self.assertIn("vector_retrieval", graph.nodes)
        self.assertIn("agent", graph.nodes)
        self.assertIn("tools", graph.nodes)


class TestVectorLangGraphService(unittest.IsolatedAsyncioTestCase):
    """Tests for the VectorLangGraphService class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_backend = MagicMock()
        self.mock_backend.query_vectors = AsyncMock(
            return_value=[
                {
                    "id": "1",
                    "page_content": "test content",
                    "metadata": {"source": "test"},
                }
            ]
        )
        self.backend_patch = patch(
            "services.workflows.vector_react.backend", self.mock_backend
        )
        self.backend_patch.start()

        self.service = VectorLangGraphService(collection_name="test_collection")

    def tearDown(self):
        """Tear down test fixtures."""
        self.backend_patch.stop()

    @patch("services.workflows.vector_react.VectorReactWorkflow")
    @patch("services.workflows.vector_react.StreamingCallbackHandler")
    async def test_execute_vector_react_stream(self, mock_handler, mock_workflow):
        """Test executing a vector react stream."""
        # Setup
        history = [{"role": "user", "content": "test message"}]
        input_str = "test input"
        mock_queue = AsyncMock()
        mock_queue.get = AsyncMock(
            side_effect=[{"type": "token", "content": "test"}, {"type": "end"}]
        )
        mock_handler.return_value = MagicMock()

        mock_graph = MagicMock()
        mock_runnable = MagicMock()
        mock_workflow.return_value._create_graph.return_value = mock_graph
        mock_graph.compile.return_value = mock_runnable

        mock_task = MagicMock()
        mock_task.done = MagicMock(side_effect=[False, False, True])
        mock_result = {"messages": [MagicMock(content="test result")]}
        mock_task.__await__ = MagicMock(return_value=mock_result)

        # Execute
        with (
            patch("asyncio.Queue", return_value=mock_queue),
            patch("asyncio.get_running_loop"),
            patch("asyncio.create_task", return_value=mock_task),
            patch("asyncio.wait_for", side_effect=lambda *args, **kwargs: args[0]),
        ):
            results = [
                chunk
                async for chunk in self.service.execute_vector_react_stream(
                    history, input_str
                )
            ]

        # Verify
        self.assertEqual(len(results), 3)  # token, end, result
        self.assertEqual(results[0], {"type": "token", "content": "test"})
        self.assertEqual(results[1], {"type": "end"})
        self.assertEqual(results[2]["type"], "result")


if __name__ == "__main__":
    unittest.main()
