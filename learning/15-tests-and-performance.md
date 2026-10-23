# Lesson 15 — Tests and performance

> **Goal:** know what the 93 backend tests and 6 frontend tests check, how their fixtures and
> imports work, which performance budgets from AGENTS.md §6 the code meets, and where the gaps are
> so you can add the next test yourself.
> **Files:** [`backend/tests/`](../backend/tests), [`frontend/src/format.test.js`](../frontend/src/format.test.js),
> [`frontend/src/i18n.test.js`](../frontend/src/i18n.test.js), [`AGENTS.md`](../AGENTS.md#L123-L128).
> **Time:** ~60 min. **Before this:** [14 — Styling and DESIGN.md](14-styling.md) (the backend half only needs [11](11-request-trace.md))
> (lessons 12–14 help with the frontend tests).

---

## Where this fits

```
                       python -m pytest (backend/)              npm test (frontend/)
                                │                                        │
 unit tests ─────────── test_evaluator, test_hands, test_generator,  format.test.js
 (one module each)      test_db, test_calling_range, test_ev,        i18n.test.js
                        test_range_finder
 front-door tests ───── test_cli (main(argv)), test_api (test client)
 story tests ────────── test_dynamic_scenarios (6 player stories, both models)
 timing tests ───────── test_db.py:45, test_calling_range.py:74   ← AGENTS.md §6
```

Each earlier lesson ran its module's tests. This lesson looks at the suite as a whole: how it is
organised, what keeps it fast and offline, what it measures, and what it does not cover.

---

## Reading order

| # | Location | What to look for |
|---|----------|------------------|
| 1 | [tests/__init__.py](../backend/tests/__init__.py) | One docstring line that decides how imports work. |
| 2 | [test_api.py:7-11](../backend/tests/test_api.py#L7-L11) | A function-scoped fixture around Flask's test client. |
| 3 | [test_dynamic_scenarios.py:28-41](../backend/tests/test_dynamic_scenarios.py#L28-L41) | Module-scoped fixtures and an absolute data path. |
| 4 | [test_cli.py:35-38](../backend/tests/test_cli.py#L35-L38) and [test_api.py:72-74](../backend/tests/test_api.py#L72-L74) | `monkeypatch`: a fake keyboard and a removed API key. |
| 5 | [test_db.py:45-57](../backend/tests/test_db.py#L45-L57), [test_calling_range.py:74-78](../backend/tests/test_calling_range.py#L74-L78) | The two timing tests. |
| 6 | [AGENTS.md:123-128](../AGENTS.md#L123-L128) | The five performance budgets. |
| 7 | [test_generator.py:67-72](../backend/tests/test_generator.py#L67-L72) | A loop that silently skips a key. |
| 8 | [format.test.js](../frontend/src/format.test.js), [i18n.test.js](../frontend/src/i18n.test.js) | `node --test`, no framework. |

---

## Walkthrough

### 1. The test map

Counted with `python -m pytest --collect-only -q`. Two tests are parametrised with two cases
each ([test_api.py:176](../backend/tests/test_api.py#L176), [test_cli.py:27](../backend/tests/test_cli.py#L27)),
so 91 test functions make 93 tests.

| File | Tests | Fixtures (scope) | What it pins | Lesson |
|------|------:|------------------|--------------|--------|
| [test_evaluator.py](../backend/tests/test_evaluator.py) | 18 | none | card parsing, category order, A-2-3 / Q-K-A / K-A-2, Đĩ rules, points mod 10 | 01, 02 |
| [test_hands.py](../backend/tests/test_hands.py) | 5 | none | 455 classes, multiplicities summing to 22,100, suit invariance | 03 |
| [test_generator.py](../backend/tests/test_generator.py) | 7 | `canonical_map` (module) | exact equities, rate invariants, Monte Carlo within 1.5%, JSON schema | 04 |
| [test_db.py](../backend/tests/test_db.py) | 6 | `loaded_db` (function) | loading, **lookup latency**, errors before load and for a missing file | 05 |
| [test_calling_range.py](../backend/tests/test_calling_range.py) | 9 | `model`, `db` (module) | rows ending at 18,424, f = 0 equals `winrates.json`, monotonicity, **table latency** | 06 |
| [test_ev.py](../backend/tests/test_ev.py) | 13 | none | EV boundaries, bluff arithmetic, break-even, profit zones | 07 |
| [test_range_finder.py](../backend/tests/test_range_finder.py) | 6 | `loaded_finder`, `finder_with_model` (module) | 455 sorted records, coverage, 387 vs 250 classes, tie order | 08 |
| [test_cli.py](../backend/tests/test_cli.py) | 6 | `capsys`, `monkeypatch` (built-in) | decisions per model, exit code 2, interactive mode | 09 |
| [test_api.py](../backend/tests/test_api.py) | 17 | `client` (function), `monkeypatch` | every route, both models, 400s, offline analysis | 10 |
| [test_dynamic_scenarios.py](../backend/tests/test_dynamic_scenarios.py) | 6 | `client`, `solver` (module) | six player stories end to end | 11 |
| [format.test.js](../frontend/src/format.test.js) | 4 | — | money per locale, rounding, zones text | 13 |
| [i18n.test.js](../frontend/src/i18n.test.js) | 2 | — | EN and VI have the same keys and kinds of values | 13 |

The whole backend suite runs in about 2 seconds. The slowest tests are in `test_generator.py`,
which enumerates real opponents: `test_rate_invariants` and
`test_equity_hierarchy_monotonicity` took 0.36–0.66 s each on the course machine
(`--durations=5` shows them).

Only the unit tests for pure modules (`test_evaluator`, `test_hands`, `test_ev`) need no fixtures.
That is the payoff of AGENTS.md's "pure functions" rule: a test is just a call and an `assert`.

### 2. How `from src.… import …` works in a test

📍 [`backend/tests/__init__.py:1`](../backend/tests/__init__.py#L1)
```python
"""Test suite for Liêng Stealer."""
```

This file has no code, but its existence matters. pytest imports each test file as a module. If
the test folder is a **package** (it has `__init__.py`), pytest walks up to the first folder that
is *not* a package, here `backend/`, and puts that folder on `sys.path`. From there, `import src`
and `from app import app` work. Without `__init__.py`, pytest would put `backend/tests/` itself on
the path, and `src` would not be found.

Tested in a scratch copy with the file deleted:

| How you run it | With `__init__.py` | Without |
|----------------|--------------------|---------|
| `python -m pytest` from `backend/` | 93 passed | 93 passed (`-m` also adds the current folder to `sys.path`) |
| `pytest` from `backend/` | 93 passed | 10 collection errors: `ModuleNotFoundError: No module named 'src'` |
| `python -m pytest backend/tests` from the repo root | 93 passed | 10 collection errors |

There is no `conftest.py`, `pytest.ini` or `pyproject.toml`: this one empty file is the whole
configuration. The relative path `"data/winrates.json"` used in several fixtures still works from
the repo root thanks to the fallback in [db.py:72-79](../backend/src/db.py#L72-L79), while
`test_dynamic_scenarios.py` builds an absolute path instead.

### 3. Fixtures and their scopes

A fixture is a function whose return value pytest passes to any test that names it as a
parameter. The scope decides how often it runs.

📍 [`backend/tests/test_api.py:7-11`](../backend/tests/test_api.py#L7-L11)
```python
@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client
```

📍 [`backend/tests/test_dynamic_scenarios.py:28-41`](../backend/tests/test_dynamic_scenarios.py#L28-L41)
```python
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

- **Function scope** (the default): a fresh `client` for each of the 17 API tests. A test client
  is cheap, so this costs nothing and keeps tests independent.
- **Module scope**: built once per file. `CallingRangeModel()` takes tens of milliseconds, so
  `test_calling_range.py` and `test_range_finder.py` share one per file.
- **`yield` instead of `return`**: code after `yield` runs when the fixture is torn down. Here
  the `with` block closes the test client.

Notice what the fixtures cannot do: give the app a different database. `from app import app`
imports the module-level globals of lesson 10, so every API test uses the real
`winrates.json` and the real calling-range model, and `app.config["TESTING"] = True` changes
that shared app for the rest of the run. An app factory (lesson 10, exercise 6) would fix both.

### 4. `monkeypatch` and `capsys`: controlling the outside world

Two built-in fixtures do all the faking in this suite:

- **`monkeypatch.setattr("builtins.input", …)`** ([test_cli.py:35-38](../backend/tests/test_cli.py#L35-L38))
  replaces the keyboard with a list of answers (lesson 09).
- **`monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)`**
  ([test_api.py:72-74](../backend/tests/test_api.py#L72-L74)) removes the API key for one test,
  so `/api/analyze` takes the offline branch even on a machine where the key is set. Without this
  line, running the tests could send a request to OpenRouter.
- **`capsys.readouterr()`** ([test_cli.py:17-19](../backend/tests/test_cli.py#L17-L19)) returns
  what was printed, as `.out` and `.err`.

Every change `monkeypatch` makes is undone after the test. No test touches the network, the clock
or the file system beyond reading `winrates.json`.

### 5. The stories: run them with `-s`

`test_dynamic_scenarios.py` checks six player stories through the API and **prints** a short
report for each. pytest captures output by default, so you only see it with `-s` (no capture):

```
[Scenario 2: Junk Hand Forced Fold]
  Hand: 2s 3h 5d (5-3-2)
  Showdown Equity: 0.24%
  Net EV: -42,044 VND
  Break-Even FE: 33.12%
  Decision: CHECK/FOLD -> PASS
.
[Scenario 4: Range Coverage Sensitivity Sweep]
  f = 0.00 (Calling Station): 75.17% coverage
  f = 0.15 (Tight Caller):   84.07% coverage
  f = 0.30 (Average Player): 96.42% coverage
  f = 0.40 (Folding Player): 100.00% coverage
  Monotonicity: cov(0.0) < cov(0.15) < cov(0.30) < cov(0.40) == 100.0% -> PASS
.
[Scenario 6: Same Hand, Both Opponent Models]
  Hand: Ks Qh 3d (K-Q-3)
  Random caller:  equity 36.00%, EV +40,200 VND -> RAISE
  Calling range:  equity 1.08%, EV -27,894 VND -> CHECK/FOLD
  Decision flips with the opponent model -> PASS
```

The "-> PASS" in the text is printed before pytest has finished the test, so it is decoration:
the real verdict is the `.` after it. These stories make good documentation, and every number in
them is pinned by an `assert` (for example `abs(ev - (-42044.0)) < 100.0` at
[test_dynamic_scenarios.py:103](../backend/tests/test_dynamic_scenarios.py#L103)).

### 6. Timing tests against the budgets

📍 [`backend/tests/test_db.py:45-57`](../backend/tests/test_db.py#L45-L57)
```python
    def test_lookup_latency_budget(self, loaded_db: WinRateDB) -> None:
        """Verify O(1) hash table query latency is strictly < 5.0 microseconds per lookup."""
        n_queries = 50000
        key = "Q-K-A"

        start_time = time.perf_counter()
        for _ in range(n_queries):
            _ = loaded_db.get(key)
        elapsed = time.perf_counter() - start_time

        avg_latency_us = (elapsed / n_queries) * 1e6
        # Assert well within the 5 microsecond budget
        assert avg_latency_us < 5.0, f"Lookup latency too high: {avg_latency_us:.3f} us"
```

📍 [`backend/tests/test_calling_range.py:74-78`](../backend/tests/test_calling_range.py#L74-L78)
```python
    def test_full_table_within_latency_budget(self, model: CallingRangeModel) -> None:
        start = time.perf_counter()
        model.equity_table(0.35)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 25.0
```

`time.perf_counter()` is a high-resolution clock meant for measuring intervals. The first test
averages 50,000 lookups, so one slow lookup cannot fail it. The second times a single call, which
is noisier, but the margin is huge. Here are all five budgets from AGENTS.md §6, measured on the
machine this course was written on (your numbers will differ):

| Budget (AGENTS.md §6) | Limit | Measured | Tested? | Met? |
|-----------------------|-------|----------|---------|------|
| Single hand evaluation | < 1.0 µs | `evaluate_hand`: 2.5 µs for Q-K-A (best of 5 × 100,000); 5.3 µs on average over all 22,100 hands | no | **no** |
| Hash-table lookup | < 5.0 µs | `db.get`: about 0.1 µs; `get_by_cards` (with canonicalisation): 0.9 µs | [test_db.py:45](../backend/tests/test_db.py#L45) | yes |
| Full range EV (455 hands) | < 25 ms | `equity_table`: 0.5 ms; `solve_range`: 1.0–2.3 ms random, 1.4–3.7 ms range | [test_calling_range.py:74](../backend/tests/test_calling_range.py#L74) (the table only) | yes |
| CLI command | < 50 ms | 0.11–0.12 s random, 0.17–0.22 s range (whole process) | no | **no** |
| Lookup DB memory | < 10 MB | `WinRateDB`: ~151 KiB retained; `CallingRangeModel`: ~1.1 MiB; whole Python process: 22 MiB peak RSS | no | yes |

Why the two misses:

- **Hand evaluation.** One Python function call that sorts three ranks and builds a dataclass
  costs a few microseconds. 1 µs is not reachable this way in CPython. A table of all 22,100
  precomputed scores, keyed by the sorted cards, would make it a dictionary lookup. Nothing on the
  request path evaluates more than one hand, so the miss costs nothing in practice.
- **The CLI.** Most of the time is start-up, not solving. Measured inside one process: importing
  `rich` about 50 ms, the rest of the imports 17–33 ms, `CallingRangeModel()` 54–67 ms (range
  model only), loading the DB 2–4 ms, and `solve_range` 1–2 ms. Lazy-importing `rich` and caching
  the calling-range tables would get close; meeting 50 ms with a fresh Python process is hard.

### 7. What the tests do not check

| Gap | Where | Why it matters |
|-----|-------|----------------|
| `Hand` hashing | none | `Hand("As Kh Qd") == Hand("Kh Qd As")` is `True`, but their hashes differ, so a set holds both (lesson 02). A test would have caught it. |
| Điểm and Đĩ tie-breaks | [test_evaluator.py:240-247](../backend/tests/test_evaluator.py#L240-L247) compares different point totals only | The house rules (highest card next) can change without any test failing. |
| A malformed `winrates.json` | [test_db.py:6](../backend/tests/test_db.py#L6) promises "malformed data" | Only a *missing* file is tested; the JSON-error and schema-error branches of `load` never run. |
| One rate-invariant case | [test_generator.py:69-72](../backend/tests/test_generator.py#L69-L72) | `"10-J-K"` is not a canonical ID (it is `"K-J-10"`), so `continue` skips it silently: 5 of 6 keys are checked. |
| The OpenRouter branch | [app.py:400-440](../backend/app.py#L400-L440) | No test fakes `requests.post`, so the 200, non-200 and network-error paths are untested. |
| HTTP errors and odd bodies | [app.py:164](../backend/app.py#L164) | No test for 404/405, a list body (500), or `"nan"` (lesson 10). |
| The CLI without `rich` | [cli.py:214-220](../backend/src/cli.py#L214-L220) | The plain fallback never runs in tests. |
| `App.jsx` | — | No component test; only the pure helpers in `format.js` and `i18n.js` are tested. |
| A misleading docstring | [test_ev.py:9](../backend/tests/test_ev.py#L9) | Says more folds always raise EV; false for strong hands (lesson 07). |

`pytest-cov` is not installed, so the project has no line-coverage number. The list above comes
from reading the tests against the code.

📍 [`backend/tests/test_generator.py:67-72`](../backend/tests/test_generator.py#L67-L72)
```python
    def test_rate_invariants(self, canonical_map: dict) -> None:
        """Check mathematical consistency across multiple sample hands."""
        test_keys = ["A-A-A", "Q-K-A", "A-2-3", "9-8-7", "K-K-Q", "10-J-K"]
        for key in test_keys:
            if key not in canonical_map:
                continue
```

A `continue` like this turns a typo into a silent pass. Prefer `assert key in canonical_map` or
`pytest.mark.parametrize` over the keys, which reports each key as its own test.

### 8. The frontend tests

The frontend uses Node's built-in runner (`"test": "node --test"` in
[package.json](../frontend/package.json#L11)), which finds `*.test.js` files by itself. No Jest,
no Vitest, no browser. The tests cover the two pure helper files only:
[format.test.js](../frontend/src/format.test.js) (4 tests: `131876` becomes `"131,876"` in
`en-US` and `"131.876"` in `vi-VN`, zones become `"0%–8% · 51%–100%"`) and
[i18n.test.js](../frontend/src/i18n.test.js) (2 tests: Vietnamese defines exactly the English keys
with the same kinds of values, and every message function includes its parameter). Lesson 13
explains why those two checks catch the most common translation bugs.

### 9. Adding a test: a worked example

Say you want to pin the Điểm tie-break, and record the `Hand` hash bug without fixing it yet.

**Step 1. Find out what the code does today.** Ask Python, not your memory:

```bash
python -c '
from src.evaluator import Hand
a, b = Hand.from_str("As 3h 5d"), Hand.from_str("9s 10h Kd")
print(a.score.score, b.score.score, a > b, a.score.score_tuple, b.score.score_tuple)
'
```

```
9 9 True (1, 9, 14, 9, (14, 5, 3)) (1, 9, 13, 9, (13, 10, 9))
```

Both have 9 points; A-3-5 wins because the next field is the highest card (14 against 13).

**Step 2. Write the tests** at the end of `tests/test_evaluator.py`, next to the code they protect:

```python
class TestTieBreaks:
    """House rules for equal categories (AGENTS.md §3.2 leaves them to configuration)."""

    def test_equal_points_compare_highest_card(self) -> None:
        """Two 9-point hands: the one with the higher top card wins (A > K)."""
        a35 = Hand.from_str("As 3h 5d")
        k109 = Hand.from_str("9s 10h Kd")
        assert a35.score.score == k109.score.score == 9
        assert a35 > k109

    def test_di_compares_highest_then_second_card(self) -> None:
        assert Hand.from_str("Js Qh Qd") > Hand.from_str("Jc Jh Qs")   # Q-Q-J beats Q-J-J
        assert Hand.from_str("Qs Kh Kd") > Hand.from_str("Js Qh Qc")   # K beats Q on top

    @pytest.mark.xfail(strict=True, reason="Hand.__eq__ compares scores but __hash__ hashes cards (lesson 02)")
    def test_equal_hands_have_equal_hashes(self) -> None:
        a, b = Hand.from_str("As Kh Qd"), Hand.from_str("Kh Qd As")
        assert a == b
        assert hash(a) == hash(b)
```

**Step 3. Run only the new tests**, then everything:

```bash
python -m pytest tests/test_evaluator.py -q -k TieBreaks -rx
python -m pytest -q
```

```
..x                                                                      [100%]
XFAIL tests/test_evaluator.py::TestTieBreaks::test_equal_hands_have_equal_hashes - Hand.__eq__ compares scores but __hash__ hashes cards (lesson 02)
2 passed, 18 deselected, 1 xfailed in 0.06s
...
95 passed, 1 xfailed in 1.85s
```

`xfail(strict=True)` means "this is expected to fail". The day someone fixes `Hand.__hash__`, the
test passes, `strict` turns that into a failure, and they remove the marker. A known bug stays
visible without turning the suite red. (Test this in a scratch branch, or undo it with
`git checkout -- tests/test_evaluator.py`.)

---

## 💡 Concept: what a pytest fixture is

```python
@pytest.fixture(scope="module")      # run once per test file
def model():
    return CallingRangeModel()       # the value handed to tests

def test_size(model):                # the parameter name selects the fixture
    assert len(model) == 455
```

pytest reads each test's parameter names, finds fixtures with those names (in the same file, a
`conftest.py`, or built-ins such as `capsys`, `monkeypatch`, `tmp_path`), runs them, and passes
the results in. Scopes: `function` (default), `class`, `module`, `package`, `session`.

---

## Design decisions

- **One test file per module, plus two "front door" files and one story file.** You can find the
  test for any line quickly, and the story file shows the system working as a whole.
- **Real data, no mocks for the engine.** Tests load the real `winrates.json` and build the real
  calling-range model. That catches data drift (the schema test, f = 0 equals the file) at the
  cost of slower setup, kept down by module-scoped fixtures.
- **Fakes only at the edges.** The keyboard and the API key are the only things replaced. The
  network is never used.
- **Budgets as tests, with wide margins.** Two of the five AGENTS.md budgets are asserted, with
  thresholds far above today's numbers, so they catch an accidental O(n²) without flaking on a
  slow machine. The other three are not asserted, and two of them are missed.
- **No test configuration.** One empty `__init__.py` instead of `conftest.py` or `pytest.ini`.
  Simple, but it means no shared fixtures across files and no registered markers.

---

## ⚠️ Weak spots

1. **Two AGENTS.md budgets are missed and untested.** Hand evaluation (2.5–5.3 µs vs 1 µs) and the
   CLI (0.11–0.22 s vs 50 ms), see [AGENTS.md:124-127](../AGENTS.md#L124-L127). *Fix:* either
   change the budgets to what Python can do, or add a score table and lazy imports, then test them.
2. **Memory is unmeasured.** The 10 MB budget is met (about 1.3 MiB for both tables) but nothing
   checks it. *Fix:* a `tracemalloc` test.
3. **Coverage gaps.** `Hand` hashing, Điểm/Đĩ tie-breaks, a malformed DB file, the OpenRouter
   branch, HTTP errors, the CLI fallback and `App.jsx` (section 7).
4. **A loop that skips silently.** [test_generator.py:71-72](../backend/tests/test_generator.py#L71-L72)
   never checks `"10-J-K"`. *Fix:* parametrise, or assert membership.
5. **Shared global app.** Every API test uses the module-level app of `app.py`
   ([test_api.py:9](../backend/tests/test_api.py#L9) mutates its config), so tests cannot inject a
   small database. *Fix:* an app factory and a fixture that builds the app.
6. **Single-shot timing.** [test_calling_range.py:74-78](../backend/tests/test_calling_range.py#L74-L78)
   times one call. On a busy CI machine a single pause could fail it. *Fix:* take the best of
   several runs, as `timeit.repeat` does.
7. **Decorative "-> PASS".** The scenario narratives print PASS before the test has finished
   ([test_dynamic_scenarios.py:76](../backend/tests/test_dynamic_scenarios.py#L76)).
8. **No CI.** Nothing runs the suite on a push (lesson 16).

---

## 🧪 Try it

Backend commands run from `backend/` with the virtual environment active; npm from `frontend/`.

```bash
python -m pytest -q
```

```
........................................................................ [ 77%]
.....................                                                    [100%]
93 passed in 1.74s
```

Count tests per file:

```bash
python -m pytest --collect-only -q | grep '::' | cut -d: -f1 | sort | uniq -c
```

```
     17 tests/test_api.py
      9 tests/test_calling_range.py
      6 tests/test_cli.py
      6 tests/test_db.py
      6 tests/test_dynamic_scenarios.py
     18 tests/test_evaluator.py
     13 tests/test_ev.py
      7 tests/test_generator.py
      5 tests/test_hands.py
      6 tests/test_range_finder.py
```

Run just the timing tests, by name:

```bash
python -m pytest -k "latency or budget" -v
```

```
tests/test_calling_range.py::TestCallingRangeModel::test_full_table_within_latency_budget PASSED [ 50%]
tests/test_db.py::TestWinRateDB::test_lookup_latency_budget PASSED       [100%]

======================= 2 passed, 91 deselected in 0.33s =======================
```

Read the stories: `python -m pytest tests/test_dynamic_scenarios.py -s -q`. Find the slowest
tests: `python -m pytest -q --durations=5`.

Measure the evaluation budget yourself (machine-dependent):

```bash
python -c '
import timeit
from src.evaluator import Hand, evaluate_hand
cards = Hand.from_str("As Kh Qd").cards
print(round(min(timeit.repeat(lambda: evaluate_hand(cards), number=100000, repeat=5)) / 100000 * 1e6, 2), "us")
'
```

```
2.53 us
```

The frontend:

```bash
npm test 2>&1 | grep -E "^ok|^# (tests|pass|fail)"
```

```
ok 1 - formatMoney uses the requested locale's thousands separator
ok 2 - formatMoney rounds to whole VND and keeps the minus sign
ok 3 - formatMoney shows 0 before any value has arrived
ok 4 - formatZones lists every profitable fold-frequency interval
ok 5 - every language defines exactly the English keys, with the same kinds of values
ok 6 - messages with a parameter include it in every language
# tests 6
# pass 6
# fail 0
```

---

## 🏋️ Exercises

Exercises marked 🟡 or 🔴 change code. Undo them afterwards with `git checkout -- <file>`.

**🟢 1. Predict.** You delete `backend/tests/__init__.py` and run `python -m pytest -q` from
`backend/`. What happens? And with plain `pytest -q`?

<details><summary>Solution</summary>

`python -m pytest` still passes all 93, because `-m` adds the current folder (`backend/`) to
`sys.path`. Plain `pytest` gets 10 collection errors, one per file:
`ModuleNotFoundError: No module named 'src'`. Restore it with
`git checkout -- tests/__init__.py`.
</details>

**🟢 2. Predict.** You change `scope="module"` to the default scope on the `model` fixture in
`test_calling_range.py`. Does anything fail? What changes?

<details><summary>Solution</summary>

Nothing fails. The model is built once per test instead of once per file: 9 builds instead of 1.
On the course machine one build showed up as about 0.1 s of "setup" in `--durations`, so the file
gets slower. Scope is a speed choice here, because no test mutates the model.
</details>

**🟢 3. Predict.** Fix the key in [test_generator.py:69](../backend/tests/test_generator.py#L69)
from `"10-J-K"` to `"K-J-10"`. Does the test still pass?

<details><summary>Solution</summary>

Yes. K-J-10 is an ordinary 0-point Điểm hand (10, J and K are all worth 0), and its rates add up
like every other hand's. The point of the fix is that the sixth key is now actually checked, which
makes the test a little slower. Run `python -m pytest tests/test_generator.py -q`: 7 passed.
</details>

**🟡 4. Add the worked example.** Add the `TestTieBreaks` class from section 9 to
`tests/test_evaluator.py`. Check: `python -m pytest -q` reports `95 passed, 1 xfailed`.

<details><summary>Solution</summary>

Paste the class at the end of the file (it uses `Hand` and `pytest`, both already imported). If you
see `96 passed`, someone has fixed `Hand.__hash__` and you will see the `xfail` turn into an
`XPASS(strict)` failure: remove the marker.
</details>

**🟡 5. Test a malformed database.** Use pytest's `tmp_path` fixture to write a broken JSON file
and a file with a missing field, and assert that `WinRateDB.load` raises `DatabaseError` for both.
Check: `python -m pytest tests/test_db.py -q` shows 8 passed.

<details><summary>Solution</summary>

```python
    def test_malformed_json_raises(self, tmp_path) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        with pytest.raises(DatabaseError, match="Malformed JSON"):
            WinRateDB().load(bad)

    def test_missing_field_raises(self, tmp_path) -> None:
        bad = tmp_path / "schema.json"
        bad.write_text('{"A-A-A": {"equity": 1.0}}', encoding="utf-8")
        with pytest.raises(DatabaseError, match="Invalid record schema"):
            WinRateDB().load(bad)
```

`tmp_path` is a fresh temporary folder per test, deleted by pytest later.
</details>

**🔴 6. Test the OpenRouter branch offline.** Set a fake key with `monkeypatch.setenv`, replace
`requests.post` with a function that returns an object with `status_code = 500` and `text =
"boom"`, and assert that `/api/analyze` answers 502 with an `error` containing `500`. Add a
second test where the fake raises `requests.ConnectionError`.

<details><summary>Hints</summary>

```python
class FakeResponse:
    status_code = 500
    text = "boom"

monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
monkeypatch.setattr("app.requests.post", lambda *args, **kwargs: FakeResponse())
```

Patch `app.requests.post`, the name `app.py` uses. Nothing reaches the network, and the 502 body
shows the upstream text, which is weak spot 8 of lesson 10.
</details>

**🔴 7. Turn a budget into a test.** Add a memory test: build a `WinRateDB` and a
`CallingRangeModel` under `tracemalloc` and assert that the memory they keep is under 10 MB
(AGENTS.md §6). Then decide what to do about the evaluation budget, and write the decision down
in a test or in AGENTS.md.

<details><summary>Hints</summary>

`tracemalloc.start()`, read `tracemalloc.get_traced_memory()[0]` before and after building the
objects, and keep references to them until after the second reading. On the course machine the
difference was about 151 KiB for the DB and 1.1 MiB for the model. For evaluation, either assert
a realistic limit (for example < 20 µs, with `timeit.repeat`) or change AGENTS.md §6: a budget
nobody checks drifts into fiction.
</details>

---

## ❓ Quiz

1. Why do 91 test functions produce 93 tests?
2. What does the empty `tests/__init__.py` change?
3. Why are the calling-range fixtures module-scoped while the API `client` is function-scoped?
4. Which AGENTS.md §6 budgets are met, and which are tested?
5. How does the suite guarantee that `/api/analyze` never calls OpenRouter during a test run?

<details><summary>Answers</summary>

1. Two tests are parametrised with two cases each: `test_analyze_rejects_malformed_hand_evaluation`
   and `test_invalid_input_exits_with_message`.
2. It makes `tests/` a package, so pytest puts its parent `backend/` on `sys.path`, which makes
   `import src` and `from app import app` work however pytest is started.
3. Building a `CallingRangeModel` takes tens of milliseconds and no test changes it, so sharing it
   saves time. A test client is cheap, and a fresh one per test keeps tests independent.
4. Met: lookup, full range EV, memory. Missed: hand evaluation and the CLI. Tested: lookup
   ([test_db.py:45](../backend/tests/test_db.py#L45)) and the equity table
   ([test_calling_range.py:74](../backend/tests/test_calling_range.py#L74)).
5. The only test that reaches the LLM branch, [test_api.py:72](../backend/tests/test_api.py#L72),
   first removes `OPENROUTER_API_KEY` with `monkeypatch.delenv`; the other analyze tests fail
   validation before the key is read.
</details>

---

## Recap

- 93 backend tests in 10 files (one per module, plus CLI, API and stories) and 6 frontend tests;
  the backend suite runs in about 2 s.
- `tests/__init__.py` is the whole pytest configuration: it puts `backend/` on `sys.path`.
- Fixtures share expensive objects per module; `monkeypatch` fakes the keyboard and removes the
  API key; `capsys` captures output; `-s` shows the story narratives.
- Two budgets are asserted with wide margins (lookup, equity table) and met. Hand evaluation
  (2.5–5.3 µs) and the CLI (0.11–0.22 s) miss theirs and are untested.
- Known gaps: `Hand` hashing, tie-breaks, a malformed DB, OpenRouter, HTTP errors, the CLI
  fallback, `App.jsx`, and a silently skipped key.
- New test: find the current behaviour by running code, pin it next to the module's other tests,
  and use `xfail(strict=True)` for a known bug you are not fixing yet.

**Next:** [16 — Deployment](16-deployment.md)
