# Lesson 11 — Tracing one request end to end

> **Goal:** follow one click on "Run solver" through every layer, from the React state to the
> JSON on the wire, through the Vite proxy and ten backend modules, and back to the numbers on the
> screen.
> **Files:** [`frontend/src/App.jsx`](../frontend/src/App.jsx), [`frontend/vite.config.js`](../frontend/vite.config.js),
> [`backend/app.py`](../backend/app.py), and every module in [`backend/src/`](../backend/src) that
> the request touches.
> **Time:** ~45 min. **Before this:** [10 — The Flask API](10-flask-api.md).

---

## Where this fits

This lesson adds no new file. It connects lessons 01–10 (and previews 12 and 13) along one real
request, with the web UI's default inputs: pot 100,000, bet 50,000, fold rate 0.35, hand
`As Kh Qd`, and the `range` opponent model.

```
 Browser (App.jsx)               Vite :5173   Flask (app.py)            engine (backend/src)
 ─────────────────               ──────────   ──────────────            ────────────────────
 click "Run solver"
 startSolve(): abort the old run, new AbortController
 runSolve() → fetchSolveAndAnalysis()
   ──POST /api/solve ──────────► proxy ─────► solve_api
     (same origin: no preflight)              _request_body ──────────► a dict
                                              _parse_game_params ─────► OpponentModel("range")
                                              _parse_hand ────────────► evaluator: 3 × Card.from_str
                                              _evaluate_hand ─────────► hands.to_canonical → "Q-K-A"
                                                                        db.get → equity 0.9969
                                                                        calling_range.equity → 0.9952
                                                                        ev.evaluate_action → 131,876
                                                                        ev.profitable_fold_zones (101×)
                                              _hand_payload             13 fields
                                              _solve_range ───────────► equity_table + 455 × calculate_ev
                                              _top_hands_payload        30 rows
   ◄── 200, 5,243 bytes JSON ◄── proxy ◄───── jsonify
 onSolved → setSolveData → re-render: "Raise / all-in", "+131,876 VND", "99.5%" …
   ──POST /api/analyze (same 5 fields)► proxy ► analyze_api: recompute → no key → rule-based text
   ◄── 200 {advice, model} ◄───
 onAnalysis → setAiAdvice → notes drawer
```

Every hop below links to the line where it happens. Open them side by side as you read.

---

## Reading order

