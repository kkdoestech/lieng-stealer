"""Liêng Stealer - Opponent Calling-Range Model.

An opponent who folds a fraction f of the time does not fold at random: they fold
their weakest hands and call with the strongest (1 - f) of the 22,100-combination
space. This module computes Hero's exact showdown equity against that calling
range, including card removal (Hero's own ranks are unavailable to the opponent).

All 455 canonical classes have distinct strengths, so they form a total order.
After a one-time O(455²) table build, any equity query is O(1) per hand and a
full 455-hand table is O(455).
"""

from __future__ import annotations

from array import array
from bisect import bisect_right
from collections import Counter
from enum import Enum
from math import comb
from typing import Final, Sequence

from src.hands import CanonicalHand, generate_all_canonical_hands

TOTAL_COMBINATIONS: Final[int] = 22100
OPPONENT_COMBINATIONS: Final[int] = 18424  # C(49, 3) hands left after Hero's 3 cards

# _COMB[n][k] = C(n, k) for the at most 4 cards of a rank left in the deck
_COMB: Final[tuple[tuple[int, ...], ...]] = tuple(
    tuple(comb(n, k) for k in range(4)) for n in range(5)
)


class OpponentModel(str, Enum):
    """How the opponent decides which hands to fold."""
    RANDOM = "random"  # Folds regardless of strength, so a call comes from a random hand
    RANGE = "range"    # Folds the weakest hands, calls with the strongest (1 - f)


class CallingRangeModel:
    """Exact equity of every canonical hand against a strength-ordered calling range.

    Classes are ordered strongest-first. For Hero class h, ``_prefix[h][j]`` counts
    the opponent combinations among the j strongest classes that remain possible
    after removing Hero's three ranks from the deck.
    """

    def __init__(self, hands: Sequence[CanonicalHand] | None = None) -> None:
        """Build the card-removal prefix tables.

        Args:
            hands: Canonical hands to model. Defaults to all 455 classes.
        """
        ordered = sorted(
            hands if hands is not None else generate_all_canonical_hands(),
            key=lambda h: h.score.score_tuple,
            reverse=True,
        )
        self._ids: tuple[str, ...] = tuple(h.canonical_id for h in ordered)
        self._index: dict[str, int] = {cid: i for i, cid in enumerate(self._ids)}
        self._mult: tuple[int, ...] = tuple(h.multiplicity for h in ordered)

        cum_mult = [0]
        for m in self._mult:
            cum_mult.append(cum_mult[-1] + m)
        self._cum_mult: tuple[int, ...] = tuple(cum_mult)

        rank_counts = [Counter(r.value for r in h.ranks) for h in ordered]
        opponent_needs = [tuple(c.items()) for c in rank_counts]
        self._prefix: tuple[array[int], ...] = tuple(
            self._build_prefix_row(hero, opponent_needs) for hero in rank_counts
        )

    @staticmethod
    def _build_prefix_row(
        hero: Counter[int],
        opponent_needs: Sequence[tuple[tuple[int, int], ...]],
    ) -> array[int]:
        """Cumulative count of opponent combos per class, given Hero's ranks."""
        remaining = {rank: 4 - hero[rank] for rank in range(2, 15)}
        row = array("i", [0])
        total = 0
        for needs in opponent_needs:
            available = 1
            for rank, need in needs:
                available *= _COMB[remaining[rank]][need]
            total += available
            row.append(total)
        return row

    def __len__(self) -> int:
        return len(self._ids)

    def __contains__(self, canonical_id: object) -> bool:
        return canonical_id in self._index

    def equity(self, canonical_id: str, fold_equity: float) -> float:
        """Hero's equity when called by an opponent who folds their weakest hands.

        Args:
            canonical_id: Hero's canonical hand, e.g. 'K-Q-3'.
            fold_equity: Opponent fold frequency in [0.0, 1.0].

        Returns:
            Win probability plus half the tie probability, rounded to 4 places.
            0.0 when the calling range is empty (e.g. fold_equity == 1.0).

        Raises:
            KeyError: If canonical_id is unknown.
            ValueError: If fold_equity is outside [0.0, 1.0].
        """
        if canonical_id not in self._index:
            raise KeyError(f"Canonical hand '{canonical_id}' not found in calling-range model.")
        k, frac = self._calling_boundary(fold_equity)
        return self._equity_at(self._index[canonical_id], k, frac)

    def equity_table(self, fold_equity: float) -> dict[str, float]:
        """Equity when called for every canonical hand at one fold frequency.

        Args:
            fold_equity: Opponent fold frequency in [0.0, 1.0].

        Returns:
            Mapping of canonical ID to equity, as in ``equity()``.

        Raises:
            ValueError: If fold_equity is outside [0.0, 1.0].
        """
        k, frac = self._calling_boundary(fold_equity)
        return {cid: self._equity_at(i, k, frac) for i, cid in enumerate(self._ids)}

    def _calling_boundary(self, fold_equity: float) -> tuple[int, float]:
        """Return (k, frac): classes [0, k) call in full, class k calls with weight frac."""
        if not (0.0 <= fold_equity <= 1.0):
            raise ValueError(f"Fold equity must be between 0.0 and 1.0, got {fold_equity}.")
        calling_combos = (1.0 - fold_equity) * TOTAL_COMBINATIONS
        k = bisect_right(self._cum_mult, calling_combos) - 1
        if k >= len(self._ids):
            return len(self._ids), 0.0
        return k, (calling_combos - self._cum_mult[k]) / self._mult[k]

    def _equity_at(self, hero: int, k: int, frac: float) -> float:
        """Equity of the Hero class at strength index ``hero`` against boundary (k, frac)."""
        row = self._prefix[hero]
        boundary = frac * (row[k + 1] - row[k]) if k < len(self._ids) else 0.0
        calling = row[k] + boundary
        if calling <= 0.0:
            return 0.0

        if hero < k:
            # Hero beats every calling class weaker than itself, including the boundary
            beaten = row[k] - row[hero + 1] + boundary
            tied = row[hero + 1] - row[hero]
        elif hero == k:
            beaten = 0.0
            tied = boundary
        else:
            beaten = 0.0
            tied = 0.0
        return round((beaten + 0.5 * tied) / calling, 4)
