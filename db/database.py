from abc import ABC, abstractmethod
from lib.models import (
    ProfileResponse,
    VerificationResponse,
    XBotAuthor,
    XBotLog,
    XBotTweet,
)
from typing import Any, Dict, List, Optional


class Database(ABC):
    @abstractmethod
    def get_detailed_conversation(self, conversation_id: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_collectives(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_collective(self, collective_id: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def update_collective(self, collective_id: str, data: dict) -> bool:
        pass

    @abstractmethod
    def add_collective(
        self, name: str, mission: str, description: str
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_capabilities(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_capability(self, capability_id: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def add_capability(
        self,
        collective_id: str,
        type: str,
        contract_principal: str,
        tx_id: str,
        status: str,
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    def update_capability(
        self,
        capability_id: str,
        data: dict,
    ) -> bool:
        pass

    @abstractmethod
    def add_schedule(
        self,
        profile_id: str,
        task: str,
        cron: str,
        enabled: bool,
    ) -> bool:
        pass

    @abstractmethod
    def get_tokens(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_token(
        self,
        token_id: str,
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    def add_token(
        self,
        name: str,
        symbol: str,
        decimals: int,
        description: str,
        max_supply: str,
        image_url: Optional[str] = None,
        uri: Optional[str] = None,
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    def update_token(self, token_id: str, data: dict) -> bool:
        pass

    @abstractmethod
    def add_job(
        self,
        profile_id: str,
        conversation_id: str,
        crew_id: str,
        input_data: Dict[str, Any],
        result: Dict[str, Any],
        tokens: int,
        messages: List[Dict[str, Any]],
    ) -> bool:
        pass

    @abstractmethod
    def get_enabled_crons_expanded() -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_enabled_crons() -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_telegram_user(self, telegram_user_id: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def update_telegram_user(self, telegram_user_id: str, user_data: dict) -> bool:
        pass

    @abstractmethod
    def get_telegram_user_by_username(self, username: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_all_registered_telegram_users(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_telegram_user_by_profile(self, profile_id: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_crew_agents(self, crew_id: int) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_crew_tasks(self, crew_id: int) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_conversation_history(self, conversation_id: str) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def verify_session_token(self, token: str) -> Optional[str]:
        pass

    @abstractmethod
    def get_profile(self, identifier: str) -> Dict[str, Any]:
        pass

    # Twitter Operations
    @abstractmethod
    def get_twitter_author(self, author_id: str) -> Optional[XBotAuthor]:
        pass

    @abstractmethod
    def create_twitter_author(
        self,
        author_id: str,
        username: Optional[str] = None,
        realname: Optional[str] = None,
    ) -> XBotAuthor:
        pass

    @abstractmethod
    def get_twitter_tweet(self, tweet_id: str) -> Optional[XBotTweet]:
        pass

    @abstractmethod
    def get_thread_tweets(self, thread_id: int) -> List[XBotTweet]:
        pass

    @abstractmethod
    def get_author_tweets(self, author_id: str) -> List[XBotTweet]:
        pass

    @abstractmethod
    def add_twitter_tweet(
        self,
        author_id: str,
        tweet_id: str,
        tweet_body: str,
        thread_id: Optional[int] = None,
    ) -> XBotTweet:
        pass

    @abstractmethod
    def get_twitter_logs(self, tweet_id: str) -> List[XBotLog]:
        pass

    @abstractmethod
    def add_twitter_log(
        self, tweet_id: str, status: str, message: Optional[str] = None
    ) -> XBotLog:
        pass

    @abstractmethod
    def upload_file(self, file_path: str, file: bytes) -> str:
        pass
