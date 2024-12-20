from .database import Database
from lib.models import (
    ProfileResponse,
    VerificationResponse,
    XBotAuthor,
    XBotLog,
    XBotTweet,
)
from supabase import Client
from typing import Any, Dict, List, Optional


class SupabaseDatabase(Database):

    def __init__(self, client: Client):
        super().__init__()
        self.client = client

    def get_detailed_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """Get detailed conversation data with associated jobs."""
        jobs_response = (
            self.client.table("jobs")
            .select("*")
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=True)
            .execute()
        )

        return {
            "conversation": conversation_id,
            "jobs": [
                job
                for job in jobs_response.data
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
    ) -> Dict[str, Any]:
        """Add a new job with associated conversation data."""
        new_job = {
            "profile_id": profile_id,
            "conversation_id": conversation_id,
            "crew_id": crew_id,
            "input": input_data,
            "tokens": tokens,
            "result": result,
            "messages": messages,
        }
        return self.client.table("jobs").insert(new_job).execute()

    def get_enabled_crons_expanded(self) -> List[Dict[str, Any]]:
        """Get all enabled cron jobs with expanded crew information."""
        return (
            self.client.from_("crons")
            .select("id, input, profiles(id, account_index), crew_id")
            .eq("enabled", True)
            .order("created_at", desc=True)
            .execute()
            .data
        )

    def get_enabled_crons(self) -> List[Dict[str, Any]]:
        """Get all enabled cron jobs."""
        return (
            self.client.table("crons")
            .select("*")
            .eq("enabled", True)
            .order("created_at", desc=True)
            .execute()
            .data
        )

    def get_telegram_user(self, telegram_user_id: str) -> Dict[str, Any]:
        response = (
            self.client.table("telegram_users")
            .select("*")
            .eq("telegram_id", telegram_user_id)
            .single()
            .execute()
        )
        return response.data if response.data else {}

    def update_telegram_user(self, telegram_user_id: str, user_data: dict) -> bool:
        response = (
            self.client.table("telegram_users")
            .update(user_data)
            .eq("telegram_id", telegram_user_id)
            .execute()
        )
        return bool(response.data)

    def get_telegram_user_by_username(self, username: str) -> Dict[str, Any]:
        response = (
            self.client.table("telegram_users")
            .select("*")
            .eq("username", username)
            .single()
            .execute()
        )
        return response.data if response.data else {}

    def get_all_registered_telegram_users(self) -> List[Dict[str, Any]]:
        response = self.client.table("telegram_users").select("*").execute()
        return response.data if response.data else []

    def get_telegram_user_by_profile(self, profile_id: str) -> Dict[str, Any]:
        response = (
            self.client.table("telegram_users")
            .select("*")
            .eq("profile_id", profile_id)
            .single()
            .execute()
        )
        return response.data if response.data else {}

    def get_crew_agents(self, crew_id: int) -> List[Dict[str, Any]]:
        """Get all agents for a specific crew."""
        return (
            self.client.from_("agents")
            .select("*")
            .eq("crew_id", crew_id)
            .execute()
            .data
        )

    def get_crew_tasks(self, crew_id: int) -> List[Dict[str, Any]]:
        """Get all tasks for a specific crew."""
        return (
            self.client.from_("tasks").select("*").eq("crew_id", crew_id).execute().data
        )

    def get_conversation_history(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Get conversation history in chronological order."""
        jobs_response = (
            self.client.table("jobs")
            .select("*")
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=False)
            .execute()
        )

        history = []
        for job in jobs_response.data:
            if job.get("messages"):
                history.extend(job["messages"])

        return history

    def verify_session_token(self, token: str) -> Optional[str]:
        try:
            user = self.client.auth.get_user(token)
            return user.user.email
        except Exception as e:
            return None

    def get_profile(self, identifier: str) -> Dict[str, Any]:
        response = (
            self.client.table("profiles")
            .select("id, account_index, email")
            .eq("email", identifier)
            .single()
            .execute()
        )
        return response.data if response.data else None

    def get_twitter_author(self, author_id: str) -> Optional[XBotAuthor]:
        response = (
            self.client.table("twitter_authors")
            .select("*")
            .eq("author_id", author_id)
            .single()
            .execute()
        )
        return XBotAuthor(**response.data) if response.data else None

    def create_twitter_author(
        self,
        author_id: str,
        username: Optional[str] = None,
        realname: Optional[str] = None,
    ) -> XBotAuthor:
        data = {"author_id": author_id, "username": username, "realname": realname}
        response = self.client.table("twitter_authors").insert(data).execute()
        return XBotAuthor(**response.data[0])

    def get_twitter_tweet(self, tweet_id: str) -> Optional[XBotTweet]:
        response = (
            self.client.table("twitter_tweets")
            .select("*")
            .eq("tweet_id", tweet_id)
            .single()
            .execute()
        )
        return XBotTweet(**response.data) if response.data else None

    def get_thread_tweets(self, thread_id: int) -> List[XBotTweet]:
        response = (
            self.client.table("twitter_tweets")
            .select("*")
            .eq("thread_id", thread_id)
            .execute()
        )
        return [XBotTweet(**tweet) for tweet in response.data] if response.data else []

    def get_author_tweets(self, author_id: str) -> List[XBotTweet]:
        response = (
            self.client.table("twitter_tweets")
            .select("*")
            .eq("author_id", author_id)
            .execute()
        )
        return [XBotTweet(**tweet) for tweet in response.data] if response.data else []

    def add_twitter_tweet(
        self,
        author_id: str,
        tweet_id: str,
        tweet_body: str,
        thread_id: Optional[int] = None,
    ) -> XBotTweet:
        data = {
            "author_id": author_id,
            "tweet_id": tweet_id,
            "tweet_body": tweet_body,
            "thread_id": thread_id,
        }
        response = self.client.table("twitter_tweets").insert(data).execute()
        return XBotTweet(**response.data[0])

    def get_twitter_logs(self, tweet_id: str) -> List[XBotLog]:
        response = (
            self.client.table("twitter_logs")
            .select("*")
            .eq("tweet_id", tweet_id)
            .execute()
        )
        return [XBotLog(**log) for log in response.data] if response.data else []

    def add_twitter_log(
        self,
        tweet_id: str,
        status: str,
        message: Optional[str] = None,
    ) -> XBotLog:
        data = {"tweet_id": tweet_id, "status": status, "message": message}
        response = self.client.table("twitter_logs").insert(data).execute()
        return XBotLog(**response.data[0])

    def mask_email(self, email: str) -> str:
        """Mask and format an email address."""
        if "@stacks.id" in email:
            username = email.split("@")[0]
            return username.upper()
        return email.upper()
