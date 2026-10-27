# Lesson 02 — Hand evaluation

> **Goal:** understand how `evaluate_hand` turns any three cards into one comparable `HandScore`,
> why a single `>` settles any showdown, exactly where each edge case (A-2-3, Q-K-A, K-A-2, J-Q-K,
> A-J-J) is decided, why the rules now run only 455 times, and how the `Hand` class's broken
> hash was fixed.
> **Files:** [`backend/src/evaluator.py:179-485`](../backend/src/evaluator.py#L179-L485),
> [`backend/tests/test_evaluator.py:89-306`](../backend/tests/test_evaluator.py#L89-L306).
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
recommendation is wrong with it, which is why it has the most tests of any domain module (27).

---

## Reading order

| # | Location | What to look for |
|---|----------|------------------|
| 1 | [evaluator.py:179-197](../backend/src/evaluator.py#L179-L197) | `HandCategory`: Điểm 1 … Sáp 4. |
| 2 | [evaluator.py:200-230](../backend/src/evaluator.py#L200-L230) | The 12 Liêng sequences and their names. Which key is A-2-3? |
| 3 | [evaluator.py:233-293](../backend/src/evaluator.py#L233-L293) | `HandScore`, `score_tuple`, five comparison methods and a `__hash__`. |
| 4 | [evaluator.py:301-340](../backend/src/evaluator.py#L301-L340) | `evaluate_hand`: validate, sort, then one table lookup. |
| 5 | [evaluator.py:343-401](../backend/src/evaluator.py#L343-L401) | `_score_for_sorted_ranks`: the four checks in order, and the 455-entry table built from it. |
| 6 | [evaluator.py:404-485](../backend/src/evaluator.py#L404-L485) | `Hand`: parsing, the cached `score`, comparisons, and `__eq__`/`__hash__` at the end. |
| 7 | [test_evaluator.py:89-251](../backend/tests/test_evaluator.py#L89-L251) | The rule tests: Sáp order, 12 Liêng, K-A-2, Đĩ, mod 10. |
| 8 | [test_evaluator.py:253-306](../backend/tests/test_evaluator.py#L253-L306) | House rules, hashing, caching, errors and the 1 µs budget. |

---

## Walkthrough

### 1. The idea: one tuple per hand

Instead of writing "if both are Sáp, compare ranks; if one is Liêng and the other Đĩ, …" for every
pair of categories, the evaluator turns each hand into a tuple and lets Python compare tuples:

📍 [`backend/src/evaluator.py:252-261`](../backend/src/evaluator.py#L252-L261)
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

`HandCategory` ([evaluator.py:179-197](../backend/src/evaluator.py#L179-L197)) is an `IntEnum`:
`DIEM = 1`, `DI = 2`, `LIENG = 3`, `SAP = 4`, plus a `display_name` with the Vietnamese spelling,
read from the module-level `_CATEGORY_NAMES`.
Higher number, stronger category. (EXPERIMENT.md numbers them the other way round; lesson 00.)

Straights are not computed, they are **looked up**:

📍 [`backend/src/evaluator.py:202-215`](../backend/src/evaluator.py#L202-L215)
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

### 3. `evaluate_hand`: validate, sort, look up

📍 [`backend/src/evaluator.py:325-340`](../backend/src/evaluator.py#L325-L340)
```python
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
```

That is the whole function. It does three things:

- **Validate.** Wrong count is an `InvalidHandSizeError`; the same card twice is a
  `DuplicateCardError` (lesson 01). The duplicate test compares the rank and the suit directly
  instead of writing `c1 == c2`: the dataclass `__eq__` would build two `(rank, suit)` tuples per
  comparison. Each `Suit` member exists exactly once, so `is` is a correct and cheap equality test.
- **Sort.** The three `if`s are a **sorting network**: three fixed compare-and-swap steps that sort
  any three numbers. The first two steps push the largest value into `r3`; the third orders the
  remaining two. Every permutation of `(14, 3, 9)` comes out as `(3, 9, 14)`. It avoids building a
  list and calling `sorted()`, which matters in a function the generator calls 8.4 million times.
- **Look up.** After the sort, `r1 <= r2 <= r3`, and the score is read from a table keyed by that
  ascending triple. The ranks are `Rank` members, and the table's keys are plain `int`s; that works
  because an `IntEnum` member hashes and compares exactly like its integer.

### 4. Where the table comes from

The rules themselves live in `_score_for_sorted_ranks(r1, r2, r3)`, which expects the ranks in
ascending order. It is called once per rank pattern, at import:

📍 [`backend/src/evaluator.py:397-401`](../backend/src/evaluator.py#L397-L401)
```python
# Every rank multiset (C(15, 3) = 455 of them), scored once. Keys are ascending rank values.
_SCORE_BY_RANKS: Final[dict[tuple[int, int, int], HandScore]] = {
    (r1, r2, r3): _score_for_sorted_ranks(r1, r2, r3)
    for r1, r2, r3 in itertools.combinations_with_replacement(range(Rank.TWO, Rank.ACE + 1), 3)
}
```

`combinations_with_replacement(range(2, 15), 3)` yields every multiset of three ranks, each as an
ascending tuple: `(2, 2, 2)`, `(2, 2, 3)`, … `(14, 14, 14)`, 455 of them. That is exactly the shape
the sorting network produces, so every possible hand finds its key. Suits never change a score, so
the ranks are the only key needed.

This is the fix for the old weak spot "the 1 µs budget is not met". Until October 2026,
`evaluate_hand` ran the four checks below on every call and took about 2.6 µs (4.3 µs on the
machine this lesson was re-run on); now it is a validation, a sort and one dict lookup, about
0.32 µs. The commit that made the change checked that the table gives identical scores on all
132,600 *ordered* hands (22,100 × 3! orders), and `test_evaluation_within_latency_budget`
([test_evaluator.py:302-306](../backend/tests/test_evaluator.py#L302-L306)) now pins the budget.

One side effect: every hand with the same ranks gets the **same** `HandScore` object back, not just
an equal one. That is safe because `HandScore` is frozen, and it is why an earlier version of the
cache test could not fail (weak spot 2).

The rules function starts by building the descending tuple used as the final tie-breaker:

📍 [`backend/src/evaluator.py:343-345`](../backend/src/evaluator.py#L343-L345)
```python
def _score_for_sorted_ranks(r1: int, r2: int, r3: int) -> HandScore:
    """Score three rank values given in ascending order (the rules of evaluate_hand)."""
    descending_ranks = (r3, r2, r1)
```

### 5. The checks, part 1: Sáp, then Liêng

📍 [`backend/src/evaluator.py:347-369`](../backend/src/evaluator.py#L347-L369)
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

### 6. The checks, part 2: Đĩ

📍 [`backend/src/evaluator.py:371-382`](../backend/src/evaluator.py#L371-L382)
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

### 7. The checks, part 3: Điểm, everything else

📍 [`backend/src/evaluator.py:384-394`](../backend/src/evaluator.py#L384-L394)
```python
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
```

The rules function only has rank numbers, so `Rank(r1)` turns each back into a `Rank` to read its
`point_value` (Ace 1, 10–K 0, lesson 01). The tie-break uses the **rank** `r3`, where the Ace is 14.
So the Ace counts 1 for points and 14 for "highest card".

### 8. Where each edge case is decided

| Case | Result | Decided at |
|------|--------|------------|
| A-2-3 is the weakest Liêng | strength 1 | the key `(2, 3, 14)` at [evaluator.py:203](../backend/src/evaluator.py#L203) |
| Q-K-A is the strongest Liêng | strength 12 | [evaluator.py:214](../backend/src/evaluator.py#L214) |
| K-A-2 is not a Liêng | 3 points | `(2, 13, 14)` is missing from the table, so it falls to [evaluator.py:385](../backend/src/evaluator.py#L385) |
| J-Q-K is Liêng, not Đĩ | strength 11 | [evaluator.py:213](../backend/src/evaluator.py#L213), checked before Đĩ |
| J-J-J is Sáp, not Đĩ | Sáp J | [evaluator.py:348](../backend/src/evaluator.py#L348), checked first |
| A-J-J is not Đĩ | 1 point | `r3 <= 13` at [evaluator.py:374](../backend/src/evaluator.py#L374) |
| Đĩ beats 9 points | category 2 > 1 | the first slot of `score_tuple` |
| 19 points is 9 points | 9 | `% 10` at [evaluator.py:385](../backend/src/evaluator.py#L385) |

Each row has a test: [test_evaluator.py:115](../backend/tests/test_evaluator.py#L115) (all 12
Liêng in order), [:144](../backend/tests/test_evaluator.py#L144) (K-A-2),
[:170](../backend/tests/test_evaluator.py#L170) (J-J-J and J-Q-K),
[:180](../backend/tests/test_evaluator.py#L180) (A-J-J), [:190](../backend/tests/test_evaluator.py#L190)
(Đĩ beats 9 points) and [:222](../backend/tests/test_evaluator.py#L222) (mod 10). They test
`evaluate_hand`, so they now exercise the table: a wrong entry would fail them just as a wrong `if`
did before.

### 9. House rules for ties

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

AGENTS.md used to say Đĩ hands are "considered equal (Tie) or compared by highest face card …
based on game configuration", while the code always compared them and nothing tested it. Since
October 2026 the spec states the rule the code implements, "house rule, as implemented; there is no
configuration switch" ([AGENTS.md:61](../AGENTS.md#L61), and [:72](../AGENTS.md#L72) for Điểm), and
`TestTieBreakHouseRules` ([test_evaluator.py:253-266](../backend/tests/test_evaluator.py#L253-L266))
pins the six Đĩ hands in order, A-K-8 over K-Q-9, and a same-rank tie.

### 10. `HandScore`'s comparison methods and hash

`HandScore` is declared `@dataclass(frozen=True, order=False)`
([evaluator.py:233](../backend/src/evaluator.py#L233)) and then defines `__lt__`, `__le__`,
`__gt__`, `__ge__` and `__eq__` by hand ([evaluator.py:263-286](../backend/src/evaluator.py#L263-L286)),
each the same three lines: return `NotImplemented` for a non-`HandScore`, otherwise compare
`score_tuple`s. Writing them out makes the comparison key explicit and keeps the `name` field out
of it. The hash is written out too, from the same key:

📍 [`backend/src/evaluator.py:288-290`](../backend/src/evaluator.py#L288-L290)
```python
    def __hash__(self) -> int:
        # Must agree with __eq__: equal scores hash equally, whatever their display name.
        return hash(self.score_tuple)
```

(The hash the dataclass generated from all six fields happened to agree with `__eq__`, because every
field is a function of the three ranks. The explicit one keeps it true even if a field that isn't
part of the key, such as `name`, ever changes. A dataclass never overwrites a `__hash__` the class
defines itself.)

`calculate_points` ([evaluator.py:296-298](../backend/src/evaluator.py#L296-L298)) is a public
helper that computes the same `% 10` sum; only a test calls it.

### 11. `Hand`: three validated cards

📍 [`backend/src/evaluator.py:404-413`](../backend/src/evaluator.py#L404-L413)
```python
@dataclass(frozen=True)
class Hand:
    """Immutable representation of a 3-card Liêng hand."""
    cards: tuple[Card, Card, Card]

    def __post_init__(self) -> None:
        if len(self.cards) != 3:
            raise InvalidHandSizeError(f"A Liêng hand must have 3 cards, got {len(self.cards)}.")
        if len(set(self.cards)) != 3:
            raise DuplicateCardError("A Liêng hand cannot have duplicate cards.")
```

`__post_init__` runs right after the generated `__init__`, so an invalid `Hand` can never exist.
`Hand.from_str` ([evaluator.py:420-440](../backend/src/evaluator.py#L420-L440)) splits on spaces,
commas or hyphens with `re.split(r"[\s,\-]+", …)` ([evaluator.py:434](../backend/src/evaluator.py#L434)):
`"As,Kh,Qd"`, `"As-Kh-Qd"` and `"  As   Kh  Qd "` all parse to `As Kh Qd`; `"AsKhQd"` is one token
and fails with `found 1`. This is the entry point for the CLI ([cli.py:253](../backend/src/cli.py#L253))
and the API ([app.py:296](../backend/app.py#L296)).

The strength is evaluated **once per hand** and then remembered:

📍 [`backend/src/evaluator.py:442-449`](../backend/src/evaluator.py#L442-L449)
```python
    @cached_property
    def score(self) -> HandScore:
        """Evaluate the hand once and return its HandScore.

        ``cached_property`` writes straight into the instance ``__dict__``, so it works on this
        frozen dataclass (which has no ``__slots__``).
        """
        return evaluate_hand(self.cards)
```

The first read of `hand.score` calls `evaluate_hand` and stores the result in `hand.__dict__`;
every later read finds it there without calling the function. A frozen dataclass blocks
`hand.score = …` (its `__setattr__` raises), but `cached_property` writes to `__dict__` directly,
which is allowed. Until October 2026 this was a plain `@property` that re-evaluated on every
access, so `a > b` on two hands evaluated both of them each time. `test_score_is_cached_on_the_hand`
checks exactly that `__dict__` entry (weak spot 2).

All five comparison operators delegate to `score`, so `hand_a > hand_b` reads exactly like a rule:
`Hand.from_str("2s 2h 2d") > Hand.from_str("Qs Kh Ad")` is "Sáp beats Liêng". The last two methods
are the ones this lesson used to be about:

📍 [`backend/src/evaluator.py:471-479`](../backend/src/evaluator.py#L471-L479)
```python
    def __eq__(self, other: object) -> bool:
        """Two hands are equal when they are equally strong (they would tie at showdown)."""
        if not isinstance(other, Hand):
            return NotImplemented
        return self.score == other.score

    def __hash__(self) -> int:
        # Must agree with __eq__: hands that tie hash equally, so they collapse in sets and dicts.
        return hash(self.score.score_tuple)
```

Two hands are "equal" when they are equally *strong*. **How it was broken:** until October 2026
there was no `__hash__` here, so the frozen dataclass generated one from the *field*, the `cards`
tuple. Two hands that were `==` got different hashes. `As Kh Qd` and the same three cards dealt as
`Kh As Qd` counted as two members of a set, and a dict keyed by one could not find the other, while
a list (which only uses `==`) could. Nothing in production hashed a `Hand`, so the bug was latent,
but AGENTS.md promised hands usable as dict keys ([AGENTS.md:25](../AGENTS.md#L25)).

**How it was fixed:** the owner had two options. "Same cards" (compare and hash
`frozenset(self.cards)`) would change what `==` means. "Same strength" keeps `__eq__` and adds a
`__hash__` from the same key, `score.score_tuple`. The fix chose the second, and AGENTS.md now says
so: "`Hand` equality means equal strength (the hands would tie), and its hash agrees with it." Run
the old demonstration against the current code:

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
a == b: True | hash equal: True
a == c: True | hash equal: True
len({a, b, c}): 1
b in seen: True | c in seen: True | c in [a]: True
```

Before the fix the same snippet printed `hash equal: False` twice, `len({a, b, c}): 3` and
`b in seen: False | c in seen: False`. Now all three hands are one set member, because all three
would tie. Note what that means: a set of `Hand`s keeps one hand per *strength*, not one per set of
cards. If you need "these exact cards", use `frozenset(hand.cards)` as the key.
`test_equal_hands_hash_equally_and_collapse_in_a_set`
([test_evaluator.py:272-276](../backend/tests/test_evaluator.py#L272-L276)) pins the fix.

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
- **Rules as a readable function, speed from a table.** `_score_for_sorted_ranks` keeps the rules
  in the clearest form; `_SCORE_BY_RANKS` runs it 455 times at import, so the hot path is one dict
  lookup. The cost is about 455 objects in memory and a few milliseconds at import.
- **Ranks in the tie-breaker.** Including all three ranks makes the order total over rank patterns
  (455 distinct values), which later modules rely on. The cost is a house rule for every tie.
- **`Hand` stores cards, not a score.** It stays a tiny value object; the score is derived on first
  use and cached in the instance (`cached_property`).
- **"Equal" means "would tie".** `Hand.__eq__` and `__hash__` both use the score, so hands work as
  dict keys and set members, at the price that a set keeps one hand per strength, not per cards.
- **`HandScore` carries a display name.** The CLI and API print `str(hand.score)` ("Liêng Q-K-A")
  without a second lookup.

---

## ⚠️ Weak spots

Six weak spots were listed here when the course was written. Commit `bba5e63` ("fix(core)", October
2026) fixed four of them; two are still open. The fixes left one new gap in a test, which commit
`a9d9ce9` closed.

1. ✅ **Fixed: `Hand.__eq__` and `__hash__` disagreed.** `__eq__` compared strength while the
   dataclass-generated hash used the ordered `cards` tuple, so equal hands had different hashes and
   the same three cards counted twice in a set. Now `Hand.__hash__` hashes `score.score_tuple`
   ([evaluator.py:477-479](../backend/src/evaluator.py#L477-L479)) and `HandScore` has an explicit
   hash from the same key ([evaluator.py:288-290](../backend/src/evaluator.py#L288-L290)); AGENTS.md
   documents the choice ([AGENTS.md:25](../AGENTS.md#L25)). Pinned by `TestHashing`
   ([test_evaluator.py:272-280](../backend/tests/test_evaluator.py#L272-L280)). Exercise 4 undoes it.
2. ✅ **Fixed: `score` was not cached, and then the test couldn't fail.** It re-ran
   `evaluate_hand` on every access. Now it is a `cached_property`
   ([evaluator.py:442-449](../backend/src/evaluator.py#L442-L449)); `a > b` on two hands takes about
   0.71 µs, against 1.34 µs with a plain `@property` over the new table and 8.3 µs with the old
   code. The first test meant to pin it, `test_score_is_computed_once`, asserted
   `hand.score is hand.score`. Since the table returns the same `HandScore` object for every hand
   with those ranks, that was true even without caching: with `@property` back, all 159 tests of
   the time passed. Commit `a9d9ce9` replaced it with `test_score_is_cached_on_the_hand`
   ([test_evaluator.py:282-288](../backend/tests/test_evaluator.py#L282-L288)), which looks at the
   cache itself: `assert "score" not in hand.__dict__` before the first read, then
   `assert hand.__dict__["score"] is first` after it. Change `@cached_property` to `@property` now
   and the suite says `1 failed, 171 passed`: the last line raises `KeyError: 'score'`, because a
   plain property never writes to `__dict__`. The first assert matters too: it proves the value
   isn't there before anyone asked for it.
3. **A redundant `score` field.** For Điểm it always equals `primary_rank`; for the other
   categories it is always 0 ([evaluator.py:248](../backend/src/evaluator.py#L248),
   [:259](../backend/src/evaluator.py#L259)). Removing it from `score_tuple` leaves 455 distinct
   tuples in exactly the same order, so it never decides anything. AGENTS.md now documents the real
   six-field `HandScore` and five-element tuple ([AGENTS.md:80-83](../AGENTS.md#L80-L83)), so the
   spec and the code agree; the slot is just dead weight. *Fix:* drop it from `score_tuple`, or
   document it as display data (exercise 7).
4. ✅ **Fixed: tie-break house rules were untested and undocumented.** Making every Đĩ tie, which the
   spec then allowed, failed only one test, indirectly. Now AGENTS.md states the rules as
   implemented ([AGENTS.md:61](../AGENTS.md#L61), [:72](../AGENTS.md#L72)), `TestTieBreakHouseRules`
   ([test_evaluator.py:253-266](../backend/tests/test_evaluator.py#L253-L266)) pins them, and the
   calling-range model refuses to start, with a `ModelError`, if two classes are equally strong
   ([calling_range.py:67-68](../backend/src/calling_range.py#L67-L68), lesson 06). Exercise 6 shows
   what a rule change does now.
5. ✅ **Fixed: the 1 µs budget was not met.** `evaluate_hand` took 2.6–3.8 µs per hand (all 22,100
   hands: 0.084 s), and nothing measured it. With the 455-entry table it takes about 0.32 µs (all
   22,100: 0.007 s); `test_evaluation_within_latency_budget`
   ([test_evaluator.py:302-306](../backend/tests/test_evaluator.py#L302-L306)) checks it, scaled by
   `PERF_BUDGET_FACTOR` on slow CI machines ([tests/perf.py](../backend/tests/perf.py)), and
   AGENTS.md records the measurement ([AGENTS.md:126](../AGENTS.md#L126)).
6. **Small duplications, and a list that isn't copied.** `calculate_points`
   ([evaluator.py:296-298](../backend/src/evaluator.py#L296-L298)) and the inline sum at
   [:385](../backend/src/evaluator.py#L385) compute the same thing; only a test uses the function.
   `Hand(cards=[…])` with a list passes validation, because the type hint isn't enforced, and the
   hand keeps that very list: append a fourth card to it afterwards and `len(hand.cards)` is 4, while
   a score cached earlier still describes the first three. *Fix:* in `__post_init__`, store
   `tuple(self.cards)` with `object.__setattr__(self, "cards", tuple(self.cards))` (exercise 5).

---

## 🧪 Try it

Run from `backend/` with the virtual environment active.

```bash
python -m pytest tests/test_evaluator.py -q
```

Expected output (the timing varies):

```
...........................                                              [100%]
27 passed in 0.07s
```

Evaluate all 22,100 hands and check the claims of section 1 and weak spot 3:

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
22100 hands in 0.007 s
Counter({'DIEM': 21136, 'LIENG': 768, 'DI': 144, 'SAP': 52})
distinct score tuples: 455
same order without score field: True
weakest: (1, 0, 4, 0, (4, 3, 3)) strongest: (4, 14, 0, 0, (14, 14, 14))
```

The weakest hand in the game is 4-3-3: 0 points, and the lowest possible top card among 0-point
hands. The same loop took 0.084 s before the score table (section 4). Time one evaluation:

```bash
python -m timeit -s "from src.evaluator import Hand, evaluate_hand; cards = Hand.from_str('9s 8h 2d').cards" "evaluate_hand(cards)"
```

Expected output (the time varies; the budget is 1 µs):

```
1000000 loops, best of 5: 323 nsec per loop
```

Run the snippet in section 11 to see the fixed hash yourself.

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
4 × 4 × 4 = 64 combinations. Lesson 03 calls 64 the *multiplicity*. 768 / 22,100 = 3.48%, the
figure BLOG.md now gives (it said 3.26% until October 2026).
</details>

**🟡 4. Undo the hash fix.** Delete `Hand.__hash__`
([evaluator.py:477-479](../backend/src/evaluator.py#L477-L479)). Predict what the snippet in
section 11 prints and which test fails, then run both and `python -m pytest -q`.

<details><summary>Solution</summary>

The snippet prints the old, broken output again: `hash equal: False` twice, `len({a, b, c}): 3`,
and `b in seen: False | c in seen: False`. No error is raised anywhere: without an explicit
`__hash__`, the frozen dataclass quietly generates one from the `cards` field. `1 failed, 171
passed`: only `test_equal_hands_hash_equally_and_collapse_in_a_set`
([test_evaluator.py:272-276](../backend/tests/test_evaluator.py#L272-L276)) notices, which is why
that test exists. Undo with `git checkout -- backend/src/evaluator.py`.
</details>

**🟡 5. Give `Hand` its own copy of the cards (weak spot 6).** First show the problem: build
`cards = [Card.from_str(s) for s in ("As", "Kh", "Qd")]`, then `hand = Hand(cards=cards)`, print
`hand.score`, append `Card.from_str("2c")` to `cards`, and print `len(hand.cards)`, `hand.score`
and `type(hand.cards).__name__`. Then make `Hand.__post_init__`
([evaluator.py:407-411](../backend/src/evaluator.py#L407-L411)) store a tuple, add a test, and run
`python -m pytest -q` and `python -m mypy`.

<details><summary>Solution</summary>

Before the fix the second print is `4 Liêng Q-K-A list`: the "immutable" hand now holds four cards,
and its cached score still describes the first three. `frozen=True` only stops you from assigning
`hand.cards = …`; it doesn't copy what you passed in. Add one line at the top of `__post_init__`:

```python
        object.__setattr__(self, "cards", tuple(self.cards))  # keep our own copy, never the caller's list
```

(`object.__setattr__` is the standard way for a frozen dataclass to set its own field, the same
trick `cached_property` relies on.) The second print becomes `3 Liêng Q-K-A tuple`. A test:

```python
def test_hand_keeps_its_own_copy_of_the_cards() -> None:
    cards = [Card.from_str(s) for s in ("As", "Kh", "Qd")]
    hand = Hand(cards=cards)  # type: ignore[arg-type]
    cards.append(Card.from_str("2c"))
    assert hand.cards == tuple(cards[:3])
    assert isinstance(hand.cards, tuple)
```

`173 passed`; mypy reports `Success: no issues found in 12 source files` (it checks `src/` and
`app.py`, not the tests). The length and duplicate checks below the new line now run on the copy,
so they check exactly what the hand keeps. Undo with
`git checkout -- backend/src/evaluator.py backend/tests/test_evaluator.py`.
</details>

**🟡 6. Change a house rule.** Make every Đĩ tie, the option AGENTS.md used to allow: in the Đĩ
branch ([evaluator.py:375-382](../backend/src/evaluator.py#L375-L382)) set `primary_rank=0`,
`secondary_rank=0` and `tie_breaker=()`. Predict what happens, then run
`python -m pytest tests/test_evaluator.py -q` and `python -m pytest -q`.

<details><summary>Solution</summary>

The evaluator tests give `1 failed, 26 passed`: `test_di_order_highest_face_card_then_middle_then_rest`
now pins the rule. The whole suite stops early: `Interrupted: 2 errors during collection`.
`test_api.py` and `test_dynamic_scenarios.py` build the app when they are imported, the app builds a
`CallingRangeModel`, and the model refuses to start: `ModelError: The calling-range model needs
every canonical class to have a distinct strength.` (With `--continue-on-collection-errors`:
`5 failed, 103 passed, 14 errors`.) Before the fixes, the same change failed one test, and the
calling-range numbers were silently wrong. Now a rule change is loud, as it should be: it is a data
change too, because `winrates.json` was computed with the old rule. Undo with
`git checkout -- backend/src/evaluator.py`.
</details>

**🔴 7. Drop the redundant slot (weak spot 3).** Remove `self.score` from `score_tuple`
([evaluator.py:252-261](../backend/src/evaluator.py#L252-L261)) and fix its return type. Before
running anything, explain why `winrates.json` and the calling-range order stay valid. Then prove it:
rerun the 22,100-hand snippet from 🧪 Try it, then `python -m pytest -q` and `python -m mypy`.

<details><summary>Solution</summary>

The return type becomes `tuple[int, int, int, tuple[int, ...]]`. The slot never decided a
comparison (weak spot 3: the order is the same without it), so every `>` and `==` gives the same
answer, the 455 classes keep their order, and nothing computed from them changes. The snippet
still prints 455 distinct tuples, now with four elements (`weakest: (1, 0, 4, (4, 3, 3))`; ignore its
`same order` line, which assumes five slots);
`172 passed`; mypy reports `Success: no issues found in 12 source files`. What does change is
documentation: AGENTS.md §3.3 and the note at the top of EXPERIMENT.md describe a five-element
tuple, so a real change would update them in the same commit. Undo with
`git checkout -- backend/src/evaluator.py`.
</details>

---

## ❓ Quiz

1. Why does a Sáp 2-2-2 beat Liêng Q-K-A even though `(4, 2, …)` has a smaller second element than
   `(3, 12, …)`?
2. How does the code make A-2-3 the *weakest* straight while the Ace is 14 everywhere?
3. Why does the Đĩ check not need to exclude J-Q-K and J-J-J itself?
4. Two different hands of the same category compare as equal. What must be true of their ranks?
5. `a == b` is `True` for two `Hand`s. Why must `hash(a) == hash(b)` also hold, and what in the
   code makes it hold today?

<details><summary>Answers</summary>

1. Tuples are compared left to right and the first difference decides: 4 > 3 in the first slot,
   so the second slot is never looked at.
2. The Liêng table maps the sorted pattern `(2, 3, 14)` to strength 1, and the strength, not the top
   card, is `primary_rank`.
3. The checks run in category order and each returns: J-J-J returns as Sáp and J-Q-K as Liêng
   before the Đĩ test runs.
4. They must have the same three ranks, because `tie_breaker` contains all three. Only suits may
   differ.
5. Sets and dicts first pick a bucket by hash and only then compare with `==`; equal objects with
   different hashes land in different buckets and are never compared, so a set would keep both
   (that was the bug until October 2026). Today `Hand.__hash__` hashes `score.score_tuple`, the
   same key `__eq__` compares.
</details>

---

## Recap

- `evaluate_hand` validates, sorts three ranks with a three-step sorting network, then reads the
  score from a 455-entry table (about 0.3 µs). The table is built at import by
  `_score_for_sorted_ranks`, which checks Sáp, Liêng, Đĩ and Điểm in that order, returning at the
  first match.
- The result is a `HandScore` whose `score_tuple` is `(category, primary, secondary, score,
  tie_breaker)`; Python's tuple comparison turns all the rules into one `>`.
- Straights come from a 12-entry table: A-2-3 is the key `(2, 3, 14)` with strength 1; K-A-2 isn't
  a key, so it is 3 points.
- Đĩ is `r1 >= 11 and r3 <= 13` after Sáp and Liêng are gone: 6 shapes, Ace excluded.
- The 22,100 hands produce exactly 455 distinct score tuples; ties need identical ranks.
- `Hand` means "equal strength" for both `==` and `hash`, and caches its score.
- Fixed: the hash contract, the uncached score (now with a test that can fail), untested house
  rules, the missed 1 µs budget. Still open: a redundant tuple slot, a duplicated points helper and
  an uncopied `cards` list.

**Next:** [03 — Canonical hands: 22,100 → 455](03-canonical-hands.md)
