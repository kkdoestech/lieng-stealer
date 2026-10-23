# SKILLS.MD: CLI EXECUTION ROUTINES & DEVELOPER SKILLS

This document lists the commands that run the **Liêng Stealer** project: setup, tests, data generation,
the CLI, the API and the web UI. Every command below was run against the current code. Unless a section
says otherwise, run backend commands from `backend/` with the virtual environment active.

---

## 1. Environment & Setup

### 1.1 Backend (Python 3.11+)
```bash
cd backend
python -m venv .venv
source .venv/bin/activate              # Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

- `requirements.txt`: what the API server needs (Flask, flask-cors, Flask-Limiter, gunicorn, requests).
- `requirements-dev.txt`: that, plus pytest, rich (the CLI's tables), ruff and mypy.

### 1.2 Frontend (Node 22.22+)
```bash
cd frontend
npm install
```

---

## 2. Test Execution Routines

### 2.1 Run All Backend Tests
```bash
python -m pytest -q                   # 159 passed
```

### 2.2 Run Specific Test Suites
```bash
python -m pytest tests/test_evaluator.py -v       # ranking rules, Liêng A-2-3 vs Q-K-A, Đĩ vs 9 points
python -m pytest tests/test_hands.py -v           # 22,100 hands -> 455 canonical types
python -m pytest tests/test_generator.py -v       # exact enumeration, Monte Carlo, CLI flags
python -m pytest tests/test_db.py -v              # loading, validation, O(1) lookups
python -m pytest tests/test_calling_range.py -v   # equity against a calling range
python -m pytest tests/test_ev.py -v              # EV, break-even, profitable fold zones
python -m pytest tests/test_range_finder.py -v    # all 455 types ranked by EV
python -m pytest tests/test_cli.py -v             # the command line
python -m pytest tests/test_api.py -v             # every HTTP endpoint (no network calls)
python -m pytest tests/test_dynamic_scenarios.py -s   # end-to-end stories; -s shows their printed narrative
```

### 2.3 Performance Checks
```bash
python -m pytest -q --durations=10                # the slowest tests
PERF_BUDGET_FACTOR=3 python -m pytest -q          # loosen timing budgets on a slow machine (CI uses 3)
```

### 2.4 Frontend Tests
```bash
cd frontend
npm test                                          # Vitest: 18 passed
```

---

## 3. Data Generation Routines

`data/winrates.json` holds each canonical hand's equity against a random opponent hand. It is committed;
regenerate it only after changing the hand rules.

### 3.1 Exact Enumeration (default, deterministic)
```bash
python -m src.generator                           # all 18,424 opponent hands per class, ≈ 10 s on one core
python -m src.generator --workers 1               # gentler on a busy machine
```
The output is byte-for-byte identical to the committed file, and it is written atomically.

### 3.2 Monte Carlo (experiments only)
```bash
python -m src.generator --monte-carlo --samples 10000 --output /tmp/winrates_mc.json
```
`--exact` and `--monte-carlo` can't be combined; `--samples` must be at least 1. The tests expect the exact
data, so keep Monte Carlo files out of `data/winrates.json`.

### 3.3 Verify the Database
```bash
python -c "from src.db import WinRateDB; db = WinRateDB(); db.load(); print(len(db), 'hand types loaded and validated')"
```
`load()` rejects files that don't contain exactly the 455 hand types, or whose rates are implausible.

---

## 4. CLI Decision Solver & Heatmap Viewer Routines

There are no subcommands: options select what to show, and no options start an interactive session.

### 4.1 Evaluate a Specific Hand
```bash
# Ace of spades, King of hearts, Queen of diamonds (Liêng Q-K-A); pot 100k, bet 50k, opponent folds 35%
python -m src.cli --hand "As Kh Qd" --pot 100000 --bet 50000 --fold-equity 0.35
python -m src.cli --hand "As,Kh,Qd" --pot 100000 --bet 50000 --p-fold 0.35 --opponent-model range
```

### 4.2 Range Report Only
```bash
python -m src.cli --pot 200000 --bet 100000 --fold-equity 0.40
```
It prints the game state, how many hand types are profitable, and a per-category table.

### 4.3 Interactive Session
```bash
python -m src.cli                                 # asks for pot, bet, fold rate, opponent model and hand
python -m src.cli --opponent-model range          # same, with "range" as the default model answer
```

Exit codes: 0 success, 1 the win-rate file can't be loaded, 2 invalid input, 130 Ctrl-C.

---

## 5. API & Web UI Routines

### 5.1 Development Servers
```bash
cd backend && python app.py                       # API on http://127.0.0.1:5000
cd frontend && npm run dev                        # UI on http://localhost:5173 (proxies /api to the API)
curl -s http://127.0.0.1:5000/health
```

### 5.2 Production-Like Run
```bash
cd backend && PORT=5055 gunicorn app:app --bind 127.0.0.1:5055 --workers 2 --worker-class gthread --threads 4 --preload
cd frontend && npm run build && npm run preview
```

---

## 6. Code Quality & Formatting Skills

```bash
ruff check .                                      # from backend/: lint (imports, bugbear, pyupgrade)
mypy                                              # from backend/: strict type check of src/ and app.py
cd frontend && npm run lint                       # oxlint; any warning fails
python3 learning/verify_course.py                 # from the repo root: the course still matches the code
```

The same checks run on every push in `.github/workflows/ci.yml`.
