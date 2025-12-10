"""Utility functions for the quorum-aware lottery system."""

from decimal import Decimal, ROUND_UP
from typing import Dict, List
from uuid import UUID

from app.backend.models import AgentWithWalletTokenDTO
from app.lib.logger import configure_logger

logger = configure_logger(__name__)


class QuorumCalculator:
    """Utility class for quorum calculations and validation."""

    @staticmethod
    def calculate_quorum_threshold(
        liquid_tokens: str, quorum_percentage: float = 0.15
    ) -> str:
        """Calculate the quorum threshold from liquid tokens.

        Args:
            liquid_tokens: Total liquid token supply as string
            quorum_percentage: Percentage for quorum (default 15% = 0.15)

        Returns:
            Quorum threshold as string for precise decimal handling
        """
        try:
            liquid_decimal = Decimal(liquid_tokens)
            threshold = liquid_decimal * Decimal(str(quorum_percentage))
            # Round up to ensure we meet the minimum threshold
            return str(threshold.quantize(Decimal("1"), rounding=ROUND_UP))
        except (ValueError, TypeError) as e:
            logger.error(f"Error calculating quorum threshold: {e}")
            return "0"

    @staticmethod
    def calculate_total_eligible_tokens(
        agents_with_tokens: List[AgentWithWalletTokenDTO],
    ) -> str:
        """Calculate total tokens available from all eligible agents.

        Args:
            agents_with_tokens: List of agents with their token amounts

        Returns:
            Total available tokens as string
        """
        try:
            total = Decimal("0")
            for agent in agents_with_tokens:
                total += Decimal(agent.token_amount)
            return str(total)
        except (ValueError, TypeError) as e:
            logger.error(f"Error calculating total eligible tokens: {e}")
            return "0"


class LotterySelection:
    """Data class to hold lottery selection results."""

    def __init__(self):
        self.selected_wallets: List[Dict[str, str]] = []
        self.total_selected_tokens: str = "0"
        self.quorum_achieved: bool = False
        self.selection_rounds: int = 0
        self.total_eligible_wallets: int = 0
        self.total_eligible_tokens: str = "0"
        self.quorum_threshold: str = "0"
        self.liquid_tokens_at_creation: str = "0"
        self.quorum_percentage: float = 0.15

    def to_dict(self) -> Dict:
        """Convert to dictionary for database storage."""
        return {
            "selected_wallets": self.selected_wallets,
            "total_selected_tokens": self.total_selected_tokens,
            "quorum_achieved": self.quorum_achieved,
            "selection_rounds": self.selection_rounds,
            "total_eligible_wallets": self.total_eligible_wallets,
            "total_eligible_tokens": self.total_eligible_tokens,
            "quorum_threshold": self.quorum_threshold,
            "liquid_tokens_at_creation": self.liquid_tokens_at_creation,
            "quorum_percentage": self.quorum_percentage,
        }


def extract_wallet_ids_from_selection(
    selected_wallets: List[Dict[str, str]],
) -> List[UUID]:
    """Extract wallet IDs from selected_wallets for backward compatibility.

    Args:
        selected_wallets: List of {"wallet_id": str, "token_amount": str} dicts

    Returns:
        List of UUID wallet IDs
    """
    wallet_ids = []
    for wallet in selected_wallets:
        try:
            wallet_id = UUID(wallet.get("wallet_id", ""))
            wallet_ids.append(wallet_id)
        except (ValueError, TypeError) as e:
            logger.warning(
                f"Invalid wallet_id in selection: {wallet.get('wallet_id')}, error: {e}"
            )
    return wallet_ids


def create_wallet_selection_dict(wallet_id: UUID, token_amount: str) -> Dict[str, str]:
    """Create a standardized wallet selection dictionary.

    Args:
        wallet_id: Wallet UUID
        token_amount: Token amount as string

    Returns:
        Dictionary with wallet_id and token_amount as strings
    """
    return {"wallet_id": str(wallet_id), "token_amount": str(token_amount)}
