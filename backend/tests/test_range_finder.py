"""Unit tests for the Range Solver Engine (RangeFinder).

Verifies:
- All 455 canonical hands are evaluated by solve_range()
- When fold equity is 100%, all 22,100 combinations yield positive EV and coverage is 100.0%
- When fold equity is 0%, only hands exceeding the required pot odds threshold are profitable
- Monotonicity: Increasing fold equity strictly increases or maintains range coverage
- Opponent models: get_profitable_range honours the model; equal-EV hands are ordered by strength
"""

import pytest

from src.calling_range import CallingRangeModel, OpponentModel
from src.db import WinRateDB
from src.range_finder import RangeFinder


@pytest.fixture(scope="module")
def loaded_finder() -> RangeFinder:
    db = WinRateDB("data/winrates.json")
    return RangeFinder(db)


@pytest.fixture(scope="module")
def finder_with_model() -> RangeFinder:
    return RangeFinder(WinRateDB("data/winrates.json"), CallingRangeModel())


class TestRangeFinder:
    """Test suite for RangeFinder engine."""

    def test_solve_range_returns_all_455_classes(self, loaded_finder: RangeFinder) -> None:
        """Verify that solve_range returns exactly 455 evaluated canonical records."""
        records = loaded_finder.solve_range(pot=100000.0, bet_size=50000.0, fold_equity=0.35)
        assert len(records) == 455

        # Check descending sort order by EV
        for i in range(len(records) - 1):
            assert records[i].ev >= records[i + 1].ev

    def test_pure_fold_equity_100_percent(self, loaded_finder: RangeFinder) -> None:
        """When fold equity is 1.0, all 22,100 combinations yield EV = pot, and coverage is 100.0%."""
        pot = 100000.0
        bet = 50000.0
        records = loaded_finder.solve_range(pot=pot, bet_size=bet, fold_equity=1.0)
        assert len(records) == 455

        # All hands must yield EV = pot
        for r in records:
            assert r.ev == pot
            assert r.is_raise_profitable is True

        profitable = loaded_finder.get_profitable_range(pot=pot, bet_size=bet, fold_equity=1.0)
        assert len(profitable) == 455

        coverage = loaded_finder.calculate_range_coverage(profitable)
        assert coverage == 100.0

    def test_pure_fold_equity_zero_tight_range(self, loaded_finder: RangeFinder) -> None:
        """When fold equity is 0.0, only hands meeting pot odds are profitable."""
        pot = 100000.0
        bet = 50000.0
        # Final pot = 200k. Required equity = 50k / 200k = 0.25 (25%)
        threshold_equity = bet / (pot + 2.0 * bet)

        profitable = loaded_finder.get_profitable_range(pot=pot, bet_size=bet, fold_equity=0.0)

        # All profitable hands must have equity > threshold_equity
        for r in profitable:
            assert r.equity >= threshold_equity
            assert r.ev > 0.0

        # Coverage must be strictly less than 100% (tight range)
        coverage = loaded_finder.calculate_range_coverage(profitable)
        assert 0.0 < coverage < 100.0

    def test_coverage_monotonicity(self, loaded_finder: RangeFinder) -> None:
        """Increasing fold equity must monotonically increase range coverage."""
        pot = 100000.0
        bet = 50000.0

        cov_0 = loaded_finder.calculate_range_coverage(
            loaded_finder.get_profitable_range(pot, bet, fold_equity=0.0)
        )
        cov_25 = loaded_finder.calculate_range_coverage(
            loaded_finder.get_profitable_range(pot, bet, fold_equity=0.25)
        )
        cov_50 = loaded_finder.calculate_range_coverage(
            loaded_finder.get_profitable_range(pot, bet, fold_equity=0.50)
        )
        cov_100 = loaded_finder.calculate_range_coverage(
            loaded_finder.get_profitable_range(pot, bet, fold_equity=1.0)
        )

        assert cov_0 <= cov_25 <= cov_50 <= cov_100
        assert cov_100 == 100.0


class TestOpponentModels:
    """Test suite for the opponent-model parameter of RangeFinder."""

    def test_profitable_range_respects_opponent_model(self, finder_with_model: RangeFinder) -> None:
        """A pot-sized bet at 35% folds: 387 classes profit vs random callers, only 250 vs a calling range."""
        random_range = finder_with_model.get_profitable_range(100000.0, 100000.0, 0.35)
        calling_range = finder_with_model.get_profitable_range(
            100000.0, 100000.0, 0.35, opponent_model=OpponentModel.RANGE
        )
        assert len(random_range) == 387
        assert len(calling_range) == 250

    def test_equal_ev_hands_are_ordered_strongest_first(self, finder_with_model: RangeFinder) -> None:
        """At 35% folds every weak hand has 0 equity vs the calling range, so EV ties; strength must break them."""
        records = finder_with_model.solve_range(100000.0, 50000.0, 0.35, OpponentModel.RANGE)
        # The three weakest canonical hands, weakest last (chapter 6: 4-3-3 is the weakest of all 455)
        assert [r.canonical_id for r in records[-3:]] == ["5-3-2", "4-4-2", "4-3-3"]
