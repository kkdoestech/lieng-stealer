# 12 — The Flask Web API

> **Goal:** put the engine behind a web API, so a web page (or any program) can send a game situation as
> JSON and get the decision back as JSON.
> **You will build:** `backend/app.py` (6 endpoints) and `backend/tests/test_api.py` (6 tests).
> **Time:** ~2.5 hours.
> **Prerequisites:** [11](12-cli.md). Flask is already installed (chapter 2).

---

## The big picture

The CLI works for someone sitting at the terminal. A browser can't run Python, but it **can** send HTTP
requests. So we wrap the same engine in a small web server:

```
 Browser (React, ch 14–15)                         Flask server: backend/app.py  (port 5000)
 ─────────────────────────                         ─────────────────────────────────────────
 fetch("POST /api/solve",                    ┌──►  @app.route("/api/solve")
       {"pot":100000, "bet_size":50000,      │       1. read JSON body
        "fold_equity":0.35,                  │       2. validate numbers  ──► 400 if bad
        "hand":"As Kh Qd"})  ────────────────┘       3. Hand.from_str     ──► 400 if bad hand
                                                     4. WinRateDB + ev.py + RangeFinder   (engine, unchanged)
 ◄──────────────── 200 OK  {"summary": {...},        5. jsonify(result)
                            "hand_evaluation": {...},
                            "top_hands": [...]}
```

| Method & path | Purpose |
|---|---|
| `GET /` | service info |
| `GET /health` | is the database loaded? |
| `POST /api/solve` | full range + optional single-hand decision (what the web page uses) |
| `POST /api/evaluate` | single-hand decision only |
| `POST /api/range` | range summary only |
| `POST /api/analyze` | strategy commentary in Vietnamese, from an LLM (or a built-in fallback) |

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

## Step 12.1 — Docstring and imports

📄 **File:** `backend/app.py` — *create this file*

```python
"""Liêng Stealer - Flask REST API Backend.

Provides RESTful endpoints for game-theoretic range solving, single-hand valuation,
and AI-powered strategic commentary via OpenRouter LLM.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

from src.db import WinRateDB
from src.evaluator import Hand
from src.exceptions import LiengError
from src.ev import calculate_break_even_fold_equity, evaluate_action
from src.hands import to_canonical
from src.range_finder import RangeFinder
```

Note the location: `backend/app.py`, **next to** `src/`, not inside it. Run from `backend/`, the import
`from src.db import WinRateDB` works exactly as in the tests.

---

## Step 12.2 — Create the app, enable CORS, load the database

📄 **File:** `backend/app.py` — *add to the end*

```python

app = Flask(__name__)
# Explicitly enable CORS for all origins on /api/*, /, and /health
CORS(app, resources={r"/api/*": {"origins": "*"}, r"/": {"origins": "*"}, r"/health": {"origins": "*"}})

# Initialize WinRateDB at startup
DB_PATH = Path(__file__).resolve().parent / "data" / "winrates.json"
win_rate_db = WinRateDB()
if DB_PATH.is_file():
    win_rate_db.load(DB_PATH)
range_finder = RangeFinder(win_rate_db)
```

**How it works**

- `Flask(__name__)` creates the application. `__name__` helps Flask find files relative to this module.
- `CORS(app, resources=...)` allows **any** origin (`"*"`) to call `/api/*`, `/` and `/health`. Fine for a
  public, read-only calculator. An API with user accounts would list specific origins instead.
