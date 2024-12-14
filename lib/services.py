from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type
import requests


class BaseResource(ABC):
    """Base class for all API resources."""
    
    prefix: str = ""  # Base prefix for all endpoints in this resource
    
    def __init__(self, client: 'ServicesClient'):
        self.client = client
        
    def _request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None,
                json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make an HTTP request using the client's configuration."""
        full_endpoint = f"{self.prefix}{endpoint}"
        return self.client._request(method, full_endpoint, params, json)


class DatabaseResource(BaseResource):
    """Resource for database-related endpoints."""
    
    prefix = "/database"
    
    # Conversations
    def get_conversations(self, address: str) -> Dict[str, Any]:
        return self._request("GET", "/conversations", params={"address": address})
        
    def get_latest_conversation(self, address: str) -> Dict[str, Any]:
        return self._request("GET", "/conversations/latest", params={"address": address})
        
    def get_conversation_history(self, conversation_id: int) -> Dict[str, Any]:
        return self._request("GET", "/conversations/history", params={"id": conversation_id})
    
    # Crews
    def get_public_crews(self) -> Dict[str, Any]:
        return self._request("GET", "/crews/public")
    
    def get_crew(self, crew_id: int) -> Dict[str, Any]:
        return self._request("GET", "/crews/get", params={"id": crew_id})
    
    def create_crew(self, crew_data: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", "/crews/create", json=crew_data)
    
    def update_crew(self, crew_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("PUT", "/crews/update", params={"id": crew_id}, json=updates)
    
    def delete_crew(self, crew_id: int) -> Dict[str, Any]:
        return self._request("DELETE", "/crews/delete", params={"id": crew_id})
    
    # Agents
    def get_agents(self, crew_id: int) -> Dict[str, Any]:
        return self._request("GET", "/agents/get", params={"crewId": crew_id})
    
    def create_agent(self, agent_data: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", "/agents/create", json=agent_data)
    
    def update_agent(self, agent_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("PUT", "/agents/update", params={"id": agent_id}, json=updates)
    
    def delete_agent(self, agent_id: int) -> Dict[str, Any]:
        return self._request("DELETE", "/agents/delete", params={"id": agent_id})
    
    # Tasks
    def get_task(self, task_id: int) -> Dict[str, Any]:
        return self._request("GET", "/tasks/get", params={"id": task_id})
    
    def list_tasks(self, agent_id: int) -> Dict[str, Any]:
        return self._request("GET", "/tasks/list", params={"agentId": agent_id})
    
    def create_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", "/tasks/create", json=task_data)
    
    def update_task(self, task_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("PUT", "/tasks/update", params={"id": task_id}, json=updates)
    
    def delete_task(self, task_id: int) -> Dict[str, Any]:
        return self._request("DELETE", "/tasks/delete", params={"id": task_id})
    
    def delete_all_tasks(self, agent_id: int) -> Dict[str, Any]:
        return self._request("DELETE", "/tasks/delete-all", params={"agentId": agent_id})
    
    # Profiles
    def get_user_role(self, address: str) -> Dict[str, Any]:
        return self._request("GET", "/profiles/role", params={"address": address})
    
    def get_user_profile(self, address: str) -> Dict[str, Any]:
        return self._request("GET", "/profiles/get", params={"address": address})
    
    def create_user_profile(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", "/profiles/create", json=profile_data)
    
    def update_user_profile(self, address: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("PUT", "/profiles/update", params={"address": address}, json=updates)
    
    def delete_user_profile(self, address: str) -> Dict[str, Any]:
        return self._request("DELETE", "/profiles/delete", params={"address": address})
    
    # Admin
    def list_user_profiles(self) -> Dict[str, Any]:
        return self._request("GET", "/profiles/admin/list")
    
    def update_user_profile_by_id(self, user_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("PUT", "/profiles/admin/update", params={"userId": user_id}, json=updates)


class ImageResource(BaseResource):
    """Resource for image-related endpoints."""
    
    prefix = "/image"
    
    def generate_image(self, prompt: str, size: str = "1024x1024", n: int = 1) -> Dict[str, Any]:
        """Generate an image using the OpenAI API through the Durable Object."""
        payload = {"prompt": prompt, "size": size, "n": n}
        return self._request("POST", "/generate", json=payload)
    
    def get_image(self, image_key: str) -> bytes:
        """Retrieve an image by its key."""
        url = f"{self.client.base_url}{self.prefix}/get/{image_key}"
        response = requests.get(url, headers=self.client.headers)
        response.raise_for_status()
        return response.content
    
    def list_images(self, cursor: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        """List images stored in the Durable Object."""
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        return self._request("GET", "/list", params=params)


class ServicesClient:
    """A Python client for interacting with Cloudflare Workers' Durable Object endpoints."""
    
    # Registry of available resources
    _resources: Dict[str, Type[BaseResource]] = {
        'database': DatabaseResource,
        'image': ImageResource,
    }
    
    def __init__(self, base_url: str, shared_key: str):
        """Initialize the client with a base URL and a shared key for authentication."""
        self.base_url = base_url.rstrip("/")
        self.shared_key = shared_key
        self.headers = {
            "Authorization": self.shared_key,
            "Content-Type": "application/json"
        }
        
        # Initialize resources
        self._init_resources()
    
    def _init_resources(self) -> None:
        """Initialize all registered resources."""
        for name, resource_class in self._resources.items():
            setattr(self, name, resource_class(self))
    
    def _request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None,
                json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Internal method for making HTTP requests."""
        url = f"{self.base_url}{endpoint}"
        response = requests.request(method, url, headers=self.headers, params=params, json=json)
        response.raise_for_status()
        return response.json()
    
    @classmethod
    def register_resource(cls, name: str, resource_class: Type[BaseResource]) -> None:
        """Register a new resource type with the client."""
        cls._resources[name] = resource_class