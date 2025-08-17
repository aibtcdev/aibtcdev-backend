# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Essential Commands

### Python Development
```bash
# Start the web server (main API)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Start worker mode (background services)
python -m app.worker

# Format and lint code
ruff format .
ruff check .

# Type checking
typos  # Check for typos

# Run tests
pytest  # Testing framework

# Install dependencies
uv sync  # UV package manager
source .venv/bin/activate  # Activate virtual environment

# Install TypeScript tools
cd agent-tools-ts/ && bun install && cd ..
```

### TypeScript Tools (agent-tools-ts/)
```bash
# Build TypeScript tools
bun run build

# Development mode with watch
bun run dev

# Type checking
bun run typecheck

# Run tests (currently skipped)
bun run test
```

## Architecture Overview

### Dual-Mode System
The application operates in two distinct modes:

1. **Web Server Mode** (`app/main.py`): FastAPI application with CORS, WebSocket chat endpoint, RESTful APIs, and health monitoring
2. **Worker Mode** (`app/worker.py`): Background job processing, Telegram bot integration, system metrics monitoring

### Service Layer Structure
- **API Layer** (`app/api/`): REST endpoints for agents, DAOs, tools, webhooks, profiles
- **Services** (`app/services/`): Core business logic organized by domain
  - `ai/`: AI workflows, embeddings, LLM processing, evaluation
  - `communication/`: Discord, Telegram, Twitter integrations
  - `core/`: DAO service and core business logic
  - `infrastructure/`: Job management, scheduling, startup services
  - `integrations/`: External APIs (Hiro, webhooks, chainhook handlers)
  - `processing/`: Data processing services
- **Backend Layer** (`app/backend/`): Data persistence with Supabase integration
- **Tools** (`app/tools/`): Domain-specific utilities for agent accounts, DAOs, DEX trading, wallets

### Key Components

#### Job Management System
Advanced job processing system with auto-discovery, monitoring, and background task execution located in `app/services/infrastructure/job_management/`.

#### Webhook Handlers
Sophisticated blockchain event processing system in `app/services/integrations/webhooks/chainhook/` with handlers for:
- DAO proposals and voting
- Trading events (buy/sell)
- Airdrop processing
- Block state monitoring

#### TypeScript Tools Integration
The `agent-tools-ts/` submodule provides blockchain interaction utilities for:
- Stacks blockchain operations
- DEX trading (Faktory, Bitflow, Alex, Jing)
- DAO contract deployments
- Agent account management
- Wallet operations

## Development Practices

### Code Style
- Follow Cursor rules in `.cursor/rules/global.mdc`
- Use `ruff` for formatting with double quotes and 4-space indentation
- Type hints required for all functions
- Google-style docstrings
- Snake_case for variables/functions, PascalCase for classes

### Environment Setup
- Python 3.13+ required
- UV for dependency management (`uv.lock`)
- Bun for TypeScript tools
- Environment configuration via `.env` file

### Testing
- Use `pytest` for Python testing
- TypeScript tests currently skipped
- Run tests before commits

### Configuration
Environment variables are organized in `app/config.py` with dataclasses for:
- Database (Supabase)
- Twitter/X integration
- Backend wallet operations
- Various service configurations

## Important Notes

### Security
- Never commit sensitive information (API keys, seed phrases)
- Use environment variables for all secrets
- Validate all user inputs

### Dependencies
- Python dependencies managed via `pyproject.toml` and UV
- TypeScript dependencies in `agent-tools-ts/package.json`
- Git submodule for agent-tools-ts integration

### Blockchain Integration
The system is deeply integrated with Stacks blockchain:
- Native Stacks network support (mainnet/testnet)
- DAO proposal management and voting
- DEX trading across multiple platforms
- Agent account autonomous operations
- Transaction processing and event handling