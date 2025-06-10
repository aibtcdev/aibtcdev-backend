# aibtcdev-backend

[![standard-readme compliant](https://img.shields.io/badge/readme%20style-standard-brightgreen.svg?style=flat-square)](https://github.com/RichardLitt/standard-readme)

> A sophisticated FastAPI-based backend service that powers AI-driven interactions with Bitcoin and Stacks blockchain technologies.

aibtcdev-backend provides real-time chat functionality with AI agents, automated DAO management, social media integration, blockchain interaction capabilities, market data analysis, and document processing with vector search.

**⚠️ Disclaimer**: aibtc.dev is not liable for any lost, locked, or mistakenly sent funds. This is alpha software—use at your own risk. Any STX sent to you is owned by you, the trader, and may be redeemed, including profits or losses, at the end of the aibtc.dev Champions Sprint (~5 days). By participating, you accept that aibtc.dev is not responsible for any product use, costs, taxes incurred from trading STX or any other digital asset, or any other liability.

## Table of Contents

- [Background](#background)
- [Install](#install)
- [Usage](#usage)
- [Maintainers](#maintainers)
- [Contributing](#contributing)
- [License](#license)

## Background

aibtcdev-backend was created to bridge AI capabilities with blockchain technologies, specifically Bitcoin and Stacks. The system is designed to be modular, scalable, and easily configurable through environment variables.

### Key Features

- **AI Chat System**: Real-time WebSocket-based chat with AI agent integration, context-aware conversations, and vector search capabilities
- **DAO Management**: Automated DAO deployment monitoring, proposal creation and tracking, vote processing, and automated conclusion handling
- **Social Media Integration**: Twitter automation with automatic threading for tweets longer than 280 characters, Telegram bot integration, and Discord notifications
- **Blockchain Integration**: Stacks blockchain interaction, Bitcoin network monitoring, and multiple API integrations (Hiro, Alex, Velar, Platform API)
- **Market Analysis**: LunarCrush integration, CoinMarketCap data processing, and automated reporting
- **Background Processing**: Scheduled task management, event-driven processing, and multi-threaded task execution


## Install

### Prerequisites

- Python 3.13
- [Bun](https://bun.sh/) (for TypeScript tools)
- Git
- Conda (recommended for development) or Docker
- Node.js and npm (for agent tools)

### Development Setup

```bash
# Clone the repository
git clone [repository-url]
cd aibtcdev-backend
git submodule init
git submodule update --remote

# Copy environment file
cp .env.example .env
# Configure your environment variables by following the Configuration Guide

# Install UV (modern Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
# Or on macOS: brew install uv

# Create virtual environment and install dependencies
uv sync

# Activate the virtual environment
source .venv/bin/activate

# Set up TypeScript tools
cd agent-tools-ts/
bun install
cd ..
```

### Docker Setup

```bash
docker build -t aibtcdev-backend .
docker run -p 8000:8000 --env-file .env aibtcdev-backend
```

## Usage

### Running the Development Server

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The server will be available at `http://localhost:8000` with API documentation at `/docs`.

### Testing

```bash
pytest tests/
```

### Code Style

The project uses ruff for code formatting and linting. Configuration is in `ruff.toml`.

```bash
ruff check .
ruff format .
```

### Troubleshooting

**OpenAI Rate Limits**
- Check limits at https://platform.openai.com/settings/organization/limits
- TPM (Tokens Per Minute) limits: Tier 1: 200,000 TPM, Tier 2: 2,000,000 TPM

**WebSocket Connection Issues**
- Check network connectivity and authentication tokens
- Verify server logs for details

**Database Connection Issues**
- Verify Supabase credentials and network access
- Check connection string format

## Maintainers

[@aibtcdev](https://github.com/aibtcdev)

## Contributing

PRs accepted.

### Guidelines

- Follow the Python code style guide
- Add tests for new features
- Update documentation as needed
- Keep pull requests focused and atomic

### Development Process

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## License

[MIT](LICENSE) aibtcdev
