# 13 — The Flask Web API

> **Goal:** put the engine behind a web API, so a web page (or any program) can send a game situation as
> JSON and get the decision back as JSON, with either opponent model.
> **You will build:** `backend/app.py` (6 endpoints + shared helpers) and `backend/tests/test_api.py`
> (17 tests).
> **Time:** ~3 hours.
> **Prerequisites:** [12](12-cli.md). Flask is already installed (chapter 2).

---

## The big picture

The CLI works for someone sitting at the terminal. A browser can't run Python, but it **can** send HTTP
requests. So we wrap the same engine in a small web server:

```
 Browser (React, ch 15–16)                         Flask server: backend/app.py  (port 5000)
 ─────────────────────────                         ─────────────────────────────────────────
 fetch("POST /api/solve",                    ┌──►  @app.route("/api/solve")
       {"pot":100000, "bet_size":50000,      │       1. _parse_game_params(body)  ──► 400 if bad (error handler)
        "fold_equity":0.35,                  │       2. Hand.from_str             ──► 400 if bad hand
        "hand":"As Kh Qd",                   │       3. _evaluate_hand: EV + profitable fold zones
        "opponent_model":"range"}) ──────────┘       4. RangeFinder.solve_range + _category_breakdown
                                                     5. jsonify(result)
 ◄──────────────── 200 OK  {"summary": {...},
                            "hand_evaluation": {...},
                            "top_hands": [...]}

 created once at start-up:  WinRateDB (chapter 8) ─┐
                            CallingRangeModel (ch 9)┴─► RangeFinder (chapter 11)
```

| Method & path | Purpose |
|---|---|
| `GET /` | service info and the list of endpoints |
| `GET /health` | is the database loaded? |
| `POST /api/solve` | full range + optional single-hand decision (what the web page uses) |
| `POST /api/evaluate` | single-hand decision only |
| `POST /api/range` | range summary only |
| `POST /api/analyze` | strategy commentary in Vietnamese, from an LLM (or a built-in fallback) |

Every solver endpoint accepts an optional `"opponent_model"`: `"random"` (the **default**, so older
clients keep working) or `"range"` (chapter 9).

---

## Concepts you need

### HTTP in five minutes

The web is clients sending **requests** to servers, which send back **responses**.

A **request** has:

- a **method**: `GET` (read something) or `POST` (send data to be processed),
- a **path**: `/api/solve`,
- **headers**: metadata, e.g. `Content-Type: application/json`,
- an optional **body**: for us, JSON text.

A **response** has:

- a **status code**: `200 OK`, `400 Bad Request` (the client sent something wrong), `500 Internal
  Server Error` (the server crashed), `502 Bad Gateway` (a server we depend on failed),
- headers,
- a body (JSON for us).

An **API** ("Application Programming Interface") is a set of such URLs that programs call. **REST** is a
popular style for designing them: paths name resources, methods name actions, and bodies are JSON.

### Flask in 10 lines

```python
from flask import Flask, jsonify, request

app = Flask(__name__)

@app.route("/hello", methods=["POST"])       # "call this function for POST /hello"
def hello():
    data = request.get_json(silent=True) or {}       # body → dict (or {} if missing/invalid)
    name = data.get("name", "world")
    return jsonify({"greeting": f"Hi {name}"}), 200  # dict → JSON response, status 200
```

- `@app.route(path, methods=[...])` is a **decorator** that registers the function as the handler for
  that path.
- `request` is a special object holding the **current** request (Flask makes it work per request).
- Returning `(body, status_code)` sets the status. Returning just a body means 200.

### Error handlers: turning exceptions into responses

Instead of writing `try/except` in every route, Flask lets you register **one** function for an
exception type:

```python
@app.errorhandler(InvalidGameParamsError)
def handle_invalid_params(err):
    return jsonify({"error": str(err)}), 400
```

Now **any** code running during a request (a route, or a helper the route calls) can simply
`raise InvalidGameParamsError("...")`, and Flask converts it into a `400` JSON response. Validation code
gets short: no error-return plumbing.

### A parameter object

Four values travel together through every solver endpoint: pot, bet size, fold equity, opponent model.
Instead of passing four loose variables around, the code bundles them in a small frozen dataclass,
`GameParams`. This is called a **parameter object**: one validated value that can be passed to helpers.

### CORS: why the browser needs permission

Our page will be served from `http://localhost:5173` (Vite) and the API from `http://localhost:5000`.
Different port = different **origin**. Browsers block a page from reading responses from another origin
unless the server says it's allowed, by sending a header like `Access-Control-Allow-Origin`. This rule
is called **CORS** (Cross-Origin Resource Sharing). The `flask-cors` extension adds those headers for us.

> 💡 CORS is enforced by **browsers** only. `curl` and Python's `requests` ignore it. That's why an API
> can work perfectly with curl and still fail from a web page.

### Secrets live in environment variables

Never write passwords or API keys in source code: it ends up in git, and then on GitHub. Instead the
program reads them from the **environment**:

```python
import os
api_key = os.environ.get("OPENROUTER_API_KEY")   # None if not set
```

```bash
export OPENROUTER_API_KEY="sk-or-..."   # set it in your shell (Windows PowerShell: $env:OPENROUTER_API_KEY="...")
```

---

## Step 13.1 — Docstring and imports

📄 **File:** `backend/app.py` — *create this file*

```python
"""Liêng Stealer - Flask REST API Backend.

Provides RESTful endpoints for game-theoretic range solving, single-hand valuation,
and AI-powered strategic commentary via OpenRouter LLM.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

from src.calling_range import CallingRangeModel, OpponentModel
from src.db import WinRateDB
from src.evaluator import Hand, HandCategory
from src.exceptions import InvalidGameParamsError, LiengError
from src.ev import EVResult, calculate_break_even_fold_equity, evaluate_action, profitable_fold_zones
from src.hands import to_canonical
from src.range_finder import HandEVRecord, RangeFinder
```

Note the location: `backend/app.py`, **next to** `src/`, not inside it. Run from `backend/`, the import
`from src.db import WinRateDB` works exactly as in the tests. The imports read like a table of contents:
almost every module from chapters 4–11 is used here.

---

## Step 13.2 — Create the app, enable CORS, build the engine

📄 **File:** `backend/app.py` — *add to the end*

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

**How it works**

- `Flask(__name__)` creates the application. `__name__` helps Flask find files relative to this module.
- `CORS(app, resources=...)` allows **any** origin (`"*"`) to call `/api/*`, `/` and `/health`. Fine for a
  public, read-only calculator. An API with user accounts would list specific origins instead.
