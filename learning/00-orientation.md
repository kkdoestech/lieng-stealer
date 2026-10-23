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
| 1 | [README.md:88-149](../README.md#L88-L149) | "How it works": the ranking table, 22,100 → 455, the two equity models, the EV formula. |
| 2 | [AGENTS.md:29-82](../AGENTS.md#L29-L82) | The rules as a spec. Read it as the intended design, not as a description of the code. |
| 3 | [README.md:347-381](../README.md#L347-L381) | The project layout, one line per file. |
| 4 | [app.py:30-36](../backend/app.py#L30-L36) | The online half in seven lines: load the table, build the models, once. |
| 5 | [cli.py:272](../backend/src/cli.py#L272) | `main`, the terminal entry point you will run below. |
| 6 | [AGENTS.md:123-129](../AGENTS.md#L123-L129) | The performance budgets. Some are met, some are not (section 9). |

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
EV = f · P  +  (1 − f) · [ w · (P + 2B) − B ]          raise if and only if EV > 0
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
hands) and calls with the rest. The CLI defaults to `random`; the web page defaults to `range`.

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
   machine this course was written on, it took 25.19 s with 4 worker processes.

Every request after that is a dictionary lookup plus a little arithmetic. The whole online half is
set up in seven lines when the Flask app starts:

📍 [`backend/app.py:30-36`](../backend/app.py#L30-L36)
```python
# Initialize WinRateDB and the calling-range model at startup
DB_PATH = Path(__file__).resolve().parent / "data" / "winrates.json"
win_rate_db = WinRateDB()
if DB_PATH.is_file():
    win_rate_db.load(DB_PATH)
calling_model = CallingRangeModel()
range_finder = RangeFinder(win_rate_db, calling_model)
```

Load 455 records, build the calling-range tables, wrap both in a range finder: that is all the
server's state (module-level globals, which `AGENTS.md` forbids; see lesson
[10](10-flask-api.md)). One equity lookup took about 75 ns on the same machine.

### 6. A tour of the repository

```
lieng-stealer/
├── README.md  AGENTS.md  DESIGN.md  SKILLS.md  BLOG.md  EXPERIMENT.md  LICENSE
├── backend/
│   ├── app.py                 Flask JSON API: 6 routes                      lesson 10
│   ├── Procfile               gunicorn start command                        lesson 16
│   ├── requirements.txt       6 pinned packages                             lesson 16
│   ├── data/winrates.json     455 exact equities (generated)                lesson 04
│   ├── src/
│   │   ├── exceptions.py      LiengError and five subclasses                lesson 01
│   │   ├── evaluator.py       Card, Rank, Suit; HandScore, evaluate_hand    lessons 01, 02
│   │   ├── hands.py           22,100 → 455 canonical hands                  lesson 03
│   │   ├── generator.py       builds winrates.json (offline)                lesson 04
│   │   ├── db.py              WinRateDB: equity vs a random hand            lesson 05
│   │   ├── calling_range.py   CallingRangeModel: equity vs callers          lesson 06
│   │   ├── ev.py              EV, break-even, profitable zones              lesson 07
│   │   ├── range_finder.py    EV of all 455 hands, sorted                   lesson 08
│   │   └── cli.py             terminal report                               lesson 09
│   └── tests/                 10 test files, 93 tests                       lesson 15
└── frontend/                  React 19 + Vite 8 page                        lessons 12–14
    └── src/  main.jsx  App.jsx  i18n.js  format.js  *.css  *.test.js
```

Imports point one way only: `exceptions ← evaluator ← hands ← {generator, db, calling_range}`,
then `ev ← range_finder ← {cli, app}`. Nothing in `src/` imports Flask and `ev.py` imports nothing
from the project, so each lesson can study one file knowing only the earlier ones.

### 7. Your first run of every entry point

All commands run from `backend/` with the virtual environment active (see
[COURSE.md](COURSE.md#setup)), except `npm`, which runs from `frontend/`.

**The tests.** `python -m pytest -q` prints:

```
........................................................................ [ 77%]
.....................                                                    [100%]
93 passed in 4.14s
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
│ Opponent Model: folds at random (random)                                     │
│ Pure Bluff Break-Even Fold Equity: 33.3%                                     │
│ Final Pot (if called): 200,000                                               │
╰──────────────────────────────────────────────────────────────────────────────╯
   … the range overview and the per-category table …
╭────────────────────────── HAND EVALUATION & ACTION ──────────────────────────╮
│ Hand Evaluated: As Kh Qd (Liêng Q-K-A)                                       │
│ Canonical Class: Q-K-A (Liêng)                                               │
│ Showdown Equity: 99.69%                                                      │
│ Expected Value (EV): +132,097                                                │
│ Break-Even Fold Equity: 0.00%                                                │
│                                                                              │
│  >>> ACTION: RAISE / ALL-IN RECOMMENDED <<<                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
```

The overview in the middle says `Profitable Classes: 455 / 455`. With a fold rate of 35%, above
the 33.3% pure-bluff line, *every* hand is worth raising here.

**The API.** If the server is running (`python app.py`), ask it directly:

```bash
curl -s http://127.0.0.1:5000/health
```

```
{"classes_loaded":455,"database_loaded":true,"status":"healthy","version":"1.0.0"}
```

```bash
curl -s -X POST http://127.0.0.1:5000/api/evaluate -H "Content-Type: application/json" \
  -d '{"pot": 100000, "bet": 50000, "fold_equity": 0.35, "hand": "As Kh Qd"}'
```

```
{"bet":50000.0,"break_even_fold_equity":0.0,"canonical_id":"Q-K-A","category":"LIENG","equity_vs_random":0.9969,"ev":132097.0,"fold_equity":0.35,"hand":"As Kh Qd","is_profitable":true,"opponent_model":"random","pot":100000.0,"profitable_from_fold_equity":0.0,"recommended_action":"RAISE","showdown_equity":0.9969}
```

Same hand, same spot, same +132,097 as the CLI: both front doors call the same engine.

**The frontend tests.** `npm test` (from `frontend/`) ends with:

```
# tests 6
# suites 0
# pass 6
# fail 0
```

`npm run dev` then serves the page on <http://localhost:5173>. It solves the default spot as soon
as it loads, with the `range` model, and shows +131,876 for As Kh Qd (equity 0.9952, section 4).

**The generator** is the fourth entry point. You don't need to run it: the data is committed.
Exercise 3 shows how to run it safely.

### 8. Preview: one click, end to end

Lesson [11](11-request-trace.md) traces a click on "Run solver" through every layer. In short:

1. `handleSolve` in [App.jsx:50](../frontend/src/App.jsx#L50) sends `POST /api/solve`
   ([App.jsx:57](../frontend/src/App.jsx#L57)).
2. `solve_api` ([app.py:153](../backend/app.py#L153)) validates the numbers with
   `_parse_game_params` ([app.py:48](../backend/app.py#L48)).
3. The hand text becomes cards: `Hand.from_str` ([evaluator.py:394](../backend/src/evaluator.py#L394)).
4. The cards become a canonical id and a lookup: `get_by_cards`
   ([db.py:123](../backend/src/db.py#L123)) → `"Q-K-A"` → equity 0.9969.
5. `ev.py` turns the equity into EV and profitable fold zones ([app.py:179](../backend/app.py#L179)).
6. `range_finder.solve_range` scores all 455 hands ([app.py:196](../backend/app.py#L196)).
7. `jsonify` sends it back, and React draws the verdict, tables and the "where raising pays" bar.

### 9. The root documents, and how far to trust each

The repository has six Markdown files at the root. They were written at different times, and the
code has moved on since some of them. Here is what each one is good for today:

| File | What it is | Trust |
|------|-----------|-------|
| [README.md](../README.md) | Front page: rules, maths, CLI/API reference, test table | **High.** Updated with the code; its numbers (93 + 6 tests, ≈ 83 KB, the K-Q-3 zones) match real runs. |
| [AGENTS.md](../AGENTS.md) | The engineering spec: rules, data model, EV, budgets | **Medium.** The game rules (§3) and the EV formula (§5) are right. Several engineering rules are not what the code does (weak spot 2). |
| [DESIGN.md](../DESIGN.md) | Rules for the web UI (Ayu Dark colours, layout, copy) | **High** for the current UI. It is the rulebook for lesson [14](14-styling.md). |
| [SKILLS.md](../SKILLS.md) | A command cheat-sheet | **Low.** Written before most of the code; several commands fail or do nothing (weak spot 1). Use the README instead. |
| [BLOG.md](../BLOG.md) | The origin story, in Vietnamese | Background only. It still describes Monte Carlo simulation; the data is now exact. |
| [EXPERIMENT.md](../EXPERIMENT.md) | A two-student project proposal, in Vietnamese | Background only. A plan, not a description: Monte Carlo, "multi-way", a different category numbering. |

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
in `evaluator.py`, `winrates.json` keeps the old answers until you run the generator again
(exercise 4 shows this happening).

---

## Design decisions

- **Precompute instead of computing per request.** 8.4 million comparisons take about 25 s even
  spread over 4 processes. A lookup takes nanoseconds. The cost is one generated file that must be
  rebuilt whenever the rules change.
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
longer does. None of them breaks the program, but each one can waste an afternoon.

**1. SKILLS.md commands that fail or do nothing.**

📍 [`SKILLS.md:91`](../SKILLS.md#L91)
```
python -m src.cli solve --hand "As,Kh,Qd" --pot 100000 --bet 50000 --p-fold 0.35
```

The CLI has no subcommands, so this exits 2 with `unrecognized arguments: solve`. So do `range`
and `interactive` ([SKILLS.md:98](../SKILLS.md#L98), [:104](../SKILLS.md#L104)). Worse,
`python -m src.db --verify` ([SKILLS.md:77](../SKILLS.md#L77)) prints nothing and exits 0: `db.py`
has no `__main__` block, so it looks like a passed check and verifies nothing. Also stale:
PowerShell-only setup ([SKILLS.md:10-15](../SKILLS.md#L10-L15)); "colorama, numpy"
([SKILLS.md:22](../SKILLS.md#L22)), which [requirements.txt](../backend/requirements.txt) doesn't
have; five test files (there are ten); a "10,000 simulations" run
([SKILLS.md:65](../SKILLS.md#L65)) that, without `--monte-carlo`, runs the exact enumeration and
overwrites the committed file; `mypy` ([SKILLS.md:113](../SKILLS.md#L113)), which isn't installed.
*Fix:* rebuild SKILLS.md from the README's commands, or delete it.

**2. AGENTS.md states rules the code breaks.**

📍 [`AGENTS.md:24`](../AGENTS.md#L24)
```
- **No Global Mutable State**: Do not use global variables to store game state or cached databases. State must be injected via constructors or parameters (Dependency Injection).
```

Section 5 showed the cached database as a module-level global in `app.py`. More mismatches: §3.3
specifies a four-field `HandScore` ([AGENTS.md:80](../AGENTS.md#L80)), the code has six fields
(lesson 02); §3.2 decides Đĩ ties "based on game configuration" ([AGENTS.md:61](../AGENTS.md#L61)),
and there is no configuration; §2.1 asks for strict `mypy` ([AGENTS.md:17](../AGENTS.md#L17)),
which nobody runs; §1 says "game-theoretic solver" ([AGENTS.md:4](../AGENTS.md#L4)) while the
README's Limitations ([README.md:430](../README.md#L430)) rightly say "EV, not an equilibrium";
§1 and §4 still say Monte Carlo ([AGENTS.md:9](../AGENTS.md#L9), [:102](../AGENTS.md#L102)). Of
the §6 budgets, the lookup is met (about 75 ns vs 5 µs) but one hand evaluation (2.6–3.8 µs vs
1 µs) and a CLI run (about 0.2 s vs 50 ms) are not. *Fix:* change the code (lesson 17's capstones)
or mark these lines as goals.

**3. "GTO" and "Monte Carlo" in the UI.** The subtitle says "GTO solver for Liêng"
([i18n.js:8](../frontend/src/i18n.js#L8)), so does the browser tab
([index.html:6](../frontend/index.html#L6)), and the specs footnote says "Monte Carlo, canonical
classes" ([i18n.js:30](../frontend/src/i18n.js#L30)). Neither is true. *Fix:* two strings in each
language (lesson 13).

**4. BLOG.md numbers that don't come from the code.** The Liêng frequency is given as ≈ 3.26%
([BLOG.md:20](../BLOG.md#L20)); it is 768 / 22,100 = 3.48% (lesson 03). A "10,000 simulated
games" experiment ([BLOG.md:27](../BLOG.md#L27)) has no code in the repo. Read it as a story.

**5. EXPERIMENT.md is a plan, not a record.** It numbers categories 1 = Sáp
([EXPERIMENT.md:43](../EXPERIMENT.md#L43)), the reverse of the code; it plans a two-element score
tuple ([EXPERIMENT.md:67](../EXPERIMENT.md#L67)), multi-way games
([EXPERIMENT.md:73](../EXPERIMENT.md#L73)) and Monte Carlo convergence runs
([EXPERIMENT.md:100](../EXPERIMENT.md#L100)). The code is heads-up only and exact.

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

**🟢 3. Predict the cost of skipping canonical hands.** The generator took about 25 s for 455
hands. Roughly how long would it take if it evaluated all 22,100 hands one by one? Then run the
real generator, safely, into a scratch file and compare it with the committed one:
`python -m src.generator --output /tmp/winrates.json && cmp data/winrates.json /tmp/winrates.json && echo IDENTICAL`.

<details><summary>Solution</summary>

22,100 / 455 ≈ 48.6 times the work, so about 25 s × 48.6 ≈ 20 minutes. The generator prints
`Starting equity generation in Exact Combinatorial Enumeration across 4 workers...` and then
`Successfully generated database for 455 canonical hands -> /tmp/winrates.json`, and `cmp` finds
no difference: exact enumeration is deterministic. Never run it without `--output` from a
different folder; lesson 04 explains why.
</details>

**🟡 4. Break a rule and watch the tests (and the data) object.** Make K-A-2 a Liêng: in
[evaluator.py:196](../backend/src/evaluator.py#L196) add the line `(2, 13, 14): 1,  # K-A-2` just
below the A-2-3 entry. Before running `python -m pytest -q`, predict which kinds of test will fail.

<details><summary>Solution</summary>

`4 failed, 89 passed`:

```
FAILED tests/test_calling_range.py::TestCallingRangeModel::test_zero_fold_matches_exact_enumeration
FAILED tests/test_calling_range.py::TestCallingRangeModel::test_medium_hands_regression
FAILED tests/test_evaluator.py::TestLiengHierarchy::test_ka2_wraparound_rejection
FAILED tests/test_hands.py::TestCanonicalHandEngine::test_category_distribution
```

Two failures are rule tests (K-A-2 must be Điểm; there must be 12 Liêng classes). The two
calling-range failures are the interesting ones: the model now ranks hands with the new rule, but
`winrates.json` was computed with the old one. That is the stale-table cost of precomputation.
Undo with `git checkout -- backend/src/evaluator.py`.
</details>

**🟡 5. Fix a stale command.** Rewrite [SKILLS.md:91](../SKILLS.md#L91) so that it works, and run
it. Which option name did SKILLS.md get right?

<details><summary>Solution</summary>

`python -m src.cli --hand "As,Kh,Qd" --pot 100000 --bet 50000 --p-fold 0.35`. Only the `solve`
word was wrong: `--p-fold` is a real alias of `--fold-equity`, and commas are accepted between
cards. It prints the same report as section 7, ending in `ACTION: RAISE / ALL-IN RECOMMENDED`.
Undo with `git checkout -- SKILLS.md`.
</details>

**🔴 6. Make `python -m src.db --verify` real.** Add a `__main__` block to
[db.py](../backend/src/db.py) that loads the file given on the command line and prints the number
of classes and the multiplicity total, exiting 1 with a message if loading fails. Check:
`python -m src.db data/winrates.json` and `python -m src.db nope.json; echo $?`. The 93 tests must
still pass.

<details><summary>Solution sketch</summary>

```python
if __name__ == "__main__":
    import sys
    try:
        db = WinRateDB(sys.argv[1] if len(sys.argv) > 1 else "data/winrates.json")
    except DatabaseError as err:
        print(f"FAILED: {err}", file=sys.stderr)
        sys.exit(1)
    total = sum(s.multiplicity for s in db.all_items().values())
    print(f"{len(db)} classes, {total} combinations")
```

On the real file it prints `455 classes, 22100 combinations`. A real verifier would also check
those two numbers and fail if they differ (lesson 05, weak spots). Undo with
`git checkout -- backend/src/db.py`.
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
   reduction, about 25 s. A lookup is nanoseconds. The price is that the file must be regenerated
   whenever the rules change, or it silently disagrees with the code.
</details>

---

## Recap

- Liêng has four categories, Sáp > Liêng > Đĩ > Điểm, checked in that order. A-2-3 is the lowest
  Liêng, Q-K-A the highest, K-A-2 is 3 points, A-J-J is 1 point, and any Đĩ beats 9 points.
- The project answers one question: is raising `B` into a pot `P` profitable, given the
  opponent's fold rate `f` and your showdown equity `w`? `EV = f·P + (1 − f)·[w·(P + 2B) − B]`.
- Raising is about more than hand strength: 5-3-2 is a +2,812 raise at 35% folds.
- `random` vs `range` opponent models can change a medium hand's equity from 36% to about 1%.
- The slow part (8,382,920 comparisons, about 25 s) runs once and is stored in `winrates.json`;
  requests only look up and do arithmetic.
- Trust the code and README first, DESIGN.md for the UI, AGENTS.md for intent, and SKILLS.md,
  BLOG.md and EXPERIMENT.md only as history.

**Next:** [01 — Errors and cards](01-errors-and-cards.md)
