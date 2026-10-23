# 05 — The Hand Evaluator

> **Goal:** teach the computer the Liêng ranking rules, so it can say which of two hands wins.
> **You will build:** the second half of `backend/src/evaluator.py` (`HandCategory`, `HandScore`,
> `calculate_points`, `evaluate_hand`, `Hand`) and `backend/tests/test_evaluator.py` (18 tests).
> **Time:** ~2 hours.
> **Prerequisites:** [04](04-exceptions-and-cards.md). Re-read chapter 1, Part 2 (the rules) and
> chapter 3, §7 (tuple comparison).

---

## The big picture

This is the heart of the engine. The generator (chapter 7) will call `evaluate_hand` about **8.4
million times**, and every answer the program ever gives depends on it being right.

The design idea is simple and powerful:

> **Turn every hand into a tuple of numbers, such that a bigger tuple means a stronger hand.**

Then "who wins?" is a single `>` between two tuples.

```
   3 cards ──► evaluate_hand() ──► HandScore ──► score_tuple
                                                     │
 A♠ K♥ Q♦  ─────────────────────────────────────► (3, 12, 0, 0, (14, 13, 12))   "Liêng Q-K-A"
 7♠ 7♥ 7♦  ─────────────────────────────────────► (4,  7, 0, 0, ( 7,  7,  7))   "Sáp 7"
 J♠ Q♥ Q♦  ─────────────────────────────────────► (2, 12, 12, 0, (12, 12, 11))  "Đĩ"
 9♠ 10♥ K♦ ─────────────────────────────────────► (1,  9, 13, 9, (13, 10,  9))  "9 điểm"
                                                     ▲
                                  category first → Sáp (4) beats everything
```

The tuple's fields are:

| Position | Field | Meaning |
|----------|-------|---------|
| 0 | `category` | 4 = Sáp, 3 = Liêng, 2 = Đĩ, 1 = Điểm |
| 1 | `primary_rank` | the main strength **inside** the category |
| 2 | `secondary_rank` | a first tie-breaker |
| 3 | `score` | the Điểm points (0–9), 0 for other categories |
| 4 | `tie_breaker` | all three ranks, highest first, as a last resort |

What "primary" and "secondary" mean depends on the category:

| Category | `primary_rank` | `secondary_rank` |
|----------|----------------|------------------|
| Sáp | the rank (2…14) | 0 |
| Liêng | sequence strength: A-2-3 = 1 … Q-K-A = 12 | 0 |
| Đĩ | highest card (11…13) | middle card |
| Điểm | points (0…9) | highest card (Ace = 14) |

---

## Concepts you need

### A "lookup table" instead of clever logic

How do you check if three ranks are consecutive? You could write maths with special cases for the Ace
(A-2-3 and Q-K-A are valid, K-A-2 is not). Or you could **list all 12 valid sequences** in a dictionary
and check `if ranks in table`. The list is short, obviously correct, and impossible to get "almost
right". When the set of valid cases is small, **a table beats an algorithm**.

### Sorting three numbers with three swaps

To compare ranks we first sort the three ranks from low to high. `sorted()` would work, but for exactly
three items this is faster, and it's a classic trick (a tiny "sorting network"):

```python
if r1 > r2: r1, r2 = r2, r1   # now r1 <= r2
if r2 > r3: r2, r3 = r3, r2   # now r3 is the largest
if r1 > r2: r1, r2 = r2, r1   # fix the first two again
# result: r1 <= r2 <= r3
```

Try it with `(14, 2, 3)`: after step 1 → `(2, 14, 3)`; step 2 → `(2, 3, 14)`; step 3 → no change.

---

## Step 5.1 — `HandCategory`

📄 **File:** `backend/src/evaluator.py` — *add to the end*

