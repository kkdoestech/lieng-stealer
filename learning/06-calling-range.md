# Lesson 06 — The calling range

> **Goal:** understand how `calling_range.py` computes your *exact* equity against an opponent who
> folds their weakest hands and calls with the rest, including card removal, in about a microsecond
> per query.
> **Files:** [`backend/src/calling_range.py`](../backend/src/calling_range.py),
> [`backend/tests/test_calling_range.py`](../backend/tests/test_calling_range.py).
> **Time:** ~90 min. Take it slowly: this is the most mathematical lesson in the course.
> **Before this:** [05 — The win-rate database](05-win-rate-db.md).

---

## Where this fits

```
              your hand (canonical ID) + opponent fold rate f
        opponent_model = "random"  │  opponent_model = "range"
        ┌──────────────────────────┴──────────────────────────────┐
        ▼                                                         ▼
  db.py (lesson 05)                        ┌─────────────────────────────────────────┐
  equity vs a RANDOM hand, ignores f       │ calling_range.py (this lesson)          │
        │                                  │ equity vs the hands that CALL, uses f   │
        │                                  └─────────────────────────────────────────┘
        └──────────────► w = equity when called ──► ev.py (lesson 07) ◄──┘
```

Lessons 04 and 05 answer "how often do I beat a **random** hand?". But a sensible opponent who
*calls* your raise folds junk and calls with good cards, so their hand is not random. This module
answers what the EV formula needs: "how often do I win **given that they called**?". It is built
once at start-up; then every query is a few array lookups.

---

## Reading order

