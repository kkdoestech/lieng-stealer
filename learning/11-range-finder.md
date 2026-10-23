# 10 — The Range Finder

> **Goal:** for a given pot, bet and fold equity, compute the EV of **every** hand type, sort them, and
> measure what fraction of all hands is profitable to raise.
> **You will build:** `backend/src/range_finder.py` and `backend/tests/test_range_finder.py` (4 tests).
> **Time:** ~1 hour.
> **Prerequisites:** [09](10-expected-value.md).

---

## The big picture

Chapter 9 answered "should I raise **this** hand?". Strategy questions are bigger: *"Against this
opponent, which hands should I raise with at all?"* A set of hands is called a **range**. The range
finder answers that question for all 455 hand types at once.

```
 WinRateDB (455 × equity) ──┐
                            ├──► for each hand type: calculate_ev(P, B, f, equity)
 pot, bet, fold equity ─────┘                │
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

---

## Step 10.1 — Imports, a constant, and the record type

📄 **File:** `backend/src/range_finder.py` — *create this file*

```python
"""Liêng Stealer - Range Solver & Opportunity Scanner.

Evaluates all 455 canonical hands against current game parameters (Pot, Bet, Fold Equity),
filtering for positive expected value (EV > 0) and measuring total range coverage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Sequence

from src.db import HandStats, WinRateDB
from src.evaluator import HandCategory
from src.ev import calculate_ev, is_profitable

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

## Step 10.2 — `RangeFinder`: construction

📄 **File:** `backend/src/range_finder.py` — *add to the end*

```python


class RangeFinder:
    """Solves and ranks profitable ranges across all canonical hands."""

    def __init__(self, db: WinRateDB) -> None:
        """Initialize RangeFinder with a populated WinRateDB instance."""
        if not db.is_loaded:
            db.load()
        self._db = db
```

This is **dependency injection** from chapter 8: the finder doesn't create or find its database, it
**receives** it.

> ⚠️ **Pitfall: a hidden side effect in a constructor.** If the database isn't loaded yet, the
> constructor quietly calls `db.load()` with the **default path** (`"data/winrates.json"`, plus the
> silent fallback from chapter 8). So building an object can read a file you never mentioned, and can
> raise a `DatabaseError` from a line that looks harmless. In `app.py` (chapter 12) this line runs
> **at import time**. Constructors should be cheap and predictable. **Better:** fail fast:
>
> ```python
> if not db.is_loaded:
>     raise DatabaseNotLoadedError("RangeFinder needs a loaded WinRateDB.")
> ```

---

## Step 10.3 — `solve_range`: score and sort every hand type

📄 **File:** `backend/src/range_finder.py` — *add to the end*

```python

    def solve_range(
        self,
        pot: float,
        bet_size: float,
        fold_equity: float,
    ) -> list[HandEVRecord]:
        """Evaluate and rank all 455 canonical hands sorted descending by EV.

        Args:
            pot: Dead pot size before hero's bet (must be > 0).
            bet_size: Additional bet / raise amount (must be > 0).
            fold_equity: Opponent fold probability in [0.0, 1.0].

        Returns:
            List of all 455 HandEVRecord instances sorted by EV descending.
        """
        all_stats = self._db.all_items()
        records: list[HandEVRecord] = []

        for cid, stats in all_stats.items():
            ev = calculate_ev(
                pot=pot,
                bet_size=bet_size,
                fold_equity=fold_equity,
                win_rate_when_called=stats.equity,
            )
            records.append(
                HandEVRecord(
                    canonical_id=cid,
                    category=stats.category,
                    equity=stats.equity,
                    ev=ev,
                    multiplicity=stats.multiplicity,
                    is_raise_profitable=is_profitable(ev),
                )
            )

        # Sort descending by EV (highest profit first); tie-break by equity
        records.sort(key=lambda r: (r.ev, r.equity), reverse=True)
        return records
```

**How it works**

- Loop over all 455 `(id, stats)` pairs and build one record each, reusing `calculate_ev` and
  `is_profitable` from chapter 9. **No new maths here, just orchestration.**
- `records.sort(key=lambda r: (r.ev, r.equity), reverse=True)` sorts in place by a **tuple key**: by EV,
  and if two EVs are equal, by equity. That matters at `f = 1.0`, where every hand has EV = `P`. The
  equity tie-break still lists the strongest hands first.
- The function doesn't modify the database or any global; it returns a fresh list.

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

---

## Step 10.4 — Filtering and coverage

📄 **File:** `backend/src/range_finder.py` — *add to the end*

```python

    def get_profitable_range(
        self,
        pot: float,
        bet_size: float,
        fold_equity: float,
    ) -> list[HandEVRecord]:
        """Return only hands where Raise / All-in has positive expected value (EV > 0)."""
        all_records = self.solve_range(pot, bet_size, fold_equity)
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

---

## Step 10.5 — The tests

📄 **File:** `backend/tests/test_range_finder.py` — *create this file*

```python
"""Unit tests for the Range Solver Engine (RangeFinder).

Verifies:
- All 455 canonical hands are evaluated by solve_range()
- When fold equity is 100%, all 22,100 combinations yield positive EV and coverage is 100.0%
- When fold equity is 0%, only hands exceeding the required pot odds threshold are profitable
- Monotonicity: Increasing fold equity strictly increases or maintains range coverage
"""

import pytest

from src.db import WinRateDB
from src.range_finder import TOTAL_COMBINATIONS, RangeFinder


@pytest.fixture(scope="module")
def loaded_finder() -> RangeFinder:
    db = WinRateDB("data/winrates.json")
    return RangeFinder(db)


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

---

## ✅ Checkpoint

```bash
python -m pytest -q
```

Expected output:

```
...............................................                          [100%]
47 passed in 3.90s
```

That's the whole **core engine**: 47 tests over evaluator, hands, generator, database, EV and range
finder. Commit:

```bash
git add . && git commit -m "feat: range finder and coverage"
```

## Recap

- `solve_range` computes EV for all 455 types and sorts them by `(ev, equity)`, best first, in ~1.6 ms.
- EV is a straight line in equity with positive slope, so **the profitable range is always "every hand
  above a threshold equity"**: 0.25 for a calling station at ½-pot, falling as fold equity rises.
- **Coverage** is weighted by multiplicity: profitable real hands / 22,100.
- Pitfall: the constructor silently loads a default file; the coverage function re-filters its input.

**Next:** [11 — The command-line interface](12-cli.md)
