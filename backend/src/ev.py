"""Liêng Stealer - Expected Value (EV) Decision Engine.

Implements pure mathematical game-theoretic calculations for pot odds,
fold equity, showdown value, and break-even thresholds in Liêng:
EV = [P(Fold) * Pot] + [1 - P(Fold)] * [(P(Win|Call) * FinalPot) - BetSize]
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class EVResult:
    """Immutable result object encapsulating a complete EV calculation."""
    ev: float
    pot: float
    bet_size: float
    fold_equity: float
    win_rate_when_called: float
    final_pot: float
    break_even_fold_equity: float
    is_profitable: bool


def calculate_ev(
    pot: float,
    bet_size: float,
    fold_equity: float,
    win_rate_when_called: float,
) -> float:
    """Calculate the Expected Value (EV) of a Raise or All-in action.

    Formula:
        EV = [P(Fold) * Pot] + [1 - P(Fold)] * [(P(Win|Call) * FinalPot) - BetSize]
        where FinalPot = Pot + 2 * BetSize.

    Args:
        pot: Current dead money in the pot (must be > 0).
        bet_size: The player's wager / raise amount (must be > 0).
        fold_equity: Opponent's probability of folding, in [0.0, 1.0].
        win_rate_when_called: Hero's equity if opponent calls, in [0.0, 1.0].

    Returns:
        The expected value in units matching pot/bet currency.

    Raises:
        ValueError: If any parameter violates physical/probability bounds.
    """
    if pot <= 0:
        raise ValueError(f"Pot must be strictly positive, got {pot}.")
    if bet_size <= 0:
        raise ValueError(f"Bet size must be strictly positive, got {bet_size}.")
    if not (0.0 <= fold_equity <= 1.0):
        raise ValueError(f"Fold equity must be between 0.0 and 1.0, got {fold_equity}.")
    if not (0.0 <= win_rate_when_called <= 1.0):
        raise ValueError(f"Win rate when called must be between 0.0 and 1.0, got {win_rate_when_called}.")

    final_pot = pot + 2.0 * bet_size
    showdown_value = (win_rate_when_called * final_pot) - bet_size

    ev = (fold_equity * pot) + (1.0 - fold_equity) * showdown_value
    return round(ev, 4)


def calculate_break_even_fold_equity(
    pot: float,
    bet_size: float,
    win_rate_when_called: float,
) -> float:
    """Calculate minimum fold equity required for an action to achieve EV >= 0.

    Solving for f in:
        f * Pot + (1 - f) * ShowdownValue = 0
        f * (Pot - ShowdownValue) = -ShowdownValue
        f = -ShowdownValue / (Pot - ShowdownValue)

    Args:
        pot: Current pot (must be > 0).
        bet_size: Hero bet amount (must be > 0).
        win_rate_when_called: Equity when called, in [0.0, 1.0].

    Returns:
        Required fold equity in [0.0, 1.0]. Returns 0.0 if already profitable.
    """
    if pot <= 0:
        raise ValueError(f"Pot must be strictly positive, got {pot}.")
    if bet_size <= 0:
        raise ValueError(f"Bet size must be strictly positive, got {bet_size}.")
    if not (0.0 <= win_rate_when_called <= 1.0):
        raise ValueError(f"Win rate when called must be between 0.0 and 1.0, got {win_rate_when_called}.")

    final_pot = pot + 2.0 * bet_size
    showdown_value = (win_rate_when_called * final_pot) - bet_size

    # If showdown value is already non-negative, zero fold equity is needed
    if showdown_value >= 0.0:
        return 0.0

    denominator = pot - showdown_value
    if denominator <= 0.0:
        return 0.0

    req_fe = -showdown_value / denominator
    return round(min(1.0, max(0.0, req_fe)), 4)


def is_profitable(ev: float) -> bool:
    """Return True if Expected Value is strictly positive."""
    return ev > 0.0


def evaluate_action(
    pot: float,
    bet_size: float,
    fold_equity: float,
    win_rate_when_called: float,
) -> EVResult:
    """Perform complete financial evaluation and return an EVResult instance."""
    ev = calculate_ev(pot, bet_size, fold_equity, win_rate_when_called)
    be_fe = calculate_break_even_fold_equity(pot, bet_size, win_rate_when_called)
    final_pot = pot + 2.0 * bet_size
    return EVResult(
        ev=ev,
        pot=pot,
        bet_size=bet_size,
        fold_equity=fold_equity,
        win_rate_when_called=win_rate_when_called,
        final_pot=final_pot,
        break_even_fold_equity=be_fe,
        is_profitable=is_profitable(ev),
    )


def profitable_fold_zones(
    pot: float,
    bet_size: float,
    equity_at: Callable[[float], float],
    steps: int = 100,
) -> list[tuple[float, float]]:
    """Scan opponent fold frequencies and return the intervals where raising is +EV.

    When the opponent folds their weakest hands, a higher fold frequency also means
    a stronger calling range, so EV is not monotonic in fold equity: a medium hand
    can be profitable against loose callers, lose in the middle, and become
    profitable again once folds alone pay for the bet.

    Args:
        pot: Current pot (must be > 0).
        bet_size: Hero bet amount (must be > 0).
        equity_at: Maps a fold frequency in [0.0, 1.0] to Hero's equity when called.
        steps: Number of grid intervals over [0.0, 1.0]; resolution is 1 / steps.

    Returns:
        Sorted, non-overlapping (start, end) fold-frequency intervals on the grid
        where EV > 0. Empty if raising is never profitable.

    Raises:
        ValueError: If steps < 1 or pot/bet_size violate calculate_ev bounds.
    """
    if steps < 1:
        raise ValueError(f"Steps must be at least 1, got {steps}.")

    zones: list[tuple[float, float]] = []
    start: float | None = None
    last = 0.0
    for i in range(steps + 1):
        f = i / steps
        if is_profitable(calculate_ev(pot, bet_size, f, equity_at(f))):
            if start is None:
                start = f
            last = f
        elif start is not None:
            zones.append((start, last))
            start = None
    if start is not None:
        zones.append((start, last))
    return zones

