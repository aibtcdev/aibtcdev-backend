import os
import time
from .database import Database
from lib.logger import configure_logger
from lib.models import (
    ProfileResponse,
    VerificationResponse,
    XBotAuthor,
    XBotLog,
    XBotTweet,
)
from supabase import Client
from typing import Any, Dict, List, Optional

logger = configure_logger(__name__)


class SupabaseDatabase(Database):
    # Upload configuration
    MAX_UPLOAD_RETRIES = 3
    RETRY_DELAY_SECONDS = 1

    def __init__(self, client: Client, **kwargs):
        super().__init__()
        self.client = client
        self.bucket_name = kwargs.get("bucket_name")

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

    def upload_file(self, file_path: str, file: bytes) -> str:
        """Upload a file to Supabase storage.

        Args:
            file_path: The path where the file will be stored in the bucket
            file: The file content in bytes

        Returns:
            str: The public URL of the uploaded file

        Raises:
            ValueError: If file_path is empty or file is None
            StorageError: If upload fails or public URL cannot be generated
            Exception: For other unexpected errors
        """
        if not file_path or not file:
            raise ValueError("File path and file content are required")

        if not self.bucket_name:
            raise ValueError("Storage bucket name is not configured")

        def attempt_upload(attempt: int) -> Optional[str]:
            try:
                logger.debug(
                    f"Attempting file upload to {file_path} (attempt {attempt})"
                )
                upload_response = self.client.storage.from_(self.bucket_name).upload(
                    file_path, file, {"upsert": "true"}  # Override if file exists
                )

                if not upload_response:
                    raise Exception("Upload failed - no response received")

                logger.debug(f"Upload successful: {upload_response}")

                # Get public URL
                public_url = self.client.storage.from_(self.bucket_name).get_public_url(
                    file_path
                )
                if not public_url:
                    raise Exception("Failed to generate public URL")

                return public_url

            except Exception as e:
                logger.error(f"Upload attempt {attempt} failed: {str(e)}")
                if attempt >= self.MAX_UPLOAD_RETRIES:
                    raise
                time.sleep(self.RETRY_DELAY_SECONDS * attempt)  # Exponential backoff
                return None

        # Attempt upload with retries
        last_error = None
        for attempt in range(1, self.MAX_UPLOAD_RETRIES + 1):
            try:
                if result := attempt_upload(attempt):
                    return result
            except Exception as e:
                last_error = e

        # If we get here, all retries failed
        raise Exception(
            f"Failed to upload file after {self.MAX_UPLOAD_RETRIES} attempts: {str(last_error)}"
        )

    def get_collectives(self) -> List[Dict[str, Any]]:
        """Get all collectives."""
        response = self.client.table("collectives").select("*").execute()
        return response.data if response.data else []

    def get_collective(self, collective_id: str) -> Dict[str, Any]:
        """Get a specific collective by ID."""
        response = (
            self.client.table("collectives")
            .select("*")
            .eq("id", collective_id)
            .execute()
        )
        if not response.data:
            raise Exception("Collective not found")
        return response.data[0]

    def update_collective(self, collective_id: str, data: dict) -> bool:
        """Update a collective by ID."""
        response = (
            self.client.table("collectives")
            .update(data)
            .eq("id", collective_id)
            .execute()
        )
        return bool(response.data)

    def add_collective(
        self, name: str, mission: str, description: str
    ) -> Dict[str, Any]:
        """Add a new collective."""
        data = {
            "name": name,
            "mission": mission,
            "description": description,
        }
        response = self.client.table("collectives").insert(data).execute()
        if not response.data:
            raise Exception("Failed to create collective record")
        return response.data[0]

    def get_capabilities(self) -> List[Dict[str, Any]]:
        """Get all capabilities."""
        response = self.client.table("capabilities").select("*").execute()
        return response.data if response.data else []

    def get_capability(self, capability_id: str) -> Dict[str, Any]:
        """Get a specific capability by ID."""
        response = (
            self.client.table("capabilities")
            .select("*")
            .eq("id", capability_id)
            .execute()
        )
        if not response.data:
            raise Exception("capability not found")
        return response.data[0]

    def add_schedule(
        self,
        profile_id: str,
        task: str,
        cron: str,
        enabled: bool,
    ) -> dict:
        data = {
            "profile_id": profile_id,
            "task": task,
            "cron": cron,
            "enabled": enabled,
        }
        response = self.client.table("schedules").insert(data).execute()
        return response.data[0]

    def add_capability(
        self,
        collective_id: str,
        type: str,
        contract_principal: str,
        tx_id: str,
        status: str,
    ) -> Dict[str, Any]:
        """Add a new capabilities."""
        data = {
            "collective_id": collective_id,
            "type": type,
            "contract_principal": contract_principal,
            "tx_id": tx_id,
            "status": status,
        }
        response = self.client.table("capabilities").insert(data).execute()
        if not response.data:
            raise Exception("Failed to create capabilities record")
        return response.data[0]

    def update_capability(self, capability_id: str, data: dict) -> bool:
        """Update a capabilities by ID."""
        response = (
            self.client.table("capabilities")
            .update(data)
            .eq("id", capability_id)
            .execute()
        )
        return bool(response.data)

    def get_tokens(self) -> List[Dict[str, Any]]:
        """Get all tokens."""
        response = self.client.table("tokens").select("*").execute()
        return response.data if response.data else []

    def get_token(self, token_id: str) -> Dict[str, Any]:
        """Get a specific token by ID."""
        response = self.client.table("tokens").select("*").eq("id", token_id).execute()
        if not response.data:
            raise Exception("Token not found")
        return response.data[0]

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
        """Add a new token."""
        data = {
            "name": name,
            "symbol": symbol,
            "decimals": decimals,
            "description": description,
            "max_supply": max_supply,
            "image_url": image_url,
            "uri": uri,
        }
        response = self.client.table("tokens").insert(data).execute()
        if not response.data:
            raise Exception("Failed to create token record")
        return response.data[0]

    def update_token(self, token_id: str, data: dict) -> bool:
        """Update a token by ID."""
        response = self.client.table("tokens").update(data).eq("id", token_id).execute()
        return bool(response.data)
