# 04 — Exceptions and Cards

> **Goal:** model a playing card in Python: its suit, its rank, its point value, and how to read it
> from text like `"Ah"` or `"10s"`.
> **You will build:** `backend/src/exceptions.py` and the first half of `backend/src/evaluator.py`
> (`Suit`, `Rank`, `Card`, `Deck`).
> **Time:** ~1.5 hours.
> **Prerequisites:** [03](03-python-toolkit.md).

---

## The big picture

Everything in this project is built on one small object: **a card**. If the card is right, the rest is
easy. If the card is wrong, every chapter after this one breaks.

```
          "Ah"  (text typed by a user)
            │
            ▼   Card.from_str("Ah")
   ┌──────────────────────────────┐
   │ Card(rank=Rank.ACE,          │   immutable (frozen) and hashable
   │      suit=Suit.HEARTS)       │
   └──────────────────────────────┘
            │
            ├── .point_value   → 1      (for Điểm scoring)
            ├── .is_face_card  → False  (for Đĩ detection)
            └── str(card)      → "Ah"
```

We also decide **what happens when the input is wrong** (`"Xz"`, `"11h"`). The answer: we raise a
clear, project-specific error.

---

## Concepts you need

### Parsing

**Parsing** = turning text into structured data. `"10s"` is text; `Card(rank=Rank.TEN,
suit=Suit.SPADES)` is structured data. Our parser must handle:

| Input | Meaning | Tricky part |
|-------|---------|-------------|
| `"Ah"` | A♥ | normal case: 1 rank char + 1 suit char |
| `"10s"` | 10♠ | rank has **two** characters |
| `"Td"` | 10♦ | `T` is a common short form of ten |
| `"kd"` | K♦ | lowercase |
| `"9♠"` | 9♠ | suit given as a symbol |
| `"11h"`, `"Ax"`, `"X"` | — | invalid → raise `InvalidCardError` |

### "Fail loudly"

When input is invalid, there are two choices: quietly return something like `None`, or **raise an
exception**. Quiet failures spread: a `None` card would crash much later, far from the real mistake.
The project's rule (from `AGENTS.md`) is: **never silently swallow errors**. Raise immediately, with
a message that says what was wrong.

---

## Step 4.1 — The exception family

All of our errors inherit from one base class, `LiengError`:

```
Exception                      (built into Python)
└── LiengError                 "something went wrong in our engine"
    ├── InvalidCardError       bad card text, e.g. "11h"
    ├── InvalidHandSizeError   not exactly 3 different cards
    └── DatabaseError          problem with winrates.json   (chapter 8)
        └── DatabaseNotLoadedError   asked a question before loading the data
```

📄 **File:** `backend/src/exceptions.py` — *create this file*

```python
"""Custom exceptions for the Liêng Stealer system."""


class LiengError(Exception):
    """Base exception class for all Liêng engine errors."""
    pass


class InvalidCardError(LiengError):
    """Raised when card string or parameters are invalid."""
    pass


class InvalidHandSizeError(LiengError):
    """Raised when hand does not contain exactly 3 unique cards."""
    pass


class DatabaseError(LiengError):
    """Base error for precomputed database operations."""
    pass


class DatabaseNotLoadedError(DatabaseError):
    """Raised when querying a database that has not been loaded."""
    pass
```

**How it works**

- `class InvalidCardError(LiengError):` means "an `InvalidCardError` **is a** `LiengError`". So
  `except LiengError:` catches it.
- The class bodies are empty except for a docstring. The `pass` lines are not needed (a docstring
  is already a valid body), but they do no harm.
- Why so many classes with no code? The **type** is the information. In chapter 12 the web API does
  `except LiengError as err: return 400 Bad Request`: one line catches every "the user typed something
  wrong" error.

🧪 **Mini-check** (from `backend/`, venv active)

```bash
python -c "from src.exceptions import *; print(issubclass(DatabaseNotLoadedError, LiengError))"
```

Expected output:

```
True
```

---

