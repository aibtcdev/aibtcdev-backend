"""Transaction filtering functionality for the Stacks Chainhook Adapter."""

import re
from abc import ABC, abstractmethod
from typing import List, Optional, Union, Pattern

from ..models.chainhook import TransactionWithReceipt


class BaseTransactionFilter(ABC):
    """Abstract base class for transaction filters."""

    @abstractmethod
    def matches(self, transaction: TransactionWithReceipt) -> bool:
        """Check if the transaction matches this filter.

        Args:
            transaction: Transaction to check

        Returns:
            bool: True if transaction matches the filter
        """
        pass

    def get_filter_description(self) -> str:
        """Get a human-readable description of this filter.

        Returns:
            str: Filter description
        """
        return self.__class__.__name__


class ContractCallFilter(BaseTransactionFilter):
    """Filter for contract call transactions."""

    def __init__(
        self,
        contract_identifier: Optional[str] = None,
        method: Optional[str] = None,
        contract_pattern: Optional[Union[str, Pattern]] = None,
        method_pattern: Optional[Union[str, Pattern]] = None,
        success_only: bool = True,
    ) -> None:
        """Initialize the contract call filter.

        Args:
            contract_identifier: Exact contract identifier to match
            method: Exact method name to match
            contract_pattern: Regex pattern for contract identifier
            method_pattern: Regex pattern for method name
            success_only: Only match successful transactions
        """
        self.contract_identifier = contract_identifier
        self.method = method
        self.success_only = success_only

        # Compile regex patterns
        if isinstance(contract_pattern, str):
            self.contract_pattern = re.compile(contract_pattern)
        else:
            self.contract_pattern = contract_pattern

        if isinstance(method_pattern, str):
            self.method_pattern = re.compile(method_pattern)
        else:
            self.method_pattern = method_pattern

    def matches(self, transaction: TransactionWithReceipt) -> bool:
        """Check if transaction matches contract call criteria."""
        try:
            # Check transaction type
            if transaction.metadata.kind.type != "ContractCall":
                return False

            # Check success status
            if self.success_only and not transaction.metadata.success:
                return False

            # Get contract call data
            contract_data = transaction.metadata.kind.data
            tx_contract = contract_data.get("contract_identifier", "")
            tx_method = contract_data.get("method", "")

            # Check exact contract identifier
            if self.contract_identifier and tx_contract != self.contract_identifier:
                return False

            # Check exact method
            if self.method and tx_method != self.method:
                return False

            # Check contract pattern
            if self.contract_pattern and not self.contract_pattern.search(tx_contract):
                return False

            # Check method pattern
            if self.method_pattern and not self.method_pattern.search(tx_method):
                return False

            return True

        except Exception:
            return False

    def get_filter_description(self) -> str:
        """Get filter description."""
        parts = []
        if self.contract_identifier:
            parts.append(f"contract={self.contract_identifier}")
        if self.method:
            parts.append(f"method={self.method}")
        if self.contract_pattern:
            parts.append(f"contract_pattern={self.contract_pattern.pattern}")
        if self.method_pattern:
            parts.append(f"method_pattern={self.method_pattern.pattern}")
        if self.success_only:
            parts.append("success_only=True")

        return f"ContractCallFilter({', '.join(parts)})"


class EventTypeFilter(BaseTransactionFilter):
    """Filter transactions by event types they contain."""

    def __init__(
        self,
        event_types: List[str],
        require_all: bool = False,
        min_event_count: int = 1,
    ) -> None:
        """Initialize the event type filter.

        Args:
            event_types: List of event types to match
            require_all: If True, transaction must have ALL event types
            min_event_count: Minimum number of matching events required
        """
        self.event_types = set(event_types)
        self.require_all = require_all
        self.min_event_count = min_event_count

    def matches(self, transaction: TransactionWithReceipt) -> bool:
        """Check if transaction contains required event types."""
        try:
            # Get all event types in the transaction
            tx_event_types = {
                event.type for event in transaction.metadata.receipt.events
            }

            if self.require_all:
                # Must have all required event types
                return self.event_types.issubset(tx_event_types)
            else:
                # Must have at least one required event type
                matching_events = [
                    event
                    for event in transaction.metadata.receipt.events
                    if event.type in self.event_types
                ]
                return len(matching_events) >= self.min_event_count

        except Exception:
            return False

    def get_filter_description(self) -> str:
        """Get filter description."""
        return f"EventTypeFilter(types={list(self.event_types)}, require_all={self.require_all}, min_count={self.min_event_count})"


