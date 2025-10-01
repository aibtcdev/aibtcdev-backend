"""Helper utility functions for common operations."""

from typing import Optional, Tuple, Union
from decimal import Decimal

from ..models.chainhook import TransactionWithReceipt


def get_block_height_from_transaction(
    transaction: TransactionWithReceipt,
) -> Optional[int]:
    """Extract block height from transaction metadata.

    Note: Current chainhook format doesn't include block height in transaction.
    This is a placeholder for when that information is available.

    Args:
        transaction: Transaction to extract height from

    Returns:
        Optional[int]: Block height if available
    """
    # Placeholder - would need to be implemented when block height
    # is added to transaction metadata
    return None


def extract_contract_name(contract_identifier: str) -> Tuple[str, str]:
    """Extract address and contract name from contract identifier.

    Args:
        contract_identifier: Full contract identifier like "SP123...ABC.contract-name"

    Returns:
        Tuple[str, str]: (address, contract_name)

    Example:
        >>> extract_contract_name("SP1ABC123.my-contract")
        ("SP1ABC123", "my-contract")
    """
    if "." not in contract_identifier:
        return contract_identifier, ""

    address, contract_name = contract_identifier.split(".", 1)
    return address, contract_name


def format_stacks_address(address: str) -> str:
    """Format and validate a Stacks address.

    Args:
        address: Raw address string

    Returns:
        str: Formatted address

    Raises:
        ValueError: If address format is invalid
    """
    address = address.strip()

    # Basic validation
    if not address:
        raise ValueError("Address cannot be empty")

    # Check for valid Stacks address patterns
    if not (
        address.startswith("SP") or address.startswith("ST") or address.startswith("SM")
    ):
        raise ValueError(f"Invalid Stacks address prefix: {address}")

    # Check length (should be around 40-41 characters for mainnet/testnet)
    if len(address) < 35 or len(address) > 45:
        raise ValueError(f"Invalid Stacks address length: {address}")

    return address


def parse_stacks_amount(amount: Union[str, int], decimals: int = 6) -> Decimal:
    """Parse a Stacks token amount with proper decimal handling.

    Args:
        amount: Amount as string or integer (in microunits)
        decimals: Number of decimal places for the token

    Returns:
        Decimal: Parsed amount with correct decimal places

    Example:
        >>> parse_stacks_amount("1000000", 6)
        Decimal('1.000000')
    """
    if isinstance(amount, str):
        # Handle string amounts
        try:
            amount_int = int(amount)
        except ValueError:
            raise ValueError(f"Invalid amount format: {amount}")
    else:
        amount_int = int(amount)

    # Convert from microunits to full units
    divisor = 10**decimals
    return Decimal(amount_int) / Decimal(divisor)


def format_stacks_amount(amount: Union[Decimal, float, int], decimals: int = 6) -> str:
    """Format a Stacks amount for display.

    Args:
        amount: Amount to format
        decimals: Number of decimal places to show

    Returns:
        str: Formatted amount string

    Example:
        >>> format_stacks_amount(1.234567, 6)
        "1.234567"
    """
    if isinstance(amount, (int, float)):
        amount = Decimal(str(amount))

    # Format with specified decimal places
    format_str = f"{{:.{decimals}f}}"
    return format_str.format(float(amount))


def is_mainnet_address(address: str) -> bool:
    """Check if address is a mainnet address.

    Args:
        address: Stacks address to check

    Returns:
        bool: True if mainnet address
    """
    return address.startswith("SP") or address.startswith("SM")


def is_testnet_address(address: str) -> bool:
    """Check if address is a testnet address.

    Args:
        address: Stacks address to check

    Returns:
        bool: True if testnet address
    """
    return address.startswith("ST")


