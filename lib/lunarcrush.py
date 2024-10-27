import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()


class LunarcrushApi:

    def __init__(self):
        self.base_url = "https://lunarcrush.com/api4/public/"
        self.api_key = os.getenv("LUNARCRUSH_API_KEY")

    def _get(self, endpoint: str, params: dict = None) -> dict:
        """Make a GET request to the Velar API."""
        try:
            url = self.base_url + endpoint
            headers = {
                "Accept": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }
            response = requests.get(url, headers=headers, params=params)

            # Check for errors
            response.raise_for_status()

            # Return response data
            return response.json()
        except Exception as e:
            raise Exception(f"Lunarcrush API GET request error: {str(e)}")

    def get_token_socials(self, token_contract_addr: str) -> str:
        try:
            print(token_contract_addr)
            return self._get(f"coins/{token_contract_addr}/v1")["data"]

        except Exception as e:
            raise Exception(f"Swap data retrieval error: {str(e)}")
