"""Workflow utility functions."""

import binascii
import json
import re
from typing import Any, Dict, List, Optional

import httpx

from app.lib.logger import configure_logger

logger = configure_logger(__name__)


def split_text_into_chunks(text: str, limit: int = 280) -> List[str]:
    """Split text into chunks not exceeding the limit without cutting words.

    Args:
        text: The text to split into chunks
        limit: Maximum character limit per chunk (default 280 for Twitter)

    Returns:
        List of text chunks, each under the limit
    """
    if not text or not text.strip():
        return []

    words = text.split()
    chunks = []
    current = ""

    for word in words:
        # Check if adding this word would exceed the limit
        test_length = len(current) + len(word) + (1 if current else 0)
        if test_length <= limit:
            current = f"{current} {word}".strip()
        else:
            # Current chunk is full, start a new one
            if current:
                chunks.append(current)
            current = word

    # Add the final chunk if it exists
    if current:
        chunks.append(current)

    return chunks


def create_message_chunks(
    main_message: str,
    follow_up_message: Optional[str] = None,
    limit: int = 280,
    add_indices: bool = True,
    append_to_each: bool = False,
) -> List[str]:
    """Create an array of message chunks from main message and optional follow-up.

    Args:
        main_message: The primary message content
        follow_up_message: Optional follow-up message to append
        limit: Maximum character limit per chunk (default 280 for Twitter)
        add_indices: Whether to add thread indices like "(1/4)" to each chunk
        append_to_each: If True, append follow_up_message to each chunk instead of creating separate chunks

    Returns:
        List of chunked messages ready for sequential posting
    """
    chunks = []

    # Chunk the main message
    if main_message and main_message.strip():
        main_chunks = split_text_into_chunks(main_message.strip(), limit)
        chunks.extend(main_chunks)

    # Handle follow-up message based on append_to_each flag
    if follow_up_message and follow_up_message.strip():
        if append_to_each and chunks:
            # When appending to each chunk, we need to optimize space usage
            separator = "\n\n"
            follow_up_with_separator = f"{separator}{follow_up_message.strip()}"

            # Start with initial chunks and iteratively optimize
            optimized_chunks = []
            main_text = main_message.strip()
            words = main_text.split()
            word_index = 0
            chunk_number = 1

            while word_index < len(words):
                # Estimate the index text for this chunk (we'll refine this)
                estimated_total_chunks = max(len(chunks), chunk_number)
                temp_index_text = (
                    f"({chunk_number}/{estimated_total_chunks}) " if add_indices else ""
                )

                # Calculate available space for main content in this chunk
                reserved_space = len(follow_up_with_separator) + len(temp_index_text)
                available_main_space = limit - reserved_space

                # Build the chunk by adding words until we approach the limit
                current_chunk = ""
                chunk_words = []

                while word_index < len(words):
                    word = words[word_index]
                    test_chunk = (
                        f"{current_chunk} {word}".strip() if current_chunk else word
                    )

                    if len(test_chunk) <= available_main_space:
                        current_chunk = test_chunk
                        chunk_words.append(word)
                        word_index += 1
                    else:
                        break

                # If we couldn't fit any words, force at least one word to prevent infinite loop
                if not chunk_words and word_index < len(words):
                    current_chunk = words[word_index]
                    word_index += 1

                optimized_chunks.append(current_chunk)
                chunk_number += 1

            # Now we know the exact number of chunks, create final versions with correct indices
            total_chunks = len(optimized_chunks)
            final_chunks = []

            for i, chunk in enumerate(optimized_chunks, 1):
                # Calculate exact index text at the beginning
                index_text = (
                    f"({i}/{total_chunks}) " if add_indices and total_chunks > 1 else ""
                )

                # Calculate exact available space for this specific chunk
                reserved_space = len(follow_up_with_separator) + len(index_text)
                available_main_space = limit - reserved_space

                # Trim chunk if needed to fit exactly (shouldn't happen often with our optimization)
                if len(chunk) > available_main_space:
                    words = chunk.split()
                    trimmed_chunk = ""

                    for word in words:
                        test_length = (
                            len(trimmed_chunk) + len(word) + (1 if trimmed_chunk else 0)
                        )
                        if test_length <= available_main_space:
                            trimmed_chunk = f"{trimmed_chunk} {word}".strip()
                        else:
                            break

                    chunk = trimmed_chunk

                # Create the final chunk with index at the beginning - should be as close to 280 as possible
                final_chunk = f"{index_text}{chunk}{follow_up_with_separator}"

                # Verify we didn't exceed the limit (safety check)
                if len(final_chunk) > limit:
                    # This shouldn't happen, but if it does, we need to trim more aggressively
                    excess = len(final_chunk) - limit
                    words = chunk.split()
                    while words and excess > 0:
                        removed_word = words.pop()
                        excess -= len(removed_word) + 1  # +1 for space

                    chunk = " ".join(words)
                    final_chunk = f"{index_text}{chunk}{follow_up_with_separator}"

                final_chunks.append(final_chunk)

            return final_chunks
        else:
            # Add follow-up as separate chunks (original behavior)
            follow_up_chunks = split_text_into_chunks(follow_up_message.strip(), limit)
            chunks.extend(follow_up_chunks)

    # Add thread indices if requested and we have multiple chunks (for non-append_to_each case)
    if add_indices and len(chunks) > 1 and not (append_to_each and follow_up_message):
        indexed_chunks = []
        total_chunks = len(chunks)

        for i, chunk in enumerate(chunks, 1):
            # Calculate space needed for index at the beginning like "(3/4) "
            index_text = f"({i}/{total_chunks}) "
            index_length = len(index_text)

            # If adding the index would exceed the limit, trim the chunk
            if len(chunk) + index_length > limit:
                # Trim the chunk to make room for the index, ensuring we don't cut words
                available_space = limit - index_length
                words = chunk.split()
                trimmed_chunk = ""

                for word in words:
                    test_length = (
                        len(trimmed_chunk) + len(word) + (1 if trimmed_chunk else 0)
                    )
                    if test_length <= available_space:
                        trimmed_chunk = f"{trimmed_chunk} {word}".strip()
                    else:
                        break

                chunk = trimmed_chunk

            # Add the index to the beginning of the chunk
            indexed_chunk = f"{index_text}{chunk}"
            indexed_chunks.append(indexed_chunk)

        return indexed_chunks

    return chunks