## Step 4.2 — Start `evaluator.py`: docstring and imports

`evaluator.py` will hold the whole "domain model": cards, hands, and the ranking rules. We write its top
now and add to it for the rest of this chapter and the next.

📄 **File:** `backend/src/evaluator.py` — *create this file*

```python
"""Liêng Stealer - Core Domain Models and Hand Evaluation Engine.

Provides immutable representations of Cards, Decks, Hands, and HandScores,
with a strict total ordering adhering to Liêng rules:
Sáp (Category 4) > Liêng (Category 3) > Đĩ (Category 2) > Điểm (Category 1).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Final, Iterable, Sequence

from src.exceptions import InvalidCardError, InvalidHandSizeError
```

**How it works**

- `re` is Python's regular-expression module; we use it in chapter 5 to split `"As Kh Qd"` into pieces.
- `Final`, `Iterable`, `Sequence` are type-hint helpers. `Sequence` means "anything you can index and
  take `len()` of" (a list **or** a tuple). `Iterable` means "anything you can loop over".
- Some of these imports are only used in chapter 5. That's fine.

---

## Step 4.3 — `Suit`

📄 **File:** `backend/src/evaluator.py` — *add to the end*

```python


class Suit(Enum):
    """Card suits with standardized single-letter codes and symbols."""
    SPADES = "s"
    CLUBS = "c"
    DIAMONDS = "d"
    HEARTS = "h"

    @property
    def symbol(self) -> str:
        """Return Unicode symbol for the suit."""
        symbols = {
            Suit.SPADES: "♠",
            Suit.CLUBS: "♣",
            Suit.DIAMONDS: "♦",
            Suit.HEARTS: "♥",
        }
        return symbols[self]

    @classmethod
    def from_str(cls, suit_str: str) -> "Suit":
        """Parse suit from single-character representation or unicode symbol."""
        cleaned = suit_str.strip().lower()
        mapping = {
            "s": cls.SPADES, "♠": cls.SPADES,
            "c": cls.CLUBS, "♣": cls.CLUBS,
            "d": cls.DIAMONDS, "♦": cls.DIAMONDS,
            "h": cls.HEARTS, "♥": cls.HEARTS,
        }
        if cleaned in mapping:
            return mapping[cleaned]
        raise InvalidCardError(f"Invalid suit '{suit_str}'. Must be one of s, c, d, h or ♠, ♣, ♦, ♥.")
```

**How it works**

- `Suit` is a plain `Enum` (not `IntEnum`) because suits have **no order** in Liêng. Nobody should
  ever write `Suit.HEARTS > Suit.SPADES`, and a plain `Enum` makes that an error.
- Each member's **value** is its one-letter code: `Suit.HEARTS.value == "h"`.
- `symbol` is a `@property`: `Suit.HEARTS.symbol` → `"♥"`.
- `from_str` is a `@classmethod` "named constructor". It accepts both `"h"` and `"♥"`, cleans spaces
  (`strip()`) and case (`lower()`), and raises `InvalidCardError` for anything else.

🧪 **Mini-check**

```bash
python -c "from src.evaluator import Suit; print(Suit.from_str(' H '), Suit.from_str('♠').symbol)"
```

Expected output:

```
Suit.HEARTS ♠
```

---

## Step 4.4 — `Rank`, part 1: the members and their short names

📄 **File:** `backend/src/evaluator.py` — *add to the end*

```python


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
        if self <= Rank.NINE:
            return str(self.value)
        names = {
            Rank.TEN: "10",
            Rank.JACK: "J",
            Rank.QUEEN: "Q",
            Rank.KING: "K",
            Rank.ACE: "A",
        }
        return names[self]
```

**How it works**

- `Rank` is an `IntEnum`, so ranks compare like numbers: `Rank.ACE > Rank.KING` is `True`.
- The **values** are chosen carefully: 2 to 10 are their face numbers, then J=11, Q=12, K=13, **A=14**.
  The Ace is the highest rank for comparisons. (Its *point* value is 1; that's a different
  property, coming next.)
