from typing import Dict, List, Any
from uuid import uuid4
from fastapi import Request
from pydantic import BaseModel
from dotenv import load_dotenv
from db.supabase_client import supabase
from lib.velar import VelarApi
from lib.lunarcrush import LunarcrushApi
from cachetools import TTLCache
import os
import tiktoken
from crews.chat import UserChatSpecialistCrew

# Load environment variables
load_dotenv()

# Constants
TOKEN_MODEL = "gpt-4o-mini"
MAX_TOKENS = 50000
SAFETY_MARGIN = 500


class Config:
    """Configuration class for API settings"""

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.tokenizer = tiktoken.encoding_for_model(TOKEN_MODEL)


class ChatRequest(BaseModel):
    """Data model for chat API requests"""

    user_message: str


class SessionManager:
    """Manages chat session data and token handling"""

    def __init__(self, ttl: int = 3600, maxsize: int = 100):
        self.session_data = TTLCache(maxsize=maxsize, ttl=ttl)
        self.config = Config()

    def get_or_create_session(self, request: Request) -> str:
        session_id = request.query_params.get("session_id")
        if session_id and session_id in self.session_data:
            return session_id
        else:
            session_id = str(uuid4())
            self.session_data[session_id] = [
                {"role": "system", "content": "You're a Stacks blockchain expert."}
            ]
            return session_id

    def get_session_data(self, session_id: str) -> List[Dict[str, Any]]:
        if session_id in self.session_data:
            return self.session_data[session_id]
        raise ValueError("Session not found")

    def update_session_data(self, session_id: str, messages: List[Dict[str, Any]]):
        self.session_data[session_id] = messages

    def count_tokens(self, messages: List[Dict[str, Any]]) -> int:
        text = "".join([msg["content"] for msg in messages if msg["content"]])
        return len(self.config.tokenizer.encode(text))

    def trim_messages(self, messages: List[Dict[str, Any]]) -> None:
        while self.count_tokens(messages) > (MAX_TOKENS - SAFETY_MARGIN):
            if len(messages) > 2:
                messages.pop(1)
            else:
                break


class ToolManager:
    """Manages blockchain tool operations"""

    def __init__(self):
        self.velar_api = VelarApi()
        self.lunarcrush_api = LunarcrushApi()

    def get_tokens(self) -> str:
        return self.velar_api.get_tokens()

    def get_token_socials(self, token_contract_addr: str) -> str:
        return self.lunarcrush_api.get_token_socials(token_contract_addr)

    def get_token_stats(self, token: str, interval: str = "month") -> str:
        pools = self.velar_api.get_token_stx_pools(token.upper())
        if pools:
            return self.velar_api.get_pool_stats_history_agg(pools[0]["id"], interval)
        return "pool not found"


class UserChatSpecialistCrewManager:
    """Manages interactions with the UserChatSpecialistCrew"""

    def __init__(self):
        self.session_manager = SessionManager()
        self.tool_manager = ToolManager()

    def kickoff_conversation(self, user_input: str, session_id: str) -> str:
        crew_class = UserChatSpecialistCrew()
        crew_class.setup_agents()
        crew_class.setup_tasks(user_input)
        crew = crew_class.create_crew()
        crew.planning = True
        result = crew.kickoff()

        # Update session data with the result
        messages = self.session_manager.get_session_data(session_id)
        messages.append({"role": "assistant", "content": result.raw})
        self.session_manager.update_session_data(session_id, messages)

        return result


# Initialize managers
crew_manager = UserChatSpecialistCrewManager()
session_manager = crew_manager.session_manager
tool_manager = crew_manager.tool_manager

# Create tools dictionary for compatibility
tools = {
    "get_tokens": tool_manager.get_tokens,
    "get_token_stats": tool_manager.get_token_stats,
    "get_token_socials": tool_manager.get_token_socials,
}
