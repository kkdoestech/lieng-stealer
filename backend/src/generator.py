"""Liêng Stealer - Simulation Engine & Offline Data Generator.

Precomputes heads-up showdown equities for all 455 canonical Liêng hands
against random opponent ranges. Supports both Monte Carlo stochastic sampling
and exact combinatorial enumeration (C(49, 3) = 18,424 showdowns per hand).
Serializes results into data/winrates.json.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import random
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Sequence

from src.evaluator import Card, Deck, evaluate_hand
from src.hands import (
    CanonicalHand,
    generate_all_canonical_hands,
    get_representative_cards,
)


def compute_hand_equity(
    canonical_hand: CanonicalHand,
    exact: bool = True,
    samples: int = 10000,
    seed: int | None = None,
) -> dict[str, Any]:
    """Calculate heads-up showdown equity for a single canonical hand.

    Args:
        canonical_hand: The CanonicalHand to evaluate.
        exact: If True, iterates all C(49, 3) = 18,424 opponent combinations.
        samples: If not exact, number of random opponent hands to sample.
        seed: Optional RNG seed for deterministic Monte Carlo sampling.

    Returns:
        Dictionary conforming to data/winrates.json schema.
    """
    if seed is not None:
        random.seed(seed)

    hero_cards = get_representative_cards(canonical_hand.canonical_id)
    hero_score = canonical_hand.score

    # Construct the remaining 49-card deck
    hero_set = set(hero_cards)
    remaining_deck = [c for c in Deck.standard_52() if c not in hero_set]

    wins = 0
    ties = 0
    losses = 0

    if exact:
        # Full combinatorial enumeration: C(49, 3) = 18,424 opponent hands
        opponent_combinations = itertools.combinations(remaining_deck, 3)
        total_showdowns = 18424
        for opp_cards in opponent_combinations:
            opp_score = evaluate_hand(opp_cards)
            if hero_score > opp_score:
                wins += 1
            elif hero_score == opp_score:
                ties += 1
            else:
                losses += 1
    else:
        # Monte Carlo random sampling
        total_showdowns = samples
        for _ in range(samples):
            opp_cards = random.sample(remaining_deck, 3)
            opp_score = evaluate_hand(opp_cards)
            if hero_score > opp_score:
                wins += 1
            elif hero_score == opp_score:
                ties += 1
            else:
                losses += 1

    win_rate = wins / total_showdowns
    tie_rate = ties / total_showdowns
    loss_rate = losses / total_showdowns
    equity = (wins + 0.5 * ties) / total_showdowns

    return {
        "equity": round(equity, 8),
        "win_rate": round(win_rate, 8),
        "tie_rate": round(tie_rate, 8),
        "loss_rate": round(loss_rate, 8),
        "category": canonical_hand.category.name,
        "multiplicity": canonical_hand.multiplicity,
        "samples": total_showdowns,
    }


def _worker_task(args: tuple[CanonicalHand, bool, int, int | None]) -> tuple[str, dict[str, Any]]:
    """Worker task wrapper for ProcessPoolExecutor."""
    canonical_hand, exact, samples, seed = args
    result = compute_hand_equity(canonical_hand, exact=exact, samples=samples, seed=seed)
    return canonical_hand.canonical_id, result


def generate_winrates_database(
    exact: bool = True,
    samples: int = 10000,
    output_path: str | Path = "data/winrates.json",
    workers: int | None = None,
) -> dict[str, Any]:
    """Generate and write the winrates database for all 455 canonical hands.

    Args:
        exact: If True, run complete combinatorial enumeration.
        samples: Number of samples per hand if exact is False.
        output_path: Destination JSON filepath.
        workers: Number of parallel processes (defaults to cpu_count).

    Returns:
        The generated winrates dictionary.
    """
    canonical_hands = generate_all_canonical_hands()
    num_workers = workers or os.cpu_count() or 1

    tasks = [
        (ch, exact, samples, i if not exact else None)
        for i, ch in enumerate(canonical_hands)
    ]

    results: dict[str, Any] = {}
    if num_workers > 1:
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            for cid, data in executor.map(_worker_task, tasks):
                results[cid] = data
    else:
        for task in tasks:
            cid, data = _worker_task(task)
            results[cid] = data

    # Ensure destination directory exists
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    return results


def main(args: Sequence[str] | None = None) -> None:
    """CLI entry point for generator."""
    parser = argparse.ArgumentParser(
        description="Liêng Stealer - Precompute Showdown Equities Database."
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=10000,
        help="Number of Monte Carlo samples per hand (default: 10000).",
    )
    parser.add_argument(
        "--exact",
        action="store_true",
        help="Run exact combinatorial enumeration over all C(49, 3) = 18,424 hands.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/winrates.json",
        help="Output filepath (default: data/winrates.json).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=os.cpu_count() or 1,
        help=f"Number of parallel worker processes (default: {os.cpu_count() or 1}).",
    )

    parsed = parser.parse_args(args)
    mode = "Exact Combinatorial Enumeration" if parsed.exact else f"Monte Carlo ({parsed.samples} samples)"
    print(f"Starting equity generation in {mode} across {parsed.workers} workers...")

    results = generate_winrates_database(
        exact=parsed.exact,
        samples=parsed.samples,
        output_path=parsed.output,
        workers=parsed.workers,
    )
    print(f"Successfully generated database for {len(results)} canonical hands -> {parsed.output}")


if __name__ == "__main__":
    main()
