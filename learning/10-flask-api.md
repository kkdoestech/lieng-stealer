# Lesson 10 — The Flask API

> **Goal:** know what `app.py` does when it is imported, how one validator and one error handler
> guard every endpoint, what each of the six routes accepts and returns, and how `/api/analyze`
> answers without an API key.
> **Files:** [`backend/app.py`](../backend/app.py), [`backend/tests/test_api.py`](../backend/tests/test_api.py).
> **Time:** ~90 min. **Before this:** [09 — The command-line interface](09-cli.md).

---

## Where this fits

```
  browser (React, lesson 13)      curl / scripts       pytest (test_api.py)
            │ fetch(JSON)               │                   │ app.test_client()
            └───────────────┬───────────┴───────────────────┘
                            ▼  HTTP, CORS "*"
               ┌─────────────────────────────┐
               │  app.py  (this lesson)      │  6 routes, 1 validator, 1 error handler
               │  win_rate_db, calling_model,│  built once, at import
               │  range_finder               │
               └──────────────┬──────────────┘
          ┌───────────────────┼────────────────────┬─────────────────────┐
          ▼                   ▼                    ▼                     ▼
   db.py, hands.py     calling_range.py       ev.py               range_finder.py
   (lessons 03, 05)    (lesson 06)            (lesson 07)         (lesson 08)
                                                                   + OpenRouter (optional)
```