- `short_name` turns a rank into the text used in hand names: `Rank.SEVEN.short_name == "7"`,
  `Rank.ACE.short_name == "A"`.
- Inside the class, `self <= Rank.NINE` works because `self` is an `IntEnum` member.

---

## Step 4.5 — `Rank`, part 2: point value, face cards, parsing

These methods continue the `Rank` class, so they are **indented by 4 spaces**.

📄 **File:** `backend/src/evaluator.py` — *add to the end*

```python

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
    def from_str(cls, rank_str: str) -> "Rank":
        """Parse rank from string."""
        cleaned = rank_str.strip().upper()
        mapping = {
            "2": cls.TWO, "3": cls.THREE, "4": cls.FOUR, "5": cls.FIVE,
            "6": cls.SIX, "7": cls.SEVEN, "8": cls.EIGHT, "9": cls.NINE,
            "10": cls.TEN, "T": cls.TEN,
            "J": cls.JACK, "Q": cls.QUEEN, "K": cls.KING, "A": cls.ACE,
        }
        if cleaned in mapping:
            return mapping[cleaned]
        raise InvalidCardError(f"Invalid rank '{rank_str}'. Must be 2-10, T, J, Q, K, or A.")
```

**How it works**

- `point_value` encodes the Điểm table from chapter 1. **Check the order of the `if`s**: the Ace
  (value 14) must be handled *before* `self.value >= 10`, otherwise the Ace would score 0.
- `is_face_card` is true only for J, Q, K. The Ace is **not** a face card (important for Đĩ).
- `from_str` uses a dictionary as a lookup table: clean, uppercase, look up, or raise.

🧪 **Mini-check**

```bash
python -c "from src.evaluator import Rank; print([r.point_value for r in Rank]); print(Rank.from_str('t').short_name, Rank.ACE.is_face_card)"
```

Expected output:

```
[2, 3, 4, 5, 6, 7, 8, 9, 0, 0, 0, 0, 1]
10 False
```

---

## Step 4.6 — `Card`: the data

📄 **File:** `backend/src/evaluator.py` — *add to the end*

```python


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
```

**How it works**

- `@dataclass(frozen=True)` generates `__init__(self, rank, suit)`, a field-by-field `__eq__`, and
  a `__hash__`. So `Card(Rank.ACE, Suit.SPADES) == Card(Rank.ACE, Suit.SPADES)` is `True`, and cards can
  be put in a `set` (which we use to detect duplicate cards).
- The two properties **delegate** to the rank: a card's point value is its rank's point value. Writing
  `card.point_value` is nicer than `card.rank.point_value` everywhere.

---

## Step 4.7 — `Card`: reading and printing text

📄 **File:** `backend/src/evaluator.py` — *add to the end*

```python

    @classmethod
    def from_str(cls, card_str: str) -> "Card":
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

        rank = Rank.from_str(rank_part)
        suit = Suit.from_str(suit_part)
        return cls(rank=rank, suit=suit)

    def __str__(self) -> str:
        return f"{self.rank.short_name}{self.suit.value}"

    def __repr__(self) -> str:
        return f"Card('{self}')"
```

**How it works** (trace `from_str` by hand with `"10s"` and then `"Ah"`):

| Line | `"10s"` | `"Ah"` |
|------|---------|--------|
| `cleaned` | `"10s"` | `"Ah"` |
| starts with `"10"`? | yes | no |
| `rank_part` | `"10"` (`cleaned[:2]`) | `"A"` (`cleaned[0]`) |
| `suit_part` | `"s"` (`cleaned[2:]`) | `"h"` (`cleaned[1:]`) |
| result | `Card(TEN, SPADES)` | `Card(ACE, HEARTS)` |

- The two-character rank `"10"` is the only special case, so we test for it first.
- The method **reuses** `Rank.from_str` and `Suit.from_str`. Each class knows how to parse itself;
  `Card` just splits the text. Error checking comes for free: `"11h"` → `rank_part = "1"` →
  `Rank.from_str` raises `InvalidCardError`.
