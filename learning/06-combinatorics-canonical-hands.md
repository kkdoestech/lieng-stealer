# 06 — Combinatorics and Canonical Hands

> **Goal:** count every possible Liêng hand, and shrink the 22,100 real hands into **455 hand types**
> ("canonical hands") without losing any information.
> **You will build:** `backend/src/hands.py` and `backend/tests/test_hands.py` (5 tests).
> **Time:** ~2 hours.
> **Prerequisites:** [05](05-hand-evaluator.md). Chapter 3, §10 (`itertools`).

---

## The big picture

In chapter 7 we will simulate how often each hand wins. Each simulation compares one hand against
18,424 opponent hands. Doing that for all 22,100 hands would take ~20 minutes. Doing it for 455 hands takes
~30 seconds. This chapter is where that 48× saving comes from.

The idea is called **hand isomorphism** (from Greek "same shape"): two hands that differ **only in their
suits** are strategically identical in Liêng, because suits never decide a showdown.

```
  A♠ K♥ Q♦   A♣ K♣ Q♣   A♥ K♠ Q♠   … (64 different real hands)
       \         |         /
        \        |        /
         ▼       ▼       ▼
          canonical hand  "Q-K-A"     multiplicity = 64
```

For each canonical hand we keep:

| Field | Example for Q-K-A | Meaning |
|-------|-------------------|---------|
| `canonical_id` | `"Q-K-A"` | a text name, used as the dictionary key in `winrates.json` |
| `ranks` | `(Q, K, A)` | the three ranks |
| `multiplicity` | `64` | how many real hands have this shape |
| `category` | `LIENG` | its category |
| `score` | `HandScore(...)` | its full score (from chapter 5) |

---

## Concepts you need: counting

You'll need just one formula. The number of ways to choose `k` items out of `n`, when **order does not
matter** and nothing repeats, is "n choose k":

```
C(n, k) = n! / (k! × (n − k)!)
```

### How many 3-card hands are there?

Choose 3 cards from 52. Think of dealing them one at a time: 52 choices for the first card, 51 for the
second, 50 for the third. That's 52 × 51 × 50 = 132,600 **ordered** deals. But A♠ K♥ Q♦ and K♥ Q♦ A♠ are
the same hand, and 3 cards can be ordered in 3 × 2 × 1 = 6 ways. So:

```
C(52, 3) = (52 × 51 × 50) / (3 × 2 × 1) = 132,600 / 6 = 22,100 hands
```

### How many hand types (ignoring suits)?

A hand type is just **three ranks**, where ranks may repeat (7-7-9) and order doesn't matter. Sort the
ranks high to low and split by "shape":

| Shape | How many rank choices | Example | Real hands per type | Total real hands |
|-------|----------------------|---------|---------------------|------------------|
| **Trips** (all 3 ranks equal) | 13 (pick the rank) | 7-7-7 | C(4,3) = **4** (pick 3 of the 4 suits) | 13 × 4 = **52** |
| **Pair** (2 equal + 1 other) | 13 × 12 = 156 (pair rank, then a different kicker rank) | 9-7-7 | C(4,2) × C(4,1) = 6 × 4 = **24** (2 suits for the pair, 1 for the kicker) | 156 × 24 = **3,744** |
| **Three different ranks** | C(13,3) = 286 | 9-8-2 | 4 × 4 × 4 = **64** (any suit for each card) | 286 × 64 = **18,304** |
| **Total** | **455** types | | | **22,100** ✔ |

Both totals check out: 13 + 156 + 286 = **455**, and 52 + 3,744 + 18,304 = **22,100**. The second total
matching C(52,3) is strong evidence the counting is right.

There's also a direct formula for "choose 3 from 13 **with repetition**" (the *stars and bars* trick):
`C(13 + 3 − 1, 3) = C(15, 3) = 455`.

The number of real hands per type is called the **multiplicity**. It matters later: when we report
"what percentage of all hands are profitable", a type with multiplicity 64 counts 16 times as much as a
type with multiplicity 4.

