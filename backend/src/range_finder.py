"""Liêng Stealer - Range Solver & Opportunity Scanner.

Evaluates all 455 canonical hands against current game parameters (Pot, Bet, Fold Equity),
filtering for positive expected value (EV > 0) and measuring total range coverage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Sequence

from src.db import HandStats, WinRateDB
from src.evaluator import HandCategory
from src.ev import calculate_ev, is_profitable

TOTAL_COMBINATIONS: Final[int] = 22100


@dataclass(frozen=True)
class HandEVRecord:
    """Immutable valuation record for a canonical hand under specific game state."""
    canonical_id: str
    category: HandCategory
    equity: float
    ev: float
    multiplicity: int
    is_raise_profitable: bool


class RangeFinder:
    """Solves and ranks profitable ranges across all canonical hands."""

    def __init__(self, db: WinRateDB) -> None:
        """Initialize RangeFinder with a populated WinRateDB instance."""
        if not db.is_loaded:
            db.load()
        self._db = db

    def solve_range(
        self,
        pot: float,
        bet_size: float,
        fold_equity: float,
    ) -> list[HandEVRecord]:
        """Evaluate and rank all 455 canonical hands sorted descending by EV.

        Args:
            pot: Dead pot size before hero's bet (must be > 0).
            bet_size: Additional bet / raise amount (must be > 0).
            fold_equity: Opponent fold probability in [0.0, 1.0].

        Returns:
            List of all 455 HandEVRecord instances sorted by EV descending.
        """
        all_stats = self._db.all_items()
        records: list[HandEVRecord] = []

        for cid, stats in all_stats.items():
            ev = calculate_ev(
                pot=pot,
                bet_size=bet_size,
                fold_equity=fold_equity,
                win_rate_when_called=stats.equity,
            )
            records.append(
                HandEVRecord(
                    canonical_id=cid,
                    category=stats.category,
                    equity=stats.equity,
                    ev=ev,
                    multiplicity=stats.multiplicity,
                    is_raise_profitable=is_profitable(ev),
                )
            )

        # Sort descending by EV (highest profit first); tie-break by equity
        records.sort(key=lambda r: (r.ev, r.equity), reverse=True)
        return records

    def get_profitable_range(
        self,
        pot: float,
        bet_size: float,
        fold_equity: float,
    ) -> list[HandEVRecord]:
        """Return only hands where Raise / All-in has positive expected value (EV > 0)."""
        all_records = self.solve_range(pot, bet_size, fold_equity)
        return [r for r in all_records if r.is_raise_profitable]

    def calculate_range_coverage(
        self,
        profitable_records: Sequence[HandEVRecord],
    ) -> float:
        """Compute the weighted percentage of the 22,100 hand space where EV > 0.

        Formula:
            Coverage (%) = (Sum of Multiplicities / 22,100) * 100%

        Args:
            profitable_records: HandEVRecord instances with EV > 0.

        Returns:
            Coverage percentage rounded to 2 decimal places (0.0 to 100.0).
        """
        if not profitable_records:
            return 0.0

        combos = sum(r.multiplicity for r in profitable_records if r.is_raise_profitable)
        coverage = (combos / TOTAL_COMBINATIONS) * 100.0
        return round(min(100.0, max(0.0, coverage)), 2)

