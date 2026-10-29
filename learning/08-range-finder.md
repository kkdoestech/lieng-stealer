# Lesson 08 — The range finder

> **Goal:** understand how `range_finder.py` scores all 455 hand classes in one pass, why the
> profitable ones always form the top of its sorted list, why "coverage" counts hands, not
> classes, and how each class leaves with a bet-size recommendation already attached.
> **Files:** [`backend/src/range_finder.py`](../backend/src/range_finder.py),
> [`backend/tests/test_range_finder.py`](../backend/tests/test_range_finder.py), and its callers
> [`app.py:480-522`](../backend/app.py#L480-L522) and [`cli.py:347-385`](../backend/src/cli.py#L349-L387).
> **Time:** ~50 min. **Before this:** [07 — Expected value](07-expected-value.md).

---

## Where this fits

```
 db.py (lesson 05)                     calling_range.py (lesson 06)
 455 × equity vs a random hand         equity_table(f): 455 × equity vs the callers
            │  RANDOM                              │  RANGE
            └──────────────┬───────────────────────┘
                           ▼
            ┌──────────────────────────────────┐
 P, f ─────►│ range_finder.py  (this lesson)   │──► 455 HandEVRecords, best EV first
            │ 455 × (calculate_ev + recommend) │    + advice per class + coverage %
            └──────────────────────────────────┘
                           │
          app.py /api/solve and /api/range (lesson 10)     cli.py heat map (lesson 09)
```

Lesson 07 answered "should I bet **this** hand, and how much?". The range finder answers the strategy
question: "at this pot and fold rate, **which** hands bet, and how much, across the whole range?". A set
of hands is called a **range**. Careful with the word: lesson 06's *calling* range is the opponent's;
here it is *your* range.

---

## Reading order

| # | Location | What to look for |
|---|----------|------------------|
| 1 | [range_finder.py:24-38](../backend/src/range_finder.py#L24-L38) | `HandEVRecord`, the row of the result, advice included. |
| 2 | [range_finder.py:41-99](../backend/src/range_finder.py#L41-L99) | `OpponentEquities` (the request's one equity source) and `HandSolution`. |
| 3 | [range_finder.py:102-121](../backend/src/range_finder.py#L102-L121) | The constructor: refuse an unloaded database, build a strength map. |
| 4 | [range_finder.py:123-144](../backend/src/range_finder.py#L123-L144) | `equities`: build the one equity source a request uses. |
| 5 | [range_finder.py:146-183](../backend/src/range_finder.py#L146-L183) | `fold_cells`: the three fold-rate cells the advice ladder is priced in. |
| 6 | [range_finder.py:185-232](../backend/src/range_finder.py#L185-L232) | `solve_range`: score 455 classes from that source, attach the advice, sort. |
| 7 | [range_finder.py:234-268](../backend/src/range_finder.py#L234-L268) | `hand_solution`: the hand IS a row of that table. |
| 8 | [range_finder.py:270-278](../backend/src/range_finder.py#L270-L278) | `_equity_scan`: the `equity_at` function the zone scan needs. |
| 9 | [range_finder.py:291-311](../backend/src/range_finder.py#L291-L311) | `calculate_range_coverage`: combos, not classes. |
| 10 | [range_finder.py:307-326](../backend/src/range_finder.py#L307-L326) | `CategorySummary` and `category_breakdown()`: per-category totals for the API and the CLI. |
| 11 | [advice.py](../backend/src/advice.py) | The policy that turns the three cells into one size (lesson 07, section 8). |
| 12 | [sensitivity.py](../backend/src/sensitivity.py) | The fold-rate assumption stress grid behind `sensitivity`: vary the fold rate, report the range it implies. |
| 13 | [app.py:480-522](../backend/app.py#L480-L522) | How the API summarises the records (`_solve`) and the four 3.0.0 summary fields. |
| 14 | [test_range_finder.py](../backend/tests/test_range_finder.py) | Tests: boundaries, monotonicity, the two models, tie order, one-answer-per-hand identity, the fold cells, category totals. |

---

## Walkthrough

### 1. The result: one record per class

📍 [`backend/src/range_finder.py:25-38`](../backend/src/range_finder.py#L25-L38)
```python
class HandEVRecord:
    """Immutable valuation record for a canonical hand under specific game state.

    ``ev`` is the EV at the caller's ``bet_size``; ``advice`` is what the policy says to do with
    the ladder.
    """

    canonical_id: str
    category: HandCategory
    equity: float
    ev: float
    multiplicity: int
    is_raise_profitable: bool
    advice: Recommendation
```

Every call returns 455 of these, one per class. `equity` is whichever equity the chosen opponent
model gives (random or calling range), `ev` comes from `calculate_ev` (lesson 07), `advice` is the
`Recommendation` from `advice.py` (lesson 07 again), and `multiplicity` is carried along so coverage
can be weighted (section 6). Like `EVResult` and `HandStats`, it is a frozen dataclass: a result that
cannot change after it is built.

### 2. Construction

📍 [`backend/src/range_finder.py:112-117`](../backend/src/range_finder.py#L112-L117)
```python
        if not db.is_loaded:
            raise DatabaseNotLoadedError("RangeFinder needs a loaded WinRateDB; call db.load() first.")
        self._db = db
        self._calling_model = calling_model
        # Showdown strength of each class, used to order hands whose EV and equity tie
        self._strength = {h.canonical_id: h.score.score_tuple for h in generate_all_canonical_hands()}
```

- **The database is injected, and it must already be loaded**, as lesson 05 promised. The
  constructor never touches the filesystem: `RangeFinder(WinRateDB())` raises
  `DatabaseNotLoadedError: RangeFinder needs a loaded WinRateDB; call db.load() first.`, and the
  database you passed is still unloaded afterwards. Loading is the caller's job: `create_app()`
  loads `DEFAULT_DB_PATH` ([app.py:135-136](../backend/app.py#L135-L136)), and the CLI builds
  `WinRateDB(db_path)` ([cli.py:260](../backend/src/cli.py#L260)), whose constructor loads the
  file. (An older version loaded a relative default path into your object here; see weak spot 2.)
- The calling-range model is optional: you only need it for `RANGE`.
- **`_strength`** maps each ID to its `score_tuple` (lesson 02), for breaking ties in the sort. Building
  it means generating all 455 classes again: the whole constructor took about 3 ms here.

### 3. `solve_range`, part 1: where does equity come from?

📍 [`backend/src/range_finder.py:119-140`](../backend/src/range_finder.py#L119-L140)
```python
    def equities(self, fold_equity: float, opponent_model: OpponentModel) -> OpponentEquities:
        """Build the 455-class equity table for this request.

        Args:
            fold_equity: Opponent fold frequency in [0.0, 1.0]. Under RANGE it also fixes the
                calling set: the strongest ``(1 - fold_equity) * 22,100`` pre-deal combinations.
            opponent_model: RANDOM (equity vs one random hand) or RANGE (equity when called).

        Returns:
            The 455 equities and the fold rate they belong to.

        Raises:
            ModelError: If RANGE is requested and no CallingRangeModel was injected.
            InvalidGameParamsError: If fold_equity is outside [0.0, 1.0] (also a ValueError).
        """
        if opponent_model is OpponentModel.RANGE:
            if self._calling_model is None:
                raise ModelError("OpponentModel.RANGE requires a CallingRangeModel.")
            return OpponentEquities(opponent_model, fold_equity, self._calling_model.equity_table(fold_equity))
        return OpponentEquities(
            opponent_model, fold_equity, {cid: stats.equity for cid, stats in self._db.all_items().items()}
        )
```

- `all_items()` returns a copy of the 455 `HandStats` (lesson 05). Category and multiplicity always
  come from here, whatever the model.
- Under `RANGE`, the equities come from **one** `equity_table(f)` call. That finds the calling
  boundary once and then reads 455 prefix rows (lesson 06), instead of 455 separate `equity` calls.
- Under `RANDOM`, `range_equity` stays `None` and each class uses its stored `stats.equity`.
- `RANGE` on a finder built without a `CallingRangeModel` is a setup bug, not bad input, so it
  raises `ModelError` (weak spot 7).

### 4. `solve_range`, part 2: score and sort

📍 [`backend/src/range_finder.py:180-227`](../backend/src/range_finder.py#L180-L227)
```python
    def solve_range(
        self,
        pot: float,
        bet_size: float,
        equities: OpponentEquities,
        thresholds: AdviceThresholds = DEFAULT_THRESHOLDS,
    ) -> list[HandEVRecord]:
        """Evaluate and rank all 455 canonical hands sorted descending by EV.

        Args:
            pot: Dead pot size before hero's bet (must be > 0).
            bet_size: Additional bet / raise amount (must be > 0).
            equities: The equities to value every class under; it also carries the fold rate the
                EV formula uses.
            thresholds: The advice policy's numbers.

        Returns:
            List of all 455 HandEVRecord instances sorted by EV descending.

        Raises:
            ModelError: If the equities came from RANGE and no CallingRangeModel was injected.
        """
        fold_equity = equities.fold_equity
        board = self.fold_cells(fold_equity, equities.opponent_model)
        records: list[HandEVRecord] = []
        for cid, stats in self._db.all_items().items():
            equity = equities.of(cid)
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
                    advice=recommend(pot, FoldCell(fold_equity, equity), board[cid], thresholds),
                )
            )

        # Sort descending by EV (highest profit first); tie-break by equity, then hand strength
        records.sort(key=lambda r: (r.ev, r.equity, self._strength[r.canonical_id]), reverse=True)
        return records
```

Three things happen per class now, not two. `calculate_ev` prices your `bet_size`, which is the row's
`ev`. `recommend` prices the three rungs in the advice ladder, using `board[cid]`: the equity of that
class in the centre fold cell and in the two cells ±0.10 away, built once for all 455 classes by
`fold_cells` before the loop. Under `RANGE` that helper reads one equity table per cell; under
`RANDOM` a class has the same equity in every cell, so the three cells carry the same number. The
centre cell is exactly `equities.of(cid)`, which is what keeps the ladder and the reported equity on
one source.

`fold_cells` ([range_finder.py:146-183](../backend/src/range_finder.py#L146-L183)) is the new piece
lesson 07's policy needs: three fold rates in, 455 rows of `FoldCell` pairs out. It costs three
`equity_table` reads under `RANGE`, not 455 × 3 single lookups.

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
One full call took about 1.0 ms with `RANDOM` and 1.5 ms with `RANGE` here, well inside the
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

📍 [`backend/src/range_finder.py:298-303`](../backend/src/range_finder.py#L298-L303)
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

`TOTAL_COMBINATIONS` is `math.comb(52, 3)`, computed once in
[hands.py:33](../backend/src/hands.py#L33) and re-exported at
[range_finder.py:17](../backend/src/range_finder.py#L17). The `import X as X` form tells `ruff` and
`mypy` that the name is meant to be imported from this module too.

Notice `if r.is_raise_profitable` inside the sum: the function filters again, so passing *all*
455 records gives the same 84.65% (weak spot 5).

### 7. How the callers use the records

📍 [`backend/app.py:475-517`](../backend/app.py#L475-L517)
```python
def _solve(services: Services, params: GameParams) -> tuple[OpponentEquities, list[HandEVRecord], Json]:
    """Score all 455 classes; return the equities, the records, and the summary."""

    equities = services.range_finder.equities(params.fold_equity, params.opponent_model)
    records = services.range_finder.solve_range(
        params.pot, params.bet_size, equities, services.advice_thresholds
    )
    profitable = [r for r in records if r.is_raise_profitable]
    betting = [r for r in records if r.advice.action is not Action.CHECK]
    summary: Json = {
        "pot": params.pot,
        "bet_size": params.bet_size,
        "fold_equity": params.fold_equity,
        "opponent_model": params.opponent_model.value,
        "call_range_percent": equities.calling_percentile,
        "final_pot": final_pot(params.pot, params.bet_size),
        "pure_bluff_break_even_fold_equity": calculate_break_even_fold_equity(params.pot, params.bet_size, 0.0),
        "total_canonical_classes": len(records),
        "profitable_classes": len(profitable),
        "total_combinations": TOTAL_COMBINATIONS,
        "profitable_combinations": sum(r.multiplicity for r in profitable),
        "range_coverage_percent": services.range_finder.calculate_range_coverage(profitable),
        "action_counts": _action_counts(records),
        "bet_recommended_percent": round(
            sum(r.multiplicity for r in betting) / TOTAL_COMBINATIONS * 100.0, 2
        ),
        "bet_ladder": list(ladder(params.pot, services.advice_thresholds)),
        "sizing": _sizing_payload(services.advice_thresholds, params.pot),
        "highest_ev_hand": records[0].canonical_id if records else None,
        "highest_ev_value": records[0].ev if records else None,
        "threshold_hand": profitable[-1].canonical_id if profitable else None,
        "threshold_ev_value": profitable[-1].ev if profitable else None,
        "category_breakdown": [
            {
                "category": row.category.name,
                "classes": row.classes,
                "combos": row.combos,
                "profitable_combos": row.profitable_combos,
            }
            for row in category_breakdown(records)
        ],
    }
    return equities, records, summary
```

`_solve` is shared by `/api/solve`, `/api/range` and `/api/analyze` (lesson 10). It filters
by itself instead of calling `get_profitable_range` (which would solve the range a second time).
Because the profitable records are a prefix of the EV order, `profitable[-1]` is the lowest-EV hand
still worth raising: K-Q-4 in the range example above, not the weakest hand by strength. For
`P = B = 100,000`, `f = 0.35`, `opponent_model: "range"`, `/api/range` answers with (among
other fields):

```json
"profitable_classes": 250,
"profitable_combinations": 12060,
"range_coverage_percent": 54.57,
"action_counts": {"ALL_IN": 54, "CHECK": 128, "LARGE_BET": 98, "SMALL_BET": 175},
"bet_recommended_percent": 71.62,
"bet_ladder": [33000.0, 75000.0, 100000.0],
"highest_ev_hand": "A-A-A",
"highest_ev_value": 165000.0,
"threshold_hand": "K-Q-4",
"threshold_ev_value": 420.0,
```

The four 3.0.0 additions read differently on purpose. `profitable_classes` and
`range_coverage_percent` still answer "where is EV above zero at `bet_size`". `action_counts` and
`bet_recommended_percent` answer "what does the policy recommend", which is a different count: 128
classes check here, they stand for 6,272 of the 22,100 hands, and the other 15,828 are 71.62%. The
four counts always add up to 455, and `_action_counts` ([app.py:472-477](../backend/app.py#L472-L477))
builds them from the records, not from a second scan. `bet_ladder` and `sizing` are the pot's ladder
and the effective thresholds, so a client never has to hard-code either.

The rest of the summary is `category_breakdown` ([app.py:512-520](../backend/app.py#L512-L520)),
one row per category, built by shared code in this module:

📍 [`backend/src/range_finder.py:306-326`](../backend/src/range_finder.py#L306-L326)
```python
@dataclass(frozen=True)
class CategorySummary:
    """How many classes and combinations of one hand category exist, and how many are profitable."""
    category: HandCategory
    classes: int
    combos: int
    profitable_combos: int


def category_breakdown(records: Sequence[HandEVRecord]) -> list[CategorySummary]:
    """Summarize classes, combos, and profitable combos per hand category (strongest first)."""
    breakdown = []
    for category in sorted(HandCategory, reverse=True):
        members = [r for r in records if r.category is category]
        breakdown.append(CategorySummary(
            category=category,
            classes=len(members),
            combos=sum(r.multiplicity for r in members),
            profitable_combos=sum(r.multiplicity for r in members if r.is_raise_profitable),
        ))
    return breakdown
```

`sorted(HandCategory, reverse=True)` gives Sáp, Liêng, Đĩ, Điểm (lesson 02). In the range example
every Sáp, Liêng and Đĩ combo is profitable and 11,096 of the 21,136 Điểm combos are.
[test_range_finder.py:125-131](../backend/tests/test_range_finder.py#L125-L131) pins the class and
combo totals (13/52, 12/768, 6/144, 424/21,136). This function used to live in `app.py`, with a
second hand-written copy in `cli.py`; now both import it.

Finally, `_top_hands_payload` ([app.py:544-558](../backend/app.py#L544-L558)) sends the first
`TOP_HANDS_LIMIT = 30` records as `top_hands`, each with `showdown_equity` (the record's `equity`) and
the advice's `action`, `kind` and `amount`. A row carries those three instead of the 2.0.0
`is_profitable` and `decision`, because a table of hands is only useful when it says what to do with
each one. The CLI draws the same records as a heat map at
[cli.py:308-336](../backend/src/cli.py#L308-L336), and lesson 09 walks through it.

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

1. ✅ **Fixed: `TOTAL_COMBINATIONS` was defined twice.** `range_finder.py` and `calling_range.py`
   each typed `22100`, and the literal also appeared in `app.py` and `cli.py`. Now it is
   `math.comb(52, 3)` in one place, [hands.py:33](../backend/src/hands.py#L33); `range_finder.py:17`
   and [calling_range.py:25](../backend/src/calling_range.py#L25) re-export it, and `app.py` and
   `cli.py` import it. Pinned by `test_state_space_constants_are_computed`
   ([test_hands.py:127-131](../backend/tests/test_hands.py#L127-L131)); exercise 4 shows what else
   notices a wrong value.
2. ✅ **Fixed: the constructor loaded the database as a side effect.** It used to call `db.load()`
   with the relative default path and mutate the object it was given, so a missing file failed
   inside `RangeFinder`, at import time. Now it raises `DatabaseNotLoadedError`
   ([range_finder.py:46-47](../backend/src/range_finder.py#L46-L47)) and the caller loads: the app
   factory fails fast with a `DatabaseError` if the file is missing (lesson 10). Pinned by
   `test_requires_a_loaded_database`
   ([test_range_finder.py:119-123](../backend/tests/test_range_finder.py#L119-L123)); exercise 5
   puts the old line back.
3. **`get_profitable_range` is used only by tests.**
   [range_finder.py:107-116](../backend/src/range_finder.py#L107-L116): `app.py` and `cli.py`
   filter the records themselves. It is fine as a convenience, but it means the tests exercise a
   path production never takes.
4. **Only the 455 real IDs can be sorted (mostly fixed elsewhere).** `_strength` comes from
   `generate_all_canonical_hands` ([range_finder.py:51](../backend/src/range_finder.py#L51)), so a
   database with any other key would fail with `KeyError` at
   [range_finder.py:104](../backend/src/range_finder.py#L104), and under `RANGE` at
   `range_equity[cid]` ([:85](../backend/src/range_finder.py#L85)). A real `WinRateDB` can no longer
   hold such a key: `load()` now refuses any file that is not exactly the 455 classes
   ([db.py:163-176](../backend/src/db.py#L163-L176), lesson 05). Only a hand-made stand-in object
   can still hit the `KeyError`. *Fix, if you want it here too:* check the key set once in
   `__init__`.
5. **`calculate_range_coverage` filters twice.** Its parameter is called `profitable_records`,
   but [range_finder.py:136](../backend/src/range_finder.py#L136) re-checks
   `is_raise_profitable`, and with a correct constant the `min`/`max` clamp can never change a
   sum of positive counts below 22,100 (exercise 4 shows the one case where it hides a bug).
   Harmless, but it hides what the function expects. *Fix:* accept all records and
   rename it, or drop the inner filter.
6. **Nobody checks the inputs here.** `P`, `B` and `f` are validated only inside `calculate_ev`
   (lesson 07) on the first record, or by `equity_table` under `RANGE`, so the error message talks
   about EV, not about the range. Minor, since `app.py` and `cli.py` validate first, and the error
   is an `InvalidGameParamsError` either way.
7. ✅ **Fixed: `RANGE` without a calling-range model raised a bare `ValueError`.** That is not a
   project error type, and it reads like bad input: a caller that reports `ValueError` as the
   user's mistake (the CLI does, with exit 2) would blame the user for a setup bug. Now it raises
   `ModelError` ([range_finder.py:80-81](../backend/src/range_finder.py#L80-L81)), the project's error for a
   missing or inconsistent model ([exceptions.py:37-38](../backend/src/exceptions.py#L37-L38)),
   which the CLI reports as "Internal model error" with exit 1 (lesson 09). Pinned by
   `test_range_model_without_calling_model_is_a_model_error`
   ([test_range_finder.py:134-138](../backend/tests/test_range_finder.py#L134-L138)).

---

## 🧪 Try it

Run from `backend/` with the virtual environment active (see [COURSE.md](COURSE.md#setup)).

```bash
python -m pytest tests/test_range_finder.py -q
```

Expected output (the timing varies):

```
.........                                                                [100%]
9 passed in 0.13s
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

**🟡 4. Break the one constant.** Weak spot 1 was fixed by computing `TOTAL_COMBINATIONS` once in
[hands.py:33](../backend/src/hands.py#L33). Make it wrong on purpose: `math.comb(52, 3) - 1`. Before
you run `python -m pytest tests/test_range_finder.py tests/test_hands.py -q`, predict: which tests
notice, and does `test_pure_fold_equity_100_percent` (coverage must be exactly 100.0) fail?

<details><summary>Solution</summary>

```
FAILED tests/test_hands.py::TestCanonicalHandSafety::test_state_space_constants_are_computed
ERROR tests/test_range_finder.py::TestOpponentModels::test_profitable_range_respects_opponent_model
ERROR tests/test_range_finder.py::TestOpponentModels::test_equal_ev_hands_are_ordered_strongest_first
1 failed, 14 passed, 2 errors in 0.17s
```

The two errors happen while building the `finder_with_model` fixture:
`CallingRangeModel()` now checks that its classes cover every hand and stops with
`ModelError: The calling-range model needs classes covering all 22099 hands.` The coverage test
**passes**: 22,100 / 22,099 × 100 is 100.0045, and the `min(100.0, …)` clamp in
`calculate_range_coverage` rounds it back to 100.0. So the clamp that weak spot 5 calls useless
does matter in one case: it hides a bug. Because there is one constant, every user of it was wrong
together, and the calling-range check caught it. Undo it with `git checkout -- backend/src/hands.py`.
</details>

**🟡 5. Put the hidden load back.** Weak spot 2 was fixed at
[range_finder.py:46-47](../backend/src/range_finder.py#L46-L47). Replace the `raise` line with the
old `db.load()`. Which test fails, and what does `ruff check src/range_finder.py` say?

<details><summary>Solution</summary>

```
E       Failed: DID NOT RAISE DatabaseNotLoadedError
FAILED tests/test_range_finder.py::TestConstructionAndSummaries::test_requires_a_loaded_database
1 failed, 8 passed in 0.13s
```

Only the new test notices, because every other fixture passes a loaded database. `ruff` reports
`F401 [*] `src.exceptions.DatabaseNotLoadedError` imported but unused`. That is two independent
alarms for one regression: the test pins the behaviour, the linter notices the dead import. In
`app.py` nothing would change: `create_app()` loads the database itself before it builds the
`RangeFinder`, so the hidden load would never run there. Undo it with
`git checkout -- backend/src/range_finder.py`.
</details>

**🔴 6. Prove the threshold.** Add `required_equity(pot, bet_size, fold_equity)` to
`range_finder.py` (the formula in section 5, for `f < 1`). Then add a parametrized test: for
`B` in {50,000, 100,000, 300,000} and `f` in {0, 0.1, 0.2, 0.3, 0.5}, every record under `RANDOM`
is profitable exactly when its equity is above the threshold. Check with `python -m pytest -q`.

<details><summary>Solution</summary>

```python
def required_equity(pot: float, bet_size: float, fold_equity: float) -> float:
    """Smallest equity when called for which raising is +EV (fold_equity < 1)."""
    return (bet_size - fold_equity * pot / (1.0 - fold_equity)) / final_pot(pot, bet_size)
```

(Add `final_pot` to the `src.ev` import, and `required_equity` to the test file's
`src.range_finder` import.)

```python
@pytest.mark.parametrize("bet", [50000.0, 100000.0, 300000.0])
@pytest.mark.parametrize("fold", [0.0, 0.1, 0.2, 0.3, 0.5])
def test_random_model_cut_is_an_equity_threshold(loaded_finder: RangeFinder, bet: float, fold: float) -> None:
    need = required_equity(100000.0, bet, fold)
    for r in loaded_finder.solve_range(100000.0, bet, fold):
        assert r.is_raise_profitable == (r.equity > need), (r.canonical_id, r.equity, need)
```

That adds 15 cases: `python -m pytest tests/test_range_finder.py -q` gives `24 passed`.
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
- `category_breakdown()` gives the per-category totals that both the API and the CLI show.
- Fixed: the duplicated constant (now `hands.TOTAL_COMBINATIONS`), the hidden `load()` (now
  `DatabaseNotLoadedError`) and the bare `ValueError` for `RANGE` without a model (now
  `ModelError`). Still open: a test-only method, a dependency on the 455 real IDs, a
  double filter.

**Next:** [09 — The command-line interface](09-cli.md)
