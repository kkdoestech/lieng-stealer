# Lesson 15 — Tests and performance

> **Goal:** know what the 159 backend tests and 18 frontend tests check, how their fixtures and
> imports work, what ruff, mypy and CI add, which performance budgets from AGENTS.md §6 the code
> meets, and where the gaps are so you can add the next test yourself.
> **Files:** [`backend/tests/`](../backend/tests), [`backend/pyproject.toml`](../backend/pyproject.toml),
> [`frontend/src/*.test.js(x)`](../frontend/src/App.test.jsx), [`.github/workflows/ci.yml`](../.github/workflows/ci.yml),
> [`AGENTS.md`](../AGENTS.md#L124-L130).
> **Time:** ~60 min. **Before this:** [14 — Styling and DESIGN.md](14-styling.md) (the backend half only needs [11](11-request-trace.md))
> (lessons 12–14 help with the frontend tests).

---

## Where this fits

```
                       python -m pytest (backend/)              npm test (frontend/, Vitest)
                                │                                        │
 unit tests ─────────── test_evaluator, test_exceptions, test_hands,  format.test.js
 (one module each)      test_generator, test_db, test_calling_range,  i18n.test.js
                        test_ev, test_range_finder
 front-door tests ───── test_cli (main(argv)), test_api (create_app)  App.test.jsx (fetch mocked)
 story tests ────────── test_dynamic_scenarios (6 player stories, both models)
 timing tests ───────── test_evaluator.py:298, test_db.py:50, test_calling_range.py:76  ← AGENTS.md §6
 static checks ──────── ruff check . · mypy (strict)                  npm run lint (oxlint)
                                └──────────── .github/workflows/ci.yml runs all of it ───┘
```

Each earlier lesson ran its module's tests. This lesson looks at the suite as a whole: how it is
organised, what keeps it fast and offline, what it measures, and what it does not cover.

---

## Reading order

| # | Location | What to look for |
|---|----------|------------------|
| 1 | [tests/__init__.py](../backend/tests/__init__.py) and [pyproject.toml:21-22](../backend/pyproject.toml#L21-L22) | One docstring line that decides how imports work, and the only pytest setting. |
| 2 | [test_api.py:18-33](../backend/tests/test_api.py#L18-L33) | Module-scoped services, an app built by `create_app`, a function-scoped client. |
| 3 | [test_dynamic_scenarios.py:29-41](../backend/tests/test_dynamic_scenarios.py#L29-L41) | Module-scoped fixtures and an absolute data path. |
| 4 | [test_cli.py:39-42](../backend/tests/test_cli.py#L39-L42) and [test_api.py:324-335](../backend/tests/test_api.py#L324-L335) | `monkeypatch`: a fake keyboard and a fake OpenRouter. |
| 5 | [tests/perf.py](../backend/tests/perf.py), [test_evaluator.py:298-302](../backend/tests/test_evaluator.py#L298-L302), [test_db.py:50-62](../backend/tests/test_db.py#L50-L62), [test_calling_range.py:76-80](../backend/tests/test_calling_range.py#L76-L80) | The three timing tests and the factor that scales them. |
| 6 | [AGENTS.md:124-130](../AGENTS.md#L124-L130) | The five performance budgets, with measurements. |
| 7 | [pyproject.toml:1-19](../backend/pyproject.toml#L1-L19) and [ci.yml](../.github/workflows/ci.yml) | ruff, strict mypy, and the three CI jobs. |
| 8 | [App.test.jsx](../frontend/src/App.test.jsx), [format.test.js](../frontend/src/format.test.js), [i18n.test.js](../frontend/src/i18n.test.js) | Vitest, jsdom and a fake `fetch`. |

---

## Walkthrough

### 1. The test map

Counted with `python -m pytest --collect-only -q`. Five test functions are parametrised (three in
`test_api.py`, for example [test_api.py:216-220](../backend/tests/test_api.py#L216-L220), one in
[test_cli.py:31](../backend/tests/test_cli.py#L31) and one in
[test_exceptions.py:22](../backend/tests/test_exceptions.py#L22)), so 143 test functions make 159 tests.

| File | Tests | Fixtures (scope) | What it pins | Lesson |
|------|------:|------------------|--------------|--------|
| [test_evaluator.py](../backend/tests/test_evaluator.py) | 27 | none | card parsing, category order, A-2-3 / Q-K-A / K-A-2, Đĩ rules, points mod 10, tie-break house rules, hashing, cached score, **evaluation latency** | 01, 02 |
| [test_exceptions.py](../backend/tests/test_exceptions.py) | 8 | none | every class's parents in the exception hierarchy | 01 |
| [test_hands.py](../backend/tests/test_hands.py) | 8 | none | 455 classes, multiplicities summing to 22,100, suit invariance, duplicate cards, `<=` / `>=` | 03 |
| [test_generator.py](../backend/tests/test_generator.py) | 12 | `canonical_map` (module), `tmp_path` | exact equities, rate invariants, Monte Carlo within 1.5%, JSON schema, flags, local RNG, atomic write | 04 |
| [test_db.py](../backend/tests/test_db.py) | 13 | `loaded_db` (function), `real_records` (module), `tmp_path`, `monkeypatch` | loading, **lookup latency**, errors, malformed and implausible files, a failed reload, any working directory | 05 |
| [test_calling_range.py](../backend/tests/test_calling_range.py) | 12 | `model`, `db` (module) | rows ending at 18,424, f = 0 equals `winrates.json`, monotonicity, **table latency**, refuses partial or tied hand lists | 06 |
| [test_ev.py](../backend/tests/test_ev.py) | 15 | none | EV boundaries, bluff arithmetic, break-even, profit zones, folds that hurt the nuts | 07 |
| [test_range_finder.py](../backend/tests/test_range_finder.py) | 8 | `loaded_finder`, `finder_with_model` (module) | 455 sorted records, coverage, 387 vs 250 classes, tie order, category totals | 08 |
| [test_cli.py](../backend/tests/test_cli.py) | 10 | `capsys`, `monkeypatch`, `tmp_path` (built-in) | decisions per model, exit codes 1 and 2, no output before an error, interactive mode | 09 |
| [test_api.py](../backend/tests/test_api.py) | 40 | `shared_services`, `app` (module), `client`, `keyed_client` (function), `monkeypatch` | every route, one vocabulary, JSON errors, NaN and odd bodies, analysis recomputed and OpenRouter faked, rate limit, CORS, injection | 10 |
| [test_dynamic_scenarios.py](../backend/tests/test_dynamic_scenarios.py) | 6 | `client`, `solver` (module) | six player stories end to end | 11 |
| [App.test.jsx](../frontend/src/App.test.jsx) | 12 | `mockFetch` helper | verdict, error messages, language, stepper, model label, cancelled runs, StrictMode | 13 |
| [format.test.js](../frontend/src/format.test.js) | 4 | — | money per locale, rounding, zones text | 13 |
| [i18n.test.js](../frontend/src/i18n.test.js) | 2 | — | EN and VI have the same keys and kinds of values | 13 |

The whole backend suite runs in about 2 seconds. The slowest tests are in `test_generator.py`,
which enumerates real opponents: `test_rate_invariants` and `test_equity_hierarchy_monotonicity`
took 0.12–0.13 s each on the course machine (`--durations=5` shows them).

Only the unit tests for pure modules (`test_evaluator`, `test_exceptions`, `test_hands`, `test_ev`)
need no fixtures. That is the payoff of AGENTS.md's "pure functions" rule: a test is just a call and
an `assert`.

### 2. How `from src.… import …` works in a test

📍 [`backend/tests/__init__.py:1`](../backend/tests/__init__.py#L1)
```python
"""Test suite for Liêng Stealer."""
```

This file has no code, but its existence matters. pytest imports each test file as a module. If
the test folder is a **package** (it has `__init__.py`), pytest walks up to the first folder that
is *not* a package, here `backend/`, and puts that folder on `sys.path`. From there, `import src`,
`from app import create_app` and `from tests.perf import budget` work. Without `__init__.py`,
pytest would put `backend/tests/` itself on the path, and `src` would not be found.

Tested in a scratch copy with the file deleted:

| How you run it | With `__init__.py` | Without |
|----------------|--------------------|---------|
| `python -m pytest` from `backend/` | 159 collected | 159 collected (`-m` also adds the current folder to `sys.path`) |
| `pytest` from `backend/` | 159 collected | 11 collection errors: 9 × `No module named 'src'`, 2 × `No module named 'app'` |
| `python -m pytest backend/tests` from the repo root | 159 passed | 11 collection errors |

There is no `conftest.py` or `pytest.ini`. `pyproject.toml` has a two-line pytest section,
`testpaths = ["tests"]` ([pyproject.toml:21-22](../backend/pyproject.toml#L21-L22)), which only says
where to look when you give no path. The relative path `"data/winrates.json"` that several fixtures
still use works from the repo root thanks to the fallback in [db.py:83-89](../backend/src/db.py#L83-L89),
while the newer tests use the absolute `DEFAULT_DB_PATH` from `src/paths.py`.

### 3. Fixtures and their scopes

A fixture is a function whose return value pytest passes to any test that names it as a
parameter. The scope decides how often it runs.

📍 [`backend/tests/test_api.py:18-33`](../backend/tests/test_api.py#L18-L33)
```python
@pytest.fixture(scope="module")
def shared_services():
    """Load the database and build the calling-range model once for the whole module."""
    return WinRateDB(DEFAULT_DB_PATH), CallingRangeModel()


@pytest.fixture(scope="module")
def app(shared_services):
    db, model = shared_services
    return create_app(db=db, calling_model=model, config={"TESTING": True, "OPENROUTER_API_KEY": ""})


@pytest.fixture
def client(app):
    with app.test_client() as client:
        yield client
```

📍 [`backend/tests/test_dynamic_scenarios.py:29-41`](../backend/tests/test_dynamic_scenarios.py#L29-L41)
```python
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "winrates.json"


@pytest.fixture(scope="module")
def client():
    with create_app(config={"TESTING": True}).test_client() as c:
        yield c


@pytest.fixture(scope="module")
def solver():
    db = WinRateDB(DB_PATH)
    return RangeFinder(db)
```

- **Fixtures can use fixtures.** `client` asks for `app`, which asks for `shared_services`. pytest
  builds the chain once per scope.
- **Module scope**: built once per file. `CallingRangeModel()` takes about 60 ms, so
  `test_api.py`, `test_calling_range.py` and `test_range_finder.py` share one per file.
- **Function scope** (the default): a fresh `client` for each API test. A test client is cheap, so
  this costs nothing and keeps tests independent.
- **`yield` instead of `return`**: code after `yield` runs when the fixture is torn down. Here
  the `with` block closes the test client.
- **The app factory makes the app a value.** `create_app(db=…, calling_model=…, config=…)`
  (lesson 10) builds a new app with exactly the services and settings a test wants. Tests that need
  something different build their own app: one with a key (`keyed_client`,
  [test_api.py:315-321](../backend/tests/test_api.py#L315-L321)), one with the rate limiter on, one
  with a broken range finder. `TESTING: True` also switches the rate limiter off, and
  `"OPENROUTER_API_KEY": ""` overrides whatever key your shell exports, so the analysis takes the
  offline branch.

### 4. `monkeypatch` and `capsys`: controlling the outside world

Two built-in fixtures do most of the faking in this suite:

- **`monkeypatch.setattr("builtins.input", …)`** ([test_cli.py:39-42](../backend/tests/test_cli.py#L39-L42))
  replaces the keyboard with a list of answers (lesson 09).
- **`monkeypatch.setattr(requests, "post", fake_post)`** ([test_api.py:324-335](../backend/tests/test_api.py#L324-L335))
  replaces OpenRouter. The fake records the prompt and returns a canned answer, so the test can
  check that the server sent "As Kh Qd" and not the client's fake `hand_evaluation`. A parametrised
  test feeds four kinds of failure through the same seam: a 500, an odd JSON shape, a body that
  isn't JSON, and a `ConnectionError` ([test_api.py:338-357](../backend/tests/test_api.py#L338-L357)).
- **`monkeypatch.setattr(app.extensions["lieng"].range_finder, "solve_range", boom)`**
  ([test_api.py:247-257](../backend/tests/test_api.py#L247-L257)) makes one service crash, to check
  that the 500 says "Internal server error." and nothing more.
- **`monkeypatch.chdir(tmp_path)`** ([test_db.py:140-141](../backend/tests/test_db.py#L140-L141))
  runs a test from another folder, to prove the default database path doesn't depend on it.
- **`capsys.readouterr()`** ([test_cli.py:21-23](../backend/tests/test_cli.py#L21-L23)) returns
  what was printed, as `.out` and `.err`.

Every change `monkeypatch` makes is undone after the test. Files are written only under `tmp_path`,
a fresh temporary folder per test. The network is never used, with one exception (weak spot 1).

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

All three timing tests divide their limit through one helper:

📍 [`backend/tests/perf.py:1-12`](../backend/tests/perf.py#L1-L12)
```python
"""Shared helper for timing tests.

AGENTS.md section 6 sets the performance budgets. Shared CI machines are slower and noisier than a
developer laptop, so CI sets PERF_BUDGET_FACTOR (e.g. 3) to scale every budget; locally it is 1.
"""

import os


def budget(limit: float) -> float:
    """Return ``limit`` scaled by the PERF_BUDGET_FACTOR environment variable (default 1)."""
    return limit * float(os.environ.get("PERF_BUDGET_FACTOR", "1"))
```

On your machine `budget(5.0)` is 5.0. The CI workflow sets `PERF_BUDGET_FACTOR: "3"`
([ci.yml:24-26](../.github/workflows/ci.yml#L24-L26)), so a shared runner gets three times the room
without anyone editing a test. The tests themselves:

📍 [`backend/tests/test_evaluator.py:298-302`](../backend/tests/test_evaluator.py#L298-L302)
```python
    def test_evaluation_within_latency_budget(self) -> None:
        """AGENTS.md section 6: one hand evaluation in under 1 microsecond."""
        cards = Hand.from_str("As Kh Qd").cards
        best = min(timeit.repeat(lambda: evaluate_hand(cards), number=20000, repeat=5)) / 20000
        assert best * 1e6 < budget(1.0), f"evaluate_hand took {best * 1e6:.3f} us"
```

📍 [`backend/tests/test_db.py:50-62`](../backend/tests/test_db.py#L50-L62)
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
        assert avg_latency_us < budget(5.0), f"Lookup latency too high: {avg_latency_us:.3f} us"
```

📍 [`backend/tests/test_calling_range.py:76-80`](../backend/tests/test_calling_range.py#L76-L80)
```python
    def test_full_table_within_latency_budget(self, model: CallingRangeModel) -> None:
        start = time.perf_counter()
        model.equity_table(0.35)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < budget(25.0)
```

`time.perf_counter()` is a high-resolution clock meant for measuring intervals. The three tests
show three ways to time code, from most to least robust: `timeit.repeat` takes the **best** of five
runs (noise only ever makes code slower, so the minimum is the cleanest number); the lookup test
averages 50,000 calls, so one slow call cannot fail it; the table test times a single call, which
is the noisiest, but the margin is huge. Here are all five budgets from AGENTS.md §6, measured on
the machine this course was written on (your numbers will differ):

| Budget (AGENTS.md §6) | Limit | Measured | Tested? | Met? |
|-----------------------|-------|----------|---------|------|
| Single hand evaluation | < 1.0 µs | `evaluate_hand`: 0.34 µs for Q-K-A (best of 5 × 100,000); 0.30 µs on average over all 22,100 hands | [test_evaluator.py:298-302](../backend/tests/test_evaluator.py#L298-L302) | yes |
| Hash-table lookup | < 5.0 µs | `db.get`: about 0.09 µs; `get_by_cards` (canonicalisation and a duplicate-card check): 2.5 µs | [test_db.py:50-62](../backend/tests/test_db.py#L50-L62) (`get` only) | yes |
| Full range EV (455 hands) | < 25 ms | `equity_table`: 0.35 ms; `solve_range`: 0.99–1.18 ms random, 1.40–1.62 ms range | [test_calling_range.py:76-80](../backend/tests/test_calling_range.py#L76-L80) (the table only) | yes |
| CLI command | < 300 ms (cold start) | 0.12–0.13 s random, 0.17–0.18 s range (whole process) | no | yes |
| Lookup DB memory | < 10 MB | `WinRateDB`: ~179 KiB retained; `CallingRangeModel`: ~1.04 MiB; whole Python process: 18.5 MiB peak RSS | no | yes |

Two of these used to be misses:

- **Hand evaluation** took 2.5–5.3 µs. The fix uses the fact that suits never matter: there are
  only 455 rank multisets, so `evaluate_hand` now looks the score up in a 455-entry table built once
  (lesson 02). It was checked against the old code on all 132,600 ordered hands.
- **The CLI** budget was 50 ms, which a fresh Python process with these imports cannot meet: bare
  start-up is 12–21 ms, importing `rich`'s console about 60 ms, and building the calling-range
  tables 60–80 ms (range model only). AGENTS.md now states 300 ms with the measurement and the
  reason ([AGENTS.md:129](../AGENTS.md#L129)). Changing a budget is honest when it comes with a
  number and an explanation; it is still not tested.

### 7. Static checks and CI

Two more tools run over the backend, configured in `pyproject.toml`:

📍 [`backend/pyproject.toml:1-19`](../backend/pyproject.toml#L1-L19)
```toml
# Tool configuration for the backend. Dependencies live in requirements*.txt.

[tool.ruff]
target-version = "py311"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]
ignore = ["E501"]

[tool.mypy]
python_version = "3.11"
strict = true
files = ["src", "app.py"]

[[tool.mypy.overrides]]
# flask-cors ships no type information.
module = ["flask_cors"]
ignore_missing_imports = true
```

- **ruff** is a linter: `E`/`F` are pycodestyle errors and pyflakes (unused imports, undefined
  names), `I` sorts imports, `B` is bugbear (likely bugs such as mutable default arguments), `UP`
  modernises syntax for Python 3.11. It checks the tests too.
- **mypy `strict = true`** type-checks `src/` and `app.py`: every function needs annotations, no
  implicit `Any`, no untyped calls. The tests are not in `files`, so they may stay loosely typed.
- Both are dev dependencies in [requirements-dev.txt](../backend/requirements-dev.txt), together
  with pytest and `rich`; production installs only `requirements.txt` (lesson 16).

[.github/workflows/ci.yml](../.github/workflows/ci.yml) runs three jobs on every push and pull
request: **backend** (`ruff check .`, `mypy`, `python -m pytest -q` with `PERF_BUDGET_FACTOR=3`),
**frontend** (`npm ci`, `npm run lint`, `npm test`, `npm run build`), and **course**
(`python3 learning/verify_course.py`, so a commit that moves quoted code without updating the
lessons fails).

### 8. What the tests do not check

Most of the gaps this lesson used to list are closed: `Hand` hashing and the tie-break house rules
([test_evaluator.py:253-285](../backend/tests/test_evaluator.py#L253-L285)), malformed and
implausible database files ([test_db.py:106-150](../backend/tests/test_db.py#L106-L150)), the
OpenRouter branch, HTTP errors and odd bodies ([test_api.py:216-257](../backend/tests/test_api.py#L216-L257)),
and the React component. What is left:

| Gap | Where | Why it matters |
|-----|-------|----------------|
| The CLI's plain-text fallback | [cli.py:54-61](../backend/src/cli.py#L54-L61) and every `else:` branch after `if HAS_RICH:` | `rich` is a dev dependency, so on a production install the CLI prints this branch, which no test runs. Section 10 adds the test. |
| The CLI and memory budgets | [AGENTS.md:129-130](../AGENTS.md#L129-L130) | Measured, not asserted. A slow import or a bigger table would go unnoticed. |
| One test reads your environment | [test_api.py:363-373](../backend/tests/test_api.py#L363-L373) | It builds its app without `"OPENROUTER_API_KEY": ""`, so a key exported in your shell sends real requests (weak spot 1). |
| Rounded rates | `data/winrates.json` | 151 of the 455 records have win + tie + loss = 1.0001 (lesson 04). The database accepts this within a tolerance; nothing records it as a known issue. |
| Line coverage | — | Neither `pytest-cov` nor a Vitest coverage provider is installed, so there is no coverage number. The list above comes from reading the tests against the code. |
| Frontend blind spots | lessons 12 and 14 | The App tests can't tell a relative URL from an absolute one, and nothing checks CSS against DESIGN.md. |

### 9. The frontend tests

The frontend runs [Vitest](https://vitest.dev) (`"test": "vitest run"` in
[package.json](../frontend/package.json#L11)) with jsdom as a fake browser (lesson 12). Three files,
18 tests:

- [App.test.jsx](../frontend/src/App.test.jsx) (12 tests) renders the real `App` with `fetch`
  replaced by `mockFetch` and drives it like a user: it clicks "Run solver", reads the alert, toggles
  the language, presses the stepper. It pins the error message for each API code, that a failed
  solve clears the old verdict, that the analysis request carries only the five inputs, that a
  second click cancels a slow first analysis, and that StrictMode's duplicate request is aborted.
  Eight of the 12 fail on the `App.jsx` from before these fixes.
- [format.test.js](../frontend/src/format.test.js) (4 tests: `131876` becomes `"131,876"` in
  `en-US` and `"131.876"` in `vi-VN`, zones become `"0%–8% · 51%–100%"`).
- [i18n.test.js](../frontend/src/i18n.test.js) (2 tests: Vietnamese defines exactly the English keys
  with the same kinds of values, and every message function includes its parameter).

The two small files still use Node's `assert` module; only `test` comes from Vitest. Lesson 13 reads
all three.

### 10. Adding a test: a worked example

Say you want to pin the CLI's plain-text fallback, and record the rounding problem of lesson 04
without fixing it yet.

**Step 1. Find out what the code does today.** Ask Python, not your memory. `HAS_RICH` is a module
global, so you can switch it off for one run:

```bash
python -c '
import src.cli as cli
cli.HAS_RICH = False
cli.main(["--pot", "100000", "--bet", "100000", "--fold-equity", "0.35", "--hand", "Ks Qh 3d"])
' | sed -n 12,18p
```

```
--- SOLVER OVERVIEW ---
 Profitable Classes:   387 / 455
 Combos in Range:      18,708 / 22,100 combinations
 Range Coverage:       84.65%
 Highest EV Hand:      A-A-A (EV: +165,000)
 Threshold Hand:       K-8-3 (EV: +361.50)
-----------------------
```

**Step 2. Write the tests** next to the code they protect: the fallback at the end of
`tests/test_cli.py` (it reuses that file's `MEDIUM_HAND`), the known issue at the end of
`tests/test_db.py`:

```python
def test_plain_text_fallback_shows_the_same_totals(monkeypatch, capsys):
    """Without rich the CLI prints plain text with the same numbers (the HAS_RICH branches)."""
    monkeypatch.setattr("src.cli.HAS_RICH", False)
    main(MEDIUM_HAND)
    out = capsys.readouterr().out
    assert "--- SOLVER OVERVIEW ---" in out
    assert "Combos in Range:      18,708 / 22,100 combinations" in out
    assert ">>> ACTION: RAISE / ALL-IN RECOMMENDED <<<" in out
```

```python
@pytest.mark.xfail(strict=True, reason="rates are rounded one by one, so some sums are 1.0001 (lesson 04)")
def test_stored_rates_sum_to_exactly_one() -> None:
    db = WinRateDB(DEFAULT_DB_PATH)
    off = [cid for cid, s in db.all_items().items() if round(s.win_rate + s.tie_rate + s.loss_rate, 10) != 1.0]
    assert off == []
```

**Step 3. Run only the new tests**, then everything:

```bash
python -m pytest tests/test_cli.py tests/test_db.py -q -k "fallback or exactly_one" -rx
python -m pytest -q
```

```
.x                                                                       [100%]
=========================== short test summary info ============================
XFAIL tests/test_db.py::test_stored_rates_sum_to_exactly_one - rates are rounded one by one, so some sums are 1.0001 (lesson 04)
1 passed, 23 deselected, 1 xfailed in 0.10s
...
160 passed, 1 xfailed in 1.65s
```

`monkeypatch.setattr("src.cli.HAS_RICH", False)` swaps the flag for this test only, without
uninstalling anything. `xfail(strict=True)` means "this is expected to fail". The day someone
regenerates the data with consistent rounding, the test passes, `strict` turns that into a failure,
and they remove the marker. A known bug stays visible without turning the suite red. (Do this in a
scratch branch, or undo it with `git checkout -- tests/test_cli.py tests/test_db.py`.)

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
- **Fakes only at the edges.** The keyboard, `requests.post`, one deliberately broken service and
  the working directory are the only things replaced. Settings go in through `create_app(config=…)`
  rather than by editing the environment.
- **Budgets as tests, scaled for slow machines.** Three of the five AGENTS.md budgets are asserted,
  with thresholds far above today's numbers and one factor (`PERF_BUDGET_FACTOR`) for CI, so they
  catch an accidental O(n²) without flaking on a slow runner.
- **Almost no test configuration.** One empty `__init__.py` and `testpaths`; no `conftest.py`.
  Simple, but it means no fixtures shared across files: `test_api.py`, `test_calling_range.py`
  and `test_range_finder.py` each build their own calling-range model.
- **Static checks as part of "the tests pass".** ruff and strict mypy run in CI next to pytest, so
  an unused import or a type error fails the build like a wrong number would.

---

## ⚠️ Weak spots

Fixed since the first version of this course:

- ✅ **Fixed: two AGENTS.md budgets missed and untested.** Hand evaluation is now 0.3 µs and tested
  ([test_evaluator.py:298-302](../backend/tests/test_evaluator.py#L298-L302)); the CLI budget was
  restated as < 300 ms with a measurement ([AGENTS.md:129](../AGENTS.md#L129)). The CLI budget is
  still untested (open item 2).
- ✅ **Fixed: the coverage gaps.** `Hand` hashing, Điểm/Đĩ tie-breaks, a malformed DB file, the
  OpenRouter branch, HTTP errors and `App.jsx` all have tests now (section 8). The CLI fallback is
  the one left (open item 3).
- ✅ **Fixed: a loop that skipped silently.** The rate-invariant test used `"10-J-K"` and
  `continue`d past it; it now uses `"K-J-10"` and asserts each key exists
  ([test_generator.py:66-68](../backend/tests/test_generator.py#L66-L68)).
- ✅ **Fixed: a shared global app.** API tests used to mutate the module-level app. They now build
  their own with `create_app` ([test_api.py:18-33](../backend/tests/test_api.py#L18-L33)), and one
  test checks that an injected database is the one used
  ([test_api.py:383-386](../backend/tests/test_api.py#L383-L386)).
- ✅ **Fixed: no CI.** [ci.yml](../.github/workflows/ci.yml) runs ruff, mypy, pytest, lint, Vitest,
  the build and the course checker on every push.
- ✅ **Fixed: a misleading docstring.** `test_ev.py` no longer claims more folds always raise EV
  ([test_ev.py:9-10](../backend/tests/test_ev.py#L9-L10)), and `test_folds_hurt_unbeatable_hands`
  ([test_ev.py:149-152](../backend/tests/test_ev.py#L149-L152)) shows the opposite for w = 1.

Still open:

1. **One test depends on your shell.** `test_analyze_is_rate_limited`
   ([test_api.py:363-373](../backend/tests/test_api.py#L363-L373)) builds its app without
   `"OPENROUTER_API_KEY": ""`. With the key exported, its first two requests go to the real
   OpenRouter (spending credits), and without network they come back 502, so the test fails
   (`assert [502, 502, 429] == [200, 200, 429]`). *Fix:* add the empty key to its config
   (exercise 5).
2. **Two budgets are measured but not asserted.** The CLI (0.12–0.18 s vs 300 ms) and memory
   (about 1.2 MiB vs 10 MB), [AGENTS.md:129-130](../AGENTS.md#L129-L130). *Fix:* exercises 6 and 7.
3. **The CLI's plain-text fallback is untested** ([cli.py:54-61](../backend/src/cli.py#L54-L61)).
   *Fix:* section 10.
4. **Single-shot timing.** [test_calling_range.py:76-80](../backend/tests/test_calling_range.py#L76-L80)
   times one call. `PERF_BUDGET_FACTOR` widens the limit, but a single pause can still fail it.
   *Fix:* take the best of several runs with `timeit.repeat`, as the evaluation test does.
5. **Decorative "-> PASS".** The scenario narratives print PASS before the test has finished
   ([test_dynamic_scenarios.py:76](../backend/tests/test_dynamic_scenarios.py#L76)).
6. **No coverage number**, for either half (section 8).

---

## 🧪 Try it

Backend commands run from `backend/` with the virtual environment active; npm from `frontend/`.

```bash
python -m pytest -q
```

```
........................................................................ [ 45%]
........................................................................ [ 90%]
...............                                                          [100%]
159 passed in 1.88s
```

Count tests per file:

```bash
python -m pytest --collect-only -q | grep '::' | cut -d: -f1 | sort | uniq -c
```

```
     40 tests/test_api.py
     12 tests/test_calling_range.py
     10 tests/test_cli.py
     13 tests/test_db.py
      6 tests/test_dynamic_scenarios.py
     27 tests/test_evaluator.py
     15 tests/test_ev.py
      8 tests/test_exceptions.py
     12 tests/test_generator.py
      8 tests/test_hands.py
      8 tests/test_range_finder.py
```

Run just the timing tests, by name:

```bash
python -m pytest -k "latency or budget" -v
```

```
tests/test_calling_range.py::TestCallingRangeModel::test_full_table_within_latency_budget PASSED [ 33%]
tests/test_db.py::TestWinRateDB::test_lookup_latency_budget PASSED       [ 66%]
tests/test_evaluator.py::TestErrorsAndSpeed::test_evaluation_within_latency_budget PASSED [100%]

====================== 3 passed, 156 deselected in 0.48s =======================
```

The static checks:

```bash
ruff check .
mypy
```

```
All checks passed!
Success: no issues found in 12 source files
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
0.34 us
```

The frontend:

```bash
npm test 2>&1 | grep -E 'Test Files|Tests '
```

```
 Test Files  3 passed (3)
      Tests  18 passed (18)
```

(`npx vitest run --reporter=verbose` lists all 18 by name; lesson 12 shows the list.)

---

## 🏋️ Exercises

Exercises marked 🟡 or 🔴 change code. Undo them afterwards with `git checkout -- <file>`.

**🟢 1. Predict.** You delete `backend/tests/__init__.py` and run `python -m pytest -q` from
`backend/`. What happens? And with plain `pytest -q`?

<details><summary>Solution</summary>

`python -m pytest` still passes all 159, because `-m` adds the current folder (`backend/`) to
`sys.path`. Plain `pytest` gets 11 collection errors, one per file: nine
`ModuleNotFoundError: No module named 'src'` and two `No module named 'app'` (the two files that
import the app first). Restore it with `git checkout -- tests/__init__.py`.
</details>

**🟢 2. Predict.** You change `scope="module"` to the default scope on the `model` fixture in
[test_calling_range.py:21](../backend/tests/test_calling_range.py#L21). Does anything fail? What
changes?

<details><summary>Solution</summary>

Nothing fails. The model is built once per test that asks for it instead of once per file: 10
builds instead of 1, each about 0.05–0.06 s of "setup" in `--durations`. The file goes from about
0.11 s to 0.59 s. Scope is a speed choice here, because no test mutates the model.
</details>

**🟢 3. Predict.** What happens with `PERF_BUDGET_FACTOR=0.01 python -m pytest -k "latency or budget" -q`?

<details><summary>Solution</summary>

All three timing tests fail: the budgets shrink to 0.01 µs, 0.05 µs and 0.25 ms, below what the
code can do. The messages show the measured values, for example
`AssertionError: evaluate_hand took 0.313 us` and `AssertionError: Lookup latency too high: 0.077 us`
(the table test has no message). That is the factor working in the other direction: CI uses 3 to
make room, and you can use a small factor to check that a timing test can fail at all.
</details>

**🟡 4. Add the worked example.** Add the two tests from section 10. Check: `python -m pytest -q`
reports `160 passed, 1 xfailed`, and `ruff check .` still passes.

<details><summary>Solution</summary>

Both files already import what the tests need (`main` and `MEDIUM_HAND` in `test_cli.py`;
`pytest`, `WinRateDB` and `DEFAULT_DB_PATH` in `test_db.py`). If you see `161 passed` with an
`XPASS(strict)` failure, someone has fixed the rounding: remove the marker.
</details>

**🟡 5. Make the rate-limit test independent of your shell.** First see the problem without
touching the network: `OPENROUTER_API_KEY=dummy HTTPS_PROXY=http://127.0.0.1:9 python -m pytest tests/test_api.py -q`
(the dead proxy makes every outgoing request fail at once). Then fix
[test_api.py:363-373](../backend/tests/test_api.py#L363-L373) so the same command passes.

<details><summary>Solution</summary>

Before: `1 failed, 39 passed`, with `test_analyze_is_rate_limited` getting `[502, 502, 429]`
because the app read the key from the environment and tried OpenRouter. Add the override the
`app` fixture already uses:

```python
        config={"TESTING": True, "RATELIMIT_ENABLED": True, "ANALYZE_RATE_LIMIT": "2 per minute", "OPENROUTER_API_KEY": ""},
```

Now `40 passed` with the key set. The lesson generalises: every app a test builds should state the
settings it depends on, because `create_app` reads the environment for anything you leave out.
</details>

**🔴 6. Turn the memory budget into a test.** Add a test to `test_calling_range.py` that builds a
`WinRateDB` and a `CallingRangeModel` under `tracemalloc` and asserts that the memory they keep is
under 10 MB (AGENTS.md §6).

<details><summary>Solution</summary>

```python
def test_lookup_structures_fit_the_memory_budget() -> None:
    """AGENTS.md section 6: the lookup structures stay under 10 MB."""
    tracemalloc.start()
    try:
        before = tracemalloc.get_traced_memory()[0]
        db, model = WinRateDB(DEFAULT_DB_PATH), CallingRangeModel()
        used = tracemalloc.get_traced_memory()[0] - before
    finally:
        tracemalloc.stop()
    assert db.is_loaded and model.equity_table(0.35)
    assert used < 10 * 1024 * 1024, f"{used / 1024 / 1024:.2f} MiB"
```

plus `import tracemalloc` and `from src.paths import DEFAULT_DB_PATH` at the top. It passes with
about 1.2 MiB used (179 KiB for the DB, 1.04 MiB for the model). Keep `db` and `model` referenced
until after the second reading, or the garbage collector may free them first. Memory doesn't depend
on CPU speed, so this one needs no `budget()` factor.
</details>

**🔴 7. Turn the CLI budget into a test.** Add a test to `test_cli.py` that runs
`python -m src.cli --hand "As Kh Qd" --opponent-model range` as a real subprocess three times and
asserts the best time is under `budget(300.0)` ms. Check that it passes, then that
`PERF_BUDGET_FACTOR=0.1` makes it fail with a useful message.

<details><summary>Solution</summary>

```python
def test_cli_cold_start_within_budget() -> None:
    """AGENTS.md section 6: one cold-start CLI command in under 300 ms (best of 3)."""
    argv = [sys.executable, "-m", "src.cli", "--hand", "As Kh Qd", "--opponent-model", "range"]
    times = []
    for _ in range(3):
        start = time.perf_counter()
        subprocess.run(argv, cwd=BACKEND_DIR, capture_output=True, check=True)
        times.append(time.perf_counter() - start)
    assert min(times) * 1000 < budget(300.0), f"best of 3: {min(times) * 1000:.0f} ms"
```

with `import subprocess, sys, time` (one per line, for ruff's import sorting),
`from src.paths import BACKEND_DIR` and `from tests.perf import budget`. `sys.executable` is the
Python running the tests, so the subprocess uses the same virtual environment; `cwd=BACKEND_DIR`
makes `-m src.cli` resolvable from anywhere. It passes; with `PERF_BUDGET_FACTOR=0.1` it fails with
`AssertionError: best of 3: 172 ms`. It adds about half a second to the suite, the price of testing
a cold start for real.
</details>

---

## ❓ Quiz

1. Why do 143 test functions produce 159 tests?
2. What does the empty `tests/__init__.py` change?
3. Why is the API `app` module-scoped while the `client` is function-scoped?
4. Which AGENTS.md §6 budgets are met, which are tested, and what does `PERF_BUDGET_FACTOR` change?
5. How does the suite keep `/api/analyze` from calling OpenRouter, and which test forgets to?

<details><summary>Answers</summary>

1. Five functions are parametrised: three in `test_api.py` (5, 3 and 4 cases), one in `test_cli.py`
   (2 cases) and one in `test_exceptions.py` (7 cases). 143 + 4 + 2 + 3 + 1 + 6 = 159.
2. It makes `tests/` a package, so pytest puts its parent `backend/` on `sys.path`, which makes
   `import src`, `from app import create_app` and `from tests.perf import budget` work however
   pytest is started.
3. Building the app means building its services (the calling-range model takes about 60 ms), and no
   test changes the shared app, so one per file is enough. A test client is cheap, and a fresh one
   per test keeps tests independent. Tests that need a differently configured app build their own.
4. All five are met. Three are tested: evaluation
   ([test_evaluator.py:298-302](../backend/tests/test_evaluator.py#L298-L302)), lookup
   ([test_db.py:50-62](../backend/tests/test_db.py#L50-L62)) and the equity table
   ([test_calling_range.py:76-80](../backend/tests/test_calling_range.py#L76-L80)). The factor
   multiplies every tested limit; CI sets it to 3.
5. The shared `app` fixture passes `"OPENROUTER_API_KEY": ""` ([test_api.py:27](../backend/tests/test_api.py#L27)),
   which overrides the environment, and the tests that need a key use `keyed_client` with
   `requests.post` patched. `test_analyze_is_rate_limited` builds its own app without the override,
   so it reads your shell's key.
</details>

---

## Recap

- 159 backend tests in 11 files (one per module, plus CLI, API and stories) and 18 frontend tests
  in 3 files; the backend suite runs in about 2 s.
- `tests/__init__.py` puts `backend/` on `sys.path`; `pyproject.toml` adds only `testpaths`.
- Fixtures share expensive objects per module; `create_app(config=…)` gives each test the app it
  needs; `monkeypatch` fakes the keyboard and OpenRouter; `capsys` captures output; `-s` shows the
  story narratives.
- All five AGENTS.md budgets are met. Three are asserted, scaled by `PERF_BUDGET_FACTOR`; the CLI
  (now < 300 ms) and memory budgets are not.
- ruff, strict mypy, oxlint and the course checker run in CI with the tests.
- Known gaps: one test that reads your shell's API key, the CLI fallback, two untested budgets, a
  single-shot timing test, and no coverage number.
- New test: find the current behaviour by running code, pin it next to the module's other tests,
  and use `xfail(strict=True)` for a known bug you are not fixing yet.

**Next:** [16 — Deployment](16-deployment.md)
