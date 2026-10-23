"""Unit tests for the Opponent Calling-Range Model (CallingRangeModel).

Verifies:
- Card-removal tables: every Hero row counts exactly C(49, 3) = 18,424 opponent hands
- At 0% fold equity the model reproduces the exact enumeration in winrates.json for all 455 classes
- Equity when called never increases as the opponent folds more (calling range only gets stronger)
- Regression anchors for medium hands, and boundary handling at 100% fold equity
- Full 455-hand equity table stays within the 25 ms range-solve budget
"""

import itertools
import time

import pytest

from src.calling_range import OPPONENT_COMBINATIONS, CallingRangeModel
from src.db import WinRateDB
from tests.perf import budget


@pytest.fixture(scope="module")
def model() -> CallingRangeModel:
    return CallingRangeModel()


@pytest.fixture(scope="module")
def db() -> WinRateDB:
    return WinRateDB("data/winrates.json")


class TestCallingRangeModel:
    """Test suite for equity against a strength-ordered calling range."""

    def test_covers_all_455_classes(self, model: CallingRangeModel) -> None:
        assert len(model) == 455
        assert "K-Q-3" in model
        assert "3-K-Q" not in model

    def test_card_removal_rows_sum_to_18424(self, model: CallingRangeModel) -> None:
        """Each Hero row must count every opponent hand left in the 49-card deck exactly once."""
        assert all(row[-1] == OPPONENT_COMBINATIONS for row in model._prefix)

    def test_zero_fold_matches_exact_enumeration(self, model: CallingRangeModel, db: WinRateDB) -> None:
        """With no folds the calling range is every hand, so equity must equal winrates.json."""
        table = model.equity_table(0.0)
        for cid, stats in db.all_items().items():
            assert table[cid] == pytest.approx(stats.equity, abs=1e-4), cid

    def test_equity_never_increases_with_fold_equity(self, model: CallingRangeModel) -> None:
        tables = [model.equity_table(i / 20) for i in range(21)]
        for weaker_range, stronger_range in itertools.pairwise(tables):
            for cid, equity in stronger_range.items():
                assert equity <= weaker_range[cid] + 1e-9, cid

    def test_nuts_always_win_when_called(self, model: CallingRangeModel) -> None:
        for i in range(100):
            assert model.equity("A-A-A", i / 100) == 1.0

    def test_medium_hands_regression(self, model: CallingRangeModel) -> None:
        """Opponent folding their weakest 35% leaves 3 and 5 points far behind their random-hand equity."""
        assert model.equity("K-Q-3", 0.35) == pytest.approx(0.0108, abs=1e-4)
        assert model.equity("K-Q-5", 0.35) == pytest.approx(0.3097, abs=1e-4)

    def test_full_fold_returns_zero_without_error(self, model: CallingRangeModel) -> None:
        assert model.equity("K-Q-5", 1.0) == 0.0
        assert set(model.equity_table(1.0).values()) == {0.0}

    def test_invalid_inputs(self, model: CallingRangeModel) -> None:
        with pytest.raises(ValueError):
            model.equity("K-Q-5", -0.01)
        with pytest.raises(ValueError):
            model.equity_table(1.01)
        with pytest.raises(KeyError):
            model.equity("Z-Z-Z", 0.5)

    def test_full_table_within_latency_budget(self, model: CallingRangeModel) -> None:
        start = time.perf_counter()
        model.equity_table(0.35)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < budget(25.0)


class TestModelInvariants:
    def test_rejects_a_subset_of_hands(self) -> None:
        from src.exceptions import LiengError
        from src.hands import generate_all_canonical_hands

        with pytest.raises(LiengError, match="22100"):
            CallingRangeModel(generate_all_canonical_hands()[:100])

    def test_rejects_classes_with_equal_strength(self) -> None:
        """Making two classes tie (e.g. all Đĩ equal) must fail loudly, not give wrong equities."""
        import dataclasses

        from src.exceptions import LiengError
        from src.hands import generate_all_canonical_hands

        hands = generate_all_canonical_hands()
        hands[1] = dataclasses.replace(hands[1], score=hands[0].score)
        with pytest.raises(LiengError, match="distinct strength"):
            CallingRangeModel(hands)

    def test_errors_are_project_errors(self, model: CallingRangeModel) -> None:
        from src.exceptions import InvalidGameParamsError, UnknownHandError

        with pytest.raises(UnknownHandError):
            model.equity("J-Q-K", 0.35)
        with pytest.raises(InvalidGameParamsError):
            model.equity("K-Q-3", 1.5)