| # | Location | What to look for |
|---|----------|------------------|
| 1 | [calling_range.py:1-11](../backend/src/calling_range.py#L1-L11) | The model in one paragraph, and the claim "455 distinct strengths". |
| 2 | [calling_range.py:24-37](../backend/src/calling_range.py#L24-L37) | Constants re-exported from `hands.py`, the `_COMB` table, the `OpponentModel` enum. |
| 3 | [calling_range.py:60-76](../backend/src/calling_range.py#L60-L76) | Sort classes strongest-first, check the two invariants, build running totals. |
| 4 | [calling_range.py:78-99](../backend/src/calling_range.py#L78-L99) | One card-removal row per hero class. |
| 5 | [calling_range.py:142-150](../backend/src/calling_range.py#L142-L150) | `_calling_boundary`: where the calling range ends, with `bisect_right`. |
| 6 | [calling_range.py:152-170](../backend/src/calling_range.py#L152-L170) | `_equity_at`: count what you beat and tie. |
| 7 | [calling_range.py:107-140](../backend/src/calling_range.py#L107-L140) | The public API: `equity` and `equity_table`. |
| 8 | [test_calling_range.py](../backend/tests/test_calling_range.py) | 13 tests, including an exact cross-check against `winrates.json` and the two invariant checks. |
| 9 | [app.py:290-298](../backend/app.py#L290-L298) | `_reject_removed_fields`: the `call_range_percent` field that used to hand the caller its own range, and the message that names its replacement (section 9). |

---

## Walkthrough

### 1. Why random-hand equity is too optimistic

Here is your equity against an opponent who folds a fraction `f` of their hands, always the weakest
ones. The `f = 0` column is "they never fold", so they call with everything, which is the same as
a random hand.

| Hand | f = 0 | 0.20 | 0.35 | 0.50 | 0.70 | 0.90 |
|------|-------|------|------|------|------|------|
| Q-K-A (best Liêng) | 0.9969 | 0.9962 | 0.9952 | 0.9938 | 0.9895 | 0.9664 |
| K-K-Q (Đĩ) | 0.961 | 0.951 | 0.9394 | 0.9209 | 0.8662 | 0.5666 |
| 9-8-2 (9 points) | 0.879 | 0.8488 | 0.8147 | 0.7593 | 0.5968 | 0.0 |
| K-Q-5 (5 points) | 0.5541 | 0.44 | 0.3097 | 0.0976 | 0.0 | 0.0 |
| K-Q-3 (3 points) | 0.36 | 0.1976 | **0.0108** | 0.0 | 0.0 | 0.0 |
| K-6-6 (2 points) | 0.2541 | 0.0663 | 0.0 | 0.0 | 0.0 | 0.0 |

Monsters barely notice. Medium hands collapse: K-Q-3 wins 36% against a random hand, but about 1%
of the showdowns that happen when the opponent folds their weakest 35% (lesson 07 prices that).

### 2. The idea in one picture

Sort all 455 classes from strongest to weakest, and picture each class as a stack of its real
combos (multiplicity 4, 24 or 64, lesson 03). Together they hold all 22,100 hands.

```
 strongest ───────────────────────────────────────────────────────────────────────► weakest
 index:    0      1   …   12     13     14   …   294    295    296     297    298  …   454
 class:  A-A-A  K-K-K … 2-2-2  Q-K-A  K-Q-J  …  K-Q-3  K-J-3  K-10-3  K-9-4  K-8-5 … 4-3-3
 combos:   4      4   …   4      64     64   …   64     64     64      64     64   …   24
```

An opponent who folds a fraction `f` calls with the **top** `(1 − f) × 22,100` combos of this list.
At `f = 0.35` that is 14,365 combos. To get your equity you need three things:

1. Where does the calling range end? (a running total and a binary search, sections 3 and 5)
2. How many calling combos can the opponent *actually* hold, given your three cards? (card
   removal, section 4)
3. Of those, how many are weaker than you, and how many equal? (subtractions, section 6)

### 3. Step 1: strength order and running totals

📍 [`backend/src/calling_range.py:60-76`](../backend/src/calling_range.py#L60-L76)
```python
        ordered = sorted(
            hands if hands is not None else generate_all_canonical_hands(),
            key=lambda h: h.score.score_tuple,
            reverse=True,
        )
        if sum(h.multiplicity for h in ordered) != TOTAL_COMBINATIONS:
            raise ModelError(f"The calling-range model needs classes covering all {TOTAL_COMBINATIONS} hands.")
        if len({h.score.score_tuple for h in ordered}) != len(ordered):
            raise ModelError("The calling-range model needs every canonical class to have a distinct strength.")
        self._ids: tuple[str, ...] = tuple(h.canonical_id for h in ordered)
        self._index: dict[str, int] = {cid: i for i, cid in enumerate(self._ids)}
        self._mult: tuple[int, ...] = tuple(h.multiplicity for h in ordered)

        cum_mult = [0]
        for m in self._mult:
            cum_mult.append(cum_mult[-1] + m)
        self._cum_mult: tuple[int, ...] = tuple(cum_mult)
```

- **Sort by `score_tuple`, descending.** That is the tuple lesson 02 compares hands with, so index 0
  is A-A-A and index 454 is 4-3-3. Indices 0–12 are the 13 Sáp, 13 is Q-K-A, and K-Q-3 sits at 294.
- **`_index`** maps an ID back to its position, so a query starts with one dict lookup.
- **`_cum_mult` is a prefix sum** (concept box below): `_cum_mult[j]` = the number of combos in the
  `j` strongest classes. It has 456 entries, from 0 to 22,100.

| j | 0 | 1 | 2 | 13 | 14 | 296 | 297 | 298 | 454 | 455 |
|---|---|---|---|----|----|-----|-----|-----|-----|-----|
| `_cum_mult[j]` | 0 | 4 | 8 | 52 | 116 | 14,244 | 14,308 | 14,372 | 22,076 | 22,100 |

Read `_cum_mult[13] = 52` as "the 13 Sáp classes hold 52 combos", and `_cum_mult[297] = 14,308` as
"the 297 strongest classes hold 14,308 combos".

Everything below relies on two facts, and the two `if`s check them before any table is built:

- **The classes cover the whole deck.** Their multiplicities must add up to 22,100
  (`TOTAL_COMBINATIONS`, re-exported from `hands.py`), because the fold rate `f` is a share of
  22,100 (section 5). A list of the 100 strongest classes is refused:
  `ModelError: The calling-range model needs classes covering all 22100 hands.`
- **No two classes are equally strong.** The module docstring states it
  ([calling_range.py:8](../backend/src/calling_range.py#L8)), and the second check enforces it by
  counting distinct score tuples. It is true today: the 455 classes have 455 different score tuples.
  If a house rule made the six Đĩ classes tie (lesson 02, exercise 6), the model would now refuse to
  start instead of silently counting ties as wins or losses (weak spot 1).

Both checks were added in October 2026. They cost one pass over the list, at start-up only. Both
raise `ModelError`, the exception for "the solver's own model is broken" (lesson 01): a failed
check is a bug or a bad rule change, never something the user typed.

### 4. Step 2: card-removal rows

If you hold `K♠ Q♥ 3♦`, the opponent cannot hold those cards. They can only hold 3 kings, 3 queens
and 3 threes. So how many combos of each class can they still have?

For each rank a class needs, count the ways to pick that many cards from what is left, and
multiply: `C(cards of that rank left, cards needed)`. With you holding K-Q-3:

| Opponent class | Needs | Ways | Without card removal |
|----------------|-------|------|----------------------|
| A-A-A | 3 aces (4 left) | C(4,3) = **4** | 4 |
| K-K-K | 3 kings (3 left) | C(3,3) = **1** | 4 |
| K-K-Q | 2 kings, 1 queen | C(3,2) × C(3,1) = **9** | 24 |
| K-Q-3 (your own class) | 1 K, 1 Q, 1 three | 3 × 3 × 3 = **27** | 64 |
| K-9-4 | 1 K, 1 nine, 1 four | 3 × 4 × 4 = **48** | 64 |

The code does exactly this, for every hero class, against every opponent class in strength order:

📍 [`backend/src/calling_range.py:78-99`](../backend/src/calling_range.py#L78-L99)
```python
        rank_counts = [Counter(r.value for r in h.ranks) for h in ordered]
        opponent_needs = [tuple(c.items()) for c in rank_counts]
        self._prefix: tuple[array[int], ...] = tuple(
            self._build_prefix_row(hero, opponent_needs) for hero in rank_counts
        )

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

- `Counter(...)` turns a class into "rank → how many". K-K-Q becomes `{13: 2, 12: 1}`. The same
  counter is the hero's "cards I hold" and the opponent's "cards I need".
- `remaining` is how many of each rank are left after the hero's three cards.
- `_COMB[n][k]` is a small precomputed table of `C(n, k)` for `n ≤ 4`, `k ≤ 3`
  ([calling_range.py:29-31](../backend/src/calling_range.py#L29-L31)). `C(1, 3)` is 0, which
  correctly says "you can't make A-A-A when the hero holds two aces".
- Each row is again a **prefix sum**, but of card-removal counts: `row[j]` = how many opponent hands
  the `j` strongest classes contain, *given your cards*.

K-Q-3's row, at a few positions:

| j | 1 | 2 | 13 | 294 | 295 | 296 | 297 | 298 | 455 (last) |
|---|---|---|----|-----|-----|-----|-----|-----|------------|
| `row[j]` | 4 | 5 | 43 | 11,778 | 11,805 | 11,841 | 11,877 | 11,925 | **18,424** |

- `row[1] = 4`: A-A-A is unaffected. `row[2] = 5`: K-K-K adds only 1. `row[13] = 43`: the
  opponent can hold 43 Sáp hands, not 52, because you hold a K, a Q and a 3.
- `row[294] = 11,778`: every opponent hand stronger than K-Q-3. That is exactly the **loss count**
  from lesson 04's enumeration of K-Q-3. `row[295] − row[294] = 27` is the tie count, and
  `18,424 − row[295] = 6,619` the win count. The row stores the generator's answer, sliced by
  strength.
- **Every row ends at 18,424**, the C(49, 3) hands left after your three cards.
  [test_calling_range.py:39-41](../backend/tests/test_calling_range.py#L39-L41) checks that for all
  455 rows. It is a strong check: miss or double-count one class and the total is off.

The build is 455 rows × 455 classes, about 207,000 small multiplications, done once. It took 50 ms
here, and the 455 rows take 893,620 bytes as `array("i")` (4 bytes per number, plus each array's
own overhead).

### 5. Step 3: where does the calling range end?

📍 [`backend/src/calling_range.py:142-150`](../backend/src/calling_range.py#L142-L150)
```python
    def _calling_boundary(self, fold_equity: float) -> tuple[int, float]:
        """Return (k, frac): classes [0, k) call in full, class k calls with weight frac."""
        if not (0.0 <= fold_equity <= 1.0):
            raise InvalidGameParamsError(f"Fold equity must be between 0.0 and 1.0, got {fold_equity}.")
        calling_combos = (1.0 - fold_equity) * TOTAL_COMBINATIONS
        k = bisect_right(self._cum_mult, calling_combos) - 1
        if k >= len(self._ids):
            return len(self._ids), 0.0
        return k, (calling_combos - self._cum_mult[k]) / self._mult[k]
```

(A bad `f` is an `InvalidGameParamsError`, which is also a `ValueError`: lesson 01.)

Follow `f = 0.35` through it:

```
 calling_combos = (1 − 0.35) × 22,100 = 14,365

 j:            …    296       297    │    298       299   …
 _cum_mult[j]: …  14,244    14,308   │  14,372    14,436  …
                              ≤ 14,365 │ > 14,365
                                      ▲
            bisect_right(_cum_mult, 14365) = 298      →      k = 298 − 1 = 297
```

- `bisect_right` finds the first position whose running total is **greater** than 14,365. That is
  298, so the last total that fits is at `k = 297` (concept box below).
- Classes 0 to 296 (297 classes, 14,308 combos) call **in full**.
- Class 297, K-9-4, is the **boundary class**. Only `14,365 − 14,308 = 57` of its 64 combos fit, so
  it calls with weight `frac = 57 / 64 = 0.890625`.
- Everything after it folds.

```
 [ A-A-A … K-10-3 ][   K-9-4    ][ K-8-5 … 4-3-3 ]
   297 classes        57 of 64      157 classes
   call in full       call          fold
```

Two edge cases:

- **`f = 0`:** `calling_combos = 22,100`, `bisect_right` returns 456, so `k = 455`, one past the
  last class. [Lines 148-149](../backend/src/calling_range.py#L148-L149) catch it and return
  `(455, 0.0)`: every class calls, nothing is partial.
- **`f = 1`:** `calling_combos = 0`, `k = 0`, `frac = 0.0`. Nobody calls (weak spot 2).

Why measure `f` against the full 22,100, without card removal? Because the opponent decides on
their own cards. Their strategy, "call with the top 65%", cannot depend on what *you* hold. Weak
spot 3 looks at the price of that choice.

### 6. Step 4: count what you beat

📍 [`backend/src/calling_range.py:152-170`](../backend/src/calling_range.py#L152-L170)
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
            tied = float(row[hero + 1] - row[hero])
        elif hero == k:
            beaten = 0.0
            tied = boundary
        else:
            beaten = 0.0
            tied = 0.0
        return round((beaten + 0.5 * tied) / calling, 4)
```

(The `float(...)` around `tied` is for strict mypy: in the other branches `tied` is a float, and an
array subtraction gives an `int`.)

Everything is read from **your** row, so card removal is already included:

- `boundary` = the calling share of the boundary class: its card-removal count × `frac`.
- `calling` = all calling combos: the full classes (`row[k]`) plus the boundary share.
- The result is the lesson 04 formula, `(beaten + ½ tied) / calling`, with "all opponents" replaced
  by "calling opponents".

There are three cases, depending on where you sit relative to the boundary `k`:

```
 index:  0 ……… hero−1 │ hero │ hero+1 ……… k−1 │    k     │ k+1 … 454
         stronger      │ you  │  weaker, call   │ boundary │  fold
         you lose      │ tie  │  you win        │ you win  │  not counted
```

**Case 1: `hero < k`, you are inside the calling range.** K-Q-3 (index 294) at `f = 0.35`
(`k = 297`, `frac = 0.890625`):

| Quantity | Formula | Value |
|----------|---------|-------|
| boundary | 0.890625 × (row[298] − row[297]) = 0.890625 × (11,925 − 11,877) | 42.75 |
| calling | row[297] + boundary = 11,877 + 42.75 | 11,919.75 |
| beaten | row[297] − row[295] + boundary = 11,877 − 11,805 + 42.75 | 114.75 |
| tied | row[295] − row[294] = 11,805 − 11,778 | 27 |
| **equity** | (114.75 + 0.5 × 27) / 11,919.75 | **0.0108** |

K-Q-3 beats only K-J-3 and K-10-3 (36 combos each after card removal) and the calling part of
K-9-4. The other 11,778 calling combos beat it. That is the collapse from section 1, in numbers.

**Case 2: `hero == k`, you are the boundary class.** K-9-4 at `f = 0.35`. Every weaker class
folds, so `beaten = 0`. You can only tie the calling part of your own class:
`tied = 0.890625 × 27 = 24.05`, `calling = 11,896 + 24.05 = 11,920.05`, equity
`0.5 × 24.05 / 11,920.05 = 0.0010`.

**Case 3: `hero > k`, every caller is stronger.** 5-3-2 (index 452) at `f = 0.35`: equity 0.0.

### 7. The public API

📍 [`backend/src/calling_range.py:122-125`](../backend/src/calling_range.py#L122-L125)
```python
        if canonical_id not in self._index:
            raise UnknownHandError(f"Canonical hand '{canonical_id}' not found in calling-range model.")
        k, frac = self._calling_boundary(fold_equity)
        return self._equity_at(self._index[canonical_id], k, frac)
```

📍 [`backend/src/calling_range.py:139-140`](../backend/src/calling_range.py#L139-L140)
```python
        k, frac = self._calling_boundary(fold_equity)
        return {cid: self._equity_at(i, k, frac) for i, cid in enumerate(self._ids)}
```

`equity` answers one hand: a dict lookup, a binary search over 456 numbers (about 9 steps) and a
few subtractions. It took about 1.5 µs here. An unknown id is an `UnknownHandError`, which is both a
`LiengError` and a `KeyError` (lesson 01). `equity_table` answers all 455 at one `f` and finds the
boundary only once. It took 0.4 ms, far inside the 25 ms budget that
[test_calling_range.py:76-80](../backend/tests/test_calling_range.py#L76-L80) enforces. The range
finder uses the table (lesson 08); the API's per-hand zone scan calls `equity` 101 times (lesson 07).

Whether this module is used at all is decided by the `OpponentModel` enum
([calling_range.py:34-37](../backend/src/calling_range.py#L34-L37)): `RANDOM = "random"` or
`RANGE = "range"`. It is a `StrEnum` (Python 3.11+), whose members are also `str`s, so
`OpponentModel.RANGE == "range"` is `True`, `str(OpponentModel.RANGE)` is `"range"`, and
`OpponentModel("range")` turns the text of a web request into the enum. It is switched on in
[range_finder.py:79](../backend/src/range_finder.py#L79), [cli.py:260](../backend/src/cli.py#L260)
and [app.py:306](../backend/app.py#L306).

The same module re-exports the two state-space sizes from `hands.py` (lesson 03):

📍 [`backend/src/calling_range.py:24-25`](../backend/src/calling_range.py#L24-L25)
```python
from src.hands import OPPONENT_COMBINATIONS as OPPONENT_COMBINATIONS  # re-exported: C(49, 3) = 18,424
from src.hands import TOTAL_COMBINATIONS as TOTAL_COMBINATIONS  # re-exported: C(52, 3) = 22,100
```

The odd-looking `import X as X` is the conventional way to say "this name is part of my public
interface". `calling_range.py` never uses `OPPONENT_COMBINATIONS` itself, so a plain import would
fail `ruff` with `F401 … imported but unused`; the redundant alias tells ruff (and strict type
checkers) that the re-export is deliberate. The tests import it from here
([test_calling_range.py:16](../backend/tests/test_calling_range.py#L16)). Until October 2026 this
file defined both numbers itself.

### 8. Two independent methods that agree

At `f = 0` the calling range is every hand, so this module must reproduce `winrates.json`. It does,
exactly: I compared all 455 classes and found **0** mismatches.
[test_calling_range.py:43-47](../backend/tests/test_calling_range.py#L43-L47) pins it.

The two numbers come from completely different code: 18,424 showdowns per class in the generator,
binomial products and prefix sums here. A bug in either would show up as a mismatch.

The second invariant: **equity never increases with `f`**, because more folds drop the weakest
callers, the ones you beat ([test_calling_range.py:49-53](../backend/tests/test_calling_range.py#L49-L53),
21 values of `f`; I also checked all 101 grid values). Lesson 07 builds on this: since `w` falls as
`f` rises, EV is no longer a straight line in `f`.

### 9. The second model that was deleted

`CallingRangeModel` derives caller strength from fold frequency: if the opponent folds 35%, the
strongest 65% call. Until 2.0.0 there was a second module, `opponent_model.py`, whose function let a
caller pick the caller-range size directly, say the strongest 30%, independently of the fold
estimate. It removed Hero's cards before counting legal hands and returned exact win-plus-half-tie
equity, and the API accepted that as a `call_range_percent` request field.

Both are gone. Two assumptions in one answer meant a request could compute the hand from one of them
and the 455-class table from the other: send `call_range_percent: 30` next to `fold_equity: 0.35`
and the verdict card said one thing while the table said another. Now `fold_equity` is the only
caller assumption, the calling range is derived from it, and `call_range_percent` is rejected with a
400 that names the replacement ([app.py:290-298](../backend/app.py#L290-L298)). `AGENTS.md` §2.2
records the rule, and `git log` has the removal commit.

---

## 💡 Concept: prefix sums

A **prefix sum** stores running totals: entry `j` is the sum of the first `j` items.

```python
items  = [4, 4, 24, 64]
prefix = [0, 4, 8, 32, 96]      # prefix[j] = items[0] + … + items[j-1]
```

The sum of any block is then **one subtraction**: items 1 and 2 sum to `prefix[3] − prefix[1] =
32 − 4 = 28`. Building the table costs one pass; every block sum after that is O(1). This module
keeps one for the class sizes (`_cum_mult`) and one per hero for the card-removal counts (`_prefix`).

## 💡 Concept: binary search with `bisect_right`

On a **sorted** list, `bisect_right(a, x)` returns the position where `x` would be inserted, after
any equal values. It halves the search range each step: about 9 steps for 456 entries.

```python
>>> from bisect import bisect_right
>>> cum = [0, 4, 8, 32, 96]
>>> bisect_right(cum, 10)    # 10 would go between 8 and 32
3
>>> bisect_right(cum, 8)     # equal value: insert *after* it
3
```

So `bisect_right(cum, x) − 1` is "the last index whose total is ≤ x". A running total is always
sorted (multiplicities are positive), which is what makes the search valid.

---

## Design decisions

- **Exact counting instead of simulation.** Every quantity is an integer count from the same deck
  model as the generator, so the `f = 0` case matches lesson 04 to the last digit.
- **Precompute once, query forever.** About 50 ms and under 1 MB at start-up, then microseconds
  per query: the project's offline/online split, in small.
- **A fractional boundary class.** Calling "57 of 64 K-9-4 combos" keeps equity a smooth function of
  `f`. Without it, equity would jump in steps each time a whole class drops out (exercise 4).
- **The boundary is measured on 22,100, not on your row.** The opponent's strategy cannot see your
  cards. It is a modelling choice with a small cost (weak spot 3).
- **Refuse rather than guess.** The constructor checks its two assumptions (full deck, distinct
  strengths) and raises. A wrong equity would flow silently into every EV; an error at start-up
  can't be missed.
- **A perfect strength sorter.** `RANGE` assumes the opponent always folds exactly their weakest
  hands. Real players are messier. Together with `RANDOM` (folds without looking), the two models
  bracket reality: the truth for a real opponent is usually somewhere between.

---

## ⚠️ Weak spots

Six weak spots were listed here when the course was written. Commit `bba5e63` ("fix(core)", October
2026) fixed three of them. Two modelling choices remain, the private-state test is unchanged, and
the fix introduced one small new problem, which commit `a9d9ce9` fixed.

1. ✅ **Fixed: it silently needed 455 distinct strengths.** The `hero < k` / `hero == k` cases assume
   one strict order. Under a house rule where all Đĩ hands tie, six classes would be equal and
   `_equity_at` would have counted some ties as wins or losses, with no error. Now `__init__`
   counts distinct score tuples and raises `ModelError` if any two classes are equally strong
   ([calling_range.py:67-68](../backend/src/calling_range.py#L67-L68)). Pinned by
   `test_rejects_classes_with_equal_strength`
   ([test_calling_range.py:91-101](../backend/tests/test_calling_range.py#L91-L101)). A real tie
   rule would still need the fix the old text suggested: group equal classes into one strength
   level.
2. **`f = 1` returns 0.0.** [calling_range.py:157-158](../backend/src/calling_range.py#L157-L158):
   when nobody calls, "equity when called" is undefined, and the code returns 0, even for A-A-A.
   EV doesn't care (the `(1 − f)` factor is 0), but a UI that shows "equity when called: 0%" for
   A-A-A is misleading. `test_full_fold_returns_zero_without_error`
   ([test_calling_range.py:64-66](../backend/tests/test_calling_range.py#L64-L66)) pins the current
   choice. *Fix:* return `None`, or document it where the number is displayed.
3. **`f` is a share of 22,100, not of the hands still possible.**
   [calling_range.py:146](../backend/src/calling_range.py#L146). Your cards remove unevenly from
   strong and weak classes, so the share of *possible* opponent hands that call is not exactly
   `1 − f`. At `f = 0.35` it ranges from 64.04% (you hold K-K-K) to 65.73% (you hold 2-2-2). Small,
   but real. *Fix:* exercise 6 searches the boundary on your own row instead.
4. ✅ **Fixed: the `hands` parameter accepted a subset, but the total was 22,100.** A model built
   from the 20 strongest classes (500 combos) returned `(20, 0.0)` at `f = 0.5`: "everyone calls",
   which is meaningless. Now any list whose multiplicities don't add up to `TOTAL_COMBINATIONS` is
   refused with a `ModelError` ([calling_range.py:65-66](../backend/src/calling_range.py#L65-L66)), pinned by
   `test_rejects_a_subset_of_hands` ([test_calling_range.py:84-89](../backend/tests/test_calling_range.py#L84-L89)).
5. ✅ **Fixed: built-in errors escaped `LiengError`.** An unknown id now raises `UnknownHandError`
   ([calling_range.py:123](../backend/src/calling_range.py#L123)) and a bad `f`
   `InvalidGameParamsError` ([:145](../backend/src/calling_range.py#L145)), each also the built-in it
   replaced, so the old `test_invalid_inputs` still passes. Pinned by
   `test_errors_are_project_errors` ([test_calling_range.py:103-109](../backend/tests/test_calling_range.py#L103-L109)).
6. **Tests read private state.** [test_calling_range.py:41](../backend/tests/test_calling_range.py#L41)
   reads `model._prefix`, and the Try-it commands below read `_calling_boundary`, `_ids` and
   `_index`. `OPPONENT_COMBINATIONS` is re-exported here only for that test
   ([calling_range.py:24](../backend/src/calling_range.py#L24)). *Fix:* a small public method such
   as `opponent_combos(cid)`.
7. ✅ **Fixed: a broken model was reported as bad user input.** The two invariant checks raised the
   base class `LiengError`, and the CLI turns every `LiengError` into `Invalid input: …` with exit
   code 2. With the all-Đĩ-tie rule of lesson 02, `python -m src.cli --hand "Ks Kh Qd"
   --opponent-model range` printed `Invalid input: The calling-range model needs every canonical
   class to have a distinct strength.` and exited 2, although the user typed nothing wrong. Now both
   checks raise `ModelError` ([calling_range.py:65-68](../backend/src/calling_range.py#L65-L68)), a
   new `LiengError` subclass ([exceptions.py:37-38](../backend/src/exceptions.py#L37-L38)), and the
   CLI catches it before the catch-all ([cli.py:370-372](../backend/src/cli.py#L370-L372)): the same
   command now prints
   `Internal model error: The calling-range model needs every canonical class to have a distinct strength.`
   and exits 1, like a database problem. (With the default `random` model the CLI never builds the
   calling-range model, so it still runs and exits 0.) The API, which builds the model in
   `create_app()`, fails at start-up, which is right. Pinned by `test_rejects_a_subset_of_hands` and
   `test_rejects_classes_with_equal_strength`, which now expect `ModelError`, and by
   `test_a_broken_model_is_an_internal_error_not_invalid_input`
   ([test_cli.py:97-108](../backend/tests/test_cli.py#L97-L108)).

---

## 🧪 Try it

Run from `backend/` with the virtual environment active (see [COURSE.md](COURSE.md#setup)).

```bash
python -m pytest tests/test_calling_range.py -q
```

Expected output (the timing varies):

```
............                                                             [100%]
12 passed in 0.11s
```

The boundary and K-Q-3's card-removal row:

```bash
python -c '
from src.calling_range import CallingRangeModel
m = CallingRangeModel()
print(m._calling_boundary(0.35), m._ids[297], m._calling_boundary(0.0), m._calling_boundary(1.0))
row = m._prefix[m._index["K-Q-3"]]
print(row[-1], row[294], row[295], row[297], row[298])
'
```

Expected output:

```
(297, 0.890625) K-9-4 (455, 0.0) (0, 0.0)
18424 11778 11805 11877 11925
```

The table from section 1:

```bash
python -c '
from src.calling_range import CallingRangeModel
m = CallingRangeModel()
for cid in ["Q-K-A", "K-K-Q", "9-8-2", "K-Q-5", "K-Q-3", "K-6-6"]:
    print(f"{cid:6}", [m.equity(cid, f) for f in (0.0, 0.2, 0.35, 0.5, 0.7, 0.9)])
'
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

The cross-check with lesson 04:

```bash
python -c '
import json
from src.calling_range import CallingRangeModel
d = json.load(open("data/winrates.json"))
t = CallingRangeModel().equity_table(0.0)
print(sum(t[k] != v["equity"] for k, v in d.items()), "mismatches of", len(d))
'
```

Expected output:

```
0 mismatches of 455
```

---

## 🏋️ Exercises

Exercises marked 🟡 or 🔴 change code. Undo them afterwards with `git checkout -- <file>`.

**🟢 1. Predict.** You hold K-Q-3. How many K-K-Q combos can the opponent hold? How many 3-3-3?
Check with `row[i + 1] − row[i]` for `i = m._index["K-K-Q"]` on K-Q-3's row.

<details><summary>Solution</summary>

K-K-Q needs 2 of the 3 kings left and 1 of the 3 queens: C(3,2) × C(3,1) = **9**. 3-3-3 needs all
3 remaining threes: C(3,3) = **1**. The code agrees: K-K-Q is index 25 and its slice of K-Q-3's
row is 9; 3-3-3 is index 11 and its slice is 1.
</details>

**🟢 2. Predict.** What does `_calling_boundary(0.5)` return? Use `_cum_mult[230] = 11,020`.

<details><summary>Solution</summary>

`calling_combos = 0.5 × 22,100 = 11,050`. The last running total ≤ 11,050 is at index 230
(11,020), and class 230 has 64 combos, so `frac = (11,050 − 11,020) / 64 = 0.46875`. Answer
`(230, 0.46875)`. Class 230 is `10-3-2`, a 5-point hand: at 50% folds the opponent calls down to
about "5 points".
</details>

**🟢 3. Predict.** From which fold rate on does K-Q-3 lose every showdown that happens?
Use `_cum_mult[294] = 14,116`.

<details><summary>Solution</summary>

Once K-Q-3 is not even partially in the range: `calling_combos ≤ 14,116`, so
`f ≥ 1 − 14,116 / 22,100 ≈ 0.3613`. At `f = 0.36` K-Q-3 is the boundary class
(`(294, 0.4375)`) and only ties: equity 0.0005. At `f = 0.3613` the boundary has moved to 293 and
the equity is 0.0. Check with `m.equity("K-Q-3", 0.36)` and `m.equity("K-Q-3", 0.3613)`.
</details>

**🟡 4. Remove the partial class.** Change the last line of `_calling_boundary`
([calling_range.py:150](../backend/src/calling_range.py#L150)) to `return k, 0.0`, so the boundary
class always folds completely. Before running anything: which tests will fail? Then check with
`python -m pytest -q` and print K-Q-3 at `f` = 0.33, 0.34, 0.35.

<details><summary>Solution</summary>

`2 failed, 170 passed`: `test_medium_hands_regression` (K-Q-3 becomes 0.0072 instead of 0.0108,
K-Q-5 0.3072 instead of 0.3097) and `test_profitable_range_respects_opponent_model` in
[test_range_finder.py](../backend/tests/test_range_finder.py#L102-L109) (249 profitable classes
instead of 250). The `f = 0` cross-check still passes, because at `f = 0` nothing is partial.
K-Q-3 at 0.33/0.34/0.35 goes 0.0333, 0.0198, 0.0072 instead of 0.0349, 0.0227, 0.0108. Each value
now drops by a whole class at a time: equity becomes a step function of `f`. Undo with
`git checkout -- backend/src/calling_range.py`.
</details>

**🟡 5. Trip each invariant on purpose.** Without changing any code, build two models that the
constructor must refuse: one from `generate_all_canonical_hands()[:20]`, and one whose list still
covers all 22,100 hands but contains two equally strong classes (hint: drop `3-3-3` and add a
second `2-2-2`; both have multiplicity 4). Predict which check fires for each, then run it. Then
comment out the distinct-strength check ([calling_range.py:67-68](../backend/src/calling_range.py#L67-L68))
and run `python -m pytest tests/test_calling_range.py -q`.

<details><summary>Solution</summary>

```python
from src.calling_range import CallingRangeModel
from src.hands import generate_all_canonical_hands
hs = generate_all_canonical_hands()
two = next(h for h in hs if h.canonical_id == "2-2-2")
for hands in (hs[:20], [h for h in hs if h.canonical_id != "3-3-3"] + [two]):
    try:
        CallingRangeModel(hands)
    except Exception as err:
        print(type(err).__name__, err)
```

```
ModelError The calling-range model needs classes covering all 22100 hands.
ModelError The calling-range model needs every canonical class to have a distinct strength.
```

The first list holds only 500 combos, so the coverage check fires first. The second adds up to
22,100, passes the first check, and fails the second: two classes share 2-2-2's score tuple. With
the second check commented out, `1 failed, 11 passed`: `test_rejects_classes_with_equal_strength`
notices, and nothing else would, because every real list has distinct strengths. Undo with
`git checkout -- backend/src/calling_range.py`.
</details>

**🔴 6. A card-aware boundary.** Add `equity_card_aware(canonical_id, fold_equity)`: the opponent
calls with `(1 − f)` of the hands they *can* hold given your cards, so search the boundary on your
own row (`target = (1 − f) × row[-1]`, then `bisect_right(row, target) − 1`). Reuse `_equity_at`.
Add a test that it equals `equity` at `f = 0` and never increases with `f`. Compare both methods at
`f = 0.35`.

<details><summary>Solution</summary>

```python
    def equity_card_aware(self, canonical_id: str, fold_equity: float) -> float:
        """Like equity(), but the opponent calls with (1 - f) of the hands they can still hold."""
        if canonical_id not in self._index:
            raise UnknownHandError(f"Canonical hand '{canonical_id}' not found in calling-range model.")
        if not (0.0 <= fold_equity <= 1.0):
            raise InvalidGameParamsError(f"Fold equity must be between 0.0 and 1.0, got {fold_equity}.")
        hero = self._index[canonical_id]
        row = self._prefix[hero]
        target = (1.0 - fold_equity) * row[-1]
        k = bisect_right(row, target) - 1
        if k >= len(self._ids):
            return self._equity_at(hero, len(self._ids), 0.0)
        frac = (target - row[k]) / (row[k + 1] - row[k])
        return self._equity_at(hero, k, frac)
```

A test, in `tests/test_calling_range.py`:

```python
def test_card_aware_equity_matches_at_zero_and_never_rises(model: CallingRangeModel) -> None:
    for cid in ("Q-K-A", "K-K-Q", "K-Q-5", "K-Q-3", "K-6-6"):
        assert model.equity_card_aware(cid, 0.0) == model.equity(cid, 0.0)
        values = [model.equity_card_aware(cid, i / 100) for i in range(101)]
        assert all(b <= a + 1e-9 for a, b in itertools.pairwise(values)), cid
```

`row[k + 1] − row[k]` cannot be 0 here: `bisect_right` skips equal values. At `f = 0.35`: Q-K-A
0.9952 → 0.9953, K-K-Q 0.9394 → 0.94, K-Q-5 0.3097 → 0.314, K-Q-3 0.0108 → 0.0154, K-6-6 0.0 → 0.0.
Small differences, as weak spot 3 predicted. `173 passed`, and mypy and ruff stay clean. Undo with
`git checkout -- backend/src/calling_range.py backend/tests/test_calling_range.py`.
</details>

---

## ❓ Quiz

1. Why do the classes need to be sorted by strength before anything else?
2. What does `row[j]` in a hero's prefix row count, and why does every row end at 18,424?
3. At `f = 0.35`, which class is the boundary, and what does `frac = 0.890625` mean?
4. Why does K-Q-3 have equity 0.36 at `f = 0` but 0.0108 at `f = 0.35`?
5. Why is "`equity_table(0.0)` equals `winrates.json`" such a convincing test?

<details><summary>Answers</summary>

1. The model says the opponent folds their *weakest* hands. "Weakest" only means something on a
   strength order, and the calling range is then simply a prefix of that sorted list.
2. The number of opponent hands, given your three cards, in the `j` strongest classes. The last
   entry counts all of them: C(49, 3) = 18,424 hands left after your cards.
3. K-9-4 (index 297). The 297 stronger classes call in full (14,308 combos), and 57 of K-9-4's 64
   combos are needed to reach 14,365, so the class calls with weight 57/64.
4. At `f = 0` everyone calls, including the 6,619 hands it beats. At `f = 0.35` the opponent has
   folded almost all of those. Of 11,919.75 calling combos, K-Q-3 beats only 114.75.
5. The two numbers come from independent methods: brute-force showdowns in the generator, and
   binomial counting with prefix sums here. Agreement on all 455 classes, to four decimals, would be
   very unlikely if either had a bug.
</details>

---

## Recap

- Under the range model the opponent calls with the strongest `(1 − f) × 22,100` combos. Your
  equity is measured against those, not against a random hand.
- Step 1: sort 455 classes strongest-first and keep running totals of their sizes (`_cum_mult`).
- Step 2: for each hero class, a prefix row of card-removal counts, `∏ C(left, needed)`. Every row
  ends at 18,424.
- Step 3: `bisect_right` finds the boundary class `k` and the share `frac` of it that calls
  (`f = 0.35` → K-9-4, 57/64).
- Step 4: `(beaten + ½ tied) / calling`, all subtractions on your row, in three cases: inside the
  range, on the boundary, below it.
- `f = 0` reproduces `winrates.json` exactly, and equity never rises with `f`.
- The constructor refuses a hand list that doesn't cover 22,100 combos or has two equally strong
  classes, with a `ModelError`; bad queries raise `UnknownHandError` / `InvalidGameParamsError`.
- Fixed: the two invariants, project errors, and (since `a9d9ce9`) a broken model that the CLI
  reported as "Invalid input". Still open: `f = 1` returns 0, `f` ignores card removal, and tests
  read private state.

**Next:** [07 — Expected value](07-expected-value.md)
