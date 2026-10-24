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
import tempfile
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from src.evaluator import Deck, evaluate_hand
from src.hands import (
    OPPONENT_COMBINATIONS,
    CanonicalHand,
    generate_all_canonical_hands,
    get_representative_cards,
)
from src.paths import DEFAULT_DB_PATH


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
        seed: Optional RNG seed for deterministic Monte Carlo sampling. It seeds a private
            generator, so the global ``random`` state is never touched.

    Returns:
        Dictionary conforming to data/winrates.json schema.

    Raises:
        ValueError: If Monte Carlo mode is asked for fewer than 1 sample.
    """
    if not exact and samples < 1:
        raise ValueError(f"Monte Carlo needs at least 1 sample, got {samples}.")
    rng = random.Random(seed)

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
        total_showdowns = OPPONENT_COMBINATIONS
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
            sampled = rng.sample(remaining_deck, 3)
            opp_score = evaluate_hand(sampled)
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
        "equity": round(equity, 4),
        "win_rate": round(win_rate, 4),
        "tie_rate": round(tie_rate, 4),
        "loss_rate": round(loss_rate, 4),
        "category": canonical_hand.category.name,
        "multiplicity": canonical_hand.multiplicity,
        "samples": total_showdowns,
    }


def _file_mode(path: Path) -> int:
    """Permissions for the written file: keep the old file's mode, or use 0644 minus the umask."""
    if path.exists():
        return path.stat().st_mode & 0o777
    umask = os.umask(0)
    os.umask(umask)
    return 0o644 & ~umask


def _worker_task(args: tuple[CanonicalHand, bool, int, int | None]) -> tuple[str, dict[str, Any]]:
    """Worker task wrapper for ProcessPoolExecutor."""
    canonical_hand, exact, samples, seed = args
    result = compute_hand_equity(canonical_hand, exact=exact, samples=samples, seed=seed)
    return canonical_hand.canonical_id, result


def generate_winrates_database(
    exact: bool = True,
    samples: int = 10000,
    output_path: str | Path = DEFAULT_DB_PATH,
    workers: int | None = None,
) -> dict[str, Any]:
    """Generate and write the winrates database for all 455 canonical hands.

    Args:
        exact: If True, run complete combinatorial enumeration.
        samples: Number of samples per hand if exact is False.
        output_path: Destination JSON filepath (default: backend/data/winrates.json).
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

    # Write to a temporary file in the same folder, then rename it over the target: readers see
    # either the old file or the complete new one, never a half-written file.
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=out_file.parent, suffix=".tmp", delete=False
    ) as tmp:
        try:
            json.dump(results, tmp, indent=2)
        except BaseException:
            tmp.close()
            os.unlink(tmp.name)
            raise
    # NamedTemporaryFile creates the file as owner-only (0600); give it normal permissions first.
    os.chmod(tmp.name, _file_mode(out_file))
    os.replace(tmp.name, out_file)

    return results


def _positive_int(text: str) -> int:
    """argparse type for counts that must be at least 1."""
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be at least 1, got {value}")
    return value


def build_parser() -> argparse.ArgumentParser:
    """Build the generator's command-line parser (exact enumeration by default)."""
    parser = argparse.ArgumentParser(
        description="Liêng Stealer - Precompute Showdown Equities Database."
    )
    parser.add_argument(
        "--samples",
        type=_positive_int,
        default=10000,
        help="Number of Monte Carlo samples per hand, with --monte-carlo (default: 10000).",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--exact",
        dest="exact",
        action="store_true",
        default=True,
        help="Run exact combinatorial enumeration over all C(49, 3) = 18,424 hands (default).",
    )
    mode.add_argument(
        "--monte-carlo",
        dest="exact",
        action="store_false",
        help="Estimate equities from --samples random opponent hands instead of exact enumeration.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Output filepath (default: backend/data/winrates.json, wherever you run from).",
    )
    parser.add_argument(
        "--workers",
        type=_positive_int,
        default=os.cpu_count() or 1,
        help=f"Number of parallel worker processes (default: {os.cpu_count() or 1}).",
    )
    return parser


def main(args: Sequence[str] | None = None) -> None:
    """CLI entry point for generator."""
    parsed = build_parser().parse_args(args)
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

