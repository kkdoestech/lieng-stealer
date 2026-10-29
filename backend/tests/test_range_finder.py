"""Unit tests for the Range Solver Engine (RangeFinder) and its single equity source.

Verifies:
- All 455 canonical hands are evaluated by solve_range()
- When fold equity is 100%, all 22,100 combinations yield positive EV and coverage is 100.0%
- When fold equity is 0%, only hands exceeding the required pot odds threshold are profitable
- Monotonicity: Increasing fold equity strictly increases or maintains range coverage
- Opponent models: the inequity source honours the model; equal-EV hands are ordered by strength
- One answer per hand: the single-hand solution IS the matching row of the 455-class table
- The advice board: the centre cell of fold_cells is the reported equity, for every class
"""

import pytest

from src.calling_range import CallingRangeModel, OpponentModel
from src.db import WinRateDB
from src.evaluator import Hand
from src.exceptions import DatabaseNotLoadedError, ModelError
from src.hands import generate_all_canonical_hands, get_representative_cards
from src.range_finder import OpponentEquities, RangeFinder, category_breakdown


def _equities(finder: RangeFinder, fold_equity: float, model: OpponentModel = OpponentModel.RANDOM) -> OpponentEquities:
    """The one equity source a request would build for these inputs."""
    return finder.equities(fold_equity, model)


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
        records = loaded_finder.solve_range(100000.0, 50000.0, _equities(loaded_finder, 0.35))
        assert len(records) == 455

        # Check descending sort order by EV
        for i in range(len(records) - 1):
            assert records[i].ev >= records[i + 1].ev

    def test_pure_fold_equity_100_percent(self, loaded_finder: RangeFinder) -> None:
        """When fold equity is 1.0, all 22,100 combinations yield EV = pot, and coverage is 100.0%."""
        pot = 100000.0
        bet = 50000.0
        equities = _equities(loaded_finder, 1.0)
        records = loaded_finder.solve_range(pot, bet, equities)
        assert len(records) == 455

        # All hands must yield EV = pot
        for r in records:
            assert r.ev == pot
            assert r.is_raise_profitable is True

        profitable = loaded_finder.get_profitable_range(pot, bet, equities)
        assert len(profitable) == 455

        coverage = loaded_finder.calculate_range_coverage(profitable)
        assert coverage == 100.0

    def test_pure_fold_equity_zero_tight_range(self, loaded_finder: RangeFinder) -> None:
        """When fold equity is 0.0, only hands meeting pot odds are profitable."""
        pot = 100000.0
        bet = 50000.0
        # Final pot = 200k. Required equity = 50k / 200k = 0.25 (25%)
        threshold_equity = bet / (pot + 2.0 * bet)

        profitable = loaded_finder.get_profitable_range(pot, bet, _equities(loaded_finder, 0.0))

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
            loaded_finder.get_profitable_range(pot, bet, _equities(loaded_finder, 0.0))
        )
        cov_25 = loaded_finder.calculate_range_coverage(
            loaded_finder.get_profitable_range(pot, bet, _equities(loaded_finder, 0.25))
        )
        cov_50 = loaded_finder.calculate_range_coverage(
            loaded_finder.get_profitable_range(pot, bet, _equities(loaded_finder, 0.50))
        )
        cov_100 = loaded_finder.calculate_range_coverage(
            loaded_finder.get_profitable_range(pot, bet, _equities(loaded_finder, 1.0))
        )

        assert cov_0 <= cov_25 <= cov_50 <= cov_100
        assert cov_100 == 100.0


class TestOpponentModels:
    """Test suite for the opponent-model parameter of RangeFinder."""

    def test_profitable_range_respects_opponent_model(self, finder_with_model: RangeFinder) -> None:
        """A pot-sized bet at 35% folds: 387 classes profit vs random callers, only 250 vs a calling range."""
        random_range = finder_with_model.get_profitable_range(
            100000.0, 100000.0, _equities(finder_with_model, 0.35)
        )
        calling_range = finder_with_model.get_profitable_range(
            100000.0, 100000.0, _equities(finder_with_model, 0.35, OpponentModel.RANGE)
        )
        assert len(random_range) == 387
        assert len(calling_range) == 250

    def test_equal_ev_hands_are_ordered_strongest_first(self, finder_with_model: RangeFinder) -> None:
        """At 35% folds every weak hand has 0 equity vs the calling range, so EV ties; strength must break them."""
        records = finder_with_model.solve_range(
            100000.0, 50000.0, _equities(finder_with_model, 0.35, OpponentModel.RANGE)
        )
        # The three weakest canonical hands, weakest last (chapter 6: 4-3-3 is the weakest of all 455)
        assert [r.canonical_id for r in records[-3:]] == ["5-3-2", "4-4-2", "4-3-3"]


