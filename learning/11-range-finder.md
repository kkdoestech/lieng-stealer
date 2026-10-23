# 11 — The Range Finder

> **Goal:** for a given pot, bet, fold equity and opponent model, compute the EV of **every** hand type,
> sort them, and measure what fraction of all hands is profitable to raise.
> **You will build:** `backend/src/range_finder.py` and `backend/tests/test_range_finder.py` (4 tests).
> **Time:** ~1 hour.
> **Prerequisites:** [10](10-expected-value.md).

---

## The big picture

Chapter 10 answered "should I raise **this** hand?". Strategy questions are bigger: *"Against this
opponent, which hands should I raise with at all?"* A set of hands is called a **range**. The range
finder answers that question for all 455 hand types at once.

```
 opponent_model = RANDOM ──► equity from WinRateDB (455 × equity vs a random hand)
 opponent_model = RANGE  ──► equity from CallingRangeModel.equity_table(f)   (chapter 9)
                                             │
 pot, bet, fold equity ──────────────────────┼──► for each hand type: calculate_ev(P, B, f, equity)
                                             ▼
                              455 HandEVRecords, sorted by EV (best first)
                                             │
              ┌──────────────────────────────┼──────────────────────────────┐
              ▼                              ▼                              ▼
   get_profitable_range()        calculate_range_coverage()          top 30 for display
   (keep EV > 0)                 (% of the 22,100 real hands)        (CLI, API)
```

It costs 455 EV calculations, about **1.6 ms** in Python. `AGENTS.md` allows 25 ms.

---

## Concepts you need

### Why "the profitable range" is always "the top N hands"

Look at the EV formula as a function of equity `e`:

```
EV(e) = f·P + (1 − f)·(P + 2B)·e − (1 − f)·B
      = (a constant)  +  (a positive number) × e          (when f < 1)
```

It's a straight line in `e` with a **positive slope**. So more equity always means more EV, and sorting
hands by EV gives the same order as sorting by equity. The profitable hands are exactly those above
one **threshold equity**:

```
EV > 0   ⇔   e  >  [ B − f·P / (1 − f) ] / (P + 2B)
```

| Fold equity `f` (P = 100k, B = 50k) | Threshold equity | Profitable types | Coverage |
|----|----|----|----|
| 0.00 (calling station) | 0.25 | 343 / 455 | 75.17% |
| 0.20 | 0.125 | 397 / 455 | 87.55% |
| 0.35 | below 0 (every hand) | 455 / 455 | 100.00% |

### Coverage must be weighted

"343 of 455 types are profitable" is misleading, because types have different multiplicities. The
fair measure counts **real hands**:

```
coverage % = (sum of multiplicities of profitable types) / 22,100 × 100
```

At `f = 0`: 16,612 real hands of 22,100 → **75.17%**.

### Two opponent models, one solver

The same reasoning works for the **range** model from chapter 9: at a *fixed* `f`, every hand faces the
same calling range, and stronger hands beat more of it. So equity still falls as we go down the strength
order, and the profitable hands are still "the top N". But N is smaller, because equities against a
calling range are lower:

| Situation (pot 100k) | Random model: profitable types / coverage | Range model: profitable types / coverage |
|---|---|---|
| bet 50k, `f = 0.00` | 343 / 75.17% | 343 / 75.17% (no folds → same as random) |
| bet 50k, `f = 0.20` | 397 / 87.55% | 318 / 69.92% |
| bet 100k, `f = 0.35` | 387 / 84.65% | 250 / 54.57% |
| bet 50k, `f = 0.35` | 455 / 100% | 455 / 100% (35% folds > 33.3% bluff threshold) |

With a pot-sized bet against an opponent who folds their weakest 35%, the honest profitable range
covers about **half** of all hands, not 85%. That's the practical value of the range model.

---

## Step 11.1 — Imports, a constant, and the record type

📄 **File:** `backend/src/range_finder.py` — *create this file*

```python
"""Liêng Stealer - Range Solver & Opportunity Scanner.

Evaluates all 455 canonical hands against current game parameters (Pot, Bet, Fold Equity),
filtering for positive expected value (EV > 0) and measuring total range coverage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Sequence

from src.calling_range import CallingRangeModel, OpponentModel
from src.db import HandStats, WinRateDB
from src.evaluator import HandCategory
from src.ev import calculate_ev, is_profitable
from src.hands import generate_all_canonical_hands

TOTAL_COMBINATIONS: Final[int] = 22100


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

**How it works**

- `TOTAL_COMBINATIONS` is a named constant for C(52, 3). A **named constant** explains itself and lives
  in one place, unlike a bare `22100` typed in several files.
- `HandEVRecord` is one row of the answer: which hand, how strong, how profitable **in this situation**.
  Unlike `HandStats` (fixed forever), a record depends on the pot/bet/fold inputs.

---

## Step 11.2 — `RangeFinder`: construction

📄 **File:** `backend/src/range_finder.py` — *add to the end*

```python