def extract_image_urls(text: str) -> List[str]:
    """
    Extracts image URLs from a string by making HEAD requests to verify Content-Type.

    Args:
        text: The input string to search for URLs.

    Returns:
        A list of verified image URLs found in the string.
    """
    # Find all https URLs in the text
    url_pattern = re.compile(r'https://[^\s<>"\'()]+', re.IGNORECASE)
    urls = re.findall(url_pattern, text)

    if not urls:
        return []

    image_urls = []

    # Common image MIME types to check for
    image_mime_types = {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/gif",
        "image/webp",
        "image/bmp",
        "image/svg+xml",
        "image/tiff",
        "image/ico",
        "image/x-icon",
    }

    # Use httpx for better async support and modern HTTP handling
    try:
        with httpx.Client(
            timeout=httpx.Timeout(5.0, connect=2.0),  # 5s total, 2s connect
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ImageBot/1.0)"},
        ) as client:
            for url in urls:
                try:
                    # Make HEAD request to check Content-Type without downloading the file
                    response = client.head(url)

                    if response.status_code == 200:
                        content_type = (
                            response.headers.get("Content-Type", "")
                            .lower()
                            .split(";")[0]
                            .strip()
                        )

                        # Check if it's an image type
                        if content_type in image_mime_types:
                            image_urls.append(url)
                            logger.debug(
                                "Image URL found",
                                extra={"url": url, "content_type": content_type},
                            )
                        else:
                            logger.debug(
                                "Non-image URL skipped",
                                extra={"url": url, "content_type": content_type},
                            )
                    else:
                        logger.debug(
                            "URL access failed",
                            extra={"url": url, "status_code": response.status_code},
                        )

                except httpx.TimeoutException:
                    logger.debug("URL check timeout", extra={"url": url})
                except httpx.RequestError as e:
                    logger.debug(
                        "URL request error", extra={"url": url, "error": str(e)}
                    )
                except Exception as e:
                    logger.debug(
                        "Unexpected URL check error",
                        extra={"url": url, "error": str(e)},
                    )

    except Exception as e:
        logger.error("HTTP client initialization failed", extra={"error": str(e)})
        return []

    logger.debug(
        "Image URL extraction completed",
        extra={"image_urls_found": len(image_urls), "total_urls_checked": len(urls)},
    )
    return image_urls