class BlockHeightRangeFilter(BaseTransactionFilter):
    """Filter transactions by block height range."""

    def __init__(
        self,
        min_height: Optional[int] = None,
        max_height: Optional[int] = None,
    ) -> None:
        """Initialize the block height range filter.

        Args:
            min_height: Minimum block height (inclusive)
            max_height: Maximum block height (inclusive)
        """
        self.min_height = min_height
        self.max_height = max_height

    def matches(self, transaction: TransactionWithReceipt) -> bool:
        """Check if transaction is in the specified block height range."""
        # Note: This filter would need block height information to be added
        # to the TransactionWithReceipt model, or passed separately
        # For now, this is a placeholder implementation
        return True

    def get_filter_description(self) -> str:
        """Get filter description."""
        return f"BlockHeightRangeFilter(min={self.min_height}, max={self.max_height})"


class MethodFilter(BaseTransactionFilter):
    """Filter for specific contract methods (simplified ContractCallFilter)."""

    def __init__(
        self, methods: Union[str, List[str]], success_only: bool = True
    ) -> None:
        """Initialize the method filter.

        Args:
            methods: Method name(s) to match
            success_only: Only match successful transactions
        """
        if isinstance(methods, str):
            self.methods = {methods}
        else:
            self.methods = set(methods)

        self.success_only = success_only

    def matches(self, transaction: TransactionWithReceipt) -> bool:
        """Check if transaction calls one of the specified methods."""
        try:
            # Check transaction type
            if transaction.metadata.kind.type != "ContractCall":
                return False

            # Check success status
            if self.success_only and not transaction.metadata.success:
                return False

            # Check method
            method = transaction.metadata.kind.data.get("method", "")
            return method in self.methods

        except Exception:
            return False

    def get_filter_description(self) -> str:
        """Get filter description."""
        return f"MethodFilter(methods={list(self.methods)}, success_only={self.success_only})"


class CompositeFilter(BaseTransactionFilter):
    """Combine multiple filters with AND/OR logic."""

    def __init__(
        self,
        filters: List[BaseTransactionFilter],
        logic: str = "AND",
    ) -> None:
        """Initialize the composite filter.

        Args:
            filters: List of filters to combine
            logic: Combination logic ("AND" or "OR")
        """
        self.filters = filters
        self.logic = logic.upper()

        if self.logic not in ("AND", "OR"):
            raise ValueError("Logic must be 'AND' or 'OR'")

    def matches(self, transaction: TransactionWithReceipt) -> bool:
        """Check if transaction matches the composite filter."""
        if not self.filters:
            return True

        if self.logic == "AND":
            return all(f.matches(transaction) for f in self.filters)
        else:  # OR
            return any(f.matches(transaction) for f in self.filters)

    def get_filter_description(self) -> str:
        """Get filter description."""
        filter_descriptions = [f.get_filter_description() for f in self.filters]
        return (
            f"CompositeFilter({self.logic}, filters=[{', '.join(filter_descriptions)}])"
        )


# Convenience function for common filter combinations
def create_conclude_proposal_filter(
    contract_pattern: Optional[str] = None,
    success_only: bool = True,
) -> ContractCallFilter:
    """Create a filter for conclude-action-proposal transactions.

    Args:
        contract_pattern: Optional pattern to match contract identifier
        success_only: Only match successful transactions

    Returns:
        ContractCallFilter: Configured filter for conclude-action-proposal
    """
    return ContractCallFilter(
        method="conclude-action-proposal",
        contract_pattern=contract_pattern or r".*action-proposal-voting.*",
        success_only=success_only,
    )


def create_dao_proposal_filter(success_only: bool = True) -> CompositeFilter:
    """Create a filter for DAO proposal-related transactions.

    Args:
        success_only: Only match successful transactions

    Returns:
        CompositeFilter: Configured filter for DAO proposals
    """
    propose_filter = ContractCallFilter(
        method="propose-action",
        success_only=success_only,
    )

    conclude_filter = create_conclude_proposal_filter(success_only=success_only)

    vote_filter = ContractCallFilter(
        method_pattern=r"vote.*",
        success_only=success_only,
    )

    return CompositeFilter([propose_filter, conclude_filter, vote_filter], logic="OR")
