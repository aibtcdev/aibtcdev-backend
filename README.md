# aibtcdev-backend

## Overview

aibtcdev-backend is a sophisticated FastAPI-based backend service that powers AI-driven interactions with Bitcoin and Stacks blockchain technologies. The service provides:

1. Real-time chat functionality with AI agents via WebSocket
2. Automated DAO management and monitoring
3. Social media integration (Twitter, Telegram, Discord)
4. Blockchain interaction capabilities (Stacks, Bitcoin)
5. Market data analysis and reporting
6. Document processing and vector search capabilities

The system is designed to be modular, scalable, and easily configurable through environment variables.

## Disclaimer

aibtc.dev is not liable for any lost, locked, or mistakenly sent funds. This is alpha software—use at your own risk. Any STX sent to you is owned by you, the trader, and may be redeemed, including profits or losses, at the end of the aibtc.dev Champions Sprint (~5 days). By participating, you accept that aibtc.dev is not responsible for any product use, costs, taxes incurred from trading STX or any other digital asset, or any other liability.

## Prerequisites

- Python 3.13
- [Bun](https://bun.sh/) (for TypeScript tools)
- Git
- Conda (recommended for development) or Docker
- Node.js and npm (for agent tools)

## Project Structure

```
aibtcdev-backend/
├── api/                    # FastAPI endpoint definitions
│   ├── chat.py            # WebSocket chat endpoints
│   ├── tools.py           # Tool endpoints
│   ├── webhooks.py        # Webhook handlers
│   └── dependencies.py    # API dependencies
├── services/              # Core business logic
│   ├── workflows/         # Workflow implementations
│   ├── runner/           # Background task runners
│   ├── webhooks/         # Webhook processors
│   ├── discord/          # Discord integration
│   ├── chat.py           # Chat service
│   ├── daos.py           # DAO operations
│   ├── schedule.py       # Task scheduling
│   ├── startup.py        # App lifecycle management
│   ├── twitter.py        # Twitter integration
│   ├── bot.py            # Telegram bot
│   └── websocket.py      # WebSocket management
├── backend/              # Database and storage
├── tools/                # AI agent tools
├── lib/                  # Shared utilities
├── tests/                # Test suite
├── docs/                 # Documentation
├── examples/             # Usage examples
└── agent-tools-ts/       # TypeScript-based agent tools
```

## Key Features

### 1. AI Chat System
- Real-time WebSocket-based chat
- AI agent integration with OpenAI
- Context-aware conversations
- Document-based knowledge integration
- Vector search capabilities

### 2. DAO Management
- Automated DAO deployment monitoring
- Proposal creation and tracking
- Vote processing
- Automated conclusion handling
- Tweet generation for DAO events

### 3. Social Media Integration
- Twitter automation and monitoring
- Telegram bot integration
- Discord notifications
- Automated content generation
- Social engagement tracking

### 4. Blockchain Integration
- Stacks blockchain interaction
- Bitcoin network monitoring
- Multiple API integrations:
  - Hiro
  - Alex
  - Velar
  - Platform API

### 5. Market Analysis
- LunarCrush integration
- CoinMarketCap data processing
- Market trend analysis
- Automated reporting

### 6. Background Processing
- Scheduled task management
- Event-driven processing
- Multi-threaded task execution
- Failure recovery and retry logic

## Installation

### 1. Clone the Repository

```bash
git clone [repository-url]
cd aibtcdev-backend
git submodule init
git submodule update --remote
```

### 2. Environment Setup

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Configure your environment variables by following the [Configuration Guide](CONFIG.md)

### 3. Development Setup (Conda Recommended)

```bash
# Install Miniconda
brew install miniconda

# Initialize conda
conda init "$(basename "${SHELL}")"
# Restart your terminal

# Create and activate environment
conda create --name aibackend python=3.12
conda activate aibackend

# Install dependencies
pip install -r requirements.txt

# Set up TypeScript tools
cd agent-tools-ts/
bun install
cd ..
```

### 4. Docker Setup

```bash
docker build -t aibtcdev-backend .
docker run -p 8000:8000 --env-file .env aibtcdev-backend
```

## API Documentation

### WebSocket Endpoints (`/chat`)
- `/chat/ws`: Real-time chat communication
  - Supports message history
  - AI agent integration
  - Context management
  - Document processing

### Tool Endpoints (`/tools`)
- `/tools/available`: Available tool listing
- `/tools/execute`: Tool execution endpoint
- Custom tool integration support

### Webhook Endpoints (`/webhooks`)
- `/webhooks/chainhook`: Blockchain event processing
- `/webhooks/github`: GitHub integration
- `/webhooks/discord`: Discord notifications

### Bot Endpoints (`/bot`)
- `/bot/telegram`: Telegram bot integration
- User verification and management
- Command processing

## Development

### Running the Development Server

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Code Style

The project uses ruff for code formatting and linting. Configuration is in `ruff.toml`.

### Testing

```bash
pytest tests/
```

### Documentation

API documentation is available at `/docs` when running the server.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

Guidelines:
- Follow the Python code style guide
- Add tests for new features
- Update documentation as needed
- Keep pull requests focused and atomic

## Troubleshooting

### Common Issues

1. OpenAI Rate Limits
   - Check limits at https://platform.openai.com/settings/organization/limits
   - TPM (Tokens Per Minute) limits:
     - Tier 1: 200,000 TPM
     - Tier 2: 2,000,000 TPM

2. WebSocket Connection Issues
   - Check network connectivity
   - Verify authentication tokens
   - Check server logs for details

3. Database Connection Issues
   - Verify Supabase credentials
   - Check network access to database
   - Verify connection string format

## Support

For support:
1. Check the documentation
2. Search existing issues
3. Create a new issue with:
   - Clear description
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details

## License

[License Information]
