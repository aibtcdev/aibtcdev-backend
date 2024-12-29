import json
from .database import Database
from lib.models import (
    ProfileResponse,
    VerificationResponse,
    XBotAuthor,
    XBotLog,
    XBotTweet,
)
from lib.services import ServicesClient
from typing import Any, Dict, List, Optional


class CloudflareDatabase(Database):

    def __init__(self, client: ServicesClient, **kwargs):
        super().__init__()
        self.client = client

    def get_detailed_conversation(self, conversation_id: str) -> Dict[str, Any]:
        jobs_response = self.client.database.get_crew_executions(conversation_id)
        if not jobs_response.executions:
            return {"conversation": conversation_id, "jobs": []}
        return {
            "conversation": conversation_id,
            "jobs": [
                job
                for job in jobs_response.executions
                if job["conversation_id"] == conversation_id
            ],
        }

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
        crew_execution = self.client.database.add_crew_execution(
            profile_id, crew_id, conversation_id, input_data
        )

        # Add crew execution steps
        for message in messages:
            self.client.database.create_execution_step(
                profile_id,
                crew_id,
                crew_execution["execution"]["id"],
                message["type"],
                json.dumps(message),
            )
        return True

    def get_telegram_user(self, telegram_user_id: str) -> Dict[str, Any]:
        return self.client.database.get_telegram_user(telegram_user_id)

    def update_telegram_user(self, telegram_user_id: str, user_data: dict) -> bool:
        return self.client.database.update_telegram_user(telegram_user_id, user_data)

    def get_telegram_user_by_username(self, username: str) -> Dict[str, Any]:
        return self.client.database.get_telegram_user_by_username(username)

    def get_all_registered_telegram_users(self) -> List[Dict[str, Any]]:
        return self.client.database.get_all_registered_telegram_users()

    def get_telegram_user_by_profile(self, profile_id: str) -> Dict[str, Any]:
        return self.client.database.get_telegram_user_by_profile(profile_id)

    def get_crew_agents(self, crew_id: int) -> List[Dict[str, Any]]:
        return self.client.database.get_crew_agents(crew_id)

    def get_crew_tasks(self, crew_id: int) -> List[Dict[str, Any]]:
        return self.client.database.get_crew_tasks(crew_id)

    def get_conversation_history(self, conversation_id: str) -> List[Dict[str, Any]]:
        return self.client.database.get_conversation_history(conversation_id)

    def verify_session_token(self, token: str) -> Optional[str]:
        try:
            response = self.client.auth.verify_session_token(token)
            return response.address
        except Exception as e:
            return None

    def get_profile(self, identifier: str) -> Dict[str, Any]:
        return self.client.database.get_user_profile(identifier)

    def get_twitter_author(self, author_id: str) -> Optional[XBotAuthor]:
        return self.client.database.get_twitter_author(author_id)

    def create_twitter_author(
        self,
        author_id: str,
        username: Optional[str] = None,
        realname: Optional[str] = None,
    ) -> XBotAuthor:
        return self.client.database.create_twitter_author(author_id, username, realname)

    def get_twitter_tweet(self, tweet_id: str) -> Optional[XBotTweet]:
        return self.client.database.get_twitter_tweet(tweet_id)

    def get_thread_tweets(self, thread_id: int) -> List[XBotTweet]:
        return self.client.database.get_thread_tweets(thread_id)

    def get_author_tweets(self, author_id: str) -> List[XBotTweet]:
        return self.client.database.get_author_tweets(author_id)

    def add_twitter_tweet(
        self,
        author_id: str,
        tweet_id: str,
        tweet_body: str,
        thread_id: Optional[int] = None,
    ) -> XBotTweet:
        return self.client.database.add_twitter_tweet(
            author_id, tweet_id, tweet_body, thread_id
        )

    def get_twitter_logs(self, tweet_id: str) -> List[XBotLog]:
        return self.client.database.get_twitter_logs(tweet_id)

    def add_twitter_log(
        self, tweet_id: str, status: str, message: Optional[str] = None
    ) -> XBotLog:
        return self.client.database.add_twitter_log(tweet_id, status, message)

    def get_enabled_crons_expanded(self) -> List[Dict[str, Any]]:
        """Get all enabled cron jobs with expanded crew information."""
        return self.client.database.get_enabled_crons_detailed().crons

    def get_enabled_crons(self) -> List[Dict[str, Any]]:
        """Get all enabled cron jobs."""
        return self.client.database.get_enabled_crons().crons

    def upload_file(self, file_path: str, file: bytes) -> str:
        pass

    def get_collectives(self) -> List[Dict[str, Any]]:
        """Mock implementation to get all collectives."""
        return [
            {
                "id": "mock-collective-1",
                "name": "Mock Collective 1",
                "mission": "Mock Mission 1",
                "description": "Mock Description 1",
            },
            {
                "id": "mock-collective-2",
                "name": "Mock Collective 2",
                "mission": "Mock Mission 2",
                "description": "Mock Description 2",
            },
        ]

    def get_collective(self, collective_id: str) -> Dict[str, Any]:
        """Mock implementation to get a specific collective by ID."""
        return {
            "id": collective_id,
            "name": f"Mock Collective {collective_id}",
            "mission": f"Mock Mission for {collective_id}",
            "description": f"Mock Description for {collective_id}",
        }

    def update_collective(self, collective_id: str, data: dict) -> bool:
        """Mock implementation to update a collective by ID."""
        return True

    def add_collective(
        self, name: str, mission: str, description: str
    ) -> Dict[str, Any]:
        """Mock implementation to add a new collective."""
        return {
            "id": "new-mock-collective",
            "name": name,
            "mission": mission,
            "description": description,
        }

    def get_compatabilities(self) -> List[Dict[str, Any]]:
        """Mock implementation to get all compatabilities."""
        return [
            {
                "id": "mock-compat-1",
                "collective_id": "mock-collective-1",
                "type": "mock-type",
                "contract_principal": "mock-principal-1",
                "tx_id": "mock-tx-1",
                "is_deployed": True,
                "status": "active",
            },
            {
                "id": "mock-compat-2",
                "collective_id": "mock-collective-2",
                "type": "mock-type",
                "contract_principal": "mock-principal-2",
                "tx_id": "mock-tx-2",
                "is_deployed": False,
                "status": "pending",
            },
        ]

    def get_compatability(self, compatability_id: str) -> Dict[str, Any]:
        """Mock implementation to get a specific compatability by ID."""
        return {
            "id": compatability_id,
            "collective_id": "mock-collective-1",
            "type": "mock-type",
            "contract_principal": f"mock-principal-{compatability_id}",
            "tx_id": f"mock-tx-{compatability_id}",
            "is_deployed": True,
            "status": "active",
        }

    def add_compatability(
        self,
        collective_id: str,
        type: str,
        contract_principal: str,
        tx_id: str,
        is_deployed: bool,
        status: str,
    ) -> Dict[str, Any]:
        """Mock implementation to add a new compatability."""
        return {
            "id": "new-mock-compat",
            "collective_id": collective_id,
            "type": type,
            "contract_principal": contract_principal,
            "tx_id": tx_id,
            "is_deployed": is_deployed,
            "status": status,
        }

    def update_compatability(
        self,
        compatability_id: str,
        data: dict,
    ) -> bool:
        """Mock implementation to update a compatability by ID."""
        return True

    def get_tokens(self) -> List[Dict[str, Any]]:
        """Mock implementation to get all tokens."""
        return [
            {
                "id": "mock-token-1",
                "name": "Mock Token 1",
                "symbol": "MTK1",
                "decimals": 6,
                "description": "Mock Token Description 1",
                "max_supply": "1000000",
                "image_url": "https://mock.url/token1.png",
                "uri": "https://mock.url/token1",
            },
            {
                "id": "mock-token-2",
                "name": "Mock Token 2",
                "symbol": "MTK2",
                "decimals": 8,
                "description": "Mock Token Description 2",
                "max_supply": "2000000",
                "image_url": "https://mock.url/token2.png",
                "uri": "https://mock.url/token2",
            },
        ]

    def get_token(self, token_id: str) -> Dict[str, Any]:
        """Mock implementation to get a specific token by ID."""
        return {
            "id": token_id,
            "name": f"Mock Token {token_id}",
            "symbol": f"MTK{token_id}",
            "decimals": 6,
            "description": f"Mock Token Description {token_id}",
            "max_supply": "1000000",
            "image_url": f"https://mock.url/token{token_id}.png",
            "uri": f"https://mock.url/token{token_id}",
        }

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
        """Mock implementation to add a new token."""
        return {
            "id": "new-mock-token",
            "name": name,
            "symbol": symbol,
            "decimals": decimals,
            "description": description,
            "max_supply": max_supply,
            "image_url": image_url,
            "uri": uri,
        }

    def update_token(self, token_id: str, data: dict) -> bool:
        """Mock implementation to update a token by ID."""
        return True
