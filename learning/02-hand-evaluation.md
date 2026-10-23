# Lesson 02 — Hand evaluation

> **Goal:** understand how `evaluate_hand` turns any three cards into one comparable `HandScore`,
> why a single `>` settles any showdown, exactly where each edge case (A-2-3, Q-K-A, K-A-2, J-Q-K,
> A-J-J) is decided, and what is fragile about the `Hand` class.
> **Files:** [`backend/src/evaluator.py:174-449`](../backend/src/evaluator.py#L174-L449),
> [`backend/tests/test_evaluator.py:86-248`](../backend/tests/test_evaluator.py#L86-L248).
> **Time:** ~75 min. **Before this:** [01 — Errors and cards](01-errors-and-cards.md).

---

## Where this fits

```
  three Cards (lesson 01)
        │
        ▼
  ┌──────────────────────────────────────────────┐
  │ evaluate_hand(cards) ─► HandScore             │  this lesson
  │   (category, primary, secondary, score,       │
  │    tie_breaker)  + a display name             │
  │ Hand: three validated cards, compared by score│
  └──────────────────────────────────────────────┘
        │                    │                         │
        ▼                    ▼                         ▼
  hands.py (lesson 03)  generator.py (lesson 04)   calling_range.py (lesson 06)
  score of each of      18,424 comparisons per     sorts the 455 classes
  the 455 classes       class with > and ==        by score_tuple
```

This is where the rules of Liêng live. Everything above it trusts that `a > b` on two scores means
"a wins the showdown". If this file is wrong, every equity in `winrates.json`, every EV and every
recommendation is wrong with it, which is why it has the most tests of any domain module (18).

---

## Reading order

| # | Location | What to look for |
|---|----------|------------------|
| 1 | [evaluator.py:174-190](../backend/src/evaluator.py#L174-L190) | `HandCategory`: Điểm 1 … Sáp 4. |
| 2 | [evaluator.py:193-223](../backend/src/evaluator.py#L193-L223) | The 12 Liêng sequences and their names. Which key is A-2-3? |
| 3 | [evaluator.py:226-282](../backend/src/evaluator.py#L226-L282) | `HandScore`, `score_tuple`, five comparison methods. |
| 4 | [evaluator.py:290-374](../backend/src/evaluator.py#L290-L374) | `evaluate_hand`: validate, sort, then four checks in order. |
| 5 | [evaluator.py:377-449](../backend/src/evaluator.py#L377-L449) | `Hand`: parsing, `score`, comparisons, and the `__eq__` at the end. |
| 6 | [test_evaluator.py:86-248](../backend/tests/test_evaluator.py#L86-L248) | The rule tests: Sáp order, 12 Liêng, K-A-2, Đĩ, mod 10. |

---

## Walkthrough

### 1. The idea: one tuple per hand

Instead of writing "if both are Sáp, compare ranks; if one is Liêng and the other Đĩ, …" for every
pair of categories, the evaluator turns each hand into a tuple and lets Python compare tuples:

📍 [`backend/src/evaluator.py:245-254`](../backend/src/evaluator.py#L245-L254)
```python
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

Python compares tuples left to right and stops at the first difference (see the concept box). The
category comes first, so any Sáp `(4, …)` beats any Liêng `(3, …)` without looking further. Real
values from the code:

| Hand | Name | `score_tuple` |
|------|------|---------------|
| As Ah Ad | Sáp A | `(4, 14, 0, 0, (14, 14, 14))` |
| 2s 2h 2d | Sáp 2 | `(4, 2, 0, 0, (2, 2, 2))` |
| Qs Kh Ad | Liêng Q-K-A | `(3, 12, 0, 0, (14, 13, 12))` |
| Js Qh Kd | Liêng J-Q-K | `(3, 11, 0, 0, (13, 12, 11))` |
| As 2h 3d | Liêng A-2-3 | `(3, 1, 0, 0, (14, 3, 2))` |
| Ks Kh Qd | Đĩ | `(2, 13, 13, 0, (13, 13, 12))` |
| Ks Qh Qd | Đĩ | `(2, 13, 12, 0, (13, 12, 12))` |
| As 3h 5d | 9 điểm | `(1, 9, 14, 9, (14, 5, 3))` |
| Ks 10h 9d | 9 điểm | `(1, 9, 13, 9, (13, 10, 9))` |
| Ks Ah 2d | 3 điểm | `(1, 3, 14, 3, (14, 13, 2))` |
| As Jh Jd | 1 điểm | `(1, 1, 14, 1, (14, 11, 11))` |
| 10s 10h Kd | 0 điểm (Bù) | `(1, 0, 13, 0, (13, 10, 10))` |

What each slot means depends on the category:

| Category | `primary_rank` | `secondary_rank` | `score` |
|----------|---------------|------------------|---------|
| 4 Sáp | the rank, 2–14 | 0 | 0 |
| 3 Liêng | sequence strength, 1–12 | 0 | 0 |
| 2 Đĩ | highest card | middle card | 0 |
| 1 Điểm | points, 0–9 | highest card (Ace = 14) | points again |

`tie_breaker` is always the three ranks in descending order. Because it holds *all* the ranks, two
hands can only tie if they have the same three ranks. Evaluating all 22,100 hands gives exactly
**455** distinct tuples, one per rank pattern. Lesson 03 builds on that, and lesson 06 depends on
it.

### 2. `HandCategory` and the Liêng table

`HandCategory` ([evaluator.py:174-190](../backend/src/evaluator.py#L174-L190)) is an `IntEnum`:
`DIEM = 1`, `DI = 2`, `LIENG = 3`, `SAP = 4`, plus a `display_name` with the Vietnamese spelling.
Higher number, stronger category. (EXPERIMENT.md numbers them the other way round; lesson 00.)

Straights are not computed, they are **looked up**:

📍 [`backend/src/evaluator.py:195-208`](../backend/src/evaluator.py#L195-L208)
```python
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
```

The keys are rank values sorted **ascending**. The Ace is 14 everywhere in this codebase, so A-2-3
sorts to `(2, 3, 14)`, and the table simply says "that pattern is a straight of strength 1". There
is no special Ace-low logic anywhere else. K-A-2 sorts to `(2, 13, 14)`, which is not a key, so it
is not a straight. Twelve explicit entries are easier to check than a clever rule for "consecutive,
with the Ace at either end but not in the middle".

The strength (1–12) becomes `primary_rank`, so Liêng compare by sequence, not by their top card:
A-2-3 has the highest card of all (an Ace) and is still the weakest straight.

### 3. `evaluate_hand`, step 1: validate and sort

📍 [`backend/src/evaluator.py:310-325`](../backend/src/evaluator.py#L310-L325)
```python
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

Lines 318-323 are a **sorting network**: three fixed compare-and-swap steps that sort any three
numbers. The first two steps push the largest value into `r3`; the third orders the remaining two.
Every permutation of `(14, 3, 9)` comes out as `(3, 9, 14)`. It avoids building a list and calling
`sorted()`, which matters a little in a function the generator calls 8.4 million times.

After this block, `r1 <= r2 <= r3`, and every check below relies on that.

### 4. Steps 2 and 3: Sáp, then Liêng

📍 [`backend/src/evaluator.py:327-349`](../backend/src/evaluator.py#L327-L349)
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

Because the ranks are sorted, "all three equal" is just `r1 == r3`. Each check **returns**, so the
order of the checks is the order of the categories: a hand that is a Sáp never reaches the Liêng
test, and one that is a Liêng never reaches the Đĩ test.

### 5. Step 4: Đĩ

📍 [`backend/src/evaluator.py:351-362`](../backend/src/evaluator.py#L351-L362)
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
```

With sorted ranks, two comparisons cover all three cards: the smallest is at least J (11) and the
largest at most K (13). The order of the checks does the rest of the work for free:

- J-J-J, Q-Q-Q, K-K-K already returned as Sáp.
- J-Q-K already returned as Liêng (strength 11).
- A-J-J has `r3 = 14`, so `r3 <= 13` fails. The Ace is not a face card.

That leaves exactly the 6 Đĩ shapes AGENTS.md lists: J-J-Q, J-J-K, J-Q-Q, J-K-K, Q-Q-K, Q-K-K.

### 6. Step 5: Điểm, everything else

📍 [`backend/src/evaluator.py:364-374`](../backend/src/evaluator.py#L364-L374)
```python
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

Points use `Card.point_value` (Ace 1, 10–K 0, lesson 01). The tie-break uses the **rank**
`r3`, where the Ace is 14. So the Ace counts 1 for points and 14 for "highest card".

### 7. Where each edge case is decided

| Case | Result | Decided at |
|------|--------|------------|
| A-2-3 is the weakest Liêng | strength 1 | the key `(2, 3, 14)` at [evaluator.py:196](../backend/src/evaluator.py#L196) |
| Q-K-A is the strongest Liêng | strength 12 | [evaluator.py:207](../backend/src/evaluator.py#L207) |
| K-A-2 is not a Liêng | 3 points | `(2, 13, 14)` is missing from the table, so it falls to [evaluator.py:365](../backend/src/evaluator.py#L365) |
| J-Q-K is Liêng, not Đĩ | strength 11 | [evaluator.py:206](../backend/src/evaluator.py#L206), checked before Đĩ |
| J-J-J is Sáp, not Đĩ | Sáp J | [evaluator.py:328](../backend/src/evaluator.py#L328), checked first |
| A-J-J is not Đĩ | 1 point | `r3 <= 13` at [evaluator.py:354](../backend/src/evaluator.py#L354) |
| Đĩ beats 9 points | category 2 > 1 | the first slot of `score_tuple` |
| 19 points is 9 points | 9 | `% 10` at [evaluator.py:365](../backend/src/evaluator.py#L365) |

Each row has a test: [test_evaluator.py:112](../backend/tests/test_evaluator.py#L112) (all 12
Liêng in order), [:141](../backend/tests/test_evaluator.py#L141) (K-A-2),
[:167](../backend/tests/test_evaluator.py#L167) (J-J-J and J-Q-K),
[:177](../backend/tests/test_evaluator.py#L177) (A-J-J), [:187](../backend/tests/test_evaluator.py#L187)
(Đĩ beats 9 points) and [:219](../backend/tests/test_evaluator.py#L219) (mod 10).

### 8. House rules for ties

Real Liêng tables disagree on how to break ties *inside* a category. This code picks one set of
rules, encoded in the `secondary_rank` and `tie_breaker` slots. Real comparisons:

| Hand A | Hand B | Result | Why |
|--------|--------|--------|-----|
| Ks Kh Qd (Đĩ) | Kc Qs Qh (Đĩ) | A wins | same top card, middle K > Q |
| Ks Kh Jd (Đĩ) | Kc Kd Qs (Đĩ) | B wins | top and middle equal, then the last card |
| As 3h 5d (9 điểm) | Kc 10s 9h (9 điểm) | A wins | highest card A (14) > K (13) |
| As Kh 8d (9 điểm) | Kc Qs 9h (9 điểm) | A wins | same |
| 9s 8h 2d (9 điểm) | Kc 10s 9h (9 điểm) | B wins | K beats 9, even though 9-8-2 "has more" |
| Js Qh Kd | Jc Qd Kh | tie | same ranks; suits never count |

AGENTS.md says Đĩ hands are "considered equal (Tie) or compared by highest face card … based on
game configuration" ([AGENTS.md:61](../AGENTS.md#L61)). The code always compares them, there is no
configuration, and **no test pins any row of this table** except the last kind (weak spot 4).

### 9. `HandScore`'s comparison methods

`HandScore` is declared `@dataclass(frozen=True, order=False)`
([evaluator.py:226](../backend/src/evaluator.py#L226)) and then defines `__lt__`, `__le__`,
`__gt__`, `__ge__` and `__eq__` by hand ([evaluator.py:256-279](../backend/src/evaluator.py#L256-L279)),
each the same three lines: return `NotImplemented` for a non-`HandScore`, otherwise compare
`score_tuple`s. Writing them out makes the comparison key explicit and keeps the `name` field out
of it. (`HandScore`'s own hash, generated from all six fields, happens to be consistent with this
`__eq__`: every field is a function of the three ranks.)

`calculate_points` ([evaluator.py:285-287](../backend/src/evaluator.py#L285-L287)) is a public
helper that computes the same `% 10` sum; only a test calls it.

### 10. `Hand`: three validated cards

📍 [`backend/src/evaluator.py:377-386`](../backend/src/evaluator.py#L377-L386)
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
```

`__post_init__` runs right after the generated `__init__`, so an invalid `Hand` can never exist.
`Hand.from_str` ([evaluator.py:394-413](../backend/src/evaluator.py#L394-L413)) splits on spaces,
commas or hyphens with `re.split(r"[\s,\-]+", …)` ([evaluator.py:407](../backend/src/evaluator.py#L407)):
`"As,Kh,Qd"`, `"As-Kh-Qd"` and `"  As   Kh  Qd "` all parse to `As Kh Qd`; `"AsKhQd"` is one token
and fails with `found 1`. This is the entry point for the CLI ([cli.py:130](../backend/src/cli.py#L130))
and the API ([app.py:173](../backend/app.py#L173)).

The strength is a property that evaluates the cards **on every access**:

📍 [`backend/src/evaluator.py:415-418`](../backend/src/evaluator.py#L415-L418)
```python
    @property
    def score(self) -> HandScore:
        """Evaluate and return the HandScore."""
        return evaluate_hand(self.cards)
```

All five comparison operators delegate to it, so `hand_a > hand_b` reads exactly like a rule:
`Hand.from_str("2s 2h 2d") > Hand.from_str("Qs Kh Ad")` is "Sáp beats Liêng". The last of them is
the problem of this lesson:

📍 [`backend/src/evaluator.py:440-443`](../backend/src/evaluator.py#L440-L443)
```python
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Hand):
            return NotImplemented
        return self.score == other.score
```

Two hands are "equal" when they are equally *strong*. But the class is a frozen dataclass, which
generates `__hash__` from the *field*, the `cards` tuple. Equal hands get different hashes:

```bash
python -c '
from src.evaluator import Hand
a = Hand.from_str("As Kh Qd")
b = Hand.from_str("Ac Kd Qh")      # same ranks, other suits
c = Hand.from_str("Kh As Qd")      # the SAME three cards as a, dealt in another order
print("a == b:", a == b, "| hash equal:", hash(a) == hash(b))
print("a == c:", a == c, "| hash equal:", hash(a) == hash(c))
print("len({a, b, c}):", len({a, b, c}))
seen = {a: "first"}
print("b in seen:", b in seen, "| c in seen:", c in seen, "| c in [a]:", c in [a])
'
```

Real output:

```
a == b: True | hash equal: False
a == c: True | hash equal: False
len({a, b, c}): 3
b in seen: False | c in seen: False | c in [a]: True
```

A set of three "equal" hands has three members. A dict keyed by `a` can't find `c`, which is the
same three cards, while a *list* finds it (lists use `==`, dicts use the hash first). Weak spot 1
has the fix.

---

## 💡 Concept: tuple comparison

Python compares tuples element by element, left to right, and stops at the first difference, like
words in a dictionary: `(4, 2) > (3, 14)` is decided by `4 > 3` alone; `(1, 9, 14) > (1, 9, 13)`
by the third element. A nested tuple is compared the same way when its turn comes. That is the
whole trick of this file: put the most important thing first, and one `>` settles any showdown.

## 💡 Concept: the hash/eq contract

Sets and dicts find a key in two steps: compute `hash(key)` to pick a bucket, then use `==` inside
the bucket. That only works if **`a == b` implies `hash(a) == hash(b)`**. When a class overrides
`__eq__`, it must make `__hash__` agree, or set `__hash__ = None` to become unhashable. A frozen
dataclass generates `__hash__` from its fields; a hand-written `__eq__` that compares something
else silently breaks the contract, and no error is ever raised.

## 💡 Concept: `NotImplemented`

Returning `NotImplemented` (not raising) from `__lt__` says "I don't know how to compare with that
type". Python then tries the other operand's method and, if that fails too, raises a clear
`TypeError`. `Hand.from_str("As Kh Qd") < 5` is a `TypeError`, not `False`.

---

## Design decisions

- **A tuple as the universal key.** Every rule becomes "where does this hand sit in a total order",
  and Python's tuple comparison does the rest. The same key sorts the 455 classes in lesson 06.
- **A table for straights.** Twelve explicit entries make A-2-3 and the K-A-2 exclusion visible at
  a glance, instead of hiding them in arithmetic.
- **Sort once, then check in category order with early returns.** The order of the `if`s *is* the
  priority of the categories, so J-Q-K and J-J-J can't be misclassified as Đĩ.
- **Ranks in the tie-breaker.** Including all three ranks makes the order total over rank patterns
  (455 distinct values), which later modules rely on. The cost is a house rule for every tie.
- **`Hand` stores cards, not a score.** It stays a tiny value object; the score is derived. The
  cost is re-evaluation on every access (weak spot 2).
- **`HandScore` carries a display name.** The CLI and API print `str(hand.score)` ("Liêng Q-K-A")
  without a second lookup.

---

## ⚠️ Weak spots

1. **`Hand.__eq__` and `__hash__` disagree.** [evaluator.py:440-443](../backend/src/evaluator.py#L440-L443)
   compares strength; the dataclass hash ([evaluator.py:377](../backend/src/evaluator.py#L377)) uses
   the ordered `cards` tuple. Section 10 shows equal hands with different hashes, and the same three
   cards in another order counted twice in a set. It also contradicts AGENTS.md, which wants hands
   usable as dict keys ([AGENTS.md:25](../AGENTS.md#L25)). No production code hashes a `Hand` today,
   so the bug is latent. *Fix:* decide what "equal" means. **Same cards:** `__eq__` compares
   `frozenset(self.cards)` and `__hash__` returns `hash(frozenset(self.cards))`; compare strength
   with `a.score == b.score`. **Same strength:** keep `__eq__` and add
   `__hash__` returning `hash(self.score.score_tuple)`. Both keep the 93 tests green (exercise 4).
2. **`score` is not cached.** [evaluator.py:415-418](../backend/src/evaluator.py#L415-L418)
   re-runs `evaluate_hand` on each access, and every comparison reads it twice: `a > b` on two
   `Hand`s took 6.74 µs, comparing their `HandScore`s 475 ns. *Fix:* `functools.cached_property`
   works on a frozen dataclass and brought `a > b` to 595 ns (exercise 5).
3. **A redundant `score` field.** For Điểm it always equals `primary_rank`; for the other
   categories it is always 0 ([evaluator.py:241](../backend/src/evaluator.py#L241),
   [:252](../backend/src/evaluator.py#L252)). Removing it from `score_tuple` leaves 455 distinct
   tuples in exactly the same order, so it never decides anything. It also makes AGENTS.md's
   four-field `HandScore` ([AGENTS.md:80](../AGENTS.md#L80)) and the code's six fields harder to
   reconcile. *Fix:* drop it, or document it as display data.
4. **Tie-break house rules: untested and undocumented in the spec.** Đĩ by highest then middle card
   ([evaluator.py:357-358](../backend/src/evaluator.py#L357-L358)), Điểm by highest card with the
   Ace high ([evaluator.py:370](../backend/src/evaluator.py#L370)), then all ranks. No test compares
   two Đĩ hands or two Điểm hands with equal points. Making every Đĩ tie (AGENTS.md's other option)
   fails only one test, and only indirectly, through the calling-range cross-check (exercise 6).
   And the calling-range model needs 455 *distinct* strengths
   ([calling_range.py:8](../backend/src/calling_range.py#L8)), so real ties would break it. *Fix:*
   pin the table in section 8 with tests, and treat any change as a data change.
5. **The 1 µs budget is not met.** AGENTS.md §6 asks for under 1 µs per evaluation
   ([AGENTS.md:124](../AGENTS.md#L124)); `evaluate_hand` took 2.57–3.82 µs here, and all 22,100
   hands took 0.084 s. It doesn't matter in practice (the heavy use is offline), but nobody
   measures it. *Fix:* precompute the 455 `HandScore`s in a dict keyed by the sorted rank triple
   (exercise 7: 990 ns).
6. **Small duplications.** `calculate_points` ([evaluator.py:285-287](../backend/src/evaluator.py#L285-L287))
   and the inline sum at [:365](../backend/src/evaluator.py#L365) compute the same thing; only a
   test uses the function. `Hand(cards=[…])` with a list passes validation but makes the hand
   unhashable (`TypeError: unhashable type: 'list'`), because the type hint isn't enforced.

---

## 🧪 Try it

Run from `backend/` with the virtual environment active.

```bash
python -m pytest tests/test_evaluator.py -q
```

Expected output (the timing varies):

```
..................                                                       [100%]
18 passed in 0.02s
```

Evaluate all 22,100 hands and check the claims of sections 1 and weak spot 3:

```bash
python -c '
import itertools, time
from collections import Counter
from src.evaluator import Deck, evaluate_hand, HandCategory
t = time.perf_counter()
scores = [evaluate_hand(h) for h in itertools.combinations(Deck.standard_52(), 3)]
print(len(scores), "hands in", round(time.perf_counter() - t, 3), "s")
print(Counter(s.category.name for s in scores))
tuples = {s.score_tuple for s in scores}
print("distinct score tuples:", len(tuples))
print("same order without score field:", sorted(tuples) == sorted(tuples, key=lambda t: t[:3] + t[4:]))
print("weakest:", min(tuples), "strongest:", max(tuples))
'
```

Expected output (the time varies):

```
22100 hands in 0.084 s
Counter({'DIEM': 21136, 'LIENG': 768, 'DI': 144, 'SAP': 52})
distinct score tuples: 455
same order without score field: True
weakest: (1, 0, 4, 0, (4, 3, 3)) strongest: (4, 14, 0, 0, (14, 14, 14))
```

The weakest hand in the game is 4-3-3: 0 points, and the lowest possible top card among 0-point
hands. Run the snippet in section 10 to see the hash bug yourself.

---

## 🏋️ Exercises

Exercises marked 🟡 or 🔴 change code. Undo them afterwards with `git checkout -- <file>`.

**🟢 1. Predict the tuple.** Write down the name and `score_tuple` of `Qh Kc Jd`, `Kh Kd As`,
`Jh Js Kc`, `5h 5d 5c` and `4s 3c 3d`. Check with `Hand.from_str(s).score.score_tuple`.

<details><summary>Solution</summary>

```
Qh Kc Jd  Liêng J-Q-K   (3, 11, 0, 0, (13, 12, 11))
Kh Kd As  1 điểm        (1, 1, 14, 1, (14, 13, 13))
Jh Js Kc  Đĩ            (2, 13, 11, 0, (13, 11, 11))
5h 5d 5c  Sáp 5         (4, 5, 0, 0, (5, 5, 5))
4s 3c 3d  0 điểm (Bù)   (1, 0, 4, 0, (4, 3, 3))
```

A-K-K is a pair of face cards plus an Ace: not Đĩ (the Ace), so 1 + 0 + 0 = 1 point.
</details>

**🟢 2. Predict how far Python looks.** To decide A-2-3 vs 2-3-4, how many elements of the two
`score_tuple`s does Python compare? And for Ks Kh Jd vs Kc Kd Qs (both Đĩ)?

<details><summary>Solution</summary>

Two: `(3, 1, …)` vs `(3, 2, …)` differ at the second element. For the two Đĩ hands, `(2, 13, 13,
0, (13, 13, 11))` vs `(2, 13, 13, 0, (13, 13, 12))`: the first four are equal, so Python compares
the nested tuples, and their third element (11 vs 12) decides. The second hand wins.
</details>

**🟢 3. Predict a count.** How many of the 22,100 hands are Liêng, and why is it 12 × 64? Check
with the `Counter` in 🧪 Try it.

<details><summary>Solution</summary>

768. Each of the 12 sequences has three different ranks, and each card can be any of 4 suits:
4 × 4 × 4 = 64 combinations. Lesson 03 calls 64 the *multiplicity*. (BLOG.md's "≈ 3.26%" is wrong:
768 / 22,100 = 3.48%.)
</details>

**🟡 4. Fix the hash bug.** Replace `Hand.__eq__` with a card-identity version and add a matching
`__hash__` (weak spot 1, "same cards"). Add a test that `len({a, b, c}) == 2` for the three hands
of section 10. Check with `python -m pytest -q`.

<details><summary>Solution</summary>

```python
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Hand):
            return NotImplemented
        return frozenset(self.cards) == frozenset(other.cards)

    def __hash__(self) -> int:
        return hash(frozenset(self.cards))
```

`frozenset` ignores order, so `a == c` (same cards) stays `True` with equal hashes, and `a == b`
becomes `False`; `a.score == b.score` is still `True`. All 93 existing tests pass, because none uses
`==` between hands. A dataclass does not overwrite a `__hash__` you define yourself. Undo with
`git checkout -- backend/src/evaluator.py`.
</details>

**🟡 5. Cache the score.** Change `@property` on `Hand.score` to `@functools.cached_property`
(add `import functools`). Measure before and after:
`python -m timeit -s "from src.evaluator import Hand; a = Hand.from_str('As Kh Qd'); b = Hand.from_str('9s 8h 2d')" "a > b"`.

<details><summary>Solution</summary>

About 6.74 µs before and 595 ns after on the machine this was written on; 93 tests pass.
`cached_property` stores the result in the instance's `__dict__` directly, which a frozen dataclass
allows (it only blocks normal attribute assignment). Undo with
`git checkout -- backend/src/evaluator.py`.
</details>

**🟡 6. Change a house rule.** Make every Đĩ tie, as AGENTS.md allows: in the Đĩ branch set
`primary_rank=0`, `secondary_rank=0` and `tie_breaker=()`. Predict how many tests fail, then run
`python -m pytest -q`.

<details><summary>Solution</summary>

`1 failed, 92 passed`. None of the 18 evaluator tests notices. The one failure is
`test_zero_fold_matches_exact_enumeration` in `test_calling_range.py`, first at `Q-J-J`: the
calling-range model now sees six classes with the same strength, and `winrates.json` was computed
with the old rule. A rule change is a data change too. Undo with
`git checkout -- backend/src/evaluator.py`.
</details>

**🔴 7. Meet the 1 µs budget.** Add a module-level `_SCORE_TABLE` built once by evaluating one
representative per sorted rank triple (`itertools.combinations_with_replacement(sorted(Rank), 3)`,
suits ♠ ♥ ♦), and an `evaluate_hand_fast` that validates, runs the sorting network and returns
`_SCORE_TABLE[(r1, r2, r3)]`. Prove it agrees with `evaluate_hand` on all 22,100 hands, then time
both.

<details><summary>Solution sketch</summary>

The table has 455 entries, and both functions return equal scores with equal names on every hand.
Timed with `timeit` on `9s 8h 2d`: 990 ns for the table version, 3.54 µs for `evaluate_hand`.
Returning a shared, frozen `HandScore` is safe because nobody can modify it. To switch for real,
make `evaluate_hand` itself use the table, keeping the original logic as the function that fills
it. Undo with `git checkout -- backend/src/evaluator.py`.
</details>

---

## ❓ Quiz

1. Why does a Sáp 2-2-2 beat Liêng Q-K-A even though `(4, 2, …)` has a smaller second element than
   `(3, 12, …)`?
2. How does the code make A-2-3 the *weakest* straight while the Ace is 14 everywhere?
3. Why does the Đĩ check not need to exclude J-Q-K and J-J-J itself?
4. Two different hands of the same category compare as equal. What must be true of their ranks?
5. Why can `{a, b}` have two elements when `a == b` is `True` for two `Hand`s?

<details><summary>Answers</summary>

1. Tuples are compared left to right and the first difference decides: 4 > 3 in the first slot,
   so the second slot is never looked at.
2. The Liêng table maps the sorted pattern `(2, 3, 14)` to strength 1, and the strength, not the top
   card, is `primary_rank`.
3. The checks run in category order and each returns: J-J-J returns as Sáp and J-Q-K as Liêng
   before the Đĩ test runs.
4. They must have the same three ranks, because `tie_breaker` contains all three. Only suits may
   differ.
5. `Hand.__eq__` compares strength, but the dataclass-generated `__hash__` hashes the `cards`
   tuple. The set puts the two hands in different buckets and never calls `==`.
</details>

---

## Recap

- `evaluate_hand` validates, sorts three ranks with a three-step sorting network, then checks Sáp,
  Liêng, Đĩ and Điểm in that order, returning at the first match.
- The result is a `HandScore` whose `score_tuple` is `(category, primary, secondary, score,
  tie_breaker)`; Python's tuple comparison turns all the rules into one `>`.
- Straights come from a 12-entry table: A-2-3 is the key `(2, 3, 14)` with strength 1; K-A-2 isn't
  a key, so it is 3 points.
- Đĩ is `r1 >= 11 and r3 <= 13` after Sáp and Liêng are gone: 6 shapes, Ace excluded.
- The 22,100 hands produce exactly 455 distinct score tuples; ties need identical ranks.
- Weak spots: `Hand`'s `__eq__`/`__hash__` contract is broken, `score` is recomputed on every
  access, one tuple slot is redundant, the tie-break house rules are untested, and evaluation is
  slower than the spec's 1 µs.

**Next:** [03 — Canonical hands: 22,100 → 455](03-canonical-hands.md)
