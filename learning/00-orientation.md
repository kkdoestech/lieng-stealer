# Lesson 00 — Orientation: the game, the problem and the map

> **Goal:** know the rules of Liêng, the one question this project answers, why it is built as
> "compute once offline, look up online", where every file lives, and how far to trust each of the
> root documents. **Files:** [`README.md`](../README.md), [`AGENTS.md`](../AGENTS.md), the repo tree,
> and the four entry points ([`cli.py`](../backend/src/cli.py), [`app.py`](../backend/app.py),
> [`generator.py`](../backend/src/generator.py), the [frontend](../frontend/package.json)).
> **Time:** ~60 min. **Before this:** [COURSE.md](COURSE.md)

---

## Where this fits

```
 ┌──────────────────────────── you are here: all of it ─────────────────────────────┐
 │                                                                                    │
 │  OFFLINE, once                   evaluator.py ─► hands.py ─► generator.py          │
 │  (lessons 01–04)                 rules           22,100→455   8.4M comparisons     │
 │                                                                   │                │
 │                                                         data/winrates.json         │
 │                                                                   │                │
 │  ONLINE, every request           db.py + calling_range.py ─► ev.py ─► range_finder │
 │  (lessons 05–11)                 look up equity               EV       455 hands   │
 │                                                     │                              │
 │                                         cli.py ◄────┴────► app.py ─► React page    │
 │                                       (terminal)          (JSON)    (lessons 12–14)│
 └────────────────────────────────────────────────────────────────────────────────────┘
```

This lesson has no single module. It gives you the vocabulary (Sáp, equity, fold equity, EV), the
reason for the shape of the code (an expensive table built once, cheap lookups afterwards), and a
first run of everything, so that every later lesson can zoom in on one box of this picture.

---

## Reading order

