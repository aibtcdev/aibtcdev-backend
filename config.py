import os
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv

from lib.logger import configure_logger

logger = configure_logger(__name__)

load_dotenv()


@dataclass
class DatabaseConfig:
    backend: str = os.getenv("AIBTC_BACKEND", "supabase")
    user: str = os.getenv("AIBTC_SUPABASE_USER", "")
    password: str = os.getenv("AIBTC_SUPABASE_PASSWORD", "")
    host: str = os.getenv("AIBTC_SUPABASE_HOST", "")
    port: str = os.getenv("AIBTC_SUPABASE_PORT", "")
    dbname: str = os.getenv("AIBTC_SUPABASE_DBNAME", "")
    url: str = os.getenv("AIBTC_SUPABASE_URL", "")
    service_key: str = os.getenv("AIBTC_SUPABASE_SERVICE_KEY", "")
    bucket_name: str = os.getenv("AIBTC_SUPABASE_BUCKET_NAME", "")


@dataclass
class TwitterConfig:
    enabled: bool = os.getenv("AIBTC_TWITTER_ENABLED", "false").lower() == "true"
    interval_seconds: int = int(os.getenv("AIBTC_TWITTER_INTERVAL_SECONDS", "120"))
    consumer_key: str = os.getenv("AIBTC_TWITTER_CONSUMER_KEY", "")
    consumer_secret: str = os.getenv("AIBTC_TWITTER_CONSUMER_SECRET", "")
    client_id: str = os.getenv("AIBTC_TWITTER_CLIENT_ID", "")
    client_secret: str = os.getenv("AIBTC_TWITTER_CLIENT_SECRET", "")
    access_token: str = os.getenv("AIBTC_TWITTER_ACCESS_TOKEN", "")
    access_secret: str = os.getenv("AIBTC_TWITTER_ACCESS_SECRET", "")
    automated_user_id: str = os.getenv("AIBTC_TWITTER_AUTOMATED_USER_ID", "")
    whitelisted_authors: List[str] = field(
        default_factory=lambda: os.getenv("AIBTC_TWITTER_WHITELISTED", "").split(",")
    )


@dataclass
class TelegramConfig:
    token: str = os.getenv("AIBTC_TELEGRAM_BOT_TOKEN", "")
    enabled: bool = os.getenv("AIBTC_TELEGRAM_BOT_ENABLED", "false").lower() == "true"


@dataclass
class DiscordConfig:
    webhook_url_passed: str = os.getenv("AIBTC_DISCORD_WEBHOOK_URL_PASSED", "")
    webhook_url_failed: str = os.getenv("AIBTC_DISCORD_WEBHOOK_URL_FAILED", "")


