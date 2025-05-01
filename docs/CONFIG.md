# Configuration Guide

This document details all configuration options for the aibtcdev-backend service. All configuration is loaded from environment variables.

## Quick Start

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Configure the environment variables according to the sections below.

## Configuration Components

### Database Configuration (DatabaseConfig)
- `AIBTC_BACKEND`: Database backend type (default: "supabase")
- `AIBTC_SUPABASE_USER`: Supabase user
- `AIBTC_SUPABASE_PASSWORD`: Supabase password
- `AIBTC_SUPABASE_HOST`: Database host
- `AIBTC_SUPABASE_PORT`: Database port
- `AIBTC_SUPABASE_DBNAME`: Database name
- `AIBTC_SUPABASE_URL`: Supabase project URL
- `AIBTC_SUPABASE_SERVICE_KEY`: Supabase service key
- `AIBTC_SUPABASE_BUCKET_NAME`: Storage bucket name

### Twitter Configuration (TwitterConfig)
- `AIBTC_TWITTER_ENABLED`: Enable Twitter integration (true/false)
- `AIBTC_TWITTER_INTERVAL_SECONDS`: Interval for Twitter operations (default: 120)
- `AIBTC_TWITTER_CONSUMER_KEY`: Twitter API consumer key
- `AIBTC_TWITTER_CONSUMER_SECRET`: Twitter API consumer secret
- `AIBTC_TWITTER_CLIENT_ID`: Twitter client ID
- `AIBTC_TWITTER_CLIENT_SECRET`: Twitter client secret
- `AIBTC_TWITTER_ACCESS_TOKEN`: Twitter access token
- `AIBTC_TWITTER_ACCESS_SECRET`: Twitter access secret
- `AIBTC_TWITTER_AUTOMATED_USER_ID`: Automated Twitter user ID
- `AIBTC_TWITTER_WHITELISTED`: Comma-separated list of whitelisted authors

### Telegram Configuration (TelegramConfig)
- `AIBTC_TELEGRAM_BOT_TOKEN`: Telegram bot token
- `AIBTC_TELEGRAM_BOT_ENABLED`: Enable Telegram bot (true/false)

### Discord Configuration (DiscordConfig)
- `AIBTC_DISCORD_WEBHOOK_URL`: Discord webhook URL for notifications

### API Configuration (APIConfig)
- `AIBTC_ALEX_BASE_URL`: Alex API base URL (default: "https://api.alexgo.io/")
- `AIBTC_HIRO_API_URL`: Hiro API URL (default: "https://api.hiro.so")
- `AIBTC_PLATFORM_API_URL`: Platform API URL
- `AIBTC_VELAR_BASE_URL`: Velar network gateway URL
- `AIBTC_LUNARCRUSH_BASE_URL`: LunarCrush API base URL
- `HIRO_API_KEY`: Hiro API key
- `AIBTC_WEBHOOK_URL`: Webhook URL for notifications
- `AIBTC_WEBHOOK_AUTH_TOKEN`: Webhook authentication token
- `AIBTC_LUNARCRUSH_API_KEY`: LunarCrush API key
- `AIBTC_CMC_API_KEY`: CoinMarketCap API key
- `OPENAI_API_KEY`: OpenAI API key

### Network Configuration (NetworkConfig)
- `NETWORK`: Network type (testnet/mainnet)

### Scheduler Configuration (SchedulerConfig)

The application includes several background task runners that can be configured:

#### Schedule Sync Runner
- `AIBTC_SCHEDULE_SYNC_ENABLED`: Enable schedule sync (true/false)
- `AIBTC_SCHEDULE_SYNC_INTERVAL_SECONDS`: Sync interval in seconds (default: 60)

#### DAO Runners
- `AIBTC_DAO_RUNNER_ENABLED`: Enable DAO processing (true/false)
- `AIBTC_DAO_RUNNER_INTERVAL_SECONDS`: Processing interval (default: 30)
- `AIBTC_DAO_TWEET_RUNNER_ENABLED`: Enable DAO tweet generation (true/false)
- `AIBTC_DAO_TWEET_RUNNER_INTERVAL_SECONDS`: Tweet generation interval (default: 30)
- `AIBTC_DAO_PROPOSAL_VOTE_RUNNER_ENABLED`: Enable proposal vote processing (true/false)
- `AIBTC_DAO_PROPOSAL_VOTE_RUNNER_INTERVAL_SECONDS`: Vote processing interval (default: 60)
- `AIBTC_DAO_PROPOSAL_CONCLUDE_RUNNER_ENABLED`: Enable proposal conclusion processing (true/false)
- `AIBTC_DAO_PROPOSAL_CONCLUDE_RUNNER_INTERVAL_SECONDS`: Conclusion processing interval (default: 60)
- `AIBTC_DAO_PROPOSAL_CONCLUDE_RUNNER_WALLET_ID`: Wallet ID for conclusion processing

#### Agent Account Runner
- `AIBTC_AGENT_ACCOUNT_DEPLOY_RUNNER_ENABLED`: Enable agent account deployment (true/false)
- `AIBTC_AGENT_ACCOUNT_DEPLOY_RUNNER_INTERVAL_SECONDS`: Deployment interval (default: 60)
- `AIBTC_AGENT_ACCOUNT_DEPLOY_RUNNER_WALLET_ID`: Wallet ID for deployments

#### Tweet Runner
- `AIBTC_TWEET_RUNNER_ENABLED`: Enable tweet processing (true/false)
- `AIBTC_TWEET_RUNNER_INTERVAL_SECONDS`: Processing interval (default: 30)

## Example Configurations

### DAO Processing Configuration
```env
AIBTC_DAO_RUNNER_ENABLED=true
AIBTC_DAO_RUNNER_INTERVAL_SECONDS=30
AIBTC_DAO_TWEET_RUNNER_ENABLED=true
AIBTC_DAO_TWEET_RUNNER_INTERVAL_SECONDS=30
```

### Agent Account Deployment
```env
AIBTC_AGENT_ACCOUNT_DEPLOY_RUNNER_ENABLED=false
AIBTC_AGENT_ACCOUNT_DEPLOY_RUNNER_INTERVAL_SECONDS=60
AIBTC_AGENT_ACCOUNT_DEPLOY_RUNNER_WALLET_ID="your-wallet-id"
```

### Social Media Integration
```env
AIBTC_TWITTER_ENABLED=true
AIBTC_TWITTER_INTERVAL_SECONDS=120
AIBTC_TELEGRAM_BOT_ENABLED=true
```

## Security Considerations

1. API Keys and Secrets
   - Never commit API keys or secrets to version control
   - Use environment variables for all sensitive data
   - Rotate keys regularly
   - Use appropriate access scopes

2. Network Configuration
   - Use HTTPS for all external API communications
   - Configure appropriate CORS settings
   - Use secure WebSocket connections (WSS)

3. Database Security
   - Use strong passwords
   - Limit database user permissions
   - Enable SSL for database connections
   - Regular backup configuration

## Troubleshooting

### Common Configuration Issues

1. Database Connection
   - Verify all database credentials are correct
   - Check network access to database
   - Verify SSL requirements

2. API Integration
   - Validate API keys and tokens
   - Check API rate limits
   - Verify endpoint URLs

3. Background Tasks
   - Check runner enabled flags
   - Verify interval settings
   - Monitor task execution logs

## Maintenance

1. Regular Tasks
   - Monitor API usage and rate limits
   - Check log files for errors
   - Review and rotate API keys
   - Update configuration as needed

2. Backup Configuration
   - Regular database backups
   - Configuration backup
   - Key rotation schedule 