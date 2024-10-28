import requests


class AlexApi:

    def __init__(self):
        # Base URL for the Hiro API
        self.base_url = "https://api.alexgo.io/"

    def _get(self, endpoint: str, params: dict = None) -> dict:
        """Make a GET request to the Hiro API."""
        try:
            # Construct the full URL
            url = self.base_url + endpoint
            # Set headers for the request
            headers = {"Accept": "application/json"}
            # Make the GET request
            response = requests.get(url, headers=headers, params=params)

            # Check for HTTP errors
            response.raise_for_status()

            # Return the JSON response data
            return response.json()
        except Exception as e:
            # Raise an exception with a custom error message
            raise Exception(f"Hiro API GET request error: {str(e)}")

    def get_pairs(self) -> str:
        """Retrieve a list of tokens from the Hiro API."""
        try:
            # Make a GET request to the tokens endpoint
            return self._get("v1/public/pairs")["data"]
        except Exception as e:
            # Raise an exception with a custom error message
            raise Exception(f"Failed to get token pairs: {str(e)}")

    def get_price_history(self, token_address: str) -> str:
        """Retrieve historical price data for a specified cryptocurrency symbol."""
        try:
            # Make a GET request to the price history endpoint
            return self._get(f"v1/price_history/{token_address}?limit=1000")
        except Exception as e:
            # Raise an exception with a custom error message
            raise Exception(f"Failed to get token price history: {str(e)}")

    def get_all_swaps(self) -> str:
        """Retrieve all swap data from the Alex API."""
        try:
            # Make a GET request to the all swaps endpoint
            return self._get("v1/allswaps")
        except Exception as e:
            # Raise an exception with a custom error message
            raise Exception(f"Failed to get all swaps: {str(e)}")

    def get_token_pool_volume(self, pool_token_id: str) -> str:
        """Retrieve pool volume data for a specified pool token ID."""
        try:
            # Make a GET request to the pool volume endpoint
            return self._get(f"v1/pool_volume/{pool_token_id}?limit=1000")
        except Exception as e:
            # Raise an exception with a custom error message
            raise Exception(f"Failed to get pool volume: {str(e)}")
