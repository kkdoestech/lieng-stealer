# 09 — The Calling-Range Model

> **Goal:** compute a hand's equity against the hands an opponent **actually calls with** (their strongest
> hands), not against a random hand, exactly, including card removal, and fast enough to answer in under a
> millisecond.
> **You will build:** `backend/src/calling_range.py` and `backend/tests/test_calling_range.py` (9 tests).
> **Time:** ~3 hours. This is the most algorithmic chapter of the guide; take it slowly.
> **Prerequisites:** [06](06-combinatorics-canonical-hands.md) (counting, multiplicity),
> [07](07-generator-simulation.md) (equity), [08](08-database-layer.md).

---

## The big picture

Chapter 7 ended with a warning: our equities are measured against a **random** opponent hand, but a real
opponent who folds 35% of the time doesn't fold random hands. They fold their **worst** hands and call with
their **best**. So when you get called, you face a *stronger* opponent than "random".

This chapter builds the fix. The project now supports two **opponent models**:

| Model | The opponent folds… | So a call comes from… | Equity source |
|---|---|---|---|
| `random` | regardless of their cards | a random hand | `winrates.json` (chapter 7) |
| `range` | their **weakest** hands | the strongest `1 − f` of all hands | **this chapter** |

How big is the difference? Equity of a few hands when the opponent folds a fraction `f` of the time and
calls with the rest (the `f = 0` column equals the random-hand equity from chapter 7):

| Hand | f = 0 | f = 0.20 | f = 0.35 | f = 0.50 | f = 0.70 | f = 0.90 |
|---|---|---|---|---|---|---|
| `Q-K-A` (best Liêng) | 0.9969 | 0.9962 | 0.9952 | 0.9938 | 0.9895 | 0.9664 |
| `K-K-Q` (Đĩ) | 0.9610 | 0.9510 | 0.9394 | 0.9209 | 0.8662 | 0.5666 |
| `9-8-2` (9 points) | 0.8790 | 0.8488 | 0.8147 | 0.7593 | 0.5968 | 0.0000 |
| `K-Q-5` (5 points) | 0.5541 | 0.4400 | 0.3097 | 0.0976 | 0.0000 | 0.0000 |
| `K-Q-3` (3 points) | 0.3600 | 0.1976 | **0.0108** | 0.0000 | 0.0000 | 0.0000 |
| `K-6-6` (2 points) | 0.2541 | 0.0663 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

Monster hands barely notice. Medium hands **collapse**: `K-Q-3` wins 36% against a random hand but only
1% against an opponent who folds their weakest 35%. Using random-hand equity for such hands badly
overestimates what you win when called.

```
 455 canonical hands ──sort by strength──► A-A-A, K-K-K, …, 5-3-2, 4-4-2, 4-3-3
                                              │
     one-time build (~60 ms): for each Hero hand, a "prefix table" counting how many opponent
     combos exist among the j strongest classes, after removing Hero's cards  (455 × 456 numbers)
                                              │
 query (Hero, f) ──► where does the calling range end? (binary search) ──► count beaten / tied
                     ──► equity = (beaten + ½ tied) / calling          O(1) per hand
```

---

## Concepts you need

### 1. The calling range, as a list of combos

Sort all 455 classes **strongest first** and imagine each class as a stack of its real combos
(multiplicity 4, 24 or 64). An opponent who folds a fraction `f` calls with the first
`(1 − f) × 22,100` combos of that list.

Example, `f = 0.35`: the opponent calls with `0.65 × 22,100 = 14,365` combos. Walking down the list, the
first 297 classes contain 14,308 combos. The next class, `K-9-4` (64 combos), would bring the total to
14,372, more than 14,365. So `K-9-4` calls only **partially**: 57 of its 64 combos, a fraction
`57 / 64 = 0.890625`. We call it the **boundary class**.