- **Absolute path:** `Path(__file__).resolve().parent` is the folder containing `app.py`, so `DB_PATH`
  is correct no matter which folder the server is started from. (This is the explicit style suggested in
  chapter 8's pitfall.)
- The engine is built **once, when the module is imported**, and shared by all requests: the database
  (~2 ms), the calling-range tables (~60 ms, chapter 9) and the range finder, which receives both
  (**dependency injection**). Building them per request would redo that work every time.

> ⚠️ **Pitfall: module-level state.** `win_rate_db`, `calling_model` and `range_finder` are global
> variables created at import time, which `AGENTS.md` forbids ("no global mutable state"). Importing
> `app` now takes ~0.25 s, and if the data file is missing, `RangeFinder(...)` silently tries `load()`
> with the default path (chapter 11 pitfall) and the import itself crashes. Flask's recommended
> alternative is an **application factory**:
>
> ```python
> def create_app(db_path: Path) -> Flask:
>     app = Flask(__name__)
>     db = WinRateDB(db_path)                         # fails loudly if missing
>     finder = RangeFinder(db, CallingRangeModel())
>     # ... register routes that use db/finder (via closures or app.extensions) ...
>     return app
> ```
>
> Then tests can build an app with a small test database, and nothing happens on import.

---

## Step 13.3 — `GameParams` and `_parse_game_params`: validate once

📄 **File:** `backend/app.py` — *add to the end*

```python


@dataclass(frozen=True)
class GameParams:
    """Validated game-state parameters shared by the solver endpoints."""
    pot: float
    bet_size: float
    fold_equity: float
    opponent_model: OpponentModel


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

**How it works**

- **Never trust input from the network.** A client might send `"pot": "abc"` (→ `ValueError` in
  `float`), `"pot": null` (→ `TypeError`), `-100`, or `"opponent_model": "psychic"`. Each case raises
  `InvalidGameParamsError` (chapter 4) with a message that tells the client what to fix.
- `data.get("bet_size", data.get("bet", 50000.0))` accepts **either** name (`bet_size` or `bet`), then
  falls back to a default. Missing fields get the chapter 1 example values.
- `OpponentModel(text)` turns the string into the enum, or raises `ValueError` for unknown text
  (chapter 9). The error message lists the valid choices, built from the enum itself, so adding a third
  model would update the message automatically.
- `raise … from err` keeps the original error attached for debugging (chapter 3).
- The result is one frozen `GameParams` object: validated once, then passed around safely.

> ✅ **How the code fixed this (before → after).** The first version of this API copy-pasted the same
> ~12 lines of "parse three numbers, check their ranges, return a 400" into **three** endpoints, and the
> copies had already drifted apart (`/api/solve` accepted only `bet_size`; the others also accepted
> `bet`; the error messages differed). Now there is **one** function, used by all three endpoints, and a
> new parameter (`opponent_model`) only had to be added in one place. **Lesson:** when you see the same
> block three times, extract it before the copies diverge.

---

## Step 13.4 — The error handler

📄 **File:** `backend/app.py` — *add to the end*

```python


@app.errorhandler(InvalidGameParamsError)
def handle_invalid_params(err: InvalidGameParamsError) -> Any:
    """Render invalid game parameters as a 400 JSON error."""
    return jsonify({"error": str(err)}), 400
```

This is the "Error handlers" concept above. Because of it, the endpoints just call
`params = _parse_game_params(data)`: if the input is bad, the exception travels up out of the route and
Flask answers `400 {"error": "..."}` by itself.

---

## Step 13.5 — `_equity_function`, `_evaluate_hand`, `_break_even_fields`: one hand, either model

📄 **File:** `backend/app.py` — *add to the end*

```python


def _equity_function(canonical_id: str, random_equity: float, model: OpponentModel) -> Callable[[float], float]:
    """Map a fold frequency to Hero's equity when called, under the chosen opponent model."""
    if model is OpponentModel.RANGE:
        return lambda f: calling_model.equity(canonical_id, f)
    return lambda f: random_equity


def _evaluate_hand(
    canonical_id: str,
    random_equity: float,
    params: GameParams,
) -> tuple[EVResult, list[tuple[float, float]]]:
    """Return the EV result and the profitable fold-frequency zones."""
    equity_at = _equity_function(canonical_id, random_equity, params.opponent_model)
    ev_res = evaluate_action(params.pot, params.bet_size, params.fold_equity, equity_at(params.fold_equity))
    zones = profitable_fold_zones(params.pot, params.bet_size, equity_at)
    return ev_res, zones


def _break_even_fields(
    ev_res: EVResult,
    zones: list[tuple[float, float]],
    model: OpponentModel,
) -> dict[str, float | None]:
    """Describe when raising pays off, with one unambiguous meaning per field.

    break_even_fold_equity: exact fold frequency where EV = 0 (random model only; under
        RANGE, EV is not monotonic in fold equity, so no single break-even point exists).
    profitable_from_fold_equity: first 1%-grid fold frequency from which raising stays +EV.
        The last zone always ends at 1.0, because EV there equals the pot.
    """
    return {
        "break_even_fold_equity": ev_res.break_even_fold_equity if model is OpponentModel.RANDOM else None,
        "profitable_from_fold_equity": zones[-1][0],
    }
```

**How it works**

- **`_equity_function` returns a function** (a closure, chapter 10): "given a fold frequency, what is
  this hand's equity when called?" For the range model it asks `calling_model`; for the random model it
  ignores `f` and always returns the same number. Everything downstream works with either.
- `_evaluate_hand` uses that one function **twice**:
  1. at the current fold frequency, `equity_at(params.fold_equity)` → `evaluate_action` (chapter 10) →
     EV and decision;
  2. on the whole 0–100% grid → `profitable_fold_zones` → the zones for the UI's profit map.
- It returns a **tuple of two** values; callers unpack them (`ev_res, zones = ...`).
- **`_break_even_fields`** answers "from which fold frequency does raising pay?" with **two fields, one
  meaning each**:
  - `break_even_fold_equity`: the exact closed-form value from `calculate_break_even_fold_equity`
    (chapter 10), valid for the **random** model, where equity doesn't change with `f`. Under the **range**
    model EV isn't monotonic, so there is no single break-even point, and the field is `None` (JSON `null`)
    instead of a misleading number;
  - `profitable_from_fold_equity`: the start of the **last** profitable zone (`zones[-1][0]`), i.e. the
    first 1%-grid fold frequency from which raising stays +EV all the way to 100%. It exists for **both**
    models.
- **Why `zones[-1]` is always safe:** at `f = 1.0` the opponent always folds, so EV = the pot > 0. The
  scan therefore always ends inside a profitable zone, and the list is never empty. The docstring says
  so, so nobody "fixes" it with an unnecessary `if`.
- The return type `dict[str, float | None]` documents that a value may be `None`.

> ✅ **How the code fixed this (before → after).** The first version had **one** field,
> `break_even_fold_equity`, with **two** meanings: the exact EV = 0 point under the random model, but
> "the grid point from which raising stays +EV" under the range model (e.g. 0.51 for `K-Q-3`, although
> it is *also* profitable from 0 to 8%). A client that didn't check `opponent_model` would misread it.
> Now each meaning has its own name, and the inapplicable one is explicitly `null`. **Lesson:** a field
> name is a promise; never let one name mean two things.

---

## Step 13.6 — `_category_breakdown`: per-category numbers for the UI

📄 **File:** `backend/app.py` — *add to the end*

```python


def _category_breakdown(records: Sequence[HandEVRecord]) -> list[dict[str, Any]]:
    """Summarize classes, combos, and profitable combos per hand category (strongest first)."""
    breakdown = []
    for category in sorted(HandCategory, reverse=True):
        members = [r for r in records if r.category is category]
        breakdown.append({
            "category": category.name,
            "classes": len(members),
            "combos": sum(r.multiplicity for r in members),
            "profitable_combos": sum(r.multiplicity for r in members if r.is_raise_profitable),
        })
    return breakdown
```

**How it works**

- `sorted(HandCategory, reverse=True)` → `SAP, LIENG, DI, DIEM` (an `IntEnum` sorts by value, 4 → 1).
- For each category: count its classes, sum its multiplicities (all combos), and sum the multiplicities
  of the profitable ones. These totals are **computed from the data**: 52 / 768 / **144** / **21,136**,
  never typed by hand.

> ✅ **How the code fixed this (before → after).** The first version of the API sent only the *total*
> number of profitable combos, and the web page **guessed** the per-category split, with wrong hard-coded
> totals (288 for Đĩ instead of 144, 20,992 for Điểm instead of 21,136, copied from a wrong line in
> `DESIGN.md`). Now the backend, which has the exact data, sends `category_breakdown`, and the frontend
> just displays it (chapter 16). `DESIGN.md` and `README.md` were corrected too. **Lesson:** compute a fact
> in the one place that has the data; don't re-derive it elsewhere.

---

## Step 13.7 — The two simplest endpoints

📄 **File:** `backend/app.py` — *add to the end*

```python


@app.route("/", methods=["GET"])
def root() -> Any:
    """Root endpoint providing service metadata."""
    return jsonify({
        "service": "Lieng Stealer API",
        "status": "online",
        "endpoints": ["/health", "/api/solve", "/api/evaluate", "/api/range", "/api/analyze"],
    }), 200


@app.route("/health", methods=["GET"])
def health_check() -> Any:
    """Health check endpoint returning system status and database stats."""
    return jsonify({
        "status": "healthy",
        "database_loaded": win_rate_db.is_loaded,
        "classes_loaded": len(win_rate_db),
        "version": "1.0.0",
    })
```

**How it works**

- `jsonify(dict)` converts a Python dict into a JSON response with the right `Content-Type` header.
- A **health check** is a standard endpoint that hosting platforms call every few seconds to see if the
  service is alive. Reporting `classes_loaded: 455` also proves the data file was found.

> ✅ **How the code fixed this.** The root endpoint used to list only 3 of the 5 API endpoints
> (`/api/evaluate` and `/api/range` were missing). The list is complete now. It's still typed by hand,
> though; Flask can generate it: `[r.rule for r in app.url_map.iter_rules()]`, which can never drift.

🧪 **Mini-check.** Start the server (from `backend/`, venv active):

```bash
flask --app app run
```

`--app app` tells Flask to load the `app` object from `app.py`. You'll see a start-up message ending
with `Running on http://127.0.0.1:5000`. Leave it running and open a **second terminal**:

```bash
curl -s http://127.0.0.1:5000/
curl -s http://127.0.0.1:5000/health
```

Expected output:

```json
{"endpoints":["/health","/api/solve","/api/evaluate","/api/range","/api/analyze"],"service":"Lieng Stealer API","status":"online"}
{"classes_loaded":455,"database_loaded":true,"status":"healthy","version":"1.0.0"}
```

Stop the server with Ctrl-C. After editing `app.py`, restart it to load your changes (or start it with
`flask --app app run --debug`, which reloads automatically. Only ever use `--debug` on your own
machine). In Step 13.15 we'll also make `python app.py` start the server.

---

## Step 13.8 — `/api/solve`, part 1: parameters and the optional hand

`/api/solve` is the endpoint the web page uses. We build it in two slices.

📄 **File:** `backend/app.py` — *add to the end*

```python


@app.route("/api/solve", methods=["POST"])
def solve_api() -> Any:
    """Calculate EV range and specific hand decision.

    Expected JSON body:
        pot (float): Dead pot size (> 0).
        bet_size (float): Hero raise / wager amount (> 0).
        fold_equity (float): Opponent fold probability in [0.0, 1.0].
        hand (str, optional): Player 3-card hand notation (e.g. 'As Kh Qd').
        opponent_model (str, optional): 'random' (default) or 'range'.
    """
    data = request.get_json(silent=True) or {}
    params = _parse_game_params(data)
    pot, bet_size, fold_equity = params.pot, params.bet_size, params.fold_equity

    hand_input = data.get("hand")
    hand_eval_result = None

    if hand_input and isinstance(hand_input, str) and hand_input.strip():
        try:
            player_hand = Hand.from_str(hand_input.strip())
            stats = win_rate_db.get_by_cards(player_hand.cards)
            canonical = to_canonical(player_hand.cards)
        except LiengError as err:
            return jsonify({"error": f"Invalid hand: {err}"}), 400

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

**How it works**

- `request.get_json(silent=True)` parses the body as JSON. With `silent=True` it returns `None` instead
  of raising if the body is missing or invalid; `or {}` then gives an empty dict, so every field falls
  back to its default.
- **One line of validation** (`_parse_game_params`), thanks to Steps 13.3–13.4. The tuple assignment
  `pot, bet_size, fold_equity = …` copies three fields into short local names.
- The hand is **optional**: we only evaluate it if it's a non-empty string.
- **The `try` block is kept small**: only the three lines that can raise `LiengError` (parsing,
  lookup, canonical ID) are inside it, so an unrelated bug in `_evaluate_hand` can't be mis-reported as
  "Invalid hand". `except LiengError` turns a bad rank, bad suit, wrong card count or duplicate card into a
  400 with the engine's own message.
- The response dict converts objects to JSON-friendly values (`.name` → `"LIENG"`, `str(...)` →
  `"Liêng Q-K-A"`). New fields compared with a random-only API:
  - `showdown_equity`: the equity **actually used** (depends on the model);
  - `equity_vs_random`: the random-hand equity, always included for comparison;
  - `break_even_fold_equity` and `profitable_from_fold_equity` from Step 13.5. `**_break_even_fields(…)`
    **unpacks** the returned dict into this one (like `{**a, "x": 1}`), so both endpoints share the same
    two fields without copy-paste;
  - `profitable_fold_zones`: the zones as a list of `[start, end]` pairs (JSON has no tuples).

---

## Step 13.9 — `/api/solve`, part 2: the range and the response

📄 **File:** `backend/app.py` — *add to the end*

```python

    # Solve full range
    records = range_finder.solve_range(pot, bet_size, fold_equity, params.opponent_model)
    profitable_records = [r for r in records if r.is_raise_profitable]
    coverage = range_finder.calculate_range_coverage(profitable_records)
    be_bluff = calculate_break_even_fold_equity(pot, bet_size, win_rate_when_called=0.0)

    # Format top profitable hands (top 30)
    top_hands = [
        {
            "canonical_id": r.canonical_id,
            "category": r.category.name,
            "equity": r.equity,
            "ev": r.ev,
            "multiplicity": r.multiplicity,
            "is_profitable": r.is_raise_profitable,
        }
        for r in records[:30]
    ]

    total_combos_in_range = sum(r.multiplicity for r in profitable_records)

    return jsonify({
        "summary": {
            "pot": pot,
            "bet_size": bet_size,
            "fold_equity": fold_equity,
            "opponent_model": params.opponent_model.value,
            "final_pot": pot + 2.0 * bet_size,
            "pure_bluff_break_even_fold_equity": be_bluff,
            "total_canonical_classes": len(records),
            "profitable_classes": len(profitable_records),
            "total_combinations": 22100,
            "profitable_combinations": total_combos_in_range,
            "range_coverage_percent": coverage,
            "highest_ev_hand": records[0].canonical_id if records else None,
            "highest_ev_value": records[0].ev if records else None,
            "threshold_hand": profitable_records[-1].canonical_id if profitable_records else None,
            "threshold_ev_value": profitable_records[-1].ev if profitable_records else None,
            "category_breakdown": _category_breakdown(records),
        },
        "hand_evaluation": hand_eval_result,
        "top_hands": top_hands,
    })
```

**How it works**

- Same calculations as `run_solver` in the CLI, plus the opponent model, but the result is **data** (a
  JSON document), not text. The API doesn't decide how things look; the frontend does. That's the
  separation between backend and frontend.
- Only the **top 30** records are sent, to keep the response small. The summary carries the totals, and
  `category_breakdown` (Step 13.6) carries the per-category numbers.
- `hand_evaluation` is `null` in JSON when no hand was sent.
- `params.opponent_model.value` echoes back `"random"` or `"range"`, so the client can see which model
  produced the numbers.

🧪 **Mini-check** (restart the server first). A medium hand, pot-sized bet, range model:

```bash
curl -s -X POST http://127.0.0.1:5000/api/solve \
  -H "Content-Type: application/json" \
  -d '{"pot": 100000, "bet_size": 100000, "fold_equity": 0.35, "hand": "Ks Qh 3d", "opponent_model": "range"}'
```

The response is long. The `hand_evaluation` part should be (Flask sorts keys alphabetically):

```json
{
  "break_even_fold_equity": null,
  "canonical_id": "K-Q-3",
  "category": "DIEM",
  "category_name": "Điểm",
  "decision": "CHECK/FOLD",
  "equity_vs_random": 0.36,
  "ev": -27894.0,
  "hand": "Ks Qh 3d",
  "is_profitable": false,
  "profitable_fold_zones": [[0.0, 0.08], [0.51, 1.0]],
  "profitable_from_fold_equity": 0.51,
  "score_name": "3 điểm",
  "showdown_equity": 0.0108
}
```

Compare with chapter 9's worked example (0.0108) and chapter 10's zones. In `summary` you should find
`"opponent_model": "range"`, `"range_coverage_percent": 54.57` and

```json
"category_breakdown": [
  {"category": "SAP", "classes": 13, "combos": 52, "profitable_combos": 52},
  {"category": "LIENG", "classes": 12, "combos": 768, "profitable_combos": 768},
  {"category": "DI", "classes": 6, "combos": 144, "profitable_combos": 144},
  {"category": "DIEM", "classes": 424, "combos": 21136, "profitable_combos": 11096}
]
```

Repeat the request **without** `"opponent_model"` (so the random model): the decision flips to `RAISE`,
`showdown_equity` equals `equity_vs_random` (0.36), and the zones become `[[0.0, 1.0]]`. For a case
where both break-even fields have a value, try `2s 3h 5d` with `"bet_size": 50000, "fold_equity": 0.05`
(random model): `"break_even_fold_equity": 0.3312` (exact) and `"profitable_from_fold_equity": 0.34`
(the first grid point above it).

Now try bad input:

```bash
curl -s -i -X POST http://127.0.0.1:5000/api/solve -H "Content-Type: application/json" \
  -d '{"pot": 100, "bet_size": 50, "opponent_model": "psychic"}'
```

```
HTTP/1.1 400 BAD REQUEST
...
{"error":"opponent_model must be one of: random, range."}
```

(`-i` makes curl print the status line and headers too.) A bad hand such as `"Xx Kh Qd"` gives
`{"error":"Invalid hand: Invalid rank 'X'. Must be 2-10, T, J, Q, K, or A."}`. If you use Windows
PowerShell, `curl` may be an alias for a different command; use `curl.exe`, or test with Python's
`requests` instead.

---

## Step 13.10 — `/api/evaluate`: one hand only

📄 **File:** `backend/app.py` — *add to the end*

```python


@app.route("/api/evaluate", methods=["POST"])
def evaluate_api() -> Any:
    """Evaluate a single 3-card hand against current game parameters."""
    data = request.get_json(silent=True) or {}
    params = _parse_game_params(data)
    pot, bet, fold_equity = params.pot, params.bet_size, params.fold_equity

    hand_input = data.get("hand")
    if not hand_input or not isinstance(hand_input, str) or not hand_input.strip():
        return jsonify({"error": "Field 'hand' is required."}), 400

    try:
        player_hand = Hand.from_str(hand_input.strip())
        stats = win_rate_db.get_by_cards(player_hand.cards)
        canonical = to_canonical(player_hand.cards)
    except LiengError as err:
        return jsonify({"error": f"Invalid hand: {err}"}), 400

    ev_res, zones = _evaluate_hand(canonical.canonical_id, stats.equity, params)
    return jsonify({
        "hand": str(player_hand),
        "canonical_id": canonical.canonical_id,
        "category": stats.category.name,
        "pot": pot,
        "bet": bet,
        "fold_equity": fold_equity,
        "opponent_model": params.opponent_model.value,
        "showdown_equity": ev_res.win_rate_when_called,
        "equity_vs_random": stats.equity,
        "ev": ev_res.ev,
        **_break_even_fields(ev_res, zones, params.opponent_model),
        "recommended_action": "RAISE" if ev_res.is_profitable else "CHECK/FOLD",
        "is_profitable": ev_res.is_profitable,
    }), 200
```

**How it works**

- Here `hand` is **required**: a missing hand is a 400, not "skip it".
- The same helpers as `/api/solve`, including both break-even fields via `**_break_even_fields(…)`. The
  zones are used to compute `profitable_from_fold_equity`, but not sent in this lighter response.

> ⚠️ **Still inconsistent: response field names.** Validation is shared now, but the responses still
> name things differently: `/api/solve` says `"bet_size"` and `"decision"`; `/api/evaluate` says `"bet"`
> and `"recommended_action"`; `/api/range` calls equity `"showdown_equity"` where `/api/solve`'s
> `top_hands` says `"equity"`. Clients must remember which endpoint uses which name. A shared
> "serialise a record" helper (like `_parse_game_params` for input) would fix the output side.

---

## Step 13.11 — `/api/range`: range only

📄 **File:** `backend/app.py` — *add to the end*

```python


@app.route("/api/range", methods=["POST"])
def range_api() -> Any:
    """Scan and return full combinatorial range coverage and thresholds."""
    data = request.get_json(silent=True) or {}
    params = _parse_game_params(data)
    pot, bet, fold_equity = params.pot, params.bet_size, params.fold_equity

    records = range_finder.solve_range(pot, bet, fold_equity, params.opponent_model)
    profitable = [r for r in records if r.is_raise_profitable]
    coverage = range_finder.calculate_range_coverage(profitable)
    be_bluff = calculate_break_even_fold_equity(pot, bet, win_rate_when_called=0.0)
    combos = sum(r.multiplicity for r in profitable)

    return jsonify({
        "pot": pot,
        "bet": bet,
        "fold_equity": fold_equity,
        "opponent_model": params.opponent_model.value,
        "final_pot": pot + 2.0 * bet,
        "pure_bluff_break_even_fold_equity": be_bluff,
        "total_combinations": 22100,
        "profitable_combinations": combos,
        "range_coverage_percent": coverage,
        "total_canonical_classes": len(records),
        "profitable_classes": len(profitable),
        "top_hands": [
            {
                "canonical_id": r.canonical_id,
                "category": r.category.name,
                "showdown_equity": r.equity,
                "ev": r.ev,
                "multiplicity": r.multiplicity,
                "recommended_action": "RAISE" if r.is_raise_profitable else "CHECK/FOLD",
            }
            for r in records[:30]
        ],
    }), 200
```

Nothing new: the range part of `/api/solve` with a flat response. (The literal `22100` appears again;
`TOTAL_COMBINATIONS` would be better.)

---

## Step 13.12 — `/api/analyze`, part 1: inputs and the prompt

This endpoint asks a **Large Language Model** (an AI text generator, here Llama 3.1 via the OpenRouter
service) to write a short strategic analysis in Vietnamese. If no API key is configured, it builds
a rule-based text itself, so the feature always works.

📄 **File:** `backend/app.py` — *add to the end*

```python


@app.route("/api/analyze", methods=["POST"])
def analyze_api() -> Any:
    """Query OpenRouter LLM for strategic game-theoretic commentary."""
    data = request.get_json(silent=True) or {}
    params = _parse_game_params(data)
    pot, bet_size, fold_equity = params.pot, params.bet_size, params.fold_equity

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

    if folds_weakest:
        model_line = f"folds their weakest hands (calls only with the top {(1 - fold_equity) * 100:.0f}%)"
    else:
        model_line = "folds at random, regardless of hand strength"
    prompt = (
        f"You are a World-Class Game Theory Expert and High-Stakes Vietnamese Liêng Solver.\n"
        f"Analyze this decision spot with precision and strategic depth in Vietnamese:\n\n"
        f"- Current Pot: {pot:,.0f} VND\n"
        f"- Bet / Raise Size: {bet_size:,.0f} VND\n"
        f"- Opponent Fold Equity: {fold_equity * 100:.1f}%\n"
        f"- Opponent Model: {model_line}\n"
        f"- Total Range Coverage (Hands with EV > 0): {coverage}%\n"
    )

    if hand_eval:
        prompt += (
            f"- Hero's Hand: {hand_eval.get('hand')} ({hand_eval.get('score_name')})\n"
            f"- Showdown Equity: {hand_equity * 100:.1f}%\n"
            f"- Calculated EV: {hand_ev:+,.0f} VND\n"
            f"- Solver Decision: {hand_eval.get('decision')}\n"
        )
    else:
        prompt += f"- Hero's Hand: {hand} (General Range Analysis)\n"

    prompt += (
        "\nProvide a structured breakdown:\n"
        "1. [Quyết định Toán học & EV]: Phân tích EV, Fold Equity và ngưỡng hòa vốn.\n"
        "2. [Chiến thuật Bluff & Giá trị]: Hero có nên Tố (Raise)/Tất tay hay Check/Bỏ bài? Giải thích tâm lý đối thủ.\n"
        "3. [Lời khuyên GTO]: Nhận xét ngắn gọn về độ rủi ro và cách khai thác đối thủ."
    )
```

**How it works**

- The frontend sends back the numbers **it already got** from `/api/solve` (including
  `hand_evaluation` and the `opponent_model`), so this endpoint doesn't recompute anything.
- A **prompt** is the text instruction given to the LLM. It contains the role ("You are a … Solver"),
  the facts (pot, EV, decision, and now **how the opponent folds**) and the desired output structure
  (three numbered sections). Putting the *computed* numbers in the prompt matters: LLMs are bad at
  arithmetic, so we do the maths and let the model only explain it.
- **Validation first:** the same `_parse_game_params` as the other endpoints (Steps 13.3–13.4), plus
  checks for the extra input this endpoint reads: `hand_evaluation` must be a JSON object, and its `ev`
  and `showdown_equity` must convert to numbers. Both raise `InvalidGameParamsError`, which the error
  handler turns into a 400. After that, the f-strings can format `pot`, `hand_ev` etc. safely.
- `folds_weakest` is a boolean computed once and used twice (prompt and fallback). It now comes from the
  validated `params.opponent_model`, so an unknown model is a 400 instead of silently meaning "random".

> ✅ **How the code fixed this (before → after).** The first version of this endpoint read raw values:
> `{"pot": "abc"}` reached `f"{pot:,.0f}"`, which raised `ValueError` ("Unknown format code 'f' for object
> of type 'str'"), and Flask answered **500 Internal Server Error**. A malformed `hand_evaluation` crashed
> the same way. Because the other endpoints already shared `_parse_game_params`, the fix was mostly one
> line. Now:
>
> ```bash
> curl -s -i -X POST http://127.0.0.1:5000/api/analyze -H "Content-Type: application/json" -d '{"pot":"abc"}' | sed -n '1p;$p'
> ```
>
> ```
> HTTP/1.1 400 BAD REQUEST
> {"error":"Invalid numerical parameters for pot, bet_size, or fold_equity."}
> ```
>
> **Lesson:** a shared validation helper pays off twice: once when you write it, and again when the next
> endpoint can adopt it in one line.

---

## Step 13.13 — `/api/analyze`, part 2: the offline fallback

📄 **File:** `backend/app.py` — *add to the end*

```python

    if not api_key:
        # Fallback commentary when no OpenRouter API key is configured
        fallback_advice = (
            f"**[Phân Tích Chiến Thuật Hệ Thống (Offline Solver)]**\n\n"
            f"1. **Quyết định Toán học:** Với Pot = {pot:,.0f}, Cược = {bet_size:,.0f}, và Fold Equity = {fold_equity*100:.1f}%, "
            f"ngưỡng hòa vốn cược hù (bluff) là {(bet_size / (pot + bet_size))*100:.1f}%. "
            f"Khoảng bài có lãi (EV > 0) chiếm **{coverage}%** toàn bộ thế bài có thể có. "
            + ("Giả định đối thủ bỏ những bài yếu nhất, nên khi bị theo, Hero đối đầu với nhóm bài mạnh hơn.\n\n" if folds_weakest
               else "Giả định đối thủ bỏ bài ngẫu nhiên, không phụ thuộc độ mạnh của bài.\n\n")
            + "2. **Hành động Khuyến nghị:** "
        )
        if hand_eval:
            decision = hand_eval.get("decision", "EVALUATE")
            fallback_advice += (
                f"Hero cầm **{hand_eval.get('hand')}** ({hand_eval.get('score_name')}) "
                f"với xác suất thắng đối đầu {hand_equity*100:.1f}%. "
                f"Kỳ vọng thu nhập (EV) đạt **{hand_ev:+,.0f} VND**. "
                f"Khuyến nghị tối ưu: **{decision}**.\n\n"
                f"3. **GTO Insight:** "
                + ("Bài có EV dương rõ rệt nhờ cả showdown equity lẫn fold equity. Tố lớn để tối đa hóa lợi nhuận." if hand_ev > 0
                   else "EV âm. Showdown equity quá thấp và đối thủ ít bỏ bài. Không nên mạo hiểm, hãy Bỏ bài (Fold) hoặc Theo nhẹ nếu có thể.")
            )
        else:
            fallback_advice += (
                f"Với tần suất đối thủ bỏ bài {fold_equity*100:.1f}%, hãy ưu tiên nâng cược với các nhóm bài Sáp, Liêng, Đĩ "
                f"và các tổ hợp điểm cao (> 7 điểm). Cẩn trọng cược hù khi đối thủ có xu hướng theo cược dính."
            )

        return jsonify({
            "advice": fallback_advice,
            "model": "rule-based-solver-engine (OPENROUTER_API_KEY not configured)",
        })
```

**How it works**

- **Graceful degradation:** without a key, the endpoint still returns useful text (in Markdown:
  `**bold**`), built from the same numbers. The UI never shows an empty box, and tests can run offline.
- The text is assembled from pieces with `+`. One piece is chosen with a conditional expression
  (`"A" if folds_weakest else "B"`): it explains which opponent model the numbers assume ("the opponent
  folds their weakest hands, so when called, Hero faces a stronger group of hands" vs "the opponent folds
  at random").
- The hand's EV and equity come from the validated `hand_ev` / `hand_equity` (Step 13.12), never from the
  raw request.
- `bet_size / (pot + bet_size)` is the pure-bluff break-even `B / (P + B)` from chapter 10, written out by
  hand. Calling `calculate_break_even_fold_equity(pot, bet_size, 0.0)` would avoid a second copy of the
  formula.

---

## Step 13.14 — `/api/analyze`, part 3: calling OpenRouter

📄 **File:** `backend/app.py` — *add to the end*

```python

    # Call OpenRouter API
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/lieng-stealer",
        "X-Title": "Lieng Stealer Solver",
    }
    payload = {
        "model": "meta-llama/llama-3.1-8b-instruct:free",
        "messages": [
            {"role": "system", "content": "You are a professional game theory analyst specializing in Vietnamese card games like Liêng."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 500,
    }

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=20,
        )
        if resp.status_code == 200:
            result_json = resp.json()
            advice = result_json["choices"][0]["message"]["content"]
            return jsonify({
                "advice": advice,
                "model": "meta-llama/llama-3.1-8b-instruct:free",
            })
        else:
            return jsonify({
                "error": f"OpenRouter API returned status {resp.status_code}: {resp.text}",
                "advice": f"Không thể lấy phân tích từ AI (Mã lỗi {resp.status_code}). Vui lòng kiểm tra OPENROUTER_API_KEY.",
            }), 502
    except requests.RequestException as err:
        return jsonify({
            "error": str(err),
            "advice": "Lỗi kết nối tới OpenRouter AI gateway.",
        }), 502
```

**How it works**

- Here **our server becomes a client** of another API. `requests.post(url, headers=..., json=...,
  timeout=...)` sends the request; `json=payload` converts the dict to JSON and sets the content type.
- `Authorization: Bearer <key>` is the standard way to send an API key.
- The body follows the common **chat-completions** format: a list of `messages`, each with a `role`
  (`system` sets the behaviour, `user` asks the question). `temperature` controls randomness (0 = always
  the same answer); `max_tokens` limits the answer's length.
- **Always set a `timeout`.** Without one, a slow external service can hang your server's worker
  forever. Here: give up after 20 seconds.
- Errors from the other service become **502 Bad Gateway** ("a server I depend on failed"), never a crash.
  `requests.RequestException` is the base class of all `requests` errors (timeouts, DNS failures, …).
- The answer text is at `result_json["choices"][0]["message"]["content"]`, the standard response shape.

> ⚠️ **Pitfall: hard-coded model and leaked details.** The model name appears twice and is hard-coded;
> free models on OpenRouter come and go, so it should come from an environment variable (with this as
> the default). And the 502 response includes `resp.text`, the other service's raw error, which may
> contain details you don't want to show to every browser. Log it on the server instead; send the client
> a generic message.

---

## Step 13.15 — Running the server directly

📄 **File:** `backend/app.py` — *add to the end*

```python


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
```

**How it works**

- `python app.py` now starts Flask's **development server**.
- `PORT` comes from the environment (hosting platforms set it), defaulting to 5000.
- `host="0.0.0.0"` listens on all network interfaces (so other devices on your network can connect),
  not just `127.0.0.1`.
- `debug=False`: debug mode shows an interactive debugger in the browser on errors, which must **never**
  be enabled on a public server (anyone could run code on it). For production, use gunicorn (chapter 17).

---

## Step 13.16 — The tests

Flask has a built-in **test client**: it sends fake requests straight to your app, without starting a
server or using the network.

📄 **File:** `backend/tests/test_api.py` — *create this file*

```python
"""Unit tests for Flask API endpoints in backend/app.py."""

import pytest
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_root_endpoint(client):
    res = client.get("/")
    assert res.status_code == 200
    data = res.get_json()
    assert data["service"] == "Lieng Stealer API"
    assert data["status"] == "online"
    assert data["endpoints"] == ["/health", "/api/solve", "/api/evaluate", "/api/range", "/api/analyze"]


def test_health_endpoint(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "healthy"
    assert data["classes_loaded"] == 455


def test_solve_endpoint_general(client):
    payload = {
        "pot": 100000,
        "bet_size": 50000,
        "fold_equity": 0.35,
    }
    res = client.post("/api/solve", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert "summary" in data
    assert data["summary"]["range_coverage_percent"] == 100.0
    assert len(data["top_hands"]) > 0
```

**How it works**

- `from app import app` imports our Flask object. (pytest puts `backend/` on the path because
  `tests/` is a package, so `app.py` is importable.) Importing it builds the engine once (Step 13.2).
- The fixture uses **`yield`** instead of `return`: code before `yield` is set-up, the yielded value goes
  to the test, and code after it (here, leaving the `with` block) is clean-up.
- `client.get("/")` / `client.post("/api/solve", json=payload)` send requests; `res.status_code` and
  `res.get_json()` read the response.

📄 **File:** `backend/tests/test_api.py` — *add to the end*

```python


def test_solve_endpoint_with_hand(client):
    payload = {
        "pot": 100000,
        "bet_size": 50000,
        "fold_equity": 0.35,
        "hand": "As Kh Qd",
    }
    res = client.post("/api/solve", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["hand_evaluation"] is not None
    assert data["hand_evaluation"]["decision"] == "RAISE"
    assert data["hand_evaluation"]["canonical_id"] == "Q-K-A"
    assert data["hand_evaluation"]["ev"] > 0


def test_solve_endpoint_invalid_inputs(client):
    res = client.post("/api/solve", json={"pot": -100, "bet_size": 50})
    assert res.status_code == 400

    res2 = client.post("/api/solve", json={"pot": 100, "bet_size": 50, "fold_equity": 2.5})
    assert res2.status_code == 400

    res3 = client.post("/api/solve", json={"pot": 100, "bet_size": 50, "hand": "InvalidHand"})
    assert res3.status_code == 400
```

The first two invalid requests are rejected by `_parse_game_params` + the error handler; the third by
`except LiengError` in the route. The test doesn't care which mechanism answers, only that it's a 400.
That's good testing: test **behaviour**, not implementation.

📄 **File:** `backend/tests/test_api.py` — *add to the end*

```python


def test_analyze_endpoint(client, monkeypatch):
    # Force the offline fallback: a test must never call the real OpenRouter API
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    payload = {
        "pot": 100000,
        "bet_size": 50000,
        "fold_equity": 0.35,
        "hand": "As Kh Qd",
        "hand_evaluation": {
            "hand": "As Kh Qd",
            "score_name": "Liêng Q-K-A",
            "showdown_equity": 0.9969,
            "ev": 132097.0,
            "decision": "RAISE",
        },
        "range_coverage_percent": 100.0,
    }
    res = client.post("/api/analyze", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert "advice" in data
    assert len(data["advice"]) > 0
```

> ✅ **How the code fixed this (before → after).** The first version of `test_analyze_endpoint` had no
> `monkeypatch`: with `OPENROUTER_API_KEY` set in your shell it sent a **real** request to OpenRouter,
> which was slow, used your quota, and failed offline (502 ≠ 200). Now `monkeypatch.delenv(...)` removes
> the variable **for this test only** (pytest restores it afterwards), forcing the offline fallback.
> Check it: `OPENROUTER_API_KEY=dummy python -m pytest tests/test_api.py -q` still passes, without
> network. **Lesson:** tests must never depend on external services.

Now the tests for the opponent models. (The original file has three blank lines before this test; two
are standard, the third is harmless.)

📄 **File:** `backend/tests/test_api.py` — *add to the end*

```python



def test_solve_default_model_is_random_hand(client):
    """Omitting opponent_model keeps the original random-hand equity for existing clients."""
    res = client.post("/api/solve", json={"pot": 100000, "bet_size": 100000, "fold_equity": 0.35, "hand": "Ks Qh 3d"})
    data = res.get_json()
    hand_eval = data["hand_evaluation"]
    assert data["summary"]["opponent_model"] == "random"
    assert hand_eval["showdown_equity"] == hand_eval["equity_vs_random"]
    assert hand_eval["decision"] == "RAISE"
    assert hand_eval["profitable_fold_zones"] == [[0.0, 1.0]]


def test_solve_range_model_flips_medium_hand(client):
    """An opponent who folds their weakest 35% leaves 3 points almost drawing dead when called."""
    payload = {"pot": 100000, "bet_size": 100000, "fold_equity": 0.35, "hand": "Ks Qh 3d", "opponent_model": "range"}
    data = client.post("/api/solve", json=payload).get_json()
    hand_eval = data["hand_evaluation"]
    assert data["summary"]["opponent_model"] == "range"
    assert hand_eval["equity_vs_random"] == 0.36
    assert hand_eval["showdown_equity"] < 0.02
    assert hand_eval["decision"] == "CHECK/FOLD"
    assert len(hand_eval["profitable_fold_zones"]) == 2
    # EV is not monotonic in fold equity here, so there is no single break-even point
    assert hand_eval["break_even_fold_equity"] is None
    assert hand_eval["profitable_from_fold_equity"] == 0.51
```

**In plain words:** the **same request** about `K-Q-3`, once per model. With the default (random) model
it's a raise everywhere; with the range model it's a fold at 35%, with two profit zones, **no** single
break-even (`None`) and the "stays-profitable-from" point at 0.51. The first test is a **backward-compatibility test**: it guarantees
that clients written before the range model existed still get the old behaviour.

📄 **File:** `backend/tests/test_api.py` — *add to the end*

```python


def test_solve_invalid_opponent_model(client):
    res = client.post("/api/solve", json={"pot": 100, "bet_size": 50, "opponent_model": "psychic"})
    assert res.status_code == 400
    assert "opponent_model" in res.get_json()["error"]


def test_solve_category_breakdown(client):
    data = client.post("/api/solve", json={"pot": 100000, "bet_size": 50000, "fold_equity": 0.0}).get_json()
    breakdown = {row["category"]: row for row in data["summary"]["category_breakdown"]}
    assert [row["category"] for row in data["summary"]["category_breakdown"]] == ["SAP", "LIENG", "DI", "DIEM"]
    assert {cat: row["combos"] for cat, row in breakdown.items()} == {"SAP": 52, "LIENG": 768, "DI": 144, "DIEM": 21136}
    assert {cat: row["classes"] for cat, row in breakdown.items()} == {"SAP": 13, "LIENG": 12, "DI": 6, "DIEM": 424}
    assert sum(row["profitable_combos"] for row in breakdown.values()) == data["summary"]["profitable_combinations"]


def test_evaluate_and_range_accept_opponent_model(client):
    payload = {"pot": 100000, "bet": 100000, "fold_equity": 0.35, "hand": "Ks Qh 3d", "opponent_model": "range"}
    evaluated = client.post("/api/evaluate", json=payload).get_json()
    assert evaluated["recommended_action"] == "CHECK/FOLD"
    assert evaluated["opponent_model"] == "range"

    random_range = client.post("/api/range", json={**payload, "opponent_model": "random"}).get_json()
    calling_range = client.post("/api/range", json=payload).get_json()
    assert calling_range["range_coverage_percent"] < random_range["range_coverage_percent"]
```

**How it works**

- `test_solve_category_breakdown` pins the per-category totals to the numbers proven in chapter 6
  (52 / 768 / 144 / 21,136), plus a **consistency check**: the categories' profitable combos must add up to
  the overall total. That test would have caught the old frontend bug immediately.
- `{**payload, "opponent_model": "random"}` copies a dict and overrides one key (**dict unpacking**).
- The last test checks a **relationship** instead of exact numbers: range-model coverage must be lower
  than random-model coverage (54.57% vs 84.65%).

The last group of tests pins down the two fixes of this chapter: the **break-even fields** and the
**validation of `/api/analyze`**.

📄 **File:** `backend/tests/test_api.py` — *add to the end*

```python


def test_break_even_fields_random_model(client):
    """Random model: the exact closed-form break-even, plus the 1%-grid point where raising stays +EV."""
    payload = {"pot": 100000, "bet_size": 50000, "fold_equity": 0.05, "hand": "2s 3h 5d"}
    hand_eval = client.post("/api/solve", json=payload).get_json()["hand_evaluation"]
    # S = 0.0024 * 200k - 50k = -49,520  ->  f = 49,520 / 149,520 = 0.3312; first +EV grid point is 0.34
    assert hand_eval["break_even_fold_equity"] == 0.3312
    assert hand_eval["profitable_from_fold_equity"] == 0.34


def test_evaluate_reports_both_break_even_fields(client):
    payload = {"pot": 100000, "bet": 100000, "fold_equity": 0.35, "hand": "Ks Qh 3d", "opponent_model": "range"}
    evaluated = client.post("/api/evaluate", json=payload).get_json()
    assert evaluated["break_even_fold_equity"] is None
    assert evaluated["profitable_from_fold_equity"] == 0.51


def test_analyze_rejects_non_numeric_pot(client):
    res = client.post("/api/analyze", json={"pot": "abc"})
    assert res.status_code == 400
    assert "pot" in res.get_json()["error"]


def test_analyze_rejects_unknown_opponent_model(client):
    res = client.post("/api/analyze", json={"pot": 100000, "bet_size": 50000, "opponent_model": "psychic"})
    assert res.status_code == 400


@pytest.mark.parametrize("hand_evaluation", [{"ev": "lots", "showdown_equity": 0.5}, ["not", "a", "dict"]])
def test_analyze_rejects_malformed_hand_evaluation(client, hand_evaluation):
    res = client.post("/api/analyze", json={"pot": 100000, "bet_size": 50000, "hand_evaluation": hand_evaluation})
    assert res.status_code == 400
    assert "hand_evaluation" in res.get_json()["error"]
```

**How it works**

- `test_break_even_fields_random_model` derives both values **by hand** (the comment shows the
  arithmetic from chapter 10), so it can't be fooled by a bug shared between the code and the test.
- The three analyze tests each name a crash the first version had: a text pot, an unknown model, and a
  malformed `hand_evaluation` (a text EV, or a list instead of an object, via `parametrize`). Each must be
  a **400 with a message that names the bad field**, never a 500.

---

## ✅ Checkpoint

Stop the dev server if it's running (Ctrl-C), then:

```bash
python -m pytest -q
```

Expected output (64 engine tests + 6 CLI tests + 17 API tests):

```
........................................................................ [ 82%]
...............                                                          [100%]
87 passed in 2.40s
```

Then start the server with `python app.py` and check the evaluate endpoint with curl:

```bash
curl -s -X POST http://127.0.0.1:5000/api/evaluate -H "Content-Type: application/json" \
  -d '{"pot": 100000, "bet": 100000, "fold_equity": 0.35, "hand": "Ks Qh 3d", "opponent_model": "range"}'
```

```json
{"bet":100000.0,"break_even_fold_equity":null,"canonical_id":"K-Q-3","category":"DIEM","equity_vs_random":0.36,"ev":-27894.0,"fold_equity":0.35,"hand":"Ks Qh 3d","is_profitable":false,"opponent_model":"range","pot":100000.0,"profitable_from_fold_equity":0.51,"recommended_action":"CHECK/FOLD","showdown_equity":0.0108}
```

> 💡 The project's `README.md` documents every endpoint, both opponent models and both break-even
> fields. It was corrected together with these fixes; earlier it still showed first-version examples such
> as `"hand": "A♠ K♥ Q♦"`. When docs and code disagree, trust the running code and the tests, then fix
> the docs.

Commit:

```bash
git add . && git commit -m "feat: Flask REST API with opponent models and LLM commentary"
```

## Recap

- An HTTP API = routes (`@app.route`) that read JSON (`request.get_json`) and return JSON (`jsonify`) plus
  a status code.
- **Validate once:** `_parse_game_params` builds a frozen `GameParams` or raises `InvalidGameParamsError`;
  one `@app.errorhandler` turns that into a 400 for every endpoint.
- `_equity_function` returns a closure, so one `_evaluate_hand` serves both opponent models, producing EV
  and profit zones; `_break_even_fields` reports an exact break-even (random model only, else `null`) and
  `profitable_from_fold_equity` (both models).
- The backend computes `category_breakdown` from the data, so the frontend no longer guesses.
- **CORS** lets the browser page on port 5173 read responses from port 5000. Secrets come from
  **environment variables**; external calls always have a **timeout**; offline fallbacks keep features working.
- ✅ Fixed since the first version: duplicated validation, missing endpoints in `/`, guessed category
  numbers, `/api/analyze` crashing on bad input, one field with two meanings, a test that could hit the
  internet.
- ⚠️ Still open: module-level globals, inconsistent response field names, hard-coded LLM model name.

**Next:** [14 — Testing and performance](14-testing-and-performance.md)
