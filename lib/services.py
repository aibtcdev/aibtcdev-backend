import requests
from typing import Dict, Any
import os
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

class ServicesClient:
    def __init__(self):
        """
        Initialize the client with the base URL of the Cloudflare Worker API and shared key for authentication.
        
        :param base_url: The base URL for the Cloudflare Worker API (e.g., https://example.com/metadata).
        :param shared_key: Shared key for API authentication.
        """
        self.base_url = os.getenv("AIBTC_SERVICES_BASE_URL", "https://lunarcrush.com/api4/public/")
        self.api_key = os.getenv("AIBTC_SERVICES_API_KEY")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        """
        Generic method to handle requests to the API.
        
        :param method: HTTP method (GET, POST, PATCH).
        :param endpoint: API endpoint path relative to the base URL.
        :param kwargs: Additional parameters for the requests method.
        :return: JSON response or raises an HTTPError if the request fails.
        """
        url = f"{self.base_url}{endpoint}"
        response = requests.request(method, url, headers=self.headers, **kwargs)
        response.raise_for_status()
        return response.json()

    def generate_metadata(self, contract_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate metadata for a token.

        :param contract_id: The contract ID for the token.
        :param data: The metadata generation request payload.
        :return: Generated metadata response.
        """
        endpoint = f"/generate/{contract_id}"
        return self._request("POST", endpoint, json=data)

    def get_metadata(self, contract_id: str) -> Dict[str, Any]:
        """
        Retrieve metadata for a token.

        :param contract_id: The contract ID for the token.
        :return: Retrieved metadata.
        """
        endpoint = f"/{contract_id}"
        return self._request("GET", endpoint)

    def update_metadata(self, contract_id: str, updates: Dict[str, Any], method: str = "PATCH") -> Dict[str, Any]:
        """
        Update metadata for a token.

        :param contract_id: The contract ID for the token.
        :param updates: The updated metadata fields.
        :param method: HTTP method to use ('PATCH' for partial update, 'POST' for full update).
        :return: Updated metadata response.
        """
        if method not in {"PATCH", "POST"}:
            raise ValueError("Invalid method. Use 'PATCH' for partial update or 'POST' for full update.")
        endpoint = f"/update/{contract_id}"
        return self._request(method, endpoint, json=updates)
