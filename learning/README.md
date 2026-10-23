# Rebuild Liêng Stealer From Scratch — A Step-by-Step Learning Guide

Welcome! This folder teaches you how to build the **Liêng Stealer** project yourself, starting from an
empty folder and ending with the same working program that is in this repository:

- a **Python engine** that knows the rules of the Vietnamese card game *Liêng*,
- a **simulator** that works out how often every possible hand wins,
- a **maths module** that decides whether betting is profitable (Expected Value),
- a **command-line tool** and a **web API** (Flask),
- and a **web page** (React) that shows everything in a dashboard.

The guide is written for a **first-year university student**. If you know basic Python (variables, `if`,
`for`, functions, lists, dictionaries) you have enough to start. Everything else is explained when it is
first needed.

---

## How to use this guide

1. **Go in order.** Every chapter builds on the previous one.
2. **Type the code yourself** instead of copy-pasting. It is slower, but you will remember it.
3. **Every code block that belongs to the project has a label above it**, like this:

   > 📄 **File:** `backend/src/evaluator.py` — *create this file*
   >
   > 📄 **File:** `backend/src/evaluator.py` — *add to the end*

   - *create this file* → make a new file (or replace the whole file) with exactly this code.
   - *add to the end* → paste the code at the bottom of the file, after everything that is already there.

   Code blocks **without** this label are small examples to help you understand an idea. You do not
   need to put them in the project (but you are encouraged to try them in the Python REPL).
4. **Run every 🧪 Mini-check and ✅ Checkpoint.** Each one tells you the exact command and the output
   you should see. If your output differs, stop and fix it before you continue.
5. **Read the ⚠️ Pitfall boxes.** The original project has a few mistakes and weak spots. You will build
   the project *exactly as it is* (so the original tests still work as your answer key), and each Pitfall
   box explains what is wrong, why it matters, and how you could improve it later.
6. If a word is unfamiliar, look it up in the [Glossary](00-glossary.md).

> 💡 **The original code is your answer key.** If you get stuck, compare your file with the real one
> in [`backend/src/`](../backend/src/) or [`frontend/src/`](../frontend/src/).

---

## What we are building (the big picture)

```
                         ┌────────────────── OFFLINE (run once, ~30 seconds) ──────────────────┐
                         │                                                                      │
  52-card deck ──► evaluator.py ──► hands.py ──► generator.py ──► data/winrates.json            │
  (cards, rules)    (who wins?)     (22,100 hands    (plays every hand     (455 rows: win rate   │
                                     → 455 types)     vs every opponent)    of every hand type) │
                         └──────────────────────────────────────────────────────────────────────┘
                                                                   │
                         ┌──────────────── ONLINE (every request, ~2 ms) ─────────────────────┐
                         │                                         ▼                           │
                         │                                    db.py (WinRateDB)               │
                         │                                    load file → dict                │
                         │                                         │                           │
                         │          ev.py (Expected Value maths) ◄─┤                           │
                         │                    │                    │                           │
                         │                    ▼                    ▼                           │
                         │              range_finder.py  (rank all 455 hand types by EV)       │
                         │                    │                                                │
                         │          ┌─────────┴──────────┐                                     │
                         │          ▼                    ▼                                     │
                         │     cli.py (terminal)     app.py (Flask web API, JSON)              │
                         └────────────────────────────────┬───────────────────────────────────┘
                                                          │ HTTP (fetch)
                                                          ▼
                                       frontend/  React + Vite dashboard ("LIÊNG SCOPE")
```

The key idea: **the slow work (simulating millions of games) is done once, ahead of time, and saved to a
file. When the user asks a question, the program only looks up answers in that file**, which is almost
instant. Chapter 1 explains why this design makes sense.

---

## The final project tree

This is what your folder will look like at the end:

```
lieng-stealer/
├── .gitignore
├── .vscode/settings.json
├── backend/
│   ├── requirements.txt          (ch 02)
│   ├── Procfile                  (ch 16)
│   ├── app.py                    (ch 12)  Flask web API
│   ├── data/winrates.json        (ch 07)  generated, not typed
│   ├── src/
│   │   ├── __init__.py           (ch 02)
│   │   ├── exceptions.py         (ch 04)  custom error types
│   │   ├── evaluator.py          (ch 04–05) cards, hands, ranking rules
│   │   ├── hands.py              (ch 06)  22,100 → 455 canonical hands
│   │   ├── generator.py          (ch 07)  simulator → winrates.json
│   │   ├── db.py                 (ch 08)  in-memory lookup table
│   │   ├── ev.py                 (ch 09)  Expected Value maths
│   │   ├── range_finder.py       (ch 10)  rank all hands by EV
│   │   └── cli.py                (ch 11)  terminal interface
│   └── tests/
│       ├── __init__.py           (ch 02)
│       ├── test_evaluator.py     (ch 04–05)
│       ├── test_hands.py         (ch 06)
│       ├── test_generator.py     (ch 07)
│       ├── test_db.py            (ch 08)
│       ├── test_ev.py            (ch 09)
│       ├── test_range_finder.py  (ch 10)
│       ├── test_api.py           (ch 12)
│       └── test_dynamic_scenarios.py (ch 13)
└── frontend/
    ├── .gitignore, .oxlintrc.json, index.html, package.json, vite.config.js   (ch 14)
    └── src/
        ├── main.jsx              (ch 14)
        ├── index.css             (ch 15)
        ├── App.css               (ch 15)
        └── App.jsx               (ch 15)
```

---

## Roadmap

| # | Chapter | You will learn | Time |
|---|---------|----------------|------|
| — | [Glossary](00-glossary.md) | Every term used in this guide | reference |
| 01 | [The game and the problem](01-the-game-and-the-problem.md) | Liêng rules, the betting decision, why we need maths | 45 min |
| 02 | [Setup and project skeleton](02-setup-and-project-skeleton.md) | git, virtual environments, pip, pytest, project layout | 45 min |
| 03 | [Python toolkit](03-python-toolkit.md) | Type hints, Enum, dataclass, properties, comparisons, itertools | 1.5 h |
| 04 | [Exceptions and cards](04-exceptions-and-cards.md) | Custom errors, `Suit`, `Rank`, `Card`, `Deck`, parsing text | 1.5 h |
| 05 | [The hand evaluator](05-hand-evaluator.md) | Ranking rules in code, `HandScore`, `evaluate_hand`, `Hand` | 2 h |
| 06 | [Combinatorics and canonical hands](06-combinatorics-canonical-hands.md) | Counting, 22,100 → 455, multiplicity | 2 h |
| 07 | [The generator (simulation)](07-generator-simulation.md) | Equity, exact enumeration vs Monte Carlo, multiprocessing, JSON | 2 h |
| 08 | [The database layer](08-database-layer.md) | Hash tables, O(1) lookup, loading files safely | 1 h |
| 09 | [Expected Value](10-expected-value.md) | The EV formula, break-even fold equity, bluffing maths | 1.5 h |
| 10 | [The range finder](11-range-finder.md) | Scoring all 455 hands, sorting, coverage | 1 h |
| 11 | [The command-line interface](12-cli.md) | argparse, `rich` tables, interactive input | 1 h |
| 12 | [The Flask web API](13-flask-api.md) | HTTP, JSON, REST endpoints, CORS, calling an LLM | 2.5 h |
| 13 | [Testing and performance](14-testing-and-performance.md) | pytest fixtures, scenario tests, timing code | 1 h |
| 14 | [Frontend foundations](15-frontend-foundations.md) | Node, Vite, React, JSX, state, effects, fetch | 2 h |
| 15 | [Building the UI](16-building-the-ui.md) | The full dashboard, CSS variables, grid, flexbox | 3 h |
| 16 | [Deployment](17-deployment.md) | gunicorn, Procfile, production builds, env variables | 45 min |
| 17 | [Pitfalls and next steps](18-pitfalls-and-next-steps.md) | Every known issue in one table + ideas to extend | 30 min |

Total: roughly **25–30 hours** for a careful first read-through.

---

## Prerequisites

| Tool | Version | Check with |
|------|---------|-----------|
| Python | 3.11 or newer | `python3 --version` |
| Node.js | 20.19+ or 22.12+ (needed from chapter 14; Vite 8 requires it) | `node --version` |
| npm | comes with Node | `npm --version` |
| git | any recent version | `git --version` |
| A code editor | VS Code recommended | — |

Commands in this guide are written for **Linux / macOS** (bash). Where Windows is different, there is a
🪟 **Windows** note.

> ⚖️ **Disclaimer.** This project is for learning computer science, probability and software
> engineering. It is not gambling advice and must not be used to break any law or any platform's rules.
