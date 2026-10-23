# 18 — Pitfalls and Next Steps

> **Goal:** review every weakness found while rebuilding the project in one place: what has already
> been fixed (and how), what is still open, and what the newest code introduced. Then decide what to fix
> first and get ideas for taking the project further.
> **You will build:** nothing required. This chapter is a menu of improvements to practise on.
> **Time:** ~45 minutes to read; as long as you like to implement.
> **Prerequisites:** chapters 1–17.

---

## The big picture

You rebuilt the project **exactly as it is**, so the original tests could act as your answer key. Along
the way, ⚠️ Pitfall boxes pointed out problems and ✅ boxes showed problems that a later version of the
code had already fixed. Both are worth studying: real projects always contain rough edges, and they
improve one fix at a time. Being able to **find, explain, prioritise, and fix** such issues is a core
engineering skill, often more valuable than writing new code.

A good way to fix any of them:

1. **Write a failing test** that shows the problem (e.g.
   `assert client.post("/api/analyze", json={"pot": "abc"}).status_code == 400`).
2. Make the **smallest change** that makes it pass.
3. Run the **whole** suite (`python -m pytest -q`; `npm run lint && npm run build`).
4. Commit with a message that explains *why*.

This loop is called **test-driven development (TDD)**.

---

## 1. ✅ Already fixed: learn from the before/after

These problems existed in the first version of the project and are fixed in the current code. Each fix
is a small case study in refactoring.

| Problem in the first version | How the current code fixes it | Lesson | Ch |
|---|---|---|---|
| Equity measured only against a **random** hand, so medium hands looked far better than they are | `CallingRangeModel`: exact equity against the opponent's strongest `1 − f`, with card removal; `opponent_model` in every API endpoint and a UI toggle | Name your model's biggest assumption, then build the alternative and let users compare | [09](09-calling-range.md) |
| A single "break-even fold equity" couldn't describe EV that rises, falls and rises again | `profitable_fold_zones` scans a 1% grid and returns all +EV intervals; the UI draws them as a profit map | When a quantity isn't monotonic, return the shape, not one number | [10](10-expected-value.md) |
| Number validation copy-pasted into 3 endpoints, already drifting apart | `GameParams` + `_parse_game_params` + one `@app.errorhandler` | Extract repeated blocks before the copies diverge | [13](13-flask-api.md) |
| Root endpoint listed 3 of 5 API endpoints | List completed | Hand-maintained lists drift (generating them is even better) | [13](13-flask-api.md) |
| Frontend **guessed** per-category counts with wrong totals (Đĩ 288, Điểm 20,992) copied from `DESIGN.md` | Backend sends `category_breakdown` computed from data (144 / 21,136); docs corrected | Compute a fact once, where the data lives | [13](13-flask-api.md), [16](16-building-the-ui.md) |
| Every frontend error (even "invalid hand") shown as "SOLVER DAEMON OFFLINE" | `solveError = { key, detail }`: `invalidInput` (server said no) vs `solverOffline` (no answer) | An error message must describe the error that happened | [16](16-building-the-ui.md) |
| Linter warning: `catch (err)` with `err` unused | Optional catch binding: `catch {` | Read linter warnings; they're free code review | [16](16-building-the-ui.md) |
| UI only in English | `i18n.js` with `STRINGS.en` / `STRINGS.vi`, function-valued messages, keys stored in state, choice saved in `localStorage` | Store keys, not sentences; texts with variables are functions | [16](16-building-the-ui.md) |

---

## 2. ⚠️ Still open

**Severity:** 🔴 wrong output or crash · 🟠 fragile / misleading / breaks the project's own rules ·
🟡 cleanliness.

### Backend: correctness and robustness