```
 index:   0       1      ...     296    │  297 (K-9-4)   │  298 ...  454
 class:  A-A-A   K-K-K   ...            │  boundary      │  …       4-3-3
 combos:  4       4      ...            │  57 of 64 call │  all fold
          └──────── call in full ───────┘  (frac 0.89)   └── fold ──┘
```

### 2. Card removal

If Hero holds `K♠ Q♥ 3♦`, the opponent **cannot** hold those three cards. That changes how many combos of
each class the opponent can have. For a class, count, rank by rank, the ways to pick the needed cards
from those still in the deck:

```
opponent combos of a class  =  ∏ over its ranks  C(cards of that rank still in the deck, cards needed)
```

With Hero = K-Q-3 (one K, one Q, one 3 gone; three of each left):

| Opponent class | Needs | Count | Normally |
|---|---|---|---|
| `K-K-Q` | 2 Kings, 1 Queen | C(3,2) × C(3,1) = 3 × 3 = **9** | 24 |
| `K-K-K` | 3 Kings | C(3,3) = **1** | 4 |
| `A-A-A` | 3 Aces | C(4,3) = **4** | 4 (unaffected) |
| `K-Q-3` (tie!) | 1 K, 1 Q, 1 three | 3 × 3 × 3 = **27** | 64 |

Summed over all 455 classes, the counts always add up to C(49, 3) = **18,424**, the number of opponent
hands left after Hero's 3 cards. (The tests check this for every Hero hand.)

### 3. Prefix sums

A **prefix-sum** table stores running totals: entry `j` = sum of the first `j` items.

```python
items  = [4, 4, 24, 64]
prefix = [0, 4, 8, 32, 96]     # prefix[j] = items[0] + … + items[j-1]
```

Then the sum of any block of items is **one subtraction**: items 1..2 = `prefix[3] − prefix[1] = 32 − 4 = 28`.
No loop needed. We precompute one such table per Hero hand, so "how many calling combos are weaker than
Hero?" becomes a subtraction: O(1).

### 4. Binary search with `bisect`

To find the boundary class we need "the last index whose running total is ≤ 14,365". The list of running
totals is sorted, so we can use **binary search**. Like looking up a word in a dictionary, it halves the
search space each step: about 9 steps for 456 entries instead of up to 456. Python's `bisect` module
does it:

```python
>>> from bisect import bisect_right
>>> cum = [0, 4, 8, 32, 96]
>>> bisect_right(cum, 10)      # position where 10 would be inserted, after any equal values
3
```

So the last running total ≤ 10 is at index `3 − 1 = 2` (`cum[2] = 8 ≤ 10 < cum[3] = 32`): class 2 is the
boundary.

### 5. Precompute once, query forever

The prefix tables cost 455 rows × 456 numbers ≈ 207,000 integers to build (≈ 60 ms, ≈ 830 KB). After that,
**any** equity question is a handful of array lookups. It's the same "offline work, fast lookup" idea
as the whole project (chapter 1), at a smaller scale.

### 6. Two small Python tools

- **`array("i", [...])`** (module `array`) stores plain 32-bit integers compactly: 4 bytes each, instead of
  a full Python `int` object (~28 bytes) plus an 8-byte pointer per list slot. Useful for big numeric tables.
- **`class OpponentModel(str, Enum)`**: an enum whose members **are also strings**. So
  `OpponentModel.RANGE == "range"` is `True`, it converts to JSON naturally, and
  `OpponentModel("range")` turns text from a web request back into the enum (or raises `ValueError`).

---

## Step 9.1 — Docstring, imports and constants

📄 **File:** `backend/src/calling_range.py` — *create this file*

