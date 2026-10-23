"""Liêng Stealer - Canonical Hand Isomorphism & State Space Compression.

Collapses the full 22,100 3-card state space into 455 canonical equivalence
classes based on rank multisets. Precomputes combinatorial multiplicities:
  - Three of a kind (Sáp): C(4, 3) = 4 combinations (13 classes -> 52 hands)
  - One pair: C(4, 2) * C(4, 1) = 24 combinations (156 classes -> 3,744 hands)
  - Three distinct ranks: C(4, 1)^3 = 64 combinations (286 classes -> 18,304 hands)
Total combinations sum: 52 + 3,744 + 18,304 = 22,100 hands.
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Sequence
from dataclasses import dataclass

from src.evaluator import (
    Card,
    HandCategory,
    HandScore,
    Rank,
    Suit,
    evaluate_hand,
)
from src.exceptions import InvalidHandSizeError


@dataclass(frozen=True)
class CanonicalHand:
    """Immutable representation of a canonical equivalence class.

    Attributes:
        canonical_id: Normalized string identifier (e.g. 'A-A-A', 'Q-K-A', '9-8-7').
        ranks: Tuple of 3 Rank enums representing the class.
        multiplicity: Total concrete combinations mapping to this class (4, 24, or 64).
        category: HandCategory tier (SAP, LIENG, DI, or DIEM).
        score: HandScore evaluated from this canonical hand.
    """
    canonical_id: str
    ranks: tuple[Rank, Rank, Rank]
    multiplicity: int
    category: HandCategory
    score: HandScore

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, CanonicalHand):
            return NotImplemented
        return self.score < other.score

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, CanonicalHand):
            return NotImplemented
        return self.score > other.score

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CanonicalHand):
            return NotImplemented
        return self.score == other.score

    def __str__(self) -> str:
        return self.canonical_id

    def __repr__(self) -> str:
        return f"CanonicalHand('{self.canonical_id}', cat={self.category.name}, mult={self.multiplicity})"


def get_canonical_id(cards: Sequence[Card]) -> str:
    """Return the normalized canonical identifier string for any 3-card combination.

    Canonical IDs are formatted as descending ranks joined by hyphens,
    with special sequence ordering preserved for Liêng sequences:
      - Liêng sequences: 'Q-K-A', 'A-2-3', '9-8-7', etc.
      - Sáp: 'A-A-A', 'K-K-K', etc.
      - General hands: descending ranks 'A-K-2', 'K-Q-Q', etc.

    Args:
        cards: Sequence of 3 Card instances.

    Returns:
        Formatted canonical ID string.

    Raises:
        InvalidHandSizeError: If len(cards) != 3.
    """
    if len(cards) != 3:
        raise InvalidHandSizeError(f"Expected 3 cards to determine canonical ID, got {len(cards)}.")

    rank_values = sorted([c.rank.value for c in cards])
    sorted_triple = (rank_values[0], rank_values[1], rank_values[2])

    # Special handling for sequence ordering in Liêng
    if sorted_triple == (2, 3, 14):
        return "A-2-3"
    if sorted_triple == (12, 13, 14):
        return "Q-K-A"

    # For all other hands (including 9-8-7, A-A-A, K-K-Q, etc.), sort descending
    sorted_ranks = sorted([c.rank for c in cards], reverse=True)
    return f"{sorted_ranks[0].short_name}-{sorted_ranks[1].short_name}-{sorted_ranks[2].short_name}"


def _compute_multiplicity(ranks: tuple[Rank, Rank, Rank]) -> int:
    """Calculate the number of 3-card combinations mapping to these 3 ranks.

    - 3 identical ranks: C(4, 3) = 4
    - 2 identical ranks (1 pair): C(4, 2) * C(4, 1) = 6 * 4 = 24
    - 3 distinct ranks: C(4, 1)^3 = 64
    """
    r1, r2, r3 = ranks
    if r1 == r2 == r3:
        return 4
    if r1 == r2 or r2 == r3 or r1 == r3:
        return 24
    return 64


def get_representative_cards(canonical_id: str) -> list[Card]:
    """Generate a concrete, valid 3-card hand instance for a given canonical ID.

    Guarantees no suit collisions by using distinct suits (♠, ♥, ♦).

    Args:
        canonical_id: String notation such as 'A-A-A', 'Q-K-A', '9-8-7', 'A-2-3'.

    Returns:
        A list of 3 Card instances with distinct suits.

    Raises:
        InvalidCardError: If rank notations are invalid.
        InvalidHandSizeError: If string does not contain 3 ranks.
    """
    tokens = [t for t in re.split(r"[\s,\-]+", canonical_id.strip()) if t]
    if len(tokens) != 3:
        raise InvalidHandSizeError(f"Canonical ID '{canonical_id}' must consist of 3 ranks.")

    ranks = [Rank.from_str(tok) for tok in tokens]
    # Assign distinct suits to prevent duplicate cards even when ranks are identical
    suits = (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS)
    return [Card(rank=ranks[i], suit=suits[i]) for i in range(3)]


def to_canonical(cards: Sequence[Card]) -> CanonicalHand:
    """Map any concrete 3-card hand to its CanonicalHand representation.

    Args:
        cards: Sequence of 3 Card instances.

    Returns:
        CanonicalHand instance with precomputed score and multiplicity.
    """
    if len(cards) != 3:
        raise InvalidHandSizeError(f"Expected 3 cards, got {len(cards)}.")

    cid = get_canonical_id(cards)
    score = evaluate_hand(cards)

    # Determine canonical rank tuple with sequence handling if applicable
    rank_values = sorted([c.rank.value for c in cards])
    if (rank_values[0], rank_values[1], rank_values[2]) == (2, 3, 14):
        ranks_tuple = (Rank.ACE, Rank.TWO, Rank.THREE)
    elif (rank_values[0], rank_values[1], rank_values[2]) == (12, 13, 14):
        ranks_tuple = (Rank.QUEEN, Rank.KING, Rank.ACE)
    else:
        desc = sorted([c.rank for c in cards], reverse=True)
        ranks_tuple = (desc[0], desc[1], desc[2])

    mult = _compute_multiplicity((cards[0].rank, cards[1].rank, cards[2].rank))
    return CanonicalHand(
        canonical_id=cid,
        ranks=ranks_tuple,
        multiplicity=mult,
        category=score.category,
        score=score,
    )


def generate_all_canonical_hands() -> list[CanonicalHand]:
    """Deterministically enumerate all 455 canonical Liêng equivalence classes.

    Ranks are drawn from combinations with replacement:
      C(13 + 3 - 1, 3) = C(15, 3) = 455 classes.

    Returns:
        A list of exactly 455 CanonicalHand instances.
    """
    canonical_hands: list[CanonicalHand] = []
    all_ranks = list(Rank)

    # combinations_with_replacement generates all multisets of size 3
    for r1, r2, r3 in itertools.combinations_with_replacement(all_ranks, 3):
        # Create representative concrete cards with 3 distinct suits
        rep_cards = [
            Card(rank=r1, suit=Suit.SPADES),
            Card(rank=r2, suit=Suit.HEARTS),
            Card(rank=r3, suit=Suit.DIAMONDS),
        ]
        canon = to_canonical(rep_cards)
        canonical_hands.append(canon)

    return canonical_hands