| # | Sev | File | Issue | Suggested fix | Ch |
|---|---|------|-------|---------------|----|
| 1 | 🔴 | `app.py` | `/api/analyze` doesn't validate input; `{"pot": "abc"}` → **500** | now a one-liner: `params = _parse_game_params(data)` at the top | [13](13-flask-api.md) |
| 2 | 🔴 | `cli.py` | `LiengError` not caught; a bad `--hand` prints a traceback | `except LiengError as err: print(...)` | [12](12-cli.md) |
| 3 | 🟠 | `generator.py` | default mode is Monte Carlo, but tests require exact data (`samples == 18424`) | make `--exact` the default | [07](07-generator-simulation.md) |
| 4 | 🟠 | `test_api.py` | `test_analyze_endpoint` calls the real OpenRouter API if `OPENROUTER_API_KEY` is set | `monkeypatch.delenv(...)` | [13](13-flask-api.md) |
| 5 | 🟠 | `evaluator.py` | `Hand.__eq__` compares scores but `__hash__` uses cards | drop `__eq__`, compare `.score` explicitly | [05](05-hand-evaluator.md) |
| 6 | 🟠 | `hands.py` | canonical IDs inconsistent: `Q-K-A`/`A-2-3` ascending, `K-Q-J`/`9-8-7` descending | one naming rule, or normalise input | [06](06-combinatorics-canonical-hands.md) |
| 7 | 🟠 | `db.py` | silent fallback to `backend/data/…` when a path isn't found | callers pass absolute paths; fail if missing | [08](08-database-layer.md) |
| 8 | 🟠 | `range_finder.py` | constructor silently calls `db.load()` with the default path | raise `DatabaseNotLoadedError` instead | [11](11-range-finder.md) |
| 9 | 🟠 | `generator.py` | `random.seed()` resets Python's global random generator | `rng = random.Random(seed)` | [07](07-generator-simulation.md) |
| 10 | 🟡 | `generator.py` | `total_showdowns = 18424` hard-coded | count `wins + ties + losses` | [07](07-generator-simulation.md) |
| 11 | 🟡 | `db.py` | unknown IDs raise a plain `KeyError` | `HandNotFoundError(LiengError, KeyError)` | [08](08-database-layer.md) |

### Backend: design and cleanliness

| # | File | Issue | Suggested fix | Ch |
|---|------|-------|---------------|----|
| 12 | `app.py` | response field names still differ between endpoints (`decision` vs `recommended_action`, `bet` vs `bet_size`, `equity` vs `showdown_equity`) | one "serialise" helper per record type | [13](13-flask-api.md) |
| 13 | `app.py` | DB, calling model and finder are module-level globals built at import (~0.25 s) | application factory `create_app(db_path)` | [13](13-flask-api.md) |
| 14 | `app.py` | LLM model name hard-coded twice; 502 responses leak upstream error text | env var `OPENROUTER_MODEL`; log details server-side | [13](13-flask-api.md) |
| 15 | `cli.py` | stdout reconfigured and `_console` created at import; `except Exception: pass` | do it in `main()`; catch specific errors | [12](12-cli.md) |
| 16 | `hands.py` | `CanonicalHand` has `<`, `>`, `==` but not `<=`/`>=`; same eq/hash pattern | `functools.total_ordering`, or compare `.score` | [06](06-combinatorics-canonical-hands.md) |
| 17 | `hands.py` | A-2-3 / Q-K-A ordering logic duplicated in two functions | shared helper (DRY) | [06](06-combinatorics-canonical-hands.md) |
| 18 | `ev.py` | unreachable `denominator <= 0` branch; `pot + 2*bet` formula repeated in many places | delete dead code; one helper | [10](10-expected-value.md) |
| 19 | several | `TOTAL_COMBINATIONS` defined in both `range_finder.py` and `calling_range.py`; `22100` literals in `app.py`; category totals typed in `cli.py` | one shared constant; compute totals from data | [09](09-calling-range.md), [12](12-cli.md) |
| 20 | several | unused imports (`Final`, `Hand`, `HandStats`, `InvalidCardError`, `calculate_ev`, `Text`, …) | run a linter such as `ruff` | [06](06-combinatorics-canonical-hands.md) |

### Performance (`AGENTS.md` §6)

| # | Budget | Measured | Suggested fix | Ch |
|---|--------|----------|---------------|----|
| 21 | hand evaluation < 1 µs | ~3–10 µs | precomputed dict: sorted rank triple → `HandScore` | [05](05-hand-evaluator.md), [14](14-testing-and-performance.md) |
| 22 | CLI command < 50 ms | ~120 ms (~100 ms is imports) | import `rich` lazily | [14](14-testing-and-performance.md) |

### Frontend and deployment