```python
"""Liêng Stealer - Opponent Calling-Range Model.

An opponent who folds a fraction f of the time does not fold at random: they fold
their weakest hands and call with the strongest (1 - f) of the 22,100-combination
space. This module computes Hero's exact showdown equity against that calling
range, including card removal (Hero's own ranks are unavailable to the opponent).

All 455 canonical classes have distinct strengths, so they form a total order.
After a one-time O(455²) table build, any equity query is O(1) per hand and a
full 455-hand table is O(455).
"""

from __future__ import annotations

from array import array
from bisect import bisect_right
from collections import Counter
from enum import Enum
from math import comb
from typing import Final, Sequence

from src.hands import CanonicalHand, generate_all_canonical_hands

TOTAL_COMBINATIONS: Final[int] = 22100
OPPONENT_COMBINATIONS: Final[int] = 18424  # C(49, 3) hands left after Hero's 3 cards

# _COMB[n][k] = C(n, k) for the at most 4 cards of a rank left in the deck
_COMB: Final[tuple[tuple[int, ...], ...]] = tuple(
    tuple(comb(n, k) for k in range(4)) for n in range(5)
)
```

**How it works**

- "All 455 canonical classes have distinct strengths": every class has a different `score_tuple` (the
  tie-breaker contains its ranks, chapter 5), so they can be sorted into one strict order.
- `_COMB` is a tiny **lookup table** of binomial coefficients: `_COMB[n][k] = C(n, k)` for `n` = 0…4 cards
  of a rank left in the deck and `k` = 0…3 cards needed. It's built once, at import:

  ```
  _COMB = ((1, 0, 0, 0), (1, 1, 0, 0), (1, 2, 1, 0), (1, 3, 3, 1), (1, 4, 6, 4))
  ```

  For example, `_COMB[3][2] = 3`: three Kings left, choose two. Looking up a tuple is faster than calling
  `math.comb` hundreds of thousands of times during the table build.
- `TOTAL_COMBINATIONS` (22,100) and `OPPONENT_COMBINATIONS` (18,424 = C(49,3)) are named constants.

> 💡 `TOTAL_COMBINATIONS` is also defined in `range_finder.py` (chapter 11), and `22100` appears as a
> literal in `app.py`. One shared definition (e.g. in `hands.py`) would remove the duplication.

---

## Step 9.2 — The `OpponentModel` enum

📄 **File:** `backend/src/calling_range.py` — *add to the end*

```python


class OpponentModel(str, Enum):
    """How the opponent decides which hands to fold."""
    RANDOM = "random"  # Folds regardless of strength, so a call comes from a random hand
    RANGE = "range"    # Folds the weakest hands, calls with the strongest (1 - f)
```

The values `"random"` and `"range"` are exactly what the web API accepts in its `opponent_model` field
(chapter 13), and what the UI sends (chapter 16).

🧪 **Mini-check**

```bash
python -c "
from src.calling_range import OpponentModel
print(OpponentModel('range'), OpponentModel.RANGE == 'range', [m.value for m in OpponentModel])
"
```

Expected output:

```
OpponentModel.RANGE True ['random', 'range']
```

---

## Step 9.3 — `CallingRangeModel.__init__`, part 1: order the classes

📄 **File:** `backend/src/calling_range.py` — *add to the end*

```python


class CallingRangeModel:
    """Exact equity of every canonical hand against a strength-ordered calling range.

    Classes are ordered strongest-first. For Hero class h, ``_prefix[h][j]`` counts
    the opponent combinations among the j strongest classes that remain possible
    after removing Hero's three ranks from the deck.
    """

    def __init__(self, hands: Sequence[CanonicalHand] | None = None) -> None:
        """Build the card-removal prefix tables.

        Args:
            hands: Canonical hands to model. Defaults to all 455 classes.
        """
        ordered = sorted(
            hands if hands is not None else generate_all_canonical_hands(),
            key=lambda h: h.score.score_tuple,
            reverse=True,
        )
        self._ids: tuple[str, ...] = tuple(h.canonical_id for h in ordered)
        self._index: dict[str, int] = {cid: i for i, cid in enumerate(self._ids)}
        self._mult: tuple[int, ...] = tuple(h.multiplicity for h in ordered)

        cum_mult = [0]
        for m in self._mult:
            cum_mult.append(cum_mult[-1] + m)
        self._cum_mult: tuple[int, ...] = tuple(cum_mult)
```

