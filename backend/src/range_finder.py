"""Liêng Stealer - Range Solver & Opportunity Scanner.

Evaluates all 455 canonical hands against current game parameters (Pot, Bet, Fold Equity),
filtering for positive expected value (EV > 0) and measuring total range coverage.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from src.calling_range import CallingRangeModel, OpponentModel
from src.db import WinRateDB
from src.ev import calculate_ev, is_profitable, profitable_fold_zones
from src.evaluator import Hand, HandCategory
from src.exceptions import DatabaseNotLoadedError, ModelError, UnknownHandError
from src.hands import TOTAL_COMBINATIONS as TOTAL_COMBINATIONS  # re-exported for callers and tests
from src.hands import generate_all_canonical_hands, to_canonical


@dataclass(frozen=True)
class HandEVRecord:
    """Immutable valuation record for a canonical hand under specific game state."""
    canonical_id: str
    category: HandCategory
    equity: float
    ev: float
    multiplicity: int
    is_raise_profitable: bool


@dataclass(frozen=True)
class OpponentEquities:
    """Hero's equity when called: one immutable number per canonical class, under one assumption.

    This is the ONLY equity source inside a request. The single-hand answer and the 455-class
    table are two reads of the same object, so the verdict card and the table cannot disagree.

    Attributes:
        opponent_model: Which opponent the numbers describe.
        fold_equity: The fold frequency these numbers belong to. Under RANGE it also fixes the
            calling set (the opponent folds their weakest ``fold_equity`` share of the 22,100
            pre-deal combinations); ``calling_percentile`` is derived from it, never supplied.
        _by_class: 455 entries, canonical ID to equity when called. Wrapped in a read-only view.
    """

    opponent_model: OpponentModel
    fold_equity: float
    _by_class: Mapping[str, float]

    def __post_init__(self) -> None:
        # A frozen dataclass still holds a mutable dict; make the mapping itself read-only.
        object.__setattr__(self, "_by_class", MappingProxyType(dict(self._by_class)))

    def of(self, canonical_id: str) -> float:
        """Equity when called for one canonical class.

        Raises:
            UnknownHandError: If the class is not in the table (also a KeyError).
        """
        try:
            return self._by_class[canonical_id]
        except KeyError as err:
            raise UnknownHandError(
                f"Canonical hand '{canonical_id}' not found in the equity table."
            ) from err

    def table(self) -> Mapping[str, float]:
        """All 455 equities, as a read-only mapping."""
        return self._by_class

    @property
    def calling_percentile(self) -> float | None:
        """The strongest ``(1 - fold_equity) * 100`` percent of hands call. None under RANDOM."""
        if self.opponent_model is OpponentModel.RANDOM:
            return None
        return round((1.0 - self.fold_equity) * 100.0, 4)


@dataclass(frozen=True)
class HandSolution:
    """One hand's answer: its row of the 455-class table, plus where raising pays.

    ``record.equity`` and ``record.ev`` are the reported ``showdown_equity`` and ``ev``.
    They are not recomputed, so they cannot drift from the table.
    """

    hand: Hand
    record: HandEVRecord
    zones: tuple[tuple[float, float], ...]


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

    def equities(self, fold_equity: float, opponent_model: OpponentModel) -> OpponentEquities:
        """The one equity source for a request: 455 numbers under one opponent assumption.

        Args:
            fold_equity: Opponent fold frequency in [0.0, 1.0]. Under RANGE it also fixes the
                calling set: the strongest ``(1 - fold_equity) * 22,100`` pre-deal combinations.
            opponent_model: RANDOM (equity vs one random hand) or RANGE (equity when called).

        Returns:
            The 455 equities and the fold rate they belong to.

        Raises:
            ModelError: If RANGE is requested and no CallingRangeModel was injected.
            InvalidGameParamsError: If fold_equity is outside [0.0, 1.0] (also a ValueError).
        """
        if opponent_model is OpponentModel.RANGE:
            if self._calling_model is None:
                raise ModelError("OpponentModel.RANGE requires a CallingRangeModel.")
            return OpponentEquities(opponent_model, fold_equity, self._calling_model.equity_table(fold_equity))
        return OpponentEquities(
            opponent_model, fold_equity, {cid: stats.equity for cid, stats in self._db.all_items().items()}
        )

    def solve_range(
        self,
        pot: float,
        bet_size: float,
        equities: OpponentEquities,
    ) -> list[HandEVRecord]:
        """Evaluate and rank all 455 canonical hands sorted descending by EV.

        Args:
            pot: Dead pot size before hero's bet (must be > 0).
            bet_size: Additional bet / raise amount (must be > 0).
            equities: The request's single equity source; it also owns the fold rate used in
                the EV formula, so the table and the formula cannot be handed different ones.

        Returns:
            List of all 455 HandEVRecord instances sorted by EV descending.
        """
        fold_equity = equities.fold_equity
        records: list[HandEVRecord] = []
        for cid, stats in self._db.all_items().items():
            equity = equities.of(cid)
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

    def hand_solution(
        self,
        hand: Hand,
        records: Sequence[HandEVRecord],
        equities: OpponentEquities,
        pot: float,
        bet_size: float,
    ) -> HandSolution:
        """Answer one hand from the table: the matching row, plus the fold rates where raising pays.

        The reported equity and EV are the row's stored values, not a second computation.

        Args:
            hand: Hero's three cards.
            records: The 455 records produced by ``solve_range`` for the same equities.
            equities: The same equity source those records came from.
            pot: Dead pot size before hero's bet (must be > 0).
            bet_size: Additional bet / raise amount (must be > 0).

        Returns:
            The hand's solution, whose ``record`` is the matching element of ``records``.

        Raises:
            ModelError: If the hand's class is missing from ``records`` (a bug: the database
                always covers all 455 classes, checked at start-up).
        """
        canonical_id = to_canonical(hand.cards).canonical_id
        for record in records:
            if record.canonical_id == canonical_id:
                return HandSolution(
                    hand,
                    record,
                    tuple(profitable_fold_zones(pot, bet_size, self._equity_scan(equities, canonical_id))),
                )
        raise ModelError(f"Canonical hand '{canonical_id}' is missing from the 455-class table.")

    def _equity_scan(self, equities: OpponentEquities, canonical_id: str) -> Callable[[float], float]:
        """Map a hypothetical fold frequency to Hero's equity there, under the same assumption."""
        if equities.opponent_model is OpponentModel.RANGE:
            model = self._calling_model
            if model is None:
                raise ModelError("OpponentModel.RANGE requires a CallingRangeModel.")
            return lambda fold_equity: model.equity(canonical_id, fold_equity)
        equity = equities.of(canonical_id)
        return lambda _fold_equity: equity

    def get_profitable_range(
        self,
        pot: float,
        bet_size: float,
        equities: OpponentEquities,
    ) -> list[HandEVRecord]:
        """Return only hands where Raise / All-in has positive expected value (EV > 0)."""
        arms = self.solve_range(pot, bet_size, equities)
        return [r for r in arms if r.is_raise_profitable]

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