```python


class HandCategory(IntEnum):
    """Strict hierarchical categories in Liêng."""
    DIEM = 1
    DI = 2
    LIENG = 3
    SAP = 4

    @property
    def display_name(self) -> str:
        """Human-readable category name."""
        names = {
            HandCategory.DIEM: "Điểm",
            HandCategory.DI: "Đĩ",
            HandCategory.LIENG: "Liêng",
            HandCategory.SAP: "Sáp",
        }
        return names[self]
```

**How it works**

- An `IntEnum` again, because categories **are** ordered: `HandCategory.SAP > HandCategory.LIENG`.
- Member names use plain ASCII (`DIEM`, not `ĐIỂM`) so they are easy to type and safe to store in
  JSON (`"category": "DIEM"`). `display_name` gives the proper Vietnamese spelling for humans.

---

## Step 5.2 — The table of valid Liêng sequences

📄 **File:** `backend/src/evaluator.py` — *add to the end*

```python


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
```

**How it works**

- Keys are **sorted** rank triples (low → high, Ace = 14). So A-2-3 is stored as `(2, 3, 14)`:
  sorted, the Ace comes last. Values are the strength 1–12.
- K-A-2 would be `(2, 13, 14)`. It is **not** in the table, so it can never be a Liêng. The rule is
  enforced by *absence*, which is easy to check by eye.
- The leading underscore in `_LIENG_SEQUENCES` is a Python convention for "private to this module:
  other files shouldn't use it".
- `Final[...]` says "this name will never be reassigned".

---

## Step 5.3 — `HandScore`: the fields and the comparison tuple

📄 **File:** `backend/src/evaluator.py` — *add to the end*

```python


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
```

**How it works**

- `order=False` tells the dataclass **not** to generate `<`, `>` etc. automatically. (Generated ones would
  compare *all* fields in order, including `name`, a string. Comparing `"Sáp 7"` with `"Đĩ"`
  alphabetically would be nonsense.) We write them ourselves in the next step.
- `score_tuple` leaves `name` out. Only numbers decide the winner.
- A tuple can contain another tuple (`tie_breaker`), and comparison still works element by element.

---

## Step 5.4 — `HandScore`: comparison operators

📄 **File:** `backend/src/evaluator.py` — *add to the end*

```python

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

    def __str__(self) -> str:
        return self.name
```

**How it works**

- All five operators do the same thing: check the other object is a `HandScore`, then compare the two
  `score_tuple`s. Python's tuple comparison does the real work.
- `__eq__` means "**tie** at showdown", not "same object".
- `__str__` returns the friendly name, so `print(score)` shows `Liêng Q-K-A`.

> 💡 **Shortcut you could use instead:** `functools.total_ordering` generates `<=`, `>`, `>=` from just
> `__eq__` and `__lt__`. The project writes all five explicitly, which is longer but very easy to read.

---

## Step 5.5 — `calculate_points`

📄 **File:** `backend/src/evaluator.py` — *add to the end*

```python


def calculate_points(cards: Iterable[Card]) -> int:
    """Compute raw sum of card values modulo 10."""
    return sum(card.point_value for card in cards) % 10
```

A one-liner: sum the point values with a generator expression, keep the last digit with `% 10`. It is
a small public helper (the tests use it). `evaluate_hand` computes the same thing inline for speed.

---

## Step 5.6 — `evaluate_hand`, part 1: validate and sort

Now the main function. We build it in three slices. This first slice checks the input and sorts the
ranks.

📄 **File:** `backend/src/evaluator.py` — *add to the end*

