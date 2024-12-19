import json
from .client import services_client, supabase
from lib.models import ProfileResponse, VerificationResponse, XBotAuthor, XBotTweet, XBotLog
from typing import Any, Dict, List, Optional

# =============================================================================
# Conversation Operations
# =============================================================================


def get_detailed_conversation(conversation_id: str) -> Dict[str, Any]:
    """Get detailed conversation data with associated jobs."""
    jobs_response = services_client.database.get_crew_executions(conversation_id)

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


# =============================================================================
# Job Operations
# =============================================================================


def add_job(
    profile_id: str,
    conversation_id: str,
    crew_id: str,
    input_data: Dict[str, Any],
    result: Dict[str, Any],
    tokens: int,
    messages: List[Dict[str, Any]],
) -> bool:
    """Add a new job with associated conversation data."""
    ## need to figure out how to add these values
    print(result)
    print(tokens)

    crew_execution = services_client.database.add_crew_execution(
        profile_id, crew_id, conversation_id, input_data
    )

    # Add crew execution steps
    for message in messages:
        add_crew_execution_step(
            profile_id,
            crew_id,
            crew_execution["execution"]["id"],
            message["type"],
            json.dumps(message),
        )
    return True


def add_crew_execution(
    profile_id: str,
    conversation_id: str,
    crew_id: str,
    input_data: Dict[str, Any],
):
    """Add a new crew execution with associated conversation data."""
    return services_client.database.add_crew_execution(
        profile_id, crew_id, conversation_id, input_data
    )


def add_crew_execution_step(
    profile_id: str,
    crew_id: int,
    execution_id: int,
    step_type: str,
    step_data: Dict[str, Any],
):
    return services_client.database.create_execution_step(
        profile_id, crew_id, execution_id, step_type, step_data
    )


# =============================================================================
# Cron Operations
# =============================================================================


def get_enabled_crons_expanded() -> List[Dict[str, Any]]:
    """Get all enabled cron jobs with expanded crew information."""
    return services_client.database.get_enabled_crons_detailed().crons


def get_enabled_crons() -> List[Dict[str, Any]]:
    """Get all enabled cron jobs."""
    return services_client.database.get_enabled_crons().crons


# =============================================================================
# Telegram User Operations
# =============================================================================


def get_telegram_user(telegram_user_id: str):
    """Get a telegram user by their ID."""
    return (
        supabase.table("telegram_users")
        .select("*")
        .eq("id", telegram_user_id)
        .execute()
    )


def update_telegram_user(telegram_user_id: str, user_data: dict):
    """Update a telegram user's data."""
    return (
        supabase.table("telegram_users")
        .update(user_data)
        .eq("id", telegram_user_id)
        .execute()
    )


def get_telegram_user_by_username(username: str):
    """Get a telegram user by their username."""
    return (
        supabase.table("telegram_users")
        .select("telegram_user_id")
        .eq("username", username)
        .eq("is_registered", True)
        .execute()
    )


def get_all_registered_telegram_users():
    """Get all registered telegram users."""
    return (
        supabase.table("telegram_users")
        .select("username,telegram_user_id")
        .eq("is_registered", True)
        .execute()
    )


def get_telegram_user_by_profile(profile_id: str):
    """Get a telegram user by their profile ID."""
    return (
        supabase.table("telegram_users")
        .select("telegram_user_id")
        .eq("profile_id", profile_id)
        .eq("is_registered", True)
        .execute()
    )


# =============================================================================
# Crew Operations
# =============================================================================


def get_crew_agents(crew_id: int):
    """Get all agents for a specific crew."""
    return services_client.database.get_crew_agents(crew_id)


def get_crew_tasks(crew_id: int):
    """Get all tasks for a specific crew."""
    return services_client.database.get_crew_tasks(crew_id)


def get_conversation_history(conversation_id: str) -> List[Dict[str, Any]]:
    """Get conversation history in chronological order."""
    return services_client.database.get_conversation_history(conversation_id)


# =============================================================================
# Profile Operations
# =============================================================================


def verify_session_token(token: str) -> VerificationResponse:
    """Validate if a token is valid and belongs to a user.

    Args:
        token (str): Authentication token

    Returns:
        dict: Dictionary containing 'valid' and 'message' keys
    """
    return services_client.auth.verify_session_token(token)


def get_profile_by_address(address: str) -> ProfileResponse:
    """Get profile information by address.

    Args:
        address (str): User's address

    Returns:
        Dict: Profile data including account_index
    """
    return services_client.database.get_user_profile(address)


# =============================================================================
# Twitter Operations
# =============================================================================


def get_twitter_author(author_id: str) -> Optional[XBotAuthor]:
    """Get a Twitter author by their ID."""
    response = services_client.database.get_author(author_id)
    return response.author if response.success else None


def create_twitter_author(
    author_id: str, username: Optional[str] = None, realname: Optional[str] = None
) -> Optional[XBotAuthor]:
    """Create a new Twitter author."""
    response = services_client.database.create_author(
        author_id=author_id, username=username, realname=realname
    )
    return response.author if response.success else None


def get_twitter_tweet(tweet_id: str) -> Optional[XBotTweet]:
    """Get a Twitter tweet by its ID."""
    response = services_client.database.get_tweet(tweet_id)
    return response.tweet if response.success else None


def get_thread_tweets(thread_id: int) -> List[XBotTweet]:
    """Get all tweets in a thread."""
    response = services_client.database.get_thread_tweets(thread_id)
    return response.tweets if response.success else []


def get_author_tweets(author_id: str) -> List[XBotTweet]:
    """Get tweets by a specific author."""
    response = services_client.database.get_author_tweets(author_id)
    return response.tweets if response.success else []


def add_twitter_tweet(
    author_id: str,
    tweet_id: str,
    tweet_body: str,
    thread_id: Optional[int] = None
) -> Optional[XBotTweet]:
    """Add a new Twitter tweet."""
    response = services_client.database.add_tweet(
        author_id=author_id,
        tweet_id=tweet_id,
        tweet_body=tweet_body,
        thread_id=thread_id
    )
    return response.tweet if response.success else None


def get_twitter_logs(tweet_id: str) -> List[XBotLog]:
    """Get all logs for a specific tweet."""
    response = services_client.database.get_tweet_logs(tweet_id)
    return response.logs if response.success else []


def add_twitter_log(
    tweet_id: str, status: str, message: Optional[str] = None
) -> Optional[XBotLog]:
    """Add a new Twitter log entry."""
    response = services_client.database.add_tweet_log(
        tweet_id=tweet_id,
        status=status,
        message=message
    )
    return response.log if response.success else None
