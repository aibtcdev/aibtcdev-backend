import requests
import os
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

class AlexApi:

    def __init__(self):
        self.base_url = os.getenv('ALEX_BASE_URL', 'https://api.alexgo.io/')
        self.limits = 500

    def _get(self, endpoint: str, params: dict = {}):
        """Send a GET request to the Alex API endpoint."""
        try:
            url = self.base_url + endpoint
            headers = {"Accept": "application/json"}
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise Exception(f"Alex API GET request error: {str(e)}")

    def get_pairs(self):
        """Retrieve a list of available trading pairs."""
        try:
            return self._get("v1/public/pairs")["data"]
        except Exception as e:
            raise Exception(f"Failed to get token pairs: {str(e)}")

    def get_price_history(self, token_address: str):
        """Retrieve historical price data for a token address."""
        try:
            prices = self._get(f"v1/price_history/{token_address}?limit={self.limits}")["prices"]
            return [
                {"price": price["avg_price_usd"], "block": price["block_height"]}
                for price in prices
            ]
        except Exception as e:
            raise Exception(f"Failed to get token price history: {str(e)}")

    def get_all_swaps(self):
        """Retrieve all swap data from the Alex API."""
        try:
            return self._get("v1/allswaps")
        except Exception as e:
            raise Exception(f"Failed to get all swaps: {str(e)}")

    def get_token_pool_volume(self, pool_token_id: str):
        """Retrieve pool volume data for a specified pool token ID."""
        try:
            return self._get(f"v1/pool_volume/{pool_token_id}?limit={self.limits}")["volume_values"]
        except Exception as e:
            raise Exception(f"Failed to get pool volume: {str(e)}")

    def get_token_pool_agg_history(self, token_address: str, pool_token_id: str):
        """Retrieve aggregated price and volume history for a token and pool."""
        try:
            prices = self._get(f"v1/price_history/{token_address}?limit={self.limits}")["prices"]
            volume = self._get(f"v1/pool_volume/{pool_token_id}?limit={self.limits}")["volume_values"]
            volume_dict = {v["block_height"]: v["volume_24h"] for v in volume}
            combined_data = [
                {
                    "price": price["avg_price_usd"],
                    "block": price["block_height"],
                    "volume_24h": volume_dict.get(price["block_height"], None)
                }
                for price in prices
            ]
            return combined_data
        except Exception as e:
            raise Exception(f"Failed to get token price history: {str(e)}")

    def get_token_pool_price(self, pool_token_id: str):
        """Retrieve current pool price for a specified pool token ID."""
        try:
            return self._get(f"v1/pool_token_price/{pool_token_id}?limit={self.limits}")
        except Exception as e:
            raise Exception(f"Failed to get pool price: {str(e)}")

    def get_token_tvl(self, pool_token_id: str):
        """Retrieve total value locked data for a specified token."""
        try:
            return self._get(f"/v1/stats/tvl/{pool_token_id}?limit={self.limits}")
        except Exception as e:
            raise Exception(f"Failed to get pool volume: {str(e)}")