**How it works**

- **Sort strongest first** by `score_tuple` (chapter 5), so index 0 is `A-A-A` and index 454 is `4-3-3`.
- Three parallel structures describe the order:
  - `_ids[i]`: the canonical ID at strength position `i`;
  - `_index[cid]`: the reverse lookup, ID → position (a dict, so O(1));
  - `_mult[i]`: the multiplicity at position `i`.
- `_cum_mult` is the **prefix sum** of multiplicities: `_cum_mult[j]` = total combos in the `j` strongest
  classes. It starts at 0 and ends at 22,100. We'll binary-search it to find the boundary class.
- `hands` is optional (**dependency injection** again): tests could pass a small custom list, while normal
  use builds all 455.

---

## Step 9.4 — `__init__`, part 2: the card-removal prefix tables

📄 **File:** `backend/src/calling_range.py` — *add to the end*

```python

        rank_counts = [Counter(r.value for r in h.ranks) for h in ordered]
        opponent_needs = [tuple(c.items()) for c in rank_counts]
        self._prefix: tuple[array[int], ...] = tuple(
            self._build_prefix_row(hero, opponent_needs) for hero in rank_counts
        )
```

**How it works**

- `Counter(r.value for r in h.ranks)` counts how many of each rank a class contains:
  `K-K-Q` → `Counter({13: 2, 12: 1})`.
- `opponent_needs[j]` is the same information as a tuple of `(rank, count)` pairs, e.g. `((13, 2), (12, 1))`:
  "to hold class `j`, the opponent needs two 13s and one 12".
- For **every Hero class**, build one prefix row (next step). Result: `_prefix[h]` is Hero `h`'s table.

---

## Step 9.5 — `_build_prefix_row`: counting with card removal

📄 **File:** `backend/src/calling_range.py` — *add to the end*

```python

    @staticmethod
    def _build_prefix_row(
        hero: Counter[int],
        opponent_needs: Sequence[tuple[tuple[int, int], ...]],
    ) -> array[int]:
        """Cumulative count of opponent combos per class, given Hero's ranks."""
        remaining = {rank: 4 - hero[rank] for rank in range(2, 15)}
        row = array("i", [0])
        total = 0
        for needs in opponent_needs:
            available = 1
            for rank, need in needs:
                available *= _COMB[remaining[rank]][need]
            total += available
            row.append(total)
        return row
```

**How it works**

- `remaining`: how many cards of each rank are left after Hero's hand. A `Counter` returns 0 for missing
  keys, so ranks Hero doesn't hold keep all 4.
- For each opponent class (strongest first), multiply `C(left, needed)` over its ranks: the card-removal
  formula from Concepts §2, using the `_COMB` lookup table. If Hero holds a rank the class needs too often
  (e.g. Hero has two Kings and the class is `K-K-K`), `_COMB[2][3]` is 0: that class is impossible.
- `total` accumulates, so `row` is a **prefix sum**: `row[j]` = opponent combos among the `j` strongest
  classes. The row has 456 entries (0 plus one per class), and the last one is always 18,424.
- `@staticmethod`: the method uses only its arguments, not `self`.
- The whole build is 455 rows × 455 classes ≈ 207,000 small products: the O(455²) one-time cost.

🧪 **Mini-check** (the constructor works now; `_ids`, `_cum_mult` and `_prefix` are private, but
peeking at them is fine for learning):

```bash
python -c "
from src.calling_range import CallingRangeModel
m = CallingRangeModel()
print(m._ids[:4], m._ids[-2:])
print(m._cum_mult[:5], m._cum_mult[-1])
h = m._ids.index('K-Q-3')
print(h, len(m._prefix[h]), m._prefix[h][-1])
"
```

Expected output:

```
('A-A-A', 'K-K-K', 'Q-Q-Q', 'J-J-J') ('4-4-2', '4-3-3')
(0, 4, 8, 12, 16) 22100
294 456 18424
```

