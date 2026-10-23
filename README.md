# LIÊNG SCOPE | Real-Time GTO Decision Solver

`[ Python 3.11 ]` `[ Flask ]` `[ React 19 ]` `[ Vite ]` `[ 93 Backend + 6 Frontend Tests Passing ]` `[ Zero External Solvers ]`

> High-density combinatorial evaluator and expected value engine for imperfect-information 3-card poker variants.

---

## 1. System Architecture

LIÊNG SCOPE is an offline-computed, $O(1)$ real-time Game Theory Optimal (GTO) decision support engine for **Liêng** (a Vietnamese 3-card imperfect information card game). The engine compresses the full combinatorial state space down to suit-invariant canonical equivalence classes, enabling sub-millisecond expected value calculations and range scanning.

```
+---------------------------------------------------------------------------------------------------+
|                                  LIENG SCOPE ENGINE ARCHITECTURE                                  |
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
|  [ 52-Card French Deck ]                                                                          |
|            |                                                                                      |
|            v                                                                                      |
|  [ Combinatorial Generator ]  --->  C(52, 3) = 22,100 Distinct Combinations                       |
|            |                                                                                      |
|            v                                                                                      |
|  [ Canonical State Compression ] -> 455 Equivalence Classes (Suits Invariant)                     |
|                                     - Sáp:  13 classes (52 combos)                                |
|                                     - Liêng: 12 classes (768 combos)                              |
|                                     - Đĩ:    6 classes (144 combos)                               |
|                                     - Điểm: 424 classes (21,136 combos)                           |
|            |                                                                                      |
|            v                                                                                      |
|  [ Monte Carlo Simulation / Exact Enumeration ]                                                   |
|            |                                                                                      |
|            v                                                                                      |
|  [ In-Memory Hash Database ]  --->  backend/data/winrates.json (< 100 KB, O(1) Lookup)            |
|            |                                                                                      |
|            +-------------------------------+                                                      |
|            |                               |                                                      |
|            v                               v                                                      |
|  [ Range Finder Engine ]         [ Single Hand Evaluator ]                                        |
|  - Full Range Coverage           - Showdown Equity vs Spectrum                                    |
|  - Pure Bluff Threshold (alpha)  - EV Tree Branching & Decision                                   |
|            |                               |                                                      |
|            +---------------+---------------+                                                      |
|                            |                                                                      |
|                            v                                                                      |
|               [ Flask REST API Backend ]                                                          |
|               - Port 5000 / JSON Serialization                                                    |
|               - Endpoints: /health, /api/evaluate, /api/range, /api/solve, /api/analyze           |
|                            |                                                                      |
|                            v                                                                      |
|            [ React Web UI ]                                                                       |
|            - React 19 + Vite SPA, English / Vietnamese UI                                         |
|            - Plain dark UI (Ayu Dark colors, system font)                                         |
|            - Verdict, Profit Map, Summary, Category Matrix & Top Hands                            |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. Mathematical Model & Decision Boundary

### 2.1 Expected Value (EV) Formulation

When evaluating whether to **Raise / Tố** (or **Go All-In / Tất tay**) with bet size $B$ into an existing dead money pot $P$:

$$\text{EV} = \big[ P(\text{Fold}) \times P \big] + \big[ 1 - P(\text{Fold}) \big] \times \Big[ \big( P(\text{Win} \mid \text{Call}) \times \text{FinalPot} \big) - B \Big]$$

Where:
* $P$: Current Pot before Hero's wager (Dead Money).
* $B$: Additional Bet / Raise amount committed by Hero.
* $P(\text{Fold})$: Opponent fold equity (probability that villain folds to the bet).
* $P(\text{Win} \mid \text{Call})$: Hero showdown equity when called. Two opponent models are supported (`opponent_model` in the API):
  * `range`: the opponent folds their **weakest** hands, so a call comes from the strongest $1 - P(\text{Fold})$ of all 22,100 combos. Equity is computed exactly against that calling range, including card removal (`src/calling_range.py`).
  * `random` (API default): the opponent folds regardless of strength, so equity is against a random hand (precomputed $O(1)$ win rates in `data/winrates.json`).
* $\text{FinalPot} = P + B + C_{\text{opp}}$: The showdown pot if villain calls (standard heads-up $C_{\text{opp}} = B$, resulting in $\text{FinalPot} = P + 2B$).

**Decision Rule**:
$$\text{Action} = \begin{cases} \text{RAISE / ALL-IN} & \text{if } \text{EV} > 0 \\ \text{CHECK / FOLD} & \text{if } \text{EV} \le 0 \end{cases}$$

---

### 2.2 Bluff Tipping-Point Logic (Air Hands with Zero Points)

A central property of imperfect-information game theory is that a bet can be profitable even with zero showdown equity ($P(\text{Win} \mid \text{Call}) = 0$, e.g., "0 Điểm Bù" holdings such as `2s 3h 5d`).

When showdown equity is zero, the EV equation reduces to:

$$\text{EV}_{\text{bluff}} = \big[ P(\text{Fold}) \times P \big] - \big[ (1 - P(\text{Fold})) \times B \big]$$

Setting $\text{EV}_{\text{bluff}} > 0$:

$$P(\text{Fold}) \times P > (1 - P(\text{Fold})) \times B$$
$$P(\text{Fold}) \times (P + B) > B$$
$$P(\text{Fold}) > \frac{B}{P + B} = \alpha$$

Where $\alpha = \frac{\text{Bet}}{\text{Pot} + \text{Bet}}$ is the **Pure Bluff Break-Even Fold Equity**.

> **Example**:
> In a $100,000\text{ VND}$ pot with a $50,000\text{ VND}$ bet:
> $$\alpha = \frac{50,000}{100,000 + 50,000} = \frac{50,000}{150,000} = 33.33\%$$
> If the opponent folds more than $33.33\%$ of the time ($P(\text{Fold}) > 0.3333$), shoving with absolute air generates strictly positive long-run EV ($+EV$), regardless of Hero's hand strength.

---

## 3. Combinatorial State-Space Compression

Standard French deck Liêng possesses $\binom{52}{3} = 22,100$ initial 3-card combinations. Pre-showdown hand strength is suit-invariant, reducing the combinatorial space into **455 canonical equivalence classes**:

$$\binom{13 + 3 - 1}{3} = \binom{15}{3} = 455 \text{ canonical hand types}$$

### Hierarchy & Category Distribution

| Category | Rank Order | Description | Canonical Classes | Total Combinations | Multiplicity per Class |
| :--- | :--- | :--- | :---: | :---: | :---: |
| **Sáp** (Category 4) | $2\text{-}2\text{-}2 < \dots < A\text{-}A\text{-}A$ | Three of a Kind | 13 | 52 | $\binom{4}{3} = 4$ |
| **Liêng** (Category 3) | $A\text{-}2\text{-}3 < \dots < Q\text{-}K\text{-}A$ | 3-Card Straight (No wraparound $K\text{-}A\text{-}2$) | 12 | 768 | $4^3 = 64$ |
| **Đĩ** (Category 2) | $J\text{-}Q\text{-}K$ excl. Sáp/Liêng | 3 Face Cards ($J, Q, K$) | 6 | 144 | $\binom{4}{2} \times 4 = 24$ |
| **Điểm** (Category 1) | $0 \dots 9 \pmod{10}$ | Point Total Modulo 10 ($A=1, 10/J/Q/K=0$) | 424 | 21,136 | Varies |
| **TOTAL** | | | **455** | **22,100** | |

---

## 4. Repository Layout

```
lieng-stealer/
├── DESIGN.md                  # Web UI rules: colors, type, controls, layout, copy
├── AGENTS.md                  # Architectural guardrails, latency budgets & constraints
├── README.md                  # Project documentation & mathematical specification
├── LICENSE                    # MIT License
├── learning/                  # Step-by-step guide to rebuild this project from scratch
│
├── backend/                   # Python 3.11 GTO Solver Service
│   ├── app.py                 # Flask REST API with CORS and OpenRouter integration
│   ├── Procfile               # Deployment target definition (Railway / Render)
│   ├── requirements.txt       # Production dependencies (Flask, requests, flask-cors)
│   ├── data/
│   │   └── winrates.json      # Precomputed in-memory hash table (< 100 KB)
│   ├── src/
│   │   ├── __init__.py
│   │   ├── evaluator.py       # Pure functional 3-card hand evaluator & comparator
│   │   ├── hands.py           # Card & Hand immutable models, canonical compression
│   │   ├── ev.py              # Pure Expected Value, break-even equity & profitable fold zones
│   │   ├── calling_range.py   # Opponent models: exact equity vs the opponent's calling range
│   │   ├── range_finder.py    # Full-range combinatorial scanner & coverage resolver
│   │   ├── db.py              # Thread-safe in-memory win rate database
│   │   ├── generator.py       # Combinatorial generator for Monte Carlo / enumeration
│   │   ├── cli.py             # Terminal CLI (both opponent models, interactive mode)
│   │   └── exceptions.py      # Domain exception hierarchy (LiengError)
│   └── tests/
│       ├── test_evaluator.py  # 18 unit tests for strict hand hierarchies & edge cases
│       ├── test_hands.py      # Tests for card parsing and canonical mapping
│       ├── test_ev.py         # Tests for EV equations and bluff thresholds
│       ├── test_db.py         # In-memory database query speed and validation
│       ├── test_range_finder.py # Range coverage, opponent models and tie ordering
│       ├── test_calling_range.py # Calling-range model: card removal, exactness, monotonicity
│       ├── test_cli.py        # CLI decisions per opponent model and invalid-input handling
│       ├── test_generator.py  # Combinatorial generation completeness tests
│       ├── test_dynamic_scenarios.py # Dynamic stack & pot edge-case solver scenarios
│       └── test_api.py        # REST API endpoint integration tests
│
└── frontend/                  # React 19 + Vite web UI
    ├── index.html             # HTML shell
    ├── package.json           # Frontend dependencies and scripts (dev, build, lint, test)
    ├── vite.config.js         # Vite bundler configuration
    ├── src/
    │   ├── main.jsx           # Application entrypoint
    │   ├── App.jsx            # Page layout: inputs, verdict, tables, notes
    │   ├── i18n.js            # English / Vietnamese UI texts
    │   ├── format.js          # Pure number / zone formatting helpers
    │   ├── *.test.js          # Node built-in test runner tests (npm test)
    │   ├── App.css            # Layout and component styles
    │   └── index.css          # Color tokens and base styles
    └── public/                # Static assets & SVG indicators
