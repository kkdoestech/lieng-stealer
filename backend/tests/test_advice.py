"""Tests for the betting advice policy (src/advice.py).

Two layers. The first calls ``recommend`` with literal numbers and asserts the literal answer, one
row per rule of the ordered policy. The second runs the same function over all 455 canonical classes
and checks the invariants that must hold for every hand, so a rule cannot be satisfied by a spot
that happens to look right.

Every expectation here is a number written out, not a recomputation: a test that derived its own
answer from ``recommend`` would pass with the policy deleted.
"""

from __future__ import annotations

import pytest

from src.advice import (
    DEFAULT_THRESHOLDS,
    FOLD_EQUITY_STEP,
    Action,
    AdviceThresholds,
    Blocked,
    FoldCell,
    Kind,
    Reason,
    fold_grid,
    ladder,
    recommend,
)
from src.calling_range import CallingRangeModel, OpponentModel
from src.db import WinRateDB
from src.exceptions import InvalidGameParamsError
from src.range_finder import HandEVRecord, RangeFinder

POT = 100000.0

# The three cells the range model gives each class at fold_equity = 0.35, as the ladder sees them.
MONSTER_CELLS = (FoldCell(0.25, 0.9959), FoldCell(0.35, 0.9952), FoldCell(0.45, 0.9944))
MEDIUM_CELLS = (FoldCell(0.25, 0.142), FoldCell(0.35, 0.0108), FoldCell(0.45, 0.0))
JUNK_CELLS = (FoldCell(0.25, 0.0), FoldCell(0.35, 0.0), FoldCell(0.45, 0.0))
FOLD_RATES = (0.0, 0.1, 0.25, 0.35, 0.5, 0.65, 0.8, 0.9, 1.0)


def _flat(fold_equity: float, equity: float) -> tuple[FoldCell, ...]:
    """Three cells that all share one equity, so the worst cell equals the centre one."""
    return tuple(FoldCell(rate, equity) for rate in fold_grid(fold_equity))


@pytest.fixture(scope="module")
def finder() -> RangeFinder:
    return RangeFinder(WinRateDB("data/winrates.json"), CallingRangeModel())


@pytest.fixture(scope="module")
def range_board(finder: RangeFinder) -> list[HandEVRecord]:
    """Every class priced at pot 100,000 and a 35% fold rate against the calling range."""
    return finder.solve_range(POT, 50000.0, finder.equities(0.35, OpponentModel.RANGE))


# --- The frozen configuration ----------------------------------------------------------------

def test_default_thresholds_are_the_locked_numbers() -> None:
    assert DEFAULT_THRESHOLDS == AdviceThresholds(
        small_fraction=0.33,
        large_fraction=0.75,
        all_in_fraction=1.00,
        min_edge_ratio=0.05,
        all_in_min_equity=0.85,
        large_min_equity=0.50,
        value_equity_floor=0.55,
        bluff_equity_ceiling=0.45,
        fold_step=0.10,
    )
    assert FOLD_EQUITY_STEP == 0.10


@pytest.mark.parametrize(
    "overrides",
    [
        {"small_fraction": 0.80},                       # small is no longer the smallest
        {"large_fraction": 1.20},                       # a rung above the whole pot
        {"all_in_fraction": 1.50},
        {"min_edge_ratio": 0.0},                        # a floor that clears a losing bet
        {"min_edge_ratio": 1.0},
        {"bluff_equity_ceiling": 0.60, "value_equity_floor": 0.55},
        {"large_min_equity": 0.90, "all_in_min_equity": 0.85},
    ],
)
def test_thresholds_reject_an_out_of_order_configuration(overrides: dict[str, float]) -> None:
    with pytest.raises(InvalidGameParamsError):
        AdviceThresholds(**overrides)


def test_fold_grid_clamps_and_deduplicates_at_the_ends() -> None:
    assert fold_grid(0.35) == (0.25, 0.35, 0.45)
    assert fold_grid(0.0) == (0.0, 0.1)
    assert fold_grid(0.05) == (0.0, 0.05, 0.15)
    assert fold_grid(1.0) == (0.9, 1.0)


