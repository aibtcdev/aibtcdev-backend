"""Utility functions for the Stacks Chainhook Adapter."""

from .helpers import (
    get_block_height_from_transaction,
    extract_contract_name,
    format_stacks_address,
    parse_stacks_amount,
    is_mainnet_address,
    is_testnet_address,
)

from .output_manager import (
    detect_transaction_type,
    detect_block_title,
    create_output_filename,
    ensure_output_directory,
    save_chainhook_data,
    save_chainhook_data_with_template,
    save_comparison_data,
    get_saved_outputs,
    create_output_summary,
)

from .template_manager import (
    ChainhookTemplateManager,
    get_template_manager,
)

__all__ = [
    "get_block_height_from_transaction",
    "extract_contract_name",
    "format_stacks_address",
    "parse_stacks_amount",
    "is_mainnet_address",
    "is_testnet_address",
    "detect_transaction_type",
    "detect_block_title",
    "create_output_filename",
    "ensure_output_directory",
    "save_chainhook_data",
    "save_chainhook_data_with_template",
    "save_comparison_data",
    "get_saved_outputs",
    "create_output_summary",
    "ChainhookTemplateManager",
    "get_template_manager",
]
