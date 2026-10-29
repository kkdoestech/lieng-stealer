"""Liêng Stealer - Betting Advice Policy.

One pure function turns a hand's numbers into one ``Recommendation``: an ordered walk down a
three-rung ladder (a third of the pot, three quarters, the whole pot), where a rung must earn at
least a share of the pot in the centre cell and in the worst of the two fold-rate stress cells.

The policy sees only ``FoldCell`` pairs, so it knows nothing about a database, an opponent model,
a request, or a stack. That is what makes it testable from literals: nine EV numbers in, one frozen
value out.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from src.ev import calculate_ev
from src.exceptions import InvalidGameParamsError

# How far the fold-rate stress cells reach either side of the user's assumption.
FOLD_EQUITY_STEP: Final[float] = 0.10


class Action(StrEnum):
    """What Hero should do."""

    CHECK = "CHECK"
    SMALL_BET = "SMALL_BET"
    LARGE_BET = "LARGE_BET"
    ALL_IN = "ALL_IN"


class Kind(StrEnum):
    """What the hand is, from the win rate alone. Labels never gate value sizing.

    ``NONE`` is never returned: a check still carries the hand's label, so the caller can say
    "check, because this is a bluff" from one code.
    """

    NONE = "NONE"
    BLUFF = "BLUFF"
    THIN_VALUE = "THIN_VALUE"
    VALUE = "VALUE"


class Reason(StrEnum):
    """The one sentence that explains the recommendation."""

    CHECK_NO_EDGE = "CHECK_NO_EDGE"
    CHECK_EDGE_TOO_SMALL = "CHECK_EDGE_TOO_SMALL"
    CHECK_ASSUMPTION_FRAGILE = "CHECK_ASSUMPTION_FRAGILE"
    SMALL_BLUFF = "SMALL_BLUFF"
    SMALL_THIN = "SMALL_THIN"
    SMALL_VALUE = "SMALL_VALUE"
    LARGE_THIN = "LARGE_THIN"
    LARGE_VALUE = "LARGE_VALUE"
    ALL_IN_VALUE = "ALL_IN_VALUE"


class Blocked(StrEnum):
    """Why one rung of the ladder is not the answer."""

    EV_BELOW_FLOOR = "EV_BELOW_FLOOR"
    NEEDS_BIGGER_EDGE = "NEEDS_BIGGER_EDGE"
    BLUFF_TOO_SMALL_ONLY = "BLUFF_TOO_SMALL_ONLY"


@dataclass(frozen=True)
class AdviceThresholds:
    """Every number the policy compares against, validated once at construction.

    Attributes:
        small_fraction: The small rung, as a share of the pot.
        large_fraction: The large rung, as a share of the pot.
        all_in_fraction: The all-in rung, as a share of the pot. The whole pot is the model's
            price ceiling; there is no stack input.
        min_edge_ratio: The EV floor any bet must clear, as a share of the pot.
        all_in_min_equity: Win rate from which shoving may start the walk.
        large_min_equity: Win rate Hero must strictly beat to start at the large rung.
        value_equity_floor: Win rate from which the hand is labelled value.
        bluff_equity_ceiling: Below this win rate the hand is labelled a bluff.
        fold_step: How far the stress cells reach either side of the user's fold frequency.
    """

    small_fraction: float = 0.33
    large_fraction: float = 0.75
    all_in_fraction: float = 1.00
    min_edge_ratio: float = 0.05
    all_in_min_equity: float = 0.85
    large_min_equity: float = 0.50
    value_equity_floor: float = 0.55
    bluff_equity_ceiling: float = 0.45
    fold_step: float = FOLD_EQUITY_STEP

    def __post_init__(self) -> None:
        """Check the ordering every rule below depends on.

        Raises:
            InvalidGameParamsError: If a rung fraction, a win-rate gate, or the EV floor is out of
                order (also a ValueError).
        """
        if not 0.0 < self.small_fraction < self.large_fraction < self.all_in_fraction <= 1.0:
            raise InvalidGameParamsError(
                "Advice rung fractions must satisfy 0 < small < large < all_in <= 1, got "
                f"{self.small_fraction}, {self.large_fraction}, {self.all_in_fraction}."
            )
        if not self.bluff_equity_ceiling < self.value_equity_floor:
            raise InvalidGameParamsError(
                f"bluff_equity_ceiling ({self.bluff_equity_ceiling}) must be below "
                f"value_equity_floor ({self.value_equity_floor})."
            )
        if not self.large_min_equity < self.all_in_min_equity:
            raise InvalidGameParamsError(
                f"large_min_equity ({self.large_min_equity}) must be below "
                f"all_in_min_equity ({self.all_in_min_equity})."
            )
        if not 0.0 < self.min_edge_ratio < 1.0:
            raise InvalidGameParamsError(
                f"min_edge_ratio must be between 0.0 and 1.0, got {self.min_edge_ratio}."
            )


@dataclass(frozen=True)
class FoldCell:
    """One fold frequency and the equity Hero has when called there.

    Attributes:
        fold_equity: Opponent fold frequency in [0.0, 1.0].
        equity_when_called: Hero's showdown equity against the hands that call at that frequency.
    """

    fold_equity: float
    equity_when_called: float


@dataclass(frozen=True)
class Why:
    """The recommended bet's EV, split into the part folds pay for and the part showdown pays for.

    Attributes:
        fold_component: ``fold_equity * pot``, the EV the bet earns when the opponent folds.
        call_component: The rest of the EV, earned in the showdown against a caller.
        net: The rung's total EV, equal to ``fold_component + call_component``.
    """

    fold_component: float
    call_component: float
    net: float


@dataclass(frozen=True)
class Rung:
    """One size on the ladder, priced in the centre cell and in the worst stress cell.

    Attributes:
        action: The bet this rung is.
        amount: The wager, ``round(pot * fraction, 2)``.
        ev: EV in the centre cell.
        ev_ratio: ``ev / pot``.
        worst_ev_ratio: The minimum of ``ev / pot`` over the stress cells.
        robust: True when the worst cell does not lose money.
        eligible: True when this rung may be the answer.
        blocked_by: Why the rung is not eligible, or None when it is.
    """

    action: Action
    amount: float
    ev: float
    ev_ratio: float
    worst_ev_ratio: float
    robust: bool
    eligible: bool
    blocked_by: Blocked | None


@dataclass(frozen=True)
class Recommendation:
    """The answer for one hand: one action, one amount, one sentence, and the rungs behind it.

    Attributes:
        action: What to do.
        kind: What the hand is, from its win rate alone.
        reason: Which rule fired, as a closed code the caller renders into a sentence.
        amount: The wager in VND; 0.0 for a check.
        ev: The recommended action's EV; 0.0 for a check.
        ev_ratio: ``ev / pot``; 0.0 for a check.
        equity_when_called: Hero's equity in the centre cell.
        win_rate_defined: False when nobody can call (the fold rate left the calling range empty),
            so the UI says so instead of showing a 0% win rate.
        robust: True when the answer does not lose money in the worst stress cell.
        why: The recommended EV split into its fold and showdown parts.
        ladder: The small, large, and all-in rungs, in that order.
    """

    action: Action
    kind: Kind
    reason: Reason
    amount: float
    ev: float
    ev_ratio: float
    equity_when_called: float
    win_rate_defined: bool
    robust: bool
    why: Why
    ladder: tuple[Rung, Rung, Rung]


DEFAULT_THRESHOLDS: Final[AdviceThresholds] = AdviceThresholds()

_RUNG_ACTIONS: Final[tuple[Action, Action, Action]] = (Action.SMALL_BET, Action.LARGE_BET, Action.ALL_IN)


def fold_grid(centre: float, step: float = FOLD_EQUITY_STEP) -> tuple[float, ...]:
    """The stress cells around one fold frequency: ``centre - step``, ``centre``, ``centre + step``.

    Args:
        centre: The user's fold frequency, in [0.0, 1.0].
        step: How far either side each neighbouring cell reaches.

    Returns:
        Two or three sorted, de-duplicated fold frequencies inside [0.0, 1.0]. The grid loses a cell
        when a neighbour clamps onto the centre at either end of the range.

    Raises:
        InvalidGameParamsError: If centre is outside [0.0, 1.0] (also a ValueError).
    """
    if not 0.0 <= centre <= 1.0:
        raise InvalidGameParamsError(f"Fold equity must be between 0.0 and 1.0, got {centre}.")
    return tuple(
        sorted({round(max(0.0, centre - step), 10), round(centre, 10), round(min(1.0, centre + step), 10)})
    )


def ladder(pot: float, thresholds: AdviceThresholds = DEFAULT_THRESHOLDS) -> tuple[float, float, float]:
    """The three wagers the policy chooses between, derived from the pot alone.

    Args:
        pot: Dead pot size before Hero's bet (must be > 0).
        thresholds: The rung fractions.

    Returns:
        The small, large, and all-in amounts, strictly increasing.

    Raises:
        InvalidGameParamsError: If pot is not strictly positive (also a ValueError).
    """
    if pot <= 0:
        raise InvalidGameParamsError(f"Pot must be strictly positive, got {pot}.")
    return (
        round(pot * thresholds.small_fraction, 2),
        round(pot * thresholds.large_fraction, 2),
        round(pot * thresholds.all_in_fraction, 2),
    )


def recommend(
    pot: float,
    centre: FoldCell,
    cells: Sequence[FoldCell],
    thresholds: AdviceThresholds = DEFAULT_THRESHOLDS,
) -> Recommendation:
    """Decide what Hero should do with one hand, given its equity at one and three fold rates.

    The walk goes down from the rung the win rate allows, never up: the label comes from the win
    rate, every rung is priced in the centre cell and in the worst stress cell, and the answer is the
    first rung that clears the EV floor in both.

    Args:
        pot: Dead pot size before Hero's bet (must be > 0).
        centre: Hero's equity at the user's fold frequency.
        cells: The stress cells, including the centre one, so the worst case covers the user's own
            assumption.
        thresholds: The numbers the policy compares against.

    Returns:
        One frozen recommendation, with the full ladder so no caller recomputes a rung.

    Raises:
        InvalidGameParamsError: If a cell or the pot is outside its bounds (also a ValueError).
    """
    amounts = ladder(pot, thresholds)
    central = tuple(calculate_ev(pot, amount, centre.fold_equity, centre.equity_when_called) for amount in amounts)
    worst = tuple(
        min(calculate_ev(pot, amount, cell.fold_equity, cell.equity_when_called) for cell in cells)
        for amount in amounts
    )
    ev_ratios = tuple(ev / pot for ev in central)
    worst_ratios = tuple(ev / pot for ev in worst)

    kind = _kind(centre.equity_when_called, thresholds)
    start = _start_rung(centre.equity_when_called, thresholds)
    blockers = tuple(
        _blocker(index, start, kind, central, ev_ratios, worst_ratios, thresholds) for index in range(3)
    )
    rungs = tuple(
        Rung(
            action=action,
            amount=amounts[index],
            ev=central[index],
            ev_ratio=ev_ratios[index],
            worst_ev_ratio=worst_ratios[index],
            robust=worst_ratios[index] >= 0.0,
            eligible=blockers[index] is None,
            blocked_by=blockers[index],
        )
        for index, action in enumerate(_RUNG_ACTIONS)
    )
    built: tuple[Rung, Rung, Rung] = (rungs[0], rungs[1], rungs[2])
    # A fold rate of 1.0 leaves the calling range empty, and the range model reports equity 0.0
    # there; a random caller keeps its real equity at the same fold rate, so only that case reads 0.
    win_rate_defined = not (centre.fold_equity >= 1.0 and centre.equity_when_called == 0.0)

    chosen = next((index for index in range(start, -1, -1) if blockers[index] is None), None)
    if chosen is None:
        return Recommendation(
            action=Action.CHECK,
            kind=kind,
            reason=_check_reason(central, ev_ratios, thresholds),
            amount=0.0,
            ev=0.0,
            ev_ratio=0.0,
            equity_when_called=centre.equity_when_called,
            win_rate_defined=win_rate_defined,
            robust=True,
            why=Why(0.0, 0.0, 0.0),
            ladder=built,
        )

    fold_component = centre.fold_equity * pot
    return Recommendation(
        action=_RUNG_ACTIONS[chosen],
        kind=kind,
        reason=_bet_reason(chosen, kind),
        amount=amounts[chosen],
        ev=central[chosen],
        ev_ratio=ev_ratios[chosen],
        equity_when_called=centre.equity_when_called,
        win_rate_defined=win_rate_defined,
        robust=worst_ratios[chosen] >= 0.0,
        why=Why(fold_component, central[chosen] - fold_component, central[chosen]),
        ladder=built,
    )


def _kind(equity: float, thresholds: AdviceThresholds) -> Kind:
    if equity >= thresholds.value_equity_floor:
        return Kind.VALUE
    if equity >= thresholds.bluff_equity_ceiling:
        return Kind.THIN_VALUE
    return Kind.BLUFF


def _start_rung(equity: float, thresholds: AdviceThresholds) -> int:
    if equity >= thresholds.all_in_min_equity:
        return 2
    if equity > thresholds.large_min_equity:
        return 1
    return 0


def _blocker(
    index: int,
    start: int,
    kind: Kind,
    central: Sequence[float],
    ev_ratios: Sequence[float],
    worst_ratios: Sequence[float],
    thresholds: AdviceThresholds,
) -> Blocked | None:
    if ev_ratios[index] < thresholds.min_edge_ratio or worst_ratios[index] < thresholds.min_edge_ratio:
        return Blocked.EV_BELOW_FLOOR
    if kind is Kind.BLUFF and index > 0:
        # The label, not a number, is what forbids this size: a bluff may never risk more than small.
        return Blocked.BLUFF_TOO_SMALL_ONLY
    if index > start:
        return Blocked.NEEDS_BIGGER_EDGE
    if index == 2 and (kind is not Kind.VALUE or central[2] <= central[1]):
        return Blocked.NEEDS_BIGGER_EDGE
    return None


def _check_reason(
    central: Sequence[float],
    ev_ratios: Sequence[float],
    thresholds: AdviceThresholds,
) -> Reason:
    if max(central) <= 0.0:
        return Reason.CHECK_NO_EDGE
    if max(ev_ratios) < thresholds.min_edge_ratio:
        return Reason.CHECK_EDGE_TOO_SMALL
    return Reason.CHECK_ASSUMPTION_FRAGILE


def _bet_reason(index: int, kind: Kind) -> Reason:
    if index == 2:
        return Reason.ALL_IN_VALUE
    if index == 1:
        return Reason.LARGE_THIN if kind is Kind.THIN_VALUE else Reason.LARGE_VALUE
    if kind is Kind.BLUFF:
        return Reason.SMALL_BLUFF
    return Reason.SMALL_THIN if kind is Kind.THIN_VALUE else Reason.SMALL_VALUE
