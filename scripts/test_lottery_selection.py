#!/usr/bin/env python3
"""
Test script to simulate the exact quorum lottery selection process from ActionProposalHandler.

Usage:
    python scripts/test_lottery_selection.py \\
        --agents-json agents.json \\
        --liquid-tokens "10000000" \\
        --bitcoin-block-hash "0000000000000000000123abc..." \\
        --bitcoin-block-height 488 \\
        --min-threshold 1000000

agents.json example:
[
    {
        "agent_id": "123e4567-e89b-12d3-a456-426614174000",
        "wallet_id": "123e4567-e89b-12d3-a456-426614174001",
        "wallet_address": "ST123...",
        "token_id": "123e4567-e89b-12d3-a456-426614174002",
        "token_amount": "1500000",
        "dao_id": "123e4567-e89b-12d3-a456-426614174003",
        "dao_name": "TestDAO"
    },
    ...
]
"""

import argparse
import hashlib
import json
import logging
import os
import random
import sys
from decimal import Decimal
from typing import List, Optional

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.backend.models import AgentWithWalletTokenDTO
from app.config import config
from app.services.integrations.webhooks.chainhook.handlers.lottery_utils import (
    LotterySelection,
    QuorumCalculator,
    create_wallet_selection_dict,
)


class LotterySimulator:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.logger = logging.getLogger(__name__)
        if verbose:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)

    def conduct_quorum_lottery(
        self,
        agents_with_tokens: List[AgentWithWalletTokenDTO],
        proposal_liquid_tokens: str,
        bitcoin_block_hash: str,
        bitcoin_block_height: int,
        min_threshold: Optional[int] = None,
        max_selections: Optional[int] = None,
        quorum_percentage: Optional[float] = None,
        min_selections: Optional[int] = None,
    ) -> LotterySelection:
        """Exact replica of ActionProposalHandler._conduct_quorum_lottery."""
        if min_threshold is None:
            min_threshold = config.lottery.min_token_threshold
        if max_selections is None:
            max_selections = config.lottery.max_selections
        if quorum_percentage is None:
            quorum_percentage = config.lottery.quorum_percentage
        if min_selections is None:
            min_selections = config.lottery.min_selections

        selection = LotterySelection()

        if not agents_with_tokens:
            self.logger.warning("No agents with tokens available for lottery")
            return selection

        try:
            _ = int(proposal_liquid_tokens or "0")
        except ValueError as e:
            self.logger.warning(
                f"Invalid proposal_liquid_tokens '{proposal_liquid_tokens}': {e} - returning empty selection"
            )
            return LotterySelection()

        # Apply minimum token threshold filter
        filtered_agents = [
            agent
            for agent in agents_with_tokens
            if int(agent.token_amount or "0") >= min_threshold
        ]
        total_filtered = len(filtered_agents)
        total_original = len(agents_with_tokens)

        if total_filtered == 0:
            self.logger.warning(
                f"No agents meet min_token_threshold={min_threshold}, falling back to all {total_original} agents"
            )
            filtered_agents = agents_with_tokens
            total_filtered = total_original

        self.logger.info(
            f"Lottery filtering: {total_original} total agents → {total_filtered} eligible (>= {min_threshold} tokens)"
        )

        # Use filtered agents for the rest of the process
        agents_with_tokens = filtered_agents  # Override for consistency

        # Initialize lottery parameters using config
        selection.liquid_tokens_at_creation = proposal_liquid_tokens
        selection.quorum_percentage = quorum_percentage
        selection.total_eligible_wallets = len(agents_with_tokens)
        selection.total_eligible_tokens = (
            QuorumCalculator.calculate_total_eligible_tokens(agents_with_tokens)
        )
        selection.quorum_threshold = QuorumCalculator.calculate_quorum_threshold(
            proposal_liquid_tokens, quorum_percentage
        )

        self.logger.info(
            f"Starting quorum lottery: {len(agents_with_tokens)} eligible agents, "
            f"liquid tokens: {proposal_liquid_tokens}, quorum needed: {selection.quorum_threshold} "
            f"(max_selections={max_selections})"
        )

        # Check if quorum is achievable
        if not QuorumCalculator.is_quorum_achievable(
            proposal_liquid_tokens,
            selection.total_eligible_tokens,
            quorum_percentage,
        ):
            self.logger.warning(
                f"Quorum not achievable: need {selection.quorum_threshold} tokens, "
                f"only {selection.total_eligible_tokens} available. Selecting all agents."
            )
            # Select all available agents
            for agent in agents_with_tokens:
                selection.selected_wallets.append(
                    create_wallet_selection_dict(agent.wallet_id, agent.token_amount)
                )
            selection.total_selected_tokens = selection.total_eligible_tokens
            selection.quorum_achieved = False
            selection.selection_rounds = 1
            return selection

        # Create deterministic seed from Bitcoin block hash
        seed = hashlib.sha256(bitcoin_block_hash.encode()).hexdigest()

        # Conduct weighted lottery until quorum is met or max selections reached
        remaining_agents = agents_with_tokens.copy()
        selected_tokens = Decimal("0")
        quorum_threshold_decimal = Decimal(selection.quorum_threshold)

        round_number = 0
        while (
            selected_tokens < quorum_threshold_decimal
            and remaining_agents
            and len(selection.selected_wallets) < max_selections
        ):
            round_number += 1

            round_seed = f"{seed}_{round_number}"
            random.seed(round_seed)

            # Exact int weights (arbitrary precision, handles 1e16+ micro-units)
            weights = [int(agent.token_amount or "0") for agent in remaining_agents]
            if not weights or all(w == 0 for w in weights):
                self.logger.warning(
                    "All remaining weights are zero, using equal weights"
                )
                weights = [1] * len(remaining_agents)

            total_weight = sum(weights)  # Exact bigint sum
            rand_int = random.randrange(
                total_weight
            )  # Exact uniform int [0, total_weight)

            cumulative = 0
            selected_idx = 0
            for idx, weight in enumerate(weights):
                cumulative += weight
                if rand_int < cumulative:
                    selected_idx = idx
                    break

            selected_agent = remaining_agents[selected_idx]
            wallet_dict = create_wallet_selection_dict(
                selected_agent.wallet_id, selected_agent.token_amount
            )
            selection.selected_wallets.append(wallet_dict)

            selected_tokens += Decimal(selected_agent.token_amount)

            self.logger.debug(
                f"Round {round_number}: Selected agent {selected_agent.agent_id} "
                f"with {selected_agent.token_amount} tokens "
                f"(total: {selected_tokens}/{selection.quorum_threshold})"
            )

            remaining_agents.pop(selected_idx)

        # Finalize selection results
        selection.total_selected_tokens = str(selected_tokens)
        selection.quorum_achieved = selected_tokens >= quorum_threshold_decimal
        selection.selection_rounds = round_number

        # Ensure minimum selection for fairness
        min_agents = min(min_selections, len(agents_with_tokens))
        while (
            len(selection.selected_wallets) < min_agents
            and remaining_agents
            and len(selection.selected_wallets) < max_selections
        ):
            round_number += 1
            round_seed = f"{seed}_{round_number}"
            random.seed(round_seed)

            # Weighted selection consistent with main loop (exact int)
            weights = [int(agent.token_amount or "0") for agent in remaining_agents]
            if not weights or all(w == 0 for w in weights):
                weights = [1] * len(remaining_agents)

            total_weight = sum(weights)
            rand_int = random.randrange(total_weight)

            cumulative = 0
            selected_idx = 0
            for idx, weight in enumerate(weights):
                cumulative += weight
                if rand_int < cumulative:
                    selected_idx = idx
                    break

            selected_agent = remaining_agents[selected_idx]
            wallet_dict = create_wallet_selection_dict(
                selected_agent.wallet_id, selected_agent.token_amount
            )
            selection.selected_wallets.append(wallet_dict)

            selected_tokens += Decimal(selected_agent.token_amount)
            remaining_agents.pop(selected_idx)

        # Update final totals
        selection.total_selected_tokens = str(selected_tokens)
        selection.quorum_achieved = selected_tokens >= quorum_threshold_decimal
        selection.selection_rounds = round_number

        self.logger.info(
            f"Quorum lottery completed: selected {len(selection.selected_wallets)} agents "
            f"with {selection.total_selected_tokens} tokens "
            f"({'✓' if selection.quorum_achieved else '✗'} quorum {'achieved' if selection.quorum_achieved else 'not achieved'}) "
            f"(cfg: min_th={min_threshold}, max_sel={max_selections}, min_sel={min_selections})"
        )

        return selection

    def print_results(self, selection: LotterySelection):
        """Print detailed results in JSON format for debugging."""
        print("\n" + "=" * 80)
        print("LOTTERY RESULTS")
        print("=" * 80)
        print(json.dumps(selection.__dict__, indent=2, default=str))
        print("\nSelected Wallets:")
        for w in selection.selected_wallets:
            print(f"  - {w}")
        print("=" * 80)