### How many types and hands per category?

| Category | Types | Why | Multiplicity | Real hands |
|----------|-------|-----|--------------|-----------|
| Sáp | 13 | one per rank | 4 each | **52** |
| Liêng | 12 | the 12 sequences (all distinct ranks) | 64 each | **768** |
| Đĩ | 6 | J-J-Q, J-J-K, J-Q-Q, J-K-K, Q-Q-K, Q-K-K (all pairs) | 24 each | **144** |
| Điểm | 455 − 13 − 12 − 6 = **424** | everything else | mixed | 22,100 − 52 − 768 − 144 = **21,136** |

Remember **144** and **21,136**. In chapter 15 you'll find that the original frontend uses different
(wrong) numbers.

---

## Step 6.1 — Module docstring and imports

📄 **File:** `backend/src/hands.py` — *create this file*

```python
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
from dataclasses import dataclass
from typing import Final, Sequence

from src.evaluator import (
    Card,
    Hand,
    HandCategory,
    HandScore,
    Rank,
    Suit,
    evaluate_hand,
)
from src.exceptions import InvalidCardError, InvalidHandSizeError
```

The module docstring is the counting table above, in short form. Writing the maths in the docstring
means the next reader doesn't have to re-derive it.

> 💡 `Final`, `Hand` and `InvalidCardError` are imported but never used in this file. A linter such as
> `ruff` or `flake8` would flag them. They're harmless, but unused imports make readers wonder "where is
> this used?"

---

## Step 6.2 — `CanonicalHand`

📄 **File:** `backend/src/hands.py` — *add to the end*

```python


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
```

**How it works**

- A frozen dataclass with five fields. It stores the precomputed `score` so we never re-evaluate it.
- Comparisons delegate to `score`, so `max(all_canonical_hands)` gives the strongest type (`A-A-A`).
- `__repr__` is customised to be short. The default would print the whole `HandScore`.

> ⚠️ **Pitfall: same `__eq__`/`__hash__` pattern as `Hand`.** `__eq__` compares scores, while the
> generated `__hash__` uses all fields. Here it happens to be safe: every canonical type has a
> **unique** score (the `tie_breaker` contains its three ranks), so "equal score" really does mean
> "same type". But that safety depends on a hidden fact about the scores. Also note that only `<`, `>`
> and `==` are defined: `a <= b` raises `TypeError`. A cleaner design: drop the custom `__eq__` and
> decorate the class with `functools.total_ordering`, or compare `a.score <= b.score` explicitly.

---

## Step 6.3 — `get_canonical_id`: from any 3 cards to a name

📄 **File:** `backend/src/hands.py` — *add to the end*

```python


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
```

**How it works**

- **Suits are thrown away** here: only `c.rank` is used. That is the isomorphism in one line.
- The default name is the three ranks from **highest to lowest**: `9♥ 7♦ 8♣` → `"9-8-7"`, `7♠ 7♥ 9♦` →
  `"9-7-7"`. Sorting makes the name independent of the order the cards were dealt.
- Two Liêng get a special, human-friendly name: `A-2-3` (sorted descending it would be "A-3-2") and
  `Q-K-A` ("A-K-Q").

> ⚠️ **Pitfall: inconsistent names.** Only those two sequences are written low-to-high. Every other
> Liêng is high-to-low: J-Q-K is stored as **`"K-Q-J"`**, 7-8-9 as `"9-8-7"`. A user (or programmer)
> who looks up `"J-Q-K"` gets a `KeyError`, even though `"Q-K-A"` works. The web page has a preset
> button labelled "Liêng J-Q-K" whose result shows `[K-Q-J]`. **Fix idea:** pick one rule for all IDs
> (e.g. always descending, so `"A-K-Q"` and `"3-2-A"`) or accept several spellings by normalising the
> input with `get_canonical_id(get_representative_cards(text))` before looking it up.

🧪 **Mini-check**