| # | Location | What happens |
|---|----------|--------------|
| 1 | [App.jsx:372-379](../frontend/src/App.jsx#L372-L379) | The button calls `startSolve`. |
| 2 | [App.jsx:155-208](../frontend/src/App.jsx#L155-L208) | `startSolve` and the mount effect start a run; `runSolve` builds the body. |
| 3 | [App.jsx:47-90](../frontend/src/App.jsx#L47-L90) | `fetchSolveAndAnalysis`: both requests, outside the component. |
| 4 | [vite.config.js:7-14](../frontend/vite.config.js#L7-L14) | The `/api` proxy that forwards the request to Flask. |
| 5 | [app.py:404-422](../backend/app.py#L404-L422) | `solve_api`: the whole server side in a dozen lines. |
| 6 | [app.py:208-276](../backend/app.py#L208-L276) | The body, the numbers, the model and the hand are parsed. |
| 7 | [app.py:282-327](../backend/app.py#L282-L327) | Your hand: `_evaluate_hand`, then `_hand_payload`. |
| 8 | [app.py:330-376](../backend/app.py#L330-L376) | The whole range: `_solve_range`, then `_top_hands_payload`. |
| 9 | [App.jsx:165-183](../frontend/src/App.jsx#L165-L183), [:210-220](../frontend/src/App.jsx#L210-L220) and [:407-472](../frontend/src/App.jsx#L407-L472) | The response becomes React state, derived values, then numbers on screen. |
| 10 | [App.jsx:75-89](../frontend/src/App.jsx#L75-L89) | The follow-up `POST /api/analyze`. |

---

## Walkthrough

### Hop 1. The click

The button at [App.jsx:372-379](../frontend/src/App.jsx#L372-L379) has `onClick={startSolve}`
and is disabled while `isLoading` is true. `startSolve`
([App.jsx:187-195](../frontend/src/App.jsx#L187-L195)) first aborts the run that may still be in
flight (`currentRun.current?.abort()`), creates a new `AbortController`, remembers it in a ref,
switches on both loading flags, and calls `runSolve`. So at most one run can ever change the
screen: the newest.

You do not even need to click the first time: the mount effect at
[App.jsx:203-208](../frontend/src/App.jsx#L203-L208) starts a run through `startFirstRun`
([App.jsx:198-201](../frontend/src/App.jsx#L198-L201)), a `useEffectEvent` that reads the current
inputs without making them dependencies of the effect. In development, React's StrictMode mounts
the component twice; the effect's cleanup aborts the first run, so only the second one gets to
update the page or send an analysis. `App.test.jsx` pins that ("StrictMode's double mount aborts
the duplicate first request").

### Hop 2. Building the request

📍 [`frontend/src/App.jsx:157-165`](../frontend/src/App.jsx#L157-L165)
```jsx
  const runSolve = (controller) => {
    const body = JSON.stringify({
      pot: Number(pot),
      bet_size: Number(betSize),
      fold_equity: Number(foldEquity),
      hand: hand.trim(),
      opponent_model: opponentModel,
    });
    fetchSolveAndAnalysis(body, controller.signal, {
```

The five values come from React state, whose defaults are at
[App.jsx:128-132](../frontend/src/App.jsx#L128-L132). The body on the wire is:

```json
{"pot": 100000, "bet_size": 50000, "fold_equity": 0.35, "hand": "As Kh Qd", "opponent_model": "range"}
```

`runSolve` passes it, the run's `signal`, and three callbacks (`onSolved`, `onSolveFailed`,
`onAnalysis`) to `fetchSolveAndAnalysis`, a plain function defined *outside* the component. It
holds no state; it only reports what happened:

📍 [`frontend/src/App.jsx:47-51`](../frontend/src/App.jsx#L47-L51)
```jsx
// One solve + analysis round trip. It holds no state: it reports each step through the callbacks
// and stops calling them as soon as `signal` is aborted (a newer run started, or the page unmounted).
async function fetchSolveAndAnalysis(body, signal, { onSolved, onSolveFailed, onAnalysis }) {
  const post = (path) =>
    fetch(`${API_BASE}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body, signal });
```

`API_BASE` ([App.jsx:8](../frontend/src/App.jsx#L8)) is `import.meta.env.VITE_API_URL`, or the
empty string when that is unset. So the URL is the relative `/api/solve`, on the page's own origin
`http://localhost:5173`. A same-origin request needs no CORS preflight: there is no `OPTIONS`
request any more, only the POST.

### Hop 3. Through the Vite proxy, into Flask

The Vite dev server owns port 5173. Its proxy
([vite.config.js:7-14](../frontend/vite.config.js#L7-L14), lesson 12) forwards everything under
`/api` to `http://127.0.0.1:5000`. Against the running dev servers:

```
$ curl -s -i -X POST http://localhost:5173/api/solve -H "Content-Type: application/json" \
       -H "Origin: http://localhost:5173" \
       -d '{"pot": 100000, "bet_size": 50000, "fold_equity": 0.35, "hand": "As Kh Qd", "opponent_model": "range"}'
HTTP/1.1 200 OK
access-control-allow-origin: http://localhost:5173
vary: Origin
server: Werkzeug/3.1.9 Python/3.12.3
content-type: application/json
content-length: 5243
```

The `server` header shows that Flask answered, through the proxy. (The `access-control-allow-origin`
line is there because curl sent an `Origin` that is in `CORS_ORIGINS`; a same-origin page does not
need it.) In production there is no Vite server: the built page is served from the same origin as
the API, or `VITE_API_URL` points at the API and `CORS_ORIGINS` must list the page (lesson 16).

Werkzeug matches `POST /api/solve` to `solve_api` in the `api` blueprint:

📍 [`backend/app.py:404-422`](../backend/app.py#L404-L422)
```python
@api.post("/api/solve")
def solve_api() -> Response:
    """Rank all 455 hands and, if ``hand`` is given, evaluate that hand too.

    JSON body (all optional): pot (> 0), bet_size (> 0), fold_equity in [0, 1],
    opponent_model ('random' default, or 'range'), hand (e.g. 'As Kh Qd').
    """
    services = _services()
    data = _request_body()
    params = _parse_game_params(data)
    hand = _parse_hand(data, required=False)

    hand_evaluation = _hand_payload(_evaluate_hand(services, hand, params), params.opponent_model) if hand else None
    records, summary = _solve_range(services, params)
    return jsonify({
        "summary": summary,
        "hand_evaluation": hand_evaluation,
        "top_hands": _top_hands_payload(records),
    })
```

- `_services()` ([app.py:163-165](../backend/app.py#L163-L165)) fetches the app's database,
  calling-range model and range finder from `app.extensions` (lesson 10).
- `_request_body()` ([app.py:208-215](../backend/app.py#L208-L215)) returns the JSON object as a
  dict.
- `_parse_game_params(data)` ([app.py:236-259](../backend/app.py#L236-L259)) reads the three numbers
  with `_number` ([app.py:218-233](../backend/app.py#L218-L233)): finite, not a bool, in range. It
  turns `"range"` into `OpponentModel.RANGE`
  ([calling_range.py:34-37](../backend/src/calling_range.py#L34-L37)). The result is
  `GameParams(pot=100000.0, bet_size=50000.0, fold_equity=0.35, opponent_model=<OpponentModel.RANGE: 'range'>)`.

A failure here raises `InvalidGameParamsError`
([exceptions.py:25-26](../backend/src/exceptions.py#L25-L26)), which the handler at
[app.py:184-186](../backend/app.py#L184-L186) turns into `400 {"error": …, "code": "invalid_params"}`.

### Hop 4. The hand: text → cards → canonical class

`_parse_hand(data, required=False)` ([app.py:262-276](../backend/app.py#L262-L276)) checks that
`hand` is a non-blank string and calls `Hand.from_str("As Kh Qd")`
([evaluator.py:420-440](../backend/src/evaluator.py#L420-L440)):

1. [evaluator.py:434](../backend/src/evaluator.py#L434) splits on spaces, commas or dashes:
   `["As", "Kh", "Qd"]`.
2. [evaluator.py:439](../backend/src/evaluator.py#L439) calls `Card.from_str` for each
   ([evaluator.py:128](../backend/src/evaluator.py#L128)), which uses `Rank.from_str`
   ([:78](../backend/src/evaluator.py#L78)) and `Suit.from_str` ([:34](../backend/src/evaluator.py#L34)).
3. `Hand.__post_init__` ([evaluator.py:409-413](../backend/src/evaluator.py#L409-L413)) rejects a
   wrong count or duplicates. Result: `Hand('As Kh Qd')`.

Then `_evaluate_hand(services, hand, params)` ([app.py:291-298](../backend/app.py#L291-L298)) starts
with the canonical class:

4. `to_canonical(hand.cards)` ([hands.py:161-184](../backend/src/hands.py#L161-L184)) calls
   `get_canonical_id` ([hands.py:95-118](../backend/src/hands.py#L95-L118)), whose
   `_canonical_ranks` ([hands.py:81-92](../backend/src/hands.py#L81-L92)) sorts the ranks to
   (Q, K, A). This is one of the two straights with an Ace, which the rule at
   [hands.py:90-91](../backend/src/hands.py#L90-L91) writes the way players say it: `"Q-K-A"`. Suits are gone from here on
   (lesson 03). It also calls `evaluate_hand` ([evaluator.py:301](../backend/src/evaluator.py#L301)),
   which is one lookup in a 455-entry table keyed by sorted ranks (lesson 02): `Liêng Q-K-A`.
5. `services.db.get("Q-K-A")` ([db.py:113](../backend/src/db.py#L113)) is one dictionary lookup:
   `HandStats(equity=0.9969, win_rate=0.9962, tie_rate=0.0015, loss_rate=0.0023,
   category=LIENG, multiplicity=64, samples=18424)`.

The canonical ID is computed once per request now; an older version computed it twice (weak spot 1).
An `InvalidCardError` or `InvalidHandSizeError` from steps 1–3 goes to the handler at
[app.py:188-191](../backend/app.py#L188-L191): `400 {"error": "<the evaluator's message>", "code":
"invalid_hand"}`.

### Hop 5. Your hand's equity and EV

Still inside `_evaluate_hand` (explained in
[lesson 07](07-expected-value.md#7-how-the-api-uses-all-of-this)). Under the range model,
`_equity_function` ([app.py:282-288](../backend/app.py#L282-L288)) returns
`lambda f: services.calling_model.equity("Q-K-A", f)`. Called at f = 0.35:

| Step | Where | Value |
|------|-------|-------|
| combos that call: 0.65 × 22,100 | [calling_range.py:146](../backend/src/calling_range.py#L146) | 14,365 |
| boundary class, by `bisect_right` on cumulative combos | [:147](../backend/src/calling_range.py#L147) | k = 297 (`K-9-4`; 14,308 combos before it) |
| share of the boundary class that calls: 57 / 64 | [:150](../backend/src/calling_range.py#L150) | frac = 0.890625 |
| Q-K-A's strength index | `_index` | 13 (after the 13 Sáp classes) |
| opponent combos that call, after card removal | [:156](../backend/src/calling_range.py#L156) | 11,856.75 |
| … that Q-K-A beats / ties | [:160-163](../backend/src/calling_range.py#L160-L163) | 11,786.75 / 27 |
| equity = (11,786.75 + 0.5 × 27) / 11,856.75 | [:170](../backend/src/calling_range.py#L170) | **0.9952** |

(Lesson 06 explains the tables. The 27 ties are the other Q-K-A hands: 3 queens × 3 kings × 3 aces
left in the deck.)

Then `evaluate_action(100000, 50000, 0.35, 0.9952)` ([ev.py:129](../backend/src/ev.py#L129)):
final pot 200,000, showdown value 0.9952 × 200,000 − 50,000 = 149,040, EV = 0.35 × 100,000 +
0.65 × 149,040 = **131,876.0**. The break-even is 0.0 (the showdown value is already positive),
and `is_profitable` is `True`.

`profitable_fold_zones` ([ev.py:150](../backend/src/ev.py#L150)) then calls the same lambda 101
times and returns `[(0.0, 1.0)]`: raising Q-K-A pays at every fold rate. This scan is the most
expensive part of `_evaluate_hand`, which takes about 0.22 ms in total. Everything is returned as
one frozen `HandResult`.

### Hop 6. Packing `hand_evaluation`

📍 [`backend/app.py:313-327`](../backend/app.py#L313-L327)
```python
    return {
        "hand": str(result.hand),
        "score_name": str(result.hand.score),
        "category": result.stats.category.name,
        "category_name": result.stats.category.display_name,
        "canonical_id": result.canonical.canonical_id,
        "showdown_equity": result.ev.win_rate_when_called,
        "equity_vs_random": result.stats.equity,
        "ev": result.ev.ev,
        "break_even_fold_equity": result.ev.break_even_fold_equity if model is OpponentModel.RANDOM else None,
        "profitable_from_fold_equity": result.zones[-1][0],
        "profitable_fold_zones": [[start, end] for start, end in result.zones],
        "is_profitable": result.ev.is_profitable,
        "decision": _decision(result.ev.is_profitable),
    }
```

`_hand_payload` gives `break_even_fold_equity: null` (range model) and
`profitable_from_fold_equity: 0.0` (the start of the last zone), and `decision` comes from
`_decision` ([app.py:301-302](../backend/app.py#L301-L302)). Note the two equities side by side:
`showdown_equity` 0.9952 is against the calling range, `equity_vs_random` 0.9969 is from
`winrates.json`. `/api/evaluate` sends exactly the same 13 fields (lesson 10).

### Hop 7. The whole range

📍 [`backend/app.py:330-333`](../backend/app.py#L330-L333)
```python
def _solve_range(services: Services, params: GameParams) -> tuple[list[HandEVRecord], Json]:
    """Score all 455 classes; return the records (best first) and the summary payload."""
    records = services.range_finder.solve_range(params.pot, params.bet_size, params.fold_equity, params.opponent_model)
    profitable = [r for r in records if r.is_raise_profitable]
```

- `solve_range` ([range_finder.py:53](../backend/src/range_finder.py#L53)) copies the 455 records
  (`all_items`, [db.py:150](../backend/src/db.py#L150)), builds **one** equity table for f = 0.35
  (`equity_table`, [calling_range.py:127](../backend/src/calling_range.py#L127)), calls
  `calculate_ev` 455 times and sorts by `(ev, equity, strength)`
  ([range_finder.py:104](../backend/src/range_finder.py#L104)). First: A-A-A, EV 132,500. Last:
  4-3-3, EV 2,500.
- All 455 classes are profitable here, because 35% folds is above the 33.3% a pure bluff needs at
  a half-pot bet. So `calculate_range_coverage` ([range_finder.py:118](../backend/src/range_finder.py#L118))
  returns 22,100 / 22,100 = **100.0**.
- The summary adds `final_pot()` (200,000) and the pure-bluff break-even, `50,000 / 150,000`
  rounded to **0.3333** ([app.py:339-340](../backend/app.py#L339-L340), lesson 07), the
  highest-EV and threshold hands, and `category_breakdown` from
  [range_finder.py:150-161](../backend/src/range_finder.py#L150-L161) (lesson 08).

Then `_top_hands_payload` ([app.py:363-376](../backend/app.py#L363-L376)) keeps the first 30
records, each with `showdown_equity` and `decision`, and `jsonify`
([app.py:418-422](../backend/app.py#L418-L422)) serialises it all: status 200, 5,243 bytes.
Trimmed:

```json
{
  "hand_evaluation": {
    "break_even_fold_equity": null, "canonical_id": "Q-K-A", "category": "LIENG",
    "category_name": "Liêng", "decision": "RAISE", "equity_vs_random": 0.9969, "ev": 131876.0,
    "hand": "As Kh Qd", "is_profitable": true, "profitable_fold_zones": [[0.0, 1.0]],
    "profitable_from_fold_equity": 0.0, "score_name": "Liêng Q-K-A", "showdown_equity": 0.9952
  },
  "summary": {
    "bet_size": 50000.0, "category_breakdown": [
      {"category": "SAP", "classes": 13, "combos": 52, "profitable_combos": 52},
      {"category": "LIENG", "classes": 12, "combos": 768, "profitable_combos": 768},
      {"category": "DI", "classes": 6, "combos": 144, "profitable_combos": 144},
      {"category": "DIEM", "classes": 424, "combos": 21136, "profitable_combos": 21136}],
    "final_pot": 200000.0, "fold_equity": 0.35, "highest_ev_hand": "A-A-A",
    "highest_ev_value": 132500.0, "opponent_model": "range", "pot": 100000.0,
    "profitable_classes": 455, "profitable_combinations": 22100,
    "pure_bluff_break_even_fold_equity": 0.3333, "range_coverage_percent": 100.0,
    "threshold_ev_value": 2500.0, "threshold_hand": "4-3-3",
    "total_canonical_classes": 455, "total_combinations": 22100
  },
  "top_hands": [
    {"canonical_id": "A-A-A", "category": "SAP", "decision": "RAISE", "ev": 132500.0, "is_profitable": true, "multiplicity": 4, "showdown_equity": 1.0},
    {"canonical_id": "K-K-K", "category": "SAP", "decision": "RAISE", "ev": 132461.0, "is_profitable": true, "multiplicity": 4, "showdown_equity": 0.9997},
    "… 28 more, down to Q-Q-J (DI, showdown_equity 0.9386, EV 124,518)"
  ]
}
```

(The real body has no spaces and escapes "ê" as `\u00ea`; `JSON.parse` turns it back.) The
response grew from 4,403 to 5,243 bytes when every top hand's `equity` became `showdown_equity`
and gained a `decision` next to `is_profitable` (the one-vocabulary change of lesson 10).

Where the time goes, measured per call on the course machine (machine-dependent):

| Hop | Time |
|-----|------|
| `Hand.from_str` | 7 µs |
| `to_canonical` | 5 µs |
| `db.get` | 0.1 µs |
| `_evaluate_hand` (canonical class, 1 EV, 101-point zone scan) | 0.22 ms |
| `_hand_payload` | 2 µs |
| `_solve_range` (equity table, 455 EVs, sort, summary, breakdown) | 1.6 ms |
| `_top_hands_payload` | 0.01 ms |
| **whole request through the test client** | **2.5 ms** |

Over real HTTP, `curl` measured 4–7 ms per request through the Vite proxy and 4–5 ms straight to
Flask. The 54 ms `CallingRangeModel` build never shows up: it happened once, in `create_app()`
(lesson 10).

### Hop 8. Back in the browser: state

📍 [`frontend/src/App.jsx:53-73`](../frontend/src/App.jsx#L53-L73)
```jsx
  let solveJson;
  try {
    const solveRes = await post("/api/solve");
    if (signal.aborted) return;
    if (!solveRes.ok) {
      const errorBody = await solveRes.json().catch(() => ({}));
      if (!signal.aborted) onSolveFailed(solveErrorFor(solveRes.status, errorBody));
      return;
    }
    try {
      solveJson = await solveRes.json();
    } catch {
      if (!signal.aborted) onSolveFailed({ key: "badResponse" });
      return;
    }
  } catch {
    if (!signal.aborted) onSolveFailed({ key: "solverOffline" });
    return;
  }
  if (signal.aborted) return;
  onSolved(solveJson);
```

After every `await` the function checks `signal.aborted`: if a newer run started meanwhile, it
returns without calling anything, so a stale answer can never reach the screen. Otherwise there
are five outcomes:

| What came back | `onSolveFailed` / `onSolved` with | The page shows (English) |
|----------------|-----------------------------------|--------------------------|
| 400 `invalid_hand` | `{key: "invalidHand", detail}` | `Check your hand: Invalid card 'Xh': Invalid rank 'X'. …` |
| 400 any other code | `{key: "invalidParams", detail}` | `Check your inputs: …` |
| 5xx with a `code` (Flask's own 500) | `{key: "serverError"}` | `The solver hit an internal error. …` |
| 5xx without a `code`, or no answer at all | `{key: "solverOffline"}` | `Can't reach the solver. Start the backend on port 5000 and try again.` |
| 200, but not JSON | `{key: "badResponse"}` | `The solver sent a response this page couldn't read. …` |
| 200 | `onSolved(solveJson)` | the results |

`solveErrorFor` ([App.jsx:41-45](../frontend/src/App.jsx#L41-L45)) makes that choice from `status`
and `code` only, never from the message text. The "5xx without a code" row is what you get when
Flask is down in development: the Vite proxy answers `502` with an empty body.

The callbacks live in `runSolve` ([App.jsx:165-183](../frontend/src/App.jsx#L165-L183)).
`onSolveFailed` clears the old verdict, tables and analysis, since they belong to other inputs.
`onSolved` stores the whole JSON in `solveData` and sets `isLoading` to false, which re-enables the
button **before** the analysis starts.

`setSolveData` makes React run `App()` again. On that render the derived values pick the response
apart:

📍 [`frontend/src/App.jsx:210-220`](../frontend/src/App.jsx#L210-L220)
```jsx
  const handEval = solveData?.hand_evaluation;
  const summary = solveData?.summary;
  const isRaise = handEval?.decision === "RAISE";

  const zones = handEval?.profitable_fold_zones;

  // Category Matrix Statistics (computed by the solver per category)
  const categoryMatrix = (summary?.category_breakdown || []).map((row) => ({
    ...row,
    pct: ((row.profitable_combos / row.combos) * 100).toFixed(1),
  }));
```

### Hop 9. Numbers on the screen

Each JSON value and where it lands (English UI; Vietnamese uses `vi-VN` number formatting, so
131,876 becomes 131.876):

| JSON value | Rendered at | You see |
|------------|-------------|---------|
| `decision` "RAISE" | [App.jsx:408-412](../frontend/src/App.jsx#L408-L412) | green banner, "Raise / all-in" |
| `hand`, `canonical_id`, `score_name` | [:415-419](../frontend/src/App.jsx#L415-L419) | "As Kh Qd · Q-K-A · Liêng Q-K-A" |
| `ev` 131876.0 | [:426](../frontend/src/App.jsx#L426) (via `formatMoney`) | "+131,876 VND" |
| `profitable_fold_zones` [[0,1]] | [:429](../frontend/src/App.jsx#L429) (via `formatZones`) and the bar at [:329-342](../frontend/src/App.jsx#L329-L342) | "Raising is +EV when the opponent folds 0%–100%" |
| `range_coverage_percent` 100.0 | [:440](../frontend/src/App.jsx#L440) | "100.0%" |
| `profitable_combinations` 22100 | [:443](../frontend/src/App.jsx#L443) | "22,100 of 22,100 combos are +EV" |
| `showdown_equity` 0.9952 | [:450](../frontend/src/App.jsx#L450) | "99.5%" |
| `fold_equity`, `equity_vs_random` | [:453-456](../frontend/src/App.jsx#L453-L456) | "vs. the top 65% that call · 99.7% vs. a random hand" |
| `ev` again | [:464](../frontend/src/App.jsx#L464) | "+131,876" |
| `pure_bluff_break_even_fold_equity` 0.3333 | [:472](../frontend/src/App.jsx#L472) | "33.3%" |
| `category_breakdown` | [:498-513](../frontend/src/App.jsx#L498-L513) | four rows, each "100.0%", "Raise all" |
| `top_hands` (30 sent) | [:539-551](../frontend/src/App.jsx#L539-L551) | the first 10: A-A-A "100.0%" "+132,500 VND" "4 combos" "Raise" … 5-5-5 |

`formatMoney` and `formatZones` live in [format.js](../frontend/src/format.js) (lesson 13). The
top-hands table reads `showdown_equity` ([:543](../frontend/src/App.jsx#L543)) and
`is_profitable` ([:548](../frontend/src/App.jsx#L548)); its `decision` is not used. Fifteen of the
29 keys in `summary` and `hand_evaluation` are never read by the page either, for example
`break_even_fold_equity`, `profitable_from_fold_equity`, `category_name`, `final_pot`,
`highest_ev_hand` and `threshold_hand`. They exist for other clients, such as scripts that call
`/api/evaluate` or `/api/range`, which share the same fields.

### Hop 10. The follow-up: `POST /api/analyze`

📍 [`frontend/src/App.jsx:75-89`](../frontend/src/App.jsx#L75-L89)
```jsx
  // The server recomputes everything for the analysis from the same inputs.
  let advice;
  try {
    const analyzeRes = await post("/api/analyze");
    if (signal.aborted) return;
    if (analyzeRes.ok) {
      const analyzeJson = await analyzeRes.json();
      advice = analyzeJson.advice ? { text: analyzeJson.advice, model: analyzeJson.model } : { key: "aiNoAdvice" };
    } else {
      advice = { key: analyzeRes.status === 429 ? "aiRateLimited" : "aiUnreachable" };
    }
  } catch (aiErr) {
    advice = { key: "aiTransportFault", detail: aiErr.message };
  }
  if (!signal.aborted) onAnalysis(advice);
```

`post("/api/analyze")` sends the **same body** as the solve: the five inputs, nothing the server
computed. `App.test.jsx` pins that ("analysis requests send only the inputs, never client-side
results"). `analyze_api` ([app.py:452](../backend/app.py#L452)) parses them again, recomputes the
hand and the range itself, and, with `OPENROUTER_API_KEY` unset, returns the rule-based text of
[lesson 10](10-flask-api.md#6-apianalyze-recompute-then-an-llm-or-a-fallback) with status 200 and
`"model": "rule-based-solver-engine (OPENROUTER_API_KEY not configured)"`. Its second paragraph
for this click is:

```
2. **Hành động Khuyến nghị:** Hero cầm **As Kh Qd** (Liêng Q-K-A) với xác suất thắng đối đầu 99.5%. Kỳ vọng thu nhập (EV) đạt **+131,876 VND**. Khuyến nghị tối ưu: **RAISE**.
```

Back in the browser, `advice` becomes `{text, model}`, or a notice key: `aiRateLimited` for a 429,
`aiUnreachable` for any other error status (such as the 502 of a failed OpenRouter call),
`aiTransportFault` if the request itself threw. `onAnalysis`
([App.jsx:179-182](../frontend/src/App.jsx#L179-L182)) stores it and clears `isAiLoading`. The
notes drawer shows the text at [App.jsx:581](../frontend/src/App.jsx#L581) and the model the API
reported at [App.jsx:574](../frontend/src/App.jsx#L574), only when you open the drawer.

---

## 💡 Concept: `async`, `await` and `fetch`

`fetch(url, options)` starts an HTTP request and immediately returns a *Promise*, a placeholder for
a result that arrives later. Inside an `async` function, `await promise` pauses that function
(not the page) until the result is there. So `fetchSolveAndAnalysis` reads top to bottom like
Python, while the browser keeps drawing. Two traps: `fetch` only throws for network failures, so a
400 or 500 must be checked with `res.ok`; and `await res.json()` throws if the body is not JSON
(the proxy's empty 502, for one), which is why [App.jsx:58](../frontend/src/App.jsx#L58) adds
`.catch(() => ({}))`.

## 💡 Concept: `AbortController`, one per run

```js
const controller = new AbortController();
fetch(url, { signal: controller.signal });   // the request listens to this signal
controller.abort();                          // the pending fetch rejects with an AbortError,
                                             // and controller.signal.aborted becomes true
```

`startSolve` aborts the previous run's controller before it starts a new one. That cancels a
request still on the wire, and the `signal.aborted` checks in `fetchSolveAndAnalysis` catch the
case where an answer already arrived: the old run simply stops calling its callbacks. Without it, a
slow analysis from an old click could overwrite the analysis of a newer one, which is exactly what
`App.test.jsx`'s "a click while the analysis is still loading cancels the old run" makes happen on
purpose.

## 💡 Concept: why `setSolveData` changes the screen

A React component is a function from state to markup. Calling a setter such as `setSolveData`
stores the new value and schedules a new call of `App()`. That call reads the new `solveData`,
recomputes `handEval`, `summary` and `zones`, and returns new markup; React then updates only the
parts of the page that changed. Nothing in this file touches the DOM directly.

---

## Design decisions

- **One request for everything the page needs.** `/api/solve` returns the hand and the range
  together, so the page renders consistent numbers from one moment. The cost: changing only the
  hand still re-solves all 455 classes (1.6 ms, cheap enough).
- **Two requests in sequence, not in parallel.** The page shows the numbers as soon as the first
  answer arrives (`onSolved` runs before the second `fetch`), so a slow LLM never delays them. The
  analysis no longer needs the solve's *result*, only its inputs, so the two could now run in
  parallel; keeping them in order means an invalid input fails once, with one message.
- **The network code lives outside the component.** `fetchSolveAndAnalysis` takes a body, a signal
  and callbacks. It has no state, so the tests can drive it through a mocked `fetch`, and the
  component only decides what each callback does to the screen.
- **The newest click wins.** One `AbortController` per run, aborted by the next run or by unmount.
- **Same origin in development.** A relative `/api` and the Vite proxy mean no hard-coded host, no
  CORS preflight, and the same URLs as in a production build served next to the API.
- **All state lives in the browser.** The server keeps nothing between requests (the rate
  limiter's counters aside): each request carries all inputs. That is what lets gunicorn run
  independent workers (lesson 16).
- **Heavy work happens before the request.** The request itself only looks things up and does
  arithmetic, with tables built at start-up and win rates computed offline (lesson 04). That is
  the offline/online split from lesson 00, made concrete: 2.5 ms here, against ~30 s to regenerate
  `winrates.json`.

---

## ⚠️ Weak spots

1. ✅ **Fixed: work done twice.** The canonical ID used to be computed in `get_by_cards` and again
   in `to_canonical`. Now `_evaluate_hand` computes `to_canonical` once and looks the stats up by
   its ID ([app.py:293-294](../backend/app.py#L293-L294)). The output is identical, so no test
   could tell; `test_solve_default_ui_request_numbers`
   ([test_api.py:88-92](../backend/tests/test_api.py#L88-L92)) checks that the numbers of this very
   request did not move.
2. ✅ **Fixed: the server's answer made a round trip through the client.** Hop 10 used to send
   `hand_evaluation` and `range_coverage_percent` back, and the server believed them. Now the page
   sends only the inputs and the server recomputes. Pinned on both sides:
   `test_analyze_recomputes_instead_of_trusting_the_client`
   ([test_api.py:273-283](../backend/tests/test_api.py#L273-L283)) and the "analysis requests send
   only the inputs" test in [App.test.jsx](../frontend/src/App.test.jsx) (exercise 5).
3. **Unused payload.** Still open. 30 `top_hands` are sent and 10 shown
   ([App.jsx:539](../frontend/src/App.jsx#L539)); 15 summary and evaluation keys, and every
   `top_hands[].decision`, are never read by the page. *Fix:* a `limit` parameter, and document
   which keys are for other clients.
4. ✅ **Fixed: stacked error prefixes.** A bad hand used to read `Invalid input: Invalid hand:
   Invalid rank 'X'. …`, with one prefix from `i18n.js` and one from `app.py`. Now the server sends
   the evaluator's message as it is, naming the whole card
   ([evaluator.py:156](../backend/src/evaluator.py#L156)), and the page adds one translated prefix:
   `Check your hand: Invalid card 'Xh': Invalid rank 'X'. …`. Pinned by
   `test_invalid_hand_message_has_no_stacked_prefix` ([test_api.py:108-110](../backend/tests/test_api.py#L108-L110))
   and the "an invalid hand shows its message" test in `App.test.jsx`.
5. ✅ **Fixed: two requests on page load in development.** StrictMode still mounts twice, but the
   cleanup of the effect at [App.jsx:203-208](../frontend/src/App.jsx#L203-L208) aborts the first
   run: its solve is cancelled and it never sends an analysis. Pinned by "StrictMode's double mount
   aborts the duplicate first request" in `App.test.jsx`. Production builds mount once.
6. ✅ **Fixed: a misleading label.** The drawer used to say "OpenRouter · Llama 3.1 8B Instruct"
   even for the offline fallback. Now it shows the `model` string the API reported
   ([App.jsx:574](../frontend/src/App.jsx#L574)). Pinned by "the notes show the model the API
   reports" in `App.test.jsx`.
7. **Every solve also runs an analysis.** New, and open. The analysis request is sent after every
   solve, even when the notes drawer stays closed, and `/api/analyze` is rate-limited to 10 per
   minute per client. The page load and nine quick clicks use up that budget; the next click's
   analysis comes back as `aiRateLimited`, for a drawer you may never open. With a key, each one
   also costs an LLM call.
   *Fix:* fetch the analysis when the drawer is opened, once per run (exercise 7).

---

## 🧪 Try it

Run from `backend/` with the virtual environment active, and `OPENROUTER_API_KEY` unset.

Replay the click without a browser, and print what the page shows:

```bash
python -c '
from app import create_app
c = create_app(config={"TESTING": True}).test_client()
body = {"pot": 100000, "bet_size": 50000, "fold_equity": 0.35, "hand": "As Kh Qd", "opponent_model": "range"}
r = c.post("/api/solve", json=body)
d = r.get_json(); e, s = d["hand_evaluation"], d["summary"]
print(r.status_code, len(r.data), e["decision"], e["ev"], e["showdown_equity"], e["equity_vs_random"])
print(e["profitable_fold_zones"], s["range_coverage_percent"], s["profitable_combinations"], s["pure_bluff_break_even_fold_equity"])
print([h["canonical_id"] for h in d["top_hands"][:3]], len(d["top_hands"]), sorted(d["top_hands"][0]))
a = c.post("/api/analyze", json=body)
print(a.status_code, a.get_json()["model"])
'
```

```
200 5243 RAISE 131876.0 0.9952 0.9969
[[0.0, 1.0]] 100.0 22100 0.3333
['A-A-A', 'K-K-K', 'Q-Q-Q'] 30 ['canonical_id', 'category', 'decision', 'ev', 'is_profitable', 'multiplicity', 'showdown_equity']
200 rule-based-solver-engine (OPENROUTER_API_KEY not configured)
```

Reproduce hop 5's equity step by step:

```bash
python -c '
from src.calling_range import CallingRangeModel
m = CallingRangeModel()
print(m._calling_boundary(0.35), m._index["Q-K-A"], m._ids[297], m.equity("Q-K-A", 0.35))
'
```

```
(297, 0.890625) 13 K-9-4 0.9952
```

With `python app.py` and `npm run dev` running, send the request the way the page does, through
the proxy, and time it:

```bash
curl -s -o /dev/null -w "%{http_code} %{size_download} %{time_total}\n" -X POST http://localhost:5173/api/solve \
     -H "Content-Type: application/json" \
     -d '{"pot": 100000, "bet_size": 50000, "fold_equity": 0.35, "hand": "As Kh Qd", "opponent_model": "range"}'
```

```
200 5243 0.004933
```

Then open http://localhost:5173 with the browser's developer tools on the **Network** tab and
reload: you will see `POST solve` (in development, one more marked as cancelled, see weak spot 5)
and then `POST analyze`, and no `OPTIONS` request at all. From `frontend/`, `npm test` runs the
App tests this lesson quotes: `Tests  18 passed (18)`.

---

## 🏋️ Exercises

Exercises marked 🟡 or 🔴 change code. Undo them afterwards with `git checkout -- <file>`.

**🟢 1. Predict.** Same click, but with the `random` model. Which hops change, and what are
`showdown_equity` and `ev`?

<details><summary>Solution</summary>

Only hop 5 and hop 7. `_equity_function` returns the constant `lambda f: 0.9969`, so no
calling-range lookup happens, and `solve_range` uses the database equities instead of
`equity_table`. `showdown_equity` is 0.9969 and `ev` is 132,097.0 (lesson 07's worked example).
`break_even_fold_equity` becomes 0.0 instead of `null`.
</details>

**🟢 2. Predict.** You type `As As Qd` and click. Which hop stops the request, what comes back,
what does the page show, and what happens to the results that were on screen?

<details><summary>Solution</summary>

Hop 4: `Hand.__post_init__` raises `DuplicateCardError`, a kind of `InvalidHandSizeError`, which the
handler at [app.py:188-191](../backend/app.py#L188-L191) turns into
`400 {"error": "A Liêng hand cannot have duplicate cards.", "code": "invalid_hand"}`. The page shows
`Check your hand: A Liêng hand cannot have duplicate cards.` `onSolveFailed` clears the old verdict,
tables and analysis, and `/api/analyze` is never called, because of the `return` at
[App.jsx:60](../frontend/src/App.jsx#L60).
</details>

**🟢 3. Predict.** You stop the Flask server (keep Vite running) and click. Does `fetch` throw?
Which message appears?

<details><summary>Solution</summary>

`fetch` does not throw: the Vite proxy is still there and answers `502` with an empty body. The
`.json()` fails, so `errorBody` is `{}`, and `solveErrorFor(502, {})` sees a 5xx without a `code`:
`solverOffline`, "Can't reach the solver. Start the backend on port 5000 and try again." Only when
the page talks to Flask directly (`VITE_API_URL` set) would `fetch` itself reject and land in the
`catch` at [App.jsx:68-70](../frontend/src/App.jsx#L68-L70), with the same message. Both cases are
in `App.test.jsx`'s "shows the matching message" table.
</details>

**🟡 4. Remove the abort guards.** In the analysis half of `fetchSolveAndAnalysis`, delete
`if (!signal.aborted)` in front of `onAnalysis(advice)` ([App.jsx:89](../frontend/src/App.jsx#L89))
and run `npm test`. Then also delete `if (signal.aborted) return;` at
[App.jsx:79](../frontend/src/App.jsx#L79) and run it again. Predict both results.

<details><summary>Solution</summary>

With only the first guard gone: `Tests  18 passed (18)`. The late answer of the old run is stopped
one step earlier, at line 79, right after its `await`. With both gone:

```
     × a click while the analysis is still loading cancels the old run 126ms
      Tests  1 failed | 17 passed (18)
```

The old run's "First run" advice now overwrites "Second run". So is the guard at line 89 dead
code? No: an abort can also land while `await analyzeRes.json()` (line 81) is waiting, and only
line 89 catches that. The test happens to exercise the other window. Undo it with
`git checkout -- frontend/src/App.jsx`.
</details>

**🟡 5. Put the round trip back.** Make the analysis request send the old extra field again: replace
`post("/api/analyze")` with a `fetch` whose body is
`JSON.stringify({ ...JSON.parse(body), hand_evaluation: solveJson.hand_evaluation })`. Which
frontend test fails? Does the advice on screen change?

<details><summary>Solution</summary>

```
     × analysis requests send only the inputs, never client-side results 40ms
AssertionError: expected [ 'bet_size', 'fold_equity', …(4) ] to deeply equal [ 'bet_size', 'fold_equity', …(3) ]
      Tests  1 failed | 17 passed (18)
```

The advice does not change: the server ignores `hand_evaluation` and recomputes (a test-client
request with and without the field returns identical JSON). Weak spot 2 is fixed twice, once on
each side, and each side has its own test, so this regression is caught even though the user
would see nothing. Undo it with `git checkout -- frontend/src/App.jsx`.
</details>

**🔴 6. Time every hop yourself.** Write a script that replays the click and prints the time of
each backend hop (parse, hand, `_evaluate_hand`, `_solve_range`, `jsonify`), averaged over 200
runs. Which hop dominates, and does the answer change under the random model?

<details><summary>Hints</summary>

`from app import create_app, _evaluate_hand, _solve_range, GameParams`, then
`app = create_app(config={"TESTING": True})` and `services = app.extensions["lieng"]`. Both helpers
take `services` as their first argument, so they need no request. Time them with
`timeit.repeat(..., number=200)` and take the minimum; call each once before timing. On the course
machine `_solve_range` dominated (1.6 ms of 2.5 ms); under the random model it skips
`equity_table` and the zone scan calls a constant lambda, so both shrink.
</details>

**🔴 7. Analyse only on demand.** Close weak spot 7: send `/api/analyze` only when the notes drawer
is opened, at most once per run, and keep the abort behaviour. Add an App test with the mocked
`fetch`: after the verdict appears there is no analyze call; after a click on "Show analysis
notes" there is exactly one; a second open does not send another.

<details><summary>Hints</summary>

Split `fetchSolveAndAnalysis` in two: the solve half stays in `runSolve`; the analysis half
becomes a function the drawer toggle calls when `aiAdvice` is still `null` for the current run.
Reuse the run's `AbortController` (in `currentRun.current`), so a new solve still cancels a
pending analysis. `isAiLoading` should start `false` and become `true` only when the request
starts. Count calls with `calls.filter((c) => c.path === "/api/analyze")`, as the existing tests
do. Expect to adapt the existing tests that wait for an analyze call without opening the drawer,
such as "analysis requests send only the inputs".
</details>

---

## ❓ Quiz

1. Why does the browser send no `OPTIONS` request in development, and when would it send one?
2. Where do the suits of `As Kh Qd` stop mattering?
3. `showdown_equity` is 0.9952 and `equity_vs_random` is 0.9969. Where does each come from?
4. Why does the page show results before the analysis text arrives?
5. You click "Run solver" twice in quick succession. Why can the first click's analysis never
   replace the second's?

<details><summary>Answers</summary>

1. The page and the API share one origin: the page calls the relative `/api/solve` on
   `localhost:5173`, and the Vite proxy forwards it to Flask. A preflight is only needed for a
   cross-origin JSON POST, for example with `VITE_API_URL` pointing at another host; flask-cors
   ([app.py:130-131](../backend/app.py#L130-L131)) would answer it for the origins in
   `CORS_ORIGINS`.
2. In `get_canonical_id` (and `evaluate_hand`): they keep only the ranks, so every suit combination
   of Q-K-A maps to the key `"Q-K-A"`.
3. 0.9952 from `CallingRangeModel.equity("Q-K-A", 0.35)` (against the hands that still call);
   0.9969 from `winrates.json` via `db.get` (against a random hand).
4. `onSolved` (`setSolveData`, `setIsLoading(false)`) runs before the analysis `fetch` is awaited.
5. The second click's `startSolve` aborts the first run's `AbortController`. The first run's pending
   `fetch` rejects, or its answer is dropped by the `signal.aborted` checks, so it never calls
   `onAnalysis`.
</details>

---

## Recap

- A click runs `startSolve`: abort the old run, then `runSolve` → `fetchSolveAndAnalysis` sends
  `POST /api/solve` with five fields to a relative URL, which the Vite proxy forwards to Flask.
- Flask parses them into `GameParams` and a `Hand`; `_evaluate_hand` maps the hand to the canonical
  key `Q-K-A` once and reads its random-hand equity in one dict lookup.
- Under the range model, the calling-range tables give 0.9952; `ev.py` turns that into +131,876
  and the zone `[0, 1]`; `_hand_payload` packs 13 fields.
- `_solve_range` evaluates all 455 classes with one equity table; the response adds coverage, the
  bluff threshold, the top 30 and a category breakdown: 5,243 bytes in about 2.5 ms.
- React stores the JSON, re-renders, and formats each value; then a second request with the same
  five inputs fetches the analysis, which the server recomputes from scratch.

**Next:** [12 — Frontend tooling](12-frontend-tooling.md)