def strip_metadata_section(text: str) -> str:
    """Remove metadata section starting with '--- Metadata ---' to the end of the text.

    Args:
        text: The input text that may contain a metadata section

    Returns:
        The text with the metadata section removed
    """
    metadata_pattern = r"--- Metadata ---.*$"
    # Remove from '--- Metadata ---' to the end, including the marker
    return re.sub(metadata_pattern, "", text, flags=re.DOTALL).rstrip()


def decode_hex_parameters(hex_string: Optional[str]) -> Optional[str]:
    """Decodes a hexadecimal-encoded string if valid.

    Args:
        hex_string: The hexadecimal string to decode.

    Returns:
        The decoded string, or None if decoding fails.
    """
    if not hex_string:
        return None
    if hex_string.startswith("0x"):
        hex_string = hex_string[2:]  # Remove "0x" prefix
    try:
        decoded_bytes = binascii.unhexlify(hex_string)

        # Handle Clarity hex format with various string prefixes
        if len(decoded_bytes) > 5:
            # Try common Clarity string prefixes
            if decoded_bytes[0] == 0x0D:  # Most common string type
                decoded_bytes = decoded_bytes[5:]
            elif len(decoded_bytes) > 1:
                # Try skipping first few bytes for other formats
                decoded_bytes = decoded_bytes[1:]

        # ROBUST CLEANUP: Remove any remaining non-printable ASCII characters at the start
        # This handles cases where prefix bytes are left behind (like &, >, 5, ` etc.)
        while decoded_bytes and not (32 <= decoded_bytes[0] <= 126):
            decoded_bytes = decoded_bytes[1:]

        decoded_string = decoded_bytes.decode("utf-8", errors="ignore").strip()
        logger.debug(
            "Hex string decoded successfully",
            extra={"hex_preview": hex_string[:20] + "..."},
        )
        return decoded_string
    except (binascii.Error, UnicodeDecodeError) as e:
        logger.warning(
            "Hex string decoding failed",
            extra={
                "error": str(e),
                "hex_preview": hex_string[:20] + "..." if hex_string else "None",
            },
        )
        return None  # Return None if decoding fails


