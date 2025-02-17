import requests
from config import config
from typing import Any, Dict, Optional


class PlatformApi:
    def __init__(self):
        """Initialize the Platform API client."""
        self.base_url = config.api.platform_base_url
        self.api_key = config.api.hiro_api_key
        self.webhook_url = config.api.webhook_url
        self.webhook_auth = config.api.webhook_auth
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

    def generate_dao_x_linkage(
        self,
        contract_identifier: str,
        method: str = "send",
        start_block: int = 601924,
        network: str = "mainnet",
        name: str = "getMessage",
        end_block: Optional[int] = None,
        webhook_url: Optional[str] = "",
        webhook_auth: Optional[str] = "",
    ) -> Dict[str, Any]:
        """Generate a chainhook predicate for DAO X linkage monitoring.

        Args:
            txid: The transaction ID to monitor
            start_block: The block height to start monitoring from
            name: Name of the chainhook
            network: Network to monitor (testnet or mainnet)
            end_block: Optional block height to stop monitoring
            expire_after_occurrence: Number of occurrences before expiring
            webhook_url: Optional custom webhook URL
            webhook_auth: Optional custom webhook authorization header
            contract_identifier: The contract identifier for contract call
            method: The method name for contract call

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
                        "scope": "contract_call",
                        "method": method,
                        "contract_identifier": contract_identifier,
                    },
                    "end_block": end_block,
                    "then_that": {
                        "http_post": {
                            "url": webhook_url or self.webhook_url,
                            "authorization_header": webhook_auth or self.webhook_auth,
                        }
                    },
                    "start_block": start_block,
                    "decode_clarity_values": True,
                }
            },
        }

    def create_dao_x_linkage_hook(
        self, contract_identifier: str, method: str, **kwargs
    ) -> Dict[str, Any]:
        """Create a chainhook for monitoring DAO X linkage.

        Args:
            txid: The transaction ID to monitor
            **kwargs: Additional arguments to pass to generate_contract_deployment_predicate

        Returns:
            Dict containing the response from the API
        """
        predicate = self.generate_dao_x_linkage(contract_identifier, method, **kwargs)
        return self.create_chainhook(predicate)
