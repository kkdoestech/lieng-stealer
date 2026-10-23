"""Liêng Stealer - Range Solver & Opportunity Scanner.

Evaluates all 455 canonical hands against current game parameters (Pot, Bet, Fold Equity),
filtering for positive expected value (EV > 0) and measuring total range coverage.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from src.calling_range import CallingRangeModel, OpponentModel
from src.db import WinRateDB
from src.ev import calculate_ev, is_profitable
from src.evaluator import HandCategory
from src.exceptions import DatabaseNotLoadedError
from src.hands import TOTAL_COMBINATIONS as TOTAL_COMBINATIONS  # re-exported for callers and tests
from src.hands import generate_all_canonical_hands


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

    def __init__(self, db: WinRateDB, calling_model: CallingRangeModel | None = None) -> None:
        """Initialize RangeFinder with a populated WinRateDB instance.

        Args:
            db: A loaded win-rate database (equity against a random opponent hand). Loading is
                the caller's job, so the constructor never touches the filesystem.
            calling_model: Calling-range model, required only for OpponentModel.RANGE.

        Raises:
            DatabaseNotLoadedError: If ``db`` has not been loaded.
        """
        if not db.is_loaded:
            raise DatabaseNotLoadedError("RangeFinder needs a loaded WinRateDB; call db.load() first.")
        self._db = db
        self._calling_model = calling_model
        # Showdown strength of each class, used to order hands whose EV and equity tie
        self._strength = {h.canonical_id: h.score.score_tuple for h in generate_all_canonical_hands()}

    def solve_range(
        self,
        pot: float,
        bet_size: float,
        fold_equity: float,
        opponent_model: OpponentModel = OpponentModel.RANDOM,
    ) -> list[HandEVRecord]:
        """Evaluate and rank all 455 canonical hands sorted descending by EV.

        Args:
            pot: Dead pot size before hero's bet (must be > 0).
            bet_size: Additional bet / raise amount (must be > 0).
            fold_equity: Opponent fold probability in [0.0, 1.0].
            opponent_model: RANDOM uses equity vs a random hand; RANGE uses equity
                vs an opponent who folds their weakest hands.

        Returns:
            List of all 455 HandEVRecord instances sorted by EV descending.

        Raises:
            ValueError: If RANGE is requested without a CallingRangeModel.
        """
        all_stats = self._db.all_items()
        records: list[HandEVRecord] = []

        range_equity: dict[str, float] | None = None
        if opponent_model is OpponentModel.RANGE:
            if self._calling_model is None:
                raise ValueError("OpponentModel.RANGE requires a CallingRangeModel.")
            range_equity = self._calling_model.equity_table(fold_equity)

        for cid, stats in all_stats.items():
            equity = range_equity[cid] if range_equity is not None else stats.equity
            ev = calculate_ev(
                pot=pot,
                bet_size=bet_size,
                fold_equity=fold_equity,
                win_rate_when_called=equity,
            )
            records.append(
                HandEVRecord(
                    canonical_id=cid,
                    category=stats.category,
                    equity=equity,
                    ev=ev,
                    multiplicity=stats.multiplicity,
                    is_raise_profitable=is_profitable(ev),
                )
            )

        # Sort descending by EV (highest profit first); tie-break by equity, then hand strength
        records.sort(key=lambda r: (r.ev, r.equity, self._strength[r.canonical_id]), reverse=True)
        return records

    def get_profitable_range(
        self,
        pot: float,
        bet_size: float,
        fold_equity: float,
        opponent_model: OpponentModel = OpponentModel.RANDOM,
    ) -> list[HandEVRecord]:
        """Return only hands where Raise / All-in has positive expected value (EV > 0)."""
        all_records = self.solve_range(pot, bet_size, fold_equity, opponent_model)
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


@dataclass(frozen=True)
class CategorySummary:
    """How many classes and combinations of one hand category exist, and how many are profitable."""
    category: HandCategory
    classes: int
    combos: int
    profitable_combos: int


def category_breakdown(records: Sequence[HandEVRecord]) -> list[CategorySummary]:
    """Summarize classes, combos, and profitable combos per hand category (strongest first)."""
    breakdown = []
    for category in sorted(HandCategory, reverse=True):
        members = [r for r in records if r.category is category]
        breakdown.append(CategorySummary(
            category=category,
            classes=len(members),
            combos=sum(r.multiplicity for r in members),
            profitable_combos=sum(r.multiplicity for r in members if r.is_raise_profitable),
        ))
    return breakdown