| # | Location | What to look for |
|---|----------|------------------|
| 1 | [README.md:89-150](../README.md#L89-L150) | "How it works": the ranking table, 22,100 → 455, the two equity models, the EV formula. |
| 2 | [AGENTS.md:29-83](../AGENTS.md#L29-L83) | The rules as a spec. Since October 2026 it also describes what the code really does (section 9). |
| 3 | [README.md:371-410](../README.md#L371-L410) | The project layout, one line per file. |
| 4 | [app.py:135-139](../backend/app.py#L135-L139) | The online half in five lines: load the table, build the models, once per app. |
| 5 | [cli.py:317](../backend/src/cli.py#L317) | `main`, the terminal entry point you will run below. |
| 6 | [AGENTS.md:124-130](../AGENTS.md#L124-L130) | The performance budgets, now with measured numbers (section 9). |

---

## Walkthrough

### 1. The cards and the four categories

Liêng uses a normal 52-card deck: 13 ranks (2 … 10, J, Q, K, A) and 4 suits (♠ ♣ ♦ ♥). Each player
gets three cards. In this codebase a card is written as rank + one-letter suit: `As` is A♠, `10d`
is 10♦, `Td` also means 10♦.

**Suits never decide a showdown.** A♠ K♥ Q♦ is exactly as strong as A♣ K♣ Q♥. Keep that in mind:
lesson 03 uses it to shrink the problem from 22,100 hands to 455.

Every hand falls into exactly one category, and a higher category always wins:

```
  STRONGEST
     ▲   4  Sáp    three of a kind              7♠ 7♥ 7♦
     │   3  Liêng  three consecutive ranks      7♠ 8♥ 9♦
     │   2  Đĩ     three face cards (J, Q, K)   J♠ Q♥ Q♦
     │   1  Điểm   points 0–9                   2♠ 5♥ 9♦ → 6 points
  WEAKEST
```

The numbers 4–1 are the values the code uses (`HandCategory`, lesson 02). To classify a hand, ask
the questions top-down and stop at the first "yes": same rank? consecutive? all face cards?
Otherwise it is Điểm.

**Points.** 2–9 count their face value, 10/J/Q/K count 0, the Ace counts 1. Add them and keep the
last digit (`% 10`). 9 is the best score, 0 (*Bù*) the worst.

| Hand | Sum | Points |
|------|-----|--------|
| 9-10-K | 9 + 0 + 0 | 9 |
| A-3-5 | 1 + 3 + 5 | 9 |
| 9-8-2 | 19 | 9 |
| 10-10-K | 0 | 0 (Bù) |

Four edge cases cause most of the bugs people write in Liêng engines. Lesson 02 shows exactly where
the code handles each one:

| Hand | What it is | Why |
|------|-----------|-----|
| A-2-3 | the **weakest** Liêng | the Ace may sit below the 2 |
| Q-K-A | the **strongest** Liêng | the Ace may sit above the K |
| K-A-2 | **not** a Liêng: 3 points | no wrap-around |
| A-J-J | **not** Đĩ: 1 point | the Ace is not a face card |

And one rule that surprises newcomers: **any Đĩ beats any Điểm hand, even 9 points.**

### 2. The decision: raise or give up

The project studies one simplified moment of the game. There is already a pot `P` on the table. You
may raise (*Tố*, or *Tất tay* when it is all-in) by betting `B`. The opponent then folds or calls:

```
                         you raise B
                              │
             ┌────────────────┴────────────────┐
     opponent folds (f)                 opponent calls (1 − f)
     you take the pot P                 cards are shown, final pot P + 2B
                                   ┌──────────┴──────────┐
                              you win (w)            you lose (1 − w)
                              + (P + B)              − B
```

Two probabilities decide everything:

- **Fold equity `f`**: how often the opponent folds. You *estimate* it from how they play. A
  "calling station" has `f ≈ 0`. The code never computes `f`; it is an input.
- **Showdown equity `w`**: how often your hand wins when the opponent calls. This is what the
  computer works out for you, and most of the backend exists to produce it.

### 3. Expected value in brief

The **expected value** (EV) of raising is your average profit if you could make this exact
decision many times, measured against giving up (which is worth 0):

```
EV = f · P  +  (1 − f) · [ w · (P + 2B) − B ]
```

Lesson [07](07-expected-value.md) derives every part of this. For now, two worked examples with the
web page's default spot (`P = 100,000`, `B = 50,000`, `f = 0.35`), using equities from
`winrates.json`:

| | Q-K-A (best Liêng) | 5-3-2 (0 points) |
|---|---|---|
| `w` against a random hand | 0.9969 | 0.0024 |
| showdown part `w · 200,000 − 50,000` | 149,380 | −49,520 |
| fold part `0.35 × 100,000` | 35,000 | 35,000 |
| **EV** = fold + 0.65 × showdown | **+132,097** | **+2,812** |
| break-even fold rate | 0 (profitable even if never folded to) | 0.3312 |

The second column is the point of the whole project. 5-3-2 is close to the worst hand in the game,
yet raising it makes money here, because the opponent folds more often than the 33.12% this bluff
needs. If they folded only 5% of the time, the same raise would lose 42,044 on average. **"Strong
hand → raise" is too simple.** The decision depends on the pot, the bet, the opponent's fold rate
and the equity together.

A pure bluff (`w = 0`) breaks even at `f = B / (P + B) = 50,000 / 150,000 = 33.33%`. 5-3-2 needs a
little less (33.12%) because it still wins 0.24% of showdowns.

EV above zero is necessary and not sufficient. The tool answers with one of three sizes, and a bet
must earn at least 5% of the pot at your fold rate and at the worst fold rate ten points away before
it becomes the answer (lesson 07, section 8). A positive EV under 5% of the pot is a check.

### 4. Who calls? The two opponent models

The equity above is measured against a **random** hand. Real opponents don't fold at random: they
fold their *worst* hands and call with their best. So when you are called, you usually face
something stronger than random. The code supports both views, chosen by `opponent_model`:

| Model | The opponent folds… | Your `w` is measured against… | Lesson |
|---|---|---|---|
| `random` | regardless of their cards | every possible hand | [05](05-win-rate-db.md) |
| `range` | their weakest hands first | only the strongest `(1 − f)` of the 22,100 hands | [06](06-calling-range.md) |

For strong hands the models barely differ (Q-K-A: 0.9969 vs 0.9952 at `f = 0.35`). For medium
hands the difference is dramatic. K-Q-3 (3 points) wins **36%** against a random hand, but only
**1.08%** (`0.0108`) against an opponent who folds their weakest 35% (that is 7,735 of the 22,100
hands) and calls with the rest. The API, the CLI and the web page all default to `range`; pass
`random` (`--opponent-model random` on the command line, `"opponent_model": "random"` over HTTP) to
use the uniform model.

### 5. Why precompute: the offline/online split

To know `w` for a hand exactly, remove its three cards from the deck. 49 cards remain, and the
opponent can hold any 3 of them: C(49, 3) = **18,424** hands. Compare yours with each one and count
wins, ties and losses.

Doing that for every one of the C(52, 3) = **22,100** starting hands means
22,100 × 18,424 = **407,170,400** comparisons. Two ideas make it cheap:

1. **Suits don't matter**, so the 22,100 hands collapse into **455** rank patterns
   ("canonical hands", lesson [03](03-canonical-hands.md)). Only 455 × 18,424 = **8,382,920**
   comparisons are needed.
2. **Do it once, ahead of time.** `generator.py` (lesson [04](04-generator.md)) runs those 8.4
   million comparisons and saves 455 answers to `backend/data/winrates.json` (82,694 bytes). On the
   machine this lesson was re-run on, it took 10 s with a single worker process. (The first version
   of this course measured 25 s with 4 workers; the evaluator became about eight times faster in
   October 2026, lesson 02.)

Every request after that is a dictionary lookup plus a little arithmetic. The whole online half is
set up in seven lines when the Flask app is created:

📍 [`backend/app.py:148-154`](../backend/app.py#L148-L154)
```python
    if db is None:
        db = WinRateDB(DEFAULT_DB_PATH)
    if calling_model is None:
        calling_model = CallingRangeModel()
    if thresholds is None:
        thresholds = _thresholds_from_config(app.config)
    app.extensions["lieng"] = Services(db, calling_model, RangeFinder(db, calling_model), thresholds)
```

Load 455 records, build the calling-range tables, read the advice thresholds, wrap it all in a range
finder: that is all the server's state. These lines live inside `create_app()`, an **app factory**
(lesson [10](10-flask-api.md)): each app object gets its own services, stored in `app.extensions`, and
a test can pass in its own database. Until October 2026 the same objects were module-level globals,
which `AGENTS.md` forbids; the only module-level object left is `app = create_app()`
([app.py:870](../backend/app.py#L870)), the entry point for `gunicorn app:app` and `python app.py`.
One equity lookup took about 0.1 µs on the same machine.

### 6. A tour of the repository

```
lieng-stealer/
├── README.md  AGENTS.md  DESIGN.md  SKILLS.md  BLOG.md  EXPERIMENT.md  LICENSE
├── .github/workflows/ci.yml   CI: ruff, mypy, pytest, lint, build, course   lesson 15
├── backend/
│   ├── app.py                 Flask JSON API: create_app(), 6 routes         lesson 10
│   ├── Procfile               gunicorn start command                        lesson 16
│   ├── requirements.txt       5 pinned runtime packages                     lesson 16
│   ├── requirements-dev.txt   + pytest, rich, ruff, mypy                    lesson 16
│   ├── pyproject.toml         ruff, strict mypy and pytest settings         lesson 15
│   ├── data/winrates.json     455 exact equities (generated)                lesson 04
│   ├── src/
│   │   ├── exceptions.py      LiengError and eight subclasses               lesson 01
│   │   ├── paths.py           the absolute path of winrates.json            lesson 05
│   │   ├── evaluator.py       Card, Rank, Suit; HandScore, evaluate_hand    lessons 01, 02
│   │   ├── hands.py           22,100 → 455 canonical hands                  lesson 03
│   │   ├── generator.py       builds winrates.json (offline)                lesson 04
│   │   ├── db.py              WinRateDB: equity vs a random hand            lesson 05
│   │   ├── calling_range.py   CallingRangeModel: equity vs callers          lesson 06
│   │   ├── ev.py              EV, break-even, profitable zones              lesson 07
│   │   ├── range_finder.py    EV of all 455 hands, sorted                   lesson 08
│   │   └── cli.py             terminal report                               lesson 09
│   └── tests/                 11 test files, 172 tests                      lesson 15
└── frontend/                  React 19 + Vite 8 page                        lessons 12–14
    └── src/  main.jsx  App.jsx  i18n.js  format.js  *.css  *.test.js(x)
```

Imports point one way only: `exceptions ← evaluator ← hands ← {generator, db, calling_range}`,
then `ev ← range_finder ← {cli, app}`, with `paths.py` (one constant) used by `db`, `generator`,
`cli` and `app`. Nothing in `src/` imports Flask, and `ev.py` imports only `exceptions.py` from the
project, so each lesson can study one file knowing only the earlier ones.

### 7. Your first run of every entry point

All commands run from `backend/` with the virtual environment active (see
[COURSE.md](COURSE.md#setup)), except `npm`, which runs from `frontend/`.

**The tests.** `python -m pytest -q` prints:

```
........................................................................ [ 41%]
........................................................................ [ 83%]
............................                                             [100%]
172 passed in 2.11s
```

**The CLI.** The README's example, trimmed to the first and last panels:

```bash
python -m src.cli --pot 100000 --bet 50000 --fold-equity 0.35 --hand "As Kh Qd"
```

```
╭───────────────────── LIÊNG STEALER - GAME STATE BANNER ──────────────────────╮
│ Pot Size (Dead Money): 100,000                                               │
│ Bet / Raise Sizing: 50,000                                                   │
│ Opponent Fold Equity: 35.0%                                                  │
│ Opponent Model: folds their weakest 35% first, calls with the best 65%       │
│ (range)                                                                      │
│ Opponent Calling Range: strongest 65.0% of the 22,100 hands                  │
│ Pure Bluff Break-Even Fold Equity: 33.3%                                     │
│ Final Pot (if called): 200,000                                               │
╰──────────────────────────────────────────────────────────────────────────────╯
   … the range overview and the per-category table …
╭────────────────────────── HAND EVALUATION & ACTION ──────────────────────────╮
│ Hand Evaluated: As Kh Qd (Liêng Q-K-A)                                       │
│ Canonical Class: Q-K-A (Liêng)                                               │
│ Showdown Equity: 99.52%                                                      │
│ Expected Value (EV) at 50,000: +131,876                                      │
│ Break-Even Fold Equity: n/a (range model)                                    │
│                                                                              │
│  >>> ACTION: ALL IN (100,000) — VALUE <<<                                    │
│ Why: All in: you win about 99.52% at showdown, so +164,064 is worth risking  │
│ the pot even if they fold 10% less often than you assumed.                   │
│ Ladder (ALL_IN_VALUE):                                                       │
│   ✓ SMALL BET     33,000  EV +  120,932.08  worst +117.64% of pot            │
│   ✓ LARGE BET     75,000  EV +     147,970  worst +140.48% of pot            │
│   ✓ ALL IN       100,000  EV +     164,064  worst +154.08% of pot  <-        │
│ recommended                                                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
```

The `SOLVER OVERVIEW` panel in the middle says `Profitable Classes: 455 / 455 canonical classes`.
With a fold rate of 35%, above the 33.3% pure-bluff line, *every* hand is worth a bet here. The
answer is still one size. Q-K-A clears the floor at all three rungs and the policy takes the biggest
one; lesson 07 explains the ladder and lesson 09 shows the same panel for a hand that has to bluff.
The CLI checks the hand and the numbers before it prints anything: `--hand "As Xh Kd"` prints only
`Invalid input: Invalid card 'Xh': …` and exits with code 2 (lesson 09).

**The API.** If the server is running (`python app.py`), ask it directly:

```bash
curl -s http://127.0.0.1:5000/health
```

```
{"classes_loaded":455,"database_loaded":true,"status":"healthy","version":"3.0.0"}
```

```bash
curl -s -X POST http://127.0.0.1:5000/api/evaluate -H "Content-Type: application/json" \
  -d '{"pot": 100000, "bet_size": 50000, "fold_equity": 0.35, "hand": "As Kh Qd"}'
```

```
{"advice": {"action": "ALL_IN", "amount": 100000.0, "equity_when_called": 0.99693335, "ev": 164402.00325, "ev_ratio": 1.6440200325, "kind": "VALUE", "ladder": [{"action": "SMALL_BET", "amount": 33000.0, "blocked_by": null, "eligible": true, "ev": 121119.10846500001, "ev_ratio": 1.21119108465, "robust": true, "worst_ev_ratio": 1.1787001485500002}, {"action": "LARGE_BET", "amount": 75000.0, "blocked_by": null, "eligible": true, "ev": 148251.669375, "ev_ratio": 1.48251669375, "robust": true, "worst_ev_ratio": 1.4082833562500001}, {"action": "ALL_IN", "amount": 100000.0, "blocked_by": null, "eligible": true, "ev": 164402.00325, "ev_ratio": 1.6440200325, "robust": true, "worst_ev_ratio": 1.5449400275}], "reason": "ALL_IN_VALUE", "robust": true, "why": {"call_component": 129402.00325000001, "fold_component": 35000.0, "net": 164402.00325}, "win_rate_defined": true}, "bet_size": 50000.0, "break_even_fold_equity": 0.0, "call_range_percent": null, "canonical_id": "Q-K-A", "category": "LIENG", "category_name": "Li\u00eang", "equity_vs_random": 0.99693335, "ev": 132101.33550000002, "fold_equity": 0.35, "hand": "As Kh Qd", "is_profitable": true, "opponent_model": "random", "pot": 100000.0, "profitable_fold_zones": [[0.0, 1.0]], "profitable_from_fold_equity": 0.0, "random_hand_equity": 0.99693335, "score_name": "Li\u00eang Q-K-A", "showdown_equity": 0.99693335}
```

Same hand, same spot, same +132,101 as the CLI: both front doors call the same engine. (`\u00ea`
is how JSON escapes the `ê` of Liêng; a JSON parser turns it back.) Every endpoint uses the same
names, `bet_size`, `showdown_equity` and `advice`; the old request field `bet` is still accepted.
`advice` is the recommendation: an action, a kind, an amount, the reason and the three rungs behind
it (lesson 07). The `sensitivity` block is cut from this paste. A bad request is JSON too, with a
stable code, e.g.
`{"code": "invalid_hand", "error": "A Liêng hand cannot have duplicate cards."}` (lesson 10).

**The frontend tests.** `npm test` (from `frontend/`) runs Vitest and ends with:

```
 Test Files  3 passed (3)
      Tests  37 passed (37)
```

`npm run dev` then serves the page on <http://localhost:5173>. It solves the default spot as soon
as it loads, with the `range` model, and shows +131,876 for As Kh Qd (equity 0.9952, section 4).

**The generator** is the fourth entry point. You don't need to run it: the data is committed.
Exercise 3 shows how to run it safely.

### 8. Preview: one click, end to end

Lesson [11](11-request-trace.md) traces a click on "Run solver" through every layer. In short:

1. A click on "Run solver" calls `startSolve` ([App.jsx:196](../frontend/src/App.jsx#L196)), which
   cancels any run still in flight and calls `fetchSolveAndAnalysis`
   ([App.jsx:50](../frontend/src/App.jsx#L50)). That sends `POST /api/solve`
   ([App.jsx:56](../frontend/src/App.jsx#L56)) to a relative URL, which the Vite dev server forwards
   to Flask.
2. `solve_api` ([app.py:424](../backend/app.py#L424)) validates the numbers with
   `_parse_game_params` ([app.py:256](../backend/app.py#L256)).
3. The hand text becomes cards: `Hand.from_str` ([evaluator.py:420-421](../backend/src/evaluator.py#L420-L421)).
4. The cards become a canonical class and a lookup: `to_canonical` and `db.get`
   ([app.py:313-314](../backend/app.py#L313-L314)) → `"Q-K-A"` → equity 0.9969.
5. `ev.py` turns the equity into EV and profitable fold zones
   ([app.py:316-317](../backend/app.py#L316-L317)).
6. `range_finder.solve_range` scores all 455 hands ([app.py:352](../backend/app.py#L352)).
7. `jsonify` sends it back, React draws the verdict, tables and the "where raising pays" bar, and
   the same function then asks `/api/analyze` for the notes ([App.jsx:87](../frontend/src/App.jsx#L87)).

### 9. The root documents, and how far to trust each

The repository has six Markdown files at the root. They were written at different times; on
2026-10-24 (commit `8c987ea`, "bring README, AGENTS, SKILLS and DESIGN in line with the code") all
six were updated, four of them substantially, and a follow-up commit the same day (`a9d9ce9`) fixed
the small slips this lesson's weak spots had found. Here is what each one is good for today:

| File | What it is | Trust |
|------|-----------|-------|
| [README.md](../README.md) | Front page: rules, maths, CLI/API reference, test table | **High.** Its numbers match real runs: 172 + 20 tests ([README.md:10](../README.md#L10)), the unified API fields and error codes, real JSON examples, every environment variable. The two small slips the course found are fixed (weak spot 6). |
| [AGENTS.md](../AGENTS.md) | The engineering spec: rules, data model, EV, budgets | **High.** Rewritten to describe the code: an EV engine, not an equilibrium solver ([AGENTS.md:4](../AGENTS.md#L4)); exact enumeration; strict mypy and ruff, enforced in CI; the real exception tree, `create_app()`, `Hand` equality, the house tie-breaks, the six-field `HandScore`; and measured budgets. One budget was met by relaxing it (weak spot 2). |
| [DESIGN.md](../DESIGN.md) | Rules for the web UI (Ayu Dark colours, layout, copy) | **High** for the current UI. It is the rulebook for lesson [14](14-styling.md); the UI was brought in line with it (new colour tokens, one message per error code). Since `a9d9ce9` the text the backend sends obeys it too (weak spot 3). |
| [SKILLS.md](../SKILLS.md) | A command cheat-sheet | **High** (it was the least trustworthy file). Rewritten from commands that actually run: bash with PowerShell notes, no CLI subcommands, the real dependencies, the exact-by-default generator. I ran a sample: they work (weak spot 1). |
| [BLOG.md](../BLOG.md) | The origin story, in Vietnamese | Background only. A dated note at the top ([BLOG.md:5](../BLOG.md#L5)) says the data is now exact and the "10,000 games" experiment has no code; the Liêng frequency is corrected to 3.48%. The story itself still describes Monte Carlo. |
| [EXPERIMENT.md](../EXPERIMENT.md) | A two-student project proposal, in Vietnamese | Background only. A dated note ([EXPERIMENT.md:5](../EXPERIMENT.md#L5)) lists what the code does differently; the body is still the original plan (weak spot 5). |

When a document and the code disagree, the code and its tests win. This course always quotes the
code.

---

## 💡 Concept: expected value is a long-run average

A friend offers: "Flip a coin. Heads, I pay you 30. Tails, you pay me 10." For each outcome,
multiply its probability by its profit, then add:

```
EV = 0.5 × (+30) + 0.5 × (−10) = +10        on average you win 10 per flip
```

Any single flip loses or wins; the EV is what thousands of flips average out to. The Liêng formula
in section 3 is the same sum over three outcomes (fold, call and win, call and lose). A positive EV
does not promise you win *this* hand. It says the raise pays over many hands like it.

## 💡 Concept: offline precomputation, online lookup

When an answer is expensive to compute but depends on only a few inputs, compute every possible
answer once, store it, and look it up later. Maps (routes between tiles), search engines (an index)
and chess engines (endgame tables) all do this. Here the inputs are just the 455 rank patterns, so
the table is tiny (82,694 bytes). The price is that the table can go **stale**: if you change a rule
in `evaluator.py`, `winrates.json` keeps the old answers until you run the generator again.
Exercise 4 shows this happening, and shows the safety net added in October 2026: the loader
compares the file with the current rules and refuses a stale one.

---

## Design decisions

- **Precompute instead of computing per request.** 8.4 million comparisons take about 10 s on one
  core. A lookup takes about 0.1 µs. The cost is one generated file that must be rebuilt whenever
  the rules change.
- **Exact enumeration instead of Monte Carlo.** With only 18,424 opponents per hand, counting all
  of them is affordable, so the equities have no sampling error and the file is reproducible: a
  fresh run produced a byte-for-byte identical `winrates.json`. Monte Carlo is still available
  behind `--monte-carlo` for experiments (lesson 04).
- **Two opponent models instead of one.** `random` is simple and needs only the table. `range` is
  more realistic but needs extra tables (lesson 06). Offering both lets you see how much the
  assumption matters (K-Q-3: 36% vs 1.08%).
- **One engine, three front doors.** The CLI, the API and the React page all go through the same
  `src/` modules, so a number on screen can always be reproduced in a terminal.
- **The opponent's fold rate is an input.** The tool does not model the opponent's psychology. It
  answers "if they fold this often, should I raise?" and leaves the estimate to you.

---

## ⚠️ Weak spots

This lesson's weak spots are all **documentation drift**: a document says something the code no
longer does. None of them breaks the program, but each one can waste an afternoon. When the course
was written there were five; the documentation pass of 2026-10-24 (commit `8c987ea`) fixed most of
them, a careful re-read turned up a few small new ones, and the follow-up commit `a9d9ce9` fixed
those too. What is left is one budget worth reading carefully (weak spot 2), two historical
documents (weak spots 4 and 5), and the fact that no test watches the documents.

**1. ✅ Fixed: SKILLS.md commands that failed or did nothing.** It used to document a CLI with
subcommands (`python -m src.cli solve …`, which exits 2 with `unrecognized arguments: solve`), a
`python -m src.db --verify` that printed nothing and exited 0 (so it looked like a passed check),
PowerShell-only setup, packages that aren't dependencies (colorama, numpy), five test files, and
`mypy`, which wasn't installed. It was rewritten from commands that run, for example:

📍 [`SKILLS.md:99-101`](../SKILLS.md#L99-L101)
```
# Ace of spades, King of hearts, Queen of diamonds (Liêng Q-K-A); pot 100k, bet 50k, opponent folds 35%
python -m src.cli --hand "As Kh Qd" --pot 100000 --bet 50000 --fold-equity 0.35
python -m src.cli --hand "As,Kh,Qd" --pot 100000 --bet 50000 --p-fold 0.35 --opponent-model range
```

I ran both: they print the full report and exit 0 (+131,876 each, since the first runs the default
`range` model and the second names it; +132,101.34 with `--opponent-model random`). The database check
is now a real one that loads and validates the file
([SKILLS.md:87](../SKILLS.md#L87)): it prints `455 hand types loaded and validated`. Nothing tests
the documents automatically, though; only `verify_course.py` checks the course.

**2. ✅ Fixed: AGENTS.md stated rules the code broke.** The spec forbade global state while
`app.py` kept the database in module-level globals; it described a four-field `HandScore`, Đĩ ties
"based on game configuration", strict `mypy` that nobody ran, a "game-theoretic solver", Monte Carlo
data, and budgets that weren't met. Now both sides moved: the code got an app factory, mypy and ruff
in CI and a faster evaluator, and the spec describes what is true. Its global-state rule now says
how the app obeys it:

📍 [`AGENTS.md:24`](../AGENTS.md#L24)
```
- **No Global Mutable State**: Do not use global variables to store game state or cached databases. State must be injected via constructors or parameters (Dependency Injection). The Flask app is built by `create_app(db=..., calling_model=..., config=...)`, which keeps its services in `app.extensions`; the module-level `app` object exists only as the entry point for gunicorn and `python app.py`.
```

The last stale phrase went in `a9d9ce9`. §4.2 used to say the 455 classes minimise "offline Monte
Carlo overhead", although the data is exact; it now gives the real saving:

📍 [`AGENTS.md:105`](../AGENTS.md#L105)
```
- Reducing $22,100 \rightarrow 455$ canonical keys cuts the offline work to $455 \times 18{,}424 \approx 8.4$ million exact showdowns and keeps the database below 100 KB.
```

*Worth knowing:* one budget was met by changing the spec rather than the code. A CLI run is now
budgeted at < 300 ms instead of 50 ms ([AGENTS.md:129](../AGENTS.md#L129)), with no test. That is
a legitimate choice (a fresh Python process can't start in 50 ms with these imports), but it is
worth knowing which kind of "met" it is.

**3. ✅ Fixed: "GTO" and "Monte Carlo" in the UI.** The subtitle said "GTO solver for Liêng",
so did the browser tab, and the specs footnote said "Monte Carlo". Now the subtitle is
"Expected-value solver for Liêng" ([i18n.js:8](../frontend/src/i18n.js#L8)), the tab
"Liêng Scope – EV solver" ([index.html:6](../frontend/index.html#L6)), and the footnote
"Exact enumeration, 455 canonical classes" ([i18n.js:42](../frontend/src/i18n.js#L42)). The text
the **backend** writes into the notes panel followed in `a9d9ce9`. The rule-based notes, which are
what you see without an API key, used to end with `3. **GTO Insight:**`; now the heading is
Vietnamese for "tactical assessment":

📍 [`backend/app.py:854`](../backend/app.py#L854)
```python
        f"3. **Nhận định chiến thuật:** {_reason_sentence(advice_rec, summary)}"
```

and the LLM prompt asks for "[Lời khuyên chiến thuật]" (tactical advice) instead of
"[Lời khuyên GTO]" ([app.py:559](../backend/app.py#L559)), so a real model isn't invited to write
the word either. That is what DESIGN.md asks: "no 'GTO'" ([DESIGN.md:88](../DESIGN.md#L88)). *Still
open:* no test pins it, so nothing stops the word from coming back (exercise 5 adds one).

**4. ✅ Fixed: BLOG.md numbers that didn't come from the code.** The Liêng frequency now reads
3.48% (768 / 22,100, [BLOG.md:22](../BLOG.md#L22)), and the dated note says the "10,000 simulated
games" experiment ([BLOG.md:29](../BLOG.md#L29)) has no code in the repo. Read the rest as a story:
it still says the team "ran the Monte Carlo code" ([BLOG.md:68](../BLOG.md#L68)).

**5. Mitigated: EXPERIMENT.md is a plan, not a record.** The dated note at the top now says so and
lists the differences (exact data, heads-up only, a five-element score tuple). The body is
unchanged: it numbers categories 1 = Sáp ([EXPERIMENT.md:45](../EXPERIMENT.md#L45)), the reverse of
the code; it plans a two-element score tuple ([EXPERIMENT.md:69](../EXPERIMENT.md#L69)), multi-way
games ([EXPERIMENT.md:75](../EXPERIMENT.md#L75)) and Monte Carlo convergence runs
([EXPERIMENT.md:102](../EXPERIMENT.md#L102)). Fine for a historical document, as long as nobody
reads it as a spec.

**6. ✅ Fixed: two small slips in the README.** "What it does" said the slow work takes "≈ 30 s",
while "Regenerating the data" says "≈ 10 s on one core" ([README.md:359](../README.md#L359)); 10 s
is what I measured, and since `a9d9ce9` both say it ([README.md:43](../README.md#L43)). The
configuration section also started with an orphaned table header just above the sentence that
introduces the real table, which rendered as an empty table; now the section opens with that
sentence ([README.md:451](../README.md#L451)). No test reads the README, so slips like these are
found only by reading it next to the code.

---

## 🧪 Try it

Run from `backend/` with the virtual environment active.

Classify a few hands, including all four edge cases:

```bash
python -c '
from src.evaluator import Hand
for s in ["2s 2h 2d", "Qs Kh Ad", "As 2h 3d", "Js Qh Qd", "9s 10h Kd", "Ks Ah 2d", "As Jh Jd", "9s 8h 2d"]:
    h = Hand.from_str(s)
    print(f"{s:10} -> {h.score.name:15} {h.score.category.name}")
'
```

Expected output:

```
2s 2h 2d   -> Sáp 2           SAP
Qs Kh Ad   -> Liêng Q-K-A     LIENG
As 2h 3d   -> Liêng A-2-3     LIENG
Js Qh Qd   -> Đĩ              DI
9s 10h Kd  -> 9 điểm          DIEM
Ks Ah 2d   -> 3 điểm          DIEM
As Jh Jd   -> 1 điểm          DIEM
9s 8h 2d   -> 9 điểm          DIEM
```

Reproduce the three hands of sections 3 and 4 under both opponent models:

```bash
python -c '
from src.db import WinRateDB
from src.calling_range import CallingRangeModel
from src.ev import calculate_ev, calculate_break_even_fold_equity
db = WinRateDB("data/winrates.json"); m = CallingRangeModel()
for cid in ("Q-K-A", "5-3-2", "K-Q-3"):
    w = db.get(cid).equity
    print(cid, w, m.equity(cid, 0.35), calculate_ev(100000, 50000, 0.35, w),
          calculate_break_even_fold_equity(100000, 50000, w))
'
```

Expected output (columns: id, equity vs random, equity vs callers at 35% folds, EV, break-even):

```
Q-K-A 0.9969 0.9952 132097.0 0.0
5-3-2 0.0024 0.0 2812.0 0.3312
K-Q-3 0.36 0.0108 49300.0 0.0
```

---

## 🏋️ Exercises

Exercises marked 🟡 or 🔴 change code. Undo them afterwards with `git checkout -- <file>`.

**🟢 1. Predict the winner.** Without running anything: (a) 2♠ 2♥ 2♦ vs Q♠ K♥ A♦; (b) A♠ 2♥ 3♦ vs
K♠ K♥ Q♦; (c) J♠ Q♥ Q♦ vs 9♠ 10♥ K♦; (d) K♠ A♥ 2♦ vs 5♠ 4♥ 3♦. Check with
`Hand.from_str(a) > Hand.from_str(b)`.

<details><summary>Solution</summary>

(a) 2-2-2: any Sáp beats any Liêng. (b) A-2-3: the weakest Liêng still beats K-K-Q, which is a Đĩ.
(c) J-Q-Q: Đĩ beats 9 points. (d) 5-4-3: it is a Liêng (3-4-5), while K-A-2 is only 3 points.
All four comparisons print `True` when you put the winner on the left.
</details>

**🟢 2. Predict an EV.** K-Q-3 against a random hand has `w = 0.36`. With `P = 100,000`,
`B = 50,000`, `f = 0.35`, what is the EV? Then: what does it become under the `range` model, where
`w = 0.0108`? Check both with `calculate_ev`.

<details><summary>Solution</summary>

Random: showdown part `0.36 × 200,000 − 50,000 = 22,000`; EV = `35,000 + 0.65 × 22,000 = 49,300`.
Range: `0.0108 × 200,000 − 50,000 = −47,840`; EV = `35,000 − 0.65 × 47,840 = 3,904`.
`calculate_ev(100000, 50000, 0.35, 0.36)` prints `49300.0` and
`calculate_ev(100000, 50000, 0.35, 0.0108)` prints `3904.0`. Still a raise, but only because the
folds pay for it.
</details>

**🟢 3. Predict the cost of skipping canonical hands.** The generator took about 10 s for 455
hands on one core. Roughly how long would it take if it evaluated all 22,100 hands one by one? Then
run the real generator, safely, into a scratch file and compare it with the committed one:
`python -m src.generator --workers 1 --output /tmp/winrates.json && cmp data/winrates.json /tmp/winrates.json && echo IDENTICAL`.

<details><summary>Solution</summary>

22,100 / 455 ≈ 48.6 times the work, so about 10 s × 48.6 ≈ 8 minutes. The generator prints
`Starting equity generation in Exact Combinatorial Enumeration across 1 workers...` and then
`Successfully generated database for 455 canonical hands -> /tmp/winrates.json`, and `cmp` finds
no difference: exact enumeration is deterministic. Without `--output` it would overwrite the
committed `backend/data/winrates.json` (from any folder: the default path is absolute since
October 2026); lesson 04 explains the details.
</details>

**🟡 4. Break a rule and watch the tests (and the data) object.** Make K-A-2 a Liêng: in
[evaluator.py:203](../backend/src/evaluator.py#L203) add the line `(2, 13, 14): 1,  # K-A-2` just
below the A-2-3 entry. Before running anything, predict what `python -m pytest -q` and
`python -m src.cli --hand "Ks Ah 2d"` will do.

<details><summary>Solution</summary>

Only two *rule* tests notice the rule itself: `python -m pytest tests/test_evaluator.py tests/test_hands.py -q`
gives `2 failed, 33 passed` (`test_ka2_wraparound_rejection`: K-A-2 must be Điểm;
`test_category_distribution`: there must be 12 Liêng classes). The whole suite doesn't even get
going: `Interrupted: 2 errors during collection`, because `test_api.py` and
`test_dynamic_scenarios.py` load the database when they are imported, and the loader now refuses
it. The CLI says why, and exits 1:

```
Cannot load the win-rate database: '…/backend/data/winrates.json': A-K-2 is recorded as DIEM x64, expected LIENG x64.
```

That is the stale-table cost of precomputation, caught at the door: `winrates.json` was computed
with the old rule, and since October 2026 `WinRateDB` compares every record with the classes the
current code generates (lesson 05). Before that check existed, the same change failed 4 of 93
tests and the app served the stale numbers. Undo with `git checkout -- backend/src/evaluator.py`.
</details>

**🟡 5. Pin the "no GTO" rule with a test (weak spot 3).** The word is gone from the backend's
notes ([app.py:588](../backend/app.py#L588)) and from the LLM prompt
([app.py:559](../backend/app.py#L559)), but no test would notice if it came back. Write one test in
`tests/test_api.py` that checks both texts, watch it pass, then put `**GTO Insight:**` back at
app.py:588 and watch it fail.

<details><summary>Solution</summary>

`test_api.py` already has what you need: `client` (no API key, so you get the rule-based notes),
`keyed_client` (a key, for tests that patch `requests.post`), `ANALYZE_PAYLOAD` and `_FakeResponse`.
Catch the prompt the way `test_analyze_uses_openrouter_when_a_key_is_set` does:

```python
def test_notes_make_no_gto_claim(client, keyed_client, monkeypatch):
    """DESIGN.md: no "GTO" (the tool computes EV, not an equilibrium)."""
    assert "GTO" not in client.post("/api/analyze", json=ANALYZE_PAYLOAD).get_json()["advice"]
    sent = {}

    def fake_post(url, headers, json, timeout):
        sent["prompt"] = json["messages"][1]["content"]
        return _FakeResponse(200, {"choices": [{"message": {"content": "Tố."}}]})

    monkeypatch.setattr(requests, "post", fake_post)
    keyed_client.post("/api/analyze", json=ANALYZE_PAYLOAD)
    assert "GTO" not in sent["prompt"]
```

`python -m pytest -q` now gives `173 passed`. With `3. **GTO Insight:** ` back in the fallback:
`1 failed, 46 passed` in `test_api.py`, `AssertionError: assert 'GTO' not in '**[Phân Tíc...a lợi nhuận.'`.
Put the fallback right and write `[Lời khuyên GTO]` into the prompt instead: the same test fails on
its second assert, `assert 'GTO' not in 'You are a W...hác đối thủ.'`. A test only for the fallback
would have missed that half. Undo with `git checkout -- backend/app.py backend/tests/test_api.py`.
</details>

**🔴 6. A real `python -m src.db` check.** The old SKILLS.md promised `python -m src.db --verify`,
which did nothing. Add a `__main__` block to [db.py](../backend/src/db.py) that loads the file given
on the command line (default: `DEFAULT_DB_PATH`), prints the number of classes and the multiplicity
total, and exits 1 with a message if loading fails. Check:
`python -m src.db data/winrates.json; echo $?` and `python -m src.db nope.json; echo $?`. The 172
tests, `ruff check .` and `mypy` must still pass.

<details><summary>Solution sketch</summary>

```python
if __name__ == "__main__":
    import sys

    try:
        db = WinRateDB(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB_PATH)
    except DatabaseError as err:
        print(f"FAILED: {err}", file=sys.stderr)
        sys.exit(1)
    total = sum(s.multiplicity for s in db.all_items().values())
    print(f"OK: {len(db)} classes, {total} combinations")
```

On the real file it prints `OK: 455 classes, 22100 combinations` and exits 0; on `nope.json`,
`FAILED: Database file 'nope.json' does not exist.` and exits 1. The block is short because
`WinRateDB` already validates everything (lesson 05): a verifier only has to report what `load`
decided. Undo with `git checkout -- backend/src/db.py`.
</details>

---

## ❓ Quiz

1. Name the four categories from strongest to weakest, with the number the code gives each.
2. Why is K-A-2 worth 3 points and A-J-J worth 1 point?
3. What is the difference between fold equity and showdown equity? Which one does the program
   compute, and which one must you supply?
4. Why does K-Q-3 have 36% equity under one opponent model and about 1% under the other?
5. Why does the project ship a 455-entry JSON file instead of comparing hands on each request, and
   what is the price of that choice?

<details><summary>Answers</summary>

1. Sáp (4) > Liêng (3) > Đĩ (2) > Điểm (1).
2. Neither is special. K-A-2 is not a Liêng because there is no wrap-around, so it scores
   0 + 1 + 2 = 3 points. A-J-J is not Đĩ because the Ace is not a face card, so it scores
   1 + 0 + 0 = 1 point.
3. Fold equity `f` is how often the opponent folds to your raise; you estimate it and pass it in.
   Showdown equity `w` is how often your hand wins when called; the program computes it (from
   `winrates.json` or the calling-range model).
4. Against a random hand, K-Q-3 beats many weak hands. Under the `range` model the opponent folds
   their weakest 35%, which are exactly the hands K-Q-3 beats, so the hands that call are mostly
   stronger.
5. Comparing every hand with every opponent is 8.4 million comparisons even after the 22,100 → 455
   reduction, about 10 s on one core. A lookup is about 0.1 µs. The price is that the file must be
   regenerated whenever the rules change. Since October 2026 a stale file no longer disagrees
   *silently*: the loader refuses it if a class's category or multiplicity has changed.
</details>

---

## Recap

- Liêng has four categories, Sáp > Liêng > Đĩ > Điểm, checked in that order. A-2-3 is the lowest
  Liêng, Q-K-A the highest, K-A-2 is 3 points, A-J-J is 1 point, and any Đĩ beats 9 points.
- The project answers one question: is raising `B` into a pot `P` profitable, given the
  opponent's fold rate `f` and your showdown equity `w`? `EV = f·P + (1 − f)·[w·(P + 2B) − B]`.
- Raising is about more than hand strength: 5-3-2 is a +2,812 raise at 35% folds.
- `random` vs `range` opponent models can change a medium hand's equity from 36% to about 1%.
- The slow part (8,382,920 comparisons, about 10 s on one core) runs once and is stored in
  `winrates.json`; requests only look up and do arithmetic. `create_app()` builds the online state
  once per app.
- Trust the code and its tests first. README, AGENTS.md, SKILLS.md and DESIGN.md were brought in
  line with the code on 2026-10-24 and are now reliable; BLOG.md and EXPERIMENT.md are history with
  a dated note on top.

**Next:** [01 — Errors and cards](01-errors-and-cards.md)
