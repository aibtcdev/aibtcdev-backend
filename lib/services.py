import requests
from abc import ABC
from lib.models import (
    AgentResponse,
    AuthResponse,
    CrewResponse,
    CrewStepResponse,
    CronResponse,
    ImageGenerationResponse,
    ImageListResponse,
    ProfileResponse,
    RoleResponse,
    TaskResponse,
    TwitterResponse,
    VerificationResponse,
)
from typing import Any, Dict, List, Optional


class BaseResource(ABC):
    """Base class for all API resources."""

    prefix: str = ""

    def __init__(self, client: "ServicesClient"):
        self.client = client

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
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
        data = self._request(
            "GET", "/conversations/latest", params={"address": address}
        )
        return data.get("conversation")

    def get_conversation_history(self, conversation_id: int) -> List[Dict[str, Any]]:
        data = self._request(
            "GET", "/conversations/history", params={"id": conversation_id}
        )
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
        data = self._request(
            "PUT", "/crews/update", params={"id": crew_id}, json=updates
        )
        return CrewResponse(**data)

    def delete_crew(self, crew_id: int) -> CrewResponse:
        data = self._request("DELETE", "/crews/delete", params={"id": crew_id})
        return CrewResponse(**data)

    def get_crew_executions(self, address: str) -> CrewResponse:
        data = self._request("GET", "/crews/executions", params={"address": address})
        return CrewResponse(**data)

    def add_crew_execution(
        self,
        address: str,
        crew_id: int,
        conversation_id: int,
        input: Optional[str] = None,
    ) -> CrewResponse:
        data = self._request(
            "POST",
            "/crews/executions/add",
            json={
                "address": address,
                "crew_id": crew_id,
                "conversation_id": conversation_id,
                "input": input,
            },
        )
        return CrewResponse(**data)

    def get_execution_steps(self, execution_id: int) -> CrewStepResponse:
        """Get all steps for a crew execution.

        This endpoint requires authentication via Authorization header.
        """
        data = self._request(
            "GET", "/crews/steps/get", params={"executionId": execution_id}
        )
        return CrewStepResponse(**data)

    def create_execution_step(
        self,
        profile_id: str,
        crew_id: int,
        execution_id: int,
        step_type: str,
        step_data: Dict[str, Any],
    ) -> CrewStepResponse:
        """Create a new execution step.

        Required fields in step_data:
        - profile_id: str
        - crew_id: int
        - execution_id: int
        - step_type: str
        - step_data: Dict[str, Any]

        This endpoint requires authentication via Authorization header.
        The profile_id must match the authenticated user's address.
        """
        step_data = {
            "profile_id": profile_id,
            "crew_id": crew_id,
            "execution_id": execution_id,
            "step_type": step_type,
            "step_data": step_data,
        }
        data = self._request("POST", "/crews/steps/create", json=step_data)
        return CrewStepResponse(**data)

    def delete_execution_steps(self, execution_id: int) -> CrewStepResponse:
        """Delete all steps for a crew execution.

        This endpoint requires authentication via Authorization header.
        """
        data = self._request(
            "DELETE", "/crews/steps/delete", params={"executionId": execution_id}
        )
        return CrewStepResponse(**data)

    # Agents
    def get_crew_agents(self, crew_id: int) -> AgentResponse:
        data = self._request("GET", "/agents/get", params={"crewId": crew_id})
        return AgentResponse(**data)

    def create_agent(self, agent_data: Dict[str, Any]) -> AgentResponse:
        data = self._request("POST", "/agents/create", json=agent_data)
        return AgentResponse(**data)

    def update_agent(self, agent_id: int, updates: Dict[str, Any]) -> AgentResponse:
        data = self._request(
            "PUT", "/agents/update", params={"id": agent_id}, json=updates
        )
        return AgentResponse(**data)

    def delete_agent(self, agent_id: int) -> AgentResponse:
        data = self._request("DELETE", "/agents/delete", params={"id": agent_id})
        return AgentResponse(**data)

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

    def update_user_profile(
        self, address: str, updates: Dict[str, Any]
    ) -> ProfileResponse:
        data = self._request(
            "PUT", "/profiles/update", params={"address": address}, json=updates
        )
        return ProfileResponse(**data)

    def delete_user_profile(self, address: str) -> ProfileResponse:
        data = self._request("DELETE", "/profiles/delete", params={"address": address})
        return ProfileResponse(**data)

    # Tasks
    def get_task(self, task_id: int) -> TaskResponse:
        data = self._request("GET", "/tasks/get", params={"id": task_id})
        return TaskResponse(**data)

    def get_crew_tasks(self, crew_id: int) -> TaskResponse:
        """Get all tasks for a specific crew."""
        data = self._request("GET", "/tasks/list", params={"crewId": crew_id})
        return TaskResponse(**data)

    def get_agent_tasks(self, agent_id: int) -> TaskResponse:
        """Get all tasks for a specific agent."""
        data = self._request("GET", "/tasks/list", params={"agentId": agent_id})
        return TaskResponse(**data)

    def create_task(self, task_data: Dict[str, Any]) -> TaskResponse:
        """Create a new task.

        Required fields in task_data:
        - profile_id: str
        - crew_id: int
        - agent_id: int
        - task_name: str
        - task_description: str
        - task_expected_output: str
        """
        data = self._request("POST", "/tasks/create", json=task_data)
        return TaskResponse(**data)

    def update_task(self, task_id: int, updates: Dict[str, Any]) -> TaskResponse:
        """Update an existing task.

        Only task_name, task_description, and task_expected_output can be updated.
        """
        data = self._request(
            "PUT", "/tasks/update", params={"id": task_id}, json=updates
        )
        return TaskResponse(**data)

    def delete_task(self, task_id: int) -> TaskResponse:
        """Delete a specific task."""
        data = self._request("DELETE", "/tasks/delete", params={"id": task_id})
        return TaskResponse(**data)

    def delete_agent_tasks(self, agent_id: int) -> TaskResponse:
        """Delete all tasks for a specific agent."""
        data = self._request(
            "DELETE", "/tasks/delete-all", params={"agentId": agent_id}
        )
        return TaskResponse(**data)

    # Cron Operations
    def get_enabled_crons(self) -> CronResponse:
        """Get all enabled crons."""
        data = self._request("GET", "/crons/enabled")
        return CronResponse(**data)

    def get_enabled_crons_detailed(self) -> CronResponse:
        """Get detailed information about all enabled crons."""
        data = self._request("GET", "/crons/enabled/detailed")
        return CronResponse(**data)

    def get_crew_crons(self, crew_id: int) -> CronResponse:
        """Get all crons for a specific crew."""
        data = self._request("GET", "/crons/get", params={"crewId": crew_id})
        return CronResponse(**data)

    def create_cron(self, cron_data: Dict[str, Any]) -> CronResponse:
        """Create a new cron job.

        Required fields in cron_data:
        - profile_id: str
        - crew_id: int
        - AIBTC_CRON_ENABLED: bool

        Optional fields:
        - cron_interval: str (default: "0 * * * *")
        - cron_input: str (default: "")
        """
        data = self._request("POST", "/crons/create", json=cron_data)
        return CronResponse(**data)

    def update_cron_input(self, cron_id: int, cron_input: str) -> CronResponse:
        """Update the input string for a cron job."""
        data = self._request(
            "PUT",
            "/crons/update",
            params={"id": cron_id},
            json={"cron_input": cron_input},
        )
        return CronResponse(**data)

    def toggle_cron(self, cron_id: int, enabled: bool) -> CronResponse:
        """Enable or disable a cron job."""
        data = self._request(
            "PUT",
            "/crons/toggle",
            params={"id": cron_id},
            json={"AIBTC_CRON_ENABLED": enabled},
        )
        return CronResponse(**data)

    # Twitter
    def get_author(self, author_id: str) -> TwitterResponse:
        data = self._request(
            "GET", "/twitter/authors/get", params={"authorId": author_id}
        )
        print(data)
        return TwitterResponse(**data)

    def create_author(
        self,
        author_id: str,
        realname: Optional[str] = None,
        username: Optional[str] = None,
    ) -> TwitterResponse:
        json_data = {"author_id": author_id, "realname": realname, "username": username}
        data = self._request("POST", "/twitter/authors/create", json=json_data)
        return TwitterResponse(**data)

    def get_tweet(self, tweet_id: str) -> TwitterResponse:
        data = self._request("GET", "/twitter/tweets/get", params={"tweetId": tweet_id})
        return TwitterResponse(**data)

    def get_thread_tweets(self, thread_id: int) -> TwitterResponse:
        data = self._request(
            "GET", "/twitter/tweets/thread", params={"threadId": thread_id}
        )
        return TwitterResponse(**data)

    def get_author_tweets(self, author_id: str) -> TwitterResponse:
        data = self._request(
            "GET", "/twitter/tweets/author", params={"authorId": author_id}
        )
        return TwitterResponse(**data)

    def add_tweet(
        self,
        author_id: str,
        tweet_id: str,
        tweet_body: str,
        thread_id: Optional[int] = None,
        parent_tweet_id: Optional[str] = None,
        is_bot_response: bool = False,
    ) -> TwitterResponse:
        json_data = {
            "author_id": author_id,
            "tweet_id": tweet_id,
            "tweet_body": tweet_body,
            "thread_id": thread_id,
            "parent_tweet_id": parent_tweet_id,
            "is_bot_response": is_bot_response,
        }
        data = self._request("POST", "/twitter/tweets/add", json=json_data)
        return TwitterResponse(**data)

    def get_tweet_logs(self, tweet_id: str) -> TwitterResponse:
        data = self._request("GET", "/twitter/logs/get", params={"tweet_id": tweet_id})
        return TwitterResponse(**data)

    def add_tweet_log(
        self, tweet_id: str, status: str, message: Optional[str] = None
    ) -> TwitterResponse:
        json_data = {"tweet_id": tweet_id, "status": status, "message": message}
        data = self._request("POST", "/twitter/logs/add", json=json_data)
        return TwitterResponse(**data)