def parse_agent_tool_result(tool_result: Dict[str, Any]) -> Dict[str, Any]:
    """Parse agent tool _arun result into standardized format.

    Agent tools (TypeScript) return results in ToolResponse<T> format:
    {
        "success": boolean,
        "message": string,
        "data": T,  // Contains tool-specific data like txid
        "output": string | dict  // Raw output that may contain the ToolResponse
    }

    Args:
        tool_result: The result dictionary from agent tool _arun method

    Returns:
        Parsed result dictionary with standardized structure

    Raises:
        ValueError: If result cannot be parsed or is invalid
    """
    if not tool_result or not isinstance(tool_result, dict):
        raise ValueError("Tool result must be a non-empty dictionary")

    # Extract the output field which contains the actual ToolResponse
    output = tool_result.get("output")
    if not output:
        logger.debug("No output field in tool result, returning as-is")
        return tool_result

    try:
        # Parse output if it's a JSON string
        if isinstance(output, str):
            try:
                parsed_output = json.loads(output)
            except json.JSONDecodeError as e:
                logger.debug("Tool output JSON parse failed", extra={"error": str(e)})
                # Return original tool_result if output can't be parsed
                return tool_result
        else:
            parsed_output = output

        # Check if parsed output has ToolResponse structure
        if isinstance(parsed_output, dict) and "success" in parsed_output:
            # This looks like a ToolResponse, extract data from it
            result = {
                "success": parsed_output.get("success", False),
                "message": parsed_output.get("message", ""),
                "data": parsed_output.get("data", {}),
                "raw_output": output,  # Keep original for debugging
            }

            # Also include any additional fields from the original tool_result
            for key, value in tool_result.items():
                if key not in result and key != "output":
                    result[key] = value

            return result
        else:
            # Output doesn't have ToolResponse structure, return original
            logger.debug("Output missing ToolResponse structure")
            return tool_result

    except Exception as e:
        logger.error("Agent tool result parsing failed", extra={"error": str(e)})
        # Return original tool_result if parsing fails
        return tool_result


def extract_transaction_id_from_tool_result(
    tool_result: Dict[str, Any], fallback_regex_pattern: Optional[str] = None
) -> Optional[str]:
    """Extract transaction ID from agent tool result with proper formatting.

    Args:
        tool_result: The result dictionary from agent tool _arun method
        fallback_regex_pattern: Optional regex pattern for fallback extraction

    Returns:
        Transaction ID with proper 0x prefix, or None if not found

    Examples:
        >>> result = {"output": '{"success": true, "data": {"txid": "abcd1234"}}'}
        >>> extract_transaction_id_from_tool_result(result)
        "0xabcd1234"

        >>> result = {"output": "Transaction broadcasted successfully: 0xabcd1234"}
        >>> extract_transaction_id_from_tool_result(
        ...     result, r"successfully: (0x[a-fA-F0-9]+)"
        ... )
        "0xabcd1234"
    """
    try:
        # First try to parse using standard ToolResponse format
        parsed_result = parse_agent_tool_result(tool_result)

        # Look for txid in the data field
        if "data" in parsed_result and isinstance(parsed_result["data"], dict):
            raw_tx_id = parsed_result["data"].get("txid")

            if raw_tx_id:
                # Ensure tx_id always has 0x prefix
                tx_id = raw_tx_id if raw_tx_id.startswith("0x") else f"0x{raw_tx_id}"
                logger.debug(
                    "Transaction ID extracted from data field", extra={"tx_id": tx_id}
                )
                return tx_id

        # If not found in data field, try to extract from raw output using regex
        if fallback_regex_pattern:
            output = tool_result.get("output", "")
            if isinstance(output, str):
                match = re.search(fallback_regex_pattern, output)
                if match:
                    raw_tx_id = match.group(1)
                    # Ensure tx_id always has 0x prefix
                    tx_id = (
                        raw_tx_id if raw_tx_id.startswith("0x") else f"0x{raw_tx_id}"
                    )
                    logger.debug(
                        "Transaction ID extracted using regex fallback",
                        extra={"tx_id": tx_id},
                    )
                    return tx_id

        logger.debug("No transaction ID found in tool result")
        return None

    except Exception as e:
        logger.error("Transaction ID extraction failed", extra={"error": str(e)})
        return None


def ensure_tx_id_prefix(tx_id: Optional[str]) -> Optional[str]:
    """Ensure transaction ID has proper 0x prefix.

    Args:
        tx_id: The transaction ID string

    Returns:
        Transaction ID with 0x prefix, or None if input is None/empty
    """
    if not tx_id:
        return None

    return tx_id if tx_id.startswith("0x") else f"0x{tx_id}"


