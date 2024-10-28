from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
import ast
from services.chat_services import (
    ChatRequest,
    crew_manager,
    session_manager,
)

router = APIRouter()


@router.post("/chat")
async def chat_endpoint(
    request: ChatRequest,
    session_id: str = Depends(session_manager.get_or_create_session),
) -> Dict[str, str]:
    """Handle chat messages and tool interactions"""
    # Get session messages
    messages = session_manager.session_data[session_id]

    # Add user message
    messages.append({"role": "user", "content": request.user_message})

    # Trim messages if needed
    session_manager.trim_messages(messages)

    # Get LLM response
    response = crew_manager.kickoff_conversation(str(messages), session_id)
    return {"response": response.raw, "session_id": session_id}


@router.post("/reset")
async def reset_history(
    session_id: str = Depends(session_manager.get_or_create_session),
) -> Dict[str, str]:
    """Reset conversation history for a session"""
    session_manager.session_data[session_id] = [
        {
            "role": "system",
            "content": "You are a helpful assistant. Specifically you're a Stacks blockchain "
            "expert around Stacks blockchain. You have access to a bunch of tools "
            "to provide extra data regarding Stacks blockchain. Use tools when needed.",
        }
    ]

    return {"detail": "Conversation history reset.", "session_id": session_id}
