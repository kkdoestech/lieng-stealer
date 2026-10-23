"""Liêng Stealer - Core Domain Models and Hand Evaluation Engine.

Provides immutable representations of Cards, Decks, Hands, and HandScores,
with a strict total ordering adhering to Liêng rules:
Sáp (Category 4) > Liêng (Category 3) > Đĩ (Category 2) > Điểm (Category 1).
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import Enum, IntEnum
from functools import cached_property
from typing import Final

from src.exceptions import DuplicateCardError, InvalidCardError, InvalidHandSizeError


class Suit(Enum):
    """Card suits with standardized single-letter codes and symbols."""
    SPADES = "s"
    CLUBS = "c"
    DIAMONDS = "d"
    HEARTS = "h"

    @property
    def symbol(self) -> str:
        """Return Unicode symbol for the suit."""
        return _SUIT_SYMBOLS[self]

    @classmethod
    def from_str(cls, suit_str: str) -> Suit:
        """Parse suit from single-character representation or unicode symbol."""
        suit = _SUIT_BY_TEXT.get(suit_str.strip().lower())
        if suit is None:
            raise InvalidCardError(f"Invalid suit '{suit_str}'. Must be one of s, c, d, h or ♠, ♣, ♦, ♥.")
        return suit


class Rank(IntEnum):
    """Card ranks ordered by strength (2 lowest, Ace highest)."""
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14

    @property
    def short_name(self) -> str:
        """Compact rank string representation."""
        return _RANK_NAMES[self]

    @property
    def point_value(self) -> int:
        """Card point value for Điểm calculation: Ace=1, 2-9=Face, 10/J/Q/K=0."""
        if self == Rank.ACE:
            return 1
        if self.value >= 10:
            return 0
        return self.value

    @property
    def is_face_card(self) -> bool:
        """Return True if the rank is a face card (Jack, Queen, King)."""
        return self in (Rank.JACK, Rank.QUEEN, Rank.KING)

    @classmethod
    def from_str(cls, rank_str: str) -> Rank:
        """Parse rank from string."""
        rank = _RANK_BY_TEXT.get(rank_str.strip().upper())
        if rank is None:
            raise InvalidCardError(f"Invalid rank '{rank_str}'. Must be 2-10, T, J, Q, K, or A.")
        return rank


# Lookup tables used by the enums above. They live at module level because a dict assigned inside
# an Enum class body would become an enum member, and building them once avoids per-call work.
_SUIT_SYMBOLS: Final[dict[Suit, str]] = {
    Suit.SPADES: "♠",
    Suit.CLUBS: "♣",
    Suit.DIAMONDS: "♦",
    Suit.HEARTS: "♥",
}
_SUIT_BY_TEXT: Final[dict[str, Suit]] = {
    **{suit.value: suit for suit in Suit},
    **{symbol: suit for suit, symbol in _SUIT_SYMBOLS.items()},
}
_RANK_NAMES: Final[dict[Rank, str]] = {
    **{rank: str(rank.value) for rank in Rank if rank <= Rank.TEN},
    Rank.JACK: "J",
    Rank.QUEEN: "Q",
    Rank.KING: "K",
    Rank.ACE: "A",
}
_RANK_BY_TEXT: Final[dict[str, Rank]] = {
    **{name: rank for rank, name in _RANK_NAMES.items()},
    "T": Rank.TEN,
}


@dataclass(frozen=True)
class Card:
    """Immutable representation of a playing card."""
    rank: Rank
    suit: Suit

    @property
    def point_value(self) -> int:
        """Return point contribution (0-9)."""
        return self.rank.point_value

    @property
    def is_face_card(self) -> bool:
        """Return True if card is Jack, Queen, or King."""
        return self.rank.is_face_card

    @classmethod
    def from_str(cls, card_str: str) -> Card:
        """Parse a card string such as 'Ah', '9d', '10c', or 'Ts'.

        Args:
            card_str: Compact card notation string.

        Returns:
            A frozen Card instance.

        Raises:
            InvalidCardError: If the card string format is invalid.
        """
        cleaned = card_str.strip()
        if len(cleaned) < 2:
            raise InvalidCardError(f"Card string '{card_str}' is too short.")

        if cleaned.upper().startswith("10"):
            rank_part = cleaned[:2]
            suit_part = cleaned[2:]
        else:
            rank_part = cleaned[0]
            suit_part = cleaned[1:]

        try:
            rank = Rank.from_str(rank_part)
            suit = Suit.from_str(suit_part)
        except InvalidCardError as err:
            # Name the whole card: "11h" alone would otherwise be reported as "Invalid rank '1'".
            raise InvalidCardError(f"Invalid card '{cleaned}': {err}") from err
        return cls(rank=rank, suit=suit)

    def __str__(self) -> str:
        return f"{self.rank.short_name}{self.suit.value}"

    def __repr__(self) -> str:
        return f"Card('{self}')"


class Deck:
    """Factory for standard 52-card French decks."""

    @staticmethod
    def standard_52() -> tuple[Card, ...]:
        """Generate a complete immutable standard 52-card deck."""
        return tuple(
            Card(rank=r, suit=s)
            for r in Rank
            for s in Suit
        )


class HandCategory(IntEnum):
    """Strict hierarchical categories in Liêng."""
    DIEM = 1
    DI = 2
    LIENG = 3
    SAP = 4

    @property
    def display_name(self) -> str:
        """Human-readable category name."""
        return _CATEGORY_NAMES[self]


_CATEGORY_NAMES: Final[dict[HandCategory, str]] = {
    HandCategory.DIEM: "Điểm",
    HandCategory.DI: "Đĩ",
    HandCategory.LIENG: "Liêng",
    HandCategory.SAP: "Sáp",
}


# Predefined canonical Liêng sequences mapped to strength (1 = lowest, 12 = highest).
# Notice: K-A-2 is strictly absent, preventing wrap-around.
_LIENG_SEQUENCES: Final[dict[tuple[int, int, int], int]] = {
    (2, 3, 14): 1,   # A-2-3 (Lowest Liêng)
    (2, 3, 4): 2,    # 2-3-4
    (3, 4, 5): 3,    # 3-4-5
    (4, 5, 6): 4,    # 4-5-6
    (5, 6, 7): 5,    # 5-6-7
    (6, 7, 8): 6,    # 6-7-8
    (7, 8, 9): 7,    # 7-8-9
    (8, 9, 10): 8,   # 8-9-10
    (9, 10, 11): 9,  # 9-10-J
    (10, 11, 12): 10, # 10-J-Q
    (11, 12, 13): 11, # J-Q-K
    (12, 13, 14): 12, # Q-K-A (Highest Liêng)
}

_LIENG_NAMES: Final[dict[int, str]] = {
    1: "A-2-3",
    2: "2-3-4",
    3: "3-4-5",
    4: "4-5-6",
    5: "5-6-7",
    6: "6-7-8",
    7: "7-8-9",
    8: "8-9-10",
    9: "9-10-J",
    10: "10-J-Q",
    11: "J-Q-K",
    12: "Q-K-A",
}


@dataclass(frozen=True, order=False)
class HandScore:
    """Standardized comparable score tuple for total ordering in Liêng.

    Attributes:
        category: Hierarchical category (SAP > LIENG > DI > DIEM).
        primary_rank: Category-specific primary strength value.
        secondary_rank: Secondary tie-breaker value.
        score: Modulo 10 points (0-9) for DIEM, 0 otherwise.
        tie_breaker: Additional rank tuple for fine-grained showdown comparison.
        name: Human-readable description of the hand.
    """
    category: HandCategory
    primary_rank: int
    secondary_rank: int
    score: int
    tie_breaker: tuple[int, ...]
    name: str

    @property
    def score_tuple(self) -> tuple[int, int, int, int, tuple[int, ...]]:
        """Normalized comparison tuple supporting lexicographical comparison."""
        return (
            self.category.value,
            self.primary_rank,
            self.secondary_rank,
            self.score,
            self.tie_breaker,
        )

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, HandScore):
            return NotImplemented
        return self.score_tuple < other.score_tuple

    def __le__(self, other: object) -> bool:
        if not isinstance(other, HandScore):
            return NotImplemented
        return self.score_tuple <= other.score_tuple

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, HandScore):
            return NotImplemented
        return self.score_tuple > other.score_tuple

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, HandScore):
            return NotImplemented
        return self.score_tuple >= other.score_tuple

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, HandScore):
            return NotImplemented
        return self.score_tuple == other.score_tuple

    def __hash__(self) -> int:
        # Must agree with __eq__: equal scores hash equally, whatever their display name.
        return hash(self.score_tuple)

    def __str__(self) -> str:
        return self.name


def calculate_points(cards: Iterable[Card]) -> int:
    """Compute raw sum of card values modulo 10."""
    return sum(card.point_value for card in cards) % 10


def evaluate_hand(cards: Sequence[Card]) -> HandScore:
    """Evaluate a 3-card Liêng hand with strict total ordering.

    Hierarchical evaluation rules:
      1. Sáp (Cat 4): 3 cards of identical rank. A-A-A is strongest, 2-2-2 weakest.
      2. Liêng (Cat 3): 3 consecutive cards. Q-K-A is strongest, A-2-3 weakest.
         No wraparound across K-A-2.
      3. Đĩ (Cat 2): 3 face cards (J, Q, K) excluding Sáp and Liêng.
         Strictly beats any Điểm hand, including 9 points.
      4. Điểm (Cat 1): Score = sum(CardValue) mod 10 (0 to 9).

    Suits never change a hand's strength, so every score is looked up in a 455-entry table keyed
    by the sorted ranks (built once at import by ``_score_for_sorted_ranks``).

    Args:
        cards: A sequence of exactly 3 unique Card instances.

    Returns:
        A fully-populated HandScore instance.

    Raises:
        InvalidHandSizeError: If card count != 3.
        DuplicateCardError: If the same card appears twice (a subclass of InvalidHandSizeError).
    """
    if len(cards) != 3:
        raise InvalidHandSizeError(f"A Liêng hand must contain exactly 3 cards, got {len(cards)}.")

    c1, c2, c3 = cards[0], cards[1], cards[2]
    r1, r2, r3 = c1.rank, c2.rank, c3.rank
    # Two cards are equal only if both rank and suit match; suits are enum singletons.
    if (r1 == r2 and c1.suit is c2.suit) or (r2 == r3 and c2.suit is c3.suit) or (r1 == r3 and c1.suit is c3.suit):
        raise DuplicateCardError("A Liêng hand cannot contain duplicate cards.")

    if r1 > r2:
        r1, r2 = r2, r1
    if r2 > r3:
        r2, r3 = r3, r2
    if r1 > r2:
        r1, r2 = r2, r1
    return _SCORE_BY_RANKS[(r1, r2, r3)]


def _score_for_sorted_ranks(r1: int, r2: int, r3: int) -> HandScore:
    """Score three rank values given in ascending order (the rules of evaluate_hand)."""
    descending_ranks = (r3, r2, r1)

    # 1. Check Sáp (Three of a Kind)
    if r1 == r3:
        return HandScore(
            category=HandCategory.SAP,
            primary_rank=r1,
            secondary_rank=0,
            score=0,
            tie_breaker=descending_ranks,
            name=f"Sáp {Rank(r1).short_name}",
        )

    # 2. Check Liêng (Straight / Consecutive Sequence)
    sorted_triple = (r1, r2, r3)
    if sorted_triple in _LIENG_SEQUENCES:
        seq_strength = _LIENG_SEQUENCES[sorted_triple]
        return HandScore(
            category=HandCategory.LIENG,
            primary_rank=seq_strength,
            secondary_rank=0,
            score=0,
            tie_breaker=descending_ranks,
            name=f"Liêng {_LIENG_NAMES[seq_strength]}",
        )

    # 3. Check Đĩ (Three Face Cards - J, Q, K)
    # Ranks are sorted: all three cards are face cards iff 11 <= r1 <= r2 <= r3 <= 13.
    # Note: Ace is rank 14, so r3 <= 13 strictly excludes Ace.
    if r1 >= 11 and r3 <= 13:
        return HandScore(
            category=HandCategory.DI,
            primary_rank=r3,  # Highest face card
            secondary_rank=r2,
            score=0,
            tie_breaker=descending_ranks,
            name="Đĩ",
        )

    # 4. Fall through to Điểm (Points modulo 10)
    point_score = (Rank(r1).point_value + Rank(r2).point_value + Rank(r3).point_value) % 10
    name = f"{point_score} điểm" if point_score > 0 else "0 điểm (Bù)"
    return HandScore(
        category=HandCategory.DIEM,
        primary_rank=point_score,
        secondary_rank=r3,  # Highest card rank as tie-breaker
        score=point_score,
        tie_breaker=descending_ranks,
        name=name,
    )


# Every rank multiset (C(15, 3) = 455 of them), scored once. Keys are ascending rank values.
_SCORE_BY_RANKS: Final[dict[tuple[int, int, int], HandScore]] = {
    (r1, r2, r3): _score_for_sorted_ranks(r1, r2, r3)
    for r1, r2, r3 in itertools.combinations_with_replacement(range(Rank.TWO, Rank.ACE + 1), 3)
}


@dataclass(frozen=True)
class Hand:
    """Immutable representation of a 3-card Liêng hand."""
    cards: tuple[Card, Card, Card]

    def __post_init__(self) -> None:
        if len(self.cards) != 3:
            raise InvalidHandSizeError(f"A Liêng hand must have 3 cards, got {len(self.cards)}.")
        if len(set(self.cards)) != 3:
            raise DuplicateCardError("A Liêng hand cannot have duplicate cards.")

    @classmethod
    def from_cards(cls, c1: Card, c2: Card, c3: Card) -> Hand:
        """Construct a Hand from 3 Card instances."""
        return cls(cards=(c1, c2, c3))

    @classmethod
    def from_str(cls, hand_str: str) -> Hand:
        """Parse a hand string such as 'Ah Kd 2c' or 'As,Kh,Qd'.

        Args:
            hand_str: Separated card strings.

        Returns:
            A validated Hand instance.

        Raises:
            InvalidHandSizeError: If parsed card count != 3 or contains duplicates.
            InvalidCardError: If any card string is malformed.
        """
        tokens = [t for t in re.split(r"[\s,\-]+", hand_str.strip()) if t]
        if len(tokens) != 3:
            raise InvalidHandSizeError(
                f"Hand string '{hand_str}' must contain exactly 3 cards, found {len(tokens)}."
            )
        c1, c2, c3 = (Card.from_str(tok) for tok in tokens)
        return cls(cards=(c1, c2, c3))

    @cached_property
    def score(self) -> HandScore:
        """Evaluate the hand once and return its HandScore.

        ``cached_property`` writes straight into the instance ``__dict__``, so it works on this
        frozen dataclass (which has no ``__slots__``).
        """
        return evaluate_hand(self.cards)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Hand):
            return NotImplemented
        return self.score < other.score

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Hand):
            return NotImplemented
        return self.score <= other.score

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Hand):
            return NotImplemented
        return self.score > other.score

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Hand):
            return NotImplemented
        return self.score >= other.score

    def __eq__(self, other: object) -> bool:
        """Two hands are equal when they are equally strong (they would tie at showdown)."""
        if not isinstance(other, Hand):
            return NotImplemented
        return self.score == other.score

    def __hash__(self) -> int:
        # Must agree with __eq__: hands that tie hash equally, so they collapse in sets and dicts.
        return hash(self.score.score_tuple)

    def __str__(self) -> str:
        return " ".join(str(c) for c in self.cards)

    def __repr__(self) -> str:
        return f"Hand('{self}')"
