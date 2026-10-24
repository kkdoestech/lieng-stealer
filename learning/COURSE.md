# Liêng Stealer — a guided tour of the codebase

This course walks you through **every file in this repository**, in the order the data flows: from
three playing cards, to a table of 455 win rates computed offline, to an expected-value decision
served by a Flask API and drawn by a React page.

It is a *tour*, not a rebuild. You don't retype anything. Each lesson tells you which lines to open,
quotes the important ones, explains what they do and why they were written that way, points out
what is weak about them, and then has you run, break and change the real code.

**Who it's for:** you know basic Python (functions, classes, lists, dicts) and basic JavaScript, and
you want to understand this project well enough to change any part of it with confidence. Anything
beyond the basics, such as frozen dataclasses, `bisect`, prefix sums, CORS or React effects, is
explained in a short 💡 box the first time it appears.

**Time:** about 18–20 hours for a careful first pass. Lessons are 40–90 minutes each.

> ⚖️ This project is for learning computer science, probability and software engineering. It is not
> gambling advice.

---

## Setup

You need **Python 3.11+**, **Node.js 22.22+** (Vite 8 and the Vitest/jsdom test stack require it), npm and git.

```bash
# Backend (from the repository root)
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt   # API + CLI + tests + ruff/mypy (requirements.txt = server only)
python -m pytest -q              # 159 passed

# Frontend (in a second terminal)
cd frontend
npm install
npm test                         # 18 tests pass (Vitest)
```

Unless a lesson says otherwise, Python commands run from `backend/` **with the virtual environment
active**, and npm commands run from `frontend/`.

To see the whole app running:

```bash
cd backend && python app.py      # API on http://127.0.0.1:5000
cd frontend && npm run dev       # web UI on http://localhost:5173 (it proxies /api to the backend)
```

`/api/analyze` works without an API key: it falls back to a rule-based answer (lesson 10). Keep
`OPENROUTER_API_KEY` unset while doing the course, so nothing is sent to an external service.

---

## The map

```
 OFFLINE (run once, ~30 s)                                  lessons 01–04
 ─────────────────────────
 52 cards ─► evaluator.py ─► hands.py ─► generator.py ─► data/winrates.json
             who beats whom   22,100 → 455  plays every hand    455 win rates
                                            against every other  vs a random hand

 ONLINE (every request, a few ms)                           lessons 05–11
 ────────────────────────────────
 at start-up:  db.py (WinRateDB)              calling_range.py (CallingRangeModel)
               equity vs a random hand        equity vs the hands that CALL
                          └───────────┬───────────────┘
                     opponent_model = "random" | "range"
                                      ▼
                           ev.py  (expected value, profit zones)
                                      ▼
                           range_finder.py  (rank all 455 hands by EV)
                     ┌────────────────┴────────────────┐
                     ▼                                 ▼
                 cli.py (terminal)              app.py (Flask JSON API)
                                                       │ HTTP
                                                       ▼
 FRONTEND                                   React + Vite page, English / Vietnamese
                                            lessons 12–14
```

The central idea: **the slow work (8.4 million hand comparisons) happens once, ahead of time. A
request only looks answers up and does a little arithmetic.** Lesson 00 explains why.

---

## Syllabus

| # | Lesson | Main files | Time |
|---|--------|-----------|------|
| 00 | [Orientation: the game, the problem and the map](00-orientation.md) | `README.md`, `AGENTS.md`, the repo tree | 60 min |
| 01 | [Errors and cards](01-errors-and-cards.md) | `exceptions.py`, `evaluator.py` (cards) | 45 min |
| 02 | [Hand evaluation](02-hand-evaluation.md) | `evaluator.py` (ranking) | 75 min |
| 03 | [Canonical hands: 22,100 → 455](03-canonical-hands.md) | `hands.py` | 60 min |
| 04 | [The generator and `winrates.json`](04-generator.md) | `generator.py`, `data/winrates.json` | 60 min |
| 05 | [The win-rate database](05-win-rate-db.md) | `db.py` | 40 min |
| 06 | [The calling range](06-calling-range.md) | `calling_range.py` | 90 min |
| 07 | [Expected value](07-expected-value.md) | `ev.py` | 60 min |
| 08 | [The range finder](08-range-finder.md) | `range_finder.py` | 45 min |
| 09 | [The command-line interface](09-cli.md) | `cli.py` | 45 min |
| 10 | [The Flask API](10-flask-api.md) | `app.py` | 90 min |
| 11 | [Tracing one request end to end](11-request-trace.md) | every layer | 45 min |
| 12 | [Frontend tooling](12-frontend-tooling.md) | `package.json`, `vite.config.js`, `main.jsx` | 40 min |
| 13 | [The React app](13-frontend-app.md) | `App.jsx`, `i18n.js`, `format.js` | 75 min |
| 14 | [Styling and DESIGN.md](14-styling.md) | `index.css`, `App.css`, `DESIGN.md` | 40 min |
| 15 | [Tests and performance](15-tests-and-performance.md) | `backend/tests/`, `*.test.js` | 60 min |
| 16 | [Deployment](16-deployment.md) | `Procfile`, `requirements.txt`, the build | 40 min |
| 17 | [Weak spots and next steps](17-weak-spots-and-next-steps.md) | everything | 60 min |
| — | [Glossary](glossary.md) | every term, with the lesson that teaches it | reference |

