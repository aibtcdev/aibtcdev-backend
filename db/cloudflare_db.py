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

    def __init__(self, client: ServicesClient):
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
