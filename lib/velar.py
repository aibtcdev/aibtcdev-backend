import requests
import json


class VelarApi:

    def __init__(self):
        self.base_url = "https://gateway.velar.network/"

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

    def get_pools(self) -> str:
        try:
            return self._get("watcherapp/pool")["message"]

        except Exception as e:
            raise Exception(f"Swap data retrieval error: {str(e)}")

    def get_token_pools(self, token: str) -> str:
        try:
            pools = self.get_pools()
            results = [
                x
                for x in pools
                if x["token0Symbol"] == token or x["token1Symbol"] == token
            ]
            return results

        except Exception as e:
            raise Exception(f"Swap data retrieval error: {str(e)}")

    def get_token_stx_pools(self, token: str) -> str:
        try:
            pools = self.get_pools()
            results = [
                x
                for x in pools
                if (x["token0Symbol"] == token and x["token1Symbol"] == "STX")
                or (x["token0Symbol"] == "STX" and x["token1Symbol"] == token)
            ]
            return results

        except Exception as e:
            raise Exception(f"Swap data retrieval error: {str(e)}")

    def get_token_price_history(self, token: str, interval: str = "hour") -> str:
        try:
            return self._get(f"watcherapp/stats/price/{token}/?interval={interval}")
        except Exception as e:
            raise Exception(f"Token stats retrieval error: {str(e)}")

    def get_token_stats(self, token: str) -> str:
        try:
            return self._get(f"watcherapp/pool/{token}")
        except Exception as e:
            raise Exception(f"Token pool stats retrieval error: {str(e)}")

    def get_pool_stats_history(
        self, poolId: str, type: str, interval: str = "month"
    ) -> str:
        try:
            return self._get(
                f"watcherapp/stats/{poolId}?type={type}&interval={interval}"
            )
        except Exception as e:
            raise Exception(f"Token pool stats history retrieval error: {str(e)}")

    def get_pool_stats_history_agg(self, poolId: str, interval: str = "month") -> str:
        try:
            tvl_data = self._get(
                f"watcherapp/stats/{poolId}?type=tvl&interval={interval}"
            )
            volume_data = self._get(
                f"watcherapp/stats/{poolId}?type=volume&interval={interval}"
            )
            price_data = self._get(
                f"watcherapp/stats/{poolId}?type=price&interval={interval}"
            )

            # Aggregate the data
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
            raise Exception(f"Token pool stats history retrieval error: {str(e)}")


# obj = VelarApi()
# target = "LEO"

# tokens = obj.get_tokens()
# # print(json.dumps(tokens, indent=4))

# pools = obj.get_pools()
# # print(json.dumps(pools, indent=4))

# token_pools = obj.get_token_pools(target)
# # print(json.dumps(token_pools, indent=4))

# token_stx_pools = obj.get_token_stx_pools(target)
# # print(json.dumps(token_stx_pools, indent=4))

# token_price_history = obj.get_token_price_history(target)
# # print(json.dumps(token_price_history, indent=4))

# pool_price = obj.get_pool_stats_history(token_stx_pools[0]["id"], "tvl", "day")
# # print(json.dumps(pool_price, indent=4))

# pool_agg = obj.get_pool_stats_history_agg(token_stx_pools[0]["id"], "month")
# print(json.dumps(pool_agg, indent=4))