class TestOneAnswerPerHand:
    """The single-hand answer must be the table's own row, by construction."""

    def test_hand_solution_is_the_table_row_for_every_class(self, finder_with_model: RangeFinder) -> None:
        """One answer per hand: hand_solution's record IS the matching element of solve_range."""
        equities = _equities(finder_with_model, 0.35, OpponentModel.RANGE)
        records = finder_with_model.solve_range(100000.0, 50000.0, equities)
        by_class = {record.canonical_id: record for record in records}
        for canonical in generate_all_canonical_hands():
            solution = finder_with_model.hand_solution(
                Hand.from_cards(*get_representative_cards(canonical.canonical_id)),
                records,
                equities,
                100000.0,
                50000.0,
            )
            assert solution.record is by_class[canonical.canonical_id], canonical.canonical_id
            assert solution.record.equity == equities.of(canonical.canonical_id)

    def test_equity_table_is_immutable(self, finder_with_model: RangeFinder) -> None:
        equities = _equities(finder_with_model, 0.35, OpponentModel.RANGE)
        with pytest.raises(TypeError):
            equities.table()["Q-K-A"] = 0.0  # type: ignore[index]

    def test_hand_solution_zones_stay_inside_the_fold_grid(self, finder_with_model: RangeFinder) -> None:
        equities = _equities(finder_with_model, 0.35, OpponentModel.RANGE)
        records = finder_with_model.solve_range(100000.0, 50000.0, equities)
        solution = finder_with_model.hand_solution(
            Hand.from_str("As Kh Qd"), records, equities, 100000.0, 50000.0
        )
        assert solution.zones, "EV at fold_equity=1.0 is the pot, so a profitable zone always exists"
        assert all(0.0 <= start <= end <= 1.0 for start, end in solution.zones)


class TestFoldCells:
    """The advice ladder reads the same equity source as the reported number, one cell at a time."""

    @pytest.mark.parametrize("fold_equity", [0.0, 0.2, 0.35, 0.5, 0.75, 1.0])
    @pytest.mark.parametrize("model", [OpponentModel.RANGE, OpponentModel.RANDOM])
    def test_centre_column_equals_equities(
        self, finder_with_model: RangeFinder, fold_equity: float, model: OpponentModel
    ) -> None:
        board = finder_with_model.fold_cells(fold_equity, model)
        equities = _equities(finder_with_model, fold_equity, model)

        assert len(board) == 455
        for canonical in generate_all_canonical_hands():
            cells = board[canonical.canonical_id]
            centre = next(cell for cell in cells if cell.fold_equity == round(fold_equity, 10))
            assert centre.equity_when_called == equities.of(canonical.canonical_id), canonical.canonical_id

    def test_grid_is_a_step_either_side_and_clamps_at_the_ends(self, finder_with_model: RangeFinder) -> None:
        def rates(fold_equity: float) -> list[float]:
            return [cell.fold_equity for cell in finder_with_model.fold_cells(fold_equity, OpponentModel.RANGE)["Q-K-A"]]

        assert rates(0.35) == [0.25, 0.35, 0.45]
        assert rates(0.0) == [0.0, 0.1]
        assert rates(1.0) == [0.9, 1.0]

    def test_range_cells_price_the_calling_range_at_each_fold_rate(self, finder_with_model: RangeFinder) -> None:
        """A tighter fold assumption is a stronger caller, so the off-centre cells are priced too."""
        cells = finder_with_model.fold_cells(0.35, OpponentModel.RANGE)["5-3-2"]
        assert [(cell.fold_equity, cell.equity_when_called) for cell in cells] == [(0.25, 0.0), (0.35, 0.0), (0.45, 0.0)]

    def test_random_cells_reuse_one_stored_equity(self, finder_with_model: RangeFinder) -> None:
        cells = finder_with_model.fold_cells(0.35, OpponentModel.RANDOM)["5-3-2"]
        assert [cell.equity_when_called for cell in cells] == [0.00236105, 0.00236105, 0.00236105]


class TestConstructionAndSummaries:
    def test_requires_a_loaded_database(self) -> None:
        with pytest.raises(DatabaseNotLoadedError):
            RangeFinder(WinRateDB())

    def test_category_breakdown_totals(self, loaded_finder: RangeFinder) -> None:
        rows = category_breakdown(loaded_finder.solve_range(100000.0, 50000.0, _equities(loaded_finder, 0.0)))
        assert [(r.category.name, r.classes, r.combos) for r in rows] == [
            ("SAP", 13, 52), ("LIENG", 12, 768), ("DI", 6, 144), ("DIEM", 424, 21136),
        ]


def test_range_model_without_calling_model_is_a_model_error(loaded_finder: RangeFinder) -> None:
    with pytest.raises(ModelError):
        loaded_finder.equities(0.35, OpponentModel.RANGE)


def test_random_model_equities_are_the_database_rates(loaded_finder: RangeFinder) -> None:
    equities = _equities(loaded_finder, 0.35)
    for cid, stats in loaded_finder._db.all_items().items():
        assert equities.of(cid) == stats.equity
