from typing import List, Optional, Dict, Any, Type
from abc import ABC
import requests

from lib.models import (
    UserProfile, UserTask, UserCrew, CrewExecution,
    XBotAuthor, XBotTweet, XBotLog,
    ImageGenerationResponse, ImageListResponse,
    AuthResponse, VerificationResponse,
    ProfileResponse, RoleResponse, TaskResponse,
    CrewResponse, TwitterResponse
)

class BaseResource(ABC):
    """Base class for all API resources."""
    
    prefix: str = ""
    
    def __init__(self, client: 'ServicesClient'):
        self.client = client
        
    def _request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None,
                json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        full_endpoint = f"{self.prefix}{endpoint}"
        return self.client._request(method, full_endpoint, params, json)


class DatabaseResource(BaseResource):
    """Resource for database-related endpoints with typed responses."""
    
    prefix = "/database"
    
    # Conversations
    def get_conversations(self, address: str) -> List[Dict[str, Any]]:
        data = self._request("GET", "/conversations", params={"address": address})
        return data["conversations"]
        
    def get_latest_conversation(self, address: str) -> Optional[Dict[str, Any]]:
        data = self._request("GET", "/conversations/latest", params={"address": address})
        return data.get("conversation")
        
    def get_conversation_history(self, conversation_id: int) -> List[Dict[str, Any]]:
        data = self._request("GET", "/conversations/history", params={"id": conversation_id})
        return data["history"]
    
    # Crews
    def get_public_crews(self) -> CrewResponse:
        data = self._request("GET", "/crews/public")
        return CrewResponse(**data)
    
    def get_crew(self, crew_id: int) -> CrewResponse:
        data = self._request("GET", "/crews/get", params={"id": crew_id})
        return CrewResponse(**data)
    
    def create_crew(self, crew_data: Dict[str, Any]) -> CrewResponse:
        data = self._request("POST", "/crews/create", json=crew_data)
        return CrewResponse(**data)
    
    def update_crew(self, crew_id: int, updates: Dict[str, Any]) -> CrewResponse:
        data = self._request("PUT", "/crews/update", params={"id": crew_id}, json=updates)
        return CrewResponse(**data)
    
    def delete_crew(self, crew_id: int) -> CrewResponse:
        data = self._request("DELETE", "/crews/delete", params={"id": crew_id})
        return CrewResponse(**data)

    def get_crew_executions(self, address: str) -> CrewResponse:
        data = self._request("GET", "/crews/executions", params={"address": address})
        return CrewResponse(**data)

    def add_crew_execution(self, address: str, crew_id: int, conversation_id: int, input: Optional[str] = None) -> CrewResponse:
        data = self._request("POST", "/crews/executions/add", json={
            "address": address,
            "crew_id": crew_id,
            "conversation_id": conversation_id,
            "input": input
        })
        return CrewResponse(**data)

    # User Profiles
    def get_user_profile(self, address: str) -> ProfileResponse:
        data = self._request("GET", "/profiles/get", params={"address": address})
        return ProfileResponse(**data)

    def get_user_role(self, address: str) -> RoleResponse:
        data = self._request("GET", "/profiles/role", params={"address": address})
        return RoleResponse(**data)

    def create_user_profile(self, profile_data: Dict[str, Any]) -> ProfileResponse:
        data = self._request("POST", "/profiles/create", json=profile_data)
        return ProfileResponse(**data)

    def update_user_profile(self, address: str, updates: Dict[str, Any]) -> ProfileResponse:
        data = self._request("PUT", "/profiles/update", params={"address": address}, json=updates)
        return ProfileResponse(**data)

    def delete_user_profile(self, address: str) -> ProfileResponse:
        data = self._request("DELETE", "/profiles/delete", params={"address": address})
        return ProfileResponse(**data)

    # Tasks
    def get_task(self, task_id: int) -> TaskResponse:
        data = self._request("GET", "/tasks/get", params={"id": task_id})
        return TaskResponse(**data)

    def get_tasks(self, agent_id: int) -> TaskResponse:
        data = self._request("GET", "/tasks", params={"agent_id": agent_id})
        return TaskResponse(**data)

    def create_task(self, task_data: Dict[str, Any]) -> TaskResponse:
        data = self._request("POST", "/tasks/create", json=task_data)
        return TaskResponse(**data)

    def update_task(self, task_id: int, updates: Dict[str, Any]) -> TaskResponse:
        data = self._request("PUT", "/tasks/update", params={"id": task_id}, json=updates)
        return TaskResponse(**data)

    def delete_task(self, task_id: int) -> TaskResponse:
        data = self._request("DELETE", "/tasks/delete", params={"id": task_id})
        return TaskResponse(**data)

    # Twitter
    def get_author(self, author_id: str) -> TwitterResponse:
        data = self._request("GET", "/twitter/authors/get", params={"author_id": author_id})
        return TwitterResponse(**data)
    
    def create_author(self, author_id: str, realname: Optional[str] = None, username: Optional[str] = None) -> TwitterResponse:
        json_data = {
            "author_id": author_id,
            "realname": realname,
            "username": username
        }
        data = self._request("POST", "/twitter/authors/create", json=json_data)
        return TwitterResponse(**data)
    
    def get_tweet(self, tweet_id: str) -> TwitterResponse:
        data = self._request("GET", "/twitter/tweets/get", params={"tweet_id": tweet_id})
        return TwitterResponse(**data)
    
    def get_thread_tweets(self, thread_id: int) -> TwitterResponse:
        data = self._request("GET", "/twitter/tweets/thread", params={"thread_id": thread_id})
        return TwitterResponse(**data)
    
    def get_author_tweets(self, author_id: str) -> TwitterResponse:
        data = self._request("GET", "/twitter/tweets/author", params={"author_id": author_id})
        return TwitterResponse(**data)
    
    def add_tweet(self, author_id: str, tweet_id: str, tweet_body: str, thread_id: Optional[int] = None) -> TwitterResponse:
        json_data = {
            "author_id": author_id,
            "tweet_id": tweet_id,
            "tweet_body": tweet_body,
            "thread_id": thread_id
        }
        data = self._request("POST", "/twitter/tweets/add", json=json_data)
        return TwitterResponse(**data)
    
    def get_tweet_logs(self, tweet_id: str) -> TwitterResponse:
        data = self._request("GET", "/twitter/logs/get", params={"tweet_id": tweet_id})
        return TwitterResponse(**data)
    
    def add_tweet_log(self, tweet_id: str, status: str, message: Optional[str] = None) -> TwitterResponse:
        json_data = {
            "tweet_id": tweet_id,
            "status": status,
            "message": message
        }
        data = self._request("POST", "/twitter/logs/add", json=json_data)
        return TwitterResponse(**data)