```python


def evaluate_hand(cards: Sequence[Card]) -> HandScore:
    """Evaluate a 3-card Liêng hand with strict total ordering.

    Hierarchical evaluation rules:
      1. Sáp (Cat 4): 3 cards of identical rank. A-A-A is strongest, 2-2-2 weakest.
      2. Liêng (Cat 3): 3 consecutive cards. Q-K-A is strongest, A-2-3 weakest.
         No wraparound across K-A-2.
      3. Đĩ (Cat 2): 3 face cards (J, Q, K) excluding Sáp and Liêng.
         Strictly beats any Điểm hand, including 9 points.
      4. Điểm (Cat 1): Score = sum(CardValue) mod 10 (0 to 9).

    Args:
        cards: A sequence of exactly 3 unique Card instances.

    Returns:
        A fully-populated HandScore instance.

    Raises:
        InvalidHandSizeError: If card count != 3 or cards contain duplicates.
    """
    if len(cards) != 3:
        raise InvalidHandSizeError(f"A Liêng hand must contain exactly 3 cards, got {len(cards)}.")

    c1, c2, c3 = cards[0], cards[1], cards[2]
    if c1 == c2 or c2 == c3 or c1 == c3:
        raise InvalidHandSizeError("A Liêng hand cannot contain duplicate cards.")

    r1, r2, r3 = c1.rank.value, c2.rank.value, c3.rank.value
    if r1 > r2:
        r1, r2 = r2, r1
    if r2 > r3:
        r2, r3 = r3, r2
    if r1 > r2:
        r1, r2 = r2, r1

    descending_ranks = (r3, r2, r1)
```

**How it works**

