# Lesson 17 — Weak spots and next steps

> **Goal:** see the health of the whole codebase in one place: how it got to its current shape,
> what is still wrong or fragile, and which improvements are worth doing first.
> **Files:** everything, through the ⚠️ sections of lessons 00–16.
> **Time:** ~60 min. **Before this:** [16 — Deployment](16-deployment.md).

---

## Where this fits

```
  lessons 00–16: one module each, each with its own ⚠️ Weak spots section
                               │
                               ▼
  lesson 17: the same findings in one table, sorted by how much they matter,
             plus the fixes that already happened and projects to do next
```

Every earlier lesson ends its walkthrough with weak spots in the code it just showed you. This
lesson collects them so you can plan work instead of reading about it. Use it as a backlog: each
row has a location, a lesson that explains it, and a fix idea small enough to start today.

---

## Reading order

| # | Location | What to look for |
|---|----------|------------------|
| 1 | "How the code got here" below | The 19 fixes already made: each one is a pattern you can reuse. |
| 2 | The weak-spot table below | Sorted High → Low. Read the High rows closely. Each lesson's own ⚠️ section has smaller items that aren't repeated here. |
| 3 | [AGENTS.md](../AGENTS.md#6-performance-budgets--latency-guardrails) | The performance budgets two rows refer to. |
| 4 | `git show 661abfc:learning/18-pitfalls-and-next-steps.md` | The previous course's pitfall chapter, kept in git, if you want the longer history. |
| 5 | The exercises below | The capstone projects: pick one and do it test-first. |

---

## Walkthrough

### How the code got here

The first commit (`4dad10b`, 2026-09-04) already contained the whole stack, so git can't show the
very first steps. What it does show is a round of fixes on 2026-10-23. Each one is a small lesson in
design:

| # | Before | After | The principle |
|---|--------|-------|---------------|
| 1 | Equity was always measured against a random hand. | `CallingRangeModel` measures it against the hands that actually call, with card removal; `opponent_model` chooses ([06](06-calling-range.md)). | Model the opponent you face, not an average one. |
| 2 | One break-even fold rate per hand. | `profitable_fold_zones` returns every +EV interval ([07](07-expected-value.md)). | When a curve isn't monotonic, a single threshold lies. |
| 3 | `get_profitable_range` ignored the opponent model. | It passes the model through ([08](08-range-finder.md)). | A parameter that isn't forwarded is a silent bug. |
| 4 | Hands with equal EV came out in arbitrary order. | Hand strength is a third sort key. | Make sort order total, or results depend on luck. |
| 5 | A typo in `--hand` printed a traceback; the CLI only knew one model. | `--opponent-model`, "Invalid input" with exit code 2, `test_cli.py` ([09](09-cli.md)). | Errors are part of the interface. |
| 6 | The generator defaulted to Monte Carlo. | Exact enumeration by default, `--monte-carlo` opt-in ([04](04-generator.md)). | Make the correct choice the default. |
| 7 | Validation was copied into three endpoints. | One `GameParams`, one `_parse_game_params`, one error handler ([10](10-flask-api.md)). | One rule, one place. |
| 8 | `/api/analyze` returned 500 on bad input. | It returns 400. | Client mistakes are 4xx, server bugs are 5xx. |
| 9 | `break_even_fold_equity` had two meanings. | Exact value or `null`, plus `profitable_from_fold_equity` ([07](07-expected-value.md)). | One name, one meaning. |
| 10 | A test called the real OpenRouter API. | `monkeypatch.delenv` forces the offline fallback ([15](15-tests-and-performance.md)). | Tests must not depend on the network. |
| 11 | The root endpoint listed 3 of 5 endpoints. | It lists all of them. | Self-description drifts unless something checks it. |
| 12 | The frontend guessed category totals. | The backend sends `category_breakdown`. | Compute numbers where the data is. |
| 13 | Scenario tests covered only the random model. | Scenario 6 runs both models. | Test every mode a user can pick. |
| 14 | Every UI error said "SOLVER DAEMON OFFLINE". | `invalidInput` vs `solverOffline` ([13](13-frontend-app.md)). | Tell the user what actually happened. |
| 15 | An unused `err` variable caused a lint warning. | `catch {` | Keep the linter quiet so real warnings stand out. |
| 16 | English-only UI. | `i18n.js` with English and Vietnamese. | Keep text out of components. |
| 17 | Vietnamese number format in English mode. | `formatMoney(num, locale)` with tests. | Formatting depends on the locale, not the data. |
| 18 | Nothing checked that both languages had the same keys. | `i18n.test.js` ([13](13-frontend-app.md)). | Turn a convention into a test. |
| 19 | Stale README, no licence. | README rewritten, MIT `LICENSE` added. | Docs are code that nobody runs. |

The same day the UI was restyled from a neon "radar terminal" to a plain dark look on the Ayu Dark
palette ([14](14-styling.md)), and `DESIGN.md` was rewritten to match.

### How to read the table

- **High:** it can give a wrong answer, crash a request, or be abused from outside.
- **Medium:** it works today, but it is a trap: the next change nearby is likely to break something.
- **Low:** cleanliness, dead code, docs. Cheap to fix, low risk either way.

Several rows are *deliberate simplifications* rather than mistakes (one betting round, a 1% grid
for profit zones, an opponent who sorts hands perfectly by strength). They are listed under
Design decisions instead.

---

## Design decisions

These limits are chosen on purpose. Changing them is a new feature, not a bug fix:

- **One betting round, and the call always equals the bet.** EV is `f·P + (1 − f)·[w·(P + 2B) − B]`
  ([07](07-expected-value.md)). There are no re-raises and no later streets.
- **Profit zones on a 1% grid.** 101 fold rates are scanned, so a pure bluff that breaks even at
  exactly 50% is reported as profitable from 51% ([07](07-expected-value.md)).
- **The range-model opponent is a perfect sorter.** They fold exactly their weakest `f` share of
  the 22,100 hands, and the boundary ignores your cards. So at `f = 0.35` the share of the hands they
  can actually hold that still calls is 64.04–65.73% rather than exactly 65%, depending on your hand
  ([06](06-calling-range.md)).
- **The UI defaults to `range`, the API to `random`.** The UI shows the more realistic model; the
  API keeps the older default so existing callers don't change ([13](13-frontend-app.md)).
- **EV, not equilibrium.** Despite "GTO" in the subtitle, nothing here solves a game. README's
  Limitations section says so.

---

## ⚠️ Weak spots

### High

| # | Problem | Where | Lesson | Fix idea |
|---|---------|-------|--------|----------|
| H1 | Two equal `Hand`s have different hashes: `Hand("As Kh Qd") == Hand("Ac Kd Qh")` is `True`, yet a set keeps both. Breaks any dict/set keyed by `Hand`, which AGENTS.md promises works. | [evaluator.py:440](../backend/src/evaluator.py#L440) | [02](02-hand-evaluation.md) | Define `__hash__` from `score_tuple`, or compare cards in `__eq__` and add a separate "same strength" method. |
| H2 | `"pot": "nan"` passes validation: the response is 200 with `"pot":NaN`, which is not valid JSON, so strict clients fail to parse it. | [app.py:55](../backend/app.py#L55) | [10](10-flask-api.md) | Reject non-finite numbers with `math.isfinite` in `_parse_game_params`. |
| H3 | A JSON body that isn't an object (e.g. `[1, 2]`) crashes with `AttributeError` and returns an HTML 500. | [app.py:55](../backend/app.py#L55) | [10](10-flask-api.md) | Check `isinstance(data, dict)` and raise `InvalidGameParamsError`. |
| H4 | `/api/analyze` trusts the numbers the client sends and pastes user text into the LLM prompt (prompt injection), and its 502 response passes on the upstream error text. | [app.py:315-440](../backend/app.py#L315-L440) | [10](10-flask-api.md) | Recompute the evaluation on the server; send only validated fields; return a fixed error message. |
| H5 | CORS allows every origin and nothing rate-limits the endpoint that spends LLM credits, so any website can make visitors' browsers spend your OpenRouter key. | [app.py:28](../backend/app.py#L28) | [16](16-deployment.md) | Allow only the deployed frontend's origin; add a rate limit (e.g. Flask-Limiter) to `/api/analyze`. |

### Medium

| # | Problem | Where | Lesson | Fix idea |
|---|---------|-------|--------|----------|
| M1 | The database, calling-range model and range finder are module-level globals built at import time, against AGENTS.md §2.2. Tests can't swap in a fake, and the API tests mutate the one shared app ([test_api.py:9](../backend/tests/test_api.py#L9)). | [app.py:26-36](../backend/app.py#L26-L36) | [10](10-flask-api.md) | An app factory `create_app(db, model)` that stores them on `app.extensions`. |
| M2 | The "load only if the file exists" guard does nothing: `RangeFinder.__init__` loads the DB anyway and fails at import, so `/health` can never report `database_loaded: false`. | [app.py:33](../backend/app.py#L33), [range_finder.py:42-43](../backend/src/range_finder.py#L42-L43) | [08](08-range-finder.md) | Constructors shouldn't do I/O: require a loaded DB, or make `/health` honest. |
| M3 | Endpoints disagree on field names: `decision` vs `recommended_action`, `bet` vs `bet_size`, `equity` vs `showdown_equity`. | [app.py](../backend/app.py#L153-L312) | [10](10-flask-api.md) | One response schema per concept, shared by all endpoints. |
| M4 | 404, 405 and 500 responses are Flask's HTML pages, not JSON. | [app.py:75](../backend/app.py#L75) | [10](10-flask-api.md) | Register JSON handlers for `HTTPException` and `Exception`. |
| M5 | Canonical IDs are written two ways: "Q-K-A" and "A-2-3" ascending, everything else descending ("K-Q-J"). The special case is coded twice. | [hands.py:94](../backend/src/hands.py#L94), [:161](../backend/src/hands.py#L161) | [03](03-canonical-hands.md) | One `canonical_id(ranks)` function used everywhere, and one rule. |
| M6 | `get_canonical_id` doesn't reject duplicate cards: `db.get_by_cards([As, As, Kd])` happily returns A-A-K's equity, 0.2806. | [hands.py:69](../backend/src/hands.py#L69) | [03](03-canonical-hands.md) | Check uniqueness there, not only in `Hand`. |
| M7 | The calling-range maths silently assumes all 455 classes have different strengths. Making Đĩ hands tie (which AGENTS.md allows) would give wrong equities, not an error, and the tie-break house rules themselves are untested: making every Đĩ hand tie fails only one test. | [calling_range.py:8](../backend/src/calling_range.py#L8) | [06](06-calling-range.md) | Assert distinct strengths in `__init__`, or group tied classes. |
| M8 | Plain `KeyError`/`ValueError` escape past `LiengError`, so callers that catch only project errors miss them. | [db.py:119](../backend/src/db.py#L119), [calling_range.py:112](../backend/src/calling_range.py#L112), [:134](../backend/src/calling_range.py#L134) | [01](01-errors-and-cards.md) | Raise project exceptions (e.g. an `UnknownHandError(LiengError, KeyError)`). |
| M9 | The generator: `--exact` does nothing, `random.seed` changes global state, the output path is relative to the current folder, and the write isn't atomic. | [generator.py:46](../backend/src/generator.py#L46), [:163](../backend/src/generator.py#L163) | [04](04-generator.md) | A local `random.Random(seed)`, an absolute default path, write to a temp file then `os.replace`. |
| M10 | Magic numbers 18,424 and 22,100 are hard-coded in several modules. | [generator.py:62](../backend/src/generator.py#L62), [range_finder.py:18](../backend/src/range_finder.py#L18), [calling_range.py:24](../backend/src/calling_range.py#L24) | [04](04-generator.md) | Compute them once (`math.comb(52, 3)`, `math.comb(49, 3)`) in one module. |
| M11 | `WinRateDB.load` checks the JSON shape but not its meaning: a file with 10 hands, or rates above 1, loads fine. A `data/winrates.json` in whatever folder you run from silently wins over `backend/data/`. | [db.py:63](../backend/src/db.py#L63) | [05](05-win-rate-db.md) | Validate 455 keys, the 22,100 multiplicity sum and rates in [0, 1]. |
| M12 | A test silently skips one of its cases: `"10-J-K"` is not a canonical ID, so the loop `continue`s past it. | [test_generator.py:69](../backend/tests/test_generator.py#L69) | [15](15-tests-and-performance.md) | Use the real ID "K-J-10" and fail on unknown keys instead of skipping. |
| M13 | An invalid `--hand` is reported only after the whole 48-line report is printed. Interactive mode exits 0 even after an error, crashes with a traceback on end-of-input (`EOFError`), and silently ignores `--opponent-model`. | [cli.py:242](../backend/src/cli.py#L242), [:268](../backend/src/cli.py#L268) | [09](09-cli.md) | Parse the hand before rendering anything; return a non-zero code from interactive errors. |
| M14 | Two AGENTS.md budgets are missed: one hand evaluation takes ≈2.5–5.3 µs (budget 1 µs) and a CLI run ≈0.1–0.3 s (budget 50 ms), depending on the machine and its load. Only two budgets are tested at all. | [AGENTS.md](../AGENTS.md#6-performance-budgets--latency-guardrails) | [15](15-tests-and-performance.md) | Cache `Hand.score`; build the rank/suit lookup dicts once instead of per call; precompute a 455-entry table; import `rich` lazily. Or update the budgets. |
| M15 | The UI's error messages are assembled in the wrong places: they stack prefixes ("Invalid input: Invalid hand: Invalid rank 'X'…"), a server crash shows as "Invalid input: HTTP 500", and a broken response body shows as "Can't reach the solver". | [app.py:177](../backend/app.py#L177), [i18n.js](../frontend/src/i18n.js) | [13](13-frontend-app.md) | Let the backend send a code (`"error": "invalid_hand"`) and the UI choose the text. |
| M16 | The mount effect that runs the first solve triggers two lint warnings. | [App.jsx:117-119](../frontend/src/App.jsx#L117-L119) | [13](13-frontend-app.md) | Move the first fetch out of the effect body, or memoise `handleSolve` with `useCallback`. |
| M17 | No test pins the exception hierarchy. Change `DatabaseError` to inherit from `Exception` and all 93 tests still pass, yet the CLI then crashes with a traceback instead of "Invalid input". | [exceptions.py:24](../backend/src/exceptions.py#L24) | [01](01-errors-and-cards.md) | One test: `assert issubclass(DatabaseError, LiengError)` for every class. |
| M18 | `.env` files are not git-ignored (only `.env.local` and `.env.*.local` are), so an `OPENROUTER_API_KEY` saved in `backend/.env` would be committed. | [.gitignore:17-18](../.gitignore#L17-L18) | [16](16-deployment.md) | Add `.env` and `*.env` to `.gitignore`. |
| M19 | `/api/analyze` waits up to 20 s for OpenRouter on a synchronous worker, and production runs only 2 workers: two slow analyses stall every other request. | [app.py:422](../backend/app.py#L422), [Procfile](../backend/Procfile) | [16](16-deployment.md) | Use threaded workers (`--worker-class gthread --threads 4`), a shorter timeout, or move the LLM call off the request path. |
| M20 | After a rejected input, the previous verdict, EV and tables stay on screen next to the error, so they look like the answer for the new (invalid) inputs. | [App.jsx:69-76](../frontend/src/App.jsx#L69-L76) | [13](13-frontend-app.md) | Clear `solveData` (or grey out the results) when a solve fails. |

### Low

| # | Problem | Where | Lesson | Fix idea |
|---|---------|-------|--------|----------|
| L1 | A guard that can never be true. | [ev.py:101-103](../backend/src/ev.py#L101-L103) | [07](07-expected-value.md) | Delete it. |
| L2 | `P + 2B` is recomputed in several places. | [ev.py:60](../backend/src/ev.py#L60) | [07](07-expected-value.md) | A `final_pot()` helper. |
| L3 | A test docstring claims more fold equity always raises EV (false for strong hands). | [test_ev.py:9](../backend/tests/test_ev.py#L9) | [07](07-expected-value.md) | Fix the text; add a `w = 1` test. |
| L4 | `Hand.score` re-evaluates the hand on every access: one `a > b` costs about 6.7 µs, against about 0.6 µs with caching (one machine's timing). | [evaluator.py:416](../backend/src/evaluator.py#L416) | [02](02-hand-evaluation.md) | `functools.cached_property` (needs care on a frozen dataclass). |
| L5 | `CanonicalHand` has `<` and `>` but no `<=`/`>=`. | [hands.py:47-57](../backend/src/hands.py#L47-L57) | [03](03-canonical-hands.md) | `functools.total_ordering`, or compare `score_tuple` directly. |
| L6 | Unused code: imports `Final`, `Hand`, `InvalidCardError` in `hands.py`, `Card` in `generator.py`, `InvalidHandSizeError` in `db.py`; `Suit.symbol` and `Rank.is_face_card` are used only by tests or not at all. | [hands.py:16](../backend/src/hands.py#L16), [:20](../backend/src/hands.py#L20), [:27](../backend/src/hands.py#L27), [generator.py:20](../backend/src/generator.py#L20), [db.py:15](../backend/src/db.py#L15) | [03](03-canonical-hands.md) | Add `ruff` and let it remove them. |
| L7 | The Vite `/api` proxy is configured but unused, because the app calls an absolute URL. | [vite.config.js:8](../frontend/vite.config.js#L8) | [12](12-frontend-tooling.md) | Use relative `/api/...` URLs in dev, or delete the proxy. |
| L8 | Unused UI text and labels: four i18n keys are never shown; the notes header always says "OpenRouter · Llama 3.1 8B Instruct", even for the rule-based fallback; the footnote says "Monte Carlo" though the data is exact. | [i18n.js](../frontend/src/i18n.js), [App.jsx](../frontend/src/App.jsx) | [13](13-frontend-app.md) | Delete the keys; show the `model` field the API already returns; fix the footnote. |
| L9 | CSS class names (`tactical-btn`, `hud-card`, `radar-slider`) describe a design that no longer exists. | [App.css](../frontend/src/App.css) | [14](14-styling.md) | Rename them in one commit. |
| L10 | `pytest` and `rich` (used only by the CLI) are installed on the production server. | [requirements.txt](../backend/requirements.txt) | [16](16-deployment.md) | Split into `requirements.txt` and `requirements-dev.txt`. |
| L11 | Docs drift: SKILLS.md lists commands and dependencies that don't exist; AGENTS.md describes a 4-field `HandScore`, strict mypy and no global state; BLOG.md says Liêng hands are 3.26% (it's 768 / 22,100 = 3.48%); BLOG.md and EXPERIMENT.md still describe Monte Carlo data. | [SKILLS.md](../SKILLS.md), [AGENTS.md](../AGENTS.md), [BLOG.md](../BLOG.md) | [00](00-orientation.md) | Delete or rewrite SKILLS.md; correct AGENTS.md to match the code (or the code to match it). |
| L12 | Error messages quote the wrong fragment: the card "11h" is reported as "Invalid rank '1'". | [evaluator.py:150-151](../backend/src/evaluator.py#L150-L151) | [01](01-errors-and-cards.md) | Quote the whole card text in the message. |
| L13 | Rates are rounded one by one, so 151 of the 455 records have win + tie + loss = 1.0001. | [generator.py:89-93](../backend/src/generator.py#L89-L93) | [04](04-generator.md) | Round two rates and derive the third, or store counts instead of rates. |
| L14 | At `f = 1` the calling-range equity is 0.0 even for A-A-A, although "equity when called" is undefined when nobody calls. | [calling_range.py:146-147](../backend/src/calling_range.py#L146-L147) | [06](06-calling-range.md) | Return `None` (or raise) and let callers decide; EV at `f = 1` doesn't need it. |
| L15 | `python app.py` listens on `0.0.0.0`, so the dev server is reachable from your whole network, not just your machine. | [app.py:445](../backend/app.py#L445) | [10](10-flask-api.md) | Bind `127.0.0.1` by default; opt in to `0.0.0.0` with an environment variable. |
| L16 | A production build made without `VITE_API_URL` silently calls `http://127.0.0.1:5000`, which fails on every visitor's machine. | [App.jsx:6](../frontend/src/App.jsx#L6) | [16](16-deployment.md) | Fail the build when the variable is missing, or use relative `/api` URLs. |
| L17 | The API sends more than the UI uses: 30 top hands (10 shown) and 15 of the 29 summary/evaluation fields are never read. | [App.jsx:552](../frontend/src/App.jsx#L552) | [11](11-request-trace.md) | Trim the response or let the client ask for what it needs. |
| L18 | The UI breaks its own DESIGN.md: the title is 1.35rem (maximum 1.25rem), the notes arrow is 0.75rem (minimum 0.87rem), two corners are 2px (rule: 3px), three colours aren't tokens, 18 class names have no CSS rule, and a few strings live outside `i18n.js`. | [App.css:23](../frontend/src/App.css#L23), [:563](../frontend/src/App.css#L563) | [14](14-styling.md) | Fix the CSS to match, or change DESIGN.md on purpose; nothing checks it automatically. |
| L19 | Frontend tooling is loose: `npm run lint` exits 0 even with warnings, `package.json` has no `engines` field although Vite 8 needs Node 20.19+, and `App.jsx` has no tests at all. | [package.json](../frontend/package.json) | [12](12-frontend-tooling.md) | `oxlint --deny-warnings`, an `engines` entry, and component tests (e.g. Vitest + Testing Library). |

---

## 🧪 Try it

Run from `backend/` with the virtual environment active. Each command shows one High or Medium row
for yourself.

**H1, equal hands with different hashes:**

```bash
python -c '
from src.evaluator import Hand
a, b = Hand.from_str("As Kh Qd"), Hand.from_str("Ac Kd Qh")
print(a == b, hash(a) == hash(b), len({a, b}))
'
```

```
True False 2
```

**H2, NaN accepted:**

```bash
python -c '
from app import app
r = app.test_client().post("/api/solve", json={"pot": "nan", "bet_size": 50000})
print(r.status_code, "\"pot\":NaN" in r.get_data(as_text=True))
'
```

```
200 True
```

**H3 and M4, a list body and an unknown URL (both answer with HTML):**

```bash
python -c '
from app import app
c = app.test_client()
print(c.post("/api/solve", json=[1, 2]).status_code, c.post("/api/solve", json=[1, 2]).content_type)
print(c.get("/api/nope").status_code, c.get("/api/nope").content_type)
' 2>/dev/null
```

```
500 text/html; charset=utf-8
404 text/html; charset=utf-8
```

**M13, the late error:**

```bash
python -m src.cli --pot 100000 --bet 50000 --fold-equity 0.35 --hand "As Xh Kd" | wc -l; echo "exit=${PIPESTATUS[0]}"
```

```
Invalid input: Invalid rank 'X'. Must be 2-10, T, J, Q, K, or A.
48
exit=2
```

(The error goes to stderr, so it appears first; the 48 lines of report went to stdout before it.)

---

## 🏋️ Exercises

These are the capstone projects. Each one fixes one or more rows above. Work test-first: write a
test that fails, make the smallest change that passes it, run the whole suite
(`python -m pytest -q`, `npm test`), and only then tidy up. Commit each project separately so you
can undo it with `git revert`.

**🟢 1. Triage.** Without looking at the severity column, sort H1, M5, M13 and L1 by how much they
matter to a user of the web UI. Then compare with the table.

<details><summary>Discussion</summary>

A web user never touches the CLI, so M13 doesn't affect them, and L1 is invisible to everyone. M5
matters only to someone calling the API with hand IDs. H1 matters to anyone who builds on `Hand`,
for example a cache keyed by hands. Severity depends on who you are protecting: the table assumes
the code is a library *and* a service.
</details>

**🟡 2. Fix H1.** Write a test that `len({Hand.from_str("As Kh Qd"), Hand.from_str("Ac Kd Qh")})`
is 1, see it fail, then make it pass.

<details><summary>Solution sketch</summary>

In `Hand`, add `def __hash__(self) -> int: return hash(self.score.score_tuple)`. A frozen dataclass
won't generate a hash if you define one yourself. Equal objects now hash equally. Think about
whether "equal strength" is really the equality you want for `Hand`; the alternative is to compare
cards in `__eq__` and keep strength comparisons in `<`/`>` only.
</details>

**🟡 3. Fix H2 and H3.** Add three tests to `test_api.py`: `"pot": "nan"`, `"pot": "inf"` and a
list body must each return 400 with a JSON `error`.

<details><summary>Solution sketch</summary>

At the top of `_parse_game_params`: `if not isinstance(data, dict): raise InvalidGameParamsError(...)`.
After converting numbers: `if not all(map(math.isfinite, (pot, bet_size, fold_equity))): raise ...`.
The existing error handler turns both into 400 JSON.
</details>

**🟡 4. Fix M4.** Make every error response JSON. Test that `GET /api/nope` returns 404 with
`{"error": ...}` and `content_type == "application/json"`.

<details><summary>Solution sketch</summary>

```python
from werkzeug.exceptions import HTTPException

@app.errorhandler(HTTPException)
def handle_http_error(err):
    return jsonify({"error": err.description}), err.code
```

For unexpected exceptions, register a second handler that logs the traceback and returns a fixed
`{"error": "Internal error"}` with 500. Never put the exception text in the response.
</details>

**🔴 5. Fix M1 (and make M2 disappear).** Introduce `create_app(db=None, calling_model=None)`
that builds everything inside the function, and change `Procfile` to `gunicorn "app:create_app()"`.
Then write a test that passes a tiny fake database.

<details><summary>Hints</summary>

Keep a module-level `app = create_app()` for `python app.py` and the existing tests, then move
tests over one by one. Store the dependencies on `app.extensions["lieng"]` and read them inside
the views via `current_app`. Once the DB is passed in already loaded, `RangeFinder` no longer needs
to load it, and the M2 guard can go.
</details>

**🔴 6. Fix M5.** Make the canonical ID format consistent. Decide the rule first: should the top
straight be "A-K-Q" (descending, like every other ID) or stay "Q-K-A"? Write the rule in `hands.py`'s
module docstring, change the code to follow it, regenerate `winrates.json` into a scratch path
(`python -m src.generator --output /tmp/winrates.json`), and see which tests and which parts of the
UI break.

<details><summary>What you'll find</summary>

The IDs are baked into `winrates.json`, the tests (`"Q-K-A"`, `"A-2-3"`), the UI's top-hands table
and the README. Changing them is a data migration, not a refactor: you have to regenerate the file,
update every literal, and decide whether the API should accept the old spellings for a while. That
cost is why the inconsistency has survived.
</details>

**🔴 7. Close M14.** Get `evaluate_hand` under 1 µs, or prove it can't be done in pure Python and
change the budget in AGENTS.md with a measurement attached.

<details><summary>Hints</summary>

There are only 455 rank multisets. Precompute `{sorted_ranks: HandScore}` once, and evaluation
becomes a sort of three numbers plus a dict lookup. Suits never matter. Measure with `timeit` before
and after, on the same machine. Lesson 15 shows how.
</details>

**🔴 8. Add a linter and CI.** Add `ruff` and `mypy` (AGENTS.md asks for both), fix what they find
(L6 will disappear), and add a GitHub Actions workflow that runs `pytest`, `npm test` and
`python3 learning/verify_course.py` on every push.

<details><summary>Hints</summary>

Start with `ruff check backend` and fix only the errors; turn on more rules later. For mypy, begin
with `--ignore-missing-imports` on `backend/src`. The course checker belongs in CI because the course
quotes line numbers: a refactor that moves code should update the lessons in the same pull request.
</details>

---

## ❓ Quiz

1. Which row would you fix first before putting the app on the public internet, and why?
2. Why is M5 (two ID formats) so expensive to fix, compared with how simple it looks?
3. What do fixes 7 ("one rule, one place") and M3 (different field names) have in common?
4. Why is "the UI defaults to `range`, the API to `random`" listed as a design decision, not a bug?
5. Two budgets in AGENTS.md are missed. Name two honest ways to resolve that.

<details><summary>Answers</summary>

1. H4 or H5: they are the only rows an outsider can exploit, and `/api/analyze` spends real money on
   LLM calls. H2/H3 come next because they break clients.
2. The IDs are data: they live in `winrates.json`, tests, the UI and docs. Changing them needs a
   regeneration and a migration, not just a code edit.
3. Both are about a single source of truth. Fix 7 applied it to validation; M3 is the same problem
   for response shapes, not yet fixed.
4. It's a deliberate trade-off between realism (UI) and backward compatibility (API), and it is
   documented. It becomes a bug only if someone relies on the two being the same without knowing.
5. Make the code meet them (cache scores, precompute a lookup table, import `rich` lazily), or
   change the budgets in AGENTS.md with a measurement and a reason. Ignoring the mismatch is the
   only dishonest option.
</details>

---

## Recap

- The code got here through 19 focused fixes. Each one is a reusable principle: one rule in one
  place, one name with one meaning, the correct choice as the default, tests that don't touch the
  network.
- Five High rows can give wrong answers, crash requests or be abused: the `Hand` hash, NaN input,
  non-object bodies, `/api/analyze` trust, and open CORS on a paid endpoint.
- Most Medium rows are about structure: globals instead of an app factory, constructors that do
  I/O, duplicated rules, and silent assumptions such as distinct hand strengths.
- Some limits are deliberate (one betting round, the 1% grid, a perfectly sorting opponent). Change
  them as features, with the README's Limitations section updated.
- Work test-first, one project per commit, and run `python3 learning/verify_course.py` so the course
  keeps up with the code.

**Next:** you've finished the course. Go back to [COURSE.md](COURSE.md), tick the last box, and pick
a capstone.