`K-Q-3` is class number 294 in strength order, and its row ends at 18,424 = C(49, 3), as it must.

---

## Step 9.6 — Container protocols

📄 **File:** `backend/src/calling_range.py` — *add to the end*

```python

    def __len__(self) -> int:
        return len(self._ids)

    def __contains__(self, canonical_id: object) -> bool:
        return canonical_id in self._index
```

Same protocol methods as `WinRateDB` (chapter 8): `len(model)` → 455, `"K-Q-3" in model` → `True`.

---

## Step 9.7 — The public API: `equity` and `equity_table`

📄 **File:** `backend/src/calling_range.py` — *add to the end*

```python

    def equity(self, canonical_id: str, fold_equity: float) -> float:
        """Hero's equity when called by an opponent who folds their weakest hands.

        Args:
            canonical_id: Hero's canonical hand, e.g. 'K-Q-3'.
            fold_equity: Opponent fold frequency in [0.0, 1.0].

        Returns:
            Win probability plus half the tie probability, rounded to 4 places.
            0.0 when the calling range is empty (e.g. fold_equity == 1.0).

        Raises:
            KeyError: If canonical_id is unknown.
            ValueError: If fold_equity is outside [0.0, 1.0].
        """
        if canonical_id not in self._index:
            raise KeyError(f"Canonical hand '{canonical_id}' not found in calling-range model.")
        k, frac = self._calling_boundary(fold_equity)
        return self._equity_at(self._index[canonical_id], k, frac)

    def equity_table(self, fold_equity: float) -> dict[str, float]:
        """Equity when called for every canonical hand at one fold frequency.

        Args:
            fold_equity: Opponent fold frequency in [0.0, 1.0].

        Returns:
            Mapping of canonical ID to equity, as in ``equity()``.

        Raises:
            ValueError: If fold_equity is outside [0.0, 1.0].
        """
        k, frac = self._calling_boundary(fold_equity)
        return {cid: self._equity_at(i, k, frac) for i, cid in enumerate(self._ids)}
```

**How it works**

- Both methods do the same two steps: (1) find where the calling range ends, (2) compute equity for
  Hero. They delegate to two private helpers (next steps).
- `equity_table` computes the boundary **once** and reuses it for all 455 hands. That's what the range
  finder (chapter 11) needs: one call per solve, about 0.6 ms.
- At `fold_equity == 1.0` nobody calls, so there's no showdown. The method returns 0.0 instead of dividing
  by zero, and documents it.

---

## Step 9.8 — `_calling_boundary`: where does the calling range end?

📄 **File:** `backend/src/calling_range.py` — *add to the end*

```python

    def _calling_boundary(self, fold_equity: float) -> tuple[int, float]:
        """Return (k, frac): classes [0, k) call in full, class k calls with weight frac."""
        if not (0.0 <= fold_equity <= 1.0):
            raise ValueError(f"Fold equity must be between 0.0 and 1.0, got {fold_equity}.")
        calling_combos = (1.0 - fold_equity) * TOTAL_COMBINATIONS
        k = bisect_right(self._cum_mult, calling_combos) - 1
        if k >= len(self._ids):
            return len(self._ids), 0.0
        return k, (calling_combos - self._cum_mult[k]) / self._mult[k]
```

**How it works**: the boundary from Concepts §1, in four lines.

1. `calling_combos = (1 − f) × 22,100`: for `f = 0.35`, **14,365**.
2. `bisect_right(_cum_mult, 14365) − 1` = the last index whose running total is ≤ 14,365 → `k = 297`
   (`_cum_mult[297] = 14,308`).
3. If `f = 0`, all 22,100 combos call: `k` would be 455 (past the end), so return "all classes in full,
   no partial class".
4. Otherwise the boundary class `k` calls with weight `(14,365 − 14,308) / 64 = 0.890625`.

🧪 **Mini-check**

