"""Unit tests for the Expected Value (EV) Decision Engine.

Verifies:
- Mathematical boundary conditions:
    P(Fold) = 1.0 => EV = Pot
    P(Fold) = 0.0, P(Win) = 1.0 => EV = Pot + Bet
    P(Fold) = 0.0, P(Win) = 0.0 => EV = -Bet
- Mathematical bluffing: junk hand (win_rate = 0.05) has EV > 0 when fold_equity = 0.8
- Strict monotonicity with respect to fold equity and win rate
- Break-even fold equity calculation correctness
- Parameter bound validations and error handling
"""

import pytest

from src.ev import (
    calculate_break_even_fold_equity,
    calculate_ev,
    evaluate_action,
    is_profitable,
)


class TestEVEngine:
    """Test suite for mathematical EV calculations."""

    def test_boundary_all_fold(self) -> None:
        """When opponent folds 100% of the time, EV must equal the dead pot."""
        pot = 100000.0
        bet = 50000.0
        ev = calculate_ev(pot=pot, bet_size=bet, fold_equity=1.0, win_rate_when_called=0.0)
        assert ev == pot

    def test_boundary_zero_fold_nuts(self) -> None:
        """When opponent never folds and hero wins 100%, EV = Pot + Bet."""
        pot = 100000.0
        bet = 50000.0
        ev = calculate_ev(pot=pot, bet_size=bet, fold_equity=0.0, win_rate_when_called=1.0)
        # FinalPot = 100k + 100k = 200k; Payoff = 200k - 50k = 150k = pot + bet
        assert ev == pot + bet

    def test_boundary_zero_fold_zero_equity(self) -> None:
        """When opponent never folds and hero has zero equity, EV = -Bet."""
        pot = 100000.0
        bet = 50000.0
        ev = calculate_ev(pot=pot, bet_size=bet, fold_equity=0.0, win_rate_when_called=0.0)
        assert ev == -bet

    def test_bluff_profitability(self) -> None:
        """A junk hand (5% win rate when called) must yield positive EV if fold equity is 80%."""
        pot = 100000.0
        bet = 50000.0
        ev = calculate_ev(pot=pot, bet_size=bet, fold_equity=0.80, win_rate_when_called=0.05)
        # Fold component: 0.8 * 100k = 80k
        # Call component: 0.2 * (0.05 * 200k - 50k) = 0.2 * (10k - 50k) = -8k
        # Net EV = 80k - 8k = 72k > 0
        assert ev == 72000.0
        assert is_profitable(ev) is True

    def test_small_positive_ev_is_not_rounded_to_break_even(self) -> None:
        """Keep EV sign accurate near zero; display rounding must not change the action."""
        ev = calculate_ev(
            pot=1.0,
            bet_size=0.5,
            fold_equity=0.0,
            win_rate_when_called=0.250001,
        )
        assert 0.0 < ev < 0.0001
        assert is_profitable(ev) is True

    def test_monotonicity(self) -> None:
        """Increasing fold equity or win rate must strictly increase EV."""
        pot = 100000.0
        bet = 50000.0

        ev_fe_low = calculate_ev(pot=pot, bet_size=bet, fold_equity=0.2, win_rate_when_called=0.5)
        ev_fe_high = calculate_ev(pot=pot, bet_size=bet, fold_equity=0.6, win_rate_when_called=0.5)
        assert ev_fe_high > ev_fe_low

        ev_win_low = calculate_ev(pot=pot, bet_size=bet, fold_equity=0.4, win_rate_when_called=0.3)
        ev_win_high = calculate_ev(pot=pot, bet_size=bet, fold_equity=0.4, win_rate_when_called=0.7)
        assert ev_win_high > ev_win_low

    def test_break_even_fold_equity(self) -> None:
        """At break-even fold equity, calculated EV must be approximately zero."""
        pot = 100000.0
        bet = 50000.0
        win_rate = 0.20

        be_fe = calculate_break_even_fold_equity(pot, bet, win_rate)
        assert 0.0 <= be_fe <= 1.0

        ev_at_be = calculate_ev(pot, bet, be_fe, win_rate)
        # 4 decimal places on be_fe introduces at most ~0.005% rounding delta on a 100k pot
        assert abs(ev_at_be) <= 5.0
        assert abs(ev_at_be) / pot < 0.0001

    def test_break_even_for_profitable_showdown(self) -> None:
        """If showdown alone is profitable, break-even fold equity is 0.0."""
        pot = 100000.0
        bet = 50000.0
        # Final pot = 200k. Win rate = 80% => Showdown value = 160k - 50k = 110k > 0
        be_fe = calculate_break_even_fold_equity(pot, bet, 0.80)
        assert be_fe == 0.0

    def test_parameter_validations(self) -> None:
        """Verify invalid parameter values raise ValueError."""
        with pytest.raises(ValueError):
            calculate_ev(pot=-10.0, bet_size=50.0, fold_equity=0.5, win_rate_when_called=0.5)
        with pytest.raises(ValueError):
            calculate_ev(pot=100.0, bet_size=0.0, fold_equity=0.5, win_rate_when_called=0.5)
        with pytest.raises(ValueError):
            calculate_ev(pot=100.0, bet_size=50.0, fold_equity=1.5, win_rate_when_called=0.5)
        with pytest.raises(ValueError):
            calculate_ev(pot=100.0, bet_size=50.0, fold_equity=0.5, win_rate_when_called=-0.1)

    @pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf")])
    def test_non_finite_parameters_are_rejected(self, invalid: float) -> None:
        """Reject values that would otherwise propagate undefined EV results."""
        with pytest.raises(ValueError, match="finite"):
            calculate_ev(
                pot=invalid,
                bet_size=50.0,
                fold_equity=0.5,
                win_rate_when_called=0.5,
            )
        with pytest.raises(ValueError, match="finite"):
            calculate_break_even_fold_equity(
                pot=100.0,
                bet_size=50.0,
                win_rate_when_called=invalid,
            )

    def test_evaluate_action_helper(self) -> None:
        """Verify evaluate_action returns complete EVResult object."""
        res = evaluate_action(pot=100000.0, bet_size=50000.0, fold_equity=0.40, win_rate_when_called=0.60)
        assert res.pot == 100000.0
        assert res.bet_size == 50000.0
        assert res.final_pot == 200000.0
        assert res.is_profitable is True
        assert res.ev > 0.0