```

---

## 5. Local Quickstart Guide

### Prerequisites
- **Python 3.11+** installed
- **Node.js 20.19+ or 22.12+** (required by Vite 8) and **npm** installed

### 1. Clone & Setup Workspace
```bash
git clone https://github.com/kkdoestech/lieng-stealer.git
cd lieng-stealer
```

### 2. Backend Setup & Startup
```bash
cd backend

# Create virtual environment (optional but recommended)
python -m venv .venv

# Activate virtual environment
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On Linux / macOS:
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the Flask API daemon (runs on port 5000)
python app.py
```

### 3. Frontend Setup & Startup (In a Separate Terminal)
```bash
cd frontend

# Install dependencies
npm install

# Start Vite development server (runs on port 5173)
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) to use the **LIÊNG SCOPE** web UI.

---

## 6. REST API Specification

All request and response bodies use standard `application/json`.

| Endpoint | Method | Description |
| :--- | :---: | :--- |
| `/health` | `GET` | System health check and database telemetry statistics. |
| `/api/evaluate` | `POST` | Evaluates a specific 3-card hand against pot odds and villain fold equity. |
| `/api/range` | `POST` | Scans the full 22,100 hand spectrum to return range coverage and top holdings. |
| `/api/solve` | `POST` | Combined single-hand decision and full range scanner. |
| `/api/analyze` | `POST` | Strategic game-theoretic analysis powered by OpenRouter LLM. |