```bash
python -c "
from src.evaluator import Hand
from src.hands import get_canonical_id
for s in ['9h 7d 8c', 'Qs Kh Ad', 'As 2h 3d', 'Js Qh Kd', '7s 7h 9d']:
    print(s, '->', get_canonical_id(Hand.from_str(s).cards))
"
```

Expected output:

```
9h 7d 8c -> 9-8-7
Qs Kh Ad -> Q-K-A
As 2h 3d -> A-2-3
Js Qh Kd -> K-Q-J
7s 7h 9d -> 9-7-7
```

---

## Step 6.4 — `_compute_multiplicity`

📄 **File:** `backend/src/hands.py` — *add to the end*

```python


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
```

This is the "real hands per type" column of the counting table, turned into code. Python allows chained
comparisons: `r1 == r2 == r3` means `r1 == r2 and r2 == r3`. The underscore prefix marks it as a private
helper.

---

## Step 6.5 — `get_representative_cards`: from a name back to real cards

The generator (chapter 7) needs an actual 3-card hand for each type, so it can remove those cards from
the deck and deal opponent hands from the rest. This function builds one.

📄 **File:** `backend/src/hands.py` — *add to the end*

```python


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
```

**How it works**

- Split `"Q-K-A"` into `["Q", "K", "A"]` with the same regular expression as `Hand.from_str`, then parse
  each rank.
- Give the three cards **three different suits** (♠, ♥, ♦). That guarantees three distinct cards even
  for `"A-A-A"` → A♠ A♥ A♦. With the same suit twice we'd get an invalid hand with a duplicate card.

> 💡 **Does it matter which suits we pick?** Not for the result. Any representative of the type has the
> same equity, because suits never decide anything. That's the whole point of isomorphism.

---

## Step 6.6 — `to_canonical`: any real hand → its `CanonicalHand`

📄 **File:** `backend/src/hands.py` — *add to the end*

```python


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
```

**How it works**

1. Name it (`get_canonical_id`).
2. Score it (`evaluate_hand` from chapter 5).
3. Build the `ranks` tuple in the **same order as the name** (special order for A-2-3 and Q-K-A).
4. Count its multiplicity.
5. Pack everything into a `CanonicalHand`.

> 💡 **Repetition alert.** Step 3 repeats the "is it A-2-3 / Q-K-A?" logic from `get_canonical_id`. If
> someone changed the naming rule in one function but forgot the other, the `ranks` and the name would
> disagree. A shared helper (e.g. `_canonical_rank_order(cards) -> tuple[Rank, Rank, Rank]`) used by
> both functions would remove the duplication. The software principle is called **DRY**: Don't
> Repeat Yourself.

🧪 **Mini-check**

```bash
python -c "
from src.evaluator import Hand
from src.hands import to_canonical
for s in ['Qs Kh Ad', '7s 7h 9d', 'Kd Ks Qh', '2s 2h 2d']:
    print(repr(to_canonical(Hand.from_str(s).cards)))
"
```

Expected output:

```
CanonicalHand('Q-K-A', cat=LIENG, mult=64)
CanonicalHand('9-7-7', cat=DIEM, mult=24)
CanonicalHand('K-K-Q', cat=DI, mult=24)
CanonicalHand('2-2-2', cat=SAP, mult=4)
```

---

## Step 6.7 — `generate_all_canonical_hands`: list all 455 types

📄 **File:** `backend/src/hands.py` — *add to the end*

```python


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
```

**How it works**

- `itertools.combinations_with_replacement(all_ranks, 3)` yields every multiset of 3 ranks **exactly
  once**, in a fixed order: `(2,2,2), (2,2,3), (2,2,4), …, (A,A,A)`. No duplicates, nothing missing. That
  is far safer than three hand-written nested loops.
- For each multiset, make real cards with three different suits, then reuse `to_canonical`.
- The function is **deterministic**: same output, same order, every run. Chapter 7 relies on this.

🧪 **Mini-check**

