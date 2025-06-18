# AI Workflows

This directory contains AI-powered workflow implementations for the aibtcdev backend.

## Configuration

The workflows use separate configurations for chat-based LLMs and embedding models:

### Chat LLM Configuration

Set these environment variables to configure chat-based language models:

- `AIBTC_CHAT_DEFAULT_MODEL` - Default chat model (default: "gpt-4o")
- `AIBTC_CHAT_DEFAULT_TEMPERATURE` - Default temperature for chat models (default: "0.9")
- `AIBTC_CHAT_API_BASE` - API base URL for chat models (optional)
- `AIBTC_CHAT_API_KEY` - API key for chat models (required)
- `AIBTC_CHAT_REASONING_MODEL` - Model for reasoning tasks (default: "o3-mini")
- `AIBTC_CHAT_REASONING_TEMPERATURE` - Temperature for reasoning tasks (default: "0.9")

### Embedding Configuration

Set these environment variables to configure embedding models:

- `AIBTC_EMBEDDING_DEFAULT_MODEL` - Default embedding model (default: "text-embedding-ada-002")
- `AIBTC_EMBEDDING_API_BASE` - API base URL for embeddings (optional)
- `AIBTC_EMBEDDING_API_KEY` - API key for embeddings (required)
- `AIBTC_EMBEDDING_DIMENSIONS` - Embedding dimensions (default: "1536")

## Architecture

### Base Classes

- **BaseWorkflow**: Abstract base class for all workflow implementations
- **BaseWorkflowService**: Base service implementation with common streaming functionality
- **WorkflowService**: Abstract interface for workflow services

### Mixins

The workflows system uses a mixin architecture to provide reusable capabilities:

- **VectorRetrievalCapability**: Adds vector search and retrieval functionality
- **Other capability mixins**: Additional mixins for specific workflow features

### Services

- **ChatService**: Primary workflow service for handling chat interactions
- **MessageProcessor**: Handles message formatting and processing
- **StreamingCallbackHandler**: Manages real-time streaming of responses

### Utilities

- **ModelFactory**: Centralized factory for creating configured LLM instances
- **TokenUsageCallback**: Tracks and reports token usage for cost monitoring

## Model Factory Usage

The model factory provides several convenience functions:

- `create_chat_openai()`: Create a configured ChatOpenAI instance
- `create_planning_llm()`: For planning operations (uses default chat model)
- `create_reasoning_llm()`: For reasoning operations (defaults to configured reasoning model)
- `get_default_model_name()`: Get current default model name
- `get_default_temperature()`: Get current default temperature

## Usage

### Basic Chat Workflow

```python
from services.ai.workflows.workflow_service import execute_workflow_stream

async for chunk in execute_workflow_stream(
    workflow_type="chat",
    history=[],
    input_str="Hello, how can you help me?",
    persona="helpful_assistant"
):
    print(chunk)
```

### Vector-Enhanced Chat

```python
async for chunk in execute_workflow_stream(
    workflow_type="chat",
    history=[],
    input_str="Tell me about recent proposals",
    vector_collections=["dao_proposals", "knowledge_base"]
):
    print(chunk)
```

### Custom Model Configuration

```python
from services.ai.workflows.utils.model_factory import create_chat_openai

# Create custom chat model
llm = create_chat_openai(
    model="gpt-4o",
    temperature=0.7,
    streaming=True
)

# Create reasoning model
reasoning_llm = create_reasoning_llm(
    model="o3-mini",
    temperature=0.5
)
```

## Development

### Adding New Workflows

1. Create a new workflow class extending `BaseWorkflowService`
2. Implement the `_execute_stream_impl` method
3. Add any required mixins for additional capabilities
4. Register the workflow in the factory if needed

### Adding New Capabilities

1. Create a new mixin class extending `BaseWorkflowMixin`
2. Implement the capability methods
3. Add integration methods for use with existing workflows
4. Update documentation and tests

### Testing

Run the workflow tests:

```bash
python -m pytest tests/workflows/ -v
```

## Error Handling

The workflow system includes comprehensive error handling:

- **ExecutionError**: Raised when workflow execution fails
- **StreamingError**: Raised when streaming encounters issues
- **Validation errors**: Raised when input validation fails

All errors are logged with appropriate context and can be caught and handled by the calling code.

## Performance Considerations

- **Streaming**: All workflows support real-time streaming for better user experience
- **Caching**: Vector results are cached to improve performance
- **Token tracking**: Comprehensive token usage tracking for cost monitoring
- **Async/await**: Full async support for concurrent operations 