class RangeFinder:
    """Solves and ranks profitable ranges across all canonical hands."""

    def __init__(self, db: WinRateDB, calling_model: CallingRangeModel | None = None) -> None:
        """Initialize RangeFinder with a populated WinRateDB instance.

        Args:
            db: Win-rate database (equity against a random opponent hand).
            calling_model: Calling-range model, required only for OpponentModel.RANGE.
        """
        if not db.is_loaded:
            db.load()
        self._db = db
        self._calling_model = calling_model
        # Showdown strength of each class, used to order hands whose EV and equity tie
        self._strength = {h.canonical_id: h.score.score_tuple for h in generate_all_canonical_hands()}
```

This is **dependency injection** from chapter 8: the finder doesn't create or find its data sources,
it **receives** them. The calling-range model is **optional** (`= None`): code that only needs the
random model (the CLI, the old tests) can keep writing `RangeFinder(db)`. Adding a parameter with a
default value is a classic way to extend a class **without breaking existing callers** (backward
compatibility).

The last line precomputes a small lookup table: canonical ID → **showdown strength** (`score_tuple`,
chapter 5), built once from `generate_all_canonical_hands()` (chapter 6) in about 5 ms. The next step uses
it to order hands whose EV is exactly equal.

> ⚠️ **Pitfall: a hidden side effect in a constructor.** If the database isn't loaded yet, the
> constructor quietly calls `db.load()` with the **default path** (`"data/winrates.json"`, plus the
> silent fallback from chapter 8). So building an object can read a file you never mentioned, and can
> raise a `DatabaseError` from a line that looks harmless. In `app.py` (chapter 13) this line runs
> **at import time**. Constructors should be cheap and predictable. **Better:** fail fast:
>
> ```python
> if not db.is_loaded:
>     raise DatabaseNotLoadedError("RangeFinder needs a loaded WinRateDB.")
> ```

---

## Step 11.3 — `solve_range`: score and sort every hand type

📄 **File:** `backend/src/range_finder.py` — *add to the end*

```python

    def solve_range(
        self,
        pot: float,
        bet_size: float,
        fold_equity: float,
        opponent_model: OpponentModel = OpponentModel.RANDOM,
    ) -> list[HandEVRecord]:
        """Evaluate and rank all 455 canonical hands sorted descending by EV.

        Args:
            pot: Dead pot size before hero's bet (must be > 0).
            bet_size: Additional bet / raise amount (must be > 0).
            fold_equity: Opponent fold probability in [0.0, 1.0].
            opponent_model: RANDOM uses equity vs a random hand; RANGE uses equity
                vs an opponent who folds their weakest hands.

        Returns:
            List of all 455 HandEVRecord instances sorted by EV descending.

        Raises:
            ValueError: If RANGE is requested without a CallingRangeModel.
        """
        all_stats = self._db.all_items()
        records: list[HandEVRecord] = []

        range_equity: dict[str, float] | None = None
        if opponent_model is OpponentModel.RANGE:
            if self._calling_model is None:
                raise ValueError("OpponentModel.RANGE requires a CallingRangeModel.")
            range_equity = self._calling_model.equity_table(fold_equity)

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

**How it works**

- **Choose the equity source once, before the loop.** For the range model, `equity_table(fold_equity)`
  computes all 455 equities in one call (~0.6 ms, chapter 9). Inside the loop each hand just picks its
  number: `range_equity[cid]` or the random-hand `stats.equity`.
- `opponent_model is OpponentModel.RANGE` uses `is`: enum members are **singletons** (there is exactly
  one `OpponentModel.RANGE` object), so identity comparison is the idiomatic check.
- Asking for the range model without having injected one is a programming error, so it raises
  `ValueError` immediately (**fail fast**) instead of silently falling back to random equity.
- Then, as before: build one record per hand, reusing `calculate_ev` and `is_profitable` from chapter 10.
  **No new maths, just orchestration.** The record stores the equity actually used, so tables and the
  UI show the model's equity.
