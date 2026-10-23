# LIÊNG SCOPE | Real-Time GTO Decision Solver

`[ Python 3.11 ]` `[ Flask ]` `[ React 18 ]` `[ Vite ]` `[ 58 Tests Passing ]` `[ Zero External Solvers ]`

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
|               - Endpoints: /health, /api/evaluate, /api/range, /api/solve                         |
|                            |                                                                      |
|                            v                                                                      |
|            [ Reactive Tactical HUD Terminal ]                                                     |
|            - React 18 + Vite SPA                                                                  |
|            - EPL SCOPE Dark Radar Theme (JetBrains Mono)                                          |
|            - Decision Banner, 4-Card HUD, Range Matrix & Top Holdings                             |
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
├── DESIGN.md                  # Persistent tactical UI/UX specification (EPL SCOPE)
├── AGENTS.md                  # Architectural guardrails, latency budgets & constraints
├── README.md                  # Project documentation & mathematical specification
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
│   │   ├── ev.py              # Pure Expected Value & break-even equity equations
│   │   ├── range_finder.py    # Full-range combinatorial scanner & coverage resolver
│   │   ├── db.py              # Thread-safe in-memory win rate database
│   │   ├── generator.py       # Combinatorial generator for Monte Carlo / enumeration
│   │   ├── cli.py             # High-speed terminal CLI for head-to-head simulations
│   │   └── exceptions.py      # Domain exception hierarchy (LiengError)
│   └── tests/
│       ├── test_evaluator.py  # 18 unit tests for strict hand hierarchies & edge cases
│       ├── test_hands.py      # Tests for card parsing and canonical mapping
│       ├── test_ev.py         # Tests for EV equations and bluff thresholds
│       ├── test_db.py         # In-memory database query speed and validation
│       ├── test_range_finder.py # Range coverage and combinatorial filtering tests
│       ├── test_generator.py  # Combinatorial generation completeness tests
│       ├── test_dynamic_scenarios.py # Dynamic stack & pot edge-case solver scenarios
│       └── test_api.py        # REST API endpoint integration tests
│
└── frontend/                  # React 18 + Vite Tactical Radar Dashboard
    ├── index.html             # HTML shell with JetBrains Mono typography
    ├── package.json           # Frontend dependencies and build scripts
    ├── vite.config.js         # Vite bundler configuration
    ├── src/
    │   ├── main.jsx           # Application entrypoint
    │   ├── App.jsx            # Tactical radar terminal layout & telemetry controls
    │   ├── App.css            # EPL SCOPE dark terminal styling & responsive HUD grid
    │   └── index.css          # Design tokens, CSS variables, and 24px canvas grid
    └── public/                # Static assets & SVG indicators
```

---

## 5. Local Quickstart Guide

### Prerequisites
- **Python 3.11+** installed
- **Node.js 18+** and **npm** installed

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

Open [http://localhost:5173](http://localhost:5173) to access the **LIÊNG SCOPE** tactical terminal.

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
  "hand": "A♠ K♥ Q♦",
  "canonical_id": "Q-K-A",
  "category": "LIENG",
  "pot": 100000.0,
  "bet": 50000.0,
  "fold_equity": 0.35,
  "showdown_equity": 0.9969,
  "ev": 132097.0,
  "break_even_fold_equity": 0.0,
  "recommended_action": "RAISE",
  "is_profitable": true
}
```

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
  "final_pot": 200000.0,
  "pure_bluff_break_even_fold_equity": 0.3333333333333333,
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
```

### Test Coverage Summary (58 Tests Passing)
* `test_evaluator.py` (18 tests):
  - Strict total ordering: $\text{Sáp} > \text{Liêng} > \text{Đĩ} > \text{Điểm}$.
  - Straight validation: $A\text{-}2\text{-}3$ is lowest Liêng, $Q\text{-}K\text{-}A$ is highest Liêng, $K\text{-}A\text{-}2$ wraparound rejection.
  - Modulo 10 points boundary cases (19 pts $\equiv$ 9 pts, 20 pts $\equiv$ 0 pts Bù).
* `test_hands.py` (5 tests):
  - Card string deserialization, rank sorting, and canonical multiset mapping ($22,100 \rightarrow 455$).
* `test_ev.py` (9 tests):
  - Positive, zero, and negative EV branching.
  - Bluff tipping-point calculation against analytical $\alpha$.
* `test_db.py` (6 tests):
  - Database preloading verification, $O(1)$ lookup latency ($< 5\mu\text{s}$), and missing card exception handling.
* `test_range_finder.py` (4 tests):
  - Full range solver sorting, combination multiplicity weighting, and range coverage metrics.
* `test_generator.py` (5 tests):
  - Combinatorial completeness: exact $\binom{52}{3} = 22,100$ hands and canonical partition sums.
* `test_dynamic_scenarios.py` (5 tests):
  - Complex multi-street parameter permutations and edge-case pot odds.
* `test_api.py` (6 tests):
  - HTTP endpoint integration, JSON payload schema validation, and error response codes.

---

## 8. Deployment Architecture

| Tier | Platform | Build Command | Runtime Command | Target Configuration |
| :--- | :--- | :--- | :--- | :--- |
| **Backend API** | [Railway](https://railway.app) / Render | `pip install -r requirements.txt` | `gunicorn -w 4 -b 0.0.0.0:$PORT app:app` | `backend/Procfile` |
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