def load_agents_from_json(file_path: str) -> List[AgentWithWalletTokenDTO]:
    """Load agents from JSON file into DTOs."""
    with open(file_path, "r") as f:
        data = json.load(f)
    return [AgentWithWalletTokenDTO(**item) for item in data]


def main():
    parser = argparse.ArgumentParser(description="Simulate quorum lottery selection")
    parser.add_argument(
        "--agents-json",
        required=True,
        help="Path to JSON file with list of AgentWithWalletTokenDTO dicts",
    )
    parser.add_argument(
        "--liquid-tokens", required=True, help="Proposal liquid tokens (str)"
    )
    parser.add_argument(
        "--bitcoin-block-hash", required=True, help="Bitcoin block hash (str)"
    )
    parser.add_argument(
        "--bitcoin-block-height",
        type=int,
        required=True,
        help="Bitcoin block height (int)",
    )
    parser.add_argument(
        "--min-threshold",
        type=int,
        default=None,
        help="Override min_token_threshold (default: config.lottery.min_token_threshold)",
    )
    parser.add_argument(
        "--max-selections",
        type=int,
        default=None,
        help="Override max_selections (default: config)",
    )
    parser.add_argument(
        "--quorum-percentage",
        type=float,
        default=None,
        help="Override quorum_percentage (default: 0.15)",
    )
    parser.add_argument(
        "--min-selections",
        type=int,
        default=None,
        help="Override min_selections (default: 3)",
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    # Load data
    agents = load_agents_from_json(args.agents_json)
    print(f"Loaded {len(agents)} agents from {args.agents_json}")

    # Run simulation
    simulator = LotterySimulator(verbose=args.verbose)
    selection = simulator.conduct_quorum_lottery(
        agents,
        args.liquid_tokens,
        args.bitcoin_block_hash,
        args.bitcoin_block_height,
        args.min_threshold,
        args.max_selections,
        args.quorum_percentage,
        args.min_selections,
    )

    # Print results
    simulator.print_results(selection)


if __name__ == "__main__":
    main()
