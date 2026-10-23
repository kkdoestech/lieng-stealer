# 18 — Pitfalls and Next Steps

> **Goal:** review every weakness found while rebuilding the project in one place: what has already
> been fixed (and how), and what is still open. Then decide what to fix next and get ideas for taking the
> project further.
> **You will build:** nothing required. This chapter is a menu of improvements to practise on.
> **Time:** ~45 minutes to read; as long as you like to implement.
> **Prerequisites:** chapters 1–17.

---

## The big picture

You rebuilt the project **exactly as it is**, so the original tests could act as your answer key. Along
the way, ⚠️ Pitfall boxes pointed out problems, and ✅ boxes showed problems that the code has since fixed.
Both are worth studying: real projects always contain rough edges, and they improve one fix at a time.
Being able to **find, explain, prioritise, and fix** such issues is a core engineering skill, often more
valuable than writing new code.

Every fix in the ✅ table below was made the same way, and you can use the same loop:

1. **Write a failing test** that shows the problem (e.g.
   `assert client.post("/api/analyze", json={"pot": "abc"}).status_code == 400`) and **watch it fail**.
2. Make the **smallest change** that makes it pass.
3. Run the **whole** suite (`python -m pytest -q`; `npm test`, `npm run lint`, `npm run build`).
4. Do a quick **mutation check**: undo the fix for a moment and confirm a test fails.
5. Commit with a message that explains *why*.

This loop is called **test-driven development (TDD)**.

---

## 1. ✅ Already fixed: learn from the before/after

These problems existed in earlier versions of the project and are fixed in the current code.

| Problem in an earlier version | How the current code fixes it | Lesson | Ch |
|---|---|---|---|
| Equity measured only against a **random** hand, so medium hands looked far better than they are | `CallingRangeModel`: exact equity against the opponent's strongest `1 − f`, with card removal; `opponent_model` in the API, CLI and UI | Name your model's biggest assumption, then build the alternative | [09](09-calling-range.md) |
| A single "break-even fold equity" couldn't describe EV that rises, falls and rises again | `profitable_fold_zones` returns all +EV intervals; the UI draws a profit map | When a quantity isn't monotonic, return the shape, not one number | [10](10-expected-value.md) |
| `get_profitable_range` ignored the opponent model | parameter added and passed through | When you extend a function, check its wrappers | [11](11-range-finder.md) |
| Equal-EV hands came out in arbitrary order (`threshold_hand` = `A-A-K`) | hand strength as a third sort key (`4-3-3` is now correctly last) | Decide tie-breaks on purpose | [11](11-range-finder.md) |
| The CLI crashed with a traceback on a typo, and only knew the random model | `--opponent-model`; `Invalid input: …` on stderr with exit code 2; interactive mode catches `LiengError`; `test_cli.py` | Use your error hierarchy at the boundary; test CLIs in-process | [12](12-cli.md) |
| The generator defaulted to Monte Carlo, whose output broke the tests | exact enumeration is the default, `--monte-carlo` is opt-in; parser tested | Make the safe choice the default | [07](07-generator-simulation.md) |
| Number validation copy-pasted into 3 endpoints, drifting apart | `GameParams` + `_parse_game_params` + one `@app.errorhandler` | Extract repeated blocks before the copies diverge | [13](13-flask-api.md) |
| `/api/analyze` answered **500** for `{"pot": "abc"}` or a malformed `hand_evaluation` | same validation as the other endpoints, plus checks for `hand_evaluation` → 400 | A shared helper makes the next fix one line | [13](13-flask-api.md) |
| `break_even_fold_equity` meant two different things depending on the model | exact value (random) or `null`; new `profitable_from_fold_equity` for both | One name, one meaning | [13](13-flask-api.md) |
| An API test called the real OpenRouter API when a key was set | `monkeypatch.delenv` forces the offline fallback | Tests must never depend on external services | [13](13-flask-api.md) |
| Root endpoint listed 3 of 5 API endpoints | list completed | Hand-maintained lists drift | [13](13-flask-api.md) |
| Frontend **guessed** per-category counts with wrong totals (Đĩ 288, Điểm 20,992) | backend sends `category_breakdown` computed from data | Compute a fact once, where the data lives | [13](13-flask-api.md), [16](16-building-the-ui.md) |
| Scenario tests covered only the random model | scenario 6: one hand under both models (mutation-checked) | A test that never failed may test nothing | [14](14-testing-and-performance.md) |
| Every frontend error (even "invalid hand") shown as "SOLVER DAEMON OFFLINE"; an unused `err` lint warning | `solveError = { key, detail }`: `invalidInput` vs `solverOffline`; `catch {` | An error message must describe the error that happened | [16](16-building-the-ui.md) |
| UI only in English | `i18n.js`: `STRINGS.en` / `STRINGS.vi`, function-valued messages, keys in state, `localStorage` | Store keys, not sentences | [16](16-building-the-ui.md) |
| English mode showed money with Vietnamese dots (`+131.876`) | `format.js`: `formatMoney(num, locale)`, unit-tested with `node --test` | Pull pure logic out of components so it can be tested | [16](16-building-the-ui.md) |
| Nothing checked that the two dictionaries stay in sync | `i18n.test.js` compares key sets, value kinds and placeholders | Let a test compare data that must match | [16](16-building-the-ui.md) |
| `README.md` showed React 18, Node 18+, "58 tests", first-version API examples, `-w 4`, and linked a missing `LICENSE` | README corrected (both opponent models, both break-even fields, real test counts) and an MIT `LICENSE` added | Trust the code and tests, then fix the docs | [13](13-flask-api.md) |

