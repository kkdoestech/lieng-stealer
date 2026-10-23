# Lesson 08 — The range finder

> **Goal:** understand how `range_finder.py` scores all 455 hand classes in one pass, why the
> profitable ones always form the top of its sorted list, and why "coverage" counts hands, not
> classes.
> **Files:** [`backend/src/range_finder.py`](../backend/src/range_finder.py),
> [`backend/tests/test_range_finder.py`](../backend/tests/test_range_finder.py), and its callers
> [`app.py:196-198`](../backend/app.py#L196-L198) and [`cli.py:238-240`](../backend/src/cli.py#L238-L240).
> **Time:** ~45 min. **Before this:** [07 — Expected value](07-expected-value.md).

---

## Where this fits

```
 db.py (lesson 05)                     calling_range.py (lesson 06)
 455 × equity vs a random hand         equity_table(f): 455 × equity vs the callers
            │  RANDOM                              │  RANGE
            └──────────────┬───────────────────────┘
                           ▼
            ┌──────────────────────────────────┐
 P, B, f ──►│ range_finder.py  (this lesson)   │──► 455 HandEVRecords, best EV first
            │ 455 × calculate_ev (lesson 07)   │    + coverage % of the 22,100 hands
            └──────────────────────────────────┘
                           │
          app.py /api/solve and /api/range (lesson 10)     cli.py heat map (lesson 09)
```

Lesson 07 answered "should I raise **this** hand?". The range finder answers the strategy
question: "at this pot, bet and fold rate, **which** hands should I raise at all?". A set of hands
is called a **range**. Careful with the word: lesson 06's *calling* range is the opponent's;
here it is *your* profitable range.

---

## Reading order

| # | Location | What to look for |
|---|----------|------------------|
| 1 | [range_finder.py:18-29](../backend/src/range_finder.py#L18-L29) | A constant and `HandEVRecord`, the row of the result. |
| 2 | [range_finder.py:35-47](../backend/src/range_finder.py#L35-L47) | The constructor: a hidden `load()` and a strength map. |
| 3 | [range_finder.py:49-101](../backend/src/range_finder.py#L49-L101) | `solve_range`: pick an equity source, score 455 classes, sort. |
| 4 | [range_finder.py:103-112](../backend/src/range_finder.py#L103-L112) | `get_profitable_range`: a filter (used by tests only). |
| 5 | [range_finder.py:114-134](../backend/src/range_finder.py#L114-L134) | `calculate_range_coverage`: combos, not classes. |
| 6 | [app.py:196-233](../backend/app.py#L196-L233) | How the API summarises the records. |
| 7 | [test_range_finder.py](../backend/tests/test_range_finder.py) | 6 tests: boundaries, monotonicity, the two models, tie order. |

---

## Walkthrough

### 1. The result: one record per class

📍 [`backend/src/range_finder.py:21-29`](../backend/src/range_finder.py#L21-L29)
```python
@dataclass(frozen=True)
class HandEVRecord:
    """Immutable valuation record for a canonical hand under specific game state."""
    canonical_id: str
    category: HandCategory
    equity: float
    ev: float
    multiplicity: int
    is_raise_profitable: bool
```

Every call returns 455 of these, one per class. `equity` is whichever equity the chosen opponent
model gives (random or calling range), `ev` comes from `calculate_ev` (lesson 07), and
`multiplicity` is carried along so coverage can be weighted (section 6). Like `EVResult` and
`HandStats`, it is a frozen dataclass: a result that cannot change after it is built.

### 2. Construction

📍 [`backend/src/range_finder.py:42-47`](../backend/src/range_finder.py#L42-L47)
```python
        if not db.is_loaded:
            db.load()
        self._db = db
        self._calling_model = calling_model
        # Showdown strength of each class, used to order hands whose EV and equity tie
        self._strength = {h.canonical_id: h.score.score_tuple for h in generate_all_canonical_hands()}
```

- **The database is injected**, as lesson 05 promised. The calling-range model is optional: you
  only need it for `RANGE`.
- **A hidden load.** If you pass an unloaded database, the constructor quietly loads the default
  `"data/winrates.json"` *into your object*. I checked: after `RangeFinder(WinRateDB())`, the
  database you passed has `is_loaded == True` and 455 records. That is a side effect (weak spot 2).
- **`_strength`** maps each ID to its `score_tuple` (lesson 02), for breaking ties in the sort. Building
  it means generating all 455 classes again: the whole constructor took 4.9 ms here.

### 3. `solve_range`, part 1: where does equity come from?

📍 [`backend/src/range_finder.py:71-78`](../backend/src/range_finder.py#L71-L78)
```python
        all_stats = self._db.all_items()
        records: list[HandEVRecord] = []

        range_equity: dict[str, float] | None = None
        if opponent_model is OpponentModel.RANGE:
            if self._calling_model is None:
                raise ValueError("OpponentModel.RANGE requires a CallingRangeModel.")
            range_equity = self._calling_model.equity_table(fold_equity)
```

- `all_items()` returns a copy of the 455 `HandStats` (lesson 05). Category and multiplicity always
  come from here, whatever the model.
- Under `RANGE`, the equities come from **one** `equity_table(f)` call. That finds the calling
  boundary once and then reads 455 prefix rows (lesson 06), instead of 455 separate `equity` calls.
- Under `RANDOM`, `range_equity` stays `None` and each class uses its stored `stats.equity`.

### 4. `solve_range`, part 2: score and sort

📍 [`backend/src/range_finder.py:80-101`](../backend/src/range_finder.py#L80-L101)
```python
        for cid, stats in all_stats.items():
            equity = range_equity[cid] if range_equity is not None else stats.equity
            ev = calculate_ev(
                pot=pot,
                bet_size=bet_size,
                fold_equity=fold_equity,
                win_rate_when_called=equity,
            )
            records.append(
                HandEVRecord(
                    canonical_id=cid,
                    category=stats.category,
                    equity=equity,
                    ev=ev,
                    multiplicity=stats.multiplicity,
                    is_raise_profitable=is_profitable(ev),
                )
            )

        # Sort descending by EV (highest profit first); tie-break by equity, then hand strength
        records.sort(key=lambda r: (r.ev, r.equity, self._strength[r.canonical_id]), reverse=True)
        return records
```

The loop is lesson 07's formula 455 times. The interesting line is the sort.

**Why three keys?** EV alone is not enough, because many classes can have exactly the same EV.
Take the UI defaults, `P = 100,000`, `B = 50,000`, `f = 0.35`, under the range model. The calling
range ends at K-9-4 (lesson 06), so the 157 classes below it have equity 0 and the same EV:

```
EV = 0.35 × 100,000 + 0.65 × (0 × 200,000 − 50,000) = 35,000 − 32,500 = +2,500
```

157 records with equal `ev` and equal `equity`: without a third key, their order would just be the
order they came out of the dict, which is the file's multiset order (lesson 04). The strength
tuple puts them strongest first, so the list always ends with the three weakest hands, `5-3-2`,
`4-4-2`, `4-3-3`. [test_range_finder.py:111-115](../backend/tests/test_range_finder.py#L111-L115)
pins that. The 455 strength tuples are all different (lesson 06), so the order is total and
repeatable.

`reverse=True` applies to the whole tuple: highest EV first, then highest equity, then strongest.
One full call took about 1.0 ms with `RANDOM` and 1.4 ms with `RANGE` here, well inside the
25 ms AGENTS.md §6 allows.

### 5. Why the profitable hands are always the top of the list

At a fixed `f`, every class faces the same pot, bet and fold rate. Only `w`, its equity, differs.
Rewrite lesson 07's formula as a function of `w`:

```
EV(w) = f·P − (1 − f)·B  +  (1 − f)·(P + 2B) · w
        ───────────────     ─────────────────
          same for all       positive slope (when f < 1)
```

A straight line with a positive slope: more equity always means more EV. So sorting by EV sorts by
equity, and "EV > 0" is the same as "equity above a threshold":

```
EV > 0   ⇔   w  >  ( B − f·P / (1 − f) ) / (P + 2B)
```

With `P = 100,000`:

| Bet B | f | Required w | RANDOM: classes / coverage / last + | RANGE: classes / coverage / last + |
|-------|---|-----------|--------------------------------------|-------------------------------------|
| 50,000 | 0.00 | 0.25 | 343 / 75.17% / K-6-6 | 343 / 75.17% / K-6-6 |
| 50,000 | 0.20 | 0.125 | 397 / 87.55% / J-6-5 | 318 / 69.92% / 9-7-7 |
| 50,000 | 0.35 | below 0 | 455 / 100% | 455 / 100% |
| 100,000 | 0.35 | 0.1538 | 387 / 84.65% / K-8-3 | 250 / 54.57% / K-Q-4 |

Read the rows:

- **`f = 0`: the models agree.** No folds means the calling range is every hand (lesson 06).
  K-6-6 (0.2541) is the last hand above 0.25 and Q-Q-2 (0.2473) the first below.
- **`B = 50,000`, `f = 0.35`: everything is profitable.** 35% is above the pure-bluff break-even
  of 33.3% (lesson 07), so even a hand that never wins makes +2,500.
- **The pot-sized bet is where the models split.** Against random callers, 387 classes profit.
  Against an opponent who folds their weakest 35%, only 250 do. That is the pair
  [test_range_finder.py:102-109](../backend/tests/test_range_finder.py#L102-L109) checks.

**A surprise: the top of the EV list is not always the top of the strength list.** Equity is
almost, but not exactly, ordered by strength, because of card removal. Under the range model at
`P = B = 100,000`, `f = 0.35`, K-Q-4 is profitable (equity 0.156, EV +420) while K-K-4, which is
one place *stronger*, is not (0.1538, EV −9). K-K-4 beats one more class, but holding two kings
leaves the opponent only two, so every K-x-y hand it beats has fewer combos: K-J-3, for example,
has 32 combos against K-K-4 and 48 against K-Q-4. In the end K-K-4 beats 1,821 calling combos and
K-Q-4 beats 1,843. Against random hands, I counted 72 places where a class has *more* equity than
the next-stronger one (K-K-J 0.9612 just above K-K-Q 0.961). So "the profitable range" means
"the top of the **EV** order", and that is exactly what the sort produces.

### 6. Coverage counts hands, not classes

📍 [`backend/src/range_finder.py:129-134`](../backend/src/range_finder.py#L129-L134)
```python
        if not profitable_records:
            return 0.0

        combos = sum(r.multiplicity for r in profitable_records if r.is_raise_profitable)
        coverage = (combos / TOTAL_COMBINATIONS) * 100.0
        return round(min(100.0, max(0.0, coverage)), 2)
```

"387 of 455 classes" sounds like a share of hands, but it isn't: classes have different sizes. The
coverage weights each class by its multiplicity, so it answers "what share of the hands you could
be dealt should you raise?":

| | Classes | Share of classes | Hands (combos) | Share of 22,100 |
|---|---------|------------------|----------------|-----------------|
| RANDOM, P = B = 100k, f = 0.35 | 387 | 85.05% | 18,708 | **84.65%** |
| RANGE, same | 250 | 54.95% | 12,060 | **54.57%** |
| the 13 Sáp | 13 | 2.86% | 52 | 0.24% |
| the 286 three-different-rank classes | 286 | 62.86% | 18,304 | 82.82% |

The first two rows are close by luck. The last two show how wrong counting classes can be: Sáp is
almost 3% of the classes and a quarter of a percent of the hands you will ever hold.

Notice `if r.is_raise_profitable` inside the sum: the function filters again, so passing *all*
455 records gives the same 84.65% (weak spot 5).

### 7. How the callers use the records

📍 [`backend/app.py:196-198`](../backend/app.py#L196-L198)
```python
    records = range_finder.solve_range(pot, bet_size, fold_equity, params.opponent_model)
    profitable_records = [r for r in records if r.is_raise_profitable]
    coverage = range_finder.calculate_range_coverage(profitable_records)
```

The API filters by itself instead of calling `get_profitable_range` (which would solve the range a
second time). Then it sends the first 30 records as `top_hands`
([app.py:211](../backend/app.py#L211)), the last profitable record as `threshold_hand`
([app.py:231](../backend/app.py#L231)), and per-category totals built by `_category_breakdown`
([app.py:118](../backend/app.py#L118)). Because the profitable records are a prefix of the EV
order, `profitable_records[-1]` is the lowest-EV hand still worth raising: K-Q-4 in the range
example above, not the weakest hand by strength. The CLI does the same at
[cli.py:238-240](../backend/src/cli.py#L238-L240), and lesson 09 draws the result as a heat map.

---

## 💡 Concept: sorting with a tuple key

`list.sort(key=...)` calls the key function once per item and sorts by the results. When the key
is a tuple, Python compares tuples **element by element**, left to right: the second element only
matters when the first ones are equal, and so on.

```python
rows = [(2500.0, 0.0, "weak"), (2500.0, 0.0, "strong"), (165000.0, 1.0, "nuts")]
rows.sort(reverse=True)    # [(165000.0, 1.0, 'nuts'), (2500.0, 0.0, 'weak'), (2500.0, 0.0, 'strong')]
```

Here the strings sort alphabetically, which is why the real code uses `score_tuple` (lesson 02)
as the third element: a tuple of numbers whose order *is* hand strength. `reverse=True` flips the
whole comparison, so every element is "biggest first".

---

## Design decisions

- **Score everything, every time.** 455 EV calculations cost about a millisecond, so there is no
  cache and no incremental update. Simple code, always consistent with the inputs.
- **One equity table per call under `RANGE`.** The boundary search is done once, not 455 times.
- **Return every record, sorted.** Callers slice what they need (top 30, the profitable prefix,
  categories). The alternative, returning only the profitable ones, would lose the "just below the
  line" hands the UI shows.
- **A total order.** The strength tie-break makes the output deterministic even when 157 classes
  share one EV, which keeps tests and the UI stable.
- **Coverage weighted by multiplicity.** It is the honest answer to "how often will I raise?",
  because you are dealt hands, not classes.

---

## ⚠️ Weak spots

1. **`TOTAL_COMBINATIONS` is defined twice.** [range_finder.py:18](../backend/src/range_finder.py#L18)
   and [calling_range.py:24](../backend/src/calling_range.py#L24), and 22,100 also appears as a
   literal in `app.py` and `cli.py` (lesson 10). *Fix:* define it once and import it (exercise 4).
2. **The constructor loads the database as a side effect.**
   [range_finder.py:42-43](../backend/src/range_finder.py#L42-L43) calls `db.load()` with the
   relative default path and mutates the object it was given. It also defeats the guard in
   `app.py` (lesson 10): a missing file fails here, at import time. *Fix:* raise
   `DatabaseNotLoadedError` and let the caller decide (exercise 5).
3. **`get_profitable_range` is used only by tests.**
   [range_finder.py:103-112](../backend/src/range_finder.py#L103-L112): `app.py` and `cli.py`
   filter the records themselves. It is fine as a convenience, but it means the tests exercise a
   path production never takes.
4. **Only the 455 real IDs can be sorted.** `_strength` comes from `generate_all_canonical_hands`
   ([range_finder.py:47](../backend/src/range_finder.py#L47)), so a database with any other key
   fails with `KeyError` at [range_finder.py:100](../backend/src/range_finder.py#L100). Lesson 05,
   exercise 6 hits this with a fake database. Under `RANGE`, `range_equity[cid]` at
   [:81](../backend/src/range_finder.py#L81) has the same problem. *Fix:* take the strength from
   the injected data, or validate the key set once in `__init__`.
5. **`calculate_range_coverage` filters twice.** Its parameter is called `profitable_records`,
   but [range_finder.py:132](../backend/src/range_finder.py#L132) re-checks
   `is_raise_profitable`, and the `min`/`max` clamp can never change a sum of positive counts
   below 22,100. Harmless, but it hides what the function expects. *Fix:* accept all records and
   rename it, or drop the inner filter.
6. **Nobody checks the inputs here.** `P`, `B` and `f` are validated only inside `calculate_ev`
   (lesson 07) on the first record, or by `equity_table` under `RANGE`, so the error message talks
   about EV, not about the range. Minor, since `app.py` validates first.

---

## 🧪 Try it

Run from `backend/` with the virtual environment active (see [COURSE.md](COURSE.md#setup)).

```bash
python -m pytest tests/test_range_finder.py -q
```

Expected output (the timing varies):

```
......                                                                   [100%]
6 passed in 0.10s
```

Both models with a pot-sized bet, with the last profitable hand and the first one out:

```bash
python -c '
from src.calling_range import CallingRangeModel, OpponentModel
from src.db import WinRateDB
from src.range_finder import RangeFinder
rf = RangeFinder(WinRateDB("data/winrates.json"), CallingRangeModel())
for model in (OpponentModel.RANDOM, OpponentModel.RANGE):
    records = rf.solve_range(100000.0, 100000.0, 0.35, model)
    profitable = [r for r in records if r.is_raise_profitable]
    cut, first_out = profitable[-1], records[len(profitable)]
    print(model.value, len(profitable), rf.calculate_range_coverage(profitable),
          (cut.canonical_id, cut.equity, cut.ev), (first_out.canonical_id, first_out.equity, first_out.ev))
'
```

Expected output:

```
random 387 84.65 ('K-8-3', 0.1557, 361.5) ('K-7-4', 0.1533, -106.5)
range 250 54.57 ('K-Q-4', 0.156, 420.0) ('K-K-4', 0.1538, -9.0)
```

The tie-break at the UI defaults (half-pot bet, range model):

```bash
python -c '
from src.calling_range import CallingRangeModel, OpponentModel
from src.db import WinRateDB
from src.range_finder import RangeFinder
rf = RangeFinder(WinRateDB("data/winrates.json"), CallingRangeModel())
records = rf.solve_range(100000.0, 50000.0, 0.35, OpponentModel.RANGE)
for r in records[:2] + records[-3:]:
    print(r.canonical_id, r.equity, r.ev, r.is_raise_profitable)
'
```

Expected output:

```
A-A-A 1.0 132500.0 True
K-K-K 0.9997 132461.0 True
5-3-2 0.0 2500.0 True
4-4-2 0.0 2500.0 True
4-3-3 0.0 2500.0 True
```

---

## 🏋️ Exercises

Exercises marked 🟡 or 🔴 change code. Undo them afterwards with `git checkout -- <file>`.

**🟢 1. Predict.** At `P = 100,000`, `B = 50,000`, `f = 0.35`, how many classes are profitable
under each model, and what is the EV of 4-3-3 under each? Check with `solve_range`.

<details><summary>Solution</summary>

All 455 under both: the fold part alone pays for a pure bluff, because 0.35 is above
`B / (P + B) = 0.333`. Under `RANGE` 4-3-3 has equity 0 and EV `35,000 − 32,500 = 2,500`. Under
`RANDOM` its equity is 0.0001, so the EV is 2,513.
</details>

**🟢 2. Predict.** If only the 13 Sáp classes were profitable, what would
`calculate_range_coverage` return?

<details><summary>Solution</summary>

13 classes × 4 combos = 52 hands, `52 / 22,100 × 100 = 0.235…`, rounded to **0.24**. Check:
`rf.calculate_range_coverage([r for r in rf.solve_range(1e5, 5e4, 0.0) if r.category.name == "SAP"])`.
</details>

**🟢 3. Predict.** Under `RANDOM` at `P = B = 100,000`, `f = 0.35`, is the profitable set exactly
the 387 strongest classes? Under `RANGE`, is it exactly the 250 strongest?

<details><summary>Solution</summary>

Under `RANDOM`, yes, here. Under `RANGE`, no: K-Q-4 (strength index 250) is in and K-K-4 (index
249) is out, for the card-removal reason in section 5. In both cases the set is exactly the top of
the EV-sorted list, which is what the code relies on. Check by comparing
`{r.canonical_id for r in records if r.is_raise_profitable}` with `set(CallingRangeModel()._ids[:250])`.
</details>

**🟡 4. One constant.** Delete `TOTAL_COMBINATIONS` from
[range_finder.py:18](../backend/src/range_finder.py#L18) and import it from `calling_range`
instead. Will [test_range_finder.py:15](../backend/tests/test_range_finder.py#L15), which imports
it from `range_finder`, still work? Check with `python -m pytest -q`.

<details><summary>Solution</summary>

```python
from src.calling_range import TOTAL_COMBINATIONS, CallingRangeModel, OpponentModel
```

and remove `Final` from the `typing` import. The test import still works: a name imported into a
module is an attribute of that module, so `from src.range_finder import TOTAL_COMBINATIONS` finds
it. (The test never uses it, so it is an unused import there anyway.) All tests pass.
</details>

**🟡 5. No hidden load.** Replace [range_finder.py:42-43](../backend/src/range_finder.py#L42-L43)
with a `DatabaseNotLoadedError` (import it from `src.exceptions`). Which tests break? What would
change in `app.py` if `data/winrates.json` were missing?

<details><summary>Solution</summary>

```python
        if not db.is_loaded:
            raise DatabaseNotLoadedError("RangeFinder needs a loaded WinRateDB.")
```

No test breaks: every fixture passes a loaded database. In `app.py`, a missing file now fails at
import with "RangeFinder needs a loaded WinRateDB" instead of a `DatabaseError` from the hidden
`load()`. Either way the app cannot start without the file, which is lesson 10's point about the
`if DB_PATH.is_file()` guard.
</details>

**🔴 6. Prove the threshold.** Add `required_equity(pot, bet_size, fold_equity)` to
`range_finder.py` (the formula in section 5, for `f < 1`). Then add a parametrized test: for
`B` in {50,000, 100,000, 300,000} and `f` in {0, 0.1, 0.2, 0.3, 0.5}, every record under `RANDOM`
is profitable exactly when its equity is above the threshold. Check with `python -m pytest -q`.

<details><summary>Solution</summary>

```python
def required_equity(pot: float, bet_size: float, fold_equity: float) -> float:
    """Smallest equity when called for which raising is +EV (fold_equity < 1)."""
    return (bet_size - fold_equity * pot / (1.0 - fold_equity)) / (pot + 2.0 * bet_size)
```

```python
@pytest.mark.parametrize("bet", [50000.0, 100000.0, 300000.0])
@pytest.mark.parametrize("fold", [0.0, 0.1, 0.2, 0.3, 0.5])
def test_random_model_cut_is_an_equity_threshold(loaded_finder: RangeFinder, bet: float, fold: float) -> None:
    need = required_equity(100000.0, bet, fold)
    for r in loaded_finder.solve_range(100000.0, bet, fold):
        assert r.is_raise_profitable == (r.equity > need), (r.canonical_id, r.equity, need)
```

That adds 15 cases. With exercises 4, 5 and 6 together, the whole suite gave 108 passed.
`required_equity(100000, 100000, 0.35)` is 0.1538…, which is why K-K-4 (0.1538) misses by EV −9.
</details>

---

## ❓ Quiz

1. Why does `solve_range` call `equity_table` once instead of `equity` 455 times?
2. At `P = 100,000`, `B = 50,000`, `f = 0.35` under `RANGE`, 157 classes share one EV. Which one?
   What decides their order?
3. Why are the profitable records always a prefix of the sorted list?
4. Why can a stronger hand (K-K-4) be unprofitable while a weaker one (K-Q-4) is profitable?
5. Why is coverage 84.65% and not 387 / 455 = 85.05%?

<details><summary>Answers</summary>

1. `equity_table` finds the calling boundary once (one binary search) and then reads 455 prefix
   rows. 455 `equity` calls would repeat the boundary search 455 times.
2. +2,500: equity 0, so `EV = 0.35 × 100,000 − 0.65 × 50,000`. Equal EV and equal equity leave the
   strength tuple as the deciding key, so they are listed strongest first and 4-3-3 is last.
3. At a fixed `f`, EV is a straight line in equity with a positive slope, so higher equity means
   higher EV. The sort is by EV first, so every +EV record comes before every other.
4. Card removal. Holding two kings leaves the opponent fewer K-x-y hands, which are exactly the
   hands K-K-4 would beat. It beats 1,821 calling combos, K-Q-4 beats 1,843.
5. Coverage counts hands: the 387 classes hold 18,708 of the 22,100 combos. Classes have 4, 24 or
   64 combos, so a share of classes is not a share of hands.
</details>

---

## Recap

- `solve_range` turns `(P, B, f, model)` into 455 `HandEVRecord`s: equity from the database or one
  `equity_table`, EV from lesson 07, sorted by `(ev, equity, strength)`.
- The strength tie-break makes the order total, even when 157 classes share EV +2,500.
- At a fixed `f`, EV rises with equity, so the profitable hands are the top of the EV order. Card
  removal means that is not always the top of the strength order (K-Q-4 in, K-K-4 out).
- Pot-sized bet, `f = 0.35`: 387 classes / 84.65% against random callers, 250 / 54.57% against a
  calling range. A half-pot bet at the same `f` makes all 455 profitable.
- Coverage is weighted by multiplicity: hands, not classes.
- Weak spots: a duplicated constant, a hidden `load()`, a test-only method, a hard dependency on
  the 455 real IDs, a double filter.

**Next:** [09 — The command-line interface](09-cli.md)
