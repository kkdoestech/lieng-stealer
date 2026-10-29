# Lesson 03 — Canonical hands: 22,100 → 455

> **Goal:** understand why suits can be thrown away, how `hands.py` names each of the 455 rank
> patterns, how many real hands each name stands for, and why those names are a little
> inconsistent (and how the duplicated code behind them was cleaned up).
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
| 2 | [hands.py:31-34](../backend/src/hands.py#L31-L34) | `TOTAL_COMBINATIONS` and `OPPONENT_COMBINATIONS`: 22,100 and 18,424, computed once. |
| 3 | [hands.py:81-118](../backend/src/hands.py#L81-L118) | `_canonical_ranks` and `get_canonical_id`: validate, order, two special cases, join. |
| 4 | [hands.py:121-133](../backend/src/hands.py#L121-L133) | `_compute_multiplicity`: 4, 24 or 64. |
| 5 | [hands.py:136-158](../backend/src/hands.py#L136-L158) | `get_representative_cards`: from a name back to three cards. |
| 6 | [hands.py:161-184](../backend/src/hands.py#L161-L184) | `to_canonical`: id + score + ranks + multiplicity, from one ordering helper. |
| 7 | [hands.py:187-210](../backend/src/hands.py#L187-L210) | `generate_all_canonical_hands`: the 455, via `combinations_with_replacement`. |
| 8 | [hands.py:37-78](../backend/src/hands.py#L37-L78) | `CanonicalHand`: `@total_ordering`, strength-based `==` and a matching hash. |
| 9 | [test_hands.py](../backend/tests/test_hands.py) | Eight tests: 455, 22,100, category counts, suit invariance, round trip, and three safety tests. |

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

The two sizes every later module needs are defined here, once:

📍 [`backend/src/hands.py:31-34`](../backend/src/hands.py#L31-L34)
```python
# Size of the state space: every 3-card hand from 52 cards, and the opponent hands left once
# yours is dealt. Computed rather than typed, so no module carries its own copy of 22100 / 18424.
TOTAL_COMBINATIONS: Final[int] = math.comb(52, 3)
OPPONENT_COMBINATIONS: Final[int] = math.comb(52 - 3, 3)
```

Until October 2026 the numbers 22,100 and 18,424 were typed out in the generator, the range finder
and the calling-range model (lesson 04, weak spot 2). Now the generator, `calling_range.py`,
`range_finder.py`, the CLI and the API import them from here, and
[test_hands.py:127-131](../backend/tests/test_hands.py#L127-L131) checks both against `math.comb`.

### 2. `get_canonical_id`: a name for a rank pattern

The ordering rule lives in one small helper:

📍 [`backend/src/hands.py:81-92`](../backend/src/hands.py#L81-L92)
```python
def _canonical_ranks(cards: Sequence[Card]) -> tuple[Rank, Rank, Rank]:
    """Return the three ranks in canonical-ID order.

    Ranks are listed in descending order, except the two straights that contain an Ace, which
    are written the way players say them: A-2-3 (lowest Liêng) and Q-K-A (highest Liêng).
    """
    low, mid, high = sorted(c.rank for c in cards)
    if (low, mid, high) == (Rank.TWO, Rank.THREE, Rank.ACE):
        return (Rank.ACE, Rank.TWO, Rank.THREE)
    if (low, mid, high) == (Rank.QUEEN, Rank.KING, Rank.ACE):
        return (Rank.QUEEN, Rank.KING, Rank.ACE)
    return (high, mid, low)
```

and `get_canonical_id` validates, then joins the helper's ranks:

📍 [`backend/src/hands.py:114-118`](../backend/src/hands.py#L114-L118)
```python
    if len(cards) != 3:
        raise InvalidHandSizeError(f"Expected 3 cards to determine canonical ID, got {len(cards)}.")
    if len(set(cards)) != 3:
        raise DuplicateCardError("A Liêng hand cannot contain duplicate cards.")
    return "-".join(rank.short_name for rank in _canonical_ranks(cards))
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

You can see the two spellings side by side in one API response. The web page has a preset for
`Js Qh Kd` ([App.jsx:20](../frontend/src/App.jsx#L20)) labelled "Liêng J-Q-K"
([i18n.js:29](../frontend/src/i18n.js#L29)); for that hand, `/api/solve` returns
`"score_name": "Liêng J-Q-K"` (from `evaluator.py`'s names) and `"canonical_id": "K-Q-J"` (from
here).

### 3. `_compute_multiplicity`: 4, 24 or 64

📍 [`backend/src/hands.py:121-133`](../backend/src/hands.py#L121-L133)
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

📍 [`backend/src/hands.py:151-158`](../backend/src/hands.py#L151-L158)
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
([generator.py:57](../backend/src/generator.py#L57)). It is deliberately lenient: it splits like
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

📍 [`backend/src/hands.py:170-184`](../backend/src/hands.py#L170-L184)
```python
    if len(cards) != 3:
        raise InvalidHandSizeError(f"Expected 3 cards, got {len(cards)}.")

    cid = get_canonical_id(cards)
    score = evaluate_hand(cards)
    ranks_tuple = _canonical_ranks(cards)

    mult = _compute_multiplicity((cards[0].rank, cards[1].rank, cards[2].rank))
    return CanonicalHand(
        canonical_id=cid,
        ranks=ranks_tuple,
        multiplicity=mult,
        category=score.category,
        score=score,
    )
```

It bundles the id, the full `HandScore` (lesson 02), the ranks in the same order as the id, and the
multiplicity into one frozen `CanonicalHand`. Both the id and the `ranks` tuple come from
`_canonical_ranks`, so they can't disagree: `A-2-3` has ranks `(ACE, TWO, THREE)`, while `K-Q-J`
has `(KING, QUEEN, JACK)`. Until October 2026 the A-2-3/Q-K-A decision was written out twice, once
in each function (weak spot 2). The API and CLI call this on the player's hand
([app.py:313](../backend/app.py#L313), [cli.py:164](../backend/src/cli.py#L164)), and the API then
looks the stats up by the id it returns ([app.py:314](../backend/app.py#L314)), so the id is
computed once per request. (Before the API refactor it was computed twice: once by
`db.get_by_cards`, once here.)

### 6. `generate_all_canonical_hands`: the 455

📍 [`backend/src/hands.py:196-210`](../backend/src/hands.py#L196-L210)
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
ascending triple: `(2, 2, 2)`, `(2, 2, 3)`, …, `(A, A, A)`. It took 2.88 ms to build all 455. The
list comes out in that **multiset order**, not strength order: it starts
`2-2-2, 3-2-2, 4-2-2, 5-2-2, 6-2-2, 7-2-2` and ends `A-A-Q, K-K-K, A-K-K, A-A-K, A-A-A`. Note that
5-2-2 (9 points) is followed by 6-2-2 (0 points). That is also the key order of `winrates.json`.
Modules that need strength order sort by `score_tuple` themselves (lesson 06).

The generator, the calling-range model and the range finder all call this function at start-up
([generator.py:142](../backend/src/generator.py#L142),
[calling_range.py:61](../backend/src/calling_range.py#L61),
[range_finder.py:51](../backend/src/range_finder.py#L51)).

### 7. `CanonicalHand` and its comparisons

`CanonicalHand` ([hands.py:37-53](../backend/src/hands.py#L37-L53)) is a frozen dataclass with five
fields, decorated with `@total_ordering`. It defines `__lt__`, `__gt__` and `__eq__`, all comparing
`score`, a `__hash__` that agrees with them ([hands.py:55-72](../backend/src/hands.py#L55-L72)), and a
short `__repr__` such as `CanonicalHand('A-2-3', cat=LIENG, mult=64)`. So `max(hands)` is A-A-A and
`min(hands)` is 4-3-3, and `<=`/`>=` work too:

📍 [`backend/src/hands.py:65-72`](../backend/src/hands.py#L65-L72)
```python
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CanonicalHand):
            return NotImplemented
        return self.score == other.score

    def __hash__(self) -> int:
        # Must agree with __eq__, which compares strength.
        return hash(self.score)
```

`@total_ordering` (concept box below) supplies the missing `__le__` and `__ge__` from `__lt__` and
`__eq__`. Until October 2026 it wasn't there, and
`hands["Q-K-A"] <= hands["A-A-A"]` raised
`TypeError: '<=' not supported between instances of 'CanonicalHand' and 'CanonicalHand'`.

`__eq__` follows the same rule as `Hand` in lesson 02: equal means equally strong, and the hash is
built from the same thing (`hash(self.score)`, which is `HandScore`'s hash of its `score_tuple`).
Since each of the 455 classes has a unique score, "equally strong" and "the same class" coincide
here, and the calling-range model checks that fact at start-up (lesson 06).

### 8. What the tests pin

[test_hands.py](../backend/tests/test_hands.py) has eight tests. Five check the combinatorics:
exactly 455 unique ids ([:31](../backend/tests/test_hands.py#L31)); multiplicities summing to
22,100 with counts 13/156/286 ([:40](../backend/tests/test_hands.py#L40)); category counts
13/12/6/424 and the six Đĩ shapes ([:52](../backend/tests/test_hands.py#L52)); suit invariance,
including the spellings `9-8-7`, `Q-K-A` and `A-2-3` ([:80](../backend/tests/test_hands.py#L80));
and the round trip id → representative cards → id for all 455
([:102](../backend/tests/test_hands.py#L102)). Three in `TestCanonicalHandSafety` pin the fixes:
duplicates are rejected ([:115](../backend/tests/test_hands.py#L115)), all four comparisons work
([:121](../backend/tests/test_hands.py#L121)), and the two constants equal `math.comb`
([:127](../backend/tests/test_hands.py#L127)). Elsewhere,
[test_calling_range.py:37](../backend/tests/test_calling_range.py#L37) pins that `"3-K-Q"` is *not*
a valid id.

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
other three. `CanonicalHand` defines `__lt__`, `__gt__` and `__eq__` itself, and the decorator,
placed above `@dataclass`, adds `__le__` and `__ge__` (exercise 5 removes it). It only fills in
methods the class doesn't already define, and the derived ones are a little slower than hand-written
ones, which doesn't matter for 455 objects.

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

Six weak spots were listed here when the course was written. Commit `bba5e63` ("fix(core)", October
2026) fixed four; the id format itself and a little repeated work remain.

1. **An inconsistent id format.** Descending everywhere except `A-2-3` and `Q-K-A`
   ([hands.py:88-91](../backend/src/hands.py#L88-L91)). `J-Q-K` and `A-K-Q` are not keys, while the
   same hands are *named* "Liêng J-Q-K" and "Liêng Q-K-A" by the evaluator. Anyone calling
   `db.get("J-Q-K")` gets an `UnknownHandError` (lesson 01). Changing the format is not a local
   fix, and the database validation added in October 2026 makes that louder: removing the special
   case makes the committed `winrates.json` fail to load ("2 missing (e.g. ['A-3-2', 'A-K-Q']), 2
   unknown"), and after regenerating it 10 tests still fail, because tests spell `"Q-K-A"` and
   `"A-2-3"` out (exercise 7). *Fix:* keep the stored format and normalise lookups instead, with
   `get_canonical_id(get_representative_cards(text))`.
2. ✅ **Fixed: the special case was written twice.** `get_canonical_id` built the id string and
   `to_canonical` rebuilt the rank tuple, each with its own A-2-3/Q-K-A test, so a change to one
   alone would have made a class's `id` and `ranks` disagree. Now both use `_canonical_ranks`
   ([hands.py:81-92](../backend/src/hands.py#L81-L92); used at [:118](../backend/src/hands.py#L118)
   and [:175](../backend/src/hands.py#L175)). The suit-invariance and round-trip tests
   ([test_hands.py:80](../backend/tests/test_hands.py#L80),
   [:102](../backend/tests/test_hands.py#L102)) pin that the ids didn't change.
3. ✅ **Fixed: no duplicate check in `get_canonical_id`.** It checked only the count, so
   `db.get_by_cards([As, As, Kd])` quietly returned A-A-K's stats (equity 0.2806). Now it raises
   `DuplicateCardError` ([hands.py:116-117](../backend/src/hands.py#L116-L117)), pinned by
   `test_duplicate_cards_are_rejected` ([test_hands.py:115-119](../backend/tests/test_hands.py#L115-L119)).
   Exercise 4 reopens the hole.
4. ✅ **Fixed: `CanonicalHand` had no `<=` or `>=`.** Now it is decorated with `@total_ordering`
   ([hands.py:37](../backend/src/hands.py#L37)) and has an explicit `__hash__` that agrees with its
   strength-based `__eq__` ([hands.py:70-72](../backend/src/hands.py#L70-L72)). Pinned by
   `test_canonical_hands_support_all_comparisons`
   ([test_hands.py:121-125](../backend/tests/test_hands.py#L121-L125)).
5. ✅ **Fixed: unused imports.** `Final`, `Hand` and `InvalidCardError` were imported and never used.
   `ruff` now runs with the `F` (pyflakes) rules in CI ([pyproject.toml](../backend/pyproject.toml)),
   which reports any unused import as `F401`; `Final` is now used by the two constants.
6. **A little repeated work per request.** `to_canonical` checks the count twice (itself and in
   `get_canonical_id`) and sorts the same three ranks three times: twice through `_canonical_ranks`
   (once via `get_canonical_id`) and once in `evaluate_hand`'s sorting network. It costs about
   1.5 µs per call (4.9 µs against 3.5 µs when the id is joined from the rank tuple it already has,
   exercise 6), so it is tidiness, not speed.

---

## 🧪 Try it

Run from `backend/` with the virtual environment active.

```bash
python -m pytest tests/test_hands.py -q
```

Expected output (the timing varies):

```
........                                                                 [100%]
8 passed in 0.04s
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

See the inconsistent format, and the duplicate check that now stops a bad lookup:

```bash
python -c '
from src.evaluator import Card, Hand
from src.hands import get_canonical_id
from src.db import WinRateDB
db = WinRateDB("data/winrates.json")
print(get_canonical_id(Hand.from_str("Js Qh Kd").cards), get_canonical_id(Hand.from_str("Qs Kh Ad").cards))
print([(k, k in db) for k in ("K-Q-J", "J-Q-K", "Q-K-A", "A-K-Q")])
dup = [Card.from_str("As"), Card.from_str("As"), Card.from_str("Kd")]
try:
    db.get_by_cards(dup)
except Exception as err:
    print(type(err).__name__, err)
'
```

Expected output:

```
K-Q-J Q-K-A
[('K-Q-J', True), ('J-Q-K', False), ('Q-K-A', True), ('A-K-Q', False)]
DuplicateCardError A Liêng hand cannot contain duplicate cards.
```

Before the October 2026 fixes the last line was `A-A-K 0.2806`: the duplicate hand got A-A-K's
equity.

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

**🟢 3. Predict the error.** What does `db.get_by_cards([As, As, Kd])` do now, which line raises,
and what would the API answer if such a hand ever reached it?

<details><summary>Solution</summary>

It raises `DuplicateCardError: A Liêng hand cannot contain duplicate cards.` from
`get_canonical_id` ([hands.py:116-117](../backend/src/hands.py#L116-L117)), which `get_by_cards`
calls before the dict lookup ([db.py:147-148](../backend/src/db.py#L147-L148)). `DuplicateCardError`
is an `InvalidHandSizeError`, so the API's handler would answer 400 with `"code": "invalid_hand"`
(lesson 01). In practice the API and CLI build a `Hand` first, whose `__post_init__` already rejects
duplicates (lesson 02); the check in `hands.py` protects every other caller.
</details>

**🟡 4. Reopen the duplicate hole.** Delete the duplicate check
([hands.py:116-117](../backend/src/hands.py#L116-L117)). Predict which test fails and what the probe
from 🧪 Try it prints, then run both and `python -m pytest -q`.

<details><summary>Solution</summary>

`1 failed, 171 passed`: only `test_duplicate_cards_are_rejected`
([test_hands.py:115-119](../backend/tests/test_hands.py#L115-L119)). The probe's last line goes back
to `0.2806` (it prints the equity without raising), A-A-K's stats for an impossible hand. The other
171 tests pass because every other path builds a `Hand` first: the hole is latent, which is exactly
why it needs its own test. Undo with `git checkout -- backend/src/hands.py`.
</details>

**🟡 5. Remove `@total_ordering`.** Delete the decorator ([hands.py:37](../backend/src/hands.py#L37)).
Predict which comparisons still work on two `CanonicalHand`s and which test fails, then run
`python -m pytest -q`.

<details><summary>Solution</summary>

`<`, `>`, `==`, `min()`, `max()` and `sorted()` still work: they only need the methods the class
writes itself. `<=` and `>=` raise
`TypeError: '<=' not supported between instances of 'CanonicalHand' and 'CanonicalHand'`.
`1 failed, 171 passed`: `test_canonical_hands_support_all_comparisons`
([test_hands.py:121-125](../backend/tests/test_hands.py#L121-L125)). Undo with
`git checkout -- backend/src/hands.py`.
</details>

**🟡 6. Sort once less (weak spot 6).** In `to_canonical`, replace `cid = get_canonical_id(cards)`
with an id joined from `ranks_tuple`, so the ranks are ordered only once. Which check does
`get_canonical_id` do that you must not lose? Time it before and after with
`python -m timeit -s "from src.hands import to_canonical; from src.evaluator import Hand; c = Hand.from_str('Js Qh Kd').cards" "to_canonical(c)"`,
then run `python -m pytest -q`.

<details><summary>Solution sketch</summary>

```python
    score = evaluate_hand(cards)  # also rejects duplicate cards
    ranks_tuple = _canonical_ranks(cards)
    cid = "-".join(rank.short_name for rank in ranks_tuple)
```

`get_canonical_id` rejects duplicates; `evaluate_hand` does too (`DuplicateCardError`, lesson 02), so
calling it first keeps `to_canonical([As, As, Kd])` an error. About 4.9 µs before, 3.5 µs after;
`172 passed`, and the suit-invariance and round-trip tests prove the ids didn't change. The cost is
that `to_canonical` now repeats the join instead of calling the one function that defines an id;
a helper `_join(ranks)` used by both would remove that too. Undo with
`git checkout -- backend/src/hands.py`.
</details>

**🔴 7. Measure the cost of one id format.** Work on a **copy** of `backend/` (the generator writes
next to `src/`, so a copy keeps your real data safe):
`cp -r backend /tmp/lieng-copy && cd /tmp/lieng-copy`, then activate the same virtual environment.
First, delete the two special cases at [hands.py:88-91](../backend/src/hands.py#L88-L91) and run
`python -m pytest -q`. Then regenerate the data with `python -m src.generator --workers 1` (about
10 s) and run the tests again. Finally, back in the real repo, implement the cheaper alternative: a
`normalise_canonical_id(text)` in `hands.py` that `WinRateDB.get` tries when a key is missing.

<details><summary>Solution</summary>

Without the special case, pytest stops at collection (`Interrupted: 2 errors during collection`):
`WinRateDB` now validates the file and refuses it, `'data/winrates.json' must contain exactly the
455 canonical hands: 2 missing (e.g. ['A-3-2', 'A-K-Q']), 2 unknown (e.g. ['A-2-3', 'Q-K-A'])`.
(With `--continue-on-collection-errors`: `17 failed, 90 passed, 15 errors`.) After regenerating:
`10 failed, 162 passed`, the tests that spell `"Q-K-A"` or `"A-2-3"` out (in `test_api.py`,
`test_db.py`, `test_generator.py` and `test_hands.py`). An id format is a public contract: it is in
the data file, the API and the tests.

The alternative:

```python
def normalise_canonical_id(text: str) -> str:
    """Return the stored spelling of any rank-order spelling ('J-Q-K' -> 'K-Q-J')."""
    try:
        return get_canonical_id(get_representative_cards(text))
    except LiengError:
        return text
```

With `db.get` retrying through it, `db.get("J-Q-K")` returns 0.995, `"A-K-Q"` and `"q k a"` return
0.9969, `"3-2-A"` returns 0.962, and `"INVALID_KEY"` still raises `UnknownHandError`. One test fails,
`1 failed, 171 passed`: `test_unknown_id_is_a_project_error_and_a_key_error`
([test_db.py:146-151](../backend/tests/test_db.py#L146-L151)) uses `"J-Q-K"` as its example of an
unknown id, which is now found. That is a decision, not a bug: change its example to a truly invalid
id such as `"Z-Z-Z"`. Undo with `git checkout -- backend/src/hands.py backend/src/db.py`, and
delete the copy.
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
4. `A-2-3` and `Q-K-A`. `J-Q-K` is stored as `K-Q-J`, so `db.get("J-Q-K")` raises
   `UnknownHandError` (which is also a `KeyError`).
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
- `TOTAL_COMBINATIONS` (22,100) and `OPPONENT_COMBINATIONS` (18,424) are computed here, once, and
  imported everywhere else.
- Fixed: one ordering helper instead of two copies of the special case, a duplicate check,
  `@total_ordering`, no unused imports. Still open: the inconsistent id format (a public contract
  now) and a little repeated sorting in `to_canonical`.

**Next:** [04 — The generator and `winrates.json`](04-generator.md)