def extract_proposal_id_from_args(args: list) -> Optional[int]:
    """Extract proposal ID from contract call arguments.

    Args:
        args: List of contract call arguments

    Returns:
        Optional[int]: Proposal ID if found

    Example:
        >>> extract_proposal_id_from_args(["u31", "SP123.contract"])
        31
    """
    if not args:
        return None

    # Look for uint argument that looks like a proposal ID
    for arg in args:
        if isinstance(arg, str) and arg.startswith("u"):
            try:
                return int(arg[1:])
            except ValueError:
                continue

    return None


def normalize_contract_identifier(contract_id: str) -> str:
    """Normalize a contract identifier for consistent comparison.

    Args:
        contract_id: Contract identifier to normalize

    Returns:
        str: Normalized contract identifier
    """
    return contract_id.strip().lower()


def is_dao_contract(contract_identifier: str) -> bool:
    """Check if contract identifier appears to be a DAO contract.

    Args:
        contract_identifier: Contract to check

    Returns:
        bool: True if appears to be a DAO contract
    """
    contract_id_lower = contract_identifier.lower()

    dao_indicators = [
        "dao",
        "proposal",
        "voting",
        "governance",
        "treasury",
    ]

    return any(indicator in contract_id_lower for indicator in dao_indicators)


def extract_event_contract_id(event_data: dict) -> Optional[str]:
    """Extract contract identifier from event data.

    Args:
        event_data: Event data dictionary

    Returns:
        Optional[str]: Contract identifier if found
    """
    return event_data.get("contract_identifier") or event_data.get("contract_id")


def parse_clarity_bool(clarity_value: str) -> bool:
    """Parse a Clarity boolean value.

    Args:
        clarity_value: Clarity boolean as string ("true" or "false")

    Returns:
        bool: Parsed boolean value

    Raises:
        ValueError: If value is not a valid Clarity boolean
    """
    if clarity_value == "true":
        return True
    elif clarity_value == "false":
        return False
    else:
        raise ValueError(f"Invalid Clarity boolean: {clarity_value}")


def parse_clarity_uint(clarity_value: str) -> int:
    """Parse a Clarity uint value.

    Args:
        clarity_value: Clarity uint as string (e.g., "u123")

    Returns:
        int: Parsed integer value

    Raises:
        ValueError: If value is not a valid Clarity uint
    """
    if not clarity_value.startswith("u"):
        raise ValueError(f"Invalid Clarity uint format: {clarity_value}")

    try:
        return int(clarity_value[1:])
    except ValueError:
        raise ValueError(f"Invalid Clarity uint value: {clarity_value}")


def get_transaction_description_summary(description: str, max_length: int = 100) -> str:
    """Get a summary of transaction description for logging.

    Args:
        description: Full transaction description
        max_length: Maximum length of summary

    Returns:
        str: Truncated description with ellipsis if needed
    """
    if len(description) <= max_length:
        return description

    return description[: max_length - 3] + "..."


def validate_transaction_hash(tx_hash: str) -> bool:
    """Validate a transaction hash format.

    Args:
        tx_hash: Transaction hash to validate

    Returns:
        bool: True if hash format is valid
    """
    if not tx_hash:
        return False

    # Should start with 0x and be 64 hex characters
    if not tx_hash.startswith("0x"):
        return False

    if len(tx_hash) != 66:  # 0x + 64 hex chars
        return False

    # Check if remaining characters are valid hex
    hex_part = tx_hash[2:]
    return all(c in "0123456789abcdefABCDEF" for c in hex_part)


def safe_get_nested_value(data: dict, *keys, default=None):
    """Safely get a nested value from a dictionary.

    Args:
        data: Dictionary to search
        *keys: Sequence of keys for nested access
        default: Default value if key path doesn't exist

    Returns:
        Any: Value at the key path, or default if not found

    Example:
        >>> safe_get_nested_value({"a": {"b": {"c": 123}}}, "a", "b", "c")
        123
        >>> safe_get_nested_value({"a": {"b": {}}}, "a", "b", "c", default="missing")
        "missing"
    """
    try:
        result = data
        for key in keys:
            result = result[key]
        return result
    except (KeyError, TypeError):
        return default
