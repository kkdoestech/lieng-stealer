# Lesson 03 — Canonical hands: 22,100 → 455

> **Goal:** understand why suits can be thrown away, how `hands.py` names each of the 455 rank
> patterns, how many real hands each name stands for, and why those names are a little
> inconsistent.
> **Files:** [`backend/src/hands.py`](../backend/src/hands.py),
> [`backend/tests/test_hands.py`](../backend/tests/test_hands.py).
> **Time:** ~60 min. **Before this:** [02 — Hand evaluation](02-hand-evaluation.md).

---

## Where this fits

```
  any 3 Cards ──► get_canonical_id ──► "K-Q-J"   the key of winrates.json and of every table
                    to_canonical   ──► CanonicalHand(id, ranks, multiplicity, category, score)

  ┌──────────────────────────────────────────────────────────┐
  │ hands.py (this lesson)                                   │
  │ generate_all_canonical_hands() ─► 455 CanonicalHands     │
  │ get_representative_cards("K-Q-J") ─► Js Qh Kd            │
  └──────────────────────────────────────────────────────────┘
        │                          │                         │
        ▼                          ▼                         ▼
  generator.py (04)          db.py (05)                 calling_range.py (06),
  one representative         get_by_cards: cards → id   range_finder.py (08):
  per class, 455 tasks       → equity                   loop over the 455 classes
```

Lesson 02 showed that the 22,100 possible hands produce only 455 distinct scores. This module turns
that observation into data structures: a **name** for each rank pattern, its **multiplicity** (how
many real hands share it), and a way back from a name to real cards. Every table in the project is
keyed by these names, so their exact spelling matters more than you'd expect.

---

## Reading order

