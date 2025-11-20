#!/usr/bin/env python3
"""
Command-line interface for Stacks Chainhook Adapter

This module provides a CLI for the stacks-chainhook-adapter library,
allowing users to transform Stacks blocks to chainhook format from the command line.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

from . import (
    get_block_chainhook,
    StacksChainhookAdapter,
    AdapterConfig,
    ChainHookData,
    __version__,
)


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        description="Transform Stacks blockchain data into Chainhook-compatible format",
        prog="stacks-chainhook",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"stacks-chainhook-adapter {__version__}",
    )

    parser.add_argument(
        "block_height",
        type=int,
        help="Block height to transform",
    )

    parser.add_argument(
        "-n",
        "--network",
        choices=["mainnet", "testnet"],
        default="testnet",
        help="Network to use (default: testnet)",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=str,
        help="Output file path (default: auto-generated in current directory)",
    )

    parser.add_argument(
        "--api-url",
        type=str,
        help="Custom Stacks API URL",
    )

    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output",
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress informational output",
    )

    parser.add_argument(
        "--template",
        action="store_true",
        default=True,
        help="Use template-based generation (default: True)",
    )

    parser.add_argument(
        "--no-template",
        dest="template",
        action="store_false",
        help="Disable template-based generation",
    )

    return parser


async def transform_block(
    block_height: int,
    network: str = "testnet",
    api_url: Optional[str] = None,
    output_file: Optional[str] = None,
    use_template: bool = False,
    pretty: bool = False,
    quiet: bool = False,
) -> bool:
    """
    Transform a single block and save or print the result.

    Args:
        block_height: Block height to transform
        network: Network to use
        api_url: Custom API URL
        output_file: Output file path
        use_template: Whether to use template-based generation
        pretty: Whether to pretty-print JSON
        quiet: Whether to suppress info messages

    Returns:
        True if successful, False otherwise
    """
    try:
        if not quiet:
            print(f"🔍 Transforming block {block_height} on {network}...")

        # Get chainhook data
        if api_url:
            config = AdapterConfig(network=network, api_url=api_url)
            adapter = StacksChainhookAdapter(config)
            try:
                chainhook_data = await adapter.get_block_chainhook(
                    block_height, use_template=False
                )
            finally:
                await adapter.close()
        else:
            chainhook_data = await get_block_chainhook(
                block_height, network, use_template=False
            )

        if not chainhook_data or not isinstance(chainhook_data, ChainHookData):
            print(
                f"❌ Failed to retrieve data for block {block_height}", file=sys.stderr
            )
            return False

        # Display block info
        if not quiet:
            block_info = chainhook_data.apply[0]
            print("✅ Block transformed successfully!")
            print(f"   Hash: {block_info.block_identifier.hash[:20]}...")
            print(f"   Transactions: {len(block_info.transactions)}")
            print(f"   Timestamp: {block_info.timestamp}")

        # Save or print the result
        if output_file:
            # Save to specified file
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if use_template:
                from .utils import save_chainhook_data

                saved_path = save_chainhook_data(
                    chainhook_data,
                    output_dir=str(output_path.parent),
                    prefix=output_path.stem,
                    use_template=True,
                )
                if not quiet:
                    print(f"💾 Saved to: {saved_path}")
            else:
                from dataclasses import asdict

                data_dict = asdict(chainhook_data)

                with open(output_file, "w") as f:
                    if pretty:
                        json.dump(data_dict, f, indent=2, ensure_ascii=False)
                    else:
                        json.dump(data_dict, f, ensure_ascii=False)

                if not quiet:
                    print(f"💾 Saved to: {output_file}")
        else:
            # Print to stdout
            if use_template:
                from .utils import get_template_manager

                template_manager = get_template_manager()
                from .utils.output_manager import detect_block_title

                transaction_type = detect_block_title(chainhook_data)
                data_dict = template_manager.generate_chainhook_from_template(
                    chainhook_data, transaction_type
                )
                if data_dict is None:
                    from dataclasses import asdict

                    data_dict = asdict(chainhook_data)
            else:
                from dataclasses import asdict

                data_dict = asdict(chainhook_data)

            if pretty:
                json.dump(data_dict, sys.stdout, indent=2, ensure_ascii=False)
            else:
                json.dump(data_dict, sys.stdout, ensure_ascii=False)

            if not quiet:
                print(file=sys.stderr)  # Add newline after JSON

        return True

    except KeyboardInterrupt:
        print("\n❌ Interrupted by user", file=sys.stderr)
        return False
    except Exception as e:
        print(f"❌ Error transforming block {block_height}: {e}", file=sys.stderr)
        return False


def main() -> int:
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()

    try:
        success = asyncio.run(
            transform_block(
                block_height=args.block_height,
                network=args.network,
                api_url=args.api_url,
                output_file=args.output,
                use_template=args.template,
                pretty=args.pretty,
                quiet=args.quiet,
            )
        )
        return 0 if success else 1

    except KeyboardInterrupt:
        print("\n❌ Interrupted by user", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