- **Validate first.** Exactly 3 cards, all different. (Two `Card`s are equal when rank **and** suit
  match. That's the dataclass `__eq__` from chapter 4.)
- `.rank.value` turns `Rank.ACE` into the plain integer `14`. Plain integers are a bit faster to
  compare and are what we store in the tuple.
- After the three swaps, `r1 <= r2 <= r3`. `descending_ranks` is the same numbers highest-first; it
  becomes the final `tie_breaker` for every category.
- The function is **pure**: it only reads its input and returns a new object. No printing, no files,
  no global variables. `AGENTS.md` requires this, and it makes the function easy to test and safe to run
  in parallel (chapter 7).

---

## Step 5.7 — `evaluate_hand`, part 2: Sáp and Liêng

📄 **File:** `backend/src/evaluator.py` — *add to the end*

```python

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
```

**How it works**

- **Sáp test:** the ranks are sorted, so if the smallest equals the largest, all three are equal.
  One comparison instead of two.
- `Rank(r1)` converts the integer back into a `Rank` so we can use `.short_name` for the label
  (`"Sáp 7"`).
- **Liêng test:** a dictionary lookup in the table from Step 5.2. `primary_rank` is the sequence
  strength (1–12), **not** the highest card. That is how A-2-3 (whose highest card is the Ace, 14) still
  ranks lowest.
- Each check **returns immediately**. That's what makes the order of the checks matter: a hand that
  is a Sáp never reaches the Liêng test.

---

## Step 5.8 — `evaluate_hand`, part 3: Đĩ and Điểm

📄 **File:** `backend/src/evaluator.py` — *add to the end*

```python

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
    point_score = (c1.point_value + c2.point_value + c3.point_value) % 10
    name = f"{point_score} điểm" if point_score > 0 else "0 điểm (Bù)"
    return HandScore(
        category=HandCategory.DIEM,
        primary_rank=point_score,
        secondary_rank=r3,  # Highest card rank as tie-breaker
        score=point_score,
        tie_breaker=descending_ranks,
        name=name,
    )
```

**How it works**

- **Đĩ test:** because the ranks are sorted, "all three are J/Q/K" becomes "the smallest is at least
  J (11) **and** the largest is at most K (13)". J-J-J and J-Q-K would also pass this test, but they
  already returned as Sáp and Liêng above. **The order of checks does the exclusion for us.**
- **Điểm:** everything left. `primary_rank` is the points, so 9 points beats 8 points. When points are
  equal, `secondary_rank = r3` (the highest card, Ace = 14) breaks the tie, then the full `tie_breaker`.
- `name` uses a conditional expression: `A if condition else B`.

🧪 **Mini-check**

```bash
python -c "
from src.evaluator import Card, evaluate_hand
for text in ['As Kh Qd', '7s 7h 7d', 'Js Qh Qd', '9s 10h Kd', 'Ks Ah 2d', '2s 3h 5d']:
    s = evaluate_hand([Card.from_str(t) for t in text.split()])
    print(f'{text:10} {s.category.name:5} {str(s):12} {s.score_tuple}')
"
```

Expected output:

```
As Kh Qd   LIENG Liêng Q-K-A  (3, 12, 0, 0, (14, 13, 12))
7s 7h 7d   SAP   Sáp 7        (4, 7, 0, 0, (7, 7, 7))
Js Qh Qd   DI    Đĩ           (2, 12, 12, 0, (12, 12, 11))
9s 10h Kd  DIEM  9 điểm       (1, 9, 13, 9, (13, 10, 9))
Ks Ah 2d   DIEM  3 điểm       (1, 3, 14, 3, (14, 13, 2))
2s 3h 5d   DIEM  0 điểm (Bù)  (1, 0, 5, 0, (5, 3, 2))
```

Check each line against the rules in chapter 1. Note how `K-A-2` is a 3-point Điểm, not a Liêng.

---

## Step 5.9 — `Hand`: a validated group of three cards

`evaluate_hand` works on any list of cards. It's convenient to also have a `Hand` object that
**guarantees** it holds three different cards and can be parsed from text like `"As Kh Qd"`.

📄 **File:** `backend/src/evaluator.py` — *add to the end*

```python


@dataclass(frozen=True)
class Hand:
    """Immutable representation of a 3-card Liêng hand."""
    cards: tuple[Card, Card, Card]

    def __post_init__(self) -> None:
        if len(self.cards) != 3:
            raise InvalidHandSizeError(f"A Liêng hand must have 3 cards, got {len(self.cards)}.")
        if len(set(self.cards)) != 3:
            raise InvalidHandSizeError("A Liêng hand cannot have duplicate cards.")

    @classmethod
    def from_cards(cls, c1: Card, c2: Card, c3: Card) -> "Hand":
        """Construct a Hand from 3 Card instances."""
        return cls(cards=(c1, c2, c3))

    @classmethod
    def from_str(cls, hand_str: str) -> "Hand":
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
        parsed_cards = tuple(Card.from_str(tok) for tok in tokens)
        return cls(cards=parsed_cards)  # type: ignore[arg-type]
```

**How it works**

- **`__post_init__`** is a special dataclass hook: it runs right after the generated `__init__`. It's
  the place to **validate**. Here: exactly 3 cards, and `len(set(cards)) == 3` means no duplicates (a
  set drops repeated items).
- **`re.split(r"[\s,\-]+", text)`** splits on any run of whitespace (`\s`), commas or hyphens. So
  `"As Kh Qd"`, `"As,Kh,Qd"` and `"As-Kh-Qd"` all work. The `r"..."` is a *raw string*: backslashes
  are kept as-is, which regular expressions need.
- `[t for t in ... if t]` removes empty strings (e.g. from a trailing comma).
- `# type: ignore[arg-type]` silences `mypy`: it can't prove that a tuple built from a list has
  exactly 3 items (we checked it ourselves above).

---

## Step 5.10 — `Hand`: score and comparisons

📄 **File:** `backend/src/evaluator.py` — *add to the end*

```python

    @property
    def score(self) -> HandScore:
        """Evaluate and return the HandScore."""
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
        if not isinstance(other, Hand):
            return NotImplemented
        return self.score == other.score

    def __str__(self) -> str:
        return " ".join(str(c) for c in self.cards)

    def __repr__(self) -> str:
        return f"Hand('{self}')"
```

**How it works**

- `score` is a property that **calls `evaluate_hand` every time** it is read. That keeps `Hand` simple
  (no stored score), at the cost of recomputing it.
- Comparisons delegate to `HandScore`. So `Hand.from_str("2s 2h 2d") > Hand.from_str("Qs Kh Ad")` reads
  exactly like the rule "Sáp beats Liêng".
- `__str__` joins the cards with spaces: `"As Kh Qd"`.

> ⚠️ **Pitfall: `__eq__` and `__hash__` disagree.**
> `Hand.__eq__` compares **scores**, but the dataclass still generates a `__hash__` from the **cards**
> (because the class is `frozen=True`). Python requires that `a == b` implies `hash(a) == hash(b)`.
> Here that rule is broken:
>
> ```python
> >>> h1 = Hand.from_str("As Kh Qd"); h2 = Hand.from_str("Ac Kc Qh")
> >>> h1 == h2              # same strength → "equal"
> True
> >>> hash(h1) == hash(h2)  # different cards → different hash
> False
> >>> len({h1, h2})         # a set of two "equal" items still has 2 elements!
> 2
> ```
>
> **Why it matters:** sets and dicts give confusing results, and "equal" is misleading: `h1 == h2`
> reads as "same hand" but means "same strength".
> **Better design (optional upgrade):** keep the generated field-based `__eq__` (same cards ⇔ equal)
> by deleting `Hand.__eq__`, and compare strength explicitly with `h1.score == h2.score`. Keep `<`/`>`
> for strength if you like. The original tests still pass with this change, because they only use
> `<`, `>` and `.score`. `CanonicalHand` in chapter 6 has the same issue.

> ⚠️ **Pitfall: the speed budget is not met.**
> `AGENTS.md` §6 asks for "< 1.0 µs per hand evaluation". On a typical laptop this pure-Python
> `evaluate_hand` takes about **3–10 µs** (try it: `python -m timeit -s "from src.evaluator import Hand,
> evaluate_hand; c = Hand.from_str('9s 8h 2d').cards" "evaluate_hand(c)"`). Most of the time goes into
> creating the `HandScore` object. It doesn't matter in practice, because the slow part runs offline
> once (chapter 7). But a spec number nobody measures is a spec nobody meets. If you needed the speed:
> precompute a dict from the sorted rank triple (only 455 possibilities, since suits don't matter) to a
> ready-made `HandScore`, and `evaluate_hand` becomes one lookup.

> 💡 **A house-rule choice.** For two Điểm hands with equal points, this code says the higher top card
> wins, with the **Ace as the highest** (14), even though the Ace is worth only 1 point. So `A-3-5`
> (9 points) beats `K-10-9` (9 points). Some tables play differently. Because the rule lives in one
> place (`secondary_rank=r3`), changing it later is a one-line edit.

---

## Step 5.11 — The official tests

Delete the temporary card tests from chapter 4. The same tests are in the official file below.

```bash
rm tests/test_cards_tmp.py
```

The test file is long, but each test is short and checks **one rule from chapter 1**. Read the test
names: together they are a precise, executable copy of the rules.

📄 **File:** `backend/tests/test_evaluator.py` — *create this file*

```python
"""Unit tests for Card, Hand, and strict Hand Evaluator in Liêng.

Verifies:
- Sáp hierarchy (AAA > KKK > ... > 222)
- Sáp > Liêng > Đĩ > Điểm
- Liêng edge sequences (QKA > ... > 234 > A23)
- Strict rejection of wrap-around sequence K-A-2 as Liêng
- Priority of Đĩ over any 9-point hand (JQQ > 9-10-K)
- Isolation of JJJ as Sáp and JQK as Liêng (neither evaluated as Đĩ)
- Modulo 10 arithmetic (10+J+Q = 0 pts, 9+10+K = 9 pts, A+3+5 = 9 pts)
- Strict error handling (invalid cards, duplicate cards, hand size != 3)
"""

import pytest

from src.evaluator import (
    Card,
    Hand,
    HandCategory,
    Rank,
    Suit,
    calculate_points,
    evaluate_hand,
)
from src.exceptions import InvalidCardError, InvalidHandSizeError


class TestCardAndRank:
    """Test Card domain model, Rank values, and string parser."""

    def test_card_from_str_standard(self) -> None:
        card = Card.from_str("Ah")
        assert card.rank == Rank.ACE
        assert card.suit == Suit.HEARTS
        assert card.point_value == 1

        card_10 = Card.from_str("10s")
        assert card_10.rank == Rank.TEN
        assert card_10.suit == Suit.SPADES
        assert card_10.point_value == 0

        card_t = Card.from_str("Td")
        assert card_t.rank == Rank.TEN
        assert card_t.suit == Suit.DIAMONDS
        assert card_t.point_value == 0

    def test_card_from_str_case_and_symbols(self) -> None:
        c1 = Card.from_str("kd")
        assert c1.rank == Rank.KING
        assert c1.suit == Suit.DIAMONDS
        assert c1.is_face_card is True

        c2 = Card.from_str("9♠")
        assert c2.rank == Rank.NINE
        assert c2.suit == Suit.SPADES
        assert c2.point_value == 9

    def test_invalid_card_string_raises(self) -> None:
        with pytest.raises(InvalidCardError):
            Card.from_str("X")
        with pytest.raises(InvalidCardError):
            Card.from_str("11h")
        with pytest.raises(InvalidCardError):
            Card.from_str("Ax")


class TestHandCreation:
    """Test Hand creation, validation, and error boundaries."""

    def test_valid_hand_from_str(self) -> None:
        hand = Hand.from_str("As Kh Qd")
        assert len(hand.cards) == 3
        assert hand.cards[0] == Card(Rank.ACE, Suit.SPADES)

    def test_duplicate_cards_raises(self) -> None:
        with pytest.raises(InvalidHandSizeError):
            Hand.from_str("As As Qd")

    def test_invalid_hand_size_raises(self) -> None:
        with pytest.raises(InvalidHandSizeError):
            Hand.from_str("As Kh")
        with pytest.raises(InvalidHandSizeError):
            Hand.from_str("As Kh Qd Jc")
```

Grouping tests into classes (`class TestHandCreation:`) is just organisation. pytest runs every
`test_` method inside any class whose name starts with `Test`.

Next, the Sáp and Liêng rules:

📄 **File:** `backend/tests/test_evaluator.py` — *add to the end*

```python


class TestSapHierarchy:
    """Test Sáp (Three of a Kind, Category 4) evaluation and ranking."""

    def test_sap_isolation_and_order(self) -> None:
        sap_a = Hand.from_str("As Ah Ad")
        sap_k = Hand.from_str("Ks Kh Kd")
        sap_2 = Hand.from_str("2s 2h 2d")

        assert sap_a.score.category == HandCategory.SAP
        assert sap_k.score.category == HandCategory.SAP
        assert sap_2.score.category == HandCategory.SAP

        # Total order: AAA > KKK > ... > 222
        assert sap_a > sap_k
        assert sap_k > sap_2
        assert sap_a > sap_2

    def test_sap_beats_highest_lieng(self) -> None:
        sap_2 = Hand.from_str("2s 2h 2d")
        highest_lieng = Hand.from_str("Qs Kh Ad")  # Q-K-A
        assert sap_2 > highest_lieng


class TestLiengHierarchy:
    """Test Liêng (Straight, Category 3) evaluation and sequences."""

    def test_all_twelve_valid_lieng_sequences(self) -> None:
        sequences = [
            "As 2h 3d",  # 1: A-2-3 (Lowest)
            "2s 3h 4d",  # 2: 2-3-4
            "3s 4h 5d",  # 3: 3-4-5
            "4s 5h 6d",  # 4: 4-5-6
            "5s 6h 7d",  # 5: 5-6-7
            "6s 7h 8d",  # 6: 6-7-8
            "7s 8h 9d",  # 7: 7-8-9
            "8s 9h 10d", # 8: 8-9-10
            "9s 10h Jd", # 9: 9-10-J
            "10s Jh Qd", # 10: 10-J-Q
            "Js Qh Kd",  # 11: J-Q-K
            "Qs Kh Ad",  # 12: Q-K-A (Highest)
        ]
        hands = [Hand.from_str(seq) for seq in sequences]

        # Verify each is recognized as Category LIENG
        for h in hands:
            assert h.score.category == HandCategory.LIENG

        # Verify strict monotonicity: sequence i < sequence i + 1
        for i in range(len(hands) - 1):
            assert hands[i] < hands[i + 1]

        # Verify edge checks: Q-K-A is highest, A-2-3 is lowest
        assert hands[-1] > hands[0]
        assert hands[1] > hands[0]  # 2-3-4 > A-2-3

    def test_ka2_wraparound_rejection(self) -> None:
        """K-A-2 is strictly prohibited as a Liêng and falls back to Điểm."""
        ka2_hand = Hand.from_str("Ks Ah 2d")
        score = ka2_hand.score
        assert score.category == HandCategory.DIEM
        assert score.category != HandCategory.LIENG
        # K(0) + A(1) + 2(2) = 3 points
        assert score.score == 3
        assert score.primary_rank == 3
```

Then the Đĩ rules, the trickiest category:

📄 **File:** `backend/tests/test_evaluator.py` — *add to the end*

```python


class TestDiHierarchy:
    """Test Đĩ (Three Face Cards, Category 2) evaluation and priority."""

    def test_di_valid_combinations(self) -> None:
        di_hands = [
            Hand.from_str("Js Qh Qd"),  # J-Q-Q
            Hand.from_str("Js Kh Kd"),  # J-K-K
            Hand.from_str("Js Jh Qd"),  # J-J-Q
            Hand.from_str("Js Jh Kd"),  # J-J-K
            Hand.from_str("Qs Qh Kd"),  # Q-Q-K
            Hand.from_str("Qs Kh Kd"),  # Q-K-K
        ]
        for h in di_hands:
            assert h.score.category == HandCategory.DI

    def test_di_isolation_from_sap_and_lieng(self) -> None:
        """JJJ must be SAP (Cat 4), and JQK must be LIENG (Cat 3), NOT Đĩ (Cat 2)."""
        jjj = Hand.from_str("Js Jh Jd")
        assert jjj.score.category == HandCategory.SAP
        assert jjj.score.category != HandCategory.DI

        jqk = Hand.from_str("Js Qh Kd")
        assert jqk.score.category == HandCategory.LIENG
        assert jqk.score.category != HandCategory.DI

    def test_ace_plus_face_cards_not_di(self) -> None:
        """Ace is not a face card in Liêng, so A-J-J and A-Q-J are Điểm (1 pt), NOT Đĩ."""
        ajj = Hand.from_str("As Jh Jd")
        assert ajj.score.category == HandCategory.DIEM
        assert ajj.score.score == 1

        aqj = Hand.from_str("As Qh Jd")
        assert aqj.score.category == HandCategory.DIEM
        assert aqj.score.score == 1

    def test_di_strictly_beats_nine_points(self) -> None:
        """Crucial rule: Any Đĩ strictly beats any point hand, including 9 points."""
        di_hand = Hand.from_str("Js Qh Qd")
        nine_pts_1 = Hand.from_str("9s 10h Kd")  # 9 + 0 + 0 = 9 pts
        nine_pts_2 = Hand.from_str("As 3h 5d")   # 1 + 3 + 5 = 9 pts

        assert nine_pts_1.score.category == HandCategory.DIEM
        assert nine_pts_1.score.score == 9

        assert nine_pts_2.score.category == HandCategory.DIEM
        assert nine_pts_2.score.score == 9

        assert di_hand > nine_pts_1
        assert di_hand > nine_pts_2

    def test_lieng_beats_di(self) -> None:
        """Lowest Liêng (A-2-3) strictly beats any Đĩ."""
        lowest_lieng = Hand.from_str("As 2h 3d")
        strongest_di = Hand.from_str("Qs Kh Kd")  # Q-K-K
        assert lowest_lieng > strongest_di
```

Finally the Điểm (points) rules:

📄 **File:** `backend/tests/test_evaluator.py` — *add to the end*

```python


class TestDiemModulo10:
    """Test Category 1 Điểm modulo 10 scoring and comparisons."""

    def test_point_sum_values(self) -> None:
        # Card value calculation: 10 + J + Q = 0 + 0 + 0 = 0 pts
        c10 = Card.from_str("10s")
        cj = Card.from_str("Jc")
        cq = Card.from_str("Qd")
        assert calculate_points([c10, cj, cq]) == 0

    def test_modulo_10_calculations(self) -> None:
        # 9 + 10 + K = 19 -> 9 pts
        hand_19 = Hand.from_str("9s 10h Kd")
        assert hand_19.score.category == HandCategory.DIEM
        assert hand_19.score.score == 9

        # A + 3 + 5 = 9 pts
        hand_9 = Hand.from_str("As 3h 5d")
        assert hand_9.score.category == HandCategory.DIEM
        assert hand_9.score.score == 9

        # 0 pts (Bù): 10 + J + K = 0 + 0 + 0 = 0 pts (non-straight, non-face only)
        hand_bu = Hand.from_str("10s Jh Kd")
        assert hand_bu.score.category == HandCategory.DIEM
        assert hand_bu.score.score == 0

        # 20 pts: 10 + 10 + K -> 0 pts (Bù)
        hand_20 = Hand.from_str("10s 10h Kd")
        assert hand_20.score.category == HandCategory.DIEM
        assert hand_20.score.score == 0

    def test_points_ordering(self) -> None:
        hand_9 = Hand.from_str("As 3h 5d")  # 9 pts
        hand_8 = Hand.from_str("2s 2h 4d")  # 8 pts
        hand_0 = Hand.from_str("10s Jh Kd") # 0 pts

        assert hand_9 > hand_8
        assert hand_8 > hand_0
        assert hand_9 > hand_0
```

> 💡 **Why can 10, J, Q, K be worth 0?** The test comment says "9 + 10 + K = 19": that's counting the
> 10 as ten points. Our code counts it as 0, so the raw sum is 9. **The score is 9 either way**,
> because adding 10 never changes the last digit (10 % 10 = 0). That's why the code can treat 10/J/Q/K
> as 0. Whether you count them as 10 or as 0, the result modulo 10 is identical.

---

## ✅ Checkpoint

```bash
python -m pytest tests/test_evaluator.py -v
```

Expected (abbreviated; you should see **18 passed**):

```
tests/test_evaluator.py::TestCardAndRank::test_card_from_str_standard PASSED
tests/test_evaluator.py::TestCardAndRank::test_card_from_str_case_and_symbols PASSED
...
tests/test_evaluator.py::TestDiemModulo10::test_points_ordering PASSED
============================== 18 passed in 0.03s ==============================
```

Also compare your file with the original (replace `/path/to/lieng-stealer` with wherever the original
repository is on your computer). `-B` ignores differences in blank lines:

```bash
diff -B src/evaluator.py /path/to/lieng-stealer/backend/src/evaluator.py
```

No output means your code is identical to the original. You can do this for every file in later
chapters too.

Commit:

```bash
git add . && git commit -m "feat: hand evaluator with strict total ordering"
```

## Recap

- Every hand becomes a **`HandScore`** whose `score_tuple` = `(category, primary, secondary, points, tie_breaker)`.
  Bigger tuple = stronger hand.
- **`evaluate_hand`** validates, sorts the ranks with three swaps, then checks **Sáp → Liêng → Đĩ → Điểm**
  and returns at the first match. The order of checks handles the "J-J-J is not Đĩ" exclusions.
- Liêng uses a **lookup table** of the 12 valid sorted triples, so K-A-2 is impossible by construction.
- **`Hand`** validates 3 distinct cards in `__post_init__` and parses `"As Kh Qd"` with a regular expression.
- Pitfalls: `Hand.__eq__` breaks the hash/eq contract; the 1 µs speed budget isn't met (but doesn't need to be).

**Next:** [06 — Combinatorics and canonical hands](06-combinatorics-canonical-hands.md)