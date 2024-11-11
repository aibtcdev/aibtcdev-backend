import requests


class VelarApi:
    def __init__(self):
        # Base URL for the Velar API
        self.base_url = "https://gateway.velar.network/"

    def _get(self, endpoint: str, params: dict = None) -> dict:
        """Make a GET request to the Velar API."""
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
            raise Exception(f"Velar API GET request error: {str(e)}")

    def get_tokens(self) -> str:
        """Retrieve a list of tokens from the Velar API."""
        try:
            # Make a GET request to the tokens endpoint
            return self._get("swapapp/swap/tokens")["message"]
        except Exception as e:
            # Raise an exception with a custom error message
            raise Exception(f"Swap data retrieval error: {str(e)}")

    def get_pools(self) -> str:
        """Retrieve a list of pools from the Velar API."""
        try:
            # Make a GET request to the pools endpoint
            return self._get("watcherapp/pool")["message"]
        except Exception as e:
            # Raise an exception with a custom error message
            raise Exception(f"Swap data retrieval error: {str(e)}")

    def get_token_pools(self, token: str) -> str:
        """Retrieve pools containing a specific token."""
        try:
            # Get all pools
            pools = self.get_pools()
            # Filter pools that contain the specified token
            results = [
                x
                for x in pools
                if x["token0Symbol"] == token or x["token1Symbol"] == token
            ]
            return results
        except Exception as e:
            # Raise an exception with a custom error message
            raise Exception(f"Swap data retrieval error: {str(e)}")

    def get_token_stx_pools(self, token: str) -> str:
        """Retrieve pools containing a specific token paired with STX."""
        try:
            # Get all pools
            pools = self.get_pools()
            # Filter pools that contain the specified token paired with STX
            results = [
                x
                for x in pools
                if (x["token0Symbol"] == token and x["token1Symbol"] == "STX")
                or (x["token0Symbol"] == "STX" and x["token1Symbol"] == token)
            ]
            return results
        except Exception as e:
            # Raise an exception with a custom error message
            raise Exception(f"Swap data retrieval error: {str(e)}")

    def get_token_price_history(self, token: str, interval: str = "month") -> str:
        """Retrieve the price history of a specific token."""
        try:
            # Make a GET request to the price history endpoint
            return self._get(
                f"watcherapp/stats/{token}/?type=price&interval={interval}"
            )
        except Exception as e:
            # Raise an exception with a custom error message
            raise Exception(f"Token stats retrieval error: {str(e)}")

    def get_token_stats(self, token: str) -> str:
        """Retrieve statistics for a specific token."""
        try:
            # Make a GET request to the token stats endpoint
            return self._get(f"watcherapp/pool/{token}")
        except Exception as e:
            # Raise an exception with a custom error message
            raise Exception(f"Token pool stats retrieval error: {str(e)}")

    def get_pool_stats_history(
        self, poolId: str, type: str, interval: str = "month"
    ) -> str:
        """Retrieve historical statistics for a specific pool."""
        try:
            # Make a GET request to the pool stats history endpoint
            return self._get(
                f"watcherapp/stats/{poolId}?type={type}&interval={interval}"
            )
        except Exception as e:
            # Raise an exception with a custom error message
            raise Exception(f"Token pool stats history retrieval error: {str(e)}")

    def get_pool_stats_history_agg(self, poolId: str, interval: str = "month") -> str:
        """Retrieve and aggregate historical statistics for a specific pool."""
        try:
            # Retrieve TVL, volume, and price data for the pool
            tvl_data = self._get(
                f"watcherapp/stats/{poolId}?type=tvl&interval={interval}"
            )
            volume_data = self._get(
                f"watcherapp/stats/{poolId}?type=volume&interval={interval}"
            )
            price_data = self._get(
                f"watcherapp/stats/{poolId}?type=price&interval={interval}"
            )

            # Aggregate the data into a single list
            aggregated_data = []
            for price, tvl, volume in zip(
                price_data["data"], tvl_data["data"], volume_data["data"]
            ):
                aggregated_data.append(
                    {
                        "price": price["value"],
                        "tvl": tvl["value"],
                        "datetime": price[
                            "datetime"
                        ],  # Assuming datetime is the same across all
                        "volume": volume["value"],
                    }
                )

            return aggregated_data
        except Exception as e:
            # Raise an exception with a custom error message
            raise Exception(f"Token pool stats history retrieval error: {str(e)}")
