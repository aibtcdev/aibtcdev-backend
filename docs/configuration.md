# Configuration Documentation

This document provides comprehensive information about configuring aibtcdev-backend for different environments and use cases.

## Table of Contents

- [Overview](#overview)
- [Environment Variables](#environment-variables)
- [Network Configuration](#network-configuration)
- [Database Configuration](#database-configuration)
- [AI Service Configuration](#ai-service-configuration)
- [Blockchain Configuration](#blockchain-configuration)
- [Authentication Configuration](#authentication-configuration)
- [Integration Configuration](#integration-configuration)
- [Development Configuration](#development-configuration)
- [Production Configuration](#production-configuration)
- [Security Considerations](#security-considerations)
- [Configuration Validation](#configuration-validation)
- [Troubleshooting](#troubleshooting)

## Overview

aibtcdev-backend uses environment variables for configuration, allowing easy deployment across different environments without code changes. The configuration system is designed to be:

- **Environment-specific**: Different settings for development, staging, and production
- **Secure**: Sensitive data stored in environment variables
- **Flexible**: Optional integrations can be enabled/disabled
- **Validated**: Configuration is validated at startup

## Environment Variables

### Core Configuration

Create a `.env` file in the project root:

```bash
# Network Configuration
AIBTC_NETWORK=testnet                    # Network mode: testnet or mainnet

# Database Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key

# AI Configuration
OPENAI_API_KEY=sk-your_openai_api_key

# Authentication
AIBTC_WEBHOOK_AUTH_TOKEN=Bearer your_webhook_secret_token

# Optional: CORS Configuration
AIBTC_CORS_ORIGINS=http://localhost:3000,https://app.aibtc.dev
```

### Environment Variable Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AIBTC_NETWORK` | Yes | `testnet` | Blockchain network (testnet/mainnet) |
| `SUPABASE_URL` | Yes | - | Supabase project URL |
| `SUPABASE_KEY` | Yes | - | Supabase anonymous key |
| `OPENAI_API_KEY` | Yes | - | OpenAI API key for AI features |
| `AIBTC_WEBHOOK_AUTH_TOKEN` | Yes | - | Authentication token for webhooks |
| `AIBTC_CORS_ORIGINS` | No | `*` | Allowed CORS origins (comma-separated) |
| `LOG_LEVEL` | No | `INFO` | Logging level (DEBUG/INFO/WARNING/ERROR) |
| `DEBUG` | No | `false` | Enable debug mode |

## Network Configuration

### Testnet Configuration

For development and testing:

```bash
# Network
AIBTC_NETWORK=testnet

# Blockchain APIs
STACKS_API_URL=https://api.testnet.hiro.so
BITCOIN_API_URL=https://blockstream.info/testnet/api

# Testnet-specific settings
ENABLE_FAUCETS=true
TESTNET_ONLY_FEATURES=true
```

**Features available in testnet**:
- STX faucet integration
- sBTC faucet integration
- Reduced transaction fees
- Faster block times
- Test token contracts

### Mainnet Configuration

For production deployment:

```bash
# Network
AIBTC_NETWORK=mainnet

# Blockchain APIs
STACKS_API_URL=https://api.hiro.so
BITCOIN_API_URL=https://blockstream.info/api

# Mainnet-specific settings
ENABLE_FAUCETS=false
TESTNET_ONLY_FEATURES=false
MAINNET_SAFETY_CHECKS=true
```

**Important mainnet considerations**:
- Real money transactions
- Higher transaction fees
- Longer confirmation times
- Production contract addresses
- Enhanced security validations

## Database Configuration

### Supabase Setup

1. **Create Supabase Project**:
   - Go to [supabase.com](https://supabase.com)
   - Create new project
   - Note the project URL and anon key

2. **Configure Database Access**:
```bash
# Required Supabase settings
SUPABASE_URL=https://abcdefghijklmnop.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9... # Optional for admin operations
```

3. **Database Schema**:
   - Tables are managed through the backend abstraction
   - Schema migrations handled automatically
   - Row Level Security (RLS) enabled for data protection

### Connection Pool Configuration

```bash
# Optional database tuning
DB_POOL_SIZE=10                  # Connection pool size
DB_POOL_TIMEOUT=30               # Connection timeout (seconds)
DB_RETRY_ATTEMPTS=3              # Number of retry attempts
DB_RETRY_DELAY=1                 # Delay between retries (seconds)
```

### Local Development Database

For local development with Supabase CLI:

```bash
# Start local Supabase
supabase start

# Use local configuration
SUPABASE_URL=http://localhost:54321
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9... # Local anon key
```

## AI Service Configuration

### OpenAI Configuration

```bash
# Required OpenAI settings
OPENAI_API_KEY=sk-your_openai_api_key_here
OPENAI_ORGANIZATION=org-your_organization_id    # Optional

# Model configuration
OPENAI_DEFAULT_MODEL=gpt-4.1                   # Default model for AI operations
OPENAI_TEMPERATURE=0.1                         # Default temperature
OPENAI_MAX_TOKENS=4000                         # Maximum tokens per request

# Rate limiting
OPENAI_REQUESTS_PER_MINUTE=60                  # Adjust based on your tier
OPENAI_TOKENS_PER_MINUTE=200000               # Adjust based on your tier
```

### AI Model Configuration

```bash
# Model-specific settings
GPT4_MODEL=gpt-4.1                            # GPT-4 model version
GPT35_MODEL=gpt-3.5-turbo                     # GPT-3.5 model version
EMBEDDING_MODEL=text-embedding-ada-002        # Embedding model

# AI behavior tuning
AI_SYSTEM_PROMPT_OVERRIDE=""                  # Override default system prompts
AI_ENABLE_STREAMING=true                      # Enable streaming responses
AI_RESPONSE_TIMEOUT=300                       # AI response timeout (seconds)
```

### AI Feature Toggles

```bash
# Enable/disable AI features
ENABLE_PROPOSAL_RECOMMENDATIONS=true
ENABLE_COMPREHENSIVE_EVALUATION=true
ENABLE_AI_METADATA_GENERATION=true
ENABLE_AI_CONTENT_ENHANCEMENT=true
```

## Blockchain Configuration

### Stacks Blockchain

```bash
# Stacks API configuration
STACKS_API_URL=https://api.testnet.hiro.so    # Testnet
# STACKS_API_URL=https://api.hiro.so          # Mainnet

STACKS_API_KEY=your_hiro_api_key              # Optional, for higher rate limits
STACKS_NETWORK_ID=testnet                     # testnet or mainnet

# Transaction configuration
STACKS_DEFAULT_FEE=1000                       # Default transaction fee (micro-STX)
STACKS_CONFIRMATION_BLOCKS=1                  # Blocks to wait for confirmation
STACKS_BROADCAST_TIMEOUT=60                   # Transaction broadcast timeout
```

### Bitcoin Configuration

```bash
# Bitcoin API configuration
BITCOIN_API_URL=https://blockstream.info/testnet/api  # Testnet
# BITCOIN_API_URL=https://blockstream.info/api        # Mainnet

BITCOIN_NETWORK=testnet                       # testnet or mainnet
BITCOIN_API_TIMEOUT=30                        # API request timeout
```

### DEX Configuration (Faktory)

```bash
# Faktory DEX settings
FAKTORY_API_URL=https://api.faktory.com
FAKTORY_DEFAULT_SLIPPAGE=15                   # Default slippage (basis points)
FAKTORY_MAX_SLIPPAGE=500                      # Maximum allowed slippage
FAKTORY_API_TIMEOUT=30                        # API timeout
```

## Authentication Configuration

### Session Configuration

```bash
# JWT/Session configuration
JWT_SECRET_KEY=your-super-secret-jwt-key      # Keep this secret!
JWT_EXPIRATION_HOURS=24                       # Token expiration time
JWT_ALGORITHM=HS256                           # JWT signing algorithm

# API Key configuration
API_KEY_EXPIRATION_DAYS=365                   # API key default expiration
API_KEY_RATE_LIMIT=1000                       # Requests per hour per key
```

### Webhook Authentication

```bash
# Webhook security
AIBTC_WEBHOOK_AUTH_TOKEN=Bearer your_very_secret_webhook_token

# Additional webhook security
WEBHOOK_IP_WHITELIST=127.0.0.1,::1           # Allowed IP addresses
WEBHOOK_TIMEOUT=30                            # Request timeout
```

### CORS Configuration

```bash
# CORS settings for web clients
AIBTC_CORS_ORIGINS=http://localhost:3000,https://app.aibtc.dev
AIBTC_CORS_ALLOW_CREDENTIALS=true
AIBTC_CORS_ALLOW_METHODS=GET,POST,PUT,DELETE,OPTIONS
AIBTC_CORS_ALLOW_HEADERS=*
```

## Integration Configuration

### Telegram Bot

```bash
# Telegram integration (optional)
TELEGRAM_BOT_TOKEN=1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijk
TELEGRAM_CHAT_ID=-1001234567890               # Target chat/channel ID
TELEGRAM_ENABLE_NOTIFICATIONS=true            # Enable notifications
TELEGRAM_API_TIMEOUT=30                       # API timeout
```

### Twitter/X Integration

```bash
# Twitter integration (optional)
TWITTER_API_KEY=your_twitter_api_key
TWITTER_API_SECRET=your_twitter_api_secret
TWITTER_ACCESS_TOKEN=your_access_token
TWITTER_ACCESS_TOKEN_SECRET=your_access_token_secret
TWITTER_BEARER_TOKEN=your_bearer_token

# Twitter features
ENABLE_TWITTER_EMBEDS=true                    # Enable tweet embedding
TWITTER_OEMBED_TIMEOUT=10                     # oEmbed API timeout
```

### Discord Integration

```bash
# Discord integration (optional)
DISCORD_BOT_TOKEN=your_discord_bot_token
DISCORD_GUILD_ID=your_guild_id
DISCORD_CHANNEL_ID=your_channel_id
ENABLE_DISCORD_NOTIFICATIONS=true
```

### Email Configuration

```bash
# Email service (optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
SMTP_USE_TLS=true
EMAIL_FROM=noreply@aibtc.dev
```

## Development Configuration

### Complete Development `.env` Example

```bash
# Development environment
DEBUG=true
LOG_LEVEL=DEBUG
AIBTC_NETWORK=testnet

# Database (local Supabase)
SUPABASE_URL=http://localhost:54321
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# AI services
OPENAI_API_KEY=sk-your_dev_openai_key
OPENAI_DEFAULT_MODEL=gpt-3.5-turbo            # Cheaper for development

# Local development
AIBTC_CORS_ORIGINS=http://localhost:3000,http://localhost:3001
ENABLE_HOT_RELOAD=true
DISABLE_AUTH_FOR_TESTING=false               # Only in development!

# Blockchain (testnet)
STACKS_API_URL=https://api.testnet.hiro.so
BITCOIN_API_URL=https://blockstream.info/testnet/api

# Authentication
AIBTC_WEBHOOK_AUTH_TOKEN=Bearer dev_webhook_token_123
JWT_SECRET_KEY=dev-secret-key-change-in-production

# Development features
ENABLE_FAUCETS=true
ENABLE_DEBUG_ENDPOINTS=true
MOCK_EXTERNAL_APIS=false                      # Set to true to mock APIs
```

### Development-Specific Settings

```bash
# Development helpers
ENABLE_ADMIN_ENDPOINTS=true                   # Admin-only endpoints
LOG_SQL_QUERIES=true                          # Log database queries
PROFILE_PERFORMANCE=true                      # Enable performance profiling
AUTO_RELOAD_ON_CHANGE=true                    # Auto-reload on file changes

# Testing configuration
TEST_DATABASE_URL=postgresql://localhost/aibtc_test
PYTEST_TIMEOUT=300                            # Test timeout
ENABLE_INTEGRATION_TESTS=true
```

## Production Configuration

### Complete Production `.env` Example

```bash
# Production environment
DEBUG=false
LOG_LEVEL=INFO
AIBTC_NETWORK=mainnet

# Database (production Supabase)
SUPABASE_URL=https://your-prod-project.supabase.co
SUPABASE_KEY=your_production_supabase_key

# AI services
OPENAI_API_KEY=sk-your_production_openai_key
OPENAI_DEFAULT_MODEL=gpt-4.1
OPENAI_ORGANIZATION=org-your_production_org

# Production domain
AIBTC_CORS_ORIGINS=https://app.aibtc.dev,https://aibtc.dev

# Blockchain (mainnet)
STACKS_API_URL=https://api.hiro.so
BITCOIN_API_URL=https://blockstream.info/api
STACKS_API_KEY=your_production_hiro_api_key

# Security
AIBTC_WEBHOOK_AUTH_TOKEN=Bearer super_secret_production_webhook_token
JWT_SECRET_KEY=ultra_secure_production_jwt_secret_minimum_32_chars

# Production optimizations
CONNECTION_POOL_SIZE=20
ENABLE_CACHING=true
CACHE_TTL=300
RATE_LIMIT_ENABLED=true
```

### Production Security Settings

```bash
# Security hardening
FORCE_HTTPS=true
SECURE_COOKIES=true
HSTS_MAX_AGE=31536000
CONTENT_SECURITY_POLICY=strict

# Rate limiting
RATE_LIMIT_PER_MINUTE=100
RATE_LIMIT_PER_HOUR=6000
RATE_LIMIT_PER_DAY=144000

# Monitoring
ENABLE_METRICS=true
METRICS_PORT=9090
HEALTH_CHECK_INTERVAL=30
```

## Security Considerations

### Sensitive Data Management

**Never commit sensitive data to version control:**

```bash
# Good: Using environment variables
OPENAI_API_KEY=sk-your_key_here

# Bad: Hardcoded in source code
api_key = "sk-your_key_here"  # DON'T DO THIS
```

### Environment Variable Security

```bash
# Use proper file permissions
chmod 600 .env

# Use encrypted environment storage in production
# AWS Secrets Manager, HashiCorp Vault, etc.

# Rotate secrets regularly
OPENAI_API_KEY=sk-new_rotated_key
JWT_SECRET_KEY=new_jwt_secret_after_rotation
```

### Production Security Checklist

- [ ] All secrets stored in secure environment variables
- [ ] HTTPS enforced (`FORCE_HTTPS=true`)
- [ ] CORS properly configured (no wildcards)
- [ ] Rate limiting enabled
- [ ] Webhook tokens are cryptographically secure
- [ ] JWT secrets are at least 32 characters
- [ ] Database credentials secured
- [ ] Monitoring and alerting configured
- [ ] Regular security audits scheduled

## Configuration Validation

### Startup Validation

The application validates configuration at startup:

```python
# Configuration is automatically validated
from app.config import config

# This will raise an error if required variables are missing
print(f"Running on {config.network.network} network")
```

### Manual Validation

```bash
# Check configuration
python -c "
from app.config import config
print('✓ Configuration loaded successfully')
print(f'Network: {config.network.network}')
print(f'Database: {config.database.url[:50]}...')
print(f'AI Service: OpenAI configured')
"
```

### Configuration Testing

```bash
# Test database connection
python -c "
from app.backend.factory import backend
profiles = backend.list_profiles()
print(f'✓ Database connected, found {len(profiles)} profiles')
"

# Test AI service
python -c "
import openai
models = openai.models.list()
print('✓ OpenAI service connected')
"

# Test blockchain APIs
curl -s https://api.testnet.hiro.so/v2/info | jq '.stacks_tip_height'
```

## Troubleshooting

### Common Configuration Issues

**Missing Environment Variables**:
```bash
# Error: Required environment variable missing
ERROR: Environment variable 'OPENAI_API_KEY' is required

# Solution: Check .env file
grep OPENAI_API_KEY .env
```

**Database Connection Issues**:
```bash
# Error: Database connection failed
ERROR: Could not connect to Supabase

# Debug steps:
1. Check SUPABASE_URL format
2. Verify SUPABASE_KEY is correct
3. Test network connectivity
4. Check Supabase project status
```

**CORS Issues**:
```bash
# Error: CORS policy blocks request
ERROR: Access to fetch blocked by CORS policy

# Solution: Update CORS configuration
AIBTC_CORS_ORIGINS=http://localhost:3000,https://yourdomain.com
```

**Authentication Errors**:
```bash
# Error: Invalid webhook token
ERROR: Invalid authentication token

# Solution: Check token format
AIBTC_WEBHOOK_AUTH_TOKEN=Bearer your_secret_token
# Must include "Bearer " prefix
```

### Environment Debugging

```bash
# Check all environment variables
printenv | grep AIBTC
printenv | grep SUPABASE
printenv | grep OPENAI

# Verify .env file loading
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
print('Environment variables loaded:')
for key in os.environ:
    if key.startswith(('AIBTC_', 'SUPABASE_', 'OPENAI_')):
        print(f'{key}={os.environ[key][:20]}...')
"
```

### Configuration Validation Script

Create `scripts/validate_config.py`:

```python
#!/usr/bin/env python3
"""Configuration validation script."""

import os
import sys
from app.config import config

def validate_config():
    """Validate all configuration settings."""
    errors = []
    
    # Required settings
    required = [
        'AIBTC_NETWORK',
        'SUPABASE_URL', 
        'SUPABASE_KEY',
        'OPENAI_API_KEY',
        'AIBTC_WEBHOOK_AUTH_TOKEN'
    ]
    
    for var in required:
        if not os.getenv(var):
            errors.append(f"Missing required variable: {var}")
    
    # Network validation
    if config.network.network not in ['testnet', 'mainnet']:
        errors.append("AIBTC_NETWORK must be 'testnet' or 'mainnet'")
    
    # URL validation
    if not config.database.url.startswith('http'):
        errors.append("SUPABASE_URL must be a valid HTTP URL")
    
    if errors:
        print("❌ Configuration validation failed:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    else:
        print("✅ Configuration validation passed")

if __name__ == "__main__":
    validate_config()
```

Run validation:
```bash
python scripts/validate_config.py
```

### Getting Help

If you encounter configuration issues:

1. **Check this documentation** for the specific setting
2. **Validate environment variables** using the validation script
3. **Check logs** for specific error messages
4. **Test individual components** (database, AI service, etc.)
5. **Create a minimal reproduction** with basic configuration
6. **Ask for help** with detailed error messages and configuration (without secrets)