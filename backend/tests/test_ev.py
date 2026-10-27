"""Unit tests for the Expected Value (EV) Decision Engine.

Verifies:
- Mathematical boundary conditions:
    P(Fold) = 1.0 => EV = Pot
    P(Fold) = 0.0, P(Win) = 1.0 => EV = Pot + Bet
    P(Fold) = 0.0, P(Win) = 0.0 => EV = -Bet
- Mathematical bluffing: junk hand (win_rate = 0.05) has EV > 0 when fold_equity = 0.8
- Monotonicity in win rate, and in fold equity for hands whose showdown value is below the pot
  (for strong hands, more folds cost money: the slope of EV in fold equity is P - showdown value)
- Break-even fold equity calculation correctness
- Parameter bound validations and error handling
"""

import pytest

from src.calling_range import CallingRangeModel
from src.ev import (
    calculate_break_even_fold_equity,
    calculate_ev,
    evaluate_action,
    is_profitable,
    profitable_fold_zones,
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
        """At w = 0.5 more folds help, and higher equity always helps."""
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


class TestProfitableFoldZones:
    """Test suite for scanning fold frequencies where raising is +EV."""

    def test_pure_bluff_starts_above_closed_form_threshold(self) -> None:
        """Air needs f > B / (P + B) = 50%; the first grid point strictly above is 51%."""
        zones = profitable_fold_zones(pot=100000.0, bet_size=100000.0, equity_at=lambda f: 0.0)
        assert zones == [(0.51, 1.0)]

    def test_nuts_profitable_everywhere(self) -> None:
        zones = profitable_fold_zones(pot=100000.0, bet_size=100000.0, equity_at=lambda f: 1.0)
        assert zones == [(0.0, 1.0)]

    def test_medium_hand_has_two_zones_against_calling_range(self) -> None:
        """K-Q-3 wins against loose callers and as a bluff, but loses in between."""
        model = CallingRangeModel()
        zones = profitable_fold_zones(
            pot=100000.0,
            bet_size=100000.0,
            equity_at=lambda f: model.equity("K-Q-3", f),
        )
        assert len(zones) == 2
        assert zones[0][0] == 0.0
        assert zones[1] == (0.51, 1.0)

    def test_invalid_steps(self) -> None:
        with pytest.raises(ValueError):
            profitable_fold_zones(pot=100.0, bet_size=50.0, equity_at=lambda f: 0.5, steps=0)


class TestStrongHands:
    def test_folds_hurt_unbeatable_hands(self) -> None:
        """With w = 1 the showdown value P + B exceeds the pot, so every fold gives up a won showdown."""
        evs = [calculate_ev(100000.0, 50000.0, f, 1.0) for f in (0.0, 0.5, 1.0)]
        assert evs == [150000.0, 125000.0, 100000.0]

    def test_final_pot_is_pot_plus_two_bets(self) -> None:
        from src.ev import final_pot

        assert final_pot(100000.0, 50000.0) == 200000.0
