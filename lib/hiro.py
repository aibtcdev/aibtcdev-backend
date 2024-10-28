import requests


class HiroApi:

    def __init__(self):
        # Base URL for the Hiro API
        self.base_url = "https://api.hiro.so"

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

    def get_token_holders(self, token: str) -> str:
        """Retrieve a list of tokens from the Hiro API."""
        try:
            # Make a GET request to the tokens endpoint
            return self._get(f"extended/v1/tokens/ft/{token}/holders")
        except Exception as e:
            # Raise an exception with a custom error message
            raise Exception(f"Hiro API GET request error: {str(e)}")

    def get_wallet_balance(self, addr: str) -> str:
        """Retrieve a list of tokens from the Hiro API."""
        try:
            # Make a GET request to the wallet balance endpoint
            return self._get(f"extended/v1/address/{addr}/balances")
        except Exception as e:
            # Raise an exception with a custom error message
            raise Exception(f"Hiro API GET request error: {str(e)}")