| # | Location | What to look for |
|---|----------|------------------|
| 1 | [hands.py:1-9](../backend/src/hands.py#L1-L9) | The whole idea and the arithmetic, in the module docstring. |
| 2 | [hands.py:69-101](../backend/src/hands.py#L69-L101) | `get_canonical_id`: sort, two special cases, join. |
| 3 | [hands.py:104-116](../backend/src/hands.py#L104-L116) | `_compute_multiplicity`: 4, 24 or 64. |
| 4 | [hands.py:119-141](../backend/src/hands.py#L119-L141) | `get_representative_cards`: from a name back to three cards. |
| 5 | [hands.py:144-176](../backend/src/hands.py#L144-L176) | `to_canonical`: id + score + ranks + multiplicity. Spot the repeated special case. |
| 6 | [hands.py:179-202](../backend/src/hands.py#L179-L202) | `generate_all_canonical_hands`: the 455, via `combinations_with_replacement`. |
| 7 | [hands.py:30-66](../backend/src/hands.py#L30-L66) | `CanonicalHand`: which comparisons exist, and which don't. |
| 8 | [test_hands.py](../backend/tests/test_hands.py) | Five tests: 455, 22,100, category counts, suit invariance, round trip. |

---

## Walkthrough

### 1. Why suits can be thrown away

Look back at lesson 02: no line of `evaluate_hand` reads a suit except the duplicate check. So two
hands with the same three ranks have the same score, whatever their suits, and they win, tie and
lose against exactly the same opponents. That makes "same ranks" an **equivalence relation**: it
splits the 22,100 hands into groups (classes) whose members are interchangeable. One
representative per class is enough to compute every equity.

How many classes? A class is a *multiset* of three ranks (order doesn't matter, repeats allowed),
chosen from 13 ranks: C(13 + 3 − 1, 3) = C(15, 3) = **455**. You can also count by shape:

| Shape | How to choose the ranks | Classes | Suit choices each (multiplicity) | Real hands |
|-------|------------------------|---------|-----------------------------------|-----------|
| three of a rank (7-7-7) | 13 ranks | 13 | C(4, 3) = 4 | 13 · 4 = 52 |
| a pair (7-7-9) | 13 for the pair × 12 for the odd card | 156 | C(4, 2) · 4 = 24 | 156 · 24 = 3,744 |
| three different (7-8-9) | C(13, 3) | 286 | 4 · 4 · 4 = 64 | 286 · 64 = 18,304 |
| **total** | | **455** | | **22,100** |

So **13·4 + 156·24 + 286·64 = 52 + 3,744 + 18,304 = 22,100 = C(52, 3)**. Every real hand is counted
exactly once. The module docstring ([hands.py:1-9](../backend/src/hands.py#L1-L9)) states the same
sum, and [test_hands.py:40-50](../backend/tests/test_hands.py#L40-L50) checks it.

### 2. `get_canonical_id`: a name for a rank pattern

📍 [`backend/src/hands.py:87-101`](../backend/src/hands.py#L87-L101)
```python
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

Sorting makes the name independent of suits and of the order the cards were dealt. The rule is
"ranks from high to low, joined by hyphens", with two exceptions written the way players say them:
A-2-3 (descending would be `A-3-2`) and Q-K-A (descending would be `A-K-Q`). Real output:

| Cards | `get_canonical_id` |
|-------|-------------------|
| 9h 7d 8c | `9-8-7` |
| 8s 9h 10d | `10-9-8` |
| 7s 7h 9d | `9-7-7` |
| As Kh Kd | `A-K-K` |
| Ks Ah 2d | `A-K-2` |
| As 2h 3d | `A-2-3` |
| Qs Kh Ad | `Q-K-A` |
| Js Qh Kd | **`K-Q-J`** |

That last row is the catch. Only two of the 12 straights are spelled low-to-high; J-Q-K is stored as
`K-Q-J`, 7-8-9 as `9-8-7`. Of the 455 keys in `winrates.json`, exactly two are not in descending
order: `A-2-3` and `Q-K-A`. A lookup must use the exact stored spelling:

| Key | In the database? |
|-----|------------------|
| `Q-K-A` | yes |
| `A-K-Q` | no |
| `K-Q-J` | yes |
| `J-Q-K` | no |
| `A-2-3` | yes |
| `3-2-A`, `A-3-2` | no |

You can see the two spellings side by side in one API response. The web page has a preset labelled
"Liêng J-Q-K" ([App.jsx:353](../frontend/src/App.jsx#L353)); for that hand, `/api/solve` returns
`"score_name": "Liêng J-Q-K"` (from `evaluator.py`'s names) and `"canonical_id": "K-Q-J"` (from
here).

### 3. `_compute_multiplicity`: 4, 24 or 64

📍 [`backend/src/hands.py:104-116`](../backend/src/hands.py#L104-L116)
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

Only equality matters, so the ranks don't need to be sorted. The multiplicity is the **weight** of
a class. Every module that reports "how many hands" or "what share of the range" adds up
multiplicities, not classes: the generator stores it in each record (lesson 04), the calling-range
model builds prefix sums of it (lesson 06), and range coverage is a sum of multiplicities over
22,100 (lesson 08). Counting classes instead would give the 13 Sáp classes the same weight as 13
ordinary classes that stand for 64 hands each.

Per category (real counts from `generate_all_canonical_hands()`):

| Category | Classes | Real hands | Multiplicities |
|----------|---------|-----------|----------------|
| Sáp | 13 | 52 | 13 × 4 |
| Liêng | 12 | 768 | 12 × 64 |
| Đĩ | 6 | 144 | 6 × 24 |
| Điểm | 424 | 21,136 | 150 × 24 + 274 × 64 |
| **total** | **455** | **22,100** | |

Điểm gets everything that is left: the 156 − 6 = 150 pair classes that aren't Đĩ, and the
286 − 12 = 274 three-rank classes that aren't straights. A random hand is a Liêng
768 / 22,100 = 3.48% of the time.

### 4. `get_representative_cards`: from a name back to cards

📍 [`backend/src/hands.py:134-141`](../backend/src/hands.py#L134-L141)
```python
    tokens = [t for t in re.split(r"[\s,\-]+", canonical_id.strip()) if t]
    if len(tokens) != 3:
        raise InvalidHandSizeError(f"Canonical ID '{canonical_id}' must consist of 3 ranks.")

    ranks = [Rank.from_str(tok) for tok in tokens]
    # Assign distinct suits to prevent duplicate cards even when ranks are identical
    suits = (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS)
    return [Card(rank=ranks[i], suit=suits[i]) for i in range(3)]
```

Giving the three cards three *different* suits (♠ ♥ ♦) guarantees a valid hand even for A-A-A. The
generator uses this to get a concrete hero hand for each class
([generator.py:48](../backend/src/generator.py#L48)). It is deliberately lenient: it splits like
`Hand.from_str` and accepts ranks in any order and case, so it works as a **normaliser**:

```
'J-Q-K'  -> [Card('Js'), Card('Qh'), Card('Kd')] -> K-Q-J
'j q k'  -> [Card('Js'), Card('Qh'), Card('Kd')] -> K-Q-J
'3,K,Q'  -> [Card('3s'), Card('Kh'), Card('Qd')] -> K-Q-3
'T-9-8'  -> [Card('10s'), Card('9h'), Card('8d')] -> 10-9-8
```

(the right-hand column is `get_canonical_id` of the cards). `get_canonical_id(get_representative_cards(text))`
turns any spelling into the stored one. Nothing in the code uses it that way yet (exercise 7).

### 5. `to_canonical`: everything about one hand

📍 [`backend/src/hands.py:156-169`](../backend/src/hands.py#L156-L169)
```python
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
```

It bundles the id, the full `HandScore` (lesson 02), the ranks in the same order as the id, and the
multiplicity into one frozen `CanonicalHand`. Lines 160-164 repeat the A-2-3/Q-K-A decision from
lines 94-97, so the "ranks" tuple matches the "id" string: `A-2-3` has ranks
`(ACE, TWO, THREE)`, while `K-Q-J` has `(KING, QUEEN, JACK)`. The API and CLI call this on the
player's hand ([app.py:175](../backend/app.py#L175), [cli.py:132](../backend/src/cli.py#L132)),
right after `db.get_by_cards` has already computed the same id once
([app.py:174](../backend/app.py#L174)).

### 6. `generate_all_canonical_hands`: the 455

📍 [`backend/src/hands.py:188-202`](../backend/src/hands.py#L188-L202)
```python
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

`itertools.combinations_with_replacement(ranks, 3)` yields each multiset exactly once, as an
ascending triple: `(2, 2, 2)`, `(2, 2, 3)`, …, `(A, A, A)`. It took 4.74 ms to build all 455. The
list comes out in that **multiset order**, not strength order: it starts
`2-2-2, 3-2-2, 4-2-2, 5-2-2, 6-2-2, 7-2-2` and ends `A-A-Q, K-K-K, A-K-K, A-A-K, A-A-A`. Note that
5-2-2 (9 points) is followed by 6-2-2 (0 points). That is also the key order of `winrates.json`.
Modules that need strength order sort by `score_tuple` themselves (lesson 06).

The generator, the calling-range model and the range finder all call this function at start-up
([generator.py:124](../backend/src/generator.py#L124),
[calling_range.py:54](../backend/src/calling_range.py#L54),
[range_finder.py:47](../backend/src/range_finder.py#L47)).

### 7. `CanonicalHand` and its comparisons

`CanonicalHand` ([hands.py:30-45](../backend/src/hands.py#L30-L45)) is a frozen dataclass with five
fields. It defines `__lt__`, `__gt__` and `__eq__`, all comparing `score`
([hands.py:47-60](../backend/src/hands.py#L47-L60)), and a short `__repr__` such as
`CanonicalHand('A-2-3', cat=LIENG, mult=64)`. So `max(hands)` is A-A-A and `min(hands)` is 4-3-3.
But `<=` and `>=` were never written:

```
TypeError: '<=' not supported between instances of 'CanonicalHand' and 'CanonicalHand'
```

`__eq__` follows the same pattern as `Hand` in lesson 02 (strength, while the generated hash uses
all fields). Here it is harmless: each class has a unique score, so equal score means the same
class and identical fields. The safety rests on that hidden fact.

### 8. What the tests pin

[test_hands.py](../backend/tests/test_hands.py) has five tests: exactly 455 unique ids
([:31](../backend/tests/test_hands.py#L31)); multiplicities summing to 22,100 with counts 13/156/286
([:40](../backend/tests/test_hands.py#L40)); category counts 13/12/6/424 and the six Đĩ shapes
([:52](../backend/tests/test_hands.py#L52)); suit invariance, including the spellings `9-8-7`,
`Q-K-A` and `A-2-3` ([:80](../backend/tests/test_hands.py#L80)); and the round trip
id → representative cards → id for all 455 ([:102](../backend/tests/test_hands.py#L102)). Elsewhere,
[test_calling_range.py:35](../backend/tests/test_calling_range.py#L35) pins that `"3-K-Q"` is *not*
a valid id. No test checks the duplicate-card case or the missing comparisons.

---

## 💡 Concept: `combinations` vs `combinations_with_replacement`

`itertools.combinations("ABC", 2)` gives `AB AC BC`: no repeats, order ignored. That is how you
list the 22,100 hands from 52 *cards*: `combinations(deck, 3)`. `combinations_with_replacement("ABC",
2)` gives `AA AB AC BB BC CC`: repeats allowed. That is how you list the 455 multisets of 13
*ranks*: a rank can appear twice or three times, because there are four suits. The count of
multisets of size k from n items is C(n + k − 1, k), the "stars and bars" formula:
C(13 + 3 − 1, 3) = 455. `math.comb(15, 3)` confirms it.

## 💡 Concept: `functools.total_ordering`

Python doesn't derive `<=` from `<` and `==` on its own. Decorate a class that defines `__eq__` and
one of `__lt__`, `__le__`, `__gt__`, `__ge__` with `@functools.total_ordering` and it fills in the
other three. `CanonicalHand` defines `__lt__`, `__gt__` and `__eq__` but not `__le__`/`__ge__`, so
`a <= b` fails. Adding the decorator above `@dataclass` fixes it (exercise 5).

---

## Design decisions

- **Compress by rank multiset.** 22,100 → 455 makes the generator 48.6 times cheaper and keeps
  `winrates.json` at 82,694 bytes. It is exact, not an approximation, because the evaluator never
  looks at suits.
- **Strings as keys.** `"K-Q-J"` is readable in JSON, logs and API responses, and works as a dict
  key everywhere. A tuple of ranks would be safer (no spelling choices) but uglier in JSON.
- **Player-friendly names for the two Ace straights.** `A-2-3` and `Q-K-A` are how players say
  them. The cost is an inconsistent format (weak spot 1).
- **Store the multiplicity with each class.** The weight travels with the data, so every later
  module can count real hands without redoing the combinatorics.
- **A representative with three different suits.** It is always a legal hand, even for A-A-A.
- **Generation order = multiset order.** Deterministic and simple; strength order is left to the
  modules that need it.

---

## ⚠️ Weak spots

1. **An inconsistent id format.** Descending everywhere except `A-2-3` and `Q-K-A`
   ([hands.py:94-97](../backend/src/hands.py#L94-L97)). `J-Q-K` and `A-K-Q` are not keys, while the
   same hands are *named* "Liêng J-Q-K" and "Liêng Q-K-A" by the evaluator. Anyone calling
   `db.get("J-Q-K")` gets a `KeyError` (lesson 01, weak spot 2). Changing the format is not a local
   fix: removing the special case fails 29 tests with the committed data, and still 6 after
   regenerating `winrates.json`, because tests spell `"Q-K-A"` and `"A-2-3"` out (exercise 7).
   *Fix:* keep the stored format and normalise lookups instead, with
   `get_canonical_id(get_representative_cards(text))`.
2. **The special case is written twice.** [hands.py:94-97](../backend/src/hands.py#L94-L97) for the id
   and [:161-164](../backend/src/hands.py#L161-L164) for the rank tuple. If one changes alone, a
   class's `id` and `ranks` disagree. *Fix:* one helper that returns the ordered ranks, used by both
   (the id is just those ranks joined).
3. **No duplicate check in `get_canonical_id`.** It checks only the count
   ([hands.py:87-88](../backend/src/hands.py#L87-L88)). `[As, As, Kd]` gets the id `A-A-K`, and
   `db.get_by_cards([As, As, Kd])` quietly returns A-A-K's stats (equity 0.2806). `to_canonical` does
   reject it, but only because it calls `evaluate_hand`. Today every caller passes a validated
   `Hand`, so the hole is latent. *Fix:* `len(set(cards)) != 3` → `InvalidHandSizeError`
   (exercise 4).
4. **`CanonicalHand` has no `<=` or `>=`.** [hands.py:47-60](../backend/src/hands.py#L47-L60) defines
   only `<`, `>` and `==`. *Fix:* `functools.total_ordering` (exercise 5). Its strength-based
   `__eq__` is safe only because the 455 scores are distinct.
5. **Unused imports.** `Final` ([hands.py:16](../backend/src/hands.py#L16)), `Hand`
   ([:20](../backend/src/hands.py#L20)) and `InvalidCardError` ([:27](../backend/src/hands.py#L27))
   are imported and never used. A linter (lesson 17 suggests ruff) would flag them.
6. **Repeated work per request.** `to_canonical` sorts the same three ranks four times (in
   `get_canonical_id`, `evaluate_hand`, and twice in its own body), and the API computes the id
   twice ([app.py:174-175](../backend/app.py#L174-L175)). It costs microseconds, but it is the kind
   of duplication that lets weak spot 2 happen.

---

## 🧪 Try it

Run from `backend/` with the virtual environment active.

```bash
python -m pytest tests/test_hands.py -q
```

Expected output (the timing varies):

```
.....                                                                    [100%]
5 passed in 0.04s
```

Check the arithmetic by brute force: group all 22,100 hands by id and compare with the
multiplicities.

```bash
python -c '
import itertools
from collections import Counter
from src.evaluator import Deck
from src.hands import generate_all_canonical_hands, get_canonical_id
hands = generate_all_canonical_hands()
print(Counter(h.multiplicity for h in hands))
print(13*4 + 156*24 + 286*64, sum(h.multiplicity for h in hands))
groups = Counter(get_canonical_id(c) for c in itertools.combinations(Deck.standard_52(), 3))
print(len(groups), groups == Counter({h.canonical_id: h.multiplicity for h in hands}))
'
```

Expected output:

```
Counter({64: 286, 24: 156, 4: 13})
22100 22100
455 True
```

See the inconsistent format and the missing duplicate check:

```bash
python -c '
from src.evaluator import Card, Hand
from src.hands import get_canonical_id
from src.db import WinRateDB
db = WinRateDB("data/winrates.json")
print(get_canonical_id(Hand.from_str("Js Qh Kd").cards), get_canonical_id(Hand.from_str("Qs Kh Ad").cards))
print([(k, k in db) for k in ("K-Q-J", "J-Q-K", "Q-K-A", "A-K-Q")])
dup = [Card.from_str("As"), Card.from_str("As"), Card.from_str("Kd")]
print(get_canonical_id(dup), db.get_by_cards(dup).equity)
'
```

Expected output:

```
K-Q-J Q-K-A
[('K-Q-J', True), ('J-Q-K', False), ('Q-K-A', True), ('A-K-Q', False)]
A-A-K 0.2806
```

---

## 🏋️ Exercises

Exercises marked 🟡 or 🔴 change code. Undo them afterwards with `git checkout -- <file>`.

**🟢 1. Predict the id.** What does `get_canonical_id` return for `3d Ac 2s`, `Kd Qs Ah`,
`Kc Qd Jh`, `2h Ks As` and `10c 10d 9s`? Check with
`get_canonical_id(Hand.from_str(s).cards)`.

<details><summary>Solution</summary>

`A-2-3`, `Q-K-A`, `K-Q-J`, `A-K-2` and `10-10-9`. Only the first two get the special spelling; the
third is a straight too, but descending. `A-K-2` is not a straight (lesson 02), just descending
ranks.
</details>

**🟢 2. Predict the multiplicity.** How many real hands does each class stand for: `7-7-7`,
`9-7-7`, `9-8-7`, `K-Q-Q`? And how many pair classes are there, and why 13 × 12 rather than
C(13, 2)?

<details><summary>Solution</summary>

4, 24, 64, 24. Pair classes: 156 = 13 × 12, because the pair rank and the odd rank play different
roles (7-7-9 and 9-9-7 are different classes). C(13, 2) = 78 would count only the unordered pair
of ranks. Check with `[h.multiplicity for h in generate_all_canonical_hands() if h.canonical_id
== "9-7-7"]`.
</details>

**🟢 3. Predict the leak.** Why does `db.get_by_cards([As, As, Kd])` return a result instead of
raising, and why doesn't the API ever hit this?

<details><summary>Solution</summary>

`get_by_cards` is `get_canonical_id` plus a dict lookup ([db.py:136-137](../backend/src/db.py#L136-L137)),
and `get_canonical_id` only checks the count. It returns A-A-K's stats (equity 0.2806). The API and
CLI always build a `Hand` first, whose `__post_init__` rejects duplicates (lesson 02).
</details>

**🟡 4. Close the duplicate hole.** In `get_canonical_id`, after the length check, raise
`InvalidHandSizeError("A Liêng hand cannot contain duplicate cards.")` when
`len(set(cards)) != 3`. Run `python -m pytest -q` and the probe from 🧪 Try it.

<details><summary>Solution</summary>

93 tests pass, and the probe now stops with
`InvalidHandSizeError: A Liêng hand cannot contain duplicate cards.` Add a test with `pytest.raises`
so it stays fixed. Undo with `git checkout -- backend/src/hands.py`.
</details>

**🟡 5. Complete the ordering.** Add `import functools` and decorate `CanonicalHand` with
`@functools.total_ordering` (above `@dataclass(frozen=True)`). Check that
`hands["Q-K-A"] <= hands["A-A-A"]` works, where `hands` maps ids to classes, and that the tests
pass. While you're in the file, remove the three unused imports.

<details><summary>Solution</summary>

`hands = {h.canonical_id: h for h in generate_all_canonical_hands()}`; `hands["Q-K-A"] <=
hands["A-A-A"]` and `hands["A-A-A"] >= hands["Q-K-A"]` both print `True`. 93 tests pass. Undo with
`git checkout -- backend/src/hands.py`.
</details>

**🟡 6. One place for the special case.** Write `_ordered_ranks(cards) -> tuple[Rank, Rank, Rank]`
that returns `(ACE, TWO, THREE)`, `(QUEEN, KING, ACE)` or the descending ranks, and use it in both
`get_canonical_id` (join the `short_name`s) and `to_canonical`. Check with `python -m pytest -q`:
all ids must stay exactly the same.

<details><summary>Solution sketch</summary>

```python
def _ordered_ranks(cards: Sequence[Card]) -> tuple[Rank, Rank, Rank]:
    low, mid, high = sorted(c.rank for c in cards)
    if (low, mid, high) == (Rank.TWO, Rank.THREE, Rank.ACE):
        return (Rank.ACE, Rank.TWO, Rank.THREE)
    if (low, mid, high) == (Rank.QUEEN, Rank.KING, Rank.ACE):
        return (Rank.QUEEN, Rank.KING, Rank.ACE)
    return (high, mid, low)
```

`get_canonical_id` becomes `"-".join(r.short_name for r in _ordered_ranks(cards))` after the
checks. `test_suit_invariance` and `test_representative_cards_validity` prove the ids didn't
change; the 93 tests pass. Undo with `git checkout -- backend/src/hands.py`.
</details>

**🔴 7. Measure the cost of one id format.** First, delete the special case at
[hands.py:93-97](../backend/src/hands.py#L93-L97) and run `python -m pytest -q`. Then regenerate the
data *into the repo copy you're experimenting on* (`python -m src.generator`) and run the tests
again. Finally, undo everything and implement the cheaper alternative: a
`normalise_canonical_id(text)` in `hands.py` that `WinRateDB.get` tries when a key is missing.

<details><summary>Solution</summary>

Without the special case: `29 failed, 64 passed`, mostly `KeyError: 'A-2-3'` because
`winrates.json` still uses the old keys. After regenerating: `6 failed, 87 passed`, the tests that
spell `"Q-K-A"` or `"A-2-3"` out (in `test_api.py`, `test_db.py`, `test_generator.py` and
`test_hands.py`). An id format is a public contract: it is in the data file, the API and the
tests.

The alternative keeps all 93 tests green:

```python
def normalise_canonical_id(text: str) -> str:
    """Return the stored spelling of any rank-order spelling ('J-Q-K' -> 'K-Q-J')."""
    try:
        return get_canonical_id(get_representative_cards(text))
    except LiengError:
        return text
```

With `db.get` retrying through it, `db.get("J-Q-K")` returns 0.995, `"A-K-Q"` and `"q k a"` return
0.9969, `"3-2-A"` returns 0.962, and `"INVALID_KEY"` still raises `KeyError`. Undo with
`git checkout -- backend/src/hands.py backend/src/db.py backend/data/winrates.json`.
</details>

---

## ❓ Quiz

1. Why is it safe to compute equity for one representative per class instead of all 22,100 hands?
2. Where do the three multiplicities 4, 24 and 64 come from?
3. Why does range coverage add up multiplicities rather than count classes?
4. Which two canonical ids are not in descending order, and what happens if you look up `J-Q-K`?
5. In what order does `generate_all_canonical_hands` return the classes, and why doesn't the
   calling-range model use that order directly?

<details><summary>Answers</summary>

1. `evaluate_hand` never looks at suits, so every hand in a class has the same score and therefore
   the same wins, ties and losses against every opponent.
2. Choosing suits: three cards of one rank use 3 of its 4 suits, C(4, 3) = 4; a pair uses
   C(4, 2) = 6 suit pairs times 4 suits for the odd card, 24; three different ranks choose a suit
   each, 4³ = 64.
3. Classes stand for different numbers of real hands (4 to 64). Coverage is a share of the 22,100
   hands, so each class must be weighted by its multiplicity.
4. `A-2-3` and `Q-K-A`. `J-Q-K` is stored as `K-Q-J`, so `db.get("J-Q-K")` raises `KeyError`.
5. In multiset order from `combinations_with_replacement` (`2-2-2`, `3-2-2`, … `A-A-A`), which is
   not strength order (5-2-2 with 9 points is followed by 6-2-2 with 0). The calling-range model
   needs strongest-first, so it sorts by `score_tuple` itself.
</details>

---

## Recap

- Suits never affect a score, so the 22,100 hands fall into 455 rank-multiset classes:
  C(15, 3) = 455, and 13·4 + 156·24 + 286·64 = 22,100.
- `get_canonical_id` names a class by its ranks, high to low, except `A-2-3` and `Q-K-A`; J-Q-K is
  `K-Q-J`. Lookups need the exact spelling.
- The multiplicity (4, 24 or 64) is each class's weight; every "how many hands" in the project is a
  sum of multiplicities.
- `get_representative_cards` turns a name into a legal hand with suits ♠ ♥ ♦, and doubles as a
  normaliser for other spellings.
- `generate_all_canonical_hands` returns the 455 in multiset order, which is also the key order of
  `winrates.json`.
- Weak spots: the inconsistent id format (a public contract now), the special case written twice,
  no duplicate check, missing `<=`/`>=`, and three unused imports.

**Next:** [04 — The generator and `winrates.json`](04-generator.md)