Every `POST` endpoint validates `pot` (> 0), `bet_size` (or `bet`, > 0) and `fold_equity` (0–1) and
answers **`400`** with `{"error": "..."}` for invalid input. They also accept an optional
**`opponent_model`**:

| `opponent_model` | Meaning |
| :--- | :--- |
| `random` *(API default)* | The opponent folds regardless of hand strength; equity is against a random hand. |
| `range` *(web UI default)* | The opponent folds their weakest hands; equity is against the strongest `1 - fold_equity` of all combos. |

Single-hand results report two different break-even notions:

| Field | Meaning |
| :--- | :--- |
| `break_even_fold_equity` | Exact fold frequency where EV = 0 (random model). `null` under `range`, where EV is not monotonic in fold equity. |
| `profitable_from_fold_equity` | First fold frequency (on a 1% grid) from which raising stays +EV up to 100%. |
| `profitable_fold_zones` | (`/api/solve` only) Every `[start, end]` fold-frequency interval where raising is +EV, on a 1% grid. |

---

### POST `/api/evaluate`

Evaluates single-hand expected value, showdown equity, and recommended action.

#### Request Body
```json
{
  "pot": 100000,
  "bet": 50000,
  "fold_equity": 0.35,
  "hand": "As Kh Qd"
}
```

#### Response Body (`200 OK`)
```json
{
  "hand": "As Kh Qd",
  "canonical_id": "Q-K-A",
  "category": "LIENG",
  "pot": 100000.0,
  "bet": 50000.0,
  "fold_equity": 0.35,
  "opponent_model": "random",
  "showdown_equity": 0.9969,
  "equity_vs_random": 0.9969,
  "ev": 132097.0,
  "break_even_fold_equity": 0.0,
  "profitable_from_fold_equity": 0.0,
  "recommended_action": "RAISE",
  "is_profitable": true
}
```

With `"opponent_model": "range"`, a medium hand such as `"Ks Qh 3d"` (pot = bet = 100000, `fold_equity`
0.35) returns `"showdown_equity": 0.0108` (vs `"equity_vs_random": 0.36`), `"recommended_action":
"CHECK/FOLD"`, `"break_even_fold_equity": null` and `"profitable_from_fold_equity": 0.51`.

