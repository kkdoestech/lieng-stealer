"""Liêng Stealer - Assumption Stress Testing for one hand.

The verdict for a hand depends on one opponent assumption: the fold frequency ``f``. Under the
strength-ordered model that single number also fixes the calling range (the opponent folds their
weakest ``f`` share of the 22,100 pre-deal combinations), so this module stresses ``f`` alone and
reports the derived calling range in each cell.

The result is a 3-point grid around the user's assumption. ``ROBUST_BET`` means raising stays
profitable in every cell, ``ROBUST_NO_BET`` means it never is, and ``ASSUMPTION_SENSITIVE`` means
the recommendation flips somewhere inside the grid.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from src.advice import FOLD_EQUITY_STEP, fold_grid
from src.calling_range import CallingRangeModel, OpponentModel
from src.ev import evaluate_action
from src.exceptions import ModelError
from src.range_finder import OpponentEquities


class Verdict(StrEnum):
    """How the verdict moves when the opponent is not exactly what the user assumed."""

    ROBUST_BET = "ROBUST_BET"                    # raising is +EV in every cell
    ROBUST_NO_BET = "ROBUST_NO_BET"              # raising is -EV in every cell
    ASSUMPTION_SENSITIVE = "ASSUMPTION_SENSITIVE"


@dataclass(frozen=True)
class Scenario:
    """One fold frequency, the calling range it implies, and the EV it gives the hand."""

    fold_equity: float
    call_range_percent: float | None      # None under the random model: no strength cut exists
    equity_when_called: float
    ev: float


@dataclass(frozen=True)
class Sensitivity:
    """The 3-point assumption grid around the user's fold frequency."""

    fold_equity_range: tuple[float, float]
    central_equity_when_called: float
    status: Verdict
    scenarios: tuple[Scenario, ...]


def stress_test(
    equities: OpponentEquities,
    calling_model: CallingRangeModel | None,
    canonical_id: str,
    pot: float,
    bet_size: float,
    *,
    fold_step: float = FOLD_EQUITY_STEP,
) -> Sensitivity:
    """Vary the fold frequency around the user's assumption and classify the verdict.

    Args:
        equities: The request's resolved opponent assumption (supplies the central fold rate).
        calling_model: The calling-range tables, required under OpponentModel.RANGE.
        canonical_id: Hero's canonical hand, e.g. 'Q-K-A'.
        pot: Dead pot size before hero's bet (must be > 0).
        bet_size: Additional bet / raise amount (must be > 0).
        fold_step: How far either side of the central fold frequency each cell reaches.

    Returns:
        The three scenarios, their EV range, and the verdict classification.

    Raises:
        ModelError: If RANGE is requested and no CallingRangeModel was supplied.
    """
    if equities.opponent_model is OpponentModel.RANGE and calling_model is None:
        raise ModelError("OpponentModel.RANGE requires a CallingRangeModel.")

    fold_rates = fold_grid(equities.fold_equity, fold_step)
    scenarios: list[Scenario] = []
    for fold_equity in fold_rates:
        if equities.opponent_model is OpponentModel.RANGE:
            # Under RANGE the fold frequency is also the cut: a tighter assumption means a
            # stronger caller and lower equity. Under RANDOM equity is constant.
            assert calling_model is not None  # guarded above; narrows the type for mypy
            equity = calling_model.equity(canonical_id, fold_equity)
            percentile: float | None = round((1.0 - fold_equity) * 100.0, 4)
        else:
            equity = equities.of(canonical_id)
            percentile = None
        scenarios.append(
            Scenario(
                fold_equity=fold_equity,
                call_range_percent=percentile,
                equity_when_called=equity,
                ev=evaluate_action(pot, bet_size, fold_equity, equity).ev,
            )
        )

    scenario_evs = [scenario.ev for scenario in scenarios]
    if all(ev > 0.0 for ev in scenario_evs):
        status = Verdict.ROBUST_BET
    elif all(ev <= 0.0 for ev in scenario_evs):
        status = Verdict.ROBUST_NO_BET
    else:
        status = Verdict.ASSUMPTION_SENSITIVE

    return Sensitivity(
        fold_equity_range=(fold_rates[0], fold_rates[-1]),
        central_equity_when_called=equities.of(canonical_id),
        status=status,
        scenarios=tuple(scenarios),
    )
