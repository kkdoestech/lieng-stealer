# 17 — Pitfalls and Next Steps

> **Goal:** review every weakness found while rebuilding the project in one place, decide which to fix
> first, and get ideas for taking the project further.
> **You will build:** nothing required. This chapter is a menu of improvements to practise on.
> **Time:** ~30 minutes to read; as long as you like to implement.
> **Prerequisites:** chapters 1–16.

---

## The big picture

You rebuilt the project **exactly as it is**, so the original tests could act as your answer key. Along
the way, ⚠️ Pitfall boxes pointed out problems. None of them makes the app unusable, which is typical of
real projects: most code that "works" still has rough edges. Being able to **find, explain, and
prioritise** such issues is a core engineering skill, often more valuable than writing new code.

A good way to fix any of them:

1. **Write a failing test** that shows the problem (e.g. `assert len({h1, h2}) == 1` for the hash bug,
   or `client.post("/api/analyze", json={"pot": "abc"}).status_code == 400`).
2. Make the **smallest change** that makes it pass.
3. Run the **whole** suite (`python -m pytest -q`; `npm run lint && npm run build`).
4. Commit with a message that explains *why*.

This loop is called **test-driven development (TDD)**.

---

## 1. All pitfalls in one table

**Severity:** 🔴 gives wrong output or crashes · 🟠 fragile / misleading / violates the project's own rules
· 🟡 cleanliness.

### Backend: correctness and robustness

| # | File | Issue | Why it matters | Suggested fix | Ch |
|---|------|-------|----------------|---------------|----|
| 1 | `app.py` | `/api/analyze` doesn't validate input; `{"pot": "abc"}` → **500** | user input can crash an endpoint | shared `_parse_game_params` helper → 400 | [12](13-flask-api.md) |
| 2 | `cli.py` | `LiengError` not caught; a bad `--hand` prints a traceback | the custom error family exists to prevent exactly this | `except LiengError as err: print(...)` | [11](12-cli.md) |
| 3 | `generator.py` | default mode is Monte Carlo, but tests require exact data (`samples == 18424`) | running the generator with defaults breaks the test suite | make `--exact` the default | [07](07-generator-simulation.md) |
| 4 | `test_api.py` | `test_analyze_endpoint` calls the real OpenRouter API if `OPENROUTER_API_KEY` is set | slow, flaky, uses quota | `monkeypatch.delenv(...)` | [12](13-flask-api.md) |
| 5 | `evaluator.py` | `Hand.__eq__` compares scores but `__hash__` uses cards | breaks Python's hash/eq contract; sets behave oddly | drop `__eq__`, compare `.score` explicitly | [05](05-hand-evaluator.md) |
| 6 | `hands.py` | canonical IDs inconsistent: `Q-K-A`, `A-2-3` ascending, but `K-Q-J`, `9-8-7` descending | lookups of `"J-Q-K"` fail; a test silently skips `"10-J-K"` | one naming rule, or normalise input | [06](06-combinatorics-canonical-hands.md) |
| 7 | `db.py` | silent fallback to `backend/data/…` when a path isn't found | you can load a different file than you asked for | make callers pass absolute paths; fail if missing | [08](08-database-layer.md) |
| 8 | `range_finder.py` | constructor silently calls `db.load()` with the default path | hidden I/O; import of `app.py` can crash | raise `DatabaseNotLoadedError` instead | [10](11-range-finder.md) |
| 9 | `generator.py` | `random.seed()` resets Python's global random generator | global mutable state (forbidden by `AGENTS.md`) | `rng = random.Random(seed)` | [07](07-generator-simulation.md) |
| 10 | `generator.py` | `total_showdowns = 18424` hard-coded | wrong rates if the deck logic ever changes | count `wins + ties + losses` | [07](07-generator-simulation.md) |
| 11 | `db.py` | unknown IDs raise a plain `KeyError` | outside the `LiengError` family that callers catch | `HandNotFoundError(LiengError, KeyError)` | [08](08-database-layer.md) |

### Backend: design and cleanliness

