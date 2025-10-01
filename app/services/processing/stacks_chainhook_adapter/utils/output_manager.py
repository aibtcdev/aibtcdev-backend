#!/usr/bin/env python3
"""
Output Manager for Stacks Chainhook Adapter

This module handles automatic saving of transformed chainhook data with
descriptive filenames based on transaction types and block heights.
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import asdict

from ..models.chainhook import ChainHookData, TransactionWithReceipt
from .template_manager import get_template_manager


def detect_transaction_type(transaction: TransactionWithReceipt) -> str:
    """
    Detect the transaction type and generate a descriptive name.

    Args:
        transaction: The transaction to analyze

    Returns:
        A descriptive string for the transaction type
    """
    if not transaction or not transaction.metadata:
        return "unknown-transaction"

    metadata = transaction.metadata

    # Handle different transaction types based on metadata structure
    if hasattr(metadata, "kind") and metadata.kind:
        kind = metadata.kind

        # Check if it's a dictionary-like object
        if hasattr(kind, "type") or (isinstance(kind, dict) and "type" in kind):
            tx_type = (
                kind.get("type")
                if isinstance(kind, dict)
                else getattr(kind, "type", None)
            )

            if tx_type == "ContractCall":
                # Extract contract call data
                data = (
                    kind.get("data")
                    if isinstance(kind, dict)
                    else getattr(kind, "data", None)
                )
                if data:
                    method = (
                        data.get("method")
                        if isinstance(data, dict)
                        else getattr(data, "method", "unknown-method")
                    )
                    contract_id = (
                        data.get("contract_identifier")
                        if isinstance(data, dict)
                        else getattr(data, "contract_identifier", "")
                    )

                    # Extract contract name from identifier
                    contract_name = extract_contract_name(contract_id)

                    # Generate descriptive names based on method and contract
                    return generate_transaction_title(method, contract_name)

            elif tx_type == "TokenTransfer":
                return "token-transfer"

            elif tx_type == "Coinbase":
                return "coinbase"

            elif tx_type == "TenureChange":
                return "tenure-change"

    # Fallback: try to detect from description
    if hasattr(metadata, "description") and metadata.description:
        desc = metadata.description
        if "conclude-action-proposal" in desc:
            return "conclude-action-proposal"
        elif "create-action-proposal" in desc:
            return "create-action-proposal"
        elif "vote-on-action-proposal" in desc:
            return "vote-on-action-proposal"
        elif "buy-and-deposit" in desc:
            return "buy-and-deposit"
        elif "send-many" in desc:
            if "faces2-faktory" in desc:
                return "send-many-governance-airdrop"
            else:
                return "send-many-stx-airdrop"

    return "unknown-transaction"


def extract_contract_name(contract_identifier: str) -> str:
    """Extract a clean contract name from the full identifier."""
    if not contract_identifier:
        return "unknown-contract"

    # Split by '.' and take the last part (contract name)
    parts = contract_identifier.split(".")
    if len(parts) >= 2:
        contract_name = parts[-1]
        # Clean up common prefixes and make it readable
        contract_name = clean_contract_name(contract_name)
        return contract_name

    return "unknown-contract"


def clean_contract_name(name: str) -> str:
    """Clean up contract names for better readability."""
    # Remove common prefixes
    name = re.sub(r"^(aibtc-acct-|faces[23]?-)", "", name)

    # Handle specific contract patterns
    if "action-proposal-voting" in name:
        return "action-proposal-voting"
    elif "bitflow-buy-and-deposit" in name:
        return "bitflow-buy-and-deposit"
    elif "send-many" in name:
        return "send-many"
    elif "faktory" in name:
        return "faktory"
    elif name.startswith("ST") and len(name) > 20:
        # Long addresses, just use a generic name
        return "contract-call"

    return name


def generate_transaction_title(method: str, contract_name: str) -> str:
    """Generate a descriptive title based on method and contract."""
    # Handle specific method patterns
    if method == "vote-on-action-proposal":
        return "vote-on-action-proposal"
    elif method == "create-action-proposal":
        return "create-action-proposal"
    elif method == "conclude-action-proposal":
        return "conclude-action-proposal"
    elif method == "buy-and-deposit":
        return "buy-and-deposit"
    elif method == "send-many":
        if "faktory" in contract_name:
            return "send-many-governance-airdrop"
        else:
            return "send-many-stx-airdrop"

    # Fallback to method-contract combination
    return f"{method}-{contract_name}".lower().replace("_", "-")


def detect_block_title(chainhook_data: ChainHookData) -> str:
    """
    Detect the overall title for a block based on its transactions.

    Args:
        chainhook_data: The complete chainhook data

    Returns:
        A descriptive title for the block
    """
    if not chainhook_data.apply or not chainhook_data.apply[0].transactions:
        return "empty-block"

    transactions = chainhook_data.apply[0].transactions

    if len(transactions) == 1:
        # Single transaction block - use the transaction type
        return detect_transaction_type(transactions[0])
    else:
        # Multi-transaction block - analyze all transactions
        types = [detect_transaction_type(tx) for tx in transactions]

        # Check for coinbase block (tenure-change + coinbase combination)
        if "tenure-change" in types and "coinbase" in types:
            return "coinbase"

        # Check for specific combinations
        if any("vote-on-action-proposal" in t for t in types) and any(
            "send-many" in t for t in types
        ):
            return "governance-and-airdrop-multi-tx"
        elif all("vote-on-action-proposal" in t for t in types):
            return "multi-vote-on-action-proposal"
        elif all("send-many" in t for t in types):
            return "multi-send-many"

        # Generic multi-transaction
        return f"multi-tx-{len(transactions)}-transactions"


def create_output_filename(
    chainhook_data: ChainHookData, prefix: Optional[str] = None
) -> str:
    """
    Create a descriptive filename for the chainhook data.

    Args:
        chainhook_data: The chainhook data to save
        prefix: Optional prefix for the filename

    Returns:
        A descriptive filename
    """
    # Get block height
    block_height = chainhook_data.apply[0].block_identifier.index

    # Detect block title
    title = detect_block_title(chainhook_data)

    # Create filename
    if prefix:
        filename = f"{prefix}-{title}-{block_height}.json"
    else:
        filename = f"{title}-{block_height}.json"

    # Clean filename
    filename = re.sub(r"[^\w\-.]", "-", filename)
    filename = re.sub(r"-+", "-", filename)  # Remove multiple dashes

    return filename


def ensure_output_directory(base_path: str = "output") -> Path:
    """
    Ensure the output directory exists.

    Args:
        base_path: Base path for output directory

    Returns:
        Path object for the output directory
    """
    output_dir = Path(base_path)
    output_dir.mkdir(exist_ok=True)

    # Create subdirectories
    (output_dir / "adapter-output").mkdir(exist_ok=True)
    (output_dir / "original-chainhook").mkdir(exist_ok=True)
    (output_dir / "comparisons").mkdir(exist_ok=True)

    return output_dir


def save_chainhook_data(
    chainhook_data: ChainHookData,
    output_dir: str = "output/adapter-output",
    prefix: Optional[str] = None,
    use_template: bool = True,
) -> Path:
    """
    Save chainhook data to a file with a descriptive name.

    Args:
        chainhook_data: The chainhook data to save
        output_dir: Directory to save to
        prefix: Optional prefix for the filename
        use_template: Whether to use template-based generation for exact compatibility

    Returns:
        Path to the saved file
    """
    # Ensure output directory exists
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Create filename
    filename = create_output_filename(chainhook_data, prefix)
    file_path = output_path / filename

    # Detect transaction type for template selection
    transaction_type = detect_block_title(chainhook_data)

    if use_template:
        # Use template-based generation for exact compatibility
        template_manager = get_template_manager()
        data_dict = template_manager.generate_chainhook_from_template(
            chainhook_data, transaction_type
        )

        if data_dict is None:
            print("⚠️  Template generation failed, falling back to dataclass conversion")
            # Fallback to original method - no extra metadata for 100% compatibility
            data_dict = asdict(chainhook_data)
    else:
        # Original dataclass conversion method - no extra metadata for 100% compatibility
        data_dict = asdict(chainhook_data)

    # Save to file
    with open(file_path, "w") as f:
        json.dump(data_dict, f, indent=2, ensure_ascii=False)

    return file_path


def save_chainhook_data_with_template(
    chainhook_data: ChainHookData,
    template_type: str,
    output_dir: str = "output/template-based",
    prefix: Optional[str] = None,
) -> Path:
    """
    Save chainhook data using template-based generation for exact compatibility.

    Args:
        chainhook_data: The chainhook data to save
        template_type: The template type to use
        output_dir: Directory to save to
        prefix: Optional prefix for the filename

    Returns:
        Path to the saved file
    """
    # Ensure output directory exists
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Use template manager
    template_manager = get_template_manager()
    data_dict = template_manager.generate_chainhook_from_template(
        chainhook_data, template_type
    )

    if data_dict is None:
        raise ValueError(
            f"Failed to generate chainhook data using template: {template_type}"
        )

    # Create filename
    filename = create_output_filename(chainhook_data, prefix or "template")
    file_path = output_path / filename

    # Save to file
    with open(file_path, "w") as f:
        json.dump(data_dict, f, indent=2, ensure_ascii=False)

    return file_path


def save_comparison_data(
    original_data: Dict[str, Any],
    adapter_data: ChainHookData,
    block_height: int,
    output_dir: str = "output/comparisons",
) -> Path:
    """
    Save a comparison between original chainhook data and adapter output.

    Args:
        original_data: Original chainhook data
        adapter_data: Adapter-generated chainhook data
        block_height: Block height for filename
        output_dir: Directory to save to

    Returns:
        Path to the saved comparison file
    """
    # Ensure output directory exists
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Create filename
    title = detect_block_title(adapter_data)
    filename = f"comparison-{title}-{block_height}.json"
    file_path = output_path / filename

    # Create comparison data
    comparison = {
        "block_height": block_height,
        "title": title,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "original": original_data,
        "adapter_output": asdict(adapter_data),
        "comparison_summary": {
            "block_height_match": original_data["apply"][0]["block_identifier"]["index"]
            == adapter_data.apply[0].block_identifier.index,
            "transaction_count_original": len(
                original_data["apply"][0]["transactions"]
            ),
            "transaction_count_adapter": len(adapter_data.apply[0].transactions),
            "transaction_count_match": len(original_data["apply"][0]["transactions"])
            == len(adapter_data.apply[0].transactions),
        },
    }

    # Save to file
    with open(file_path, "w") as f:
        json.dump(comparison, f, indent=2, ensure_ascii=False)

    return file_path


def get_saved_outputs(output_dir: str = "output/adapter-output") -> List[Path]:
    """
    Get list of all saved adapter outputs.

    Args:
        output_dir: Directory to search

    Returns:
        List of saved output file paths
    """
    output_path = Path(output_dir)
    if not output_path.exists():
        return []

    return list(output_path.glob("*.json"))


def create_output_summary(output_dir: str = "output") -> Dict[str, Any]:
    """
    Create a summary of all saved outputs.

    Args:
        output_dir: Base output directory

    Returns:
        Summary dictionary
    """
    base_path = Path(output_dir)

    summary = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "output_directory": str(base_path.resolve()),
        "adapter_outputs": [],
        "comparisons": [],
        "statistics": {
            "total_adapter_outputs": 0,
            "total_comparisons": 0,
            "blocks_processed": set(),
            "transaction_types": set(),
        },
    }

    # Scan adapter outputs
    adapter_dir = base_path / "adapter-output"
    if adapter_dir.exists():
        for file_path in adapter_dir.glob("*.json"):
            try:
                with open(file_path) as f:
                    data = json.load(f)

                output_info = {
                    "filename": file_path.name,
                    "block_height": data.get("_adapter_metadata", {}).get(
                        "block_height"
                    ),
                    "size_bytes": file_path.stat().st_size,
                    "modified": datetime.fromtimestamp(
                        file_path.stat().st_mtime
                    ).isoformat(),
                }
                summary["adapter_outputs"].append(output_info)

                if output_info["block_height"]:
                    summary["statistics"]["blocks_processed"].add(
                        output_info["block_height"]
                    )

            except Exception:
                pass  # Skip files that can't be read

    # Scan comparisons
    comparison_dir = base_path / "comparisons"
    if comparison_dir.exists():
        for file_path in comparison_dir.glob("*.json"):
            comparison_info = {
                "filename": file_path.name,
                "size_bytes": file_path.stat().st_size,
                "modified": datetime.fromtimestamp(
                    file_path.stat().st_mtime
                ).isoformat(),
            }
            summary["comparisons"].append(comparison_info)

    # Update statistics
    summary["statistics"]["total_adapter_outputs"] = len(summary["adapter_outputs"])
    summary["statistics"]["total_comparisons"] = len(summary["comparisons"])
    summary["statistics"]["blocks_processed"] = list(
        summary["statistics"]["blocks_processed"]
    )

    return summary
