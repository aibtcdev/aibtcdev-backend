import requests
import os
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()


class LunarcrushApi:

    def __init__(self):
        # Base URL for the Lunarcrush API
        self.base_url = "https://lunarcrush.com/api4/public/"
        # Retrieve the API key from environment variables
        self.api_key = os.getenv("LUNARCRUSH_API_KEY")

    def _get(self, endpoint: str, params: dict = None) -> dict:
        """Make a GET request to the Lunarcrush API."""
        try:
            # Construct the full URL
            url = self.base_url + endpoint
            # Set headers for the request, including the API key for authorization
            headers = {
                "Accept": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }
            # Make the GET request
            response = requests.get(url, headers=headers, params=params)

            # Check for HTTP errors
            response.raise_for_status()

            # Return the JSON response data
            return response.json()
        except Exception as e:
            # Raise an exception with a custom error message
            raise Exception(f"Lunarcrush API GET request error: {str(e)}")

    def get_token_socials(self, token_contract_addr: str) -> str:
        """Retrieve social data for a specific token using its contract address."""
        try:
            # Print the token contract address (for debugging purposes)
            print(token_contract_addr)
            # Make a GET request to the token socials endpoint
            return self._get(f"coins/{token_contract_addr}/v1")["data"]
        except Exception as e:
            # Raise an exception with a custom error message
            raise Exception(f"Swap data retrieval error: {str(e)}")