| # | File | Issue | Suggested fix | Ch |
|---|------|-------|---------------|----|
| 12 | `app.py` | number validation copy-pasted 3×; field names differ between endpoints (`bet` vs `bet_size`, `decision` vs `recommended_action`) | one helper; one naming scheme | [12](13-flask-api.md) |
| 13 | `app.py` | DB and finder are module-level globals created at import | application factory `create_app(db_path)` | [12](13-flask-api.md) |
| 14 | `app.py` | `/` lists 3 of 6 endpoints | generate from `app.url_map` | [12](13-flask-api.md) |
| 15 | `app.py` | LLM model name hard-coded twice; 502 responses leak upstream error text | env var `OPENROUTER_MODEL`; log details server-side | [12](13-flask-api.md) |
| 16 | `cli.py` | stdout reconfigured and `_console` created at import; `except Exception: pass` | do it in `main()`; catch specific errors | [11](12-cli.md) |
| 17 | `hands.py` | `CanonicalHand` has `<`, `>`, `==` but not `<=`/`>=`; same eq/hash pattern | `functools.total_ordering`, or compare `.score` | [06](06-combinatorics-canonical-hands.md) |
| 18 | `hands.py` | A-2-3 / Q-K-A ordering logic duplicated in two functions | shared helper (DRY) | [06](06-combinatorics-canonical-hands.md) |
| 19 | `ev.py` | unreachable `denominator <= 0` branch; `pot + 2*bet` formula repeated in 5 places | delete dead code; one helper | [09](10-expected-value.md) |
| 20 | several | `22100` and category totals typed as literals in `app.py`, `cli.py` | use `TOTAL_COMBINATIONS`; compute totals from data | [11](12-cli.md) |
| 21 | several | unused imports (`Final`, `Hand`, `InvalidCardError`, `calculate_ev`, `Text`, …) | run a linter such as `ruff` | [06](06-combinatorics-canonical-hands.md) |

### Performance (`AGENTS.md` §6)

| # | Budget | Measured | Suggested fix | Ch |
|---|--------|----------|---------------|----|
| 22 | hand evaluation < 1 µs | ~3–10 µs | precomputed dict: sorted rank triple → `HandScore` | [05](05-hand-evaluator.md), [13](14-testing-and-performance.md) |
| 23 | CLI command < 50 ms | ~120 ms (~100 ms is imports) | import `rich` lazily | [13](14-testing-and-performance.md) |

### Frontend

| # | File | Issue | Suggested fix | Ch |
|---|------|-------|---------------|----|
| 24 🔴 | `App.jsx` | category matrix uses **288** (Đĩ) and **20,992** (Điểm) instead of **144** and **21,136**, and *guesses* per-category counts from one total | have `/api/solve` return per-category counts | [15](16-building-the-ui.md) |
| 25 | `App.jsx` | every error (even a 400 "invalid hand") is shown as "SOLVER DAEMON OFFLINE" | show the server's `error` message | [15](16-building-the-ui.md) |
| 26 | `App.jsx` | "LIVE SOLVER / 455 CLASSES LOADED" is static text | read `/health` | [15](16-building-the-ui.md) |
| 27 | `App.jsx` | LLM Markdown shown as raw text (`**bold**`) | a Markdown renderer (never raw HTML) | [15](16-building-the-ui.md) |
| 28 | `vite.config.js` | `/api` proxy configured but unused (absolute URL used instead) | pick one mechanism | [14](15-frontend-foundations.md) |
| 29 | `App.jsx` | five copy-pasted preset buttons; unused `tier` field; specs card says "Monte Carlo" though data is exact | `.map` over an array; remove dead data; fix label | [15](16-building-the-ui.md) |
| 30 | `src/assets`, `public` | unused starter files from the Vite template | delete | [14](15-frontend-foundations.md) |
| 31 | `app.py` / deploy | CORS allows every origin; no rate limit on `/api/analyze` | restrict origin; `Flask-Limiter` | [16](17-deployment.md) |

### Documentation