def test_ladder_is_pot_relative_and_strictly_increasing() -> None:
    assert ladder(100000.0) == (33000.0, 75000.0, 100000.0)
    assert ladder(200000.0) == (66000.0, 150000.0, 200000.0)


# --- One row per rule of the ordered policy --------------------------------------------------

def test_a_monster_shoves_the_whole_pot() -> None:
    advice = recommend(POT, FoldCell(0.35, 0.9952), MONSTER_CELLS)

    assert (advice.action, advice.kind, advice.reason) == (Action.ALL_IN, Kind.VALUE, Reason.ALL_IN_VALUE)
    assert (advice.amount, advice.ev) == (100000.0, 164064.0)
    assert advice.ev_ratio == pytest.approx(1.64064)
    assert (advice.why.fold_component, advice.why.call_component, advice.why.net) == (35000.0, 129064.0, 164064.0)
    assert advice.robust is True and advice.win_rate_defined is True
    assert [(rung.action, rung.ev, rung.eligible) for rung in advice.ladder] == [
        (Action.SMALL_BET, pytest.approx(120932.08), True),
        (Action.LARGE_BET, 147970.0, True),
        (Action.ALL_IN, 164064.0, True),
    ]


def test_a_medium_hand_bluffs_the_smallest_rung() -> None:
    advice = recommend(POT, FoldCell(0.35, 0.0108), MEDIUM_CELLS)

    assert (advice.action, advice.kind, advice.reason) == (Action.SMALL_BET, Kind.BLUFF, Reason.SMALL_BLUFF)
    assert (advice.amount, advice.ev) == (33000.0, 14715.32)
    assert advice.ev_ratio == pytest.approx(0.1471532)
    assert (advice.why.fold_component, advice.why.call_component, advice.why.net) == (35000.0, -20284.68, 14715.32)
    assert [(rung.ev, rung.worst_ev_ratio, rung.blocked_by) for rung in advice.ladder] == [
        (14715.32, pytest.approx(0.1471532), None),
        (-11995.0, pytest.approx(-0.11995), Blocked.EV_BELOW_FLOOR),
        (-27894.0, pytest.approx(-0.27894), Blocked.EV_BELOW_FLOOR),
    ]


def test_a_junk_hand_checks_when_a_small_bet_only_pays_at_your_own_fold_rate() -> None:
    advice = recommend(POT, FoldCell(0.35, 0.0), JUNK_CELLS)

    assert (advice.action, advice.kind, advice.reason) == (Action.CHECK, Kind.BLUFF, Reason.CHECK_ASSUMPTION_FRAGILE)
    assert (advice.amount, advice.ev, advice.ev_ratio) == (0.0, 0.0, 0.0)
    assert (advice.why.fold_component, advice.why.call_component, advice.why.net) == (0.0, 0.0, 0.0)
    assert (advice.ladder[0].ev, advice.ladder[0].worst_ev_ratio) == (13550.0, 0.0025)
    assert advice.ladder[0].eligible is False


def test_a_junk_hand_checks_when_the_worst_cell_pays_under_the_floor() -> None:
    cells = tuple(FoldCell(rate, 0.00236105) for rate in (0.25, 0.35, 0.45))
    advice = recommend(POT, FoldCell(0.35, 0.00236105), cells)

    assert (advice.action, advice.kind, advice.reason) == (Action.CHECK, Kind.BLUFF, Reason.CHECK_ASSUMPTION_FRAGILE)
    assert (advice.ladder[0].ev, advice.ladder[0].worst_ev_ratio) == (pytest.approx(13804.76), pytest.approx(0.0054395, rel=1e-5))


def test_a_junk_hand_bluffs_small_when_the_worst_cell_still_pays() -> None:
    cells = tuple(FoldCell(rate, 0.00236105) for rate in (0.4, 0.5, 0.6))
    advice = recommend(POT, FoldCell(0.5, 0.00236105), cells)

    assert (advice.action, advice.kind, advice.reason) == (Action.SMALL_BET, Kind.BLUFF, Reason.SMALL_BLUFF)
    assert (advice.amount, advice.ev) == (33000.0, pytest.approx(33695.97))
    assert advice.ladder[0].worst_ev_ratio == pytest.approx(0.2043516)
    assert [rung.blocked_by for rung in advice.ladder] == [
        None, Blocked.EV_BELOW_FLOOR, Blocked.EV_BELOW_FLOOR,
    ]


