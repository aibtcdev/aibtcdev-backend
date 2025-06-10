"""Workflow utility functions."""

import binascii
import logging
import re
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


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
                                f"Found image URL: {url} (Content-Type: {content_type})"
                            )
                        else:
                            logger.debug(
                                f"Skipped non-image URL: {url} (Content-Type: {content_type})"
                            )
                    else:
                        logger.debug(
                            f"Failed to access URL: {url} (Status: {response.status_code})"
                        )

                except httpx.TimeoutException:
                    logger.debug(f"Timeout checking URL: {url}")
                except httpx.RequestError as e:
                    logger.debug(f"Request error checking URL {url}: {str(e)}")
                except Exception as e:
                    logger.debug(f"Unexpected error checking URL {url}: {str(e)}")

    except Exception as e:
        logger.error(f"Failed to initialize HTTP client: {str(e)}")
        return []

    logger.info(f"Found {len(image_urls)} image URLs out of {len(urls)} total URLs")
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

        # Handle Clarity hex format which often includes length prefixes
        # First 5 bytes typically contain: 4-byte length + 1-byte type indicator
        if len(decoded_bytes) > 5 and decoded_bytes[0] == 0x0D:  # Length byte check
            # Skip the 4-byte length prefix and any potential type indicator
            decoded_bytes = decoded_bytes[5:]

        decoded_string = decoded_bytes.decode("utf-8", errors="ignore")
        logger.debug(f"Successfully decoded hex string: {hex_string[:20]}...")
        return decoded_string
    except (binascii.Error, UnicodeDecodeError) as e:
        logger.warning(f"Failed to decode hex string: {str(e)}")
        return None  # Return None if decoding fails


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
        logger.error(f"Error converting token counts to integers: {str(e)}")
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

    # Debug logging with more detail
    logger.debug(
        f"Cost calculation details: Model={model_name} | Input={input_tokens} tokens * ${model_prices['input']}/1M = ${input_cost:.6f} | Output={output_tokens} tokens * ${model_prices['output']}/1M = ${output_cost:.6f} | Total=${total_cost:.6f} | Token details={token_details}"
    )

    return {
        "input_cost": round(input_cost, 6),
        "output_cost": round(output_cost, 6),
        "total_cost": round(total_cost, 6),
        "currency": "USD",
        "details": token_details,
    }