> 🔎 **A retracted "bug".** An earlier version of this chapter listed "no profitable zone → the verdict
> shows a blank text" as a frontend problem. It can't happen: at a 100% fold frequency EV equals the pot,
> which is always positive, so the zone list always ends with a zone reaching 100%. Checking a suspected
> bug against the maths **before** "fixing" it saved a pointless change (chapter 16, verdict banner).

---

## 2. ⚠️ Still open

**Severity:** 🔴 wrong output or crash · 🟠 fragile / misleading / breaks the project's own rules ·
🟡 cleanliness.

### Backend: correctness and robustness

| # | Sev | File | Issue | Suggested fix | Ch |
|---|---|------|-------|---------------|----|
| 1 | 🟠 | `evaluator.py` | `Hand.__eq__` compares scores but `__hash__` uses cards | drop `__eq__`, compare `.score` explicitly | [05](05-hand-evaluator.md) |
| 2 | 🟠 | `hands.py` | canonical IDs inconsistent: `Q-K-A`/`A-2-3` ascending, `K-Q-J`/`9-8-7` descending | one naming rule, or normalise input | [06](06-combinatorics-canonical-hands.md) |
| 3 | 🟠 | `db.py` | silent fallback to `backend/data/…` when a path isn't found | callers pass absolute paths; fail if missing | [08](08-database-layer.md) |
| 4 | 🟠 | `range_finder.py` | constructor silently calls `db.load()` with the default path | raise `DatabaseNotLoadedError` instead | [11](11-range-finder.md) |
| 5 | 🟠 | `generator.py` | `random.seed()` resets Python's global random generator | `rng = random.Random(seed)` | [07](07-generator-simulation.md) |
| 6 | 🟡 | `generator.py` | `total_showdowns = 18424` hard-coded | count `wins + ties + losses` | [07](07-generator-simulation.md) |
| 7 | 🟡 | `db.py` | unknown IDs raise a plain `KeyError` | `HandNotFoundError(LiengError, KeyError)` | [08](08-database-layer.md) |
| 8 | 🟡 | `cli.py` | a bad `--hand` is reported only **after** the whole report has been printed | parse the hand before rendering anything | [12](12-cli.md) |

### Backend: design and cleanliness

| # | File | Issue | Suggested fix | Ch |
|---|------|-------|---------------|----|
| 9 | `app.py` | response field names differ between endpoints (`decision` vs `recommended_action`, `bet` vs `bet_size`, `equity` vs `showdown_equity`) | one "serialise" helper per record type | [13](13-flask-api.md) |
| 10 | `app.py` | DB, calling model and finder are module-level globals built at import (~0.25 s) | application factory `create_app(db_path)` | [13](13-flask-api.md) |
| 11 | `app.py` | LLM model name hard-coded twice; 502 responses leak upstream error text | env var `OPENROUTER_MODEL`; log details server-side | [13](13-flask-api.md) |
| 12 | `cli.py` | stdout reconfigured and `_console` created at import; `except Exception: pass` | do it in `main()`; catch specific errors | [12](12-cli.md) |
| 13 | `hands.py` | `CanonicalHand` has `<`, `>`, `==` but not `<=`/`>=`; same eq/hash pattern | `functools.total_ordering`, or compare `.score` | [06](06-combinatorics-canonical-hands.md) |
| 14 | `hands.py` | A-2-3 / Q-K-A ordering logic duplicated in two functions | shared helper (DRY) | [06](06-combinatorics-canonical-hands.md) |
| 15 | `ev.py` | unreachable `denominator <= 0` branch; `pot + 2*bet` formula repeated in many places | delete dead code; one helper | [10](10-expected-value.md) |
| 16 | several | `TOTAL_COMBINATIONS` defined in both `range_finder.py` and `calling_range.py`; `22100` literals in `app.py`; category totals typed in `cli.py` | one shared constant; compute totals from data | [09](09-calling-range.md), [12](12-cli.md) |
| 17 | several | unused imports (`Final`, `Hand`, `HandStats`, `InvalidCardError`, `calculate_ev`, `Text`, …) | run a linter such as `ruff` | [06](06-combinatorics-canonical-hands.md) |

### Performance (`AGENTS.md` §6)