- `__str__` is used by `print()` and f-strings: `str(card)` → `"Ah"`. `__repr__` is used by the REPL
  and inside lists: `[Card('Ah'), Card('10s')]`. Notice `f"Card('{self}')"` calls `__str__` on itself.

> 💡 **Note.** `Suit.symbol` exists but `__str__` prints the letter (`"Ah"`), not the symbol (`"A♥"`).
> The project's `README.md` shows `"A♠ K♥ Q♦"` in an API example; the real API returns `"As Kh Qd"`.
> Small differences like this between docs and code are very common. Always trust a test over a doc.

🧪 **Mini-check**

```bash
python -c "from src.evaluator import Card; print(Card.from_str('10s'), repr(Card.from_str(' kd ')), Card.from_str('9♠').point_value)"
```

Expected output:

```
10s Card('Kd') 9
```

---

## Step 4.8 — `Deck`: all 52 cards

📄 **File:** `backend/src/evaluator.py` — *add to the end*

```python


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
```

**How it works**

- A generator expression with **two** `for` clauses works like nested loops: for every rank, for every
  suit, make a card. 13 × 4 = 52.
- It returns a **tuple** (immutable), so nobody can accidentally remove cards from "the" deck.
- `tuple[Card, ...]` is the type hint for "a tuple of any length containing Cards".
- It's a `@staticmethod` because it needs no instance: we call `Deck.standard_52()` directly.

🧪 **Mini-check**

```bash
python -c "from src.evaluator import Deck; d = Deck.standard_52(); print(len(d), len(set(d)), d[:5])"
```

Expected output:

```
52 52 (Card('2s'), Card('2c'), Card('2d'), Card('2h'), Card('3s'))
```

`len(set(d)) == 52` proves there are no duplicates (and that cards are hashable).

---

## ✅ Checkpoint

The project's official card tests live in `tests/test_evaluator.py`, which also tests hands, so we write
it in chapter 5. For now, create a **temporary** test file (no 📄 label: it's not part of the final
project) containing the same card tests:

```python
# backend/tests/test_cards_tmp.py  (temporary — delete it in chapter 5)
import pytest

from src.evaluator import Card, Deck, Rank, Suit
from src.exceptions import InvalidCardError


def test_card_from_str_standard() -> None:
    card = Card.from_str("Ah")
    assert card.rank == Rank.ACE
    assert card.suit == Suit.HEARTS
    assert card.point_value == 1
    assert Card.from_str("10s").rank == Rank.TEN
    assert Card.from_str("Td").suit == Suit.DIAMONDS


def test_card_from_str_case_and_symbols() -> None:
    assert Card.from_str("kd").is_face_card is True
    assert Card.from_str("9♠").suit == Suit.SPADES


def test_invalid_card_string_raises() -> None:
    for bad in ["X", "11h", "Ax"]:
        with pytest.raises(InvalidCardError):
            Card.from_str(bad)


def test_deck() -> None:
    assert len(set(Deck.standard_52())) == 52
```

`with pytest.raises(InvalidCardError):` means "the code inside this block **must** raise this error;
if it doesn't, the test fails."

Run:

```bash
python -m pytest -q
```

Expected output:

```
....                                                                     [100%]
4 passed in 0.02s
```

Commit:

```bash
git add . && git commit -m "feat: exceptions, Suit, Rank, Card, Deck"
```

## Recap

- All project errors inherit from **`LiengError`**, so callers can catch them in one place.
- **`Suit`** is an `Enum` (no order); **`Rank`** is an `IntEnum` (A=14 is highest), with
  `point_value` (A=1, 10/J/Q/K=0) and `is_face_card` (J, Q, K only).
- **`Card`** is a frozen dataclass: immutable, comparable, hashable. `Card.from_str` handles `"10s"`, `"Td"`, lowercase and symbols.
- **`Deck.standard_52()`** builds all 52 cards with a double generator expression.

**Next:** [05 — The hand evaluator](05-hand-evaluator.md)
