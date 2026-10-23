# 13 — Testing and Performance

> **Goal:** finish the backend test suite with end-to-end "scenario" tests, learn the pytest features you
> have been using, and measure the code against the speed and memory budgets in `AGENTS.md`.
> **You will build:** `backend/tests/test_dynamic_scenarios.py` (5 tests).
> **Time:** ~1 hour.
> **Prerequisites:** [12](13-flask-api.md).

---

## The big picture

You've written tests chapter by chapter. Each file tests **one module** in isolation: these are **unit
tests**. This chapter adds a different kind: **scenario (end-to-end) tests** that tell a story through
the whole stack (HTTP request → API → engine → JSON) and check that the *answer makes sense* to a player.

```
              ▲ fewer, slower, broader
              │      test_dynamic_scenarios.py   "a monster hand must say RAISE"   (whole stack)
              │      test_api.py                 HTTP contract of each endpoint
              │      test_range_finder.py, test_db.py, test_generator.py
              │      test_ev.py, test_hands.py, test_evaluator.py   (one function at a time)
              ▼ many, fast, narrow
```

This shape (many small unit tests, a few big end-to-end tests) is often called the **test pyramid**.

---

## Concepts you need: pytest features you've used (summary)

| Feature | Example from this project | What it does |
|---|---|---|
| test discovery | `tests/test_*.py`, `def test_…`, `class Test…` | pytest finds and runs them automatically |
| `assert` | `assert hand_9 > hand_8` | fails with a detailed diff if false |
| `pytest.raises` | `with pytest.raises(InvalidCardError):` | the block **must** raise that error |
| fixture | `@pytest.fixture def client(): …` | prepares an object; tests receive it by parameter name |
| fixture scope | `@pytest.fixture(scope="module")` | build once per file instead of once per test |
| `yield` fixture | `with app.test_client() as c: yield c` | set-up before `yield`, clean-up after |
| tolerance | `abs(a - b) < 0.015` | compare floats safely |

Useful command-line options:

```bash
python -m pytest -q                       # quiet: dots and a summary
python -m pytest -v                       # verbose: one line per test
python -m pytest tests/test_ev.py         # one file
python -m pytest -k lieng                 # only tests whose name contains "lieng"
python -m pytest -x                       # stop at the first failure
python -m pytest -s                       # show print() output (normally hidden)
python -m pytest --durations=5            # list the 5 slowest tests
```

---

## Step 13.1 — Scenario tests: set-up

📄 **File:** `backend/tests/test_dynamic_scenarios.py` — *create this file*

```python
"""Comprehensive Dynamic Scenario Verification Suite for Liêng Stealer.

Verifies that the engine and API are completely dynamic and mathematically
rigorous across 5 diverse game scenarios:
1. Monster Hand Value Raise (Liêng Q-K-A)
2. Junk Hand against Calling Station (Forced Fold with 0 points)
3. Mathematical Pure Bluff (0 points flips to Raise under high fold equity)
4. Range Coverage Sensitivity Sweep across fold equities
5. API Schema, Endpoint Variations & Dynamic Response Verification
"""

import sys
from pathlib import Path
import pytest

# Ensure UTF-8 encoding on Windows terminal output
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app import app
from src.db import WinRateDB
from src.range_finder import RangeFinder

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "winrates.json"


@pytest.fixture(scope="module")
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture(scope="module")
def solver():
    db = WinRateDB(DB_PATH)
    return RangeFinder(db)
```

**How it works**

- Two fixtures, one per layer: `client` tests through **HTTP** (the Flask test client), `solver` tests
  the **engine directly** (a `RangeFinder`).
- The UTF-8 block is the same trick as in the CLI: these tests `print` Vietnamese text, which must not
  crash on Windows.
