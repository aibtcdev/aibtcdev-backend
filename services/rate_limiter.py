from datetime import datetime, timedelta
from typing import Dict, Optional
import os

from lib.logger import configure_logger

logger = configure_logger(__name__)

class DAORateLimiter:
    def __init__(self):
        """Initialize the DAO rate limiter."""
        self._weekly_limit = int(os.getenv("AIBTC_TWITTER_WEEKLY_DAO_LIMIT", "1500"))
        self._public_access = os.getenv("AIBTC_TWITTER_PUBLIC_ACCESS", "false").lower() == "true"
        self._whitelisted_users = set(os.getenv("AIBTC_TWITTER_WHITELISTED", "").split(","))
        self._usage_counters: Dict[str, Dict] = {}

    def _clean_old_records(self, user_id: str) -> None:
        """Remove records older than 7 days."""
        now = datetime.utcnow()
        if user_id in self._usage_counters:
            self._usage_counters[user_id]["timestamps"] = [
                ts for ts in self._usage_counters[user_id]["timestamps"]
                if now - ts < timedelta(days=7)
            ]

    def check_rate_limit(self, user_id: str) -> bool:
        """
        Check if a user has exceeded their rate limit.

        Args:
            user_id: Twitter user ID

        Returns:
            True if user can proceed, False if rate limited
        """
        # Whitelisted users bypass rate limiting
        if user_id in self._whitelisted_users:
            return True

        # If public access is disabled, only whitelisted users can proceed
        if not self._public_access:
            return False

        self._clean_old_records(user_id)
        
        # Check current usage
        if user_id in self._usage_counters:
            current_count = len(self._usage_counters[user_id]["timestamps"])
            return current_count < self._weekly_limit
        
        return True

    def increment_counter(self, user_id: str) -> None:
        """
        Increment the usage counter for a user.

        Args:
            user_id: Twitter user ID
        """
        if user_id not in self._usage_counters:
            self._usage_counters[user_id] = {"timestamps": []}
        
        self._usage_counters[user_id]["timestamps"].append(datetime.utcnow())
        self._clean_old_records(user_id)

    def get_usage_stats(self, user_id: str) -> Dict:
        """
        Get usage statistics for a user.

        Args:
            user_id: Twitter user ID

        Returns:
            Dictionary containing usage statistics
        """
        self._clean_old_records(user_id)
        
        if user_id not in self._usage_counters:
            return {
                "total_usage": 0,
                "remaining": self._weekly_limit if self._public_access else 0,
                "is_whitelisted": user_id in self._whitelisted_users
            }
        
        current_count = len(self._usage_counters[user_id]["timestamps"])
        return {
            "total_usage": current_count,
            "remaining": self._weekly_limit - current_count if self._public_access else 0,
            "is_whitelisted": user_id in self._whitelisted_users
        }