| # | Budget | Measured | Suggested fix | Ch |
|---|--------|----------|---------------|----|
| 18 | hand evaluation < 1 µs | ~3–10 µs | precomputed dict: sorted rank triple → `HandScore` | [05](05-hand-evaluator.md), [14](14-testing-and-performance.md) |
| 19 | CLI command < 50 ms | ~120 ms (~100 ms is imports; +~50 ms with `--opponent-model range`) | import `rich` lazily; cache the calling-range tables on disk | [14](14-testing-and-performance.md) |

### Frontend and deployment

| # | File | Issue | Suggested fix | Ch |
|---|------|-------|---------------|----|
| 20 | `App.jsx` | "LIVE SOLVER / 455 CLASSES LOADED" is static text | read `/health` | [16](16-building-the-ui.md) |
| 21 | `App.jsx` | LLM Markdown shown as raw text (`**bold**`) | a Markdown renderer (never raw HTML) | [16](16-building-the-ui.md) |
| 22 | `App.jsx` | five copy-pasted hand-preset buttons; specs card says "MONTE CARLO" though data is exact | `.map` over an array; fix the label | [16](16-building-the-ui.md) |
| 23 | `vite.config.js` | `/api` proxy configured but unused (absolute URL used instead) | pick one mechanism | [15](15-frontend-foundations.md) |
| 24 | `src/assets`, `public` | unused starter files from the Vite template | delete | [15](15-frontend-foundations.md) |
| 25 | `app.py` / deploy | CORS allows every origin; no rate limit on `/api/analyze` | restrict origin; `Flask-Limiter` | [17](17-deployment.md) |

### Documented limitations (by design, not bugs)

| # | Where | Note | Ch |
|---|---|---|---|
| L1 | `ev.py` | profit zones are on a 1% grid: a bluff's exact threshold 0.5 is reported as 0.51 (the exact value is in `break_even_fold_equity` under the random model) | [10](10-expected-value.md) |
| L2 | `calling_range.py` | the opponent is modelled as a perfect strength-sorter, and the range boundary ignores card removal | [09](09-calling-range.md) |
| L3 | UI vs API | the UI defaults to the `range` model, the API to `random` (backward compatibility); every response echoes `opponent_model`, and the README documents both | [16](16-building-the-ui.md) |
| L4 | `test_calling_range.py` | one test reads the private `_prefix` attribute: a deliberate trade-off for checking an important invariant | [09](09-calling-range.md) |

---

## 3. What to fix next

1. **#5**: the global `random.seed`. A one-line fix plus a test that two Monte Carlo runs with the same seed don't affect `random.random()` elsewhere.
2. **#3 + #4**: hidden file loading. Make `WinRateDB.load` and `RangeFinder.__init__` fail fast; the tests that rely on the fallback show you exactly which callers to fix.
3. **#1**: the `Hand` equality/hash contract. A test like `len({h1, h2}) == …` makes the problem visible first.
4. **#9**: consistent response field names. Agree on one name per concept, add new names next to the old ones, and remove the old names later (so clients have time to switch).
5. **#21**: render the AI advice as Markdown. Use a library that does **not** allow raw HTML, and write a test that `**bold**` becomes bold text.

---

## 4. Ideas, from small to ambitious

**Engineering practice**

- Add **type checking** (`pip install mypy` → `mypy --strict src`) and a **linter** (`ruff check .`), and fix
  what they report. `AGENTS.md` already asks for mypy compliance.
- Add **continuous integration**: a GitHub Actions workflow that runs `pytest`, `npm test`, `npm run lint` and
  `npm run build` on every push.
- Measure **test coverage** (`pip install pytest-cov` → `pytest --cov=src`) and test the uncovered branches
  (e.g. malformed JSON in `db.py`).
- Add **component tests** for the React UI (e.g. Vitest + React Testing Library): "clicking a preset updates
  the input", "switching to VI translates the error box".
- Cache `/api/solve` results with `functools.lru_cache` keyed by `(pot, bet, fold_equity, opponent_model)`.

**Product features**

- Show the **threshold hands** (the weakest hands that are still profitable) instead of always the same top-10 Sáp hands.
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
      variables, grid and flexbox, and unit-test its pure helpers with `node --test`.
- [ ] Measure performance against a budget, and deploy backend and frontend separately.
- [ ] Fix bugs test-first, and use mutation checks to prove a test protects a fix.
- [ ] Read code critically: spot contract violations, hidden side effects, duplicated facts, stale docs and
      model assumptions, and recognise good fixes when you see them.

## Recap

- **18 problems already fixed** in the current code. Study the before/after: calling-range model, profit
  zones, shared validation, clean CLI errors, exact-by-default generator, unambiguous break-even fields,
  offline tests, locale-aware numbers, tested dictionaries, corrected docs, and more.
- **25 issues still open** (contract violations, hidden I/O, missed speed budgets, …) and **4 documented
  limitations** by design.
- Fix them test-first: failing test → smallest change → full suite → mutation check → commit.
- Plenty of room to grow: type checking, CI, component tests, mixed opponent models, bet-size-dependent
  folds, multi-way pots, CFR.

**Back to:** [the index](README.md)
