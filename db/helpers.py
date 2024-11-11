from .supabase_client import supabase


def add_job(profile, conversation_id, crew_id, input_data, result, messages):
    """
    Add a new run with input, result, and thought process for a specific conversation and crew.
    """
    new_job = {
        "conversation_id": conversation_id,
        "crew_id": crew_id,
        "profile_id": profile.id,
        "input": input_data,
        "result": result,
        "messages": messages,
    }
    result = supabase.table("jobs").insert(new_job).execute()
    return result


def add_conversation(profile, name: str = "New Conversation"):
    """
    Add a new conversation for a specific profile.
    """
    new_conversation = {
        "profile_id": profile.id,
        "name": name,
    }
    result = supabase.table("conversations").insert(new_conversation).execute()
    return result


def get_jobs(profile) -> list:
    """
    Get all jobs for a specific profile.
    """
    runs_response = (
        supabase.table("jobs")
        .select("*")
        .eq("profile_id", profile.id)
        .order("created_at", desc=True)
        .execute()
    )

    if runs_response.data:
        return runs_response.data
    else:
        return []


def get_conversations(profile) -> list:
    """
    Get all conversations for a specific profile.
    """
    conversation_response = (
        supabase.table("conversations")
        .select("*")
        .eq("profile_id", profile.id)
        .order("created_at", desc=True)
        .execute()
    )

    if conversation_response.data:
        return conversation_response.data
    else:
        return []


def get_detailed_conversation(profile, conversation_id):
    """
    Get detailed conversation data for a specific conversation and profile.
    """
    conversation_response = (
        supabase.table("conversations")
        .select("*")
        .eq("profile_id", profile.id)
        .eq("id", conversation_id)
        .order("created_at", desc=True)
        .execute()
    )

    if conversation_response.data:
        conversation_ids = [
            conversation["id"] for conversation in conversation_response.data
        ]

        # Retrieve all tasks linked to this conversation
        jobs_response = (
            supabase.table("jobs")
            .select("*")
            .in_("conversation_id", conversation_ids)
            .order("created_at", desc=True)
            .execute()
        )

        # Zip up the conversations data and next the tasks for the conversations
        _with_jobs = {
            "conversation": conversation_response.data[0],
            "jobs": [
                job
                for job in jobs_response.data
                if job["conversation_id"] == conversation_response.data[0]["id"]
            ],
        }

        return _with_jobs
    else:
        # No conversation exists
        return {}


def get_detailed_conversations(profile):
    conversation_response = (
        supabase.table("conversations")
        .select("*")
        .eq("profile_id", profile.id)
        .order("created_at", desc=True)
        .execute()
    )

    if conversation_response.data:
        conversation_ids = [
            conversation["id"] for conversation in conversation_response.data
        ]

        # Retrieve all tasks linked to this conversation
        jobs_response = (
            supabase.table("jobs")
            .select("*")
            .in_("conversation_id", conversation_ids)
            .order("created_at", asc=True)
            .execute()
        )

        # Zip up the conversations data and next the tasks for the conversations
        _with_jobs = [
            {
                "conversation": conversation,
                "jobs": [
                    job
                    for job in jobs_response.data
                    if job["conversation_id"] == conversation["id"]
                ],
            }
            for conversation in conversation_response.data
        ]

        return _with_jobs
    else:
        # No conversation exists
        return []


def update_message(profile, messages):
    response = (
        supabase.table("conversations")
        .select("*")
        .eq("profile_id", profile.id)
        .execute()
    )
    data = response.data

    if data:
        # Conversation exists, so append to the existing messages
        conversation_id = data[0]["id"]
        existing_messages = data[0]["messages"]

        # Append the new message to the messages array
        updated_messages = existing_messages + messages

        # Update the conversation with the appended messages
        supabase.table("conversations").update({"messages": updated_messages}).eq(
            "id", conversation_id
        ).execute()

    else:
        # No conversation exists, create a new one
        new_conversation = {
            "profile_id": profile.id,
            "messages": messages,
        }
        supabase.table("conversations").insert(new_conversation).execute()


def get_latest_conversation(profile):
    # Retrieve the history of messages for the user
    response = (
        supabase.table("conversations")
        .select("*")
        .eq("profile_id", profile.id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    data = response.data
    if data:
        return data[0]
    else:
        # No conversation exists, return an empty list
        return []


def get_latest_conversation_id(profile) -> int:
    # Retrieve the history of messages for the user
    response = (
        supabase.table("conversations")
        .select("id")
        .eq("profile_id", profile.id)
        .order("created_at", desc=True)
        .limit()
        .execute()
    )
    data = response.data
    if data:
        # Conversation exists, so return the id
        return data[0]["id"]
    else:
        # No conversation exists, return an empty list
        return 0


def delete_conversation(profile, conversation_id):
    # Delete the conversation from the database
    supabase.table("conversations").delete().eq("id", conversation_id).eq(
        "profile_id", profile.id
    ).execute()
    return True


def mask_email(email: str) -> str:
    """Mask the @stacks.id part of the email and capitalize the username."""
    if "@stacks.id" in email:
        username = email.split("@")[0]
        return username.upper()
    return email.upper()


def get_public_crews():
    try:
        # Fetch crews from the 'crews' table
        crews_response = (
            supabase.table("crews")
            .select("*", count="exact")
            .eq("is_public", True)
            .execute()
        )

        if not crews_response.data:
            return []

        result = []
        for crew in crews_response.data:
            creator_response = (
                supabase.table("profiles")
                .select("email")
                .eq("id", crew["profile_id"])
                .single()
                .execute()
            )
            agents_response = (
                supabase.table("agents").select("*").eq("crew_id", crew["id"]).execute()
            )

            agents = []
            for agent in agents_response.data:
                tasks_response = (
                    supabase.table("tasks")
                    .select("*")
                    .eq("agent_id", agent["id"])
                    .execute()
                )
                agent_with_tasks = {**agent, "tasks": tasks_response.data or []}
                agents.append(agent_with_tasks)

            crew_response = {
                **crew,
                "creator_email": mask_email(creator_response.data.get("email", "")),
                "agents": agents,
            }
            result.append(crew_response)

        return result

    except Exception as e:
        raise Exception(f"Error fetching public crews: {str(e)}")
