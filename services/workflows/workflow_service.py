"""Generic workflow service interface and factory.

This module provides a standard interface for all workflow services and
a factory function to instantiate the appropriate service based on configuration.
"""

import asyncio
import datetime
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, List, Optional, Type, Union

from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.embeddings import Embeddings
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from lib.logger import configure_logger
from services.workflows.base import ExecutionError, StreamingError
from services.workflows.react import (
    LangGraphService,
    MessageProcessor,
    StreamingCallbackHandler,
)
from services.workflows.vector_react import VectorLangGraphService

logger = configure_logger(__name__)


class WorkflowService(ABC):
    """Abstract base class for all workflow services."""

    @abstractmethod
    async def execute_stream(
        self,
        history: List[Dict],
        input_str: str,
        persona: Optional[str] = None,
        tools_map: Optional[Dict] = None,
        **kwargs,
    ) -> AsyncGenerator[Dict, None]:
        """Execute the workflow and stream results."""
        pass


class BaseWorkflowService(WorkflowService):
    """Base implementation for workflow services with common functionality."""

    def __init__(self):
        """Initialize the base workflow service."""
        self.message_processor = MessageProcessor()
        self.logger = configure_logger(self.__class__.__name__)

    async def execute_stream(
        self,
        history: List[Dict],
        input_str: str,
        persona: Optional[str] = None,
        tools_map: Optional[Dict] = None,
        **kwargs,
    ) -> AsyncGenerator[Dict, None]:
        """Standard interface to execute a workflow stream.

        This is the main entry point for executing workflows.
        Subclasses should implement _execute_stream_impl for specific implementations.

        Args:
            history: Conversation history
            input_str: Current user input
            persona: Optional persona to use
            tools_map: Optional tools to make available
            **kwargs: Additional arguments for specific workflow types

        Returns:
            Async generator of result chunks
        """
        self.logger.info(f"Executing {self.__class__.__name__} stream")
        self.logger.debug(
            f"Input parameters - History length: {len(history)}, "
            f"Persona present: {bool(persona)}, "
            f"Tools count: {len(tools_map) if tools_map else 0}"
        )

        try:
            # Process messages
            filtered_content = self.message_processor.extract_filtered_content(history)
            messages = self.message_processor.convert_to_langchain_messages(
                filtered_content, input_str, persona
            )

            # Execute the specific workflow implementation
            async for chunk in self._execute_stream_impl(
                messages=messages,
                input_str=input_str,
                persona=persona,
                tools_map=tools_map,
                **kwargs,
            ):
                yield chunk

        except Exception as e:
            error_msg = f"Failed to execute {self.__class__.__name__} stream: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            yield {
                "type": "error",
                "content": error_msg,
                "status": "error",
                "created_at": datetime.datetime.now().isoformat(),
            }
            raise ExecutionError(error_msg)

    @abstractmethod
    async def _execute_stream_impl(
        self,
        messages: List[Union[SystemMessage, HumanMessage, AIMessage]],
        input_str: str,
        persona: Optional[str] = None,
        tools_map: Optional[Dict] = None,
        **kwargs,
    ) -> AsyncGenerator[Dict, None]:
        """Implementation specific to each workflow service.

        Args:
            messages: Processed messages ready for the LLM
            input_str: Current user input
            persona: Optional persona to use
            tools_map: Optional tools to make available
            **kwargs: Additional arguments

        Returns:
            Async generator of result chunks
        """
        pass

    def setup_callback_handler(
        self,
        callback_queue: asyncio.Queue,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> StreamingCallbackHandler:
        """Set up a callback handler for streaming results.

        Args:
            callback_queue: Queue to stream results
            loop: Optional event loop to use

        Returns:
            Configured StreamingCallbackHandler
        """
        if not loop:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

        async def _put_token_in_queue(token_message: Dict) -> None:
            """Async helper to put token in queue."""
            await callback_queue.put(token_message)

        def on_llm_new_token(token: str, **kwargs) -> None:
            """Handle new token generation."""
            # Skip tokens marked as planning_only as they'll be sent as steps
            if kwargs.get("planning_only", False):
                return

            # Create token message
            token_message = {
                "type": "token",
                "content": token,
                "status": "processing",
                "created_at": datetime.datetime.now().isoformat(),
            }

            try:
                # Use the event loop directly instead of run_coroutine_threadsafe
                if loop.is_running():
                    loop.call_soon_threadsafe(
                        lambda: loop.create_task(_put_token_in_queue(token_message))
                    )
                else:
                    loop.run_until_complete(_put_token_in_queue(token_message))
            except Exception as e:
                logger.error(f"Error putting token in queue: {e}")

        # Create and return the callback handler
        handler = StreamingCallbackHandler(
            queue=callback_queue, on_llm_new_token=on_llm_new_token
        )

        # Store the original function as an attribute so it can be accessed and modified
        # by the planning workflows
        handler.custom_on_llm_new_token = on_llm_new_token

        return handler

    async def stream_task_results(
        self,
        task: asyncio.Task,
        callback_queue: asyncio.Queue,
        final_result_processor: Optional[callable] = None,
    ) -> AsyncGenerator[Dict, None]:
        """Stream results from a task to a queue.

        Args:
            task: Task to stream results from
            callback_queue: Queue to receive streamed results
            final_result_processor: Optional function to process the final task result

        Returns:
            Async generator of streamed results
        """
        self.logger.debug("Starting to stream task results")
        try:
            # Setup initial state tracking
            task_complete = False
            queue_size_reported = False

            # Stream intermediate results
            while not task_complete:
                try:
                    # Try to get a chunk from the queue, with timeout
                    # This allows for checking the task status periodically
                    chunk = await asyncio.wait_for(callback_queue.get(), timeout=0.1)

                    # A None chunk signals the end of streaming
                    if chunk is None:
                        self.logger.debug("Received None chunk, ending stream")
                        task_complete = True
                        break

                    # Yield the chunk to the consumer
                    self.logger.debug(f"Yielding chunk of type: {chunk.get('type')}")
                    yield chunk

                except asyncio.TimeoutError:
                    # Check if the task is done
                    if task.done():
                        task_complete = True

                        # If we have a final result processor, call it
                        if final_result_processor and not task.exception():
                            try:
                                final_result = task.result()
                                await final_result_processor(final_result)
                            except Exception as e:
                                self.logger.error(f"Error processing final result: {e}")

                        # Report any queue items left
                        if not queue_size_reported and not callback_queue.empty():
                            size = callback_queue.qsize()
                            self.logger.debug(
                                f"Task complete but {size} items left in queue"
                            )
                            queue_size_reported = True
                    # If the timeout just expired, continue and try again
                    continue

            # Send an end signal
            yield {"type": "end"}

        except Exception as e:
            self.logger.error(f"Error streaming task results: {e}")
            # Yield the error and re-raise
            yield {
                "type": "error",
                "content": f"Streaming error: {str(e)}",
                "status": "error",
                "created_at": datetime.datetime.now().isoformat(),
            }
            raise StreamingError(f"Failed to stream results: {str(e)}")

    # Static utility methods for non-BaseWorkflowService classes

    @staticmethod
    def create_callback_handler(
        callback_queue: asyncio.Queue,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> StreamingCallbackHandler:
        """Static utility method to create a callback handler without instantiating BaseWorkflowService.

        Args:
            callback_queue: Queue to stream results
            loop: Optional event loop to use

        Returns:
            Configured StreamingCallbackHandler
        """
        if not loop:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

        async def _put_token_in_queue(token_message: Dict) -> None:
            """Async helper to put token in queue."""
            await callback_queue.put(token_message)

        def on_llm_new_token(token: str, **kwargs) -> None:
            """Handle new token generation."""
            # Skip tokens marked as planning_only as they'll be sent as steps
            if kwargs.get("planning_only", False):
                return

            # Create token message
            token_message = {
                "type": "token",
                "content": token,
                "status": "processing",
                "created_at": datetime.datetime.now().isoformat(),
            }

            try:
                # Use the event loop directly instead of run_coroutine_threadsafe
                if loop.is_running():
                    loop.call_soon_threadsafe(
                        lambda: loop.create_task(_put_token_in_queue(token_message))
                    )
                else:
                    loop.run_until_complete(_put_token_in_queue(token_message))
            except Exception as e:
                logger.error(f"Error putting token in queue: {e}")

        # Create and return the callback handler
        handler = StreamingCallbackHandler(
            queue=callback_queue, on_llm_new_token=on_llm_new_token
        )

        # Store the original function as an attribute so it can be accessed and modified
        # by the planning workflows
        handler.custom_on_llm_new_token = on_llm_new_token

        return handler

    @staticmethod
    async def stream_results_from_task(
        task: asyncio.Task,
        callback_queue: asyncio.Queue,
        final_result_processor: Optional[callable] = None,
        logger_name: str = "WorkflowService",
    ) -> AsyncGenerator[Dict, None]:
        """Static utility method to stream results from a task without instantiating BaseWorkflowService.

        Args:
            task: Task to stream results from
            callback_queue: Queue to receive streamed results
            final_result_processor: Optional function to process the final task result
            logger_name: Name to use for the logger

        Returns:
            Async generator of streamed results
        """
        logger = configure_logger(logger_name)
        logger.debug("Starting to stream task results")
        try:
            # Setup initial state tracking
            task_complete = False
            queue_size_reported = False

            # Stream intermediate results
            while not task_complete:
                try:
                    # Try to get a chunk from the queue, with timeout
                    # This allows for checking the task status periodically
                    chunk = await asyncio.wait_for(callback_queue.get(), timeout=0.1)

                    # A None chunk signals the end of streaming
                    if chunk is None:
                        logger.debug("Received None chunk, ending stream")
                        task_complete = True
                        break

                    # Yield the chunk to the consumer
                    logger.debug(f"Yielding chunk of type: {chunk.get('type')}")
                    yield chunk

                except asyncio.TimeoutError:
                    # Check if the task is done
                    if task.done():
                        task_complete = True

                        # If we have a final result processor, call it
                        if final_result_processor and not task.exception():
                            try:
                                final_result = task.result()
                                await final_result_processor(final_result)
                            except Exception as e:
                                logger.error(f"Error processing final result: {e}")

                        # Report any queue items left
                        if not queue_size_reported and not callback_queue.empty():
                            size = callback_queue.qsize()
                            logger.debug(
                                f"Task complete but {size} items left in queue"
                            )
                            queue_size_reported = True
                    # If the timeout just expired, continue and try again
                    continue

            # Send an end signal
            yield {"type": "end"}

        except Exception as e:
            logger.error(f"Error streaming task results: {e}")
            # Yield the error and re-raise
            yield {
                "type": "error",
                "content": f"Streaming error: {str(e)}",
                "status": "error",
                "created_at": datetime.datetime.now().isoformat(),
            }
            raise StreamingError(f"Failed to stream results: {str(e)}")


class WorkflowBuilder:
    """Builder for creating workflow instances.

    This class helps create workflow instances with the desired configuration.
    """

    def __init__(self, workflow_class: Type, **kwargs):
        """Initialize the workflow builder.

        Args:
            workflow_class: The workflow class to build
            **kwargs: Additional arguments for the workflow
        """
        self.workflow_class = workflow_class
        self.kwargs = kwargs
        self.callback_handler = None
        self.tools = []
        self.model_name = kwargs.get("model_name", "gpt-4o")
        self.temperature = kwargs.get("temperature", 0.7)

    def with_callback_handler(
        self, callback_handler: BaseCallbackHandler
    ) -> "WorkflowBuilder":
        """Set the callback handler for the workflow.

        Args:
            callback_handler: The callback handler to use

        Returns:
            Self for chaining
        """
        self.callback_handler = callback_handler
        return self

    def with_tools(self, tools: List[Any]) -> "WorkflowBuilder":
        """Set the tools for the workflow.

        Args:
            tools: The tools to use

        Returns:
            Self for chaining
        """
        self.tools = tools
        return self

    def with_model(self, model_name: str) -> "WorkflowBuilder":
        """Set the model name for the workflow.

        Args:
            model_name: The model name to use

        Returns:
            Self for chaining
        """
        self.model_name = model_name
        return self

    def with_temperature(self, temperature: float) -> "WorkflowBuilder":
        """Set the temperature for the workflow.

        Args:
            temperature: The temperature to use

        Returns:
            Self for chaining
        """
        self.temperature = temperature
        return self

    def build(self, **extra_kwargs) -> Any:
        """Build the workflow instance.

        Args:
            **extra_kwargs: Additional arguments to pass to the workflow constructor

        Returns:
            The configured workflow instance
        """
        # Combine all configurations
        build_args = {
            "model_name": self.model_name,
            "temperature": self.temperature,
            **self.kwargs,
            **extra_kwargs,  # Add any extra kwargs passed during build
        }

        # Add callback handler and tools if provided
        if self.callback_handler:
            build_args["callback_handler"] = self.callback_handler
        if self.tools:
            build_args["tools"] = self.tools

        return self.workflow_class(**build_args)


class WorkflowFactory:
    """Factory for creating workflow service instances."""

    @classmethod
    def create_workflow_service(
        cls,
        workflow_type: str = "react",
        vector_collections: Optional[Union[str, List[str]]] = None,
        embeddings: Optional[Embeddings] = None,
        **kwargs,
    ) -> WorkflowService:
        """Create a workflow service instance based on the workflow type.

        Args:
            workflow_type: Type of workflow to create ("react", "preplan", "vector", "vector_preplan")
            vector_collections: Vector collection name(s) for vector workflows
            embeddings: Embeddings model for vector workflows
            **kwargs: Additional parameters to pass to the service

        Returns:
            An instance of a WorkflowService implementation
        """
        # Import service classes here to avoid circular imports
        from services.workflows.preplan_react import PreplanLangGraphService
        from services.workflows.vector_preplan_react import (
            VectorPreplanLangGraphService,
        )

        # Map workflow types to their service classes
        service_map = {
            "react": LangGraphService,
            "preplan": PreplanLangGraphService,
            "vector": VectorLangGraphService,
            "vector_preplan": VectorPreplanLangGraphService,
        }

        if workflow_type not in service_map:
            raise ValueError(f"Unsupported workflow type: {workflow_type}")

        service_class = service_map[workflow_type]

        # Handle vector-based workflow special cases
        if workflow_type in ["vector", "vector_preplan"]:
            if not vector_collections:
                raise ValueError(
                    f"Vector collection name(s) required for {workflow_type} workflow"
                )

            if not embeddings:
                embeddings = OpenAIEmbeddings()

            return service_class(
                collection_names=vector_collections,
                embeddings=embeddings,
                **kwargs,
            )

        # For other workflow types
        return service_class(**kwargs)


async def execute_workflow_stream(
    workflow_type: str,
    history: List[Dict],
    input_str: str,
    persona: Optional[str] = None,
    tools_map: Optional[Dict] = None,
    vector_collections: Optional[Union[str, List[str]]] = None,
    embeddings: Optional[Embeddings] = None,
    **kwargs,
) -> AsyncGenerator[Dict, None]:
    """Unified interface for executing any workflow stream.

    Args:
        workflow_type: Type of workflow to execute
        history: Conversation history
        input_str: Current user input
        persona: Optional persona to use
        tools_map: Optional tools to make available
        vector_collections: Vector collection name(s) for vector workflows
        embeddings: Embeddings model for vector workflows
        **kwargs: Additional parameters for specific workflow types

    Returns:
        Async generator of result chunks
    """
    service = WorkflowFactory.create_workflow_service(
        workflow_type=workflow_type,
        vector_collections=vector_collections,
        embeddings=embeddings,
        **kwargs,
    )

    # Execute the stream through the service's execute_stream method
    async for chunk in service.execute_stream(
        history=history,
        input_str=input_str,
        persona=persona,
        tools_map=tools_map,
        **kwargs,
    ):
        yield chunk