def test_every_size_losing_is_a_check_with_no_edge() -> None:
    advice = recommend(POT, FoldCell(0.0, 0.10), _flat(0.0, 0.10))

    assert (advice.action, advice.reason) == (Action.CHECK, Reason.CHECK_NO_EDGE)
    assert [rung.ev for rung in advice.ladder] == [-16400.0, -50000.0, -70000.0]


def test_an_edge_under_the_floor_is_a_check() -> None:
    advice = recommend(POT, FoldCell(0.0, 0.21), _flat(0.0, 0.21))

    assert (advice.action, advice.reason) == (Action.CHECK, Reason.CHECK_EDGE_TOO_SMALL)
    assert [rung.ev for rung in advice.ladder] == [1860.0, -22500.0, -37000.0]


def test_a_coin_flip_starts_at_the_small_rung() -> None:
    advice = recommend(POT, FoldCell(0.35, 0.50), _flat(0.35, 0.50))

    assert (advice.action, advice.kind, advice.reason) == (Action.SMALL_BET, Kind.THIN_VALUE, Reason.SMALL_THIN)
    assert (advice.amount, advice.ev) == (33000.0, 67500.0)
    assert [rung.blocked_by for rung in advice.ladder] == [
        None,
        Blocked.NEEDS_BIGGER_EDGE,
        Blocked.NEEDS_BIGGER_EDGE,
    ]


def test_a_favourite_starts_at_the_large_rung_and_the_all_in_is_refused() -> None:
    advice = recommend(POT, FoldCell(0.35, 0.60), _flat(0.35, 0.60))

    assert (advice.action, advice.kind, advice.reason) == (Action.LARGE_BET, Kind.VALUE, Reason.LARGE_VALUE)
    assert (advice.amount, advice.ev) == (75000.0, 83750.0)
    assert [rung.blocked_by for rung in advice.ladder] == [None, None, Blocked.NEEDS_BIGGER_EDGE]


def test_a_bluff_never_reaches_a_large_rung_even_when_it_clears_the_floor() -> None:
    advice = recommend(POT, FoldCell(0.90, 0.44), _flat(0.90, 0.44))

    assert (advice.action, advice.kind, advice.reason) == (Action.SMALL_BET, Kind.BLUFF, Reason.SMALL_BLUFF)
    assert advice.amount == 33000.0
    assert [rung.eligible for rung in advice.ladder] == [True, False, False]
    assert [rung.blocked_by for rung in advice.ladder] == [
        None,
        Blocked.BLUFF_TOO_SMALL_ONLY,
        Blocked.BLUFF_TOO_SMALL_ONLY,
    ]


@pytest.mark.parametrize(
    ("equity", "kind", "reason"),
    [
        (0.4499, Kind.BLUFF, Reason.SMALL_BLUFF),
        (0.45, Kind.THIN_VALUE, Reason.SMALL_THIN),
        (0.5499, Kind.THIN_VALUE, Reason.LARGE_THIN),
        (0.55, Kind.VALUE, Reason.LARGE_VALUE),
    ],
)
def test_kind_bands_at_their_boundaries(equity: float, kind: Kind, reason: Reason) -> None:
    advice = recommend(POT, FoldCell(0.35, equity), _flat(0.35, equity))

    assert (advice.kind, advice.reason) == (kind, reason)


def test_nobody_calling_is_not_a_zero_win_rate() -> None:
    """The fold rate is 1.0, so the calling range is empty and the equity is 0.0 by convention."""
    advice = recommend(POT, FoldCell(1.0, 0.0), _flat(1.0, 0.0))

    assert advice.win_rate_defined is False
    assert (advice.action, advice.kind, advice.reason) == (Action.SMALL_BET, Kind.BLUFF, Reason.SMALL_BLUFF)
    assert (advice.amount, advice.ev) == (33000.0, 100000.0)