```bash
python -c "
from src.calling_range import CallingRangeModel
m = CallingRangeModel()
print(m._calling_boundary(0.35), m._ids[297], m._calling_boundary(0.0), m._calling_boundary(1.0))
"
```

Expected output:

```
(297, 0.890625) K-9-4 (455, 0.0) (0, 0.0)
```

---

## Step 9.9 — `_equity_at`: beaten, tied, calling

📄 **File:** `backend/src/calling_range.py` — *add to the end*

```python

    def _equity_at(self, hero: int, k: int, frac: float) -> float:
        """Equity of the Hero class at strength index ``hero`` against boundary (k, frac)."""
        row = self._prefix[hero]
        boundary = frac * (row[k + 1] - row[k]) if k < len(self._ids) else 0.0
        calling = row[k] + boundary
        if calling <= 0.0:
            return 0.0

        if hero < k:
            # Hero beats every calling class weaker than itself, including the boundary
            beaten = row[k] - row[hero + 1] + boundary
            tied = row[hero + 1] - row[hero]
        elif hero == k:
            beaten = 0.0
            tied = boundary
        else:
            beaten = 0.0
            tied = 0.0
        return round((beaten + 0.5 * tied) / calling, 4)
```

**How it works.** Everything is a subtraction in Hero's prefix row (`row`), which already accounts for card
removal:

- `boundary` = the opponent combos of the boundary class that call (its card-removal count × `frac`).
- `calling` = all calling combos = the classes before `k` in full (`row[k]`) + the partial boundary.
- Three cases, depending on where Hero sits relative to the boundary:

```
 strength order:  0 … hero … k(boundary) …           (hero < k: Hero is inside the calling range)
                  ├─ stronger ─┤hero├─ weaker but calling ─┤
                    Hero loses   tie     Hero beats these
```

  - **`hero < k`**: Hero is stronger than the boundary. It **beats** every calling class weaker than itself
    (`row[k] − row[hero+1]`, plus the boundary part), **ties** with the other combos of its own class
    (`row[hero+1] − row[hero]`), and loses to everything stronger.
  - **`hero == k`**: Hero *is* the boundary class: it can only tie with the boundary's calling combos.
  - **`hero > k`**: Hero is weaker than every calling hand: equity 0.
- Equity = `(beaten + ½ tied) / calling`, the same formula as chapter 7.

**The worked example**, `K-Q-3` (index 294) against `f = 0.35` (`k = 297`, `frac = 0.890625`), using
values from Hero's row:

| Quantity | Formula | Value |
|---|---|---|
| boundary | 0.890625 × (row[298] − row[297]) = 0.890625 × (11,925 − 11,877) | 42.75 |
| calling | row[297] + boundary = 11,877 + 42.75 | 11,919.75 |
| beaten | row[297] − row[295] + boundary = 11,877 − 11,805 + 42.75 | 114.75 |
| tied | row[295] − row[294] = 11,805 − 11,778 | 27 |
| **equity** | (114.75 + 0.5 × 27) / 11,919.75 | **0.0108** |

`K-Q-3` is near the bottom of the calling range: it only beats two classes (`K-J-3`, `K-10-3`, both
3 points with a lower second card) and the partial `K-9-4`. Notice `tied = 27`, exactly the 3 × 3 × 3 card-removal count from Concepts §2.

🧪 **Mini-check** (the table from "The big picture"):

```bash
python -c "
from src.calling_range import CallingRangeModel
m = CallingRangeModel()
for cid in ['Q-K-A', 'K-K-Q', '9-8-2', 'K-Q-5', 'K-Q-3', 'K-6-6']:
    print(f'{cid:6}', [m.equity(cid, f) for f in (0.0, 0.2, 0.35, 0.5, 0.7, 0.9)])
"
```

Expected output:

```
Q-K-A  [0.9969, 0.9962, 0.9952, 0.9938, 0.9895, 0.9664]
K-K-Q  [0.961, 0.951, 0.9394, 0.9209, 0.8662, 0.5666]
9-8-2  [0.879, 0.8488, 0.8147, 0.7593, 0.5968, 0.0]
K-Q-5  [0.5541, 0.44, 0.3097, 0.0976, 0.0, 0.0]
K-Q-3  [0.36, 0.1976, 0.0108, 0.0, 0.0, 0.0]
K-6-6  [0.2541, 0.0663, 0.0, 0.0, 0.0, 0.0]
```

The first column equals `winrates.json` exactly (`Q-K-A` 0.9969, `K-Q-3` 0.36, …), even though it was
computed by a completely different method (counting with prefix tables instead of playing 18,424
showdowns). Two independent methods agreeing is strong evidence both are right.

> ⚠️ **Pitfall: two modelling choices to be aware of.**
> 1. **The opponent is a perfect "strength sorter".** Real players sometimes call with weak hands
>    (curiosity, bluff-catching) and fold strong ones. The model is the opposite extreme of `random`; the
>    truth is usually somewhere between. Offering both models lets the user bracket reality.
> 2. **The range boundary ignores card removal.** "Calls with the top 65%" is measured over all 22,100
>    combos, but given Hero's cards only 18,424 opponent hands are possible, and Hero's cards remove
>    unevenly from strong and weak classes. So the opponent's real calling frequency differs slightly from
>    `1 − f`. It's a reasonable, documented simplification. Removing it would mean a per-Hero boundary
>    search over Hero's own prefix row.

---

## Step 9.10 — The tests

📄 **File:** `backend/tests/test_calling_range.py` — *create this file*

```python
"""Unit tests for the Opponent Calling-Range Model (CallingRangeModel).

Verifies:
- Card-removal tables: every Hero row counts exactly C(49, 3) = 18,424 opponent hands
- At 0% fold equity the model reproduces the exact enumeration in winrates.json for all 455 classes
- Equity when called never increases as the opponent folds more (calling range only gets stronger)
- Regression anchors for medium hands, and boundary handling at 100% fold equity
- Full 455-hand equity table stays within the 25 ms range-solve budget
"""

import time

import pytest

from src.calling_range import OPPONENT_COMBINATIONS, CallingRangeModel
from src.db import WinRateDB


@pytest.fixture(scope="module")
def model() -> CallingRangeModel:
    return CallingRangeModel()


@pytest.fixture(scope="module")
def db() -> WinRateDB:
    return WinRateDB("data/winrates.json")
```

📄 **File:** `backend/tests/test_calling_range.py` — *add to the end*

```python


class TestCallingRangeModel:
    """Test suite for equity against a strength-ordered calling range."""

    def test_covers_all_455_classes(self, model: CallingRangeModel) -> None:
        assert len(model) == 455
        assert "K-Q-3" in model
        assert "3-K-Q" not in model

    def test_card_removal_rows_sum_to_18424(self, model: CallingRangeModel) -> None:
        """Each Hero row must count every opponent hand left in the 49-card deck exactly once."""
        assert all(row[-1] == OPPONENT_COMBINATIONS for row in model._prefix)

    def test_zero_fold_matches_exact_enumeration(self, model: CallingRangeModel, db: WinRateDB) -> None:
        """With no folds the calling range is every hand, so equity must equal winrates.json."""
        table = model.equity_table(0.0)
        for cid, stats in db.all_items().items():
            assert table[cid] == pytest.approx(stats.equity, abs=1e-4), cid

    def test_equity_never_increases_with_fold_equity(self, model: CallingRangeModel) -> None:
        tables = [model.equity_table(i / 20) for i in range(21)]
        for weaker_range, stronger_range in zip(tables, tables[1:]):
            for cid, equity in stronger_range.items():
                assert equity <= weaker_range[cid] + 1e-9, cid
```

**How it works**

- `test_card_removal_rows_sum_to_18424`: the **invariant** from Concepts §2, checked for all 455 Hero
  rows. If the card-removal formula were wrong anywhere, a row would not sum to C(49, 3).
