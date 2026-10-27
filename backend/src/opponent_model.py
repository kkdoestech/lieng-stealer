"""Exact showdown equity against a strength-based opponent calling range."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from itertools import combinations_with_replacement
from math import ceil, comb, isfinite

from src.evaluator import Card, Deck, evaluate_hand


def calculate_calling_range_equities(
    hero_cards: Sequence[Card],
    call_range_percents: Sequence[float],
) -> dict[float, float]:
    """Calculate exact equity against the strongest specified share of legal hands.

    The opponent's calling range is modeled as the strongest ``X%`` of all
    three-card hands remaining after removing Hero's cards. Hands tied at the
    cutoff have identical showdown results and are interchangeable.

    Args:
        hero_cards: Hero's three cards.
        call_range_percents: Percentile sizes to calculate, each in ``(0, 100]``.

    Returns:
        Mapping from each requested percentile to win-plus-half-tie equity.

    Raises:
        ValueError: If a percentile is non-finite or outside ``(0, 100]``.
    """
    hero_score = evaluate_hand(hero_cards).score_tuple
    if not call_range_percents:
        return {}

    for percent in call_range_percents:
        if not isfinite(percent) or not 0.0 < percent <= 100.0:
            raise ValueError("Call range percentages must be greater than 0 and at most 100.")

    hero_set = set(hero_cards)
    available_by_rank: dict[int, list[Card]] = {}
    for card in Deck.standard_52():
        if card not in hero_set:
            available_by_rank.setdefault(card.rank.value, []).append(card)

    score_counts: Counter[tuple[int, int, int, int, tuple[int, ...]]] = Counter()
    for ranks in combinations_with_replacement(sorted(available_by_rank), 3):
        rank_counts = Counter(ranks)
        multiplicity = 1
        opponent_cards: list[Card] = []
        for rank, count in rank_counts.items():
            available_cards = available_by_rank[rank]
            if len(available_cards) < count:
                multiplicity = 0
                break
            multiplicity *= comb(len(available_cards), count)
            opponent_cards.extend(available_cards[:count])
        if multiplicity:
            score = evaluate_hand(opponent_cards).score_tuple
            score_counts[score] += multiplicity

    opponent_scores = sorted(score_counts.items(), reverse=True)
    total_opponent_hands = sum(count for _, count in opponent_scores)

    results: dict[float, float] = {}
    for percent in set(call_range_percents):
        called_count = max(1, ceil(total_opponent_hands * percent / 100.0))
        unprocessed = called_count
        wins = 0
        ties = 0
        for score, count in opponent_scores:
            selected_count = min(unprocessed, count)
            if score < hero_score:
                wins += selected_count
            elif score == hero_score:
                ties += selected_count
            unprocessed -= selected_count
            if unprocessed == 0:
                break
        results[percent] = (wins + 0.5 * ties) / called_count
    return results