| # | File | Says | Reality |
|---|------|------|---------|
| 32 | `README.md` | React 18; Node 18+ | React **19**; Vite 8 needs Node **20.19+ / 22.12+** |
| 33 | `README.md` | `/api/evaluate` returns `"hand": "A♠ K♥ Q♦"` and break-even `0.3333333333333333` | `"As Kh Qd"` and `0.3333` |
| 34 | `README.md` | deploy with `gunicorn -w 4`; links a `LICENSE` file | Procfile uses `--workers 2`; no `LICENSE` file exists |
| 35 | `DESIGN.md` | Đĩ = 288 combos, Điểm = 20,992 | 144 and 21,136 (the source of bug #24) |

> 💡 **If you only fix five things**, fix #24 (wrong numbers on screen), #1 (a crash from user input),
> #3 (defaults that break the tests), #4 (tests depending on the internet) and #2 (crash on a typo).
> They're user-visible or make the project fragile, and each takes under an hour.

---

## 2. The biggest modelling limitation: equity against a calling range

The EV formula needs **P(Win | Call)**: the chance we win **given that the opponent called**. The project
uses the equity against a **random** hand instead (chapter 7). But opponents fold their weak hands and call
with strong ones, so the hands we meet at showdown are better than random.

You can model this with a **calling range**: assume the opponent calls only with their strongest
`call_fraction` of hands. Here is a working sketch (exact enumeration, like the generator):

```python
import itertools

from src.evaluator import Deck, evaluate_hand
from src.hands import CanonicalHand, get_representative_cards


def equity_vs_calling_range(canonical_hand: CanonicalHand, call_fraction: float) -> float:
    """Equity against an opponent who only calls with their top `call_fraction` of hands."""
    hero_cards = get_representative_cards(canonical_hand.canonical_id)
    hero_score = canonical_hand.score
    remaining = [c for c in Deck.standard_52() if c not in set(hero_cards)]
    opp_scores = sorted((evaluate_hand(o) for o in itertools.combinations(remaining, 3)), reverse=True)
    calling = opp_scores[: max(1, round(len(opp_scores) * call_fraction))]
    wins = sum(hero_score > s for s in calling)
    ties = sum(hero_score == s for s in calling)
    return round((wins + 0.5 * ties) / len(calling), 4)
```

Results (the `1.0` column equals the project's current numbers):

| Hand | vs everything (1.0) | vs top 50% | vs top 30% |
|------|------|------|------|
| `Q-K-A` (best Liêng) | 0.9969 | 0.9939 | 0.9898 |
| `K-K-Q` (Đĩ) | 0.9610 | 0.9220 | 0.8700 |
| `9-8-2` (9 points) | 0.8790 | 0.7581 | 0.5968 |
| `K-6-6` (2 points) | 0.2541 | **0.0000** | **0.0000** |

Monster hands barely change, but medium hands collapse: a 9-point hand drops from 88% to 60%, and the
2-point hand that the current model calls "profitable against a calling station" can never win against
someone who only calls with the top half. A natural link: an opponent with fold equity `f` calls with
roughly the top `1 − f` of hands. **Ideas to implement:**

- Precompute a table `equity[hand][call_fraction]` for, say, 10 fractions (another offline job, still a
  small JSON file).
- Use `call_fraction = 1 − fold_equity` in `RangeFinder`.
- Add a test: "for `call_fraction < 1`, equity never increases" (a property test).

---

## 3. More ideas, from small to ambitious

**Engineering practice**

- Add **type checking** (`pip install mypy` → `mypy --strict src`) and a **linter** (`ruff check .`), and fix
  what they report. `AGENTS.md` already asks for mypy compliance.
- Add **continuous integration**: a GitHub Actions workflow that runs `pytest`, `npm run lint` and
  `npm run build` on every push.
- Measure **test coverage** (`pip install pytest-cov` → `pytest --cov=src`) and test the uncovered branches
  (e.g. malformed JSON in `db.py`).
- Add **frontend tests** with Vitest and React Testing Library (e.g. "clicking a preset updates the input").
- Cache `/api/solve` results with `functools.lru_cache` keyed by `(pot, bet, fold_equity)`.

**Product features**

- A **language switch** (Vietnamese / English) for the UI. Store the strings in a dictionary per language
  and remember the choice in `localStorage`.
- Show the **threshold hands** (weakest profitable hands) instead of always the same top-10 Sáp hands.
- Let the user pick **house rules** (e.g. Đĩ ties are split; Ace-high or not for Điểm tie-breaks). The rule
  lives in one line of `evaluate_hand`, but the data must be regenerated per rule set.
- A **bet-size explorer**: chart EV against bet size for one hand and find the best bet.

**Game theory (ambitious)**

- **Multi-way pots** (3+ players): exact enumeration explodes, so this is where the Monte Carlo code
  path becomes essential.
- **Re-raises and multiple betting rounds**: model the game as a tree and compute a real
  equilibrium strategy with **Counterfactual Regret Minimisation (CFR)**, the algorithm behind modern
  poker AIs. That would make the "GTO" in the UI's subtitle accurate. Today the tool computes
  EV against fixed assumptions, which is useful, but it isn't an equilibrium.

---

## ✅ Checkpoint: what you can now do

- [ ] Explain the rules of Liêng and turn them into a total ordering with tuples.
- [ ] Count combinations, and use isomorphism to shrink a search space (22,100 → 455).
- [ ] Compute probabilities exactly (enumeration) or approximately (Monte Carlo), in parallel.
- [ ] Derive an Expected Value formula and its break-even point from an outcome tree.
- [ ] Structure a Python project into pure domain modules, a data layer, and presentation layers (CLI, API).
- [ ] Build and test a Flask JSON API, including validation, error codes, CORS and an external service call.
- [ ] Build a React dashboard with state, effects and fetch, styled with CSS variables, grid and flexbox.
- [ ] Measure performance against a budget, and deploy backend and frontend separately.
- [ ] Read code critically: spot contract violations, hidden side effects, duplicated facts and model assumptions.

## Recap

- 35 issues found, from crashes (#1, #2) and wrong numbers on screen (#24) to doc drift (#32–35).
- Fix them test-first: failing test → smallest change → full suite → commit.
- The biggest modelling improvement is computing equity against the opponent's **calling range** instead
  of a random hand.
- Plenty of room to grow: type checking, CI, frontend tests, i18n, house rules, multi-way pots, CFR.

**Back to:** [the index](README.md)
