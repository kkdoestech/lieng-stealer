# Liêng Stealer · LIÊNG SCOPE

**An expected-value (EV) decision tool for _Liêng_, the Vietnamese three-card game.**
Given the pot, your bet, how often the opponent folds and your three cards, it tells you whether raising
(*Tố* / *Tất tay*) makes money in the long run, for your hand and for all 22,100 possible hands at once.

It ships as a Python engine with a command-line tool, a Flask JSON API, and a bilingual (English /
Vietnamese) React web app called **LIÊNG SCOPE**.

`Python 3.11+` · `Flask 3` · `React 19 + Vite 8` · `172 backend + 20 frontend tests` · `MIT license`

---

## Contents

- [What it does](#what-it-does)
- [Quick start](#quick-start)
- [How it works](#how-it-works)
- [Using it](#using-it): [web app](#web-app) · [command line](#command-line) · [HTTP API](#http-api)
- [Regenerating the data](#regenerating-the-data)
- [Project layout](#project-layout)
- [Testing](#testing)
- [Configuration and deployment](#configuration-and-deployment)
- [Limitations](#limitations)
- [Learning guide](#learning-guide)
- [Disclaimer and license](#disclaimer-and-license)

---

## What it does

- **Ranks every hand correctly.** Sáp > Liêng > Đĩ > Điểm, including the edge cases (A-2-3 is the lowest
  straight, Q-K-A the highest, K-A-2 is not a straight; any Đĩ beats 9 points).
- **Knows every hand's equity.** The win rate of all 455 hand types (all 22,100 hands, with suits
  ignored) against every possible opponent hand, computed **exactly** and stored in a small JSON file.
- **Models the opponent two ways.**
  - `random`: the opponent folds regardless of their cards.
  - `range`: the opponent folds their **weakest** hands, so you are called only by strong ones. Computed
    exactly, with card removal.
- **Computes the decision.** EV of raising, a break-even fold frequency, and every fold-frequency range in
  which raising is profitable.
- **Scans the whole range.** Which of the 22,100 hands are worth raising in this spot, per category.
- **Answers instantly.** The slow work (≈ 10 s) runs once, offline; each question is a lookup plus a
  little arithmetic (≈ 1–2 ms for all 455 hand types).

---

## Quick start

You need **Python 3.11+**, **Node.js 22.22+** (required by Vite 8 and the Vitest/jsdom test stack) and npm.

**1. Backend** (Flask API on port 5000):

```bash
git clone https://github.com/kkdoestech/lieng-stealer.git
cd lieng-stealer/backend
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt   # the API, the CLI, tests and linters (requirements.txt = server only)
python app.py
```

Check it: `curl -s http://127.0.0.1:5000/health` →
`{"classes_loaded":455,"database_loaded":true,"status":"healthy","version":"2.0.0"}`

**2. Frontend** (in a second terminal):

```bash
cd lieng-stealer/frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The page solves the default spot on load: pot 100,000 VND, bet 50,000,
the opponent folds 35%, hand `As Kh Qd`. In development the page calls `/api/...` on its own origin and
Vite forwards those requests to the backend.

**Or use the command line only** (no frontend needed):

```bash
cd backend
python -m src.cli --pot 100000 --bet 50000 --fold-equity 0.35 --hand "As Kh Qd"
```

The precomputed data (`backend/data/winrates.json`) is committed, so nothing needs to be generated first.

---

## How it works

### 1. Hand ranking

Every 3-card hand falls into exactly one category; a higher category always wins.

| Category | What it is | Order inside the category |
| :--- | :--- | :--- |
| **Sáp** | Three of a kind | 2-2-2 < … < A-A-A |
| **Liêng** | Three consecutive ranks, any suits | A-2-3 < 2-3-4 < … < J-Q-K < Q-K-A. **K-A-2 is not a Liêng.** |
| **Đĩ** | Three face cards (J, Q, K) that aren't a Sáp or a Liêng | e.g. J-Q-Q, K-K-Q. **Beats every Điểm hand, even 9 points.** |
| **Điểm** | Everything else | Points = sum of card values mod 10 (2–9 = face value, 10/J/Q/K = 0, A = 1); 9 is best, 0 (*Bù*) is worst |

Ties inside a category are broken by the cards (this is a house-rule choice; tables differ): higher Sáp
rank, higher straight, Đĩ by highest then middle card, and equal Điểm scores by the highest card (Ace
high), then the remaining cards. `evaluate_hand` turns a hand into a comparable score tuple, so one `>`
decides any showdown.

### 2. From 22,100 hands to 455 hand types

Suits never decide a showdown, so hands that differ only in suits are equivalent. C(52, 3) = **22,100**
hands collapse into C(15, 3) = **455 canonical hand types** (rank multisets). Each type has a
*multiplicity*: the number of real hands it stands for.

| Category | Types | Real hands | Hands per type |
| :--- | ---: | ---: | :--- |
| Sáp | 13 | 52 | 4 |
| Liêng | 12 | 768 | 64 |
| Đĩ | 6 | 144 | 24 |
| Điểm | 424 | 21,136 | 4, 24 or 64 |
| **Total** | **455** | **22,100** | |

### 3. Equity: how often a hand wins when called

- **Against a random hand** (`random` model): for each of the 455 types, remove its three cards from the
  deck and compare it with **every** possible opponent hand, all C(49, 3) = 18,424 of them. Equity =
  (wins + ½ ties) / 18,424. The results are stored in `backend/data/winrates.json` (≈ 83 KB) and loaded
  into a dictionary at start-up for O(1) lookups.
- **Against a calling range** (`range` model): an opponent who folds a fraction *f* of the time is assumed
  to fold their weakest hands, so a call comes from the strongest (1 − *f*) × 22,100 combinations.
  `CallingRangeModel` computes equity against exactly that range, including card removal (your cards
  can't be in the opponent's hand), using one prefix-sum table per hand type (built once in ≈ 50 ms).
  At *f* = 0 it reproduces `winrates.json` exactly.

`fold_equity` is the API's **single** opponent assumption. The calling range it implies,
`(1 − f) × 100%`, is reported back as `call_range_percent` (read-only, derived). The same engine powers
the single-hand answer and the 455-class table, so one request has exactly one equity per hand — the
verdict card and the table row cannot disagree.

The difference matters for medium hands: `K-Q-3` (3 points) wins **36%** against a random hand, but only
**1.1%** against an opponent who folds their weakest 35% and calls with the rest.

### 4. The decision: expected value

You bet *B* into a pot *P*. The opponent folds with probability *f*; if they call, you win the final pot
*P + 2B* with probability *e* (your equity):

```
EV = f × P  +  (1 − f) × (e × (P + 2B) − B)          raise if and only if EV > 0
```

- **Pure-bluff break-even:** with *e* = 0, raising pays when *f* > B / (P + B). For a 50,000 bet into
  100,000 that is **33.3%**. Above it, every hand is profitable to raise.
- **Under the `range` model, EV is not monotonic in *f*:** more folds also mean stronger callers. Example:
  `K-Q-3`, pot = bet = 100,000. Raising is +EV when the opponent folds **0–8%** (weak hands still call) or
  **51–100%** (folds alone pay for the bet), and −EV in between. The tool therefore reports every
  profitable **zone** of fold frequencies, scanned on a 1% grid.

---

## Using it

### Web app

Inputs on the left, results on the right.

- **Inputs:** pot and bet (with −/+ steppers and presets such as *100k* or *0.5x pot*), the opponent's fold
  frequency (slider), how the opponent folds (**Weakest hands** = `range`, the default; **At random** =
  `random`), and your hand (e.g. `As Kh Qd`, or one of the presets). The calling-range slider is a second
  view of the same assumption: it shows the strongest `(1 − f) × 100%` of hands and moving it moves the
  fold frequency, so the page always sends the API one opponent assumption.
- **Results:** the recommended action and EV; *where raising pays*, a bar showing the profitable fold
  ranges with a marker at your current estimate; range coverage, showdown equity, EV and bluff break-even;
  coverage by category; the most profitable hands; and optional **analysis notes** (see
  [`/api/analyze`](#http-api)). Clearing the hand keeps the range tables on screen and says so.
- **EN / VI** switch in the header; the choice is remembered in the browser. Numbers follow the language
  (`131,876` in English, `131.876` in Vietnamese).

The visual rules (colours, type, layout, copy) are in [`DESIGN.md`](DESIGN.md).

### Command line

From `backend/`:

```bash
python -m src.cli --pot 100000 --bet 100000 --fold-equity 0.35 --hand "Ks Qh 3d" --opponent-model range
```

It prints the game state, a range summary, a per-category table and the decision for your hand:

```
╭────────────────────────── HAND EVALUATION & ACTION ──────────────────────────╮
│ Hand Evaluated: Ks Qh 3d (3 điểm)                                            │
│ Canonical Class: K-Q-3 (Điểm)                                                │
│ Showdown Equity: 1.08%                                                       │
│ Expected Value (EV): -27,894                                                 │
│ Break-Even Fold Equity: n/a (range model)                                    │
│                                                                              │
│  >>> ACTION: CHECK / FOLD RECOMMENDED <<<                                    │
╰──────────────────────────────────────────────────────────────────────────────╯
```

| Option | Meaning | Default |
| :--- | :--- | :--- |
| `--pot` | Pot before your bet (VND) | 100000 |
| `--bet` | Your bet / raise | 50000 |
| `--fold-equity` (alias `--p-fold`) | Opponent fold probability, 0–1 | 0.35 |
| `--hand` | Your hand, e.g. `"As Kh Qd"` or `"As,Kh,Qd"` | none (range report only) |
| `--opponent-model` | `random` or `range` | `random` |
| `--db` | Path to the win-rate file | `backend/data/winrates.json`, wherever you run from |

Run it with no options (or only `--opponent-model`, which becomes the default answer) for an
**interactive** session. Every input is checked before anything is printed. Exit codes: **0** success,
**1** the win-rate file can't be loaded (or the solver's model is broken), **2** invalid input (`Invalid input: …` on stderr), **130** Ctrl-C.

**Card notation** (CLI and API): rank `2`–`10` (or `T`), `J`, `Q`, `K`, `A`, followed by a suit `s` `c`
`d` `h` (or `♠ ♣ ♦ ♥`); upper or lower case. Separate cards with spaces, commas or hyphens.

### HTTP API

Base URL `http://127.0.0.1:5000`. Requests and responses are JSON. Browsers may call the API only from the
origins in `CORS_ORIGINS` (by default the Vite dev server; see [Configuration](#configuration-and-deployment)).

| Method | Path | Purpose |
| :--- | :--- | :--- |
| `GET` | `/` | Service info and the list of endpoints |
| `GET` | `/health` | Status and number of hand types loaded |
| `POST` | `/api/solve` | Full range scan plus an optional single-hand decision (used by the web app) |
| `POST` | `/api/evaluate` | Single-hand decision (`hand` required) |
| `POST` | `/api/range` | Range scan only |
| `POST` | `/api/analyze` | Strategy notes in Vietnamese from an LLM, or a rule-based text when no API key is set. Rate-limited per client (default 10 per minute) |

**Common request fields** for the `POST` endpoints:

| Field | Type | Default | Rule |
| :--- | :--- | :--- | :--- |
| `pot` | number | 100000 | > 0 |
| `bet_size` (`bet` is still accepted) | number | 50000 | > 0 |
| `fold_equity` | number | 0.35 | 0–1; the single opponent assumption. Under `range` it also fixes the calling range, `(1 − f) × 100%` |
| `opponent_model` | `"random"` \| `"range"` | `"random"` | the web app sends `"range"` |
| `hand` | string | — | optional for `/api/solve`, required for `/api/evaluate` |

The body must be a JSON object, and numbers must be real, finite numbers (`"nan"`, `"inf"` and `true` are
rejected). Missing fields take the defaults above.

**Removed in 2.0.0:** `call_range_percent`. It encoded the same opponent assumption as `fold_equity`
(a caller holding the strongest 30% folds 70% of the time), so sending both let one answer be computed
from one value and the table from the other. The API now rejects it with `400` and tells the caller to
send `fold_equity = 1 - call_range_percent / 100`.

**Errors.** Every error, including unknown URLs, is JSON with a stable `code`:
`{"error": "A Liêng hand cannot have duplicate cards.", "code": "invalid_hand"}`.

| `code` | Status | When |
| :--- | :--- | :--- |
| `invalid_params` | 400 | A body that isn't valid JSON or isn't an object, a bad number, an unknown `opponent_model`, the removed `call_range_percent` field, a missing `hand` on `/api/evaluate` |
| `invalid_hand` | 400 | The hand text isn't three valid, different cards |
| `not_found` / `method_not_allowed` | 404 / 405 | Unknown URL / wrong HTTP method |
| `rate_limited` | 429 | Too many `/api/analyze` calls (the `Retry-After` header says when to try again) |
| `upstream_error` | 502 | The LLM service failed or sent something unexpected (details are logged, not returned) |
| `internal_error` | 500 | A bug; the server logs the traceback |

**One vocabulary.** The three solver endpoints use the same field names with the same meanings:
`bet_size`, `showdown_equity` (equity when called, under the chosen model), `decision` (`"RAISE"` or
`"CHECK/FOLD"`), `is_profitable`. The single-hand answer is the matching row of the 455-class table, so
`showdown_equity` and `ev` are identical in both places for the same hand. `call_range_percent` is a
derived readout of the fold frequency (`null` under `random`), and `sensitivity` stresses that one
assumption by ±10 percentage points, reporting the calling range each cell implies.

**No hand is not an error.** A cleared or absent `hand` on `/api/solve` or `/api/analyze` returns
`200` with `hand_evaluation: null` plus the full range. Only `/api/evaluate` requires a hand.

**When does raising pay?** Single-hand results contain:

| Field | Meaning |
| :--- | :--- |
| `showdown_equity` | Equity used by the chosen model; `equity_vs_random` is always included for comparison |
| `call_range_percent` | The calling range implied by `fold_equity`, `(1 − f) × 100`; `null` under `random` |
| `sensitivity` | Three stress cells (`f ∓ 0.10`), each reporting its EV, equity and implied calling range, plus `ROBUST_BET` / `ROBUST_NO_BET` / `ASSUMPTION_SENSITIVE` |
| `break_even_fold_equity` | Exact fold frequency where EV = 0 (`random` model). `null` under `range`, where no single break-even exists |
| `profitable_from_fold_equity` | First fold frequency (1% grid) from which raising stays +EV up to 100% |
| `profitable_fold_zones` | Every `[start, end]` interval where raising is +EV |

#### Example: `POST /api/solve`

```bash
curl -s -X POST http://127.0.0.1:5000/api/solve -H "Content-Type: application/json" \
  -d '{"pot": 100000, "bet_size": 100000, "fold_equity": 0.35, "hand": "Ks Qh 3d", "opponent_model": "range"}'
```

Response (shortened: `top_hands` has 30 entries and `category_breakdown` has 4):

```json
{
  "hand_evaluation": {
    "hand": "Ks Qh 3d",
    "canonical_id": "K-Q-3",
    "category": "DIEM",
    "category_name": "Điểm",
    "score_name": "3 điểm",
    "showdown_equity": 0.0108,
    "equity_vs_random": 0.3599924,
    "call_range_percent": 65.0,
    "ev": -27894.0,
    "break_even_fold_equity": null,
    "profitable_from_fold_equity": 0.51,
    "profitable_fold_zones": [[0.0, 0.08], [0.51, 1.0]],
    "sensitivity": {
      "fold_equity_range": [0.25, 0.45],
      "call_range_percent_range": [55.0, 75.0],
      "central_equity_when_called": 0.0108,
      "status": "ROBUST_NO_BET"
    },
    "is_profitable": false,
    "decision": "CHECK/FOLD"
  },
  "summary": {
    "pot": 100000.0,
    "bet_size": 100000.0,
    "fold_equity": 0.35,
    "opponent_model": "range",
    "call_range_percent": 65.0,
    "final_pot": 300000.0,
    "pure_bluff_break_even_fold_equity": 0.5,
    "total_canonical_classes": 455,
    "profitable_classes": 250,
    "total_combinations": 22100,
    "profitable_combinations": 12060,
    "range_coverage_percent": 54.57,
    "highest_ev_hand": "A-A-A",
    "highest_ev_value": 165000.0,
    "threshold_hand": "K-Q-4",
    "threshold_ev_value": 420.0,
    "category_breakdown": [
      {"category": "SAP", "classes": 13, "combos": 52, "profitable_combos": 52}
    ]
  },
  "top_hands": [
    {"canonical_id": "A-A-A", "category": "SAP", "showdown_equity": 1.0, "ev": 165000.0, "multiplicity": 4, "is_profitable": true, "decision": "RAISE"}
  ]
}
```

`threshold_hand` is the profitable hand type with the lowest EV (the last one before EV turns negative).

#### Example: `POST /api/evaluate`

```bash
curl -s -X POST http://127.0.0.1:5000/api/evaluate -H "Content-Type: application/json" \
  -d '{"pot": 100000, "bet_size": 50000, "fold_equity": 0.35, "hand": "As Kh Qd"}'
```

The game parameters plus exactly the `hand_evaluation` fields of `/api/solve`:

```json
{
  "pot": 100000.0,
  "bet_size": 50000.0,
  "fold_equity": 0.35,
  "opponent_model": "random",
  "hand": "As Kh Qd",
  "score_name": "Liêng Q-K-A",
  "canonical_id": "Q-K-A",
  "category": "LIENG",
  "category_name": "Liêng",
  "showdown_equity": 0.99693335,
  "equity_vs_random": 0.99693335,
  "call_range_percent": null,
  "ev": 132101.34,
  "break_even_fold_equity": 0.0,
  "profitable_from_fold_equity": 0.0,
  "profitable_fold_zones": [[0.0, 1.0]],
  "is_profitable": true,
  "decision": "RAISE"
}
```

`/api/range` returns the same fields as the `/api/solve` `summary` (including `category_breakdown`) plus
`top_hands`, in the same shape as above. `/api/analyze` takes the same fields as `/api/solve` (with an
optional `hand`), recomputes every number on the server, and returns `{"advice": "...", "model": "..."}`;
anything else in the body, such as a client-side `hand_evaluation`, is ignored.

---

## Regenerating the data

`backend/data/winrates.json` is committed. To rebuild it (from `backend/`):

```bash
python -m src.generator                 # exact enumeration (default): ≈ 10 s on one core
python -m src.generator --monte-carlo --samples 10000 --output data/winrates_mc.json
```

Exact enumeration is deterministic: the regenerated file is byte-for-byte identical to the committed one.
Monte Carlo is only for experiments; the tests expect the exact data. Other options: `--output` (default
`backend/data/winrates.json`, wherever you run from), `--workers` (default: number of CPU cores; use
`--workers 1` on a busy machine). The file is written atomically, so an interrupted run never leaves a
half-written database, and the loader rejects files that don't describe all 455 hand types.

---

## Project layout

```
lieng-stealer/
├── backend/
│   ├── app.py                  Flask API (validation, opponent models, LLM notes)
│   ├── Procfile                gunicorn start command for hosting platforms
│   ├── requirements.txt        runtime: Flask, flask-cors, Flask-Limiter, gunicorn, requests
│   ├── requirements-dev.txt    + pytest, rich (CLI), ruff, mypy
│   ├── pyproject.toml          ruff, mypy (strict) and pytest settings
│   ├── .env.example            every environment variable the API reads
│   ├── data/winrates.json      precomputed equity of all 455 hand types (exact)
│   ├── src/
│   │   ├── exceptions.py       LiengError hierarchy
│   │   ├── paths.py            default data path (independent of the current directory)
│   │   ├── evaluator.py        Card, Hand, HandScore, evaluate_hand (ranking rules)
│   │   ├── hands.py            22,100 hands → 455 canonical types, multiplicities
│   │   ├── generator.py        equity generator (exact or Monte Carlo, multi-process)
│   │   ├── db.py               WinRateDB: loads winrates.json for O(1) lookups
│   │   ├── calling_range.py    OpponentModel, CallingRangeModel (equity vs a calling range)
│   │   ├── ev.py               EV, break-even fold equity, profitable fold zones
│   │   ├── range_finder.py     the request's one equity source, EV of all 455 types, sorting, coverage
│   │   ├── sensitivity.py      the 3-point assumption stress grid behind `sensitivity`
│   │   └── cli.py              command-line interface
│   └── tests/                  pytest suite (205 tests)
├── frontend/
│   ├── index.html, vite.config.js, package.json, .oxlintrc.json
│   └── src/
│       ├── main.jsx, App.jsx   the web app
│       ├── solve-contract.json the UI's default request + expected numbers, read by both test suites
│       ├── i18n.js             English and Vietnamese UI text
│       ├── format.js           money and fold-zone formatting
│       ├── index.css, App.css  colour tokens and layout
│       └── *.test.js(x)        Vitest tests (24 tests)
├── .github/workflows/ci.yml    CI: backend, frontend and course checks on every push
├── learning/                   guided tour of the codebase: 18 lessons, start at COURSE.md
├── AGENTS.md                   engineering spec: rules, data model, maths, performance budgets
├── DESIGN.md                   web UI spec
├── SKILLS.md                   command cheat-sheet
├── BLOG.md, EXPERIMENT.md      project write-up and report (Vietnamese)
└── LICENSE
```

---

## Testing

From the repository root:

```bash
(cd backend && python -m pytest -q)                          # 172 passed
(cd backend && ruff check . && mypy)                         # lint + strict type check: 0 issues
(cd frontend && npm test)                                    # 20 passed (Vitest)
(cd frontend && npm run lint && npm run build)               # 0 warnings; production build in dist/
python3 learning/verify_course.py                            # the course still matches the code
```

GitHub Actions runs the same checks on every push (`.github/workflows/ci.yml`). Timing tests scale their
budgets by `PERF_BUDGET_FACTOR` (CI sets 3, because shared runners are slower).

| Test file | Tests | Covers |
| :--- | ---: | :--- |
| `test_evaluator.py` | 27 | Card parsing, category order, straight edge cases, Đĩ rules, points mod 10, tie-break house rules, hashing, the 1 µs budget |
| `test_hands.py` | 8 | 455 types, multiplicities summing to 22,100, suit invariance, duplicate cards, ordering |
| `test_exceptions.py` | 9 | The exception hierarchy callers rely on |
| `test_generator.py` | 15 | Exact equities, rate invariants, Monte Carlo convergence, data-file schema, CLI flags, atomic write, file permissions, private RNG |
| `test_db.py` | 13 | Loading, lookup latency, error handling, validation of malformed or incomplete files |
| `test_calling_range.py` | 13 | Card removal, exact match with `winrates.json` at 0% folds, monotonicity, one implementation for single queries and the full table, latency, model invariants |
| `test_ev.py` | 15 | EV boundaries, bluffing, break-even, profitable fold zones, strong hands |
| `test_range_finder.py` | 13 | Range scan, coverage, opponent models, tie ordering, one answer per hand (identity), category breakdown |
| `test_cli.py` | 12 | Decisions per model, interactive mode, exit codes, validation before output, plain-text fallback |
| `test_api.py` | 70 | Every endpoint, both models, one answer per hand, the shared UI contract, the removed field, blank hands, JSON errors, `/api/analyze` (OpenRouter mocked), rate limit and `Retry-After`, proxy handling, CORS, settings |
| `test_dynamic_scenarios.py` | 6 | End-to-end player stories (value raise, junk fold, pure bluff, coverage sweep, both models) |
| frontend `App.test.jsx` | 18 | Rendering, the shared contract body, the linked sliders, the blank-hand range view, error messages, stale results cleared, language toggle, steppers, request cancelling |
| frontend `format.test.js`, `i18n.test.js` | 6 | Locale-aware money formatting, zone formatting, EN/VI dictionary parity |

The tests never call the internet: the LLM calls are mocked or use the offline fallback.

---

## Configuration and deployment

All backend variables are listed in [`backend/.env.example`](backend/.env.example); every one is optional.

| Variable | Used by | Purpose |
| :--- | :--- | :--- |
| `OPENROUTER_API_KEY` | backend | Enables LLM notes in `/api/analyze`. Without it, a rule-based text is returned. |
| `OPENROUTER_MODEL`, `OPENROUTER_TIMEOUT` | backend | LLM model (default `meta-llama/llama-3.1-8b-instruct:free`) and timeout in seconds (default 15) |
| `CORS_ORIGINS` | backend | Comma-separated browser origins allowed to call the API (default `http://localhost:5173,http://127.0.0.1:5173`). Set it to your frontend's URL in production. |
| `ANALYZE_RATE_LIMIT`, `RATELIMIT_STORAGE_URI` | backend | Per-client limit for `/api/analyze` (default `10 per minute`) and where counts live (default `memory://`, which counts per worker; use e.g. `redis://…` for one shared limit) |
| `RATELIMIT_ENABLED` | backend | `false` turns the limiter off (default `true`; test apps turn it off themselves) |
| `PROXY_FIX_X_FOR` | backend | How many reverse proxies to trust for `X-Forwarded-For` (default `0`). Behind a hosting proxy set it to `1`, or every visitor shares one rate-limit budget. |
| `HOST`, `PORT` | backend | Address for `python app.py` (default `127.0.0.1:5000`; `HOST=0.0.0.0` shares it on your network). The `Procfile` uses `$PORT`. |
| `VITE_API_URL` | frontend, **at build time** | Backend URL. Without it the page calls `/api` on its own origin. It ends up in the public JavaScript bundle, so never put secrets in it. |

`.env` files are git-ignored, so real keys stay out of the repository. Nothing loads `.env` automatically:
export the variables in your shell (for example `set -a; . backend/.env; set +a`) or set them in your
hosting platform's settings.

| Part | Example platform | Build | Run |
| :--- | :--- | :--- | :--- |
| Backend | Render, Railway | `pip install -r requirements.txt` | `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --worker-class gthread --threads 4 --timeout 60 --preload` (from `backend/Procfile`) |
| Frontend | Vercel, Netlify | `npm run build` with `VITE_API_URL` set | serve `frontend/dist/` as static files |

---

## Limitations

- **EV, not an equilibrium.** The tool computes the expected value of one raise under the assumptions you
  give it. It does not solve for a game-theory-optimal strategy.
- **One betting round, two players:** the opponent can only fold or call; no re-raises, no multi-way pots.
- **The fold frequency is your estimate.** The `range` model also assumes the opponent folds strictly from
  the weakest hand up; real players sit somewhere between `range` and `random`.
- **Tie-breaking rules** follow one common convention (see [Hand ranking](#1-hand-ranking)); house rules vary.
- **Profitable zones are on a 1% grid**, so a zone boundary can differ from the exact value by up to one
  point (e.g. 0.51 instead of 0.50).

---

## Learning guide

[`learning/COURSE.md`](learning/COURSE.md) is a guided tour of this codebase: 18 lessons that walk through
every file, from the card evaluator to the React page, explaining what each piece does and why, with
runnable examples, exercises and quizzes. `python3 learning/verify_course.py` checks that the lessons still
match the code.

---

## Disclaimer and license

This project is for learning computer science, probability and software engineering. It is not a
gambling service, does not handle real money, and must not be used in breach of any law or any
platform's terms of service.

Released under the [MIT License](LICENSE).
