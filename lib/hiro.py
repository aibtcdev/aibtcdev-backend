import os
import requests
from dotenv import load_dotenv
from typing import Any, Dict

# Load environment variables from a .env file
load_dotenv()


class HiroApi:

    def __init__(self):
        self.base_url = os.getenv("AIBTC_HIRO_API_URL", "https://api.hiro.so")

    def _get(self, endpoint: str, params: dict = None) -> dict:
        """Make a GET request to the Hiro API."""
        try:
            url = self.base_url + endpoint
            headers = {"Accept": "application/json"}
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise Exception(f"Hiro API GET request error: {str(e)}")

    def get_token_holders(self, token: str) -> str:
        """Retrieve a list of token holders."""
        try:
            return self._get(f"/extended/v1/tokens/ft/{token}/holders")
        except Exception as e:
            raise Exception(f"Hiro API GET request error: {str(e)}")

    def get_address_balance(self, addr: str) -> str:
        """Retrieve wallet balance for an address."""
        try:
            return self._get(f"/extended/v1/address/{addr}/balances")
        except Exception as e:
            raise Exception(f"Hiro API GET request error: {str(e)}")

    # Transaction related endpoints
    def get_transaction(self, tx_id: str) -> dict:
        """Get transaction details."""
        return self._get(f"/extended/v1/tx/{tx_id}")

    def get_raw_transaction(self, tx_id: str) -> dict:
        """Get raw transaction details."""
        return self._get(f"/extended/v1/tx/{tx_id}/raw")

    def get_transactions_by_block(self, block_hash: str) -> dict:
        """Get transactions in a block."""
        return self._get(f"/extended/v1/tx/block/{block_hash}")

    def get_transactions_by_block_height(self, height: int) -> dict:
        """Get transactions in a block by height."""
        return self._get(f"/extended/v1/tx/block_height/{height}")

    def get_mempool_transactions(self) -> dict:
        """Get pending transactions."""
        return self._get("/extended/v1/tx/mempool")

    def get_dropped_mempool_transactions(self) -> dict:
        """Get dropped transactions."""
        return self._get("/extended/v1/tx/mempool/dropped")

    def get_mempool_stats(self) -> dict:
        """Get mempool statistics."""
        return self._get("/extended/v1/tx/mempool/stats")

    # Block related endpoints
    def get_blocks(self) -> dict:
        """Get recent blocks."""
        return self._get("/extended/v1/block")

    def get_block_by_height(self, height: int) -> dict:
        """Get block by height."""
        return self._get(f"/extended/v1/block/by_height/{height}")

    def get_block_by_hash(self, block_hash: str) -> dict:
        """Get block by hash."""
        return self._get(f"/extended/v1/block/{block_hash}")

    def get_block_by_burn_block_height(self, burn_block_height: int) -> dict:
        """Get block by burn block height."""
        return self._get(f"/extended/v1/block/by_burn_block_height/{burn_block_height}")

    # Address related endpoints
    def get_address_stx_balance(self, principal: str) -> dict:
        """Get STX balance."""
        return self._get(f"/extended/v1/address/{principal}/stx")

    def get_address_transactions(self, principal: str) -> dict:
        """Get transactions for an address."""
        return self._get(f"/extended/v1/address/{principal}/transactions")

    def get_address_transactions_with_transfers(self, principal: str) -> dict:
        """Get transactions with transfers."""
        return self._get(
            f"/extended/v1/address/{principal}/transactions_with_transfers"
        )

    def get_address_assets(self, principal: str) -> dict:
        """Get assets owned."""
        return self._get(f"/extended/v1/address/{principal}/assets")

    def get_address_mempool(self, principal: str) -> dict:
        """Get mempool transactions."""
        return self._get(f"/extended/v1/address/{principal}/mempool")

    def get_address_nonces(self, principal: str) -> dict:
        """Get nonce information."""
        return self._get(f"/extended/v1/address/{principal}/nonces")

    # Token related endpoints
    def get_nft_holdings(self, **params) -> dict:
        """Get NFT holdings."""
        return self._get("/extended/v1/tokens/nft/holdings", params=params)

    def get_nft_history(self, **params) -> dict:
        """Get NFT history."""
        return self._get("/extended/v1/tokens/nft/history", params=params)

    def get_nft_mints(self, **params) -> dict:
        """Get NFT mints."""
        return self._get("/extended/v1/tokens/nft/mints", params=params)

    # Contract related endpoints
    def get_contract_by_id(self, contract_id: str) -> dict:
        """Get contract details."""
        return self._get(f"/extended/v1/contract/{contract_id}")

    def get_contract_events(self, contract_id: str) -> dict:
        """Get contract events."""
        return self._get(f"/extended/v1/contract/{contract_id}/events")

    def get_contract_source(
        self, contract_address: str, contract_name: str
    ) -> Dict[str, Any]:
        """Get the source code of a contract.

        Args:
            contract_address: The contract's address
            contract_name: The name of the contract

        Returns:
            Dict containing the contract source code and metadata
        """
        response = self._get(f"/v2/contracts/source/{contract_address}/{contract_name}")
        return response.json()

    # Burnchain related endpoints
    def get_burnchain_rewards(self) -> dict:
        """Get burnchain rewards."""
        return self._get("/extended/v1/burnchain/rewards")

    def get_address_burnchain_rewards(self, address: str) -> dict:
        """Get burnchain rewards for an address."""
        return self._get(f"/extended/v1/burnchain/rewards/{address}")

    def get_address_total_burnchain_rewards(self, address: str) -> dict:
        """Get total burnchain rewards."""
        return self._get(f"/extended/v1/burnchain/rewards/{address}/total")

    # Utility endpoints
    def get_fee_rate(self) -> dict:
        """Get current fee rate."""
        return self._get("/extended/v1/fee_rate")

    def get_stx_supply(self) -> dict:
        """Get STX supply."""
        return self._get("/extended/v1/stx_supply")

    def get_stx_price(self) -> float:
        """Get the current STX price."""
        try:
            url = "https://explorer.hiro.so/stxPrice"
            params = {"blockBurnTime": "current"}
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()["price"]
        except Exception as e:
            raise Exception(f"Failed to get STX price: {str(e)}")

    def search(self, query_id: str) -> dict:
        """Search for blocks, transactions, contracts, or addresses."""
        return self._get(f"/extended/v1/search/{query_id}")
