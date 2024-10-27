import requests
import json


class HiroApi:

    def __init__(self):
        self.base_url = "https://api.hiro.so"

    def _get(self, endpoint: str, params: dict = None) -> dict:
        """Make a GET request to the Velar API."""
        try:
            url = self.base_url + endpoint
            headers = {"Accept": "application/json"}
            response = requests.get(url, headers=headers, params=params)

            # Check for errors
            response.raise_for_status()

            # Return response data
            return response.json()
        except Exception as e:
            raise Exception(f"Velar API GET request error: {str(e)}")

    def get_tokens(self) -> str:
        try:
            return self._get("swapapp/swap/tokens")["message"]

        except Exception as e:
            raise Exception(f"Swap data retrieval error: {str(e)}")
