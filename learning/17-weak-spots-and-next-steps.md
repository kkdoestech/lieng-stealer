# Lesson 17 — Weak spots and next steps

> **Goal:** see the health of the whole codebase in one place: how it got to its current shape,
> which weak spots were fixed and how, what is still open, and which improvements are worth doing next.
> **Files:** everything, through the ✅ and ⚠️ items of lessons 00–16.
> **Time:** ~60 min. **Before this:** [16 — Deployment](16-deployment.md).

---

## Where this fits

```
  lessons 00–16: one module each, each with its own ⚠️ Weak spots section
                 (✅ = fixed, with the test that pins the fix; ⚠️ = still open)
                               │
                               ▼
  lesson 17: the fixes in one place, the open items sorted by how much they matter,
             and projects to do next
```

Every earlier lesson ends its walkthrough with the weak spots of the code it just showed you. This
lesson collects them. Most of them were fixed on 2026-10-24, so this is now mostly a record of
*how* code gets better: each fix came with a test that fails without it. The short list of open
items at the end is your backlog.

---

## Reading order

| # | Location | What to look for |
|---|----------|------------------|
| 1 | "How the code got here" below | Two rounds of fixes, each one a pattern you can reuse. |
| 2 | `git log --oneline 661abfc..` | The second round: one commit per phase, a follow-up commit, and the course updates; read their messages. |
| 3 | The ⚠️ table below | What is still open, and why each item was left. |
| 4 | [AGENTS.md](../AGENTS.md#6-performance-budgets--latency-guardrails) | The performance budgets, now with measured numbers. |
| 5 | The exercises below | The capstone projects: pick one and do it test-first. |

---

## Walkthrough

### How the code got here, round 1 (2026-10-23)

The first commit (`4dad10b`, 2026-09-04) already contained the whole stack, so git can't show the
very first steps. The first round of fixes is the one the previous course recorded:

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
| 10 | A test called the real OpenRouter API. | The offline fallback in tests ([15](15-tests-and-performance.md)). | Tests must not depend on the network. |
| 11 | The root endpoint listed 3 of 5 endpoints. | It lists all of them. | Self-description drifts unless something checks it. |
| 12 | The frontend guessed category totals. | The backend sends `category_breakdown`. | Compute numbers where the data is. |
| 13 | Scenario tests covered only the random model. | Scenario 6 runs both models. | Test every mode a user can pick. |
| 14 | Every UI error said "SOLVER DAEMON OFFLINE". | Separate messages for bad input and an unreachable solver ([13](13-frontend-app.md)). | Tell the user what actually happened. |
| 15 | An unused `err` variable caused a lint warning. | `catch {` | Keep the linter quiet so real warnings stand out. |
| 16 | English-only UI. | `i18n.js` with English and Vietnamese. | Keep text out of components. |
| 17 | Vietnamese number format in English mode. | `formatMoney(num, locale)` with tests. | Formatting depends on the locale, not the data. |
| 18 | Nothing checked that both languages had the same keys. | `i18n.test.js` ([13](13-frontend-app.md)). | Turn a convention into a test. |
| 19 | Stale README, no licence. | README rewritten, MIT `LICENSE` added. | Docs are code that nobody runs. |

The same day the UI was restyled from a neon "radar terminal" to a plain dark look on the Ayu Dark
palette ([14](14-styling.md)), and this course was written.

### How the code got here, round 2 (2026-10-24)

The previous version of this lesson listed 44 weak spots. All five High items and nearly all Medium
ones were fixed on the `fix/weak-spots` branch, one commit per phase (tooling, core, API, CLI,
frontend, docs, course). Every row below has a test that fails on the old code:

| Was (old ID) | Now | Pinned by |
|--------------|-----|-----------|
| Two equal `Hand`s had different hashes, so a set kept both (H1). | `Hand.__hash__` and `HandScore.__hash__` hash the score tuple, consistent with `==` ([evaluator.py:477](../backend/src/evaluator.py#L477), [:288](../backend/src/evaluator.py#L288)). | [test_evaluator.py:269](../backend/tests/test_evaluator.py#L269) |
| `"pot": "nan"` was accepted and the API returned invalid JSON (H2); a list body crashed with an HTML 500 (H3). | The body must be a JSON object and every number finite ([app.py:226](../backend/app.py#L226), [:238](../backend/app.py#L238)). | [test_api.py:220](../backend/tests/test_api.py#L220), [:228](../backend/tests/test_api.py#L228) |
| `/api/analyze` trusted client numbers and pasted client text into the LLM prompt; 502s leaked upstream text (H4). | It recomputes everything itself; only validated values reach the prompt; upstream failures return a fixed message ([app.py:473](../backend/app.py#L473)). | [test_api.py:273](../backend/tests/test_api.py#L273) |
| CORS allowed every origin and nothing limited the paid endpoint (H5). | `CORS_ORIGINS` and Flask-Limiter on `/api/analyze` ([app.py:142](../backend/app.py#L142), [:151](../backend/app.py#L151)). | [test_api.py:363](../backend/tests/test_api.py#L363), [:376](../backend/tests/test_api.py#L376) |
| Module-level singletons, untestable with a fake DB (M1); a constructor that loaded the DB behind your back (M2). | `create_app(db=…, calling_model=…, config=…)` ([app.py:103](../backend/app.py#L103)); `RangeFinder` requires a loaded DB ([range_finder.py:47](../backend/src/range_finder.py#L47)). | [test_api.py:383](../backend/tests/test_api.py#L383) |
| Three endpoints, three vocabularies (M3); HTML error pages (M4). | Shared payload builders ([app.py:325](../backend/app.py#L325), [:350](../backend/app.py#L350)); every error is `{"error", "code"}` ([app.py:198](../backend/app.py#L198)). | [test_api.py:185](../backend/tests/test_api.py#L185), [:240](../backend/tests/test_api.py#L240) |
| The ID special case was written twice; duplicate cards got an ID (M5 part, M6). | One `_canonical_ranks` ([hands.py:81](../backend/src/hands.py#L81)); duplicates raise `DuplicateCardError` ([hands.py:116](../backend/src/hands.py#L116)). | `test_hands.py` `TestCanonicalHandSafety` |
| The calling-range maths silently assumed distinct strengths (M7). | The model checks it at start-up ([calling_range.py:67](../backend/src/calling_range.py#L67)); tie-break house rules have tests. | [test_calling_range.py:83](../backend/tests/test_calling_range.py#L83) |
| Plain `KeyError`/`ValueError` escaped `LiengError` (M8); nothing pinned the hierarchy (M17). | `UnknownHandError(LiengError, KeyError)`, `InvalidGameParamsError(LiengError, ValueError)` ([exceptions.py:25](../backend/src/exceptions.py#L25)). | [test_exceptions.py:36](../backend/tests/test_exceptions.py#L36) |
| Generator: no-op `--exact`, global RNG seed, cwd-relative output, non-atomic write (M9); hard-coded 18,424 / 22,100 (M10). | Exclusive flags, a private `random.Random`, an absolute default path, temp file + `os.replace` ([generator.py:55](../backend/src/generator.py#L55), [:175](../backend/src/generator.py#L175)); constants computed once ([hands.py:33](../backend/src/hands.py#L33)). | [test_generator.py:123](../backend/tests/test_generator.py#L123) |
| A 10-hand or nonsense `winrates.json` loaded fine (M11); a test silently skipped a case (M12). | `_validate_records` ([db.py:163](../backend/src/db.py#L163)); the test uses the real ID and fails on unknown keys. | [test_db.py:106](../backend/tests/test_db.py#L106) |
| The CLI printed a whole report before rejecting a bad hand; interactive mode exited 0 after errors (M13). | Validation before any output; exit codes 0/1/2/130 ([cli.py:236](../backend/src/cli.py#L236), [:274](../backend/src/cli.py#L274)). | [test_cli.py:59](../backend/tests/test_cli.py#L59) |
| Hand evaluation missed its 1 µs budget at 2.6–4.7 µs (M14). | A 455-entry score table: about 0.3 µs, identical results on all 132,600 ordered hands ([evaluator.py:398](../backend/src/evaluator.py#L398)). | [test_evaluator.py:302](../backend/tests/test_evaluator.py#L302) |
| Stacked UI error prefixes (M15); lint warnings on the mount effect (M16); a stale verdict after an error (M20). | One message per error `code` ([App.jsx:41](../frontend/src/App.jsx#L41)); a stateless `fetchSolveAndAnalysis` with an AbortController per run ([App.jsx:50](../frontend/src/App.jsx#L50)); a failed solve clears old results ([App.jsx:172](../frontend/src/App.jsx#L172)). | [App.test.jsx:80](../frontend/src/App.test.jsx#L80), [:151](../frontend/src/App.test.jsx#L151) |
| `.env` files weren't git-ignored (M18); slow LLM calls could stall both sync workers (M19). | `.gitignore` covers `.env` ([.gitignore:13](../.gitignore#L13)); the Procfile uses threaded workers with `--preload`. | (configuration) |
| Small things (L1–L8, L10–L12, L15, L16, L18, L19). | Dead guard gone, `final_pot()` helper ([ev.py:34](../backend/src/ev.py#L34)), true test docstring, cached `Hand.score`, `CanonicalHand` ordering, ruff-clean imports, relative `/api` with a used Vite proxy ([App.jsx:8](../frontend/src/App.jsx#L8)), honest labels, runtime vs dev requirements, docs rewritten, whole-card error messages, the dev server on `127.0.0.1` ([app.py:599](../backend/app.py#L599)), CSS on tokens only, lint with `--deny-warnings`, an `engines` field. | ruff, mypy, oxlint, tests |
| Found while re-checking the course (phase 8): a test could reach the real LLM if a key was exported; a non-JSON body silently solved the defaults; 429s had no `Retry-After`; behind a proxy every visitor shared one rate-limit budget; a broken model was reported as "Invalid input"; the atomic write left `winrates.json` readable only by its owner; "GTO" in the notes; a 404 from the wrong server read "Check your inputs". | Test apps ignore an exported key; non-JSON bodies are 400s ([app.py:226](../backend/app.py#L226)); `Retry-After` headers; opt-in `PROXY_FIX_X_FOR` ([app.py:132](../backend/app.py#L132)); `ModelError` with CLI exit 1 ([exceptions.py:37](../backend/src/exceptions.py#L37)); `_file_mode` keeps normal permissions ([generator.py:109](../backend/src/generator.py#L109)); code-less errors read "Can't reach the solver" ([App.jsx:41](../frontend/src/App.jsx#L41)). | [test_api.py:391](../backend/tests/test_api.py#L391), [:411](../backend/tests/test_api.py#L411), [:431](../backend/tests/test_api.py#L431), [test_generator.py:156](../backend/tests/test_generator.py#L156) |

Three habits made this round safe, and they're worth copying:

- **Tooling first.** ruff, strict mypy, Vitest and CI went in before any fix, so every later change
  was checked automatically.
- **Prove the fix with a test that fails without it.** Every new test was also run against the
  old code. For example, 8 of the 12 new `App.test.jsx` tests fail on the previous `App.jsx`.
- **Check that results didn't move.** The data generator's output stayed byte-identical, and the
  default request still gives EV +131,876. A fix that changes numbers is a different change.

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
- **Missing request fields take defaults.** An empty body solves the default spot; only wrong values
  are errors ([10](10-flask-api.md)).
- **The API fails fast without its data.** `create_app()` refuses to start if `winrates.json` is
  missing or invalid, so `/health` always reports `database_loaded: true` once it answers at all.
- **EV, not equilibrium.** Nothing here solves a game; the UI now says "EV solver".

---

## ⚠️ Weak spots

What is still open. Nothing High is left.

| # | Problem | Where | Lesson | Fix idea |
|---|---------|-------|--------|----------|
| M5 | Canonical IDs are written two ways: "Q-K-A" and "A-2-3" ascending, everything else descending ("K-Q-J"). Kept on purpose: the IDs are data in `winrates.json`, the tests, the UI and the docs. | [hands.py:81](../backend/src/hands.py#L81) | [03](03-canonical-hands.md) | A migration: regenerate the data, update every literal, accept old spellings for a while (exercise 3). |
| L9 | CSS class names (`tactical-btn`, `hud-card`, `radar-slider`) describe a design that no longer exists. | [App.css](../frontend/src/App.css) | [14](14-styling.md) | Rename in one commit, together with the lessons that quote them. |
| L13 | Rates are rounded one by one, so 151 of the 455 records have win + tie + loss = 1.0001. The loader tolerates it. | [generator.py](../backend/src/generator.py) | [04](04-generator.md) | Round two rates and derive the third; that changes `winrates.json`. |
| L14 | At `f = 1` the calling-range equity is 0.0 even for A-A-A, although "equity when called" is undefined when nobody calls. | [calling_range.py:157](../backend/src/calling_range.py#L157) | [06](06-calling-range.md) | Return `None`; the zone scan and the API would then need to handle it. |
| L17 | The API sends more than the UI uses: 30 top hands (10 shown) and several unused fields. | [app.py](../backend/app.py) | [11](11-request-trace.md) | Trim the response, or let the client ask for what it needs. |
| L20 | The analysis notes show the LLM's Markdown as raw text (`**bold**`). | [App.jsx:582](../frontend/src/App.jsx#L582) | [13](13-frontend-app.md) | Render a safe Markdown subset; never inject the text as HTML. |
| L21 | In the Vietnamese UI, the detail of an error still comes from the backend in English ("Invalid rank 'X'"). | [App.jsx:41](../frontend/src/App.jsx#L41) | [13](13-frontend-app.md) | Give hand errors finer codes (`invalid_rank`, `duplicate_card`, …) and translate them in `i18n.js`. |
| L22 | With `RATELIMIT_STORAGE_URI=memory://`, each gunicorn worker counts separately, so the real limit is twice the setting. (Counting visitors behind a proxy is fixed: `PROXY_FIX_X_FOR`.) | [app.py:151](../backend/app.py#L151) | [16](16-deployment.md) | Use Redis (`redis://…`) in production. |
| L23 | `WinRateDB.__len__` and `__contains__` answer 0 / False when the database isn't loaded, while `get` raises. | [db.py:156](../backend/src/db.py#L156) | [05](05-win-rate-db.md) | Raise `DatabaseNotLoadedError` consistently (it changes truthiness, so check the callers). |
| L24 | The CLI's time budget (AGENTS.md: under 300 ms cold start, measured 0.13–0.19 s) is not covered by a test. | [AGENTS.md](../AGENTS.md#6-performance-budgets--latency-guardrails) | [15](15-tests-and-performance.md) | A subprocess timing test with `PERF_BUDGET_FACTOR`. |
| L25 | Every solve also requests an analysis, even with the notes closed, so ten quick clicks within a minute reach the `/api/analyze` rate limit (the numbers still show; the notes say to wait). | [App.jsx:180](../frontend/src/App.jsx#L180) | [13](13-frontend-app.md) | Fetch the analysis only when the notes are opened, and reuse it while the inputs don't change. |
| L26 | Unknown or misspelled request fields (`"pots": 5`) are silently ignored and the default is used. | [app.py:226](../backend/app.py#L226) | [10](10-flask-api.md) | Reject keys that aren't in the documented set with `invalid_params`. |

Smaller open items live in their lesson's ⚠️ section, each with an exercise: `Hand` keeps the caller's
list of cards ([02](02-hand-evaluation.md)); the generator's permission helper briefly changes the umask
and cleans up only around `json.dump` ([04](04-generator.md)); two plain `ValueError`s remain for
programming mistakes in `ev.py` and `generator.py` ([01](01-errors-and-cards.md)); no test stops "GTO"
from coming back into the UI text ([00](00-orientation.md)); `PROXY_FIX_X_FOR=-1` is treated as 0
([16](16-deployment.md)); and the offline message's "port 5000" hint doesn't fit a production deployment
([13](13-frontend-app.md)).

---

## 🧪 Try it

Run from `backend/` with the virtual environment active. The first four commands show fixes; the
last two show open items.

**H1 fixed: equal hands hash equally**

```bash
python -c '
from src.evaluator import Hand
a, b = Hand.from_str("As Kh Qd"), Hand.from_str("Ac Kd Qh")
print(a == b, hash(a) == hash(b), len({a, b}))
'
```

```
True True 1
```

**H2 and H3 fixed: bad bodies are 400s with a code**

```bash
python -c '
from app import create_app
c = create_app(config={"TESTING": True}).test_client()
for body in ({"pot": "nan"}, [1, 2]):
    r = c.post("/api/solve", json=body); print(r.status_code, r.get_json())
print(c.get("/api/nope").status_code, c.get("/api/nope").get_json()["code"])
'
```

```
400 {'code': 'invalid_params', 'error': "pot must be a finite number, got 'nan'."}
400 {'code': 'invalid_params', 'error': 'The request body must be a JSON object.'}
404 not_found
```

**M13 fixed: nothing is printed before an invalid hand is rejected**

```bash
python -m src.cli --hand "As Xh Kd" | wc -l; echo "exit=${PIPESTATUS[0]}"
```

```
Invalid input: Invalid card 'Xh': Invalid rank 'X'. Must be 2-10, T, J, Q, K, or A.
0
exit=2
```

**The record of round 2**

```bash
git log --oneline 661abfc..
```

It prints one commit per phase; `git show <sha>` shows the code and the tests of each fix together.

**L14 open: equity at f = 1**

```bash
python -c 'from src.calling_range import CallingRangeModel; print(CallingRangeModel().equity("A-A-A", 1.0))'
```

```
0.0
```

---

## 🏋️ Exercises

The capstone projects. Work test-first: write a test that fails, make the smallest change that passes
it, run everything (`python -m pytest -q`, `ruff check .`, `mypy`, `npm test`, `npm run lint`,
`python3 learning/verify_course.py`), and commit each project separately so you can `git revert` it.

**🟢 1. Read a fix through its test.** Pick one row of the round-2 table, open its test, and predict
what it checks before reading the code. Then break the fix on purpose (for example delete
`Hand.__hash__`) and watch exactly that test fail. Undo with `git checkout -- <file>`.

<details><summary>What to notice</summary>

A good regression test fails for exactly one reason. Deleting `Hand.__hash__` fails
`TestHashing.test_equal_hands_hash_equally_and_collapse_in_a_set` (the set has 2 elements again) and
nothing else, so the test names the bug for you.
</details>

**🟢 2. Triage the open list.** Sort the ⚠️ rows by how much they matter to someone using the web UI.
Which ones would a user ever notice?

<details><summary>Discussion</summary>

A web user sees L20 (raw `**`) every time they open the notes, L21 when they type a bad hand in
Vietnamese mode, and L25 if they click "Run solver" many times in a row. L22 only matters in production, M5 only to API callers, and L9, L13, L14, L23 and L24
are invisible. Severity depends on who you protect.
</details>

**🔴 3. Do the M5 migration.** Make every canonical ID descending ("A-K-Q", "A-3-2"). Decide the rule
first and write it in `hands.py`'s docstring; regenerate `winrates.json` with `--workers 1`; update the
tests, the UI presets and the README; accept the old spellings in the API for one release.

<details><summary>What you'll find</summary>

The IDs are data: they live in `winrates.json`, in test literals ("Q-K-A", "A-2-3"), in the UI's
top-hands table and in the docs. `_canonical_ranks` is now the only place the rule lives, so the code
change is small; the migration (data, literals, compatibility) is the real work.
</details>

**🟡 4. Render the notes safely (L20).** Show `**bold**` as bold in the analysis notes without ever
inserting the server's text as HTML. Add an `App.test.jsx` test that a `<script>` in the advice
appears as text.

<details><summary>Hints</summary>

Split the text on `**` and wrap every second piece in `<strong>`; React escapes text children for
you, so nothing the server sends can become markup. Avoid `dangerouslySetInnerHTML`.
</details>

**🟡 5. Translate hand errors (L21).** Give hand errors finer codes in the backend (`invalid_rank`,
`invalid_suit`, `duplicate_card`, `wrong_card_count`) and translate each one in `i18n.js`.

<details><summary>Hints</summary>

Subclasses of `InvalidCardError` / `InvalidHandSizeError` can carry a `code` attribute that the
`invalid_hand` handler copies into the response. Keep `invalid_hand` as the general code so old clients
still work, and add the specific one as `detail_code`.
</details>

**🔴 6. One rate limit for all workers (L22).** Run Redis locally, set
`RATELIMIT_STORAGE_URI=redis://localhost:6379`, start gunicorn with two workers, and show that the
11th call within a minute is refused no matter which worker answers.

<details><summary>Hints</summary>

`flask-limiter` needs the `redis` extra (`pip install "flask-limiter[redis]"`). Test with a loop of
`curl` calls against the gunicorn port; with `memory://` you'd see up to 20 successes.
</details>

**🟡 7. Test the CLI budget (L24).** Write a test that runs `python -m src.cli --hand "As Kh Qd"` in a
subprocess and checks it finishes in under `budget(0.3)` seconds.

<details><summary>Hints</summary>

`subprocess.run([sys.executable, "-m", "src.cli", ...], capture_output=True, cwd=<backend dir>)`
timed with `time.perf_counter()`. Python start-up is part of it, which is exactly what a user waits
for. Use the `budget()` helper from `tests/perf.py` so CI's slower runners pass.
</details>

**🔴 8. Shrink the CLI's start-up.** Make `rich` load only when a report is actually printed, and
measure the cold start before and after with `/usr/bin/time`.

<details><summary>Hints</summary>

Importing `rich` costs about 60 ms of the 0.13–0.19 s. Move the `from rich… import …` lines into the
functions that print (or into `_console()`), and keep `HAS_RICH` cheap with
`importlib.util.find_spec("rich")`. The range model's table build (~60 ms) is the other big cost.
</details>

---

## ❓ Quiz

1. Why did the fix-up start with tooling (ruff, mypy, Vitest, CI) rather than with the High items?
2. What does "a test that fails on the old code" prove that "a test that passes on the new code" doesn't?
3. M5 looks like a one-line change. Why was it left open?
4. Why is "`/health` always says `database_loaded: true`" listed as a design decision?
5. Two items were proven safe because a number did *not* change. Which numbers, and why does it matter?

<details><summary>Answers</summary>

1. So every later change was checked automatically from the start. A fix that breaks typing or lint
   is caught in the same step, not three phases later.
2. That the test actually detects the bug. A test that would also pass on the broken code proves
   nothing about the fix.
3. The IDs are data: they're baked into `winrates.json`, test literals, the UI and the docs. Changing
   them is a migration with a compatibility period, not a refactor.
4. Because it follows from another choice: `create_app()` refuses to start without valid data, so a
   server that answers at all has its data loaded. The field stays for compatibility.
5. The regenerated `winrates.json` stayed byte-identical (so the faster evaluator changed no result),
   and the default request still gives EV +131,876 (so the API renames moved no numbers). A fix should
   change behaviour only where it says it does.
</details>

---

## Recap

- Round 1 (2026-10-23) gave the project its shape: two opponent models, profit zones, one validator,
  i18n. Round 2 (2026-10-24) fixed all five High and nearly all Medium weak spots, one commit per phase.
- The method is reusable: tooling first, a failing test before every fix, and a check that unrelated
  numbers stay the same.
- What's left is small and documented: the canonical ID format (a data migration), raw Markdown in the
  notes, untranslated error details, per-worker rate counts, and a few cosmetic or untested items.
- Some limits are deliberate (one betting round, the 1% grid, a perfectly sorting opponent, defaults
  for missing fields). Change them as features, with the README's Limitations section updated.
- Keep the course honest: run `python3 learning/verify_course.py` whenever code moves.

**Next:** you've finished the course. Go back to [COURSE.md](COURSE.md), tick the last box, and pick
a capstone.