- `records.sort(key=lambda r: (r.ev, r.equity, self._strength[r.canonical_id]), reverse=True)` sorts in
  place by a **tuple key**: by EV; if two EVs are equal, by equity; if those are equal too, by hand
  strength. That matters at `f = 1.0`, where every hand has EV = `P`, and under the range model (below).
- The function doesn't modify the database or any global; it returns a fresh list.

> ✅ **How the code fixed this (before → after).** Under the range model many weak hands have equity
> exactly **0** (they can't beat anything that calls), so they all get the **same** EV, e.g.
> `0.35 × 100,000 − 0.65 × 50,000 = +2,500`. The first version sorted by `(ev, equity)` only: both keys
> tied, and Python's **stable** sort kept the database's insertion order, so the "weakest profitable hand"
> reported by the API (`threshold_hand`) came out as `A-A-K` at `f = 0.35`, an arbitrary pick among
> hundreds of equal hands. With strength as the third key, tied hands are listed strongest-first, and the
> last one is truly the weakest: `4-3-3`, the weakest of all 455 hands (chapter 6). **Lesson:** when a
> sort can tie, decide the tie-break on purpose; "whatever order they came in" is a hidden dependency.

🧪 **Mini-check** (a calling station: `f = 0`)

```bash
python -c "
from src.db import WinRateDB
from src.range_finder import RangeFinder
rf = RangeFinder(WinRateDB('data/winrates.json'))
recs = rf.solve_range(100000, 50000, 0.0)
print([(r.canonical_id, r.ev) for r in recs[:3]])
prof = [r for r in recs if r.is_raise_profitable]
print(len(prof), prof[-1].canonical_id, prof[-1].equity, prof[-1].ev)
nxt = recs[len(prof)]
print(nxt.canonical_id, nxt.equity, nxt.ev)
"
```

Expected output:

```
[('A-A-A', 150000.0), ('K-K-K', 149960.0), ('Q-Q-Q', 149920.0)]
343 K-6-6 0.2541 820.0
Q-Q-2 0.2473 -540.0
```

The cut is exactly at equity 0.25, as predicted: `K-6-6` (2 points, King high, 25.41%) is the weakest
hand still worth raising; `Q-Q-2` (2 points, Queen high, 24.73%) is the first one that isn't.

🧪 **Mini-check** (both models, pot-sized bet, opponent folds 35%):

```bash
python -c "
from src.calling_range import CallingRangeModel, OpponentModel
from src.db import WinRateDB
from src.range_finder import RangeFinder
rf = RangeFinder(WinRateDB('data/winrates.json'), CallingRangeModel())
for model in OpponentModel:
    recs = rf.solve_range(100000, 100000, 0.35, model)
    prof = [r for r in recs if r.is_raise_profitable]
    print(model.value, len(prof), rf.calculate_range_coverage(prof), prof[-1].canonical_id, prof[-1].equity)
"
```

Expected output:

```
random 387 84.65 K-8-3 0.1557
range 250 54.57 K-Q-4 0.156
```

Both models cut at the **same threshold equity** (≈ 0.154, from the formula above with `B = P`,
`f = 0.35`), because the EV formula is the same. What differs is **which hands reach it**: against a
calling range, `K-8-3` no longer has 15.6% equity, so only hands down to `K-Q-4` stay profitable.
(`for model in OpponentModel` loops over the enum members, as in chapter 3.)

---

## Step 11.4 — Filtering and coverage

📄 **File:** `backend/src/range_finder.py` — *add to the end*

```python

    def get_profitable_range(
        self,
        pot: float,
        bet_size: float,
        fold_equity: float,
        opponent_model: OpponentModel = OpponentModel.RANDOM,
    ) -> list[HandEVRecord]:
        """Return only hands where Raise / All-in has positive expected value (EV > 0)."""
        all_records = self.solve_range(pot, bet_size, fold_equity, opponent_model)
        return [r for r in all_records if r.is_raise_profitable]

    def calculate_range_coverage(
        self,
        profitable_records: Sequence[HandEVRecord],
    ) -> float:
        """Compute the weighted percentage of the 22,100 hand space where EV > 0.

        Formula:
            Coverage (%) = (Sum of Multiplicities / 22,100) * 100%

        Args:
            profitable_records: HandEVRecord instances with EV > 0.

        Returns:
            Coverage percentage rounded to 2 decimal places (0.0 to 100.0).
        """
        if not profitable_records:
            return 0.0

        combos = sum(r.multiplicity for r in profitable_records if r.is_raise_profitable)
        coverage = (combos / TOTAL_COMBINATIONS) * 100.0
        return round(min(100.0, max(0.0, coverage)), 2)

```

**How it works**

- `get_profitable_range` = `solve_range` + a filter. It returns records still sorted best-first.
- `calculate_range_coverage` sums **multiplicities** (real hands), not record counts. It filters
  `is_raise_profitable` again, defensively, in case a caller passes the full list. The clamp to
  `[0, 100]` and rounding to 2 decimals keep the output display-ready.
- `if not profitable_records:` is true for an empty list: an empty range covers 0%.

> 💡 **Interface smell.** The parameter is named `profitable_records`, yet the function re-filters them,
> so it would also work with *all* records. A clearer API would take all records and say so
> (`coverage(records)`), or not re-filter. When a function doesn't trust its own parameter name, the
> name is probably wrong.

> ✅ **How the code fixed this (before → after).** When `solve_range` learned the `opponent_model`
> parameter, `get_profitable_range` was first left behind: it always called
> `solve_range(pot, bet_size, fold_equity)`, i.e. the **random** model. Nothing broke at once (the API
> filters `solve_range` results itself), but a caller asking for "the profitable range against a calling
> range" silently got the random-model answer. Now it accepts `opponent_model` (same default) and passes
> it through. **Lesson:** when you add a parameter to a function, check every function that wraps it.

---

## Step 11.5 — The tests

📄 **File:** `backend/tests/test_range_finder.py` — *create this file*

```python
"""Unit tests for the Range Solver Engine (RangeFinder).

Verifies:
- All 455 canonical hands are evaluated by solve_range()
- When fold equity is 100%, all 22,100 combinations yield positive EV and coverage is 100.0%
- When fold equity is 0%, only hands exceeding the required pot odds threshold are profitable
- Monotonicity: Increasing fold equity strictly increases or maintains range coverage
- Opponent models: get_profitable_range honours the model; equal-EV hands are ordered by strength
"""

import pytest

from src.calling_range import CallingRangeModel, OpponentModel
from src.db import WinRateDB
from src.range_finder import TOTAL_COMBINATIONS, RangeFinder


@pytest.fixture(scope="module")
def loaded_finder() -> RangeFinder:
    db = WinRateDB("data/winrates.json")
    return RangeFinder(db)


@pytest.fixture(scope="module")
def finder_with_model() -> RangeFinder:
    return RangeFinder(WinRateDB("data/winrates.json"), CallingRangeModel())


class TestRangeFinder:
    """Test suite for RangeFinder engine."""

    def test_solve_range_returns_all_455_classes(self, loaded_finder: RangeFinder) -> None:
        """Verify that solve_range returns exactly 455 evaluated canonical records."""
        records = loaded_finder.solve_range(pot=100000.0, bet_size=50000.0, fold_equity=0.35)
        assert len(records) == 455

        # Check descending sort order by EV
        for i in range(len(records) - 1):
            assert records[i].ev >= records[i + 1].ev

    def test_pure_fold_equity_100_percent(self, loaded_finder: RangeFinder) -> None:
        """When fold equity is 1.0, all 22,100 combinations yield EV = pot, and coverage is 100.0%."""
        pot = 100000.0
        bet = 50000.0
        records = loaded_finder.solve_range(pot=pot, bet_size=bet, fold_equity=1.0)
        assert len(records) == 455

        # All hands must yield EV = pot
        for r in records:
            assert r.ev == pot
            assert r.is_raise_profitable is True

        profitable = loaded_finder.get_profitable_range(pot=pot, bet_size=bet, fold_equity=1.0)
        assert len(profitable) == 455

        coverage = loaded_finder.calculate_range_coverage(profitable)
        assert coverage == 100.0
```

📄 **File:** `backend/tests/test_range_finder.py` — *add to the end*

```python

    def test_pure_fold_equity_zero_tight_range(self, loaded_finder: RangeFinder) -> None:
        """When fold equity is 0.0, only hands meeting pot odds are profitable."""
        pot = 100000.0
        bet = 50000.0
        # Final pot = 200k. Required equity = 50k / 200k = 0.25 (25%)
        threshold_equity = bet / (pot + 2.0 * bet)

        profitable = loaded_finder.get_profitable_range(pot=pot, bet_size=bet, fold_equity=0.0)

        # All profitable hands must have equity > threshold_equity
        for r in profitable:
            assert r.equity >= threshold_equity
            assert r.ev > 0.0

        # Coverage must be strictly less than 100% (tight range)
        coverage = loaded_finder.calculate_range_coverage(profitable)
        assert 0.0 < coverage < 100.0

    def test_coverage_monotonicity(self, loaded_finder: RangeFinder) -> None:
        """Increasing fold equity must monotonically increase range coverage."""
        pot = 100000.0
        bet = 50000.0

        cov_0 = loaded_finder.calculate_range_coverage(
            loaded_finder.get_profitable_range(pot, bet, fold_equity=0.0)
        )
        cov_25 = loaded_finder.calculate_range_coverage(
            loaded_finder.get_profitable_range(pot, bet, fold_equity=0.25)
        )
        cov_50 = loaded_finder.calculate_range_coverage(
            loaded_finder.get_profitable_range(pot, bet, fold_equity=0.50)
        )
        cov_100 = loaded_finder.calculate_range_coverage(
            loaded_finder.get_profitable_range(pot, bet, fold_equity=1.0)
        )

        assert cov_0 <= cov_25 <= cov_50 <= cov_100
        assert cov_100 == 100.0
```

These are **property tests** in spirit: instead of checking one magic number, they check properties
that must hold whatever the data is (sorted order, the 25% threshold, coverage never shrinking as `f`
grows). Such tests survive regenerating the data with a different method.

All four tests use `RangeFinder(db)` without a calling model, i.e. the default random model, and still
pass unchanged: the backward compatibility from Step 11.2 in action.

Two more tests cover the opponent models directly. They use a second fixture, `finder_with_model`, so
they get a finder **with** a `CallingRangeModel`:

📄 **File:** `backend/tests/test_range_finder.py` — *add to the end*

```python


class TestOpponentModels:
    """Test suite for the opponent-model parameter of RangeFinder."""

    def test_profitable_range_respects_opponent_model(self, finder_with_model: RangeFinder) -> None:
        """A pot-sized bet at 35% folds: 387 classes profit vs random callers, only 250 vs a calling range."""
        random_range = finder_with_model.get_profitable_range(100000.0, 100000.0, 0.35)
        calling_range = finder_with_model.get_profitable_range(
            100000.0, 100000.0, 0.35, opponent_model=OpponentModel.RANGE
        )
        assert len(random_range) == 387
        assert len(calling_range) == 250

    def test_equal_ev_hands_are_ordered_strongest_first(self, finder_with_model: RangeFinder) -> None:
        """At 35% folds every weak hand has 0 equity vs the calling range, so EV ties; strength must break them."""
        records = finder_with_model.solve_range(100000.0, 50000.0, 0.35, OpponentModel.RANGE)
        # The three weakest canonical hands, weakest last (chapter 6: 4-3-3 is the weakest of all 455)
        assert [r.canonical_id for r in records[-3:]] == ["5-3-2", "4-4-2", "4-3-3"]
```

**Each test names the bug it catches:**

- `test_profitable_range_respects_opponent_model`: if `get_profitable_range` ignored the model again,
  both calls would return 387 hand types, not 387 vs 250 (the numbers from this chapter's mini-check).
- `test_equal_ev_hands_are_ordered_strongest_first`: if the strength tie-break disappeared, the last three
  records would be the arbitrary `A-A-Q, A-K-K, A-A-K` instead of the three weakest hands of chapter 6.
  The expected order is written by hand from chapter 6's facts, **not** computed with the code under test.

---

## ✅ Checkpoint

```bash
python -m pytest -q
```

Expected output:

```
................................................................         [100%]
64 passed in 2.30s
```

That's the whole **core engine**: 64 tests over evaluator, hands, generator, database, calling range,
EV and range finder. Commit:

```bash
git add . && git commit -m "feat: range finder with opponent models"
```

## Recap

- `solve_range` computes EV for all 455 types and sorts them by `(ev, equity, strength)`, best first, in
  ~1–2 ms. The strength tie-break makes the order fully deterministic.
- `opponent_model` picks the equity source: `RANDOM` → `winrates.json`, `RANGE` → the injected
  `CallingRangeModel` (one `equity_table` call per solve). The model is an optional constructor argument,
  so old callers keep working.
- EV is a straight line in equity with positive slope, so **the profitable range is always "every hand
  above a threshold equity"**. The range model keeps the threshold but lowers equities, shrinking the
  range (e.g. 84.65% → 54.57% coverage for a pot-sized bet at 35% folds).
- **Coverage** is weighted by multiplicity: profitable real hands / 22,100.
- ✅ Fixed: `get_profitable_range` now honours the opponent model; equal-EV hands are ordered by strength.
- Pitfalls: the constructor silently loads a default file; the coverage function re-filters its input.

**Next:** [12 — The command-line interface](12-cli.md)