"""Clarity repr format parser for smart contract events."""

import re
from typing import Any, Dict, Optional, Union
import logging

from .base import BaseParser
from ..exceptions import ParseError


class ClarityParser(BaseParser):
    """
    Parser for Clarity repr format strings.

    This parser can handle various Clarity data structures including:
    - Tuples with named fields
    - Notification/payload patterns
    - Basic data types (uint, bool, strings, principal addresses)
    - Nested structures
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        """Initialize the Clarity parser."""
        super().__init__(logger)

    def parse(self, data: Any) -> Any:
        """Parse Clarity repr data.

        Args:
            data: Raw event value data from Stacks API

        Returns:
            Any: Parsed data structure

        Raises:
            ParseError: If parsing fails
        """
        if not isinstance(data, dict):
            return data

        # Check if this is Stacks API format with repr field
        repr_value = data.get("repr")
        if not repr_value or not isinstance(repr_value, str):
            return data

        try:
            # Parse specific patterns that handlers expect
            if "notification" in repr_value and "payload" in repr_value:
                return self._parse_notification_payload(repr_value)
            else:
                # For other formats, return the repr as-is for now
                # This can be extended to handle more Clarity patterns
                return self._parse_generic_tuple(repr_value)
        except Exception as e:
            self.logger.debug(f"Could not parse Clarity repr: {e}")
            raise ParseError(
                f"Failed to parse Clarity repr format: {e}",
                raw_data=repr_value,
                parser_type="clarity",
            ) from e

    def can_parse(self, data: Any) -> bool:
        """Check if this parser can handle the data.

        Args:
            data: Data to check

        Returns:
            bool: True if data appears to be Clarity repr format
        """
        if not isinstance(data, dict):
            return False

        repr_value = data.get("repr")
        if not isinstance(repr_value, str):
            return False

        # Look for Clarity patterns
        return (
            repr_value.startswith("(tuple ")
            or "notification" in repr_value
            or "payload" in repr_value
        )

    def _parse_notification_payload(self, repr_str: str) -> Dict[str, Any]:
        """Parse notification/payload tuple from Clarity repr format.

        This is the main parser for ActionConcluderHandler and similar handlers
        that expect {notification: "...", payload: {...}} format.

        Args:
            repr_str: Clarity repr string

        Returns:
            Dict[str, Any]: Parsed notification and payload
        """
        # Extract notification
        notification_match = re.search(r'notification "([^"]*)"', repr_str)
        notification = notification_match.group(1) if notification_match else ""

        # Use more precise parsing by looking for tuple elements
        payload = {}

        # Extract memo field first (has special "some" wrapper)
        memo_match = re.search(r'memo \\(some "([^"]+)"\\)', repr_str)
        if memo_match:
            payload["memo"] = memo_match.group(1)

        # Define field extractors with CORRECT boundary patterns (no closing quotes!)
        field_extractors = [
            # Contract identifiers - from quote until closing parenthesis
            ("action", r"action '([^)]+)\\)"),
            ("contractCaller", r"contractCaller '([^)]+)\\)"),
            ("creator", r"creator '([^)]+)\\)"),
            ("txSender", r"txSender '([^)]+)\\)"),
            # Uint fields (bounded by parentheses)
            ("proposalId", r"\\(proposalId u(\\d+)\\)"),
            ("status", r"\\(status u(\\d+)\\)"),
            ("votesFor", r"\\(votesFor u(\\d+)\\)"),
            ("votesAgainst", r"\\(votesAgainst u(\\d+)\\)"),
            ("bond", r"\\(bond u(\\d+)\\)"),
            ("liquidTokens", r"\\(liquidTokens u(\\d+)\\)"),
            ("vetoVotes", r"\\(vetoVotes u(\\d+)\\)"),
            # Boolean fields (bounded by parentheses)
            ("passed", r"\\(passed (true|false)\\)"),
            ("executed", r"\\(executed (true|false)\\)"),
            ("expired", r"\\(expired (true|false)\\)"),
            ("vetoed", r"\\(vetoed (true|false)\\)"),
            ("metQuorum", r"\\(metQuorum (true|false)\\)"),
            ("metThreshold", r"\\(metThreshold (true|false)\\)"),
            ("vetoExceedsYes", r"\\(vetoExceedsYes (true|false)\\)"),
            ("vetoMetQuorum", r"\\(vetoMetQuorum (true|false)\\)"),
            # Hex data (bounded by parentheses and space/paren)
            ("parameters", r"\\(parameters (0x[a-fA-F0-9]+)\\)"),
        ]

        for field_name, pattern in field_extractors:
            match = re.search(pattern, repr_str)
            if match:
                value = match.group(1)

                # Convert based on field type
                if field_name in [
                    "passed",
                    "executed",
                    "expired",
                    "vetoed",
                    "metQuorum",
                    "metThreshold",
                    "vetoExceedsYes",
                    "vetoMetQuorum",
                ]:
                    payload[field_name] = value == "true"
                elif field_name in [
                    "proposalId",
                    "status",
                    "votesFor",
                    "votesAgainst",
                    "bond",
                    "liquidTokens",
                    "vetoVotes",
                ]:
                    payload[field_name] = int(value)
                else:
                    payload[field_name] = value

        return {"notification": notification, "payload": payload}

    def _parse_generic_tuple(self, repr_str: str) -> Union[str, Dict[str, Any]]:
        """Parse a generic Clarity tuple.

        This is a fallback parser for tuple structures that don't match
        the notification/payload pattern.

        Args:
            repr_str: Clarity repr string

        Returns:
            Union[str, Dict[str, Any]]: Parsed tuple or original string
        """
        # For now, return the original string
        # This can be extended to parse more complex Clarity structures
        return repr_str

    def parse_uint(self, value_str: str) -> int:
        """Parse a Clarity uint value.

        Args:
            value_str: String like "u123"

        Returns:
            int: Parsed integer value

        Raises:
            ParseError: If parsing fails
        """
        if not value_str.startswith("u"):
            raise ParseError(f"Invalid uint format: {value_str}")

        try:
            return int(value_str[1:])
        except ValueError as e:
            raise ParseError(f"Cannot parse uint: {value_str}") from e

    def parse_bool(self, value_str: str) -> bool:
        """Parse a Clarity boolean value.

        Args:
            value_str: String "true" or "false"

        Returns:
            bool: Parsed boolean value

        Raises:
            ParseError: If parsing fails
        """
        if value_str == "true":
            return True
        elif value_str == "false":
            return False
        else:
            raise ParseError(f"Invalid boolean format: {value_str}")

    def parse_principal(self, value_str: str) -> str:
        """Parse a Clarity principal (address).

        Args:
            value_str: String like "'SP1ABC...'"

        Returns:
            str: Parsed principal address

        Raises:
            ParseError: If parsing fails
        """
        # Remove surrounding quotes
        if value_str.startswith("'") and value_str.endswith("'"):
            return value_str[1:-1]

        return value_str

    def parse_string_literal(self, value_str: str) -> str:
        """Parse a Clarity string literal.

        Args:
            value_str: String like '"hello world"'

        Returns:
            str: Parsed string content
        """
        # Remove surrounding quotes
        if value_str.startswith('"') and value_str.endswith('"'):
            return value_str[1:-1]

        return value_str

    def parse_optional(self, value_str: str) -> Optional[Any]:
        """Parse a Clarity optional value.

        Args:
            value_str: String like "(some value)" or "none"

        Returns:
            Optional[Any]: Parsed optional value
        """
        if value_str == "none":
            return None

        # Parse (some ...) pattern
        some_match = re.match(r"\\(some (.+)\\)", value_str)
        if some_match:
            inner_value = some_match.group(1)
            # Recursively parse the inner value
            return self._parse_value(inner_value)

        return value_str

    def _parse_value(self, value_str: str) -> Any:
        """Parse a generic Clarity value.

        Args:
            value_str: Raw value string

        Returns:
            Any: Parsed value
        """
        value_str = value_str.strip()

        # Try different parsing strategies
        if value_str.startswith("u") and value_str[1:].isdigit():
            return self.parse_uint(value_str)
        elif value_str in ("true", "false"):
            return self.parse_bool(value_str)
        elif value_str.startswith("'"):
            return self.parse_principal(value_str)
        elif value_str.startswith('"'):
            return self.parse_string_literal(value_str)
        elif value_str.startswith("0x"):
            return value_str  # Hex data
        elif value_str == "none" or value_str.startswith("(some "):
            return self.parse_optional(value_str)

        # Default: return as-is
        return value_str
