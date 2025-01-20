import os
import requests
from dotenv import load_dotenv
from typing import Any, Dict, Optional

# Load environment variables from a .env file
load_dotenv()


class PlatformApi:

    def __init__(self):
        self.base_url = os.getenv(
            "AIBTC_PLATFORM_API_URL", "https://api.platform.hiro.so"
        )
        self.api_key = os.getenv("HIRO_API_KEY")
        self.webhook_url = os.getenv("AIBTC_WEBHOOK_URL")
        self.webhook_auth = os.getenv("AIBTC_WEBHOOK_AUTH", "Bearer 1234567890")
        if not self.api_key:
            raise ValueError("HIRO_API_KEY environment variable is required")

    def generate_contract_deployment_predicate(
        self,
        txid: str,
        start_block: int = 75996,
        network: str = "testnet",
        name: str = "test",
        end_block: Optional[int] = None,
        expire_after_occurrence: int = 1,
        webhook_url: Optional[str] = None,
        webhook_auth: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate a chainhook predicate for specific transaction monitoring.

        Args:
            txid: The transaction ID to monitor
            start_block: The block height to start monitoring from
            name: Name of the chainhook
            network: Network to monitor (testnet or mainnet)
            end_block: Optional block height to stop monitoring
            expire_after_occurrence: Number of occurrences before expiring
            webhook_url: Optional custom webhook URL
            webhook_auth: Optional custom webhook authorization header

        Returns:
            Dict containing the chainhook predicate configuration
        """
        return {
            "name": name,
            "chain": "stacks",
            "version": 1,
            "networks": {
                f"{network}": {
                    "if_this": {"scope": "txid", "equals": txid},
                    "end_block": end_block,
                    "then_that": {
                        "http_post": {
                            "url": webhook_url or self.webhook_url,
                            "authorization_header": webhook_auth or self.webhook_auth,
                        }
                    },
                    "start_block": start_block,
                    "decode_clarity_values": True,
                    "expire_after_occurrence": expire_after_occurrence,
                }
            },
        }

    def create_contract_deployment_hook(self, txid: str, **kwargs) -> Dict[str, Any]:
        """Create a chainhook for monitoring contract deployments.

        Args:
            txid: The transaction ID to monitor
            **kwargs: Additional arguments to pass to generate_contract_deployment_predicate

        Returns:
            Dict containing the response from the API
        """
        predicate = self.generate_contract_deployment_predicate(txid, **kwargs)
        return self.create_chainhook(predicate)

    def create_chainhook(self, chainhook_predicate: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new chainhook.

        Args:
            chainhook_predicate: The chainhook predicate configuration

        Returns:
            Dict containing the response from the API
        """
        try:
            url = f"{self.base_url}/v1/ext/{self.api_key}/chainhooks"
            headers = {"Content-Type": "application/json"}
            response = requests.post(url, headers=headers, json=chainhook_predicate)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise Exception(f"Hiro API POST request error: {str(e)}")
