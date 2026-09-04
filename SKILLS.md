# SKILLS.MD: CLI EXECUTION ROUTINES & DEVELOPER SKILLS

This document specifies the operational commands, development workflows, and CLI execution routines for the **Liêng Stealer** project.

---

## 1. Environment & Setup

### Virtual Environment & Dependency Installation
```powershell
# Create virtual environment (Python 3.11+)
python -m venv .venv

# Activate virtual environment (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Install core dependencies & testing framework
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

*(Core dependencies: `pytest`, `rich`, `colorama`, `numpy`)*

---

## 2. Test Execution Routines

### 2.1 Run All Unit & Integration Tests
```powershell
pytest tests/ -v
```

### 2.2 Run Specific Test Suites
```powershell
# Test Hand Evaluator & Edge Cases (Sáp, Liêng A-2-3 vs Q-K-A, Đĩ vs 9 pts)
pytest tests/test_evaluator.py -v

# Test Combinatorics & Canonical Isomorphism
pytest tests/test_hands.py -v

# Test Expected Value (EV) & Fold Equity Logic
pytest tests/test_ev.py -v

# Test In-Memory Database & O(1) Cache
pytest tests/test_db.py -v

# Test Range Finder & Solver
pytest tests/test_range_finder.py -v
```

### 2.3 Run Tests with Performance Benchmark & Latency Checks
```powershell
pytest tests/ -v --durations=10
```

---

## 3. Data Generation & Monte Carlo Simulation Routines

The offline generator calculates heads-up win rates across all canonical hands against random or specific opponent ranges, exporting to `data/winrates.json`.

### 3.1 Fast Sampling (Development & Quick Smoke Test)
```powershell
# Runs 10,000 simulations per canonical hand for rapid verification
python -m src.generator --samples 10000 --output data/winrates.json
```

### 3.2 High-Precision Production Run (Convergence Mode)
```powershell
# Runs 100,000+ simulations per canonical hand to achieve epsilon < 0.1%
python -m src.generator --samples 100000 --output data/winrates.json --workers 4
```

### 3.3 Verify Precomputed Database
```powershell
# Validate integrity, format, and load latency (< 50ms) of data/winrates.json
python -m src.db --verify data/winrates.json
```

---

## 4. CLI Decision Solver & Heatmap Viewer Routines

Interactive and scriptable command-line interface powered by `rich` to solve EV and display playable ranges.

### 4.1 Evaluate a Specific Hand
Calculate EV and recommended action for a specific 3-card hand in a given game state:
```powershell
# Example: Player holds Ace of spades, King of hearts, Queen of diamonds (Liêng Q-K-A)
# Pot: 100k, Bet: 50k, Opponent Fold Probability: 0.35 (35%)
python -m src.cli solve --hand "As,Kh,Qd" --pot 100000 --bet 50000 --p-fold 0.35
```

### 4.2 Generate Optimal Range Heatmap (EV > 0 Matrix)
Scan all canonical hands and render an ANSI/Rich terminal heatmap of hands with positive expected value:
```powershell
# Render colored table of all profitable raising/bluffing hands
python -m src.cli range --pot 200000 --bet 100000 --p-fold 0.40 --min-ev 0
```

### 4.3 Interactive Live Session
Launch an interactive REPL session for real-time decision support at the table:
```powershell
python -m src.cli interactive
```

---

## 5. Code Quality & Formatting Skills

```powershell
# Type verification
mypy src tests --strict

# Linting & code standards
python -m py_compile src/*.py tests/*.py
```