class ImageResource(BaseResource):
    """Resource for image-related endpoints with typed responses."""
    
    prefix = "/image"
    
    def generate_image(self, prompt: str, size: str = "1024x1024", n: int = 1) -> ImageGenerationResponse:
        data = self._request("POST", "/generate", json={
            "prompt": prompt,
            "size": size,
            "n": n
        })
        return ImageGenerationResponse(**data)
    
    def get_image(self, image_key: str) -> str:
        data = self._request("GET", f"/get/{image_key}")
        return data["url"]
    
    def list_images(self, cursor: Optional[str] = None, limit: int = 100) -> ImageListResponse:
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        data = self._request("GET", "/list", params=params)
        return ImageListResponse(**data)


class AuthResource(BaseResource):
    """Resource for authentication-related endpoints with typed responses."""
    
    prefix = "/auth"
    
    def request_auth_token(self, signed_message: str) -> AuthResponse:
        data = self._request("POST", "/token", json={"signed_message": signed_message})
        return AuthResponse(**data)
    
    def verify_address(self, address: str) -> VerificationResponse:
        data = self._request("GET", "/verify/address", params={"address": address})
        return VerificationResponse(**data)
    
    def verify_session_token(self, session_token: str) -> VerificationResponse:
        data = self._request("GET", "/verify/token", params={"token": session_token})
        return VerificationResponse(**data)


class ServicesClient:
    """A Python client for interacting with Cloudflare Workers' Durable Object endpoints."""
    
    database: DatabaseResource
    image: ImageResource
    auth: AuthResource
    
    def __init__(self, base_url: str, shared_key: str):
        """Initialize the client with a base URL and a shared key for authentication."""
        self.base_url = base_url.rstrip("/")
        self.shared_key = shared_key
        self.headers = {
            "Authorization": self.shared_key,
            "Content-Type": "application/json"
        }
        
        # Initialize resources directly as instance attributes
        self.database = DatabaseResource(self)
        self.image = ImageResource(self)
        self.auth = AuthResource(self)
    
    def _request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None,
                json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Internal method for making HTTP requests."""
        url = f"{self.base_url}{endpoint}"
        response = requests.request(method, url, params=params, json=json, headers=self.headers)
        response.raise_for_status()
        return response.json()
