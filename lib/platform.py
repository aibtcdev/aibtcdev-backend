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
        self.webhook_auth = os.getenv("AIBTC_WEBHOOK_AUTH")
        if not self.api_key:
            raise ValueError("HIRO_API_KEY environment variable is required")

    def generate_contract_deployment_predicate(
        self,
        deployer_address: str,
        start_block: int = 63416,
        network: str = "testnet",
        name: str = "aibtcdevtestnet",
        end_block: Optional[int] = None,
        expire_after_occurrence: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generate a chainhook predicate for contract deployments.

        Args:
            deployer_address: The address of the contract deployer to monitor
            start_block: The block height to start monitoring from
            name: Name of the chainhook
            end_block: Optional block height to stop monitoring
            expire_after_occurrence: Optional number of occurrences before expiring

        Returns:
            Dict containing the chainhook predicate configuration
        """
        return {
            "name": name,
            "chain": "stacks",
            "version": 1,
            "networks": {
                f"{network}": {
                    "if_this": {
                        "scope": "contract_deployment",
                        "deployer": deployer_address,
                    },
                    "end_block": end_block,
                    "then_that": {
                        "http_post": {
                            "url": self.webhook_url,
                            "authorization_header": self.webhook_auth,
                        }
                    },
                    "start_block": start_block,
                    "decode_clarity_values": True,
                    "expire_after_occurrence": expire_after_occurrence,
                }
            },
        }

    def create_contract_deployment_hook(
        self, deployer_address: str, **kwargs
    ) -> Dict[str, Any]:
        """Create a chainhook for monitoring contract deployments.

        Args:
            deployer_address: The address of the contract deployer to monitor
            **kwargs: Additional arguments to pass to generate_contract_deployment_predicate

        Returns:
            Dict containing the response from the API
        """
        predicate = self.generate_contract_deployment_predicate(
            deployer_address, **kwargs
        )
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
