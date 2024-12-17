from lib.models import ProfileResponse, VerificationResponse
from .client import supabase, services_client

from typing import Dict, List, Optional, Union, Any

# =============================================================================
# Conversation Operations
# =============================================================================

def get_detailed_conversation(conversation_id: str) -> Dict[str, Any]:
    """Get detailed conversation data with associated jobs."""
    jobs_response = services_client.database.get_crew_executions(conversation_id)

    if not jobs_response.executions:
        return {
            "conversation": conversation_id,
            "jobs": []
        }

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
    messages: List[Dict[str, Any]]
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
    return supabase.table("jobs").insert(new_job).execute()

# =============================================================================
# Cron Operations
# =============================================================================

def get_enabled_crons_expanded() -> List[Dict[str, Any]]:
    """Get all enabled cron jobs with expanded crew information."""
    return (
        supabase.from_("crons")
        .select("id, input, profiles(id, account_index), crew_id")
        .eq("enabled", True)
        .order("created_at", desc=True)
        .execute()
        .data
    )

def get_enabled_crons() -> List[Dict[str, Any]]:
    """Get all enabled cron jobs."""
    return (
        supabase.table("crons")
        .select("*")
        .eq("enabled", True)
        .order("created_at", desc=True)
        .execute()
        .data
    )

# =============================================================================
# Telegram User Operations
# =============================================================================

def get_telegram_user(telegram_user_id: str):
    """Get a telegram user by their ID."""
    return supabase.table('telegram_users').select('*').eq('id', telegram_user_id).execute()

def update_telegram_user(telegram_user_id: str, user_data: dict):
    """Update a telegram user's data."""
    return supabase.table('telegram_users').update(user_data).eq('id', telegram_user_id).execute()

def get_telegram_user_by_username(username: str):
    """Get a telegram user by their username."""
    return supabase.table('telegram_users').select('telegram_user_id').eq('username', username).eq('is_registered', True).execute()

def get_all_registered_telegram_users():
    """Get all registered telegram users."""
    return supabase.table('telegram_users').select('username,telegram_user_id').eq('is_registered', True).execute()

def get_telegram_user_by_profile(profile_id: str):
    """Get a telegram user by their profile ID."""
    return supabase.table('telegram_users').select('telegram_user_id').eq('profile_id', profile_id).eq('is_registered', True).execute()

# =============================================================================
# Crew Operations
# =============================================================================

def get_all_crews():
    """Get all crews with basic information."""
    return supabase.from_("crews").select("id, name, description").execute()

def get_crew_agents(crew_id: int):
    """Get all agents for a specific crew."""
    return supabase.from_("agents").select("*").eq("crew_id", crew_id).execute()

def get_crew_tasks(crew_id: int):
    """Get all tasks for a specific crew."""
    return supabase.from_("tasks").select("*").eq("crew_id", crew_id).execute()

def get_conversation_history(conversation_id: str) -> List[Dict[str, Any]]:
    """Get conversation history in chronological order."""
    jobs_response = (
        supabase.table("jobs")
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

def mask_email(email: str) -> str:
    """Mask and format an email address."""
    if "@stacks.id" in email:
        username = email.split("@")[0]
        return username.upper()
    return email.upper()

# =============================================================================
# Profile Operations
# =============================================================================

def get_user_from_token(token: str) -> Dict:
    """Get user information from an authentication token.
    
    Args:
        token (str): Authentication token
        
    Returns:
        Dict: User information including email
    """
    return supabase.auth.get_user(token)

def get_profile_by_email(email: str) -> Dict:
    """Get profile information by email.
    
    Args:
        email (str): User's email address
        
    Returns:
        Dict: Profile data including account_index
    """
    return (
        supabase.table("profiles")
        .select("account_index, email")
        .eq("email", email)
        .single()
        .execute()
    )

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