- `DB_PATH` is absolute (built from this file's location), so the tests work from any folder.

---

## Step 13.2 — Scenario 1: a monster hand must raise

📄 **File:** `backend/tests/test_dynamic_scenarios.py` — *add to the end*

```python


def test_scenario_1_monster_hand_value_raise(client):
    """Scenario 1: Monster Hand Value Raise (Liêng Q-K-A).
    Pot=100k, Bet=50k, FoldEquity=0.20, Hand='As Kh Qd'
    """
    payload = {
        "pot": 100000.0,
        "bet_size": 50000.0,
        "fold_equity": 0.20,
        "hand": "As Kh Qd",
    }
    res = client.post("/api/solve", json=payload)
    assert res.status_code == 200
    data = res.get_json()

    hand_eval = data["hand_evaluation"]
    assert hand_eval is not None

    # Invariants:
    # 1. Recommendation MUST be "RAISE"
    assert hand_eval["decision"] == "RAISE"
    # 2. Showdown Equity MUST be > 99%
    assert hand_eval["showdown_equity"] > 0.99
    # 3. EV MUST be positive (> +100,000)
    assert hand_eval["ev"] > 100000.0
    # 4. Break-Even Fold Equity MUST be 0.0% (profitable even if opponent never folds)
    assert hand_eval["break_even_fold_equity"] == 0.0

    print("\n[Scenario 1: Monster Value Raise]")
    print(f"  Hand: {hand_eval['hand']} ({hand_eval['canonical_id']})")
    print(f"  Showdown Equity: {hand_eval['showdown_equity'] * 100:.2f}%")
    print(f"  Net EV: +{hand_eval['ev']:,.0f} VND")
    print(f"  Break-Even FE: {hand_eval['break_even_fold_equity'] * 100:.1f}%")
    print(f"  Decision: {hand_eval['decision']} -> PASS")
```

**In plain words:** "If I hold the best Liêng and the opponent rarely folds (20%), the tool must tell me
to raise, and it must say I'd profit even if they never folded." Check the EV by hand with chapter 9:
`0.2 × 100,000 + 0.8 × (0.9969 × 200,000 − 50,000) = 20,000 + 119,504 = 139,504`. ✔

The `print` lines are a **readable report** for humans, shown with `pytest -s`.

---

## Step 13.3 — Scenarios 2 and 3: the same junk hand, two answers

📄 **File:** `backend/tests/test_dynamic_scenarios.py` — *add to the end*

```python


def test_scenario_2_junk_hand_calling_station(client):
    """Scenario 2: Junk Hand against Calling Station (Forced Fold).
    Pot=100k, Bet=50k, FoldEquity=0.05, Hand='2s 3h 5d' (0 pts Bù)
    """
    payload = {
        "pot": 100000.0,
        "bet_size": 50000.0,
        "fold_equity": 0.05,
        "hand": "2s 3h 5d",
    }
    res = client.post("/api/solve", json=payload)
    assert res.status_code == 200
    data = res.get_json()

    hand_eval = data["hand_evaluation"]
    assert hand_eval is not None

    # Invariants:
    # 1. Recommendation MUST be "CHECK/FOLD"
    assert "FOLD" in hand_eval["decision"]
    # 2. Showdown Equity MUST be < 1% (0.24%)
    assert hand_eval["showdown_equity"] < 0.01
    # 3. EV MUST be negative (close to -42,000)
    assert hand_eval["ev"] < 0.0
    assert abs(hand_eval["ev"] - (-42044.0)) < 100.0
    # 4. Break-Even Fold Equity MUST be > 30% (unprofitable because 0.05 < 0.33)
    assert hand_eval["break_even_fold_equity"] > 0.30

    print("\n[Scenario 2: Junk Hand Forced Fold]")
    print(f"  Hand: {hand_eval['hand']} ({hand_eval['canonical_id']})")
    print(f"  Showdown Equity: {hand_eval['showdown_equity'] * 100:.2f}%")
    print(f"  Net EV: {hand_eval['ev']:,.0f} VND")
    print(f"  Break-Even FE: {hand_eval['break_even_fold_equity'] * 100:.2f}%")
    print(f"  Decision: {hand_eval['decision']} -> PASS")
```

📄 **File:** `backend/tests/test_dynamic_scenarios.py` — *add to the end*

```python


def test_scenario_3_pure_bluff_flip(client):
    """Scenario 3: Mathematical Pure Bluff (Junk Hand with High Fold Equity).
    Pot=100k, Bet=50k, FoldEquity=0.50, Hand='2s 3h 5d' (0 pts Bù)
    """
    payload = {
        "pot": 100000.0,
        "bet_size": 50000.0,
        "fold_equity": 0.50,
        "hand": "2s 3h 5d",
    }
    res = client.post("/api/solve", json=payload)
    assert res.status_code == 200
    data = res.get_json()

    hand_eval = data["hand_evaluation"]
    assert hand_eval is not None

    # Invariants:
    # 1. Recommendation MUST flip to "RAISE" despite holding 0 points
    assert hand_eval["decision"] == "RAISE"
    # 2. EV MUST become positive (> +20,000) solely due to fold equity exceeding 33.3%
    assert hand_eval["ev"] > 20000.0
    assert abs(hand_eval["ev"] - 25240.0) < 100.0
    assert hand_eval["is_profitable"] is True

    print("\n[Scenario 3: Mathematical Pure Bluff]")
    print(f"  Hand: {hand_eval['hand']} ({hand_eval['canonical_id']})")
    print(f"  Opponent Fold Equity: 50.0% (Threshold: {data['summary']['pure_bluff_break_even_fold_equity'] * 100:.1f}%)")
    print(f"  Net EV: +{hand_eval['ev']:,.0f} VND")
    print(f"  Decision: {hand_eval['decision']} (Flipped from Fold to Raise) -> PASS")
```

**In plain words:** the **same** worthless hand (`2-3-5`, 0 points) gets **opposite** advice depending
only on the opponent: fold against a calling station (5% folds, EV −42,044), raise against a player who
folds half the time (EV +25,240). This pair of tests captures the whole lesson of the project: the right
decision depends on the situation, not only on your cards. The numbers are the ones you computed in
chapter 9's table.

---

## Step 13.4 — Scenario 4: coverage grows with fold equity

📄 **File:** `backend/tests/test_dynamic_scenarios.py` — *add to the end*

```python


def test_scenario_4_range_coverage_sensitivity(solver):
    """Scenario 4: Range Coverage Sensitivity Sweep.
    Sweep fold equities: f = 0.00, 0.15, 0.30, 0.40
    """
    pot = 100000.0
    bet = 50000.0

    cov_00 = solver.calculate_range_coverage(solver.get_profitable_range(pot, bet, 0.00))
    cov_15 = solver.calculate_range_coverage(solver.get_profitable_range(pot, bet, 0.15))
    cov_30 = solver.calculate_range_coverage(solver.get_profitable_range(pot, bet, 0.30))
    cov_40 = solver.calculate_range_coverage(solver.get_profitable_range(pot, bet, 0.40))

    # Invariants:
    # 1. Coverage MUST strictly increase as f increases
    assert cov_00 < cov_15 < cov_30 < cov_40
    # 2. Coverage at f = 0.40 MUST equal 100.0% (pure bluff threshold is 33.3%)
    assert cov_40 == 100.0
    # 3. Coverage at f = 0.00 is restricted (< 80% under pot odds, and strict >50% equity hands < 50%)
    assert cov_00 < 80.0
    # Verify pure favorite hands (>50% equity) are < 50% of total hand space
    db = WinRateDB(DB_PATH)
    combos_above_50 = sum(s.multiplicity for s in db.all_items().values() if s.equity > 0.50)
    assert (combos_above_50 / 22100.0) * 100.0 < 50.0

    print("\n[Scenario 4: Range Coverage Sensitivity Sweep]")
    print(f"  f = 0.00 (Calling Station): {cov_00:.2f}% coverage")
    print(f"  f = 0.15 (Tight Caller):   {cov_15:.2f}% coverage")
    print(f"  f = 0.30 (Average Player): {cov_30:.2f}% coverage")
    print(f"  f = 0.40 (Folding Player): {cov_40:.2f}% coverage")
    print("  Monotonicity: cov(0.0) < cov(0.15) < cov(0.30) < cov(0.40) == 100.0% -> PASS")
```

**In plain words:** a **sensitivity sweep** changes one input step by step and checks the output moves the
right way. The more the opponent folds, the more hands are worth raising: 75.17% → 84.07% → 96.42% →
100%. This test calls the engine directly (the `solver` fixture) rather than through HTTP: faster, and
it isolates the logic from the web layer.

---

## Step 13.5 — Scenario 5: the API contract

📄 **File:** `backend/tests/test_dynamic_scenarios.py` — *add to the end*

```python


def test_scenario_5_api_schema_and_endpoints(client):
    """Scenario 5: API Schema & Endpoints Check.
    Test with and without hand, and verify dynamic variance with parameter changes.
    """
    # 1. Request with hand
    res_with_hand = client.post("/api/solve", json={
        "pot": 100000,
        "bet_size": 50000,
        "fold_equity": 0.35,
        "hand": "As Kh Qd",
    })
    assert res_with_hand.status_code == 200
    data_with_hand = res_with_hand.get_json()
    assert data_with_hand["hand_evaluation"] is not None
    assert "summary" in data_with_hand
    assert "top_hands" in data_with_hand

    # 2. Request without hand
    res_no_hand = client.post("/api/solve", json={
        "pot": 100000,
        "bet_size": 50000,
        "fold_equity": 0.35,
    })
    assert res_no_hand.status_code == 200
    data_no_hand = res_no_hand.get_json()
    assert data_no_hand["hand_evaluation"] is None
    assert data_no_hand["summary"]["range_coverage_percent"] == 100.0
```

📄 **File:** `backend/tests/test_dynamic_scenarios.py` — *add to the end*

```python

    # 3. Dynamic verification: Changing pot/bet changes EV and thresholds
    res_diff_params = client.post("/api/solve", json={
        "pot": 200000,
        "bet_size": 100000,
        "fold_equity": 0.10,
        "hand": "As Kh Qd",
    })
    data_diff = res_diff_params.get_json()
    assert data_diff["summary"]["pot"] == 200000
    assert data_diff["summary"]["final_pot"] == 400000
    assert data_diff["hand_evaluation"]["ev"] != data_with_hand["hand_evaluation"]["ev"]

    # 4. Service root metadata
    root_res = client.get("/")
    assert root_res.status_code == 200
    root_json = root_res.get_json()
    assert root_json["service"] == "Lieng Stealer API"
    assert root_json["status"] == "online"

    print("\n[Scenario 5: API Schema & Dynamic Verification]")
    print("  POST /api/solve with hand: OK")
    print("  POST /api/solve without hand: OK")
    print("  Dynamic EV scaling with Pot/Bet changes: OK")
    print("  GET / service metadata: OK -> PASS")
```

**In plain words:** the frontend (chapter 15) relies on a certain JSON shape: `summary`, `top_hands`,
and `hand_evaluation` (an object, or `null` when no hand is sent). This test pins down that **contract**,
so a backend change that would break the web page fails here first. Part 3 makes sure results really
depend on the inputs, i.e. nothing is accidentally cached or hard-coded.

> 💡 **Overlap.** Scenario 5 repeats several checks from `test_api.py` (root metadata, solve with and
> without a hand). Some overlap between test layers is normal, but if a response field is renamed you'll
> now fix it in two places.

---

## Step 13.6 — Run the whole suite and read the report

```bash
python -m pytest -q
```

Expected output:

```
..........................................................               [100%]
58 passed in 1.50s
```

**58 tests**: 18 evaluator + 5 hands + 5 generator + 6 db + 9 ev + 4 range finder + 6 API + 5 scenarios.
That matches the "58 Tests Passing" badge in the project's README.

Now with the scenario report and the slowest tests:

```bash
python -m pytest tests/test_dynamic_scenarios.py -s -q
```

```
[Scenario 1: Monster Value Raise]
  Hand: As Kh Qd (Q-K-A)
  Showdown Equity: 99.69%
  Net EV: +139,504 VND
  Break-Even FE: 0.0%
  Decision: RAISE -> PASS
.
[Scenario 2: Junk Hand Forced Fold]
  ...
  Net EV: -42,044 VND
...
[Scenario 4: Range Coverage Sensitivity Sweep]
  f = 0.00 (Calling Station): 75.17% coverage
  f = 0.15 (Tight Caller):   84.07% coverage
  f = 0.30 (Average Player): 96.42% coverage
  f = 0.40 (Folding Player): 100.00% coverage
...
5 passed in 0.22s
```

```bash
python -m pytest -q --durations=3
```

The slowest tests are the generator's exact enumerations (≈ 0.4 s each). Everything else takes
milliseconds.

---

## Step 13.7 — Measure the performance budgets

`AGENTS.md` §6 lists five budgets. Let's measure each one. No new project files: run these in the
terminal from `backend/`.

**1. Single hand evaluation (< 1 µs)** with `timeit`, the standard tool for timing small snippets.
`-s` is set-up code that isn't timed:

```bash
python -m timeit -s "from src.evaluator import Hand, evaluate_hand; c = Hand.from_str('9s 8h 2d').cards" "evaluate_hand(c)"
```

```
50000 loops, best of 5: 4.2 usec per loop        (your numbers will differ)
```

**2. Lookup (< 5 µs)**, **3. Full range (< 25 ms)** and **5. Memory (< 10 MB)**:

```bash
python -c "
import timeit, tracemalloc
tracemalloc.start()
from src.db import WinRateDB
before = tracemalloc.get_traced_memory()[0]
db = WinRateDB('data/winrates.json')
after = tracemalloc.get_traced_memory()[0]
tracemalloc.stop()
print(f'database memory: {(after - before) / 1024:.0f} KB')
from src.range_finder import RangeFinder
rf = RangeFinder(db)
print(f'lookup: {min(timeit.repeat(lambda: db.get(\"Q-K-A\"), number=100000, repeat=5)) / 100000 * 1e6:.2f} us')
print(f'full range: {min(timeit.repeat(lambda: rf.solve_range(100000, 50000, 0.35), number=100, repeat=5)) / 100 * 1000:.2f} ms')
"
```

```
database memory: 150 KB
lookup: 0.15 us
full range: 1.05 ms
```

Your timings will differ: they depend on your CPU and on what else the machine is doing. Run it twice
and expect variations of 2–3×. The memory figure should be about 150 KB everywhere.

(`tracemalloc` is Python's built-in memory tracer. It slows code down while it runs, which is why we
stop it before timing. `min(timeit.repeat(...))` takes the best of several runs, the most stable
measure.)

**4. CLI command (< 50 ms total):**

```bash
time python -m src.cli --hand "As Kh Qd" > /dev/null
```

```
real    0m0.120s
```

### The scorecard

| Budget (`AGENTS.md` §6) | Target | Measured (typical laptop) | Met? |
|---|---|---|---|
| Single hand evaluation | < 1.0 µs | ~3–10 µs | ❌ |
| Hash-table lookup | < 5.0 µs | ~0.15 µs | ✅ (30× margin) |
| Full range EV (455 hands) | < 25 ms | ~1–2 ms | ✅ |
| CLI command | < 50 ms | ~120 ms | ❌ |
| Database memory | < 10 MB | ~150 KB | ✅ |

> ⚠️ **Pitfall: two budgets aren't met, and only one is tested.** Only the lookup budget has an
> automated test (`test_db.py`). The evaluation budget is missed by ~4× (see chapter 5 for a lookup-table
> fix), and the CLI budget by ~2.5×. Python itself starts in ~10 ms, but **importing `rich` and the
> modules takes ~100 ms** (measure with `python -X importtime -m src.cli --help 2> imports.txt`). A fix is
> to import `rich` lazily, inside the render functions, or to skip it when output isn't a terminal.
> **Lesson:** a performance number in a spec is just a wish until a test or a benchmark checks it.

---

## ✅ Checkpoint

- [ ] `python -m pytest -q` → **58 passed**.
- [ ] You can explain the difference between a unit test and a scenario test.
- [ ] You measured at least three of the five budgets yourself.

The backend is **complete**. Commit:

```bash
git add . && git commit -m "test: dynamic scenario suite"
```

## Recap

- Unit tests check one function; **scenario tests** tell a player's story through the whole stack.
- Scenarios 2 and 3 show the project's core lesson: the same junk hand is a fold or a raise depending on fold equity.
- Fixtures can test the same logic through HTTP (`client`) or directly (`solver`).
- Measure performance with `timeit`, memory with `tracemalloc`, and whole commands with `time`.
- Pitfall: of five budgets, two are missed and only one is guarded by a test.

**Next:** [14 — Frontend foundations](15-frontend-foundations.md)