Lessons 00–11 build on each other. Lessons 12–14 (frontend) only need 00 and 11, so you can take
them earlier if you are more curious about the UI.

---

## Where every file is taught

```
lieng-stealer/
├── README.md, AGENTS.md, DESIGN.md, SKILLS.md, BLOG.md, EXPERIMENT.md   00 (how far to trust each)
├── backend/
│   ├── app.py                     10, 11
│   ├── Procfile, requirements.txt 16
│   ├── data/winrates.json         04 (generated, never edited by hand)
│   ├── src/
│   │   ├── exceptions.py          01
│   │   ├── evaluator.py           01 (cards), 02 (ranking)
│   │   ├── hands.py               03
│   │   ├── generator.py           04
│   │   ├── db.py                  05
│   │   ├── calling_range.py       06
│   │   ├── ev.py                  07
│   │   ├── range_finder.py        08
│   │   └── cli.py                 09
│   └── tests/test_*.py            each with its module, all together in 15
└── frontend/
    ├── index.html, package.json, vite.config.js, .oxlintrc.json   12
    └── src/
        ├── main.jsx               12
        ├── App.jsx                13
        ├── i18n.js, format.js     13
        ├── *.test.js              13, 15
        └── index.css, App.css     14
```

Files added when the weak spots were fixed (2026-10-24), and where they come up:

- [`backend/src/paths.py`](../backend/src/paths.py), the default data path that doesn't depend on the
  current folder: lessons [04](04-generator.md) and [05](05-win-rate-db.md).
- [`backend/tests/test_exceptions.py`](../backend/tests/test_exceptions.py), which pins the exception
  hierarchy, and [`backend/tests/perf.py`](../backend/tests/perf.py), the timing-budget helper: lessons
  [01](01-errors-and-cards.md) and [15](15-tests-and-performance.md).
- [`backend/pyproject.toml`](../backend/pyproject.toml) (ruff, strict mypy, pytest),
  [`backend/requirements-dev.txt`](../backend/requirements-dev.txt),
  [`backend/.env.example`](../backend/.env.example) and
  [`.github/workflows/ci.yml`](../.github/workflows/ci.yml): lessons [15](15-tests-and-performance.md)
  and [16](16-deployment.md).
- [`frontend/src/App.test.jsx`](../frontend/src/App.test.jsx) and
  [`frontend/src/test-setup.js`](../frontend/src/test-setup.js), the Vitest tests for the page: lessons
  [12](12-frontend-tooling.md), [13](13-frontend-app.md) and [15](15-tests-and-performance.md).

---

## How each lesson works

Every lesson has the same parts, so you always know where to look:

| Part | What you do |
|------|-------------|
| **Where this fits** | See the module's place on the map. |
| **Reading order** | Open these lines, in this order. Each link opens the file at the right line on GitHub. |
| **Walkthrough** | Read the quoted code and the explanation, with worked numbers. |
| **💡 Concept** | A short sidebar on a language or library feature, only when it's needed. |
| **Design decisions** | Why the code is shaped this way, and what the alternatives cost. |
| **⚠️ Weak spots** | What is wrong or fragile today, where, why it matters, and how to fix it. |
| **🧪 Try it** | Commands to run, with the output you should see. |
| **🏋️ Exercises** | 🟢 predict, 🟡 modify, 🔴 extend. Each has a solution you can unfold. |
| **❓ Quiz** | Five questions, with the answers folded underneath. |
| **Recap** | The points to remember. |

Conventions:

- 📍 marks a **verbatim excerpt**. The label names the exact lines, e.g.
  `📍 backend/src/ev.py:60-64`, and `verify_course.py` checks that they still match the file.
  Snippets without a 📍 are illustrations.
- Every number in the text (equities, EVs, test counts, timings) was produced by running the code.
  Timings depend on your machine.
- Exercises that change code end with "undo it with `git checkout -- <file>`". Commit or stash your
  own work before you start one.

---

## Your progress

Tick these off as you go (edit this file, or copy the list somewhere you'll see it):

- [ ] 00 Orientation
- [ ] 01 Errors and cards
- [ ] 02 Hand evaluation
- [ ] 03 Canonical hands
- [ ] 04 The generator
- [ ] 05 The win-rate database
- [ ] 06 The calling range
- [ ] 07 Expected value
- [ ] 08 The range finder
- [ ] 09 The CLI
- [ ] 10 The Flask API
- [ ] 11 Tracing one request
- [ ] 12 Frontend tooling
- [ ] 13 The React app
- [ ] 14 Styling
- [ ] 15 Tests and performance
- [ ] 16 Deployment
- [ ] 17 Weak spots and next steps

**Finish line:** you can pick any row from the weak-spot table in lesson 17, fix it with a test,
and keep `python -m pytest -q` and `npm test` green.

---

## Keeping this course in sync with the code

The course quotes real line numbers, so a code change can make it stale. After changing code, run:

```bash
python3 learning/verify_course.py
```

It checks that every link and line anchor still points inside its file, that every 📍 excerpt is
still identical to the lines it cites, that every lesson still has its sections, and that every
source file is taught somewhere. It exits with 1 and lists the problems if anything drifted. To
check single pages, pass their names: `python3 learning/verify_course.py 07-expected-value.md`.