```bash
python -c "
from collections import Counter
from src.hands import generate_all_canonical_hands
hs = generate_all_canonical_hands()
print(len(hs), [h.canonical_id for h in hs[:4]], max(hs).canonical_id, min(hs).canonical_id)
types, combos = Counter(), Counter()
for h in hs:
    types[h.category.name] += 1
    combos[h.category.name] += h.multiplicity
print(dict(types))
print(dict(combos), sum(combos.values()))
"
```

Expected output:

```
455 ['2-2-2', '3-2-2', '4-2-2', '5-2-2'] A-A-A 4-3-3
{'SAP': 13, 'DIEM': 424, 'LIENG': 12, 'DI': 6}
{'SAP': 52, 'DIEM': 21136, 'LIENG': 768, 'DI': 144} 22100
```

Every number matches the counting table. Interesting detail: the **weakest** hand type is `4-3-3`.
It has 0 points, and its highest card is only a 4. The one other 0-point hand topped by a 4 is `4-4-2`,
and the tie-breaker `(4, 3, 3) < (4, 4, 2)` puts `4-3-3` last.

---

## Step 6.8 — The tests

📄 **File:** `backend/tests/test_hands.py` — *create this file*

```python
"""Unit tests for Canonical Hand Isomorphism & State Space Compression in Liêng.

Verifies:
- Complete state space coverage: exactly 455 canonical classes
- Multiplicity summation: sum of class multiplicities equals 22,100
- Category distribution:
    - Sáp: 13 classes
    - Liêng: 12 classes
    - Đĩ: 6 classes
    - Điểm: 424 classes
- Suit invariance: permutations of suits map to identical canonical_id
- Representative cards validity: all 455 classes yield 3 distinct valid cards
"""

from collections import Counter
import pytest

from src.evaluator import Card, HandCategory, Rank, Suit
from src.hands import (
    CanonicalHand,
    generate_all_canonical_hands,
    get_canonical_id,
    get_representative_cards,
    to_canonical,
)


class TestCanonicalHandEngine:
    """Test suite for canonical hand isomorphism and combinatorics."""

    def test_canonical_space_size(self) -> None:
        """Verify that exactly 455 unique canonical classes are generated."""
        canonical_hands = generate_all_canonical_hands()
        assert len(canonical_hands) == 455

        # Ensure all canonical_ids are strictly unique
        unique_ids = {c.canonical_id for c in canonical_hands}
        assert len(unique_ids) == 455

    def test_multiplicity_sum(self) -> None:
        """Verify that total combinations across all 455 classes sum to C(52, 3) = 22,100."""
        canonical_hands = generate_all_canonical_hands()
        total_combos = sum(c.multiplicity for c in canonical_hands)
        assert total_combos == 22100

        # Verify multiplicity distribution (13 trips of 4, 156 pairs of 24, 286 distinct of 64)
        mult_counts = Counter(c.multiplicity for c in canonical_hands)
        assert mult_counts[4] == 13      # 13 * 4 = 52
        assert mult_counts[24] == 156    # 156 * 24 = 3744
        assert mult_counts[64] == 286    # 286 * 64 = 18304
```

`Counter` (from `collections`) counts how many times each value appears: `Counter([4, 64, 64])` →
`{64: 2, 4: 1}`.

📄 **File:** `backend/tests/test_hands.py` — *add to the end*