class ImageResource(BaseResource):
    """Resource for image-related endpoints with typed responses."""

    prefix = "/image"

    def generate_image(
        self, prompt: str, size: str = "1024x1024", n: int = 1
    ) -> ImageGenerationResponse:
        data = self._request(
            "POST", "/generate", json={"prompt": prompt, "size": size, "n": n}
        )
        return ImageGenerationResponse(**data)

    def get_image(self, image_key: str) -> str:
        data = self._request("GET", f"/get/{image_key}")
        return data["url"]

    def list_images(
        self, cursor: Optional[str] = None, limit: int = 100
    ) -> ImageListResponse:
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
            "Content-Type": "application/json",
        }

        # Initialize resources directly as instance attributes
        self.database = DatabaseResource(self)
        self.image = ImageResource(self)
        self.auth = AuthResource(self)

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make an HTTP request to the API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            params: Query parameters
            json: JSON body data

        Returns:
            Response data as a dictionary
        """
        url = f"{self.base_url}{endpoint}"
        response = requests.request(
            method,
            url,
            params=params,
            json=json,
            headers=self.headers,
        )
        try:
            response.raise_for_status()
            data = response.json()
            # Wrap the response data with success field if it's missing
            if isinstance(data, dict) and "success" not in data:
                data = {"success": True, **data}
            return data
        except requests.exceptions.RequestException as e:
            # Return error response with success=False
            print(f"Request error: {e}")
            return {"success": False, "error": str(e)}
