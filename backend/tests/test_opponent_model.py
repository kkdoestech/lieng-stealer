"""Tests for exact equity against strength-percentile calling ranges."""

from pathlib import Path

import pytest

from src.db import WinRateDB
from src.evaluator import Hand
from src.opponent_model import calculate_calling_range_equities


def test_full_calling_range_matches_random_opponent_equity() -> None:
    hand = Hand.from_str("2s 3h 5d")
    database = WinRateDB(Path(__file__).resolve().parents[1] / "data" / "winrates.json")
    expected = database.get_by_cards(hand.cards).equity

    actual = calculate_calling_range_equities(hand.cards, [100.0])[100.0]

    assert actual == pytest.approx(expected, abs=1e-8)


def test_weak_hand_has_lower_equity_against_strong_calling_range() -> None:
    hand = Hand.from_str("2s 3h 5d")
    equities = calculate_calling_range_equities(hand.cards, [30.0, 100.0])

    assert equities[30.0] == 0.0
    assert equities[30.0] < equities[100.0]


@pytest.mark.parametrize("percent", [0.0, -1.0, 100.1, float("nan"), float("inf")])
def test_invalid_calling_range_percent_is_rejected(percent: float) -> None:
    hand = Hand.from_str("As Kh Qd")

    with pytest.raises(ValueError, match="Call range percentages"):
        calculate_calling_range_equities(hand.cards, [percent])
