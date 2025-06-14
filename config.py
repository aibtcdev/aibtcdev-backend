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
    enabled: bool = os.getenv("AIBTC_TWITTER_ENABLED", "true").lower() == "true"
    interval_seconds: int = int(os.getenv("AIBTC_TWITTER_INTERVAL_SECONDS", "120"))
    consumer_key: str = os.getenv("AIBTC_TWITTER_CONSUMER_KEY", "")
    consumer_secret: str = os.getenv("AIBTC_TWITTER_CONSUMER_SECRET", "")
    client_id: str = os.getenv("AIBTC_TWITTER_CLIENT_ID", "")
    client_secret: str = os.getenv("AIBTC_TWITTER_CLIENT_SECRET", "")
    access_token: str = os.getenv("AIBTC_TWITTER_ACCESS_TOKEN", "")
    access_secret: str = os.getenv("AIBTC_TWITTER_ACCESS_SECRET", "")
    username: str = os.getenv("AIBTC_TWITTER_USERNAME", "")
    automated_user_id: str = os.getenv("AIBTC_TWITTER_AUTOMATED_USER_ID", "")
    whitelisted_authors: List[str] = field(
        default_factory=lambda: os.getenv("AIBTC_TWITTER_WHITELISTED", "").split(",")
    )


@dataclass
class BackendWalletConfig:
    """Configuration for backend wallet operations."""

    seed_phrase: str = os.getenv("AIBTC_BACKEND_WALLET_SEED_PHRASE", "")


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

    # Job-specific configurations matching job_type names exactly

    # agent_account_deployer job
    agent_account_deployer_enabled: bool = (
        os.getenv("AIBTC_AGENT_ACCOUNT_DEPLOYER_ENABLED", "true").lower() == "true"
    )
    agent_account_deployer_interval_seconds: int = int(
        os.getenv("AIBTC_AGENT_ACCOUNT_DEPLOYER_INTERVAL_SECONDS", "60")
    )

    # chain_state_monitor job
    chain_state_monitor_enabled: bool = (
        os.getenv("AIBTC_CHAIN_STATE_MONITOR_ENABLED", "true").lower() == "true"
    )
    chain_state_monitor_interval_seconds: int = int(
        os.getenv("AIBTC_CHAIN_STATE_MONITOR_INTERVAL_SECONDS", "300")
    )

    # dao_deployment job
    dao_deployment_enabled: bool = (
        os.getenv("AIBTC_DAO_DEPLOYMENT_ENABLED", "true").lower() == "true"
    )
    dao_deployment_interval_seconds: int = int(
        os.getenv("AIBTC_DAO_DEPLOYMENT_INTERVAL_SECONDS", "60")
    )

    # dao_deployment_tweet job
    dao_deployment_tweet_enabled: bool = (
        os.getenv("AIBTC_DAO_DEPLOYMENT_TWEET_ENABLED", "true").lower() == "true"
    )
    dao_deployment_tweet_interval_seconds: int = int(
        os.getenv("AIBTC_DAO_DEPLOYMENT_TWEET_INTERVAL_SECONDS", "60")
    )

    # dao_proposal_conclude job
    dao_proposal_conclude_enabled: bool = (
        os.getenv("AIBTC_DAO_PROPOSAL_CONCLUDE_ENABLED", "true").lower() == "true"
    )
    dao_proposal_conclude_interval_seconds: int = int(
        os.getenv("AIBTC_DAO_PROPOSAL_CONCLUDE_INTERVAL_SECONDS", "60")
    )

    # dao_proposal_embedder job
    dao_proposal_embedder_enabled: bool = (
        os.getenv("AIBTC_DAO_PROPOSAL_EMBEDDER_ENABLED", "true").lower() == "true"
    )
    dao_proposal_embedder_interval_seconds: int = int(
        os.getenv("AIBTC_DAO_PROPOSAL_EMBEDDER_INTERVAL_SECONDS", "300")
    )

    # dao_proposal_evaluation job
    dao_proposal_evaluation_enabled: bool = (
        os.getenv("AIBTC_DAO_PROPOSAL_EVALUATION_ENABLED", "true").lower() == "true"
    )
    dao_proposal_evaluation_interval_seconds: int = int(
        os.getenv("AIBTC_DAO_PROPOSAL_EVALUATION_INTERVAL_SECONDS", "60")
    )

    # dao_proposal_vote job
    dao_proposal_vote_enabled: bool = (
        os.getenv("AIBTC_DAO_PROPOSAL_VOTE_ENABLED", "true").lower() == "true"
    )
    dao_proposal_vote_interval_seconds: int = int(
        os.getenv("AIBTC_DAO_PROPOSAL_VOTE_INTERVAL_SECONDS", "60")
    )

    # discord job
    discord_enabled: bool = os.getenv("AIBTC_DISCORD_ENABLED", "true").lower() == "true"
    discord_interval_seconds: int = int(
        os.getenv("AIBTC_DISCORD_INTERVAL_SECONDS", "30")
    )

    # tweet job
    tweet_enabled: bool = os.getenv("AIBTC_TWEET_ENABLED", "true").lower() == "true"
    tweet_interval_seconds: int = int(os.getenv("AIBTC_TWEET_INTERVAL_SECONDS", "30"))


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
    backend_wallet: BackendWalletConfig = field(default_factory=BackendWalletConfig)

    @classmethod
    def load(cls) -> "Config":
        """Load and validate configuration"""
        config = cls()
        logger.info("Configuration loaded successfully")
        return config


# Global configuration instance
config = Config.load()
