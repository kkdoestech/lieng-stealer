# Lesson 11 — Tracing one request end to end

> **Goal:** follow one click on "Run solver" through every layer, from the React state to the
> JSON on the wire, through ten backend modules, and back to the numbers on the screen.
> **Files:** [`frontend/src/App.jsx`](../frontend/src/App.jsx), [`backend/app.py`](../backend/app.py),
> and every module in [`backend/src/`](../backend/src) that the request touches.
> **Time:** ~45 min. **Before this:** [10 — The Flask API](10-flask-api.md).

---

## Where this fits

This lesson adds no new file. It connects lessons 01–10 (and previews 13) along one real request,
with the web UI's default inputs: pot 100,000, bet 50,000, fold rate 0.35, hand `As Kh Qd`, and the
`range` opponent model.

```
 Browser (App.jsx)            Flask (app.py)                   engine (backend/src)
 ─────────────────            ──────────────                   ────────────────────
 click "Run solver"
 handleSolve() ──OPTIONS /api/solve──► flask-cors: 200, Allow-Origin
              ──POST /api/solve ─────► solve_api
                                        _parse_game_params ─────► OpponentModel("range")
                                        Hand.from_str ──────────► evaluator: 3 × Card.from_str
                                        get_by_cards ───────────► hands.get_canonical_id → "Q-K-A"
                                                                  db.get → equity 0.9969
                                        to_canonical ───────────► hands + evaluate_hand
                                        _evaluate_hand ─────────► calling_range.equity → 0.9952
                                                                  ev.evaluate_action → 131,876
                                                                  ev.profitable_fold_zones (101×)
                                        solve_range ────────────► equity_table + 455 × calculate_ev
                                        coverage, top 30, breakdown
              ◄── 200, 4,403 bytes JSON ── jsonify
 setSolveData → re-render: "Raise / all-in", "+131,876 VND", "99.5%" …
              ──POST /api/analyze ───► analyze_api ─► no key → rule-based text
              ◄── 200 {advice, model} ──
 setAiAdvice → notes drawer
```

Every hop below links to the line where it happens. Open them side by side as you read.

---

## Reading order