- **Absolute path:** `Path(__file__).resolve().parent` is the folder containing `app.py`, so `DB_PATH`
  is correct no matter which folder the server is started from. (This is the explicit style suggested in
  chapter 8's pitfall.)
- The database is loaded **once, when the module is imported**, and shared by all requests. Loading per
  request would read an 83 KB file every time.

> ⚠️ **Pitfall: module-level state.** `win_rate_db` and `range_finder` are global variables created at
> import time, which `AGENTS.md` forbids ("no global mutable state"). If the file is missing,
> `RangeFinder(...)` silently tries `load()` with the default path (chapter 10 pitfall) and the import
> itself crashes. Flask's recommended alternative is an **application factory**:
>
> ```python
> def create_app(db_path: Path) -> Flask:
>     app = Flask(__name__)
>     db = WinRateDB(db_path)          # fails loudly if missing
>     finder = RangeFinder(db)
>     # ... register routes that use db/finder (via closures or app.extensions) ...
>     return app
> ```
>
> Then tests can build an app with a small test database, and nothing happens on import.

---

## Step 12.3 — The two simplest endpoints

📄 **File:** `backend/app.py` — *add to the end*

```python


@app.route("/", methods=["GET"])
def root() -> Any:
    """Root endpoint providing service metadata."""
    return jsonify({
        "service": "Lieng Stealer API",
        "status": "online",
        "endpoints": ["/health", "/api/solve", "/api/analyze"],
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

> 💡 The root endpoint lists only 3 of the 6 endpoints (`/api/evaluate` and `/api/range` are missing).
> Hand-maintained lists drift. Flask can list routes for you: `[r.rule for r in app.url_map.iter_rules()]`.

🧪 **Mini-check.** Start the server (from `backend/`, venv active):

```bash
flask --app app run
```

`--app app` tells Flask to load the `app` object from `app.py`. You'll see a start-up message ending
with `Running on http://127.0.0.1:5000`. Leave it running and open a **second terminal**:

```bash
curl -s http://127.0.0.1:5000/health
```

Expected output:

```json
{"classes_loaded":455,"database_loaded":true,"status":"healthy","version":"1.0.0"}
```

Stop the server with Ctrl-C. After editing `app.py`, restart it to load your changes (or start it with
`flask --app app run --debug`, which reloads automatically. Only ever use `--debug` on your own
machine). In Step 12.10 we'll also make `python app.py` start the server.

---

## Step 12.4 — `/api/solve`, part 1: read and validate the numbers

`/api/solve` is the endpoint the web page uses. It's long, so we build it in three slices.

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
    """
    data = request.get_json(silent=True) or {}

    try:
        pot = float(data.get("pot", 100000.0))
        bet_size = float(data.get("bet_size", 50000.0))
        fold_equity = float(data.get("fold_equity", 0.35))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid numerical parameters for pot, bet_size, or fold_equity."}), 400

    if pot <= 0 or bet_size <= 0:
        return jsonify({"error": "Pot and bet_size must be strictly greater than zero."}), 400
    if not (0.0 <= fold_equity <= 1.0):
        return jsonify({"error": "Fold equity must be between 0.0 and 1.0."}), 400
```

**How it works**

- `request.get_json(silent=True)` parses the body as JSON. With `silent=True` it returns `None` instead
  of raising if the body is missing or invalid; `or {}` then gives an empty dict, so missing fields fall
  back to defaults.
- **Never trust input from the network.** A client might send `"pot": "abc"` (→ `ValueError` in
  `float`), `"pot": null` (→ `TypeError`), or `-100`. Each case gets a **400** with a message that tells
  the client what to fix, instead of a crash (500).
- These checks duplicate `calculate_ev`'s guard clauses on purpose: the API turns bad input into
  *friendly* errors before the engine raises a `ValueError`.

---

## Step 12.5 — `/api/solve`, part 2: the optional hand

📄 **File:** `backend/app.py` — *add to the end*

```python

    hand_input = data.get("hand")
    hand_eval_result = None

    if hand_input and isinstance(hand_input, str) and hand_input.strip():
        try:
            player_hand = Hand.from_str(hand_input.strip())
            stats = win_rate_db.get_by_cards(player_hand.cards)
            ev_res = evaluate_action(pot, bet_size, fold_equity, stats.equity)
            canonical = to_canonical(player_hand.cards)
            hand_eval_result = {
                "hand": str(player_hand),
                "score_name": str(player_hand.score),
                "category": stats.category.name,
                "category_name": stats.category.display_name,
                "canonical_id": canonical.canonical_id,
                "showdown_equity": stats.equity,
                "ev": ev_res.ev,
                "break_even_fold_equity": ev_res.break_even_fold_equity,
                "is_profitable": ev_res.is_profitable,
                "decision": "RAISE" if ev_res.is_profitable else "CHECK/FOLD",
            }
        except LiengError as err:
            return jsonify({"error": f"Invalid hand: {err}"}), 400
```

**How it works**

- The hand is optional. We only evaluate it if it's a non-empty string.
- The engine pipeline is the same four steps as the CLI (chapter 11): text → `Hand` → `HandStats` →
  `EVResult`. Then we turn the objects into a plain dict, because JSON can't hold Python objects or enums:
  `.name` gives `"LIENG"`, `str(...)` gives `"Liêng Q-K-A"`.
- **`except LiengError`**: here the custom exception family pays off. Bad rank, bad suit, wrong number of
  cards, duplicate cards: one line turns them all into a 400 with the engine's own message.

---

## Step 12.6 — `/api/solve`, part 3: the range and the response

📄 **File:** `backend/app.py` — *add to the end*

```python

    # Solve full range
    records = range_finder.solve_range(pot, bet_size, fold_equity)
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
        },
        "hand_evaluation": hand_eval_result,
        "top_hands": top_hands,
    })
```

**How it works**

- Same calculations as `run_solver` in the CLI, but the result is **data** (a JSON document), not text.
  The API doesn't decide how things look; the frontend does. That's the separation between backend and
  frontend.
- Only the **top 30** records are sent, to keep the response small. The summary carries the totals.
- `hand_evaluation` is `null` in JSON when no hand was sent.

> 💡 **A missed opportunity.** The response has totals but no **per-category** breakdown (how many Đĩ
> combos are profitable, etc.). The frontend needs exactly that for its category table and, lacking it,
> *guesses* (badly; see chapter 15). Adding `"categories": {...}` here, computed like the CLI's table,
> would fix the frontend properly.

🧪 **Mini-check** (restart the server first):

```bash
curl -s -X POST http://127.0.0.1:5000/api/solve \
  -H "Content-Type: application/json" \
  -d '{"pot": 100000, "bet_size": 50000, "fold_equity": 0.35, "hand": "As Kh Qd"}'
```

The response is long. The `hand_evaluation` part should be (Flask sorts keys alphabetically):

```json
{
  "break_even_fold_equity": 0.0,
  "canonical_id": "Q-K-A",
  "category": "LIENG",
  "category_name": "Liêng",
  "decision": "RAISE",
  "ev": 132097.0,
  "hand": "As Kh Qd",
  "is_profitable": true,
  "score_name": "Liêng Q-K-A",
  "showdown_equity": 0.9969
}
```

and the summary should include `"range_coverage_percent": 100.0`, `"threshold_hand": "4-3-3"` and
`"pure_bluff_break_even_fold_equity": 0.3333`. Now try a bad hand:

```bash
curl -s -i -X POST http://127.0.0.1:5000/api/solve -H "Content-Type: application/json" \
  -d '{"pot": 100000, "bet_size": 50000, "hand": "Xx Kh Qd"}'
```

```
HTTP/1.1 400 BAD REQUEST
...
{"error":"Invalid hand: Invalid rank 'X'. Must be 2-10, T, J, Q, K, or A."}
```

(`-i` makes curl print the status line and headers too.) If you use Windows PowerShell, `curl` may be
an alias for a different command; use `curl.exe`, or test with Python's `requests` instead.

---

## Step 12.7 — `/api/evaluate`: one hand only

📄 **File:** `backend/app.py` — *add to the end*

```python


@app.route("/api/evaluate", methods=["POST"])
def evaluate_api() -> Any:
    """Evaluate a single 3-card hand against current game parameters."""
    data = request.get_json(silent=True) or {}
    try:
        pot = float(data.get("pot", 100000.0))
        bet = float(data.get("bet", data.get("bet_size", 50000.0)))
        fold_equity = float(data.get("fold_equity", 0.35))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid numerical parameters for pot, bet, or fold_equity."}), 400

    if pot <= 0 or bet <= 0:
        return jsonify({"error": "Pot and bet must be strictly greater than zero."}), 400
    if not (0.0 <= fold_equity <= 1.0):
        return jsonify({"error": "Fold equity must be between 0.0 and 1.0."}), 400

    hand_input = data.get("hand")
    if not hand_input or not isinstance(hand_input, str) or not hand_input.strip():
        return jsonify({"error": "Field 'hand' is required."}), 400

    try:
        player_hand = Hand.from_str(hand_input.strip())
        stats = win_rate_db.get_by_cards(player_hand.cards)
        ev_res = evaluate_action(pot, bet, fold_equity, stats.equity)
        canonical = to_canonical(player_hand.cards)
        return jsonify({
            "hand": str(player_hand),
            "canonical_id": canonical.canonical_id,
            "category": stats.category.name,
            "pot": pot,
            "bet": bet,
            "fold_equity": fold_equity,
            "showdown_equity": stats.equity,
            "ev": ev_res.ev,
            "break_even_fold_equity": ev_res.break_even_fold_equity,
            "recommended_action": "RAISE" if ev_res.is_profitable else "CHECK/FOLD",
            "is_profitable": ev_res.is_profitable,
        }), 200
    except LiengError as err:
        return jsonify({"error": f"Invalid hand: {err}"}), 400
```

**How it works**

- Here `hand` is **required**: a missing hand is a 400, not "skip it".
- `data.get("bet", data.get("bet_size", 50000.0))` accepts **either** name, `bet` or `bet_size`,
  then falls back to the default.

> ⚠️ **Pitfall: copy-paste validation and inconsistent names.** The "parse three numbers and check
> their ranges" block appears **three times** (solve, evaluate, range). Copies drift apart: `/api/solve`
> only reads `bet_size`, the others accept `bet` too; the error messages differ; the response keys
> differ (`decision` vs `recommended_action`, `equity` vs `showdown_equity`). **Better:** one helper
> used by every endpoint:
>
> ```python
> def _parse_game_params(data: dict[str, Any]) -> tuple[float, float, float]:
>     """Return (pot, bet, fold_equity) or raise ValueError with a client-facing message."""
>     try:
>         pot = float(data.get("pot", 100000.0))
>         bet = float(data.get("bet", data.get("bet_size", 50000.0)))
>         fe = float(data.get("fold_equity", 0.35))
>     except (ValueError, TypeError):
>         raise ValueError("Invalid numerical parameters for pot, bet, or fold_equity.")
>     if pot <= 0 or bet <= 0:
>         raise ValueError("Pot and bet must be strictly greater than zero.")
>     if not 0.0 <= fe <= 1.0:
>         raise ValueError("Fold equity must be between 0.0 and 1.0.")
>     return pot, bet, fe
> ```
>
> Each endpoint then does `try: pot, bet, fe = _parse_game_params(data) except ValueError as err: return
> jsonify({"error": str(err)}), 400`.

---

## Step 12.8 — `/api/range`: range only

📄 **File:** `backend/app.py` — *add to the end*

```python


@app.route("/api/range", methods=["POST"])
def range_api() -> Any:
    """Scan and return full combinatorial range coverage and thresholds."""
    data = request.get_json(silent=True) or {}
    try:
        pot = float(data.get("pot", 100000.0))
        bet = float(data.get("bet", data.get("bet_size", 50000.0)))
        fold_equity = float(data.get("fold_equity", 0.35))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid numerical parameters for pot, bet, or fold_equity."}), 400

    if pot <= 0 or bet <= 0:
        return jsonify({"error": "Pot and bet must be strictly greater than zero."}), 400
    if not (0.0 <= fold_equity <= 1.0):
        return jsonify({"error": "Fold equity must be between 0.0 and 1.0."}), 400

    records = range_finder.solve_range(pot, bet, fold_equity)
    profitable = [r for r in records if r.is_raise_profitable]
    coverage = range_finder.calculate_range_coverage(profitable)
    be_bluff = calculate_break_even_fold_equity(pot, bet, win_rate_when_called=0.0)
    combos = sum(r.multiplicity for r in profitable)

    return jsonify({
        "pot": pot,
        "bet": bet,
        "fold_equity": fold_equity,
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
`TOTAL_COMBINATIONS` from `range_finder.py` would be better.)

---

## Step 12.9 — `/api/analyze`: commentary from an LLM, with a fallback

This endpoint asks a **Large Language Model** (an AI text generator, here Llama 3.1 via the OpenRouter
service) to write a short strategic analysis in Vietnamese. If no API key is configured, it builds
a rule-based text itself, so the feature always works.

### Part 1: read the inputs and build the prompt

📄 **File:** `backend/app.py` — *add to the end*

```python


@app.route("/api/analyze", methods=["POST"])
def analyze_api() -> Any:
    """Query OpenRouter LLM for strategic game-theoretic commentary."""
    data = request.get_json(silent=True) or {}

    pot = data.get("pot", 100000.0)
    bet_size = data.get("bet_size", 50000.0)
    fold_equity = data.get("fold_equity", 0.35)
    hand = data.get("hand", "None")
    hand_eval = data.get("hand_evaluation") or {}
    coverage = data.get("range_coverage_percent", 0.0)

    api_key = os.environ.get("OPENROUTER_API_KEY")

    prompt = (
        f"You are a World-Class Game Theory Expert and High-Stakes Vietnamese Liêng Solver.\n"
        f"Analyze this decision spot with precision and strategic depth in Vietnamese:\n\n"
        f"- Current Pot: {pot:,.0f} VND\n"
        f"- Bet / Raise Size: {bet_size:,.0f} VND\n"
        f"- Opponent Fold Equity: {float(fold_equity) * 100:.1f}%\n"
        f"- Total Range Coverage (Hands with EV > 0): {coverage}%\n"
    )

    if hand_eval:
        prompt += (
            f"- Hero's Hand: {hand_eval.get('hand')} ({hand_eval.get('score_name')})\n"
            f"- Showdown Equity: {float(hand_eval.get('showdown_equity', 0)) * 100:.1f}%\n"
            f"- Calculated EV: {float(hand_eval.get('ev', 0)):+,.0f} VND\n"
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
  `hand_evaluation`), so this endpoint doesn't recompute anything.
- A **prompt** is the text instruction given to the LLM. It contains the role ("You are a … Solver"),
  the facts (pot, EV, decision) and the desired output structure (three numbered sections). Putting the
  *computed* numbers in the prompt matters: LLMs are bad at arithmetic, so we do the maths and let the
  model only explain it.

> ⚠️ **Pitfall: no input validation here.** Unlike the other endpoints, these values are **not** converted
> or checked. Send `{"pot": "abc"}` and `f"{pot:,.0f}"` raises `ValueError` ("Unknown format code 'f'
> for object of type 'str'"), and Flask answers **500 Internal Server Error**. Try it:
>
> ```bash
> curl -s -i -X POST http://127.0.0.1:5000/api/analyze -H "Content-Type: application/json" -d '{"pot":"abc"}' | head -1
> ```
>
> ```
> HTTP/1.1 500 INTERNAL SERVER ERROR
> ```
>
> The `_parse_game_params` helper from Step 12.7 would fix this too.

### Part 2: the offline fallback

📄 **File:** `backend/app.py` — *add to the end*

```python

    if not api_key:
        # Fallback commentary when no OpenRouter API key is configured
        fallback_advice = (
            f"**[Phân Tích Chiến Thuật Hệ Thống (Offline Solver)]**\n\n"
            f"1. **Quyết định Toán học:** Với Pot = {pot:,.0f}, Cược = {bet_size:,.0f}, và Fold Equity = {float(fold_equity)*100:.1f}%, "
            f"ngưỡng hòa vốn cược hù (bluff) là {(bet_size / (pot + bet_size))*100:.1f}%. "
            f"Khoảng bài có lãi (EV > 0) chiếm **{coverage}%** toàn bộ thế bài có thể có.\n\n"
            f"2. **Hành động Khuyến nghị:** "
        )
        if hand_eval:
            decision = hand_eval.get("decision", "EVALUATE")
            ev = hand_eval.get("ev", 0)
            fallback_advice += (
                f"Hero cầm **{hand_eval.get('hand')}** ({hand_eval.get('score_name')}) "
                f"với xác suất thắng đối đầu {float(hand_eval.get('showdown_equity', 0))*100:.1f}%. "
                f"Kỳ vọng thu nhập (EV) đạt **{ev:+,.0f} VND**. "
                f"Khuyến nghị tối ưu: **{decision}**.\n\n"
                f"3. **GTO Insight:** "
                + ("Bài có EV dương rõ rệt nhờ cả showdown equity lẫn fold equity. Tố lớn để tối đa hóa lợi nhuận." if ev > 0
                   else "EV âm. Showdown equity quá thấp và đối thủ ít bỏ bài. Không nên mạo hiểm, hãy Bỏ bài (Fold) hoặc Theo nhẹ nếu có thể.")
            )
        else:
            fallback_advice += (
                f"Với tần suất đối thủ bỏ bài {float(fold_equity)*100:.1f}%, hãy ưu tiên nâng cược với các nhóm bài Sáp, Liêng, Đĩ "
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
- `bet_size / (pot + bet_size)` is the pure-bluff break-even `B / (P + B)` from chapter 9, written out
  by hand. Calling `calculate_break_even_fold_equity(pot, bet_size, 0.0)` would avoid a second copy of
  the formula.
- `"text" + ("A" if ev > 0 else "B")` picks one of two closing sentences.

### Part 3: calling OpenRouter

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

## Step 12.10 — Running the server directly

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
  be enabled on a public server (anyone could run code on it). For production, use gunicorn (chapter 16).

---

## Step 12.11 — The tests

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
    assert data["endpoints"] == ["/health", "/api/solve", "/api/analyze"]


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
  `tests/` is a package, so `app.py` is importable.)
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

📄 **File:** `backend/tests/test_api.py` — *add to the end*

```python


def test_analyze_endpoint(client):
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

> ⚠️ **Pitfall: a test that may call the internet.** If `OPENROUTER_API_KEY` is set in your shell,
> `test_analyze_endpoint` sends a **real** request to OpenRouter: slow, uses your quota, and fails
> offline or when the free model is unavailable (502 ≠ 200). Tests should never depend on external
> services. Fix it with pytest's `monkeypatch` fixture, which changes things only for one test:
>
> ```python
> def test_analyze_endpoint(client, monkeypatch):
>     monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)   # force the offline fallback
>     ...
> ```

---

## ✅ Checkpoint

Stop the dev server if it's running (Ctrl-C), then:

```bash
python -m pytest -q
```

Expected output (47 engine tests + 6 API tests):

```
.....................................................                    [100%]
53 passed in 1.50s
```

Then start the server with `python app.py` and check all three POST endpoints with curl, e.g.:

```bash
curl -s -X POST http://127.0.0.1:5000/api/evaluate -H "Content-Type: application/json" \
  -d '{"pot": 100000, "bet": 50000, "fold_equity": 0.35, "hand": "As Kh Qd"}'
```

```json
{"bet":50000.0,"break_even_fold_equity":0.0,"canonical_id":"Q-K-A","category":"LIENG","ev":132097.0,"fold_equity":0.35,"hand":"As Kh Qd","is_profitable":true,"pot":100000.0,"recommended_action":"RAISE","showdown_equity":0.9969}
```

> 💡 The project's `README.md` documents this response with `"hand": "A♠ K♥ Q♦"` and a break-even of
> `0.3333333333333333`. The real values are `"As Kh Qd"` and `0.3333` (rounded by `ev.py`). Trust the
> running code.

Commit:

```bash
git add . && git commit -m "feat: Flask REST API with LLM commentary"
```

## Recap

- An HTTP API = routes (`@app.route`) that read JSON (`request.get_json`) and return JSON (`jsonify`) plus
  a status code.
- **Validate everything** from the network: bad numbers → 400, bad hands (`LiengError`) → 400, failures of
  services we call → 502. Never let user input cause a 500.
- **CORS** lets the browser page on port 5173 read responses from port 5000.
- Secrets come from **environment variables**; external calls always have a **timeout**; offline fallbacks keep features working.
- Pitfalls: validation copied three times (and missing in `/api/analyze`); module-level globals; a test
  that can hit the internet; a hard-coded model name.

**Next:** [13 — Testing and performance](14-testing-and-performance.md)