| # | File | Issue | Suggested fix | Ch |
|---|------|-------|---------------|----|
| 23 | `App.jsx` | "LIVE SOLVER / 455 CLASSES LOADED" is static text | read `/health` | [16](16-building-the-ui.md) |
| 24 | `App.jsx` | LLM Markdown shown as raw text (`**bold**`) | a Markdown renderer (never raw HTML) | [16](16-building-the-ui.md) |
| 25 | `App.jsx` | five copy-pasted hand-preset buttons; specs card says "MONTE CARLO" though data is exact | `.map` over an array; fix the label | [16](16-building-the-ui.md) |
| 26 | `vite.config.js` | `/api` proxy configured but unused (absolute URL used instead) | pick one mechanism | [15](15-frontend-foundations.md) |
| 27 | `src/assets`, `public` | unused starter files from the Vite template | delete | [15](15-frontend-foundations.md) |
| 28 | `app.py` / deploy | CORS allows every origin; no rate limit on `/api/analyze` | restrict origin; `Flask-Limiter` | [17](17-deployment.md) |

---

## 3. 🆕 Introduced by the newest code

New features bring new edge cases. None of these breaks the app, but each is worth understanding.

| # | Sev | Where | Issue | Suggested fix | Ch |
|---|---|---|---|---|---|
| N1 | 🟠 | `range_finder.py` | `get_profitable_range` has no `opponent_model` parameter: it always uses the random model | add the parameter and pass it through | [11](11-range-finder.md) |
| N2 | 🟠 | `range_finder.py` / API | under the range model many hands have equity 0 → tied EV → `threshold_hand` is arbitrary (`A-A-K` at 35%) | add hand strength as a third sort key | [11](11-range-finder.md) |
| N3 | 🟠 | `app.py` | `break_even_fold_equity` means "exact EV = 0" (random) or "start of the last +EV zone" (range) | separate field names, or only the zones | [13](13-flask-api.md) |
| N4 | 🟡 | `ev.py` | zones are on a 1% grid: a bluff's threshold 0.5 is reported as 0.51 | document it; finer grid or bisection where exactness matters | [10](10-expected-value.md) |
| N5 | 🟡 | `calling_range.py` | modelling choices: the opponent is a perfect strength-sorter, and the range boundary ignores card removal | document; optional "mixed" model (see §5) | [09](09-calling-range.md) |
| N6 | 🔴 | `App.jsx` | `formatMoney` always uses `vi-VN`: in English mode EV shows `+131.876` (reads like a decimal) next to `22,100` | `formatMoney(num, t.locale)` | [16](16-building-the-ui.md) |
| N7 | 🟡 | `App.jsx` | no profitable zone → "RAISE +EV WHEN OPP. FOLDS:" followed by nothing | a "NEVER" i18n text | [16](16-building-the-ui.md) |
| N8 | 🟡 | UI vs API | UI defaults to `range`, API defaults to `random`: the same request can give different answers | document clearly; show the model in every result (the API echoes it) | [16](16-building-the-ui.md) |
| N9 | 🟠 | `i18n.js` | nothing checks that `vi` has every key of `en` (a missing function key crashes) | a key-parity test, or TypeScript types | [16](16-building-the-ui.md) |
| N10 | 🟡 | `cli.py` | the CLI only offers the random model | `--opponent-model {random,range}` | [12](12-cli.md) |
| N11 | 🟡 | `test_dynamic_scenarios.py` | scenario tests only exercise the random model | a sixth scenario: one medium hand under both models | [14](14-testing-and-performance.md) |
| N12 | 🟡 | `test_calling_range.py` | a test reads the private `_prefix` attribute | acceptable trade-off; or expose a public "row total" method | [09](09-calling-range.md) |

### Documentation

| # | File | Says | Reality |
|---|------|------|---------|
| D1 | `README.md` | React 18; Node.js 18+ | React **19**; Vite 8 needs Node **20.19+ / 22.12+** |
| D2 | `README.md` | "58 Tests Passing" (badge and coverage summary) | **76** tests |
| D3 | `README.md` | `/api/evaluate` returns `"hand": "A♠ K♥ Q♦"` and break-even `0.3333333333333333` | `"As Kh Qd"` and `0.3333`; responses also contain `opponent_model`, `equity_vs_random` |
| D4 | `README.md` | deploy with `gunicorn -w 4`; links a `LICENSE` file | Procfile uses `--workers 2`; no `LICENSE` file exists |
| D5 | `README.md` | repository layout | doesn't list `calling_range.py`, `test_calling_range.py`, `i18n.js` |

(`README.md` and `DESIGN.md` now have the correct category totals and document both opponent models.)

---

## 4. If you only fix five things

1. **#1**: validate `/api/analyze`. It's a crash from user input, and with `_parse_game_params` the fix
   is one line plus a test.