```python

    def test_category_distribution(self) -> None:
        """Verify class counts partition exactly into theoretical categories."""
        canonical_hands = generate_all_canonical_hands()
        category_counts = Counter(c.category for c in canonical_hands)

        # 1. Sáp: 13 classes (2-2-2 to A-A-A)
        assert category_counts[HandCategory.SAP] == 13

        # 2. Liêng: 12 classes (A-2-3 to Q-K-A)
        assert category_counts[HandCategory.LIENG] == 12

        # 3. Đĩ: 6 classes (multisets of J, Q, K with 1 pair)
        di_hands = [c for c in canonical_hands if c.category == HandCategory.DI]
        assert len(di_hands) == 6
        expected_di_rank_multisets = {
            (Rank.JACK, Rank.JACK, Rank.QUEEN),
            (Rank.JACK, Rank.JACK, Rank.KING),
            (Rank.JACK, Rank.QUEEN, Rank.QUEEN),
            (Rank.JACK, Rank.KING, Rank.KING),
            (Rank.QUEEN, Rank.QUEEN, Rank.KING),
            (Rank.QUEEN, Rank.KING, Rank.KING),
        }
        actual_di_rank_multisets = {tuple(sorted(c.ranks)) for c in di_hands}
        assert actual_di_rank_multisets == expected_di_rank_multisets

        # 4. Điểm: Exactly 424 classes (455 - 13 - 12 - 6)
        assert category_counts[HandCategory.DIEM] == 424
```

📄 **File:** `backend/tests/test_hands.py` — *add to the end*

```python

    def test_suit_invariance(self) -> None:
        """Verify that hands with identical ranks but different suits map to identical canonical_id."""
        hand1 = [Card.from_str("7s"), Card.from_str("8h"), Card.from_str("9d")]
        hand2 = [Card.from_str("7c"), Card.from_str("8d"), Card.from_str("9s")]
        hand3 = [Card.from_str("9h"), Card.from_str("7d"), Card.from_str("8c")]

        id1 = get_canonical_id(hand1)
        id2 = get_canonical_id(hand2)
        id3 = get_canonical_id(hand3)

        assert id1 == id2 == id3 == "9-8-7"

        # Check Q-K-A invariance
        qka1 = [Card.from_str("Qs"), Card.from_str("Kh"), Card.from_str("Ad")]
        qka2 = [Card.from_str("Qc"), Card.from_str("Kd"), Card.from_str("As")]
        assert get_canonical_id(qka1) == get_canonical_id(qka2) == "Q-K-A"

        # Check A-2-3 invariance
        a23_1 = [Card.from_str("As"), Card.from_str("2h"), Card.from_str("3d")]
        a23_2 = [Card.from_str("Ac"), Card.from_str("2d"), Card.from_str("3s")]
        assert get_canonical_id(a23_1) == get_canonical_id(a23_2) == "A-2-3"

    def test_representative_cards_validity(self) -> None:
        """Verify all 455 canonical classes produce valid 3-card hands with no duplicate cards."""
        canonical_hands = generate_all_canonical_hands()
        for ch in canonical_hands:
            cards = get_representative_cards(ch.canonical_id)
            assert len(cards) == 3
            # Ensure cards are all unique
            assert len(set(cards)) == 3
            # Ensure mapped back to the same canonical_id
            assert get_canonical_id(cards) == ch.canonical_id
```

`test_representative_cards_validity` is a **round-trip test**: name → cards → name must give back the
original name, for all 455 types. Round-trip tests are a cheap way to catch mismatches between two
functions that should be inverses of each other.

---

## ✅ Checkpoint

```bash
python -m pytest -q
```

Expected output (18 evaluator tests + 5 hands tests):

```
.......................                                                  [100%]
23 passed in 0.10s
```

Commit:

```bash
git add . && git commit -m "feat: canonical hand isomorphism (22,100 -> 455)"
```

## Recap

- There are **C(52,3) = 22,100** real hands but only **455** hand types once suits are ignored.
- Each type has a **multiplicity**: 4 (trips), 24 (pair) or 64 (three different ranks). The multiplicities add up to 22,100.
- Per category: Sáp 13 types / 52 hands, Liêng 12 / 768, Đĩ 6 / **144**, Điểm 424 / **21,136**.
- `get_canonical_id` names a hand by its ranks; `get_representative_cards` goes back the other way;
  `generate_all_canonical_hands` lists all 455 with `combinations_with_replacement`.
- Pitfalls: inconsistent Liêng names (`Q-K-A` vs `K-Q-J`); duplicated naming logic; fragile `__eq__`.

**Next:** [07 — The generator (simulation)](07-generator-simulation.md)