# Model pricing data (move this to a config or constants file later if needed)
MODEL_PRICES = {
    "gpt-4o": {
        "input": 2.50,  # $2.50 per million input tokens
        "output": 10.00,  # $10.00 per million output tokens
    },
    "gpt-4.1": {
        "input": 2.00,  # $2.00 per million input tokens
        "output": 8.00,  # $8.00 per million output tokens
    },
    "gpt-4.1-mini": {
        "input": 0.40,  # $0.40 per million input tokens
        "output": 1.60,  # $1.60 per million output tokens
    },
    "gpt-4.1-nano": {
        "input": 0.10,  # $0.10 per million input tokens
        "output": 0.40,  # $0.40 per million output tokens
    },
    # Default to gpt-4.1 pricing if model not found
    "default": {
        "input": 2.00,
        "output": 8.00,
    },
}


def calculate_token_cost(
    token_usage: Dict[str, int], model_name: str
) -> Dict[str, float]:
    """Calculate the cost of token usage based on current pricing.

    Args:
        token_usage: Dictionary containing input_tokens and output_tokens
        model_name: Name of the model used

    Returns:
        Dictionary containing cost breakdown and total cost
    """
    # Get pricing for the model, default to gpt-4.1 pricing if not found
    model_prices = MODEL_PRICES.get(model_name.lower(), MODEL_PRICES["default"])

    # Extract token counts, ensuring we get integers and handle None values
    try:
        input_tokens = int(token_usage.get("input_tokens", 0))
        output_tokens = int(token_usage.get("output_tokens", 0))
    except (TypeError, ValueError) as e:
        logger.warning(
            "Token count conversion failed",
            extra={
                "error": str(e),
                "input_tokens": token_usage.get("input_tokens"),
                "output_tokens": token_usage.get("output_tokens"),
            },
        )
        input_tokens = 0
        output_tokens = 0

    # Calculate costs with more precision
    input_cost = (input_tokens / 1_000_000.0) * model_prices["input"]
    output_cost = (output_tokens / 1_000_000.0) * model_prices["output"]
    total_cost = input_cost + output_cost

    # Create detailed token usage breakdown
    token_details = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "model_name": model_name,
        "input_price_per_million": model_prices["input"],
        "output_price_per_million": model_prices["output"],
    }

    # Add token details if available
    if "input_token_details" in token_usage:
        token_details["input_token_details"] = token_usage["input_token_details"]
    if "output_token_details" in token_usage:
        token_details["output_token_details"] = token_usage["output_token_details"]

    # Debug logging with structured data
    logger.debug(
        "Token cost calculated",
        extra={
            "model": model_name,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "input_cost": round(input_cost, 6),
            "output_cost": round(output_cost, 6),
            "total_cost": round(total_cost, 6),
            "event_type": "token_cost_calculation",
        },
    )

    return {
        "input_cost": round(input_cost, 6),
        "output_cost": round(output_cost, 6),
        "total_cost": round(total_cost, 6),
        "currency": "USD",
        "details": token_details,
    }


async def validate_wallet_recipients(recipients: List[str]) -> Dict[str, bool]:
    """Validate recipients against the wallets table using network-specific filtering.

    Args:
        recipients: List of recipient addresses to validate

    Returns:
        Dict mapping each recipient to whether it exists in wallets table
    """
    if not recipients:
        return {}

    # Import here to avoid circular imports
    from app.config import config
    from app.backend.factory import backend
    from app.backend.models import WalletFilterN

    # Determine which network to check based on config
    use_mainnet = config.network.network == "mainnet"

    # Query wallets table for all recipients at once, filtering by the appropriate network
    if use_mainnet:
        wallet_filter = WalletFilterN(mainnet_addresses=recipients)
    else:
        wallet_filter = WalletFilterN(testnet_addresses=recipients)

    wallets = backend.list_wallets_n(filters=wallet_filter)

    # Create set of valid addresses for efficient lookup
    if use_mainnet:
        valid_addresses = {w.mainnet_address for w in wallets if w.mainnet_address}
    else:
        valid_addresses = {w.testnet_address for w in wallets if w.testnet_address}

    # Check each recipient
    validation_results = {}
    for recipient in recipients:
        validation_results[recipient] = recipient in valid_addresses

    return validation_results
