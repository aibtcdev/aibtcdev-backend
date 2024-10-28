import requests


class AlexApi:

    def __init__(self):
        # Base URL for the Hiro API
        self.base_url = "https://api.alexgo.io/"
        self.limits = 500

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
            prices = self._get(f"v1/price_history/{token_address}?limit={self.limits}")[
                "prices"
            ]
            return [
                {"price": price["avg_price_usd"], "block": price["block_height"]}
                for price in prices
            ]
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
            return self._get(f"v1/pool_volume/{pool_token_id}?limit={self.limits}")[
                "volume_values"
            ]
        except Exception as e:
            # Raise an exception with a custom error message
            raise Exception(f"Failed to get pool volume: {str(e)}")

    def get_token_pool_agg_history(self, token_address: str, pool_token_id: str) -> str:
        """Retrieve historical price data for a specified cryptocurrency symbol."""
        try:
            # Make a GET request to the price history endpoint
            prices = self._get(f"v1/price_history/{token_address}?limit={self.limits}")[
                "prices"
            ]
            volume = self._get(f"v1/pool_volume/{pool_token_id}?limit={self.limits}")[
                "volume_values"
            ]
            # Create a dictionary to map block heights to volumes
            volume_dict = {v["block_height"]: v["volume_24h"] for v in volume}

            # Combine price and volume data based on block height
            combined_data = [
                {
                    "price": price["avg_price_usd"],
                    "block": price["block_height"],
                    "volume_24h": volume_dict.get(
                        price["block_height"], None
                    ),  # Use None if no volume data
                }
                for price in prices
            ]

            return combined_data
        except Exception as e:
            # Raise an exception with a custom error message
            raise Exception(f"Failed to get token price history: {str(e)}")

    def get_token_pool_price(self, pool_token_id: str) -> str:
        """Retrieve pool volume data for a specified pool token ID."""
        try:
            # Make a GET request to the pool volume endpoint
            return self._get(f"v1/pool_token_price/{pool_token_id}?limit={self.limits}")
        except Exception as e:
            # Raise an exception with a custom error message
            raise Exception(f"Failed to get pool volume: {str(e)}")

    def get_token_tvl(self, pool_token_id: str) -> str:
        """Retrieve tvl data for a specified token."""
        try:
            # Make a GET request to the tvl endpoint
            return self._get(f"/v1/stats/tvl/{pool_token_id}?limit={self.limits}")
        except Exception as e:
            # Raise an exception with a custom error message
            raise Exception(f"Failed to get pool volume: {str(e)}")
