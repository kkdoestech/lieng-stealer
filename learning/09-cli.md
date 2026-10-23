# Lesson 09 — The command-line interface

> **Goal:** understand how `cli.py` turns command-line flags (or five typed answers) into the same
> EV report the web page shows, how it prints with or without `rich`, and how it signals errors.
> **Files:** [`backend/src/cli.py`](../backend/src/cli.py), [`backend/tests/test_cli.py`](../backend/tests/test_cli.py).
> **Time:** ~45 min. **Before this:** [08 — The range finder](08-range-finder.md).

---

## Where this fits

```
   terminal: python -m src.cli --pot … --hand …        (or no flags: five questions)
                         │
              ┌──────────▼───────────┐
              │  cli.py (this lesson)│  argparse → run_solver → four renderers
              └──────────┬───────────┘
        ┌────────────────┼──────────────────┬───────────────────┐
        ▼                ▼                  ▼                   ▼
   db.py WinRateDB   calling_range.py   range_finder.py      ev.py
   (lesson 05)       (only for "range") (all 455 hands)      (your hand's EV)
```

`cli.py` is the second front door to the engine, next to the Flask API (lesson 10). Both call the
same modules, so the CLI is the quickest way to check a number without a browser. It holds no
maths of its own. What is interesting is *how* it prints and *how* it fails.

---

## Reading order

