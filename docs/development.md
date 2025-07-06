# Development Documentation

This document provides comprehensive information for developers working on aibtcdev-backend.

## Table of Contents

- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Architecture Overview](#architecture-overview)
- [Environment Configuration](#environment-configuration)
- [Testing](#testing)
- [Code Style and Quality](#code-style-and-quality)
- [Debugging](#debugging)
- [Database Development](#database-development)
- [Background Services](#background-services)
- [Performance Considerations](#performance-considerations)
- [Contributing Workflow](#contributing-workflow)
- [Common Development Tasks](#common-development-tasks)
- [Troubleshooting](#troubleshooting)

## Development Setup

### Prerequisites

Ensure you have the following installed:

- **Python 3.13**: Required for the latest async features
- **UV**: Modern Python package manager for fast dependency resolution
- **Bun**: Required for TypeScript tools in `agent-tools-ts/`
- **Git**: Version control with submodule support
- **Node.js & npm**: For agent tools development
- **Docker**: Optional, for containerized development

### Initial Setup

```bash
# Clone repository with submodules
git clone <repository-url>
cd aibtcdev-backend
git submodule init
git submodule update --remote

# Install UV (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh
# Or on macOS: brew install uv

# Create and activate virtual environment
uv sync
source .venv/bin/activate

# Install TypeScript tools
cd agent-tools-ts/
bun install
cd ..

# Copy environment configuration
cp .env.example .env
# Edit .env with your development settings
```

### Verify Installation

```bash
# Check Python environment
python --version  # Should be 3.13.x
which python      # Should point to .venv/bin/python

# Check dependencies
uv pip list

# Test basic functionality
python -c "from app.config import config; print('Config loaded successfully')"
```

## Project Structure

```
aibtcdev-backend/
├── app/                          # Main application package
│   ├── api/                      # API endpoints and routes
│   │   ├── chat.py              # WebSocket chat endpoints
│   │   ├── tools.py             # Tool execution endpoints
│   │   ├── webhooks.py          # Webhook handlers
│   │   └── dependencies.py      # Authentication dependencies
│   ├── backend/                  # Backend services and models
│   ├── config/                   # Configuration management
│   ├── lib/                      # Shared utilities and tools
│   ├── services/                 # Business logic services
│   │   ├── ai/                  # AI-related services
│   │   ├── communication/       # WebSocket and messaging
│   │   ├── core/                # Core business logic
│   │   ├── infrastructure/      # System infrastructure
│   │   ├── integrations/        # External service integrations
│   │   └── processing/          # Data processing services
│   ├── tools/                    # Tool implementations
│   ├── main.py                   # FastAPI web server
│   └── worker.py                 # Background worker
├── agent-tools-ts/               # TypeScript tools (submodule)
├── tests/                        # Test suite
├── docs/                         # Documentation
├── .env.example                  # Environment template
├── ruff.toml                     # Code style configuration
├── pyproject.toml               # Project configuration
└── README.md                    # Project overview
```

### Key Components

- **`main.py`**: FastAPI application with WebSocket support
- **`worker.py`**: Background services (jobs, bots, monitoring)
- **`app/api/`**: REST and WebSocket API implementations
- **`app/services/`**: Business logic organized by domain
- **`app/tools/`**: Individual tool implementations
- **`app/backend/`**: Data models and backend abstractions

## Architecture Overview

### Dual-Mode Architecture

The application operates in two distinct modes:

**Web Server Mode (`main.py`)**:
- FastAPI application with CORS
- WebSocket endpoints for real-time chat
- REST API for tool execution
- Health checks and monitoring

**Worker Mode (`worker.py`)**:
- Background job processing
- Telegram bot integration
- System metrics monitoring
- Automated task execution

### Service Architecture

```
┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Webhooks      │
│   (WebSocket)   │    │   (External)    │
└─────────┬───────┘    └─────────┬───────┘
          │                      │
          ▼                      ▼
┌─────────────────────────────────────────┐
│            FastAPI Router               │
├─────────────────────────────────────────┤
│         Authentication Layer            │
├─────────────────────────────────────────┤
│            Service Layer                │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │   AI    │ │  DAO    │ │ Wallet  │   │
│  │Services │ │Services │ │Services │   │
│  └─────────┘ └─────────┘ └─────────┘   │
├─────────────────────────────────────────┤
│            Backend Layer                │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │Database │ │Blockchain│ │External │   │
│  │ (Supabase)│ │(Stacks) │ │  APIs  │   │
│  └─────────┘ └─────────┘ └─────────┘   │
└─────────────────────────────────────────┘
```

## Environment Configuration

### Required Environment Variables

Create a `.env` file based on `.env.example`:

```bash
# Network Configuration
AIBTC_NETWORK=testnet  # or mainnet

# Database Configuration
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# AI Configuration
OPENAI_API_KEY=your_openai_api_key

# Blockchain Configuration
STACKS_API_URL=https://api.testnet.hiro.so
BITCOIN_API_URL=https://api.blockstream.info/testnet

# Authentication
AIBTC_WEBHOOK_AUTH_TOKEN=Bearer your_webhook_secret

# Optional Integrations
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TWITTER_API_KEY=your_twitter_api_key
```

### Development vs Production

**Development Configuration**:
```bash
# .env.development
AIBTC_NETWORK=testnet
DEBUG=true
LOG_LEVEL=DEBUG
AIBTC_CORS_ORIGINS=http://localhost:3000
```

**Production Configuration**:
```bash
# .env.production
AIBTC_NETWORK=mainnet
DEBUG=false
LOG_LEVEL=INFO
AIBTC_CORS_ORIGINS=https://app.aibtc.dev
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_api.py

# Run specific test
pytest tests/test_api.py::test_websocket_connection

# Run with verbose output
pytest -v

# Run tests in parallel
pytest -n auto
```

### Test Structure

```
tests/
├── conftest.py              # Test configuration and fixtures
├── test_api/                # API endpoint tests
│   ├── test_chat.py         # WebSocket chat tests
│   ├── test_tools.py        # Tool endpoint tests
│   └── test_webhooks.py     # Webhook tests
├── test_services/           # Service layer tests
├── test_tools/              # Individual tool tests
└── test_integration/        # Integration tests
```

### Writing Tests

**API Test Example**:
```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

@pytest.mark.asyncio
async def test_websocket_chat():
    with client.websocket_connect("/chat/ws?token=test_token") as websocket:
        # Send test message
        websocket.send_json({
            "type": "message",
            "thread_id": "test-thread",
            "content": "Hello"
        })
        
        # Receive response
        data = websocket.receive_json()
        assert data["type"] in ["message", "error"]
```

**Service Test Example**:
```python
import pytest
from app.services.core.chat_service import process_chat_message

@pytest.mark.asyncio
async def test_chat_service():
    result = await process_chat_message(
        job_id="test-job",
        thread_id="test-thread",
        profile=mock_profile,
        agent_id=None,
        input_str="Test message",
        history=[],
        output_queue=mock_queue
    )
    assert result is not None
```

### Test Configuration

**pytest Configuration** (`pytest.ini`):
```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    --strict-markers
    --disable-warnings
    --tb=short
markers =
    asyncio: marks tests as async
    integration: marks tests as integration tests
    slow: marks tests as slow running
```

## Code Style and Quality

### Ruff Configuration

The project uses `ruff` for linting and formatting. Configuration in `ruff.toml`:

```toml
target-version = "py313"
line-length = 88
extend-exclude = ["agent-tools-ts"]

[lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # Pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
]

[format]
quote-style = "double"
indent-style = "space"
```

### Code Style Commands

```bash
# Check code style
ruff check .

# Format code
ruff format .

# Check and fix automatically
ruff check --fix .

# Check specific file
ruff check app/main.py
```

### Pre-commit Setup

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run on all files
pre-commit run --all-files
```

**`.pre-commit-config.yaml`**:
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.6
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
```

## Debugging

### Logging Configuration

```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Module-specific logging
from app.lib.logger import configure_logger
logger = configure_logger(__name__)
logger.debug("Debug message")
```

### Debugging WebSocket Connections

```python
# Add debug logging to WebSocket handler
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    logger.debug(f"WebSocket connection attempt from {websocket.client}")
    
    try:
        await websocket.accept()
        logger.debug("WebSocket connection accepted")
        
        while True:
            data = await websocket.receive_json()
            logger.debug(f"Received WebSocket message: {data}")
            
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
```

### Debugging AI Responses

```python
# Debug AI service calls
from app.services.ai.workflows import evaluate_proposal_comprehensive

result = await evaluate_proposal_comprehensive(
    proposal_id="test",
    proposal_content="Test proposal",
    config={"debug": True}  # Enable debug mode
)
```

### Using Python Debugger

```python
# Add breakpoint in code
import pdb; pdb.set_trace()

# Or use modern debugger
import ipdb; ipdb.set_trace()

# Or Python 3.7+ builtin
breakpoint()
```

### Debug Environment Setup

```bash
# Run with debug mode
DEBUG=true python -m app.main

# Run with verbose logging
LOG_LEVEL=DEBUG python -m app.worker

# Debug specific service
python -c "
import asyncio
from app.services.core.chat_service import process_chat_message
# Add debug code here
"
```

## Database Development

### Database Access

```python
from app.backend.factory import backend

# List entities
profiles = backend.list_profiles()
agents = backend.list_agents()
proposals = backend.list_proposals()

# Get specific entity
profile = backend.get_profile(profile_id)
agent = backend.get_agent(agent_id)

# Create entity
from app.backend.models import ProfileCreate
new_profile = backend.create_profile(ProfileCreate(...))
```

### Database Migrations

```bash
# Apply migrations (if using Alembic)
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "Add new field"

# Check migration status
alembic current
```

### Local Database Setup

For development with local database:

```bash
# Start local Supabase (if using)
supabase start

# Reset database
supabase db reset

# Apply seed data
python scripts/seed_database.py
```

## Background Services

### Running Worker Mode

```bash
# Start background worker
python -m app.worker

# Run specific job
python -c "
import asyncio
from app.services.infrastructure.startup_service import run_standalone
asyncio.run(run_standalone())
"
```

### Job System Development

```python
# Create custom job
from app.services.processing.job_service import JobService

class CustomJob:
    async def execute(self):
        # Job implementation
        pass

# Register job
job_service = JobService()
await job_service.register_job("custom_job", CustomJob())
```

### Telegram Bot Development

```python
# Test Telegram bot locally
from app.services.communication.telegram_service import TelegramService

telegram = TelegramService()
await telegram.send_message("Test message")
```

## Performance Considerations

### Async Best Practices

```python
# Good: Proper async usage
async def process_multiple_requests():
    tasks = [process_request(req) for req in requests]
    results = await asyncio.gather(*tasks)
    return results

# Bad: Blocking async
async def bad_example():
    for req in requests:
        result = await process_request(req)  # Sequential, not parallel
```

### WebSocket Performance

```python
# Use connection pooling
from app.services.communication.websocket_service import websocket_manager

# Optimize message handling
async def handle_message(message):
    # Process quickly to avoid blocking
    asyncio.create_task(process_in_background(message))
```

### Database Performance

```python
# Use filtering to reduce data transfer
from app.backend.models import ProposalFilter

proposals = backend.list_proposals(
    ProposalFilter(
        dao_id=specific_dao_id,
        status="active",
        limit=100
    )
)

# Batch operations when possible
batch_results = await asyncio.gather(*[
    backend.get_proposal(pid) for pid in proposal_ids
])
```

## Contributing Workflow

### Branch Strategy

```bash
# Create feature branch
git checkout -b feature/new-feature

# Create bugfix branch
git checkout -b bugfix/fix-issue

# Create hotfix branch
git checkout -b hotfix/critical-fix
```

### Development Process

1. **Create Branch**: From main branch
2. **Develop**: Implement feature with tests
3. **Test**: Run full test suite
4. **Format**: Apply code formatting
5. **Commit**: Make atomic commits with clear messages
6. **Push**: Push branch to remote
7. **PR**: Create pull request with description
8. **Review**: Address review comments
9. **Merge**: Merge after approval

### Commit Message Format

```
feat: add WebSocket authentication support

- Implement token-based auth for WebSocket connections
- Add query parameter validation
- Update documentation

Closes #123
```

### Pull Request Checklist

- [ ] Tests pass (`pytest`)
- [ ] Code formatted (`ruff format`)
- [ ] Linting clean (`ruff check`)
- [ ] Documentation updated
- [ ] CHANGELOG updated (if applicable)
- [ ] Breaking changes noted

## Common Development Tasks

### Adding New API Endpoint

1. **Define Pydantic Models**:
```python
# In app/api/tools.py
class NewFeatureRequest(BaseModel):
    param1: str
    param2: Optional[int] = None
```

2. **Create Endpoint**:
```python
@router.post("/new-feature")
async def new_feature_endpoint(
    payload: NewFeatureRequest,
    profile: Profile = Depends(verify_profile_from_token)
):
    # Implementation
    return JSONResponse(content=result)
```

3. **Add Tests**:
```python
def test_new_feature_endpoint():
    response = client.post("/tools/new-feature", json={
        "param1": "value1"
    }, headers={"Authorization": "Bearer test_token"})
    assert response.status_code == 200
```

### Adding New Tool

1. **Create Tool Class**:
```python
# In app/tools/
from app.lib.tools import BaseTool

class NewTool(BaseTool):
    name = "new_tool"
    description = "Tool description"
    
    async def _arun(self, param1: str) -> dict:
        # Implementation
        return {"result": "success"}
```

2. **Register Tool**:
```python
# Tools are auto-discovered via get_available_tools()
```

3. **Add Tool Tests**:
```python
@pytest.mark.asyncio
async def test_new_tool():
    tool = NewTool()
    result = await tool._arun("test_param")
    assert result["result"] == "success"
```

### Adding New Service

1. **Create Service Module**:
```python
# In app/services/domain/
class NewService:
    def __init__(self):
        self.logger = configure_logger(__name__)
    
    async def process(self, data):
        # Implementation
        pass
```

2. **Add Service Tests**:
```python
@pytest.mark.asyncio
async def test_new_service():
    service = NewService()
    result = await service.process(test_data)
    assert result is not None
```

## Troubleshooting

### Common Issues

**Import Errors**:
```bash
# Ensure you're in the right environment
source .venv/bin/activate
which python

# Reinstall dependencies
uv sync --refresh
```

**Database Connection Issues**:
```bash
# Check environment variables
echo $SUPABASE_URL
echo $SUPABASE_KEY

# Test database connection
python -c "from app.backend.factory import backend; print(backend.list_profiles())"
```

**WebSocket Connection Failures**:
```bash
# Check server logs
tail -f logs/app.log

# Test with simple client
python -c "
import asyncio
import websockets

async def test():
    async with websockets.connect('ws://localhost:8000/chat/ws?token=test') as ws:
        print('Connected')

asyncio.run(test())
"
```

**AI Service Errors**:
```bash
# Check OpenAI API key
python -c "import openai; print(openai.api_key)"

# Test API connection
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
     https://api.openai.com/v1/models
```

### Performance Issues

**Slow API Responses**:
1. Check database query performance
2. Monitor AI service response times
3. Profile code with `cProfile`
4. Add timing logs to identify bottlenecks

**Memory Usage**:
1. Monitor with `memory_profiler`
2. Check for memory leaks in long-running processes
3. Optimize data structures and caching

**WebSocket Connection Limits**:
1. Monitor active connections
2. Implement connection pooling
3. Add connection cleanup mechanisms

### Getting Help

1. **Check Documentation**: Start with relevant docs
2. **Search Issues**: Look for similar problems
3. **Enable Debug Logging**: Add verbose logging
4. **Create Minimal Reproduction**: Isolate the issue
5. **Ask for Help**: Create detailed issue with context