@dataclass
class SchedulerConfig:
    sync_enabled: bool = (
        os.getenv("AIBTC_SCHEDULE_SYNC_ENABLED", "false").lower() == "true"
    )
    sync_interval_seconds: int = int(
        os.getenv("AIBTC_SCHEDULE_SYNC_INTERVAL_SECONDS", "60")
    )
    dao_runner_enabled: bool = (
        os.getenv("AIBTC_DAO_RUNNER_ENABLED", "false").lower() == "true"
    )
    dao_runner_interval_seconds: int = int(
        os.getenv("AIBTC_DAO_RUNNER_INTERVAL_SECONDS", "30")
    )
    dao_tweet_runner_enabled: bool = (
        os.getenv("AIBTC_DAO_TWEET_RUNNER_ENABLED", "false").lower() == "true"
    )
    dao_tweet_runner_interval_seconds: int = int(
        os.getenv("AIBTC_DAO_TWEET_RUNNER_INTERVAL_SECONDS", "30")
    )
    tweet_runner_enabled: bool = (
        os.getenv("AIBTC_TWEET_RUNNER_ENABLED", "false").lower() == "true"
    )
    tweet_runner_interval_seconds: int = int(
        os.getenv("AIBTC_TWEET_RUNNER_INTERVAL_SECONDS", "30")
    )
    discord_runner_enabled: bool = (
        os.getenv("AIBTC_DISCORD_RUNNER_ENABLED", "false").lower() == "true"
    )
    discord_runner_interval_seconds: int = int(
        os.getenv("AIBTC_DISCORD_RUNNER_INTERVAL_SECONDS", "30")
    )
    dao_proposal_vote_runner_enabled: bool = (
        os.getenv("AIBTC_DAO_PROPOSAL_VOTE_RUNNER_ENABLED", "false").lower() == "true"
    )
    dao_proposal_vote_runner_interval_seconds: int = int(
        os.getenv("AIBTC_DAO_PROPOSAL_VOTE_RUNNER_INTERVAL_SECONDS", "60")
    )
    dao_proposal_conclude_runner_enabled: bool = (
        os.getenv("AIBTC_DAO_PROPOSAL_CONCLUDE_RUNNER_ENABLED", "false").lower()
        == "true"
    )
    dao_proposal_conclude_runner_interval_seconds: int = int(
        os.getenv("AIBTC_DAO_PROPOSAL_CONCLUDE_RUNNER_INTERVAL_SECONDS", "60")
    )
    dao_proposal_conclude_runner_wallet_id: str = os.getenv(
        "AIBTC_DAO_PROPOSAL_CONCLUDE_RUNNER_WALLET_ID", ""
    )
    dao_proposal_evaluation_runner_enabled: bool = (
        os.getenv("AIBTC_DAO_PROPOSAL_EVALUATION_RUNNER_ENABLED", "false").lower()
        == "true"
    )
    dao_proposal_evaluation_runner_interval_seconds: int = int(
        os.getenv("AIBTC_DAO_PROPOSAL_EVALUATION_RUNNER_INTERVAL_SECONDS", "60")
    )
    agent_account_deploy_runner_enabled: bool = (
        os.getenv("AIBTC_AGENT_ACCOUNT_DEPLOY_RUNNER_ENABLED", "false").lower()
        == "true"
    )
    agent_account_deploy_runner_interval_seconds: int = int(
        os.getenv("AIBTC_AGENT_ACCOUNT_DEPLOY_RUNNER_INTERVAL_SECONDS", "60")
    )
    agent_account_deploy_runner_wallet_id: str = os.getenv(
        "AIBTC_AGENT_ACCOUNT_DEPLOY_RUNNER_WALLET_ID", ""
    )
    dao_proposal_vote_delay_blocks: int = int(
        os.getenv("AIBTC_DAO_PROPOSAL_VOTE_DELAY_BLOCKS", "2")
    )
    proposal_embedder_enabled: bool = (
        os.getenv("AIBTC_PROPOSAL_EMBEDDER_ENABLED", "false").lower() == "true"
    )
    proposal_embedder_interval_seconds: int = int(
        os.getenv(
            "AIBTC_PROPOSAL_EMBEDDER_INTERVAL_SECONDS", "300"
        )  # Default to 5 mins
    )
    chain_state_monitor_enabled: bool = (
        os.getenv("AIBTC_CHAIN_STATE_MONITOR_ENABLED", "true").lower() == "true"
    )
    chain_state_monitor_interval_seconds: int = int(
        os.getenv(
            "AIBTC_CHAIN_STATE_MONITOR_INTERVAL_SECONDS", "300"
        )  # Default to 5 mins
    )


@dataclass
class APIConfig:
    base_url: str = os.getenv("AIBTC_BASEURL", "https://app-staging.aibtc.dev")
    alex_base_url: str = os.getenv("AIBTC_ALEX_BASE_URL", "https://api.alexgo.io/")
    hiro_api_url: str = os.getenv("AIBTC_HIRO_API_URL", "https://api.hiro.so")
    platform_base_url: str = os.getenv(
        "AIBTC_PLATFORM_API_URL", "https://api.platform.hiro.so"
    )
    velar_base_url: str = os.getenv(
        "AIBTC_VELAR_BASE_URL", "https://gateway.velar.network/"
    )
    lunarcrush_base_url: str = os.getenv(
        "AIBTC_LUNARCRUSH_BASE_URL", "https://lunarcrush.com/api/v2"
    )
    hiro_api_key: str = os.getenv("HIRO_API_KEY", "")
    webhook_url: str = os.getenv("AIBTC_WEBHOOK_URL", "")
    webhook_auth: str = os.getenv("AIBTC_WEBHOOK_AUTH_TOKEN", "Bearer 1234567890")
    lunarcrush_api_key: str = os.getenv("AIBTC_LUNARCRUSH_API_KEY", "")
    cmc_api_key: str = os.getenv("AIBTC_CMC_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")


@dataclass
class NetworkConfig:
    network: str = os.getenv("NETWORK", "testnet")


@dataclass
class Config:
    db: DatabaseConfig = field(default_factory=DatabaseConfig)
    twitter: TwitterConfig = field(default_factory=TwitterConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    api: APIConfig = field(default_factory=APIConfig)
    network: NetworkConfig = field(default_factory=NetworkConfig)
    discord: DiscordConfig = field(default_factory=DiscordConfig)

    @classmethod
    def load(cls) -> "Config":
        """Load and validate configuration"""
        config = cls()
        logger.info("Configuration loaded successfully")
        return config


# Global configuration instance
config = Config.load()