`app.py` is the web front door. It turns JSON into Python values, calls the engine, and turns the
answer back into JSON. Most of its 446 lines are plumbing: validation, shaping the response, and a
prompt for an LLM. The maths it uses was covered in lessons 05–08, and its two EV helpers,
`_evaluate_hand` and `_break_even_fields`, were walked through in
[lesson 07](07-expected-value.md#7-how-the-api-uses-all-of-this). This lesson is about the
plumbing, and about where it leaks.

---

## Reading order

| # | Location | What to look for |
|---|----------|------------------|
| 1 | [app.py:26-36](../backend/app.py#L26-L36) | Everything that runs at import: the app, CORS, the three engine objects. |
| 2 | [app.py:39-72](../backend/app.py#L39-L72) | `GameParams` and `_parse_game_params`: the one validator. |
| 3 | [app.py:75-78](../backend/app.py#L75-L78) | The only error handler. |
| 4 | [app.py:81-129](../backend/app.py#L81-L129) | Helpers shared by the routes (lesson 07 covers the first three). |
| 5 | [app.py:132-150](../backend/app.py#L132-L150) | `GET /` and `GET /health`. |
| 6 | [app.py:153-237](../backend/app.py#L153-L237) | `POST /api/solve`: the endpoint the web UI uses (traced in lesson 11). |
| 7 | [app.py:240-312](../backend/app.py#L240-L312) | `POST /api/evaluate` and `POST /api/range`: smaller, older shapes. |
| 8 | [app.py:315-440](../backend/app.py#L315-L440) | `POST /api/analyze`: prompt, offline fallback, OpenRouter call. |
| 9 | [app.py:443-445](../backend/app.py#L443-L445) | `python app.py` for development. |
| 10 | [test_api.py](../backend/tests/test_api.py) | 17 tests, all through Flask's test client. |

---

## Walkthrough

### 1. What happens when Python imports `app.py`

📍 [`backend/app.py:26-36`](../backend/app.py#L26-L36)
```python
app = Flask(__name__)
# Explicitly enable CORS for all origins on /api/*, /, and /health
CORS(app, resources={r"/api/*": {"origins": "*"}, r"/": {"origins": "*"}, r"/health": {"origins": "*"}})

# Initialize WinRateDB and the calling-range model at startup
DB_PATH = Path(__file__).resolve().parent / "data" / "winrates.json"
win_rate_db = WinRateDB()
if DB_PATH.is_file():
    win_rate_db.load(DB_PATH)
calling_model = CallingRangeModel()
range_finder = RangeFinder(win_rate_db, calling_model)
```

These eleven lines run once per process, the moment anything does `import app` (`python app.py`,
gunicorn, or a test). After that, every request reuses the same three objects:

| Object | Built from | Cost (course machine, varies) |
|--------|-----------|-------------------------------|
| `win_rate_db` | `data/winrates.json`, 455 records (lesson 05) | 2–4 ms |
| `calling_model` | card-removal prefix tables for 455 × 455 classes (lesson 06) | 54–67 ms |
| `range_finder` | the DB, the model, and a strength map (lesson 08) | 5–6 ms |

Importing `app` took 73 ms on top of about 160 ms for Flask, flask-cors and requests. That is
paid once. A request then costs a few milliseconds (lesson 11).

`DB_PATH` is built from `__file__`, not from the current directory, so `app.py` finds its data
from wherever it is started. Note what this is **not**: dependency injection. The routes read
module-level globals (`win_rate_db`, `calling_model`, `range_finder`), and `_equity_function`
reaches for `calling_model` directly ([app.py:84](../backend/app.py#L84)). AGENTS.md §2.2 asks for
the opposite (weak spot 1).

The `if DB_PATH.is_file()` guard looks defensive, but it protects nothing. Delete the data file
in a scratch copy and the import still fails, one line later, inside `RangeFinder.__init__`
([range_finder.py:42-43](../backend/src/range_finder.py#L42-L43)), which calls `db.load()` on an
unloaded database:

```
src.exceptions.DatabaseError: Database file 'data/winrates.json' does not exist.
```

So `/health` can never answer `"database_loaded": false`: without the file there is no server.

### 2. One validator for every endpoint

📍 [`backend/app.py:48-72`](../backend/app.py#L48-L72)
```python
def _parse_game_params(data: dict[str, Any]) -> GameParams:
    """Parse and validate pot, bet size, fold equity, and opponent model from a request body.

    Raises:
        InvalidGameParamsError: If any parameter is missing a valid value or out of bounds.
    """
    try:
        pot = float(data.get("pot", 100000.0))
        bet_size = float(data.get("bet_size", data.get("bet", 50000.0)))
        fold_equity = float(data.get("fold_equity", 0.35))
    except (ValueError, TypeError) as err:
        raise InvalidGameParamsError("Invalid numerical parameters for pot, bet_size, or fold_equity.") from err

    if pot <= 0 or bet_size <= 0:
        raise InvalidGameParamsError("Pot and bet_size must be strictly greater than zero.")
    if not (0.0 <= fold_equity <= 1.0):
        raise InvalidGameParamsError("Fold equity must be between 0.0 and 1.0.")

    try:
        opponent_model = OpponentModel(data.get("opponent_model", OpponentModel.RANDOM.value))
    except ValueError as err:
        choices = ", ".join(m.value for m in OpponentModel)
        raise InvalidGameParamsError(f"opponent_model must be one of: {choices}.") from err

    return GameParams(pot, bet_size, fold_equity, opponent_model)
```

All four POST routes start the same way: `data = request.get_json(silent=True) or {}`, then
`params = _parse_game_params(data)`. The result is a frozen `GameParams`
([app.py:39-45](../backend/app.py#L39-L45)), so after this line every value is a checked number
or enum member and cannot change. Things to notice:

- **Every field has a default.** An empty body `{}` is a valid request: pot 100,000, bet 50,000,
  folds 0.35, model `random`. Note that the API's default model is `random`, while the web UI
  sends `range`.
- **`bet` is an alias of `bet_size`.** `/api/evaluate` and `/api/range` were written with `bet`;
  the lookup accepts both.
- **`float()` does the type check.** That is why the strings `"0.5"` and `"abc"` behave
  differently, and why some surprising values get through.

Here is what it does with real inputs (all verified with the test client):

| Body sent to `/api/solve` | Status | What happens |
|---------------------------|--------|--------------|
| `{}` | 200 | All defaults. |
| `{"pot": -100, "bet_size": 50}` | 400 | `Pot and bet_size must be strictly greater than zero.` |
| `{"pot": "abc"}` | 400 | `Invalid numerical parameters for pot, bet_size, or fold_equity.` |
| `{"fold_equity": 2.5}` | 400 | `Fold equity must be between 0.0 and 1.0.` |
| `{"opponent_model": "psychic"}` | 400 | `opponent_model must be one of: random, range.` |
| `{"fold_equity": "0.5"}` | 200 | The string is converted; `fold_equity` comes back as `0.5`. |
| `{"pot": true, "bet_size": 50000}` | 200 | `float(True)` is `1.0`, so the pot is 1. |
| `{"pot": "nan"}` | **200** | `float("nan")` passes `pot <= 0` (every comparison with NaN is false). The JSON contains `"pot":NaN`, `"final_pot":NaN`, `"highest_ev_value":NaN`, which is not valid JSON. |
| `{"fold_equity": "nan"}` | 400 | Here the check is written as `0.0 <= f <= 1.0`, which NaN fails. |
| `[1, 2, 3]` | **500** | A list has no `.get`: `AttributeError` at line 55, answered with Flask's HTML error page. |
| `not json` (as `application/json`) | 200 | `silent=True` turns a parse error into `None`, then `or {}`: all defaults. |

The NaN row is the interesting one. The two checks look equivalent but are not: `pot <= 0`
rejects bad values, `0.0 <= f <= 1.0` accepts good ones, and NaN is neither bad nor good.
Python's `json` module happily writes `NaN`, but `JSON.parse` in a browser throws on it.

### 3. The only error handler

📍 [`backend/app.py:75-78`](../backend/app.py#L75-L78)
```python
@app.errorhandler(InvalidGameParamsError)
def handle_invalid_params(err: InvalidGameParamsError) -> Any:
    """Render invalid game parameters as a 400 JSON error."""
    return jsonify({"error": str(err)}), 400
```

`@app.errorhandler(SomeException)` tells Flask: if a view raises this exception, call this function
and send its return value instead. That is why `_parse_game_params` can simply `raise`, and why
`/api/analyze` raises the same error for a malformed `hand_evaluation`
([app.py:324-330](../backend/app.py#L324-L330)). One handler gives one error format:
`{"error": "…"}` with status 400.

Bad *hands* are handled differently, inline, in the two routes that parse one:

📍 [`backend/app.py:171-177`](../backend/app.py#L171-L177)
```python
    if hand_input and isinstance(hand_input, str) and hand_input.strip():
        try:
            player_hand = Hand.from_str(hand_input.strip())
            stats = win_rate_db.get_by_cards(player_hand.cards)
            canonical = to_canonical(player_hand.cards)
        except LiengError as err:
            return jsonify({"error": f"Invalid hand: {err}"}), 400
```

`{"hand": "As As Qd"}` gets `{"error": "Invalid hand: A Liêng hand cannot have duplicate cards."}`
and `{"hand": "Xx Kh Qd"}` gets `Invalid hand: Invalid rank 'X'. Must be 2-10, T, J, Q, K, or A.`
The same seven lines are repeated in `/api/evaluate` ([app.py:251-256](../backend/app.py#L251-L256)).

Anything else, such as the list body above, a `KeyError`, or an unknown URL, falls through to
Flask's defaults: an **HTML** page with status 404, 405 or 500 (weak spot 5).

### 4. The six routes

| Method and path | Request fields | Response (status 200) |
|-----------------|----------------|------------------------|
| `GET /` ([:132](../backend/app.py#L132)) | none | `{service, status, endpoints[5]}` |
| `GET /health` ([:142](../backend/app.py#L142)) | none | `{status: "healthy", database_loaded, classes_loaded: 455, version: "1.0.0"}` |
| `POST /api/solve` ([:153](../backend/app.py#L153)) | `pot`, `bet_size` (or `bet`), `fold_equity`, `opponent_model`, optional `hand` | `{summary{16 keys}, hand_evaluation{13 keys} or null, top_hands[30]}` |
| `POST /api/evaluate` ([:240](../backend/app.py#L240)) | the same, `hand` **required** | flat, 14 keys: `hand, canonical_id, category, pot, bet, fold_equity, opponent_model, showdown_equity, equity_vs_random, ev, break_even_fold_equity, profitable_from_fold_equity, recommended_action, is_profitable` |
| `POST /api/range` ([:276](../backend/app.py#L276)) | the same, no hand | flat, 12 keys, with `top_hands[30]` of `{canonical_id, category, showdown_equity, ev, multiplicity, recommended_action}` |
| `POST /api/analyze` ([:315](../backend/app.py#L315)) | the game fields, `hand`, `hand_evaluation`, `range_coverage_percent` | `{advice, model}`; 502 `{error, advice}` if OpenRouter fails |

Errors: 400 `{"error"}` from the validator or a bad hand, and `Field 'hand' is required.` from
`/api/evaluate` without a hand ([app.py:248-249](../backend/app.py#L248-L249)).

Real answers, from the test client:

```
GET /        200 {"endpoints":["/health","/api/solve","/api/evaluate","/api/range","/api/analyze"],"service":"Lieng Stealer API","status":"online"}
GET /health  200 {"classes_loaded":455,"database_loaded":true,"status":"healthy","version":"1.0.0"}
```

`POST /api/evaluate` with the web UI's default inputs (`As Kh Qd`, range model):

```json
{"bet":50000.0,"break_even_fold_equity":null,"canonical_id":"Q-K-A","category":"LIENG",
 "equity_vs_random":0.9969,"ev":131876.0,"fold_equity":0.35,"hand":"As Kh Qd","is_profitable":true,
 "opponent_model":"range","pot":100000.0,"profitable_from_fold_equity":0.0,
 "recommended_action":"RAISE","showdown_equity":0.9952}
```

The keys come back sorted: Flask's `jsonify` sorts dictionary keys by default. `/api/solve`
returns the same numbers nested under `hand_evaluation`, plus the whole-range summary. Lesson 11
follows that request through every module.

### 5. Three endpoints, three shapes

The three solver endpoints were written at different times, and it shows:

| Meaning | `/api/solve` | `/api/evaluate` | `/api/range` |
|---------|--------------|-----------------|--------------|
| bet in the echo | `summary.bet_size` | `bet` | `bet` |
| the verdict | `decision` | `recommended_action` | `top_hands[].recommended_action` |
| a top hand's equity | `top_hands[].equity` | — | `top_hands[].showdown_equity` |
| a top hand's verdict | `is_profitable` (bool) | — | `recommended_action` (text) |
| profit zones | `profitable_fold_zones` | computed, not returned | — |
| `score_name`, `category_name` | yes | no | — |
| `category_breakdown` | yes | — | no |

`/api/evaluate` even computes the zones ([app.py:258](../backend/app.py#L258)) and then throws
them away. A client written against one endpoint cannot reuse its parser for another.

### 6. `/api/analyze`: an LLM with a fallback

The web UI calls this endpoint right after `/api/solve` and shows the answer in the notes drawer.
It first validates exactly like the others, then reads three things **the client sends back**:

📍 [`backend/app.py:322-334`](../backend/app.py#L322-L334)
```python
    hand = data.get("hand", "None")
    hand_eval = data.get("hand_evaluation") or {}
    if not isinstance(hand_eval, dict):
        raise InvalidGameParamsError("hand_evaluation must be a JSON object.")
    try:
        hand_ev = float(hand_eval.get("ev", 0))
        hand_equity = float(hand_eval.get("showdown_equity", 0))
    except (ValueError, TypeError) as err:
        raise InvalidGameParamsError("hand_evaluation.ev and showdown_equity must be numbers.") from err
    coverage = data.get("range_coverage_percent", 0.0)
    folds_weakest = params.opponent_model is OpponentModel.RANGE

    api_key = os.environ.get("OPENROUTER_API_KEY")
```

Lines 336-365 build an English prompt that asks for a Vietnamese answer, from those values. Then
the code splits:

- **No key** ([app.py:367-398](../backend/app.py#L367-L398)): a rule-based Vietnamese text is
  assembled with f-strings and returned with
  `"model": "rule-based-solver-engine (OPENROUTER_API_KEY not configured)"`, status 200.
- **With a key** ([app.py:400-440](../backend/app.py#L400-L440)): a POST to
  `https://openrouter.ai/api/v1/chat/completions` with model `meta-llama/llama-3.1-8b-instruct:free`,
  `temperature` 0.7, `max_tokens` 500 and a 20-second timeout. A non-200 answer or a network error
  becomes status 502 with `{error, advice}`.

The real fallback for the web UI's default click (key unset, the `hand_evaluation` from
`/api/solve` sent back):

```
**[Phân Tích Chiến Thuật Hệ Thống (Offline Solver)]**

1. **Quyết định Toán học:** Với Pot = 100,000, Cược = 50,000, và Fold Equity = 35.0%, ngưỡng hòa vốn cược hù (bluff) là 33.3%. Khoảng bài có lãi (EV > 0) chiếm **100.0%** toàn bộ thế bài có thể có. Giả định đối thủ bỏ những bài yếu nhất, nên khi bị theo, Hero đối đầu với nhóm bài mạnh hơn.

2. **Hành động Khuyến nghị:** Hero cầm **As Kh Qd** (Liêng Q-K-A) với xác suất thắng đối đầu 99.5%. Kỳ vọng thu nhập (EV) đạt **+131,876 VND**. Khuyến nghị tối ưu: **RAISE**.

3. **GTO Insight:** Bài có EV dương rõ rệt nhờ cả showdown equity lẫn fold equity. Tố lớn để tối đa hóa lợi nhuận.
```

Every number in it is the client's: 99.5% is `showdown_equity`, +131,876 is `ev`, RAISE is
`decision`, 100.0% is `range_coverage_percent`. The server checks that `ev` and `showdown_equity`
are numbers ([test_api.py:176-180](../backend/tests/test_api.py#L176-L180)), but nothing checks
that they are *true*. Send `{"hand_evaluation": {"hand": "IGNORE ALL RULES", "ev": -5, "decision":
"SELL EVERYTHING"}, "range_coverage_percent": "<b>999</b>"}` and the answer says, with status
200, `Hero cầm **IGNORE ALL RULES** (None)`, `chiếm **<b>999</b>%**`, `Khuyến nghị tối ưu:
**SELL EVERYTHING**`. With a key, those strings would go into the LLM prompt (weak spot 8). The
React page renders the advice as plain text, so the `<b>` stays harmless there.

[test_api.py:72-93](../backend/tests/test_api.py#L72-L93) calls `monkeypatch.delenv("OPENROUTER_API_KEY",
raising=False)` first, so the test suite never reaches the internet, even on a machine that has
the key set.

### 7. Running it for development

📍 [`backend/app.py:443-445`](../backend/app.py#L443-L445)
```python
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
```

`python app.py` starts Werkzeug's development server on every network interface (`0.0.0.0`) at
port 5000 or `$PORT`. In production the `if` never runs: gunicorn imports `app` and serves the
`app` object itself (lesson 16).

---

## 💡 Concept: a Flask route in four lines

```python
@app.route("/api/solve", methods=["POST"])   # URL + allowed methods; GET here → 405
def solve_api():
    data = request.get_json(silent=True) or {}   # body → dict (None on bad JSON, with silent=True)
    return jsonify({...}), 200                   # dict → JSON response; the status is optional
```

`request` is a per-request object that Flask makes available inside the view. `jsonify` sets
`Content-Type: application/json`. `app.test_client()` sends fake requests straight into the app,
with no server and no port, which is how every API test and probe in this course runs.

## 💡 Concept: CORS, and why `"*"`

A page loaded from `http://localhost:5173` may only read a response from `http://127.0.0.1:5000`
(a different *origin*: scheme, host and port) if that response says it may, with an
`Access-Control-Allow-Origin` header. For a JSON POST, the browser first sends an `OPTIONS`
*preflight* to ask. `flask-cors` answers both. Verified with the test client:

```
OPTIONS /api/solve, Origin http://localhost:5173 → 200, Access-Control-Allow-Origin: http://localhost:5173,
        Access-Control-Allow-Methods: DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT
POST    /api/solve, Origin https://evil.example  → 200, Access-Control-Allow-Origin: https://evil.example
```

With `"*"`, flask-cors echoes back whatever origin asks. That is fine for a public, read-only
calculator with no cookies or secrets. CORS only limits *browsers*; curl ignores it.

---

## Design decisions

- **Build the engine once, at import.** The tables cost tens of milliseconds, so building them per
  request would multiply the latency. Module-level globals are the shortest way to share them. An
  app factory (`create_app(db, model)`) would do the same and allow injection.
- **One validator, one error class, one handler.** Earlier versions copied the checks into each
  endpoint. Now a new endpoint gets the same rules and the same `{"error"}` format by calling
  `_parse_game_params`.
- **Defaults for everything.** A bare `POST {}` works, which is handy for curl. The price: typos in
  field names (`"fold_eq": 0.9`) are silently ignored.
- **`/api/solve` does everything in one round trip.** The UI needs your hand and the whole range
  together, so one endpoint returns both. `/api/evaluate` and `/api/range` remain for scripts.
- **The LLM is optional.** Without a key the endpoint still answers, which keeps tests offline and
  the UI working. The fallback only rephrases numbers the client already has.

---

## ⚠️ Weak spots

1. **Global state.** [app.py:26-36](../backend/app.py#L26-L36) and [:84](../backend/app.py#L84)
   contradict AGENTS.md §2.2 ("No global mutable state… dependency injection"). Tests cannot give
   the app a small fake database, and every importer pays for the tables. *Fix:* an app factory
   that receives the DB and the model.
2. **A guard that guards nothing.** [app.py:33](../backend/app.py#L33): if the file is missing,
   `RangeFinder` loads it anyway and the import fails. `database_loaded` in `/health` is always
   true. *Fix:* remove the `if`, or catch `DatabaseError` and serve a degraded `/health`.
3. **NaN gets through.** [app.py:61](../backend/app.py#L61) uses `pot <= 0`, which is false for
   NaN, so `"pot": "nan"` returns 200 with `NaN` in the body, which browsers cannot parse (`"inf"`
   also returns 200). *Fix:* `math.isfinite` (exercise 4).
4. **A list body is a 500.** [app.py:164](../backend/app.py#L164) and [:55](../backend/app.py#L55):
   `[1, 2, 3]` is valid JSON but not a dict, and `.get` raises `AttributeError`. *Fix:* check
   `isinstance(data, dict)` in the validator (exercise 5).
5. **HTML errors from a JSON API.** No handler exists for 404, 405 or 500, so `GET /api/nope` and
   `GET /api/solve` return Flask's HTML pages (`text/html`). If the UI ever got a 500, its
   `solveRes.json()` would fail on the HTML and it would show only `HTTP 500`
   ([App.jsx:69-72](../frontend/src/App.jsx#L69-L72)). *Fix:* `@app.errorhandler(HTTPException)` (exercise 5).
6. **Inconsistent response shapes.** Section 5's table. *Fix:* one response builder, used by all
   three endpoints, and a version number in the URL before changing it.
7. **Silent defaults and ignored fields.** Misspelled keys are ignored; `silent=True`
   ([app.py:164](../backend/app.py#L164)) turns a broken body into `{}`; a non-string hand
   (`{"hand": 12345}`) is skipped by [app.py:171](../backend/app.py#L171), so the answer is 200
   with `hand_evaluation: null`. *Fix:* reject unknown keys and wrong types with 400.
8. **`/api/analyze` trusts the client.** [app.py:322-331](../backend/app.py#L322-L331) takes
   `hand_evaluation` and `range_coverage_percent` as given and puts the strings into the prompt
   ([app.py:340-365](../backend/app.py#L340-L365)), which is a prompt-injection path. It also
   echoes OpenRouter's raw `resp.text` to the client ([app.py:433](../backend/app.py#L433)),
   turns an unexpected 200 body into a `KeyError` 500 ([app.py:426](../backend/app.py#L426)),
   builds the prompt even when there is no key, and hard-codes the model name twice
   ([:408](../backend/app.py#L408), [:429](../backend/app.py#L429)). *Fix:* recompute the
   evaluation on the server from `hand` and the game parameters (exercise 7).
9. **Copies and literals.** Hand parsing ([:172-177](../backend/app.py#L172-L177) /
   [:251-256](../backend/app.py#L251-L256)), the range summary ([:196-199](../backend/app.py#L196-L199) /
   [:283-287](../backend/app.py#L283-L287)), `22100` ([:226](../backend/app.py#L226),
   [:296](../backend/app.py#L296)), top 30 ([:211](../backend/app.py#L211), [:310](../backend/app.py#L310)),
   `"1.0.0"` ([:149](../backend/app.py#L149)), the defaults ([:55-57](../backend/app.py#L55-L57)),
   and the canonical ID computed twice per request ([:174-175](../backend/app.py#L174-L175)).

---

## 🧪 Try it

Run from `backend/` with the virtual environment active. Keep `OPENROUTER_API_KEY` unset.

```bash
python -m pytest tests/test_api.py -q
```

```
.................                                                        [100%]
17 passed in 0.28s
```

The validator table, without starting a server:

```bash
python -c '
from app import app
c = app.test_client()
for body in ({"pot": "abc"}, {"fold_equity": 2.5}, {"opponent_model": "psychic"}, {"hand": "As As Qd"}):
    r = c.post("/api/solve", json=body)
    print(r.status_code, r.get_json())
r = c.post("/api/solve", json={"pot": "nan"})
print(r.status_code, r.data[r.data.find(b"\"pot\""):][:10])
print(c.get("/api/nope").status_code, c.get("/api/nope").content_type)
'
```

```
400 {'error': 'Invalid numerical parameters for pot, bet_size, or fold_equity.'}
400 {'error': 'Fold equity must be between 0.0 and 1.0.'}
400 {'error': 'opponent_model must be one of: random, range.'}
400 {'error': 'Invalid hand: A Liêng hand cannot have duplicate cards.'}
200 b'"pot":NaN,'
404 text/html; charset=utf-8
```

The offline analysis, first line only:

```bash
python -c '
from app import app
r = app.test_client().post("/api/analyze", json={"pot": 100000, "bet_size": 50000})
print(r.status_code, r.get_json()["model"]); print(r.get_json()["advice"].splitlines()[0])
'
```

```
200 rule-based-solver-engine (OPENROUTER_API_KEY not configured)
**[Phân Tích Chiến Thuật Hệ Thống (Offline Solver)]**
```

If the dev server is running (`python app.py`), the same with curl:

```bash
curl -s http://127.0.0.1:5000/health
```

```
{"classes_loaded":455,"database_loaded":true,"status":"healthy","version":"1.0.0"}
```

---

## 🏋️ Exercises

Exercises marked 🟡 or 🔴 change code. Undo them afterwards with `git checkout -- <file>`.

**🟢 1. Predict.** `POST /api/solve` with `{"bet": 100000, "hand": "Ks Qh 3d"}`. Which pot, fold
rate and model are used? What are `ev`, `decision` and `profitable_fold_zones`? Check with the
test client.

<details><summary>Solution</summary>

`bet` is accepted as `bet_size` (100,000). The rest are defaults: pot 100,000, folds 0.35, model
`random`. That is the CLI's random K-Q-3 case: `ev` 40200.0, `decision` "RAISE",
`showdown_equity` 0.36, zones `[[0.0, 1.0]]`, and 387 profitable classes in the summary.
</details>

**🟢 2. Predict.** What do these return: `POST /api/evaluate` with `{"pot": 100000}`, and
`POST /api/solve` with `{"hand": 12345}`?

<details><summary>Solution</summary>

400 `{"error": "Field 'hand' is required."}` for the first. For the second, 200: the hand is not
a string, so [app.py:171](../backend/app.py#L171) skips it, and `hand_evaluation` is `null`. The
same mistake gives an error from one endpoint and silence from the other.
</details>

**🟢 3. Predict.** `{"pot": "nan"}` gives 200 but `{"fold_equity": "nan"}` gives 400. Explain it
from the two `if` lines in `_parse_game_params`.

<details><summary>Solution</summary>

`pot <= 0` asks "is it bad?": NaN compared with anything is `False`, so it is not rejected.
`not (0.0 <= f <= 1.0)` asks "is it good?": the comparison is `False`, so `not` makes it rejected.
Writing every check in the "must be good" form (`not (pot > 0)`) would have caught both.
</details>

**🟡 4. Reject non-finite numbers.** Make `"nan"`, `"inf"` and `"-inf"` a 400 for every endpoint.
Add a parametrised test to `test_api.py`. Check: `python -m pytest -q` goes from 93 to 96 passed.

<details><summary>Solution</summary>

Add `import math`, then before the `pot <= 0` check:

```python
    if not all(math.isfinite(x) for x in (pot, bet_size, fold_equity)):
        raise InvalidGameParamsError("pot, bet_size and fold_equity must be finite numbers.")
```

```python
@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_non_finite_numbers_are_rejected(client, value):
    res = client.post("/api/solve", json={"pot": value})
    assert res.status_code == 400
    assert "finite" in res.get_json()["error"]
```
</details>

**🟡 5. JSON for every error.** Make 404/405 answer `{"error": …}` and make a list body a 400.
Check: `GET /api/nope` returns JSON, and `POST /api/solve` with `[1, 2, 3]` returns 400.

<details><summary>Solution</summary>

```python
from werkzeug.exceptions import HTTPException

@app.errorhandler(HTTPException)
def handle_http_error(err: HTTPException) -> Any:
    """Render 404, 405 and friends as JSON instead of Flask's HTML page."""
    return jsonify({"error": err.description}), err.code
```

and at the top of `_parse_game_params`:

```python
    if not isinstance(data, dict):
        raise InvalidGameParamsError("The request body must be a JSON object.")
```

With exercises 4 and 5 together plus one test for this one, the suite was 97 passed. `GET /api/nope`
now gives `404 {'error': 'The requested URL was not found on the server. …'}`.
</details>

**🔴 6. An app factory.** Replace the module-level objects with
`def create_app(db: WinRateDB, calling_model: CallingRangeModel) -> Flask`, keep `app =
create_app(...)` at the bottom for gunicorn, and change the `client` fixture to build its own
app. Check: all 93 tests pass, and a new test can pass a `WinRateDB` loaded from a tiny file.

<details><summary>Hints</summary>

Move the routes inside the factory (they close over `db`, `calling_model` and `range_finder`), or
use a Flask `Blueprint` and store the objects in `app.extensions`. `_equity_function` then takes
the model as an argument instead of reading a global. Gunicorn still runs `app:app` (lesson 16).
</details>

**🔴 7. Stop trusting the client in `/api/analyze`.** Compute the hand evaluation on the server
from `hand` and the game parameters, and ignore `hand_evaluation` from the body. Check: the
"IGNORE ALL RULES" request from section 6 now gets a 400 (it has no valid hand) or a correct
general analysis, and the existing analyze tests still pass.

<details><summary>Hints</summary>

Reuse the parsing block from `/api/solve` and `_evaluate_hand(canonical.canonical_id,
stats.equity, params)`. Coverage can come from `range_finder.solve_range(...)` and
`calculate_range_coverage`. The two lines of copied parsing are a hint to extract a
`_parse_hand(data)` helper first (weak spot 9).
</details>

---

## ❓ Quiz

1. What does Python do the first time anything imports `app.py`, and roughly what does it cost?
2. Why does `/health` never report `"database_loaded": false`?
3. Why does `{"pot": "nan"}` pass validation while `{"fold_equity": "nan"}` does not?
4. Which errors come back as JSON, and which as HTML?
5. Why is the offline analysis text no more trustworthy than the request that asked for it?

<details><summary>Answers</summary>

1. It creates the Flask app, enables CORS, loads `winrates.json`, builds the calling-range tables
   and a `RangeFinder`: about 70 ms on the course machine, once per process.
2. If the file is missing, `RangeFinder.__init__` calls `db.load()` and raises `DatabaseError`
   during the import, so no server ever starts to answer `/health`.
3. `pot <= 0` is false for NaN, so it is not rejected. `0.0 <= f <= 1.0` is false for NaN, so it is.
4. JSON: `InvalidGameParamsError` (the one handler, 400), bad hands and a missing hand (inline
   400), and OpenRouter failures (502). HTML: everything else, such as 404, 405 and 500.
5. Its numbers and strings (`ev`, `showdown_equity`, `decision`, `hand`, coverage) are copied
   from the request body. The server only checks that two of them are numbers.
</details>

---

## Recap

- Importing `app.py` builds the app, CORS and three engine objects once; routes use them as
  globals, against AGENTS.md §2.2.
- Every POST route runs `_parse_game_params`: defaults for everything, `bet` as an alias, and an
  `InvalidGameParamsError` that the single handler turns into a 400 `{"error"}`.
- Bad hands are a 400 too, handled inline. Anything else (404, 405, 500) is Flask's HTML.
- `/api/solve` returns `summary`, `hand_evaluation` and `top_hands`; `/api/evaluate` and
  `/api/range` use flatter, different shapes.
- `/api/analyze` answers with a rule-based Vietnamese text when `OPENROUTER_API_KEY` is unset, and
  it trusts the evaluation the client sends.
- CORS `"*"` lets any web page call the API from a browser. That is fine only because there is
  nothing private behind it.

**Next:** [11 — Tracing one request end to end](11-request-trace.md)