---

### POST `/api/range`

Calculates global range coverage percentage, profitable combination counts, and pure bluff thresholds.

#### Request Body
```json
{
  "pot": 100000,
  "bet": 50000,
  "fold_equity": 0.35
}
```

#### Response Body (`200 OK`)
```json
{
  "pot": 100000.0,
  "bet": 50000.0,
  "fold_equity": 0.35,
  "opponent_model": "random",
  "final_pot": 200000.0,
  "pure_bluff_break_even_fold_equity": 0.3333,
  "total_combinations": 22100,
  "profitable_combinations": 22100,
  "range_coverage_percent": 100.0,
  "total_canonical_classes": 455,
  "profitable_classes": 455,
  "top_hands": [
    {
      "canonical_id": "A-A-A",
      "category": "SAP",
      "showdown_equity": 1.0,
      "ev": 132500.0,
      "multiplicity": 4,
      "recommended_action": "RAISE"
    }
  ]
}
```

---

## 7. Verification & Testing

The backend test suite is executed using `pytest`. The suite tests strict total ordering rules, canonical isomorphism, Monte Carlo database integrity, EV mathematics, and API contracts.

```bash
cd backend
python -m pytest tests/ -v

cd ../frontend
npm test          # Node's built-in test runner: formatting helpers and i18n dictionaries
```

### Test Coverage Summary (93 Backend + 6 Frontend Tests Passing)
* `test_evaluator.py` (18 tests):
  - Strict total ordering: $\text{Sáp} > \text{Liêng} > \text{Đĩ} > \text{Điểm}$.
  - Straight validation: $A\text{-}2\text{-}3$ is lowest Liêng, $Q\text{-}K\text{-}A$ is highest Liêng, $K\text{-}A\text{-}2$ wraparound rejection.
  - Modulo 10 points boundary cases (19 pts $\equiv$ 9 pts, 20 pts $\equiv$ 0 pts Bù).
* `test_hands.py` (5 tests):
  - Card string deserialization, rank sorting, and canonical multiset mapping ($22,100 \rightarrow 455$).
* `test_ev.py` (13 tests):
  - Positive, zero, and negative EV branching.
  - Bluff tipping-point calculation against analytical $\alpha$.
  - Profitable fold-frequency zones, including two separate zones against a calling range.
* `test_calling_range.py` (9 tests):
  - Card-removal tables (every row sums to $\binom{49}{3} = 18,424$), exact match with `winrates.json` at 0% folds, monotonicity, latency budget.
* `test_db.py` (6 tests):
  - Database preloading verification, $O(1)$ lookup latency ($< 5\mu\text{s}$), and missing card exception handling.
* `test_range_finder.py` (6 tests):
  - Full range solver sorting, combination multiplicity weighting, range coverage metrics, opponent models, and strength tie-breaking.
* `test_generator.py` (7 tests):
  - Exact equities, rate invariants, Monte Carlo convergence, database schema, and exact enumeration as the command-line default.
* `test_dynamic_scenarios.py` (6 tests):
  - Monster value raise, junk-hand fold, pure bluff, coverage sweep, API schema, and one hand under both opponent models.
* `test_api.py` (17 tests):
  - HTTP endpoint integration, opponent models, break-even fields, category breakdown, and `400` responses for invalid input (including `/api/analyze`).
* `test_cli.py` (6 tests):
  - CLI decisions per opponent model, interactive mode, and exit code 2 with a readable message for invalid input.
* Frontend `npm test` (6 tests):
  - Locale-aware money formatting, profit-zone formatting, and English/Vietnamese dictionary parity.

---

## 8. Deployment Architecture

| Tier | Platform | Build Command | Runtime Command | Target Configuration |
| :--- | :--- | :--- | :--- | :--- |
| **Backend API** | [Railway](https://railway.app) / Render | `pip install -r requirements.txt` | `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120` | `backend/Procfile` |
| **Frontend SPA** | [Vercel](https://vercel.com) | `npm run build` | Static Edge CDN (`dist/`) | Vite production output |

Set `VITE_API_URL` in production environment variables to bind the React frontend SPA to the deployed Flask API.

---

## 9. Academic & Research Disclaimer

> [!NOTE]
> **Academic Notice**:
> This software is created and published strictly for educational, mathematical, and computer science research purposes into **algorithmic game theory**, **imperfect-information extensive-form games**, and **combinatorial state-space compression**.
> 
> It is **not** an online gambling service, does **not** facilitate real-money wagers, and must **not** be utilized in violation of applicable laws or terms of service of commercial gaming platforms.

---

## 10. License

Released under the [MIT License](LICENSE). Built for quantitative researchers and poker theory enthusiasts.