- `test_zero_fold_matches_exact_enumeration`: the **cross-check** against chapter 7's data. With no
  folds, "calling range" = every hand = random hand, so all 455 equities must match `winrates.json`.
  `pytest.approx(x, abs=1e-4)` compares floats with a tolerance; the extra `, cid` after the assert is a
  failure message naming the hand.
- `test_equity_never_increases_with_fold_equity`: a **property test**. As `f` grows, the calling range
  only loses its weakest hands, so equity can never go up. Checked on a grid of 21 fold values for every
  hand. `zip(tables, tables[1:])` pairs each table with the next one.

> 💡 `test_card_removal_rows_sum_to_18424` reads the **private** `_prefix` attribute. Testing internals
> gives a precise check, but the test breaks if the internal layout changes even when the public behaviour
> doesn't. It's a trade-off; here the invariant is valuable enough to justify it.

📄 **File:** `backend/tests/test_calling_range.py` — *add to the end*

```python

    def test_nuts_always_win_when_called(self, model: CallingRangeModel) -> None:
        for i in range(100):
            assert model.equity("A-A-A", i / 100) == 1.0

    def test_medium_hands_regression(self, model: CallingRangeModel) -> None:
        """Opponent folding their weakest 35% leaves 3 and 5 points far behind their random-hand equity."""
        assert model.equity("K-Q-3", 0.35) == pytest.approx(0.0108, abs=1e-4)
        assert model.equity("K-Q-5", 0.35) == pytest.approx(0.3097, abs=1e-4)

    def test_full_fold_returns_zero_without_error(self, model: CallingRangeModel) -> None:
        assert model.equity("K-Q-5", 1.0) == 0.0
        assert set(model.equity_table(1.0).values()) == {0.0}
```

- A **regression test** pins down known-good values (our worked example, 0.0108) so that any future change
  to the algorithm that alters results is caught immediately.
- The full-fold test checks the edge case where the calling range is empty: no crash, equity 0.

📄 **File:** `backend/tests/test_calling_range.py` — *add to the end*

```python

    def test_invalid_inputs(self, model: CallingRangeModel) -> None:
        with pytest.raises(ValueError):
            model.equity("K-Q-5", -0.01)
        with pytest.raises(ValueError):
            model.equity_table(1.01)
        with pytest.raises(KeyError):
            model.equity("Z-Z-Z", 0.5)

    def test_full_table_within_latency_budget(self, model: CallingRangeModel) -> None:
        start = time.perf_counter()
        model.equity_table(0.35)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 25.0
```

The last test guards the `AGENTS.md` budget for a full range solve (25 ms). A typical run takes about
**0.6 ms**.

---

## ✅ Checkpoint

```bash
python -m pytest tests/test_calling_range.py -v
```

Expected: **9 passed**. Then the whole suite so far (evaluator 18 + hands 5 + generator 5 + db 6 +
calling range 9):

```bash
python -m pytest -q
```

```
...........................................                              [100%]
43 passed in 2.10s
```

Commit:

```bash
git add . && git commit -m "feat: calling-range opponent model with card removal"
```

## Recap

- A real opponent folds their **weakest** hands, so when called you face their **strongest** `1 − f`. Against
  that range, medium hands lose most of their equity (`K-Q-3`: 0.36 → 0.0108 at `f = 0.35`).
- The calling range = the strongest `(1 − f) × 22,100` combos in strength order, with one partially-calling
  **boundary class** found by **binary search** (`bisect_right`) on the running totals.
- **Card removal**: opponent combos of a class = ∏ C(cards left of a rank, cards needed). Every Hero row sums to C(49,3) = 18,424.
- **Prefix sums** turn "how many calling hands do I beat?" into subtractions: an O(455²) one-time build
  (~60 ms), then O(1) per query.
- At `f = 0` the model reproduces `winrates.json` exactly: two independent methods agree.

**Next:** [10 — Expected Value](10-expected-value.md)