def test_the_policy_is_deterministic() -> None:
    first = recommend(POT, FoldCell(0.35, 0.0108), MEDIUM_CELLS)
    second = recommend(POT, FoldCell(0.35, 0.0108), MEDIUM_CELLS)

    assert first == second
    assert (first.action, first.amount) == (Action.SMALL_BET, 33000.0)


# --- Invariants over all 455 canonical classes -----------------------------------------------

def test_the_reported_junk_spot_never_shoves(finder: RangeFinder) -> None:
    """The reported 2s 3h 5d spot: no fold rate may turn a 0-point hand into an all-in."""
    for fold_equity in FOLD_RATES:
        records = finder.solve_range(POT, 50000.0, finder.equities(fold_equity, OpponentModel.RANGE))
        junk = next(record for record in records if record.canonical_id == "5-3-2")
        assert junk.advice.action is not Action.ALL_IN, fold_equity

    at_35 = next(
        record.advice
        for record in finder.solve_range(POT, 50000.0, finder.equities(0.35, OpponentModel.RANGE))
        if record.canonical_id == "5-3-2"
    )
    assert (at_35.action, at_35.kind, at_35.reason) == (Action.CHECK, Kind.BLUFF, Reason.CHECK_ASSUMPTION_FRAGILE)
    assert (at_35.amount, at_35.ev) == (0.0, 0.0)


def test_an_all_in_always_means_a_monster_and_a_cleared_floor(range_board: list[HandEVRecord]) -> None:
    shoves = [record for record in range_board if record.advice.action is Action.ALL_IN]

    assert len(shoves) == 54
    for record in shoves:
        advice = record.advice
        assert advice.equity_when_called >= 0.85, record.canonical_id
        assert advice.ev_ratio >= 0.05, record.canonical_id
        assert advice.ladder[2].worst_ev_ratio >= 0.05, record.canonical_id
        assert advice.kind is Kind.VALUE, record.canonical_id


def test_a_bluff_never_bets_large_or_shoves(range_board: list[HandEVRecord]) -> None:
    bluffs = [record.advice for record in range_board if record.advice.kind is Kind.BLUFF]

    assert len(bluffs) == 286
    for advice in bluffs:
        assert advice.action in {Action.CHECK, Action.SMALL_BET}
        assert advice.ladder[1].eligible is False
        assert advice.ladder[2].eligible is False


def test_a_check_wagers_nothing(range_board: list[HandEVRecord]) -> None:
    checks = [record.advice for record in range_board if record.advice.action is Action.CHECK]

    assert len(checks) == 128
    for advice in checks:
        assert (advice.amount, advice.ev, advice.ev_ratio) == (0.0, 0.0, 0.0)
        assert advice.why.net == 0.0


def test_the_answer_is_always_the_first_eligible_rung_from_the_top(range_board: list[HandEVRecord]) -> None:
    """The chosen rung is the highest eligible one, and no higher rung is ever eligible."""
    for record in range_board:
        advice = record.advice
        eligible = [rung.action for rung in advice.ladder if rung.eligible]
        if advice.action is Action.CHECK:
            assert eligible == [], record.canonical_id
        else:
            assert eligible, record.canonical_id
            assert eligible[-1] is advice.action, record.canonical_id


def test_each_rung_reports_its_own_floor_verdict(range_board: list[HandEVRecord]) -> None:
    """An eligible rung clears the floor and names no blocker; every blocked rung names one."""
    for record in range_board:
        for rung in record.advice.ladder:
            if rung.eligible:
                assert rung.blocked_by is None
                assert rung.ev_ratio >= 0.05 and rung.worst_ev_ratio >= 0.05, record.canonical_id
            else:
                assert rung.blocked_by is not None
                if rung.blocked_by is Blocked.EV_BELOW_FLOOR:
                    assert rung.ev_ratio < 0.05 or rung.worst_ev_ratio < 0.05, record.canonical_id
