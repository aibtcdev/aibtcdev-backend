# aibtcdev-backend

## Overview

aibtcdev-backend is a FastAPI-based backend service that provides API endpoints for chat functionality, tools, and webhooks. It integrates with various external services including OpenAI, Twitter, Telegram, and blockchain-related APIs.

## Disclaimer

aibtc.dev is not liable for any lost, locked, or mistakenly sent funds. This is alpha software—use at your own risk. Any STX sent to you is owned by you, the trader, and may be redeemed, including profits or losses, at the end of the aibtc.dev Champions Sprint (~5 days). By participating, you accept that aibtc.dev is not responsible for any product use, costs, taxes incurred from trading STX or any other digital asset, or any other liability.

## Prerequisites

- Python 3.12
- [Bun](https://bun.sh/) (for running TypeScript scripts)
- Git
- Conda (recommended for development) or Docker

## Features

- FastAPI-based REST API
- WebSocket support for real-time communication
- Integration with multiple external services:
  - Supabase for database and storage
  - OpenAI for AI capabilities
  - Twitter API for social media integration
  - Telegram Bot API
  - Blockchain APIs (Hiro, Alex)
  - Market data APIs (LunarCrush, CMC)
- Background task scheduling system
- CORS support for multiple frontend environments
- Comprehensive logging system

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

2. Configure the following key sections in your `.env` file:
- Core Application Settings
- Database Configuration (Supabase)
- External API Endpoints & Keys
- Task Scheduling Configuration
- Social Media Integration
- Additional Tools & Services

### 3. Development Setup (Conda Recommended)

1. Install Miniconda:
```bash
# On macOS
brew install miniconda

# Initialize conda
conda init "$(basename "${SHELL}")"
# Restart your terminal
```

2. Create and activate the environment:
```bash
conda create --name aibackend python=3.12
conda activate aibackend
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up TypeScript tools:
```bash
cd agent-tools-ts/
bun install
cd ..
```

### 4. Alternative: Docker Setup

```bash
docker build -t aibtcdev-backend .
docker run -p 8000:8000 --env-file .env aibtcdev-backend
```

## API Endpoints

The service exposes the following endpoints:

### Chat Endpoints (`/chat`)
- `/chat/ws` - WebSocket endpoint for real-time chat communication
  - Supports message history retrieval
  - Real-time message processing
  - Supports agent-based conversations
  - Maintains thread-based chat history

### Tools Endpoints (`/tools`)
- `/tools/available` - Get list of available tools and their descriptions
  - Returns tool information including:
    - Tool ID and name
    - Description
    - Category
    - Required parameters

### Webhook Endpoints (`/webhooks`)
- `/webhooks/chainhook` - Handle blockchain-related webhook events
- `/webhooks/github` - Process GitHub webhook events

### Bot Endpoints (`/bot`)
- `/bot/telegram/test` - Test Telegram bot integration
  - Send test messages to verified users
  - Requires user profile verification

All endpoints require proper authentication and most endpoints use profile verification middleware to ensure secure access to the API.

For detailed API documentation including request/response schemas, visit `/docs` when running the server.

## Configuration

The application uses a hierarchical configuration system defined in `config.py`, including:

- DatabaseConfig: Supabase connection settings
- TwitterConfig: Twitter API integration settings
- TelegramConfig: Telegram bot settings
- SchedulerConfig: Background task scheduling
- APIConfig: External API endpoints and keys
- NetworkConfig: Network-specific settings

## Development

### Running the Development Server

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Background Tasks

The application includes several background tasks that can be enabled/disabled via environment variables:
- Schedule synchronization
- DAO processing pipeline
- Tweet generation and posting
- Social media integration tasks

## Contributing

1. Branch protection is enabled on `main`
2. Auto-deployment is configured for updates
3. Pull requests require one approval
4. Please ensure all tests pass before submitting a PR

## Troubleshooting

### OpenAI Rate Limits
- Check your current tier limits at https://platform.openai.com/settings/organization/limits
- TPM (Tokens Per Minute) limits:
  - Tier 1: 200,000 TPM
  - Tier 2: 2,000,000 TPM

## License

[License Information]

## Support

[Support Information]