| # | Location | What to look for |
|---|----------|------------------|
| 1 | [cli.py:13-18](../backend/src/cli.py#L13-L18) | A side effect at import time: stdout is switched to UTF-8. |
| 2 | [cli.py:28-43](../backend/src/cli.py#L28-L43) | Model descriptions, and `rich` imported *optionally*. |
| 3 | [cli.py:46-48](../backend/src/cli.py#L46-L48) | `format_currency`: thousands separators, decimals only when needed. |
| 4 | [cli.py:51-114](../backend/src/cli.py#L51-L114) | The banner and overview renderers: a `rich` branch and a plain `print` branch each. |
| 5 | [cli.py:117-162](../backend/src/cli.py#L117-L162) | Your hand: equity source, EV, "n/a (range model)". |
| 6 | [cli.py:165-220](../backend/src/cli.py#L165-L220) | The category table, with hard-coded totals. |
| 7 | [cli.py:223-247](../backend/src/cli.py#L223-L247) | `run_solver`: the whole pipeline in 25 lines. |
| 8 | [cli.py:250-269](../backend/src/cli.py#L250-L269) | `interactive_mode`: five `input()` prompts. |
| 9 | [cli.py:272-324](../backend/src/cli.py#L272-L324) | `main`: argparse, interactive or not, exit code 2. |
| 10 | [test_cli.py](../backend/tests/test_cli.py) | Six tests: `capsys`, `SystemExit`, and a fake keyboard. |

---

## Walkthrough

### 1. Starting it: why `python -m src.cli`

Run it from `backend/`:

```bash
python -m src.cli --pot 100000 --bet 100000 --fold-equity 0.35 --hand "Ks Qh 3d"
```

The `-m` matters. `cli.py` imports its neighbours as `from src.db import WinRateDB`, so Python
must find a package called `src`. With `-m`, Python puts the current directory (`backend/`) on
the import path, and `src/` is found there. Running the file directly puts `backend/src/` on the
path instead, and the import fails:

```
$ python src/cli.py --pot 1
ModuleNotFoundError: No module named 'src'
```

The default `--db data/winrates.json` is a relative path, but it also works from other
directories, because `WinRateDB.load` falls back to a path next to the backend
([db.py:72-79](../backend/src/db.py#L72-L79), lesson 05).

### 2. `main`: flags, defaults and the interactive switch

[cli.py:274-302](../backend/src/cli.py#L274-L302) declares six options: `--pot`, `--bet`,
`--fold-equity` (with the alias `--p-fold`), `--hand`, `--db` and `--opponent-model`. The
choices for the last one come from the enum itself, `[m.value for m in OpponentModel]`, so a new
model would appear in `--help` automatically. Then:

📍 [`backend/src/cli.py:304-324`](../backend/src/cli.py#L304-L324)
```python
    args = parser.parse_args(argv)

    if args.pot is None and args.bet is None and args.fold_equity is None and args.hand is None:
        interactive_mode(args.db)
    else:
        pot = args.pot if args.pot is not None else 100000.0
        bet = args.bet if args.bet is not None else 50000.0
        fold_equity = args.fold_equity if args.fold_equity is not None else 0.35
        try:
            run_solver(
                pot=pot,
                bet_size=bet,
                fold_equity=fold_equity,
                hand_str=args.hand,
                db_path=args.db,
                opponent_model=OpponentModel(args.opponent_model),
            )
        except (LiengError, ValueError) as err:
            # Bad hand text or out-of-range numbers: a clear message and the usage-error exit code
            print(f"Invalid input: {err}", file=sys.stderr)
            sys.exit(2)
```

- **`argv` is a parameter.** `main(argv=None)` lets argparse read `sys.argv` in real use, while a
  test can call `main(["--pot", "100000"])` directly. That one choice is what makes
  `test_cli.py` possible.
- **The switch is "none of the four game flags".** `--db` and `--opponent-model` don't count, so
  `python -m src.cli --opponent-model range` opens the prompts, and pressing Enter at the model
  question gives `random`: the flag is silently ignored (`interactive_mode` only receives `--db`).
- **Defaults are filled in by hand.** The options default to `None` so that the code can tell
  "not given" from "given". The real defaults, 100,000 / 50,000 / 0.35, then appear here, again in
  `interactive_mode`, and a third time in `app.py` (weak spot 6).
- **Errors become exit code 2.** `LiengError` covers bad cards and a missing database;
  `ValueError` covers the guards in `ev.py` (lesson 07). Both print one line to **stderr**, not a
  traceback.

### 3. Exit codes, verified

| Command (from `backend/`) | Printed | Exit |
|---------------------------|---------|------|
| `python -m src.cli --pot 100000 --hand "As Kh Qd"` | the report | 0 |
| `python -m src.cli --pot -5` | `Invalid input: Pot must be strictly positive, got -5.0.` | 2 |
| `python -m src.cli --fold-equity 1.5` | `Invalid input: Fold equity must be between 0.0 and 1.0, got 1.5.` | 2 |
| `python -m src.cli --hand "As Xh Kd"` | **48 lines of report**, then `Invalid input: Invalid rank 'X'. …` | 2 |
| `python -m src.cli --pot abc` | argparse usage + `error: argument --pot: invalid float value: 'abc'` | 2 |
| `python -m src.cli --opponent-model psychic` | usage + `invalid choice: 'psychic' (choose from 'random', 'range')` | 2 |
| `python -m src.cli --pot 1 --db nowhere.json` | `Invalid input: Database file 'nowhere.json' does not exist.` | 2 |
| interactive, hand `Xx Kh Qd` | `Exiting session: Invalid rank 'X'. …` | **0** |
| interactive, stdin closed | `EOFError` traceback | **1** |

Exit code 2 is the Unix convention for "you used the command wrongly", and argparse already
uses it for its own errors, so `cli.py` matches it. The last three rows are the weak spots: a
missing file is not "invalid input", and the interactive mode never reports failure.

### 4. `run_solver`: the whole pipeline

📍 [`backend/src/cli.py:223-247`](../backend/src/cli.py#L223-L247)
```python
def run_solver(
    pot: float,
    bet_size: float,
    fold_equity: float,
    hand_str: str | None = None,
    db_path: str = "data/winrates.json",
    opponent_model: OpponentModel = OpponentModel.RANDOM,
) -> None:
    """Execute the range solver pipeline and render visual reports."""
    db = WinRateDB(db_path)
    # Build the calling-range tables (~50 ms) only when the range model is requested
    calling_model = CallingRangeModel() if opponent_model is OpponentModel.RANGE else None
    finder = RangeFinder(db, calling_model)

    be_bluff = calculate_break_even_fold_equity(pot, bet_size, win_rate_when_called=0.0)
    records = finder.solve_range(pot, bet_size, fold_equity, opponent_model)
    profitable = [r for r in records if r.is_raise_profitable]
    coverage = finder.calculate_range_coverage(profitable)

    render_banner(pot, bet_size, fold_equity, be_bluff, opponent_model)
    render_tactical_overview(records, coverage)
    render_categorized_heatmap(records)

    if hand_str:
        render_single_hand_decision(hand_str, db, pot, bet_size, fold_equity, calling_model)
```

Unlike `app.py`, the CLI builds its objects *inside a function* and passes them along. Nothing is
global except the `rich` console. Every run loads the 455 records and, under the range model,
builds the card-removal tables of lesson 06. Measured on the machine this course was written on
(your numbers will differ): building `CallingRangeModel()` took 54–67 ms, loading the database
2–4 ms, and one `solve_range` 1–2 ms.

Read the order of the four renderers. **Your hand is printed last**, and it is also the first
place where the hand text is parsed (`Hand.from_str` at [cli.py:130](../backend/src/cli.py#L130)).
That is why a typo in `--hand` costs you 48 lines of report before the error appears
(weak spot 1).

`be_bluff` is the pure-bluff break-even of lesson 07, `B / (P + B)`: 33.3% for a half-pot bet,
50.0% for a pot-sized one.

### 5. Your hand: the same choice as the API

📍 [`backend/src/cli.py:130-141`](../backend/src/cli.py#L130-L141)
```python
    hand = Hand.from_str(hand_str)
    stats = db.get_by_cards(hand.cards)
    canonical_id = to_canonical(hand.cards).canonical_id
    equity = calling_model.equity(canonical_id, fold_equity) if calling_model else stats.equity
    ev_result = evaluate_action(pot, bet_size, fold_equity, equity)
    # Under the range model EV is not monotonic in fold equity, so no single break-even exists
    break_even_text = (
        f"{ev_result.break_even_fold_equity * 100:.2f}%" if calling_model is None else "n/a (range model)"
    )

    status_color = "green" if ev_result.is_profitable else "red"
    action_text = "RAISE / ALL-IN RECOMMENDED" if ev_result.is_profitable else "CHECK / FOLD RECOMMENDED"
```

Line 133 is the CLI's version of `app.py`'s `_equity_function`
([app.py:81-85](../backend/app.py#L81-L85)): the calling-range equity if a model exists,
otherwise the random-hand equity from the database. The CLI uses the *presence* of
`calling_model` as the switch, because `run_solver` only builds one for the range model. The CLI
does not compute profitable fold zones; the API does (lesson 07).

Here is the same medium hand under both models, the case `test_cli.py` pins (K-Q-3, pot-sized
bet, 35% folds). The tail of each report:

```
--opponent-model random                          --opponent-model range
Hand Evaluated: Ks Qh 3d (3 điểm)                Hand Evaluated: Ks Qh 3d (3 điểm)
Canonical Class: K-Q-3 (Điểm)                    Canonical Class: K-Q-3 (Điểm)
Showdown Equity: 36.00%                          Showdown Equity: 1.08%
Expected Value (EV): +40,200                     Expected Value (EV): -27,894
Break-Even Fold Equity: 0.00%                    Break-Even Fold Equity: n/a (range model)
>>> ACTION: RAISE / ALL-IN RECOMMENDED <<<       >>> ACTION: CHECK / FOLD RECOMMENDED <<<
```

And the overview panel above it:

| Line | random | range |
|------|--------|-------|
| Pure Bluff Break-Even Fold Equity | 50.0% | 50.0% |
| Profitable Classes | 387 / 455 | 250 / 455 |
| Combos in Range | 18,708 / 22,100 | 12,060 / 22,100 |
| Total Range Coverage | 84.65% | 54.57% |
| Highest EV Hand | A-A-A (EV: +165,000) | A-A-A (EV: +165,000) |
| Threshold Hand (EV > 0) | K-8-3 (EV: +361.50) | K-Q-4 (EV: +420) |

Two details of `format_currency` ([cli.py:46-48](../backend/src/cli.py#L46-L48)) show up here:
`+361.50` has decimals because the EV is not a whole number, while `+420` has none.

### 6. `rich` if available, `print` if not

📍 [`backend/src/cli.py:33-43`](../backend/src/cli.py#L33-L43)
```python
try:
    from rich import box
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    HAS_RICH = True
    _console = Console(legacy_windows=False)
except ImportError:
    HAS_RICH = False
    _console = None
```

`rich` draws the boxes and colours. It is in `requirements.txt`, but the CLI still works without
it: every renderer starts with `if HAS_RICH:` and has an `else:` branch of plain `print` calls
(for example [cli.py:59-80](../backend/src/cli.py#L59-L80)). You can see the fallback without
uninstalling anything, by hiding the package before the import (see 🧪 Try it). The plain
version of the range run above:

```
--- TACTICAL SOLVER OVERVIEW ---
 Profitable Classes:   250 / 455
 Combos in Range:      12,060 / 22,100 combinations
 Range Coverage:       54.57%
 Highest EV Hand:      A-A-A (EV: +165,000)
 Threshold Hand:       K-Q-4 (EV: +420)
--------------------------------


--- CATEGORY BREAKDOWN ---
 SAP  :  13 /  13 classes profitable
 LIENG:  12 /  12 classes profitable
 DI   :   6 /   6 classes profitable
 DIEM : 219 / 424 classes profitable
--------------------------
```

The two branches are not the same report. The plain category table has one column instead of
five, and the plain hand panel prints `Expected Value: 40,200` without the `+`
([cli.py:159](../backend/src/cli.py#L159)).

`rich` is also the slowest thing the CLI does. Importing it took about 50 ms on the course
machine, which is the whole CLI budget in AGENTS.md §6 on its own (lesson 15).

### 7. The category table and its hard-coded totals

[cli.py:184-189](../backend/src/cli.py#L184-L189) stores the number of combinations per category
as literals: 52, 768, 144 and 21,136. They are correct (lesson 03 derives them, and
[test_api.py:133](../backend/tests/test_api.py#L133) pins the same numbers through the API), but
`app.py` computes them from the records instead
([`_category_breakdown`, app.py:118-129](../backend/app.py#L118-L129)). Two implementations of
one table is a classic way for a CLI and an API to drift apart (exercise 6).

### 8. Interactive mode, and how the test types for you

📍 [`backend/src/cli.py:250-269`](../backend/src/cli.py#L250-L269)
```python
def interactive_mode(db_path: str = "data/winrates.json") -> None:
    """Run interactive CLI prompt session."""
    print("\n--- LIÊNG STEALER: INTERACTIVE SOLVER ---")
    try:
        pot_str = input("Enter Pot Size (e.g. 100000): ").strip()
        pot = float(pot_str) if pot_str else 100000.0

        bet_str = input("Enter Bet/Raise Size (e.g. 50000): ").strip()
        bet = float(bet_str) if bet_str else 50000.0

        fe_str = input("Enter Opponent Fold Probability [0.0 - 1.0] (e.g. 0.35): ").strip()
        fold_equity = float(fe_str) if fe_str else 0.35

        model_str = input("Opponent folds 'random' or 'range' (weakest hands first)? [random]: ").strip()
        opponent_model = OpponentModel(model_str.lower()) if model_str else OpponentModel.RANDOM

        hand_str = input("Enter your hand (e.g. 'As Kh Qd' or press Enter to skip): ").strip()
        run_solver(pot, bet, fold_equity, hand_str=hand_str or None, db_path=db_path, opponent_model=opponent_model)
    except (ValueError, LiengError, KeyboardInterrupt) as err:
        print(f"\nExiting session: {err}")
```

An empty answer means "use the default". The `except` turns every expected failure into one
line: `Exiting session: could not convert string to float: 'abc'` for a bad pot, or
`Exiting session: 'psychic' is not a valid OpponentModel` for a bad model. Then the function
returns normally, so the process exits with 0. `EOFError` (stdin closed, for example
`printf '' | python -m src.cli`) is not in the list and escapes as a traceback.

How do you test something that reads the keyboard? You replace `input`:

📍 [`backend/tests/test_cli.py:35-50`](../backend/tests/test_cli.py#L35-L50)
```python
def _answer_prompts(monkeypatch, answers):
    """Feed interactive-mode prompts from a list instead of the keyboard."""
    replies = iter(answers)
    monkeypatch.setattr("builtins.input", lambda _prompt: next(replies))


def test_interactive_mode_asks_for_opponent_model(monkeypatch, capsys):
    _answer_prompts(monkeypatch, ["100000", "100000", "0.35", "range", "Ks Qh 3d"])
    main([])
    assert "CHECK / FOLD RECOMMENDED" in capsys.readouterr().out


def test_interactive_mode_reports_invalid_hand(monkeypatch, capsys):
    _answer_prompts(monkeypatch, ["100000", "100000", "0.35", "", "Xx Kh Qd"])
    main([])
    assert "Exiting session: Invalid rank 'X'" in capsys.readouterr().out
```

- `monkeypatch.setattr("builtins.input", …)` swaps the built-in `input` for a lambda that hands
  out the next answer. pytest puts the real one back after the test.
- `main([])` passes an empty argument list, so none of the four flags is set and `main` goes
  interactive. (Calling `main()` would read pytest's own `sys.argv`.)
- `capsys.readouterr().out` returns everything printed to stdout during the test, and `.err` returns
  stderr. The exit-code test ([test_cli.py:27-32](../backend/tests/test_cli.py#L27-L32)) catches
  `SystemExit` with `pytest.raises` and checks `.code == 2` and `"Invalid input"` in `.err`.

---

## 💡 Concept: argparse in five lines

```python
parser = argparse.ArgumentParser(description="…")
parser.add_argument("--pot", type=float, default=None)          # "--pot 5" → args.pot == 5.0
parser.add_argument("--fold-equity", "--p-fold", dest="fold_equity", type=float)  # two spellings
parser.add_argument("--opponent-model", choices=["random", "range"], default="random")
args = parser.parse_args(argv)                                    # argv=None → read sys.argv
```

`type=float` converts the text and rejects `abc` for you; `choices` rejects anything else. Both
print the usage and exit with code 2. `--help` is generated from the `help=` strings.

## 💡 Concept: `sys.exit(2)` is an exception

`sys.exit(code)` raises `SystemExit(code)`. If nothing catches it, Python stops and the shell
sees `code` as the exit status (`echo $?`). That is why a test can write
`with pytest.raises(SystemExit) as exc: main(argv)` and then check `exc.value.code == 2`, and why
an over-broad `except BaseException:` would swallow the exit.

---

## Design decisions

- **Presentation only.** `cli.py` calls `WinRateDB`, `CallingRangeModel`, `RangeFinder` and
  `evaluate_action`, then prints. It never re-implements EV. If the CLI and the web UI disagree,
  the bug is in one of the two front ends, not in the engine.
- **Objects are built per run.** Unlike `app.py`, nothing is created at import time except the
  console. The cost is paid on every command (about 0.1–0.2 s in total), which is fine for a tool
  you run by hand.
- **The range model is opt-in, and the default is random.** `--opponent-model` defaults to
  `random`, which keeps old commands producing old answers
  ([test_cli.py:17](../backend/tests/test_cli.py#L17) pins it). The web UI chose the opposite
  default (lesson 13).
- **`rich` is optional.** The fallback costs duplicated code in every renderer, but the tool keeps
  working on a minimal install. The alternative, a hard dependency, would remove half the module.

---

## ⚠️ Weak spots

1. **A bad `--hand` is reported after the whole report.** [cli.py:242-247](../backend/src/cli.py#L242-L247):
   the hand is parsed last, so `--hand "As Xh Kd"` prints 48 lines and then fails with exit
   code 2. A script reading stdout sees a full, plausible report from a failed command. *Fix:*
   parse the hand at the top of `run_solver` (exercise 4).
2. **Interactive mode always "succeeds".** [cli.py:268-269](../backend/src/cli.py#L268-L269) prints
   `Exiting session: …` and returns, so the exit code is 0 after an error. `EOFError` is not caught
   at all (traceback, exit code 1). *Fix:* exit with 2 and add `EOFError` (exercise 5).
3. **Hard-coded totals.** The per-category combos at [cli.py:184-189](../backend/src/cli.py#L184-L189)
   and "22,100" at [:101](../backend/src/cli.py#L101) and [:110](../backend/src/cli.py#L110).
   `app.py` computes the same numbers from the records. *Fix:* sum `multiplicity` per category
   (exercise 6), or share `_category_breakdown`.
4. **A missing database is called "Invalid input".** `DatabaseError` is a `LiengError`
   ([exceptions.py:24](../backend/src/exceptions.py#L24)), so [cli.py:321-324](../backend/src/cli.py#L321-L324)
   reports a missing file as a usage error with exit code 2. *Fix:* catch `DatabaseError` first and
   exit with a different code and message.
5. **Import-time side effects, and a swallowed exception.** [cli.py:14-18](../backend/src/cli.py#L14-L18)
   reconfigures `sys.stdout` when the module is imported, inside `except Exception: pass`. AGENTS.md
   §2.1 says "never silently swallow exceptions". [cli.py:40](../backend/src/cli.py#L40) also creates
   a module-level console. *Fix:* move both into `main()`.
6. **Defaults written three times.** 100,000 / 50,000 / 0.35 appear at
   [cli.py:255-261](../backend/src/cli.py#L255-L261), [cli.py:309-311](../backend/src/cli.py#L309-L311)
   and [app.py:55-57](../backend/app.py#L55-L57). *Fix:* one set of constants, imported by both.
7. **Two different reports.** The plain fallback has a smaller category table
   ([cli.py:214-220](../backend/src/cli.py#L214-L220)) and no `+` on a positive EV
   ([:159](../backend/src/cli.py#L159)). No test runs the fallback. *Fix:* build the lines once and
   let `rich` only decorate them.
8. **Duplicated logic with the API.** The equity choice ([cli.py:133](../backend/src/cli.py#L133) vs
   [app.py:81-85](../backend/app.py#L81-L85)) and the category table exist twice. The CLI has no
   profitable fold zones, so for K-Q-3 it says "n/a" where the web UI shows two zones.
9. **"Game-Theoretic Solver".** The `--help` description ([cli.py:274](../backend/src/cli.py#L274))
   promises game theory. README's Limitations section is right: this is an EV calculation against
   an assumed fold rate, not an equilibrium.

---

## 🧪 Try it

Run from `backend/` with the virtual environment active (see [COURSE.md](COURSE.md#setup)).

```bash
python -m pytest tests/test_cli.py -q
```

```
......                                                                   [100%]
6 passed in 0.24s
```

The medium hand under the range model (the last lines of the report):

```bash
python -m src.cli --pot 100000 --bet 100000 --fold-equity 0.35 --hand "Ks Qh 3d" --opponent-model range | tail -8
```

```
│ Hand Evaluated: Ks Qh 3d (3 điểm)                                            │
│ Canonical Class: K-Q-3 (Điểm)                                                │
│ Showdown Equity: 1.08%                                                       │
│ Expected Value (EV): -27,894                                                 │
│ Break-Even Fold Equity: n/a (range model)                                    │
│                                                                              │
│  >>> ACTION: CHECK / FOLD RECOMMENDED <<<                                    │
╰──────────────────────────────────────────────────────────────────────────────╯
```

Watch weak spot 1 happen, and count the lines:

```bash
python -m src.cli --pot 100000 --bet 50000 --fold-equity 0.35 --hand "As Xh Kd" | wc -l; echo "exit=${PIPESTATUS[0]}"
```

```
Invalid input: Invalid rank 'X'. Must be 2-10, T, J, Q, K, or A.
48
exit=2
```

See the plain fallback without uninstalling `rich` (setting a module to `None` in `sys.modules`
makes its import raise `ImportError`):

```bash
python -c '
import sys; sys.modules["rich"] = None
from src.cli import main, HAS_RICH
print("HAS_RICH =", HAS_RICH)
main(["--pot", "100000", "--bet", "100000", "--fold-equity", "0.35", "--hand", "Ks Qh 3d", "--opponent-model", "range"])
' | head -3
```

```
HAS_RICH = False
============================================================
 LIÊNG STEALER - GAME STATE BANNER
```

Time a whole command (machine-dependent; on the course machine it was 0.11–0.12 s for the
random model and 0.17–0.22 s for the range model):

```bash
time python -m src.cli --pot 100000 --bet 50000 --fold-equity 0.35 --hand "As Kh Qd" --opponent-model range > /dev/null
```

---

## 🏋️ Exercises

Exercises marked 🟡 or 🔴 change code. Undo them afterwards with `git checkout -- <file>`.

**🟢 1. Predict.** `python -m src.cli --bet 100000`. Interactive or not? Which pot and fold
rate are used, and how many classes are profitable? Check by running it.

<details><summary>Solution</summary>

Not interactive: `--bet` is one of the four game flags. The pot defaults to 100,000 and the fold
rate to 0.35, with the random model. That is the pot-sized-bet case from section 5:
`Profitable Classes: 387 / 455`, coverage 84.65%, threshold hand K-8-3. No hand panel is printed.
</details>

**🟢 2. Predict.** `python -m src.cli --hand "As As Qd"`. What appears on stderr, how many lines
appear on stdout, and what is the exit code?

<details><summary>Solution</summary>

`Invalid input: A Liêng hand cannot have duplicate cards.` on stderr, 48 lines of report on stdout
(`… 2>/dev/null | wc -l`), exit code 2. The duplicate check lives in `Hand.__post_init__`
([evaluator.py:382-386](../backend/src/evaluator.py#L382-L386)) and raises
`InvalidHandSizeError`, a `LiengError`, so `main` catches it. It still happens after the report,
because the hand is parsed last.
</details>

**🟢 3. Predict.** In interactive mode you press Enter three times, type `range`, then press Enter
again. What runs, and what is the exit code?

<details><summary>Solution</summary>

The defaults (100,000 / 50,000 / 0.35), the range model, and no hand. The report shows
`Opponent Model: folds weakest hands first (range)` and `Profitable Classes: 455 / 455`, since a
half-pot bet at 35% folds is above the 33.3% bluff break-even, so every hand is +EV. No hand panel,
exit code 0. Check with `printf '\n\n\nrange\n\n' | python -m src.cli`.
</details>

**🟡 4. Fail before printing.** Make `--hand "As Xh Kd"` print nothing on stdout. Check: the
`wc -l` command from 🧪 Try it prints `0`, and `python -m pytest tests/test_cli.py -q` stays green.

<details><summary>Solution</summary>

Validate the hand at the top of `run_solver`, before anything is rendered:

```python
    """Execute the range solver pipeline and render visual reports."""
    if hand_str:
        Hand.from_str(hand_str)  # fail before anything is printed
    db = WinRateDB(db_path)
```

All 6 CLI tests still pass and stdout is empty. A cleaner version parses once and passes the
`Hand` object to `render_single_hand_decision` instead of the string.
</details>

**🟡 5. Make interactive errors visible to the shell.** Exit with code 2 on errors, catch
`EOFError`, and keep Ctrl+C quiet. Which existing test breaks, and how do you fix it?

<details><summary>Solution</summary>

```python
    except (ValueError, LiengError, EOFError) as err:
        print(f"\nExiting session: {err}")
        sys.exit(2)
    except KeyboardInterrupt:
        print("\nExiting session.")
```

`test_interactive_mode_reports_invalid_hand` now fails with `SystemExit: 2`: it called `main([])`
and expected a normal return. Wrap the call:

```python
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2
```

With both changes all 93 tests pass, and `printf '' | python -m src.cli; echo $?` prints
`Exiting session: EOF when reading a line` and `2`. A test that breaks because behaviour changed
on purpose is doing its job: update it in the same commit.
</details>

**🔴 6. Remove the hard-coded totals.** Replace the `total_cat_combos` lookup at
[cli.py:195](../backend/src/cli.py#L195) with a sum over the records. Check: with
`--fold-equity 0`, the table still shows `52 / 52`, `768 / 768`, `144 / 144` and
`15,648 / 21,136` (74.0%) for Điểm.

<details><summary>Solution</summary>

```python
            total_combos = sum(r.multiplicity for r in cat_records)
```

Then delete the dictionary at lines 184-189. The numbers are unchanged because each category's
multiplicities sum to its total (lesson 03). For a bigger step, import `_category_breakdown` from
a shared module so the CLI and the API build the table the same way.
</details>

**🔴 7. Show the profit zones in the CLI.** Add a line `Profitable when folds are: 0%–8% ·
51%–100%` to the hand panel, using `profitable_fold_zones` from `ev.py`. Check with the K-Q-3
range command: the web UI shows the same zones for that hand.

<details><summary>Hints</summary>

Build `equity_at` exactly like line 133 does, but as a function:
`equity_at = (lambda f: calling_model.equity(canonical_id, f)) if calling_model else (lambda f: stats.equity)`.
Then `zones = profitable_fold_zones(pot, bet_size, equity_at)` and format each `(start, end)` as
percentages (the frontend's `formatZones` in [format.js:8-11](../frontend/src/format.js#L8-L11)
is a model). Add a test that asserts `"51%–100%"` appears in `capsys.readouterr().out`.
</details>

---

## ❓ Quiz

1. Why does `python src/cli.py` fail while `python -m src.cli` works?
2. `python -m src.cli --opponent-model range`: does it run the solver straight away?
3. Which two exception families does `main` turn into exit code 2, and where does each come from?
4. How does `test_cli.py` answer the interactive prompts without a keyboard?
5. Under the range model the hand panel says "Break-Even Fold Equity: n/a (range model)". Why
   not print the number `EVResult` already contains?

<details><summary>Answers</summary>

1. The file imports `src.…`. With `-m` from `backend/`, the current directory is on the import
   path and `src` is found. Run as a script, Python puts `backend/src/` on the path, where there is
   no `src` package.
2. No. Only `--pot`, `--bet`, `--fold-equity` and `--hand` count as "flags given". With none of
   them, `main` opens interactive mode, which asks for the model again and ignores the flag.
3. `LiengError` (bad cards from `evaluator.py`, a missing database from `db.py`) and `ValueError`
   (the guards in `ev.py`, such as a negative pot or a fold rate above 1).
4. `monkeypatch.setattr("builtins.input", …)` replaces `input` with a lambda that returns the next
   item of a list, and `main([])` forces interactive mode.
5. That number assumes a constant equity. Under the range model the equity changes with the fold
   rate, so EV can rise, fall and rise again (lesson 07): a single break-even would be wrong.
</details>

---

## Recap

- Run it as `python -m src.cli` from `backend/`. With none of the four game flags it asks five
  questions instead.
- `run_solver` loads the database, builds the calling-range model only for `range`, solves all 455
  hands, then prints a banner, an overview, a category table and, last, your hand.
- Equity comes from the calling-range model or the database, exactly as in the API. The CLI shows
  no fold zones.
- `rich` is optional: every renderer has a plain branch, and the two reports differ slightly.
- Bad input means one line on stderr and exit code 2. The interactive mode exits 0 even on errors.
- The tests call `main(argv)` directly, capture output with `capsys`, and type for you with
  `monkeypatch`.

**Next:** [10 — The Flask API](10-flask-api.md)