2. **N6**: the English number format. Users read wrong numbers.
3. **N1**: `get_profitable_range` ignoring the model. A silent wrong answer waiting for its first caller.
4. **#2**: catch `LiengError` in the CLI. A crash on a typo.
5. **#4**: make the API tests offline. Tests must never depend on the internet.

Each takes under an hour, and each deserves its own failing test first.

---

## 5. Ideas, from small to ambitious

**Engineering practice**

- Add **type checking** (`pip install mypy` → `mypy --strict src`) and a **linter** (`ruff check .`), and fix
  what they report. `AGENTS.md` already asks for mypy compliance.
- Add **continuous integration**: a GitHub Actions workflow that runs `pytest`, `npm run lint` and
  `npm run build` on every push.
- Measure **test coverage** (`pip install pytest-cov` → `pytest --cov=src`) and test the uncovered branches
  (e.g. malformed JSON in `db.py`).
- Add **frontend tests** with Vitest and React Testing Library: "clicking a preset updates the input",
  "switching to VI translates the error box", and the i18n key-parity test (N9).
- Cache `/api/solve` results with `functools.lru_cache` keyed by `(pot, bet, fold_equity, opponent_model)`.

**Product features**

- Show the **threshold hands** (weakest profitable hands) instead of always the same top-10 Sáp hands,
  with strength as a tie-breaker (N2).
- An `--opponent-model` option for the CLI (N10).
- Let the user pick **house rules** (e.g. Đĩ ties are split; Ace-high or not for Điểm tie-breaks). The rule
  lives in one line of `evaluate_hand`, but the data must be regenerated per rule set.
- A **bet-size explorer**: chart EV against bet size for one hand under both models and find the best bet.

**Better opponent modelling** (building on chapter 9)

- A **mixed model**: the opponent folds their weakest hands with probability `p` and folds at random
  otherwise. The equity when called is then a weighted mix of the two models' equities, so "random" and
  "range" become the two ends of one slider.
- A **card-removal-aware boundary**: define "the top `1 − f`" over the 18,424 hands actually possible
  given Hero's cards, using a binary search on Hero's own prefix row instead of the shared `_cum_mult`.
- **Bet-size-dependent fold equity**: real opponents fold more to bigger bets; model `f` as a function of
  `B / P` instead of a fixed number.

**Game theory (ambitious)**

- **Multi-way pots** (3+ players): exact enumeration explodes, so this is where the Monte Carlo code
  path becomes essential.
- **Re-raises and multiple betting rounds**: model the game as a tree and compute a real equilibrium
  strategy with **Counterfactual Regret Minimisation (CFR)**, the algorithm behind modern poker AIs.
  That would make the "GTO" in the UI's subtitle accurate. Today the tool computes EV against fixed
  assumptions, which is useful, but it isn't an equilibrium.

---

## ✅ Checkpoint: what you can now do

- [ ] Explain the rules of Liêng and turn them into a total ordering with tuples.
- [ ] Count combinations, and use isomorphism to shrink a search space (22,100 → 455).
- [ ] Compute probabilities exactly (enumeration) or approximately (Monte Carlo), in parallel.
- [ ] Model an opponent's calling range with card removal, prefix sums and binary search.
- [ ] Derive an Expected Value formula and its break-even point, and handle EV that isn't monotonic.
- [ ] Structure a Python project into pure domain modules, a data layer, and presentation layers (CLI, API).
- [ ] Build and test a Flask JSON API with shared validation, error handlers, CORS and an external service call.
- [ ] Build a bilingual React dashboard with state, effects, fetch and a small chart, styled with CSS
      variables, grid and flexbox.
- [ ] Measure performance against a budget, and deploy backend and frontend separately.
- [ ] Read code critically: spot contract violations, hidden side effects, duplicated facts, stale docs and
      model assumptions, and recognise good fixes when you see them.

## Recap

- **8 problems already fixed** in the current code: the calling-range model, profit zones, shared
  validation, backend-computed category counts, honest error messages, i18n and more. Study the
  before/after.
- **28 older issues still open** (crashes #1–#2, fragile defaults, contract violations, missed budgets…)
  and **12 new ones** introduced with the new features (N1–N12), plus stale README sections (D1–D5).
- Fix them test-first: failing test → smallest change → full suite → commit.
- Plenty of room to grow: type checking, CI, frontend tests, mixed opponent models, bet-size-dependent
  folds, multi-way pots, CFR.

**Back to:** [the index](README.md)