| # | Location | What happens |
|---|----------|--------------|
| 1 | [App.jsx:372-379](../frontend/src/App.jsx#L372-L379) | The button calls `handleSolve`. |
| 2 | [App.jsx:50-67](../frontend/src/App.jsx#L50-L67) | The request is built and sent with `fetch`. |
| 3 | [app.py:153-165](../backend/app.py#L153-L165) | Flask routes it; the body is parsed and validated. |
| 4 | [app.py:171-177](../backend/app.py#L171-L177) | The hand: parse, look up, canonicalise. |
| 5 | [app.py:179-193](../backend/app.py#L179-L193) | Your hand's EV, zones and the `hand_evaluation` object. |
| 6 | [app.py:195-237](../backend/app.py#L195-L237) | The whole range, the summary, `jsonify`. |
| 7 | [App.jsx:69-80](../frontend/src/App.jsx#L69-L80) | The response becomes React state. |
| 8 | [App.jsx:121-131](../frontend/src/App.jsx#L121-L131) and [:407-472](../frontend/src/App.jsx#L407-L472) | Derived values, then the numbers on screen. |
| 9 | [App.jsx:82-108](../frontend/src/App.jsx#L82-L108) | The follow-up `POST /api/analyze`. |

---

## Walkthrough

### Hop 1. The click

The button at [App.jsx:372-379](../frontend/src/App.jsx#L372-L379) has `onClick={handleSolve}`
and is disabled while `isLoading` is true, so you cannot fire a second solve mid-flight. You do
not even need to click the first time: the effect at
[App.jsx:117-119](../frontend/src/App.jsx#L117-L119) calls `handleSolve()` once when the page
mounts. (In development, React's StrictMode runs mount effects twice, so the dev server sees two
requests on page load; lesson 12.)

### Hop 2. Building the request

📍 [`frontend/src/App.jsx:50-67`](../frontend/src/App.jsx#L50-L67)
```jsx
  const handleSolve = async () => {
    setIsLoading(true);
    setIsAiLoading(true);
    setSolveError(null);

    try {
      // 1. Call solve endpoint
      const solveRes = await fetch(`${API_BASE}/api/solve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          pot: Number(pot),
          bet_size: Number(betSize),
          fold_equity: Number(foldEquity),
          hand: hand.trim(),
          opponent_model: opponentModel,
        }),
      });
```

The five values come from React state, whose defaults are at
[App.jsx:26-30](../frontend/src/App.jsx#L26-L30). The body on the wire is:

```json
{"pot": 100000, "bet_size": 50000, "fold_equity": 0.35, "hand": "As Kh Qd", "opponent_model": "range"}
```

`API_BASE` ([App.jsx:6](../frontend/src/App.jsx#L6)) is `import.meta.env.VITE_API_URL`, or
`http://127.0.0.1:5000` when that is unset. Because it is an absolute URL on another port, the
browser treats this as a **cross-origin** request. A JSON POST is not a "simple" request, so the
browser first sends an `OPTIONS` preflight. flask-cors ([app.py:28](../backend/app.py#L28))
answers it. Against the running dev server:

```
$ curl -s -i -X OPTIONS http://127.0.0.1:5000/api/solve -H "Origin: http://localhost:5173" \
       -H "Access-Control-Request-Method: POST" -H "Access-Control-Request-Headers: content-type"
HTTP/1.1 200 OK
Allow: POST, OPTIONS
Access-Control-Allow-Origin: http://localhost:5173
Access-Control-Allow-Headers: content-type
Access-Control-Allow-Methods: DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT
Vary: Origin
```

Only then does the real POST leave. The `/api` proxy in
[vite.config.js](../frontend/vite.config.js) is never used, because the URL is absolute (lesson 12).

### Hop 3. Into Flask: route, body, validation

Werkzeug matches `POST /api/solve` to `solve_api` ([app.py:153](../backend/app.py#L153)). Then:

- [app.py:164](../backend/app.py#L164) `request.get_json(silent=True) or {}` gives a Python dict.
- [app.py:165](../backend/app.py#L165) `_parse_game_params(data)` ([app.py:48](../backend/app.py#L48))
  converts the three numbers with `float`, checks their ranges, and turns `"range"` into
  `OpponentModel.RANGE` ([calling_range.py:33-36](../backend/src/calling_range.py#L33-L36)).
  The result is `GameParams(pot=100000.0, bet_size=50000.0, fold_equity=0.35,
  opponent_model=OpponentModel.RANGE)`.

A failure here raises `InvalidGameParamsError` ([exceptions.py:19](../backend/src/exceptions.py#L19)),
which the handler at [app.py:75-78](../backend/app.py#L75-L78) turns into a 400.

### Hop 4. The hand: text → cards → canonical class

[app.py:173](../backend/app.py#L173) calls `Hand.from_str("As Kh Qd")`
([evaluator.py:394](../backend/src/evaluator.py#L394)):

1. [evaluator.py:407](../backend/src/evaluator.py#L407) splits on spaces, commas or dashes:
   `["As", "Kh", "Qd"]`.
2. [evaluator.py:412](../backend/src/evaluator.py#L412) calls `Card.from_str` for each
   ([evaluator.py:127](../backend/src/evaluator.py#L127)), which uses `Rank.from_str`
   ([:96](../backend/src/evaluator.py#L96)) and `Suit.from_str` ([:37](../backend/src/evaluator.py#L37)).
3. `Hand.__post_init__` ([evaluator.py:382-386](../backend/src/evaluator.py#L382-L386)) rejects a
   wrong count or duplicates. Result: `Hand('As Kh Qd')`.

[app.py:174](../backend/app.py#L174) calls `win_rate_db.get_by_cards(cards)`
([db.py:123](../backend/src/db.py#L123)):

4. `get_canonical_id` ([hands.py:69](../backend/src/hands.py#L69)) sorts the rank values to
   `(12, 13, 14)` and hits the special case at [hands.py:96-97](../backend/src/hands.py#L96-L97):
   `"Q-K-A"`. Suits are gone from here on (lesson 03).
5. `db.get("Q-K-A")` ([db.py:102](../backend/src/db.py#L102)) is one dictionary lookup:
   `HandStats(equity=0.9969, win_rate=0.9962, tie_rate=0.0015, loss_rate=0.0023,
   category=LIENG, multiplicity=64, samples=18424)`.

[app.py:175](../backend/app.py#L175) calls `to_canonical(cards)` ([hands.py:144](../backend/src/hands.py#L144)),
which computes the same ID a second time, plus `evaluate_hand` (lesson 02), giving a
`CanonicalHand` whose score prints as `Liêng Q-K-A`. Any `LiengError` in these three calls
becomes `400 {"error": "Invalid hand: …"}` ([app.py:176-177](../backend/app.py#L176-L177)).

### Hop 5. Your hand's equity and EV

[app.py:179](../backend/app.py#L179) calls `_evaluate_hand("Q-K-A", 0.9969, params)`
([app.py:88-97](../backend/app.py#L88-L97), explained in
[lesson 07](07-expected-value.md#7-how-the-api-uses-all-of-this)). Under the range model,
`_equity_function` ([app.py:81-85](../backend/app.py#L81-L85)) returns
`lambda f: calling_model.equity("Q-K-A", f)`. Called at f = 0.35:

| Step | Where | Value |
|------|-------|-------|
| combos that call: 0.65 × 22,100 | [calling_range.py:135](../backend/src/calling_range.py#L135) | 14,365 |
| boundary class, by `bisect_right` on cumulative combos | [:136](../backend/src/calling_range.py#L136) | k = 297 (`K-9-4`; 14,308 combos before it) |
| share of the boundary class that calls: 57 / 64 | [:139](../backend/src/calling_range.py#L139) | frac = 0.890625 |
| Q-K-A's strength index | `_index` | 13 (after the 13 Sáp classes) |
| opponent combos that call, after card removal | [:145](../backend/src/calling_range.py#L145) | 11,856.75 |
| … that Q-K-A beats / ties | [:151-152](../backend/src/calling_range.py#L151-L152) | 11,786.75 / 27 |
| equity = (11,786.75 + 0.5 × 27) / 11,856.75 | [:159](../backend/src/calling_range.py#L159) | **0.9952** |

(Lesson 06 explains the tables. The 27 ties are the other Q-K-A hands: 3 queens × 3 kings × 3 aces
left in the deck.)

Then `evaluate_action(100000, 50000, 0.35, 0.9952)` ([ev.py:114](../backend/src/ev.py#L114)):
final pot 200,000, showdown value 0.9952 × 200,000 − 50,000 = 149,040, EV = 0.35 × 100,000 +
0.65 × 149,040 = **131,876.0**. The break-even is 0.0 (the showdown value is already positive),
and `is_profitable` is `True`.

`profitable_fold_zones` ([ev.py:136](../backend/src/ev.py#L136)) then calls the same lambda 101
times and returns `[(0.0, 1.0)]`: raising Q-K-A pays at every fold rate. This scan is the most
expensive part of the hand evaluation, about 0.2 ms of `_evaluate_hand`'s total.

### Hop 6. Packing `hand_evaluation`

📍 [`backend/app.py:179-193`](../backend/app.py#L179-L193)
```python
        ev_res, zones = _evaluate_hand(canonical.canonical_id, stats.equity, params)
        hand_eval_result = {
            "hand": str(player_hand),
            "score_name": str(player_hand.score),
            "category": stats.category.name,
            "category_name": stats.category.display_name,
            "canonical_id": canonical.canonical_id,
            "showdown_equity": ev_res.win_rate_when_called,
            "equity_vs_random": stats.equity,
            "ev": ev_res.ev,
            **_break_even_fields(ev_res, zones, params.opponent_model),
            "profitable_fold_zones": [[start, end] for start, end in zones],
            "is_profitable": ev_res.is_profitable,
            "decision": "RAISE" if ev_res.is_profitable else "CHECK/FOLD",
        }
```

`_break_even_fields` ([app.py:100-115](../backend/app.py#L100-L115)) gives
`break_even_fold_equity: null` (range model) and `profitable_from_fold_equity: 0.0` (the start of
the last zone). Note the two equities side by side: `showdown_equity` 0.9952 is against the
calling range, `equity_vs_random` 0.9969 is from `winrates.json`.

### Hop 7. The whole range

📍 [`backend/app.py:195-199`](../backend/app.py#L195-L199)
```python
    # Solve full range
    records = range_finder.solve_range(pot, bet_size, fold_equity, params.opponent_model)
    profitable_records = [r for r in records if r.is_raise_profitable]
    coverage = range_finder.calculate_range_coverage(profitable_records)
    be_bluff = calculate_break_even_fold_equity(pot, bet_size, win_rate_when_called=0.0)
```

- `solve_range` ([range_finder.py:49](../backend/src/range_finder.py#L49)) copies the 455 records
  (`all_items`, [db.py:139](../backend/src/db.py#L139)), builds **one** equity table for f = 0.35
  (`equity_table`, [calling_range.py:116](../backend/src/calling_range.py#L116)), calls
  `calculate_ev` 455 times and sorts by `(ev, equity, strength)`
  ([range_finder.py:100](../backend/src/range_finder.py#L100)). First: A-A-A, EV 132,500. Last:
  4-3-3, EV 2,500.
- All 455 classes are profitable here, because 35% folds is above the 33.3% a pure bluff needs at
  a half-pot bet. So `calculate_range_coverage` ([range_finder.py:114](../backend/src/range_finder.py#L114))
  returns 22,100 / 22,100 = **100.0**.
- `be_bluff` is `50,000 / 150,000` rounded to **0.3333** (lesson 07).

Then [app.py:202-212](../backend/app.py#L202-L212) keeps the first 30 records as `top_hands`,
[app.py:214](../backend/app.py#L214) sums the profitable combos (22,100), and
`_category_breakdown` ([app.py:118-129](../backend/app.py#L118-L129)) counts per category.
`jsonify` ([app.py:216](../backend/app.py#L216)) serialises it all: status 200, 4,403 bytes. Trimmed:

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
    {"canonical_id": "A-A-A", "category": "SAP", "equity": 1.0, "ev": 132500.0, "is_profitable": true, "multiplicity": 4},
    {"canonical_id": "K-K-K", "category": "SAP", "equity": 0.9997, "ev": 132461.0, "is_profitable": true, "multiplicity": 4},
    "… 28 more, down to Q-Q-J (DI, equity 0.9386, EV 124,518)"
  ]
}
```

Where the time goes, measured per call on the course machine (machine-dependent):

| Hop | Time |
|-----|------|
| `Hand.from_str` | 10 µs |
| `get_by_cards` | 0.9 µs |
| `to_canonical` | 6 µs |
| `_evaluate_hand` (1 EV + 101-point zone scan) | 0.2 ms |
| `solve_range` (equity table + 455 EVs + sort) | 1.4 ms |
| `_category_breakdown` | 0.07 ms |
| **whole request through the test client** | **2.3 ms** |

Over real HTTP to the running dev server, `curl` measured 3–6 ms per request. The 0.07 s
CallingRangeModel build never shows up: it happened once, at import (lesson 10).

### Hop 8. Back in the browser: state

📍 [`frontend/src/App.jsx:69-80`](../frontend/src/App.jsx#L69-L80)
```jsx
      if (!solveRes.ok) {
        // The solver is up but rejected the input (e.g. duplicate cards)
        const errJson = await solveRes.json().catch(() => ({}));
        setSolveError({ key: "invalidInput", detail: errJson.error || `HTTP ${solveRes.status}` });
        setIsLoading(false);
        setIsAiLoading(false);
        return;
      }

      const solveJson = await solveRes.json();
      setSolveData(solveJson);
      setIsLoading(false);
```

Three outcomes are possible here. A 400 shows the server's message, prefixed by the translated
`invalidInput` (for `Xx Kh Qd`: `Invalid input: Invalid hand: Invalid rank 'X'. Must be 2-10, T,
J, Q, K, or A.`). A network failure (server down, CORS refused) throws and lands in the outer
`catch` at [App.jsx:109-113](../frontend/src/App.jsx#L109-L113): `solverOffline`. A 200 stores the
whole JSON in `solveData`, and `setIsLoading(false)` re-enables the button **before** the analysis
starts.

`setSolveData` makes React run `App()` again. On that render the derived values
([App.jsx:121-131](../frontend/src/App.jsx#L121-L131)) pick the response apart:

📍 [`frontend/src/App.jsx:121-131`](../frontend/src/App.jsx#L121-L131)
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
| `profitable_fold_zones` [[0,1]] | [:429](../frontend/src/App.jsx#L429) (via `formatZones`) and the bar at [:304-317](../frontend/src/App.jsx#L304-L317) | "Raising is +EV when the opponent folds 0%–100%" |
| `range_coverage_percent` 100.0 | [:440](../frontend/src/App.jsx#L440) | "100.0%" |
| `profitable_combinations` 22100 | [:443](../frontend/src/App.jsx#L443) | "22,100 of 22,100 combos are +EV" |
| `showdown_equity` 0.9952 | [:450](../frontend/src/App.jsx#L450) | "99.5%" |
| `fold_equity`, `equity_vs_random` | [:453-456](../frontend/src/App.jsx#L453-L456) | "vs. the top 65% that call · 99.7% vs. a random hand" |
| `ev` again | [:464](../frontend/src/App.jsx#L464) | "+131,876" |
| `pure_bluff_break_even_fold_equity` 0.3333 | [:472](../frontend/src/App.jsx#L472) | "33.3%" |
| `category_breakdown` | [:498-507](../frontend/src/App.jsx#L498-L507) | four rows, each "100.0%", "Raise all" |
| `top_hands` (30 sent) | [:552](../frontend/src/App.jsx#L552) | the first 10: A-A-A "100.0%" "+132,500 VND" "4 combos" … 5-5-5 |

`formatMoney` and `formatZones` live in [format.js](../frontend/src/format.js) (lesson 13).
Fifteen of the 29 keys in `summary` and `hand_evaluation` are never read by the page, for example
`break_even_fold_equity`, `profitable_from_fold_equity`, `category_name`, `final_pot`,
`highest_ev_hand` and `threshold_hand`. They exist for other clients (or for nobody).

### Hop 10. The follow-up: `POST /api/analyze`

📍 [`frontend/src/App.jsx:83-96`](../frontend/src/App.jsx#L83-L96)
```jsx
      try {
        const analyzeRes = await fetch(`${API_BASE}/api/analyze`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            pot: Number(pot),
            bet_size: Number(betSize),
            fold_equity: Number(foldEquity),
            hand: hand.trim(),
            opponent_model: opponentModel,
            hand_evaluation: solveJson.hand_evaluation,
            range_coverage_percent: solveJson.summary?.range_coverage_percent,
          }),
        });
```

The page sends the server's own answer back to it. `analyze_api`
([app.py:315](../backend/app.py#L315)) validates the game fields again, checks that `ev` and
`showdown_equity` are numbers, and, with `OPENROUTER_API_KEY` unset, returns the rule-based text
of [lesson 10](10-flask-api.md#6-apianalyze-an-llm-with-a-fallback) with status 200 and
`"model": "rule-based-solver-engine (OPENROUTER_API_KEY not configured)"`. Its second paragraph
for this click is:

```
2. **Hành động Khuyến nghị:** Hero cầm **As Kh Qd** (Liêng Q-K-A) với xác suất thắng đối đầu 99.5%. Kỳ vọng thu nhập (EV) đạt **+131,876 VND**. Khuyến nghị tối ưu: **RAISE**.
```

Back in the browser, [App.jsx:98-103](../frontend/src/App.jsx#L98-L103) stores `{text: advice}`
(or a translated notice if the call failed) and `finally` clears `isAiLoading`. The notes drawer
shows it at [App.jsx:598](../frontend/src/App.jsx#L598), only when you open the drawer. Its
subtitle still says "OpenRouter · Llama 3.1 8B Instruct" ([App.jsx:591](../frontend/src/App.jsx#L591)),
even when the text came from the fallback.

---

## 💡 Concept: `async`, `await` and `fetch`

`fetch(url, options)` starts an HTTP request and immediately returns a *Promise*, a placeholder for
a result that arrives later. Inside an `async` function, `await promise` pauses that function
(not the page) until the result is there. So `handleSolve` reads top to bottom like Python, while
the browser keeps drawing. Two traps: `fetch` only throws for network failures, so a 400 or 500
must be checked with `res.ok`; and `await res.json()` throws if the body is not JSON (an HTML error
page), which is why [App.jsx:71](../frontend/src/App.jsx#L71) adds `.catch(() => ({}))`.

## 💡 Concept: why `setSolveData` changes the screen

A React component is a function from state to markup. Calling a setter such as `setSolveData`
stores the new value and schedules a new call of `App()`. That call reads the new `solveData`,
recomputes `handEval`, `summary` and `zones`, and returns new markup; React then updates only the
parts of the page that changed. Nothing in this file touches the DOM directly.

---

## Design decisions

- **One request for everything the page needs.** `/api/solve` returns the hand and the range
  together, so the page renders consistent numbers from one moment. The cost: changing only the
  hand still re-solves all 455 classes (1.4 ms, cheap enough).
- **Two requests in sequence, not in parallel.** The analysis needs the solve result. The page
  shows the numbers as soon as the first answer arrives (`setIsLoading(false)` before the second
  `fetch`), so a slow LLM never delays them.
- **All state lives in the browser.** The server keeps nothing between requests: each request
  carries all inputs. That is what lets gunicorn run two independent workers (lesson 16).
- **Heavy work happens before the request.** The request itself only looks things up and does
  arithmetic, with tables built at import and win rates computed offline (lesson 04). That is the
  offline/online split from lesson 00, made concrete: 2.3 ms here, against ~30 s to regenerate
  `winrates.json`.

---

## ⚠️ Weak spots

1. **Work done twice.** The canonical ID is computed in `get_by_cards` and again in `to_canonical`
   ([app.py:174-175](../backend/app.py#L174-L175)). Harmless at 7 µs, but a sign that the two
   helpers overlap. *Fix:* compute `to_canonical` once and look up `db.get(canonical.canonical_id)`.
2. **The server's answer makes a round trip through the client.** Hop 10 sends `hand_evaluation`
   back, and the server believes it ([app.py:322-331](../backend/app.py#L322-L331)). *Fix:* let
   `/api/analyze` recompute, or return the analysis from `/api/solve` itself.
3. **Unused payload.** 30 `top_hands` are sent and 10 shown ([App.jsx:552](../frontend/src/App.jsx#L552));
   15 summary and evaluation keys are never read. *Fix:* a `limit` parameter, and drop or document
   the extra keys.
4. **Stacked error prefixes.** A bad hand reads `Invalid input: Invalid hand: Invalid rank 'X'.
   …`: one prefix from `i18n.js`, one from [app.py:177](../backend/app.py#L177), and the message
   from [evaluator.py:107](../backend/src/evaluator.py#L107). Only the first is translated.
5. **Two requests on page load in development.** StrictMode runs the mount effect at
   [App.jsx:117-119](../frontend/src/App.jsx#L117-L119) twice, so two solves and two analyses are
   sent. Production builds run it once. The lint warnings at that line are covered in lesson 13.
6. **A misleading label.** The drawer always says "OpenRouter · Llama 3.1 8B Instruct"
   ([App.jsx:591](../frontend/src/App.jsx#L591)), even though the response carries the real
   `model` string. *Fix:* render `analyzeJson.model`.

---

## 🧪 Try it

Run from `backend/` with the virtual environment active, and `OPENROUTER_API_KEY` unset.

Replay the click without a browser, and print what the page shows:

```bash
python -c '
from app import app
c = app.test_client()
body = {"pot": 100000, "bet_size": 50000, "fold_equity": 0.35, "hand": "As Kh Qd", "opponent_model": "range"}
r = c.post("/api/solve", json=body)
d = r.get_json(); e, s = d["hand_evaluation"], d["summary"]
print(r.status_code, len(r.data), e["decision"], e["ev"], e["showdown_equity"], e["equity_vs_random"])
print(e["profitable_fold_zones"], s["range_coverage_percent"], s["profitable_combinations"], s["pure_bluff_break_even_fold_equity"])
print([h["canonical_id"] for h in d["top_hands"][:3]], len(d["top_hands"]))
a = c.post("/api/analyze", json={**body, "hand_evaluation": e, "range_coverage_percent": s["range_coverage_percent"]})
print(a.status_code, a.get_json()["model"])
'
```

```
200 4403 RAISE 131876.0 0.9952 0.9969
[[0.0, 1.0]] 100.0 22100 0.3333
['A-A-A', 'K-K-K', 'Q-Q-Q'] 30
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

With `python app.py` and `npm run dev` running, open http://localhost:5173, open the browser's
developer tools on the **Network** tab, and reload: you will see the `OPTIONS` and `POST` for
`solve`, then for `analyze` (twice each in development, see weak spot 5).

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

**🟢 2. Predict.** You type `As As Qd` and click. Which hop stops the request, what status comes
back, and what text does the page show?

<details><summary>Solution</summary>

Hop 4: `Hand.__post_init__` raises `InvalidHandSizeError`, caught at
[app.py:176-177](../backend/app.py#L176-L177). Status 400 with `{"error": "Invalid hand: A Liêng
hand cannot have duplicate cards."}`. The page shows `Invalid input: Invalid hand: A Liêng hand
cannot have duplicate cards.` and never calls `/api/analyze`, because of the `return` at
[App.jsx:75](../frontend/src/App.jsx#L75).
</details>

**🟢 3. Predict.** You stop the Flask server and click. Which branch of `handleSolve` runs?

<details><summary>Solution</summary>

`fetch` itself rejects (no connection), so the outer `catch` at
[App.jsx:109-113](../frontend/src/App.jsx#L109-L113) runs: `solverOffline`, "Can't reach the
solver. Start the backend on port 5000 and try again." The old results stay on screen, because
`solveData` is not cleared.
</details>

**🟡 4. Compute the canonical class once.** Change [app.py:173-175](../backend/app.py#L173-L175) so
that `to_canonical` runs first and the stats come from `win_rate_db.get(canonical.canonical_id)`.
Check: `python -m pytest tests/test_api.py tests/test_dynamic_scenarios.py -q` stays green.

<details><summary>Solution</summary>

```python
            player_hand = Hand.from_str(hand_input.strip())
            canonical = to_canonical(player_hand.cards)
            stats = win_rate_db.get(canonical.canonical_id)
```

The response is identical, because both paths use `get_canonical_id`. Do the same in
`/api/evaluate`, or better, extract a helper both routes call.
</details>

**🟡 5. Show the real model name.** Make the drawer subtitle show the `model` string the server
returned. Check: with the key unset, the drawer says
`rule-based-solver-engine (OPENROUTER_API_KEY not configured)`; `npm test` still passes.

<details><summary>Solution</summary>

Store it with the advice at [App.jsx:100](../frontend/src/App.jsx#L100):
`setAiAdvice(analyzeJson.advice ? { text: analyzeJson.advice, model: analyzeJson.model } : { key: "aiNoAdvice" })`,
then render `{aiAdvice?.model ?? ""}` instead of the hard-coded string at line 591.
</details>

**🔴 6. Time every hop yourself.** Write a script that replays the click and prints the time of
each backend hop (parse, hand, `_evaluate_hand`, `solve_range`, `jsonify`), averaged over 200
runs. Which hop dominates, and does the answer change under the random model?

<details><summary>Hints</summary>

Import `app` as a module and call its helpers (`app._parse_game_params`, `app._evaluate_hand`,
`app.range_finder.solve_range`) between `time.perf_counter()` calls; run each once before timing.
On the course machine `solve_range` dominated (1.4 ms of 2.3 ms); under the random model it skips
`equity_table` and the zone scan returns a constant, so both shrink.
</details>

---

## ❓ Quiz

1. Why does the browser send an `OPTIONS` request before the POST, and which line answers it?
2. Where do the suits of `As Kh Qd` stop mattering?
3. `showdown_equity` is 0.9952 and `equity_vs_random` is 0.9969. Where does each come from?
4. Why does the page show results before the analysis text arrives?
5. Name two values in the `/api/analyze` request that the server takes on trust.

<details><summary>Answers</summary>

1. The page (port 5173) calls a different origin (port 5000) with a JSON body, which needs a CORS
   preflight. flask-cors, set up at [app.py:28](../backend/app.py#L28), answers it.
2. In `get_canonical_id`: it keeps only the ranks, so every suit combination of Q-K-A maps to the
   key `"Q-K-A"`.
3. 0.9952 from `CallingRangeModel.equity("Q-K-A", 0.35)` (against the hands that still call);
   0.9969 from `winrates.json` via `db.get` (against a random hand).
4. `setSolveData` and `setIsLoading(false)` run before the second `fetch` is awaited.
5. Any two of: `hand_evaluation.ev`, `hand_evaluation.showdown_equity`, `hand_evaluation.decision`,
   `hand_evaluation.hand`, `hand_evaluation.score_name`, `range_coverage_percent`.
</details>

---

## Recap

- A click runs `handleSolve`: a CORS preflight, then `POST /api/solve` with five fields.
- Flask validates them into `GameParams`, parses the hand, maps it to the canonical key `Q-K-A`,
  and reads its random-hand equity in one dict lookup.
- Under the range model, the calling-range tables give 0.9952; `ev.py` turns that into +131,876
  and the zone `[0, 1]`.
- `solve_range` evaluates all 455 classes with one equity table; the response adds coverage, the
  bluff threshold, the top 30 and a category breakdown: 4,403 bytes in about 2.3 ms.
- React stores the JSON, re-renders, and formats each value; then a second request fetches the
  analysis, which the server builds from numbers the client sent back.

**Next:** [12 — Frontend tooling](12-frontend-tooling.md)
