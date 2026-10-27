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
| 1 | [cli.py:1-8](../backend/src/cli.py#L1-L8) | The four exit codes, documented in the module docstring. |
| 2 | [cli.py:19-49](../backend/src/cli.py#L19-L49) | Imports (shared defaults, `DEFAULT_DB_PATH`, `category_breakdown`), labels, and the exit-code constants. |
| 3 | [cli.py:51-77](../backend/src/cli.py#L51-L77) | `rich` imported *optionally*; `_console()` and `_use_utf8_stdout()` run on first use, not at import. |
| 4 | [cli.py:80-82](../backend/src/cli.py#L80-L82) | `format_currency`: thousands separators, decimals only when needed. |
| 5 | [cli.py:85-146](../backend/src/cli.py#L85-L146) | The banner and the solver overview: a `rich` branch and a plain `print` branch each. |
| 6 | [cli.py:149-192](../backend/src/cli.py#L149-L192) | Your hand: equity source, EV, "n/a (range model)". |
| 7 | [cli.py:195-233](../backend/src/cli.py#L195-L233) | The category table, built from `category_breakdown`. |
| 8 | [cli.py:236-271](../backend/src/cli.py#L236-L271) | `run_solver`: validate, compute, then print. |
| 9 | [cli.py:274-312](../backend/src/cli.py#L274-L312) | `interactive_mode`: five `input()` prompts, and an exit code back. |
| 10 | [cli.py:315-376](../backend/src/cli.py#L315-L376) | `main`: argparse, interactive or not, exit codes 1 and 2. |
| 11 | [test_cli.py](../backend/tests/test_cli.py) | Twelve tests: `capsys`, `SystemExit`, a fake keyboard, an empty stdout, a forced plain branch, a fake broken model. |

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

`--db` defaults to `DEFAULT_DB_PATH`, an absolute path built from the location of
[paths.py:8-9](../backend/src/paths.py#L8-L9), so the default database is found whatever your
current directory is. A relative `--db` you type yourself is tried as given, then next to the
backend ([db.py:82-89](../backend/src/db.py#L82-L89), lesson 05).

### 2. `main`: flags, defaults and the interactive switch

[cli.py:318-347](../backend/src/cli.py#L318-L347) declares six options: `--pot`, `--bet`,
`--fold-equity` (with the alias `--p-fold`), `--hand`, `--db` and `--opponent-model`. The
choices for the last one come from the enum itself, `[m.value for m in OpponentModel]`, so a new
model would appear in `--help` automatically. Then:

📍 [`backend/src/cli.py:349-376`](../backend/src/cli.py#L349-L376)
```python
    args = parser.parse_args(argv)
    opponent_model = OpponentModel(args.opponent_model)

    if args.pot is None and args.bet is None and args.fold_equity is None and args.hand is None:
        code = interactive_mode(args.db, opponent_model)
        if code:
            sys.exit(code)
        return

    try:
        run_solver(
            pot=args.pot if args.pot is not None else DEFAULT_POT,
            bet_size=args.bet if args.bet is not None else DEFAULT_BET_SIZE,
            fold_equity=args.fold_equity if args.fold_equity is not None else DEFAULT_FOLD_EQUITY,
            hand_str=args.hand,
            db_path=args.db,
            opponent_model=opponent_model,
        )
    except DatabaseError as err:
        print(f"Cannot load the win-rate database: {err}", file=sys.stderr)
        sys.exit(EXIT_DATABASE_ERROR)
    except ModelError as err:
        print(f"Internal model error: {err}", file=sys.stderr)
        sys.exit(EXIT_DATABASE_ERROR)
    except (LiengError, ValueError) as err:
        # Bad hand text or out-of-range numbers: a clear message and the usage-error exit code
        print(f"Invalid input: {err}", file=sys.stderr)
        sys.exit(EXIT_INVALID_INPUT)
```

- **`argv` is a parameter.** `main(argv=None)` lets argparse read `sys.argv` in real use, while a
  test can call `main(["--pot", "100000"])` directly. That one choice is what makes
  `test_cli.py` possible.
- **The switch is "none of the four game flags".** `--db` and `--opponent-model` don't count, so
  `python -m src.cli --opponent-model range` opens the prompts. The flag is not lost: it is passed
  to `interactive_mode` and becomes the default answer of the model question (`[range]`).
  [test_cli.py:83-86](../backend/tests/test_cli.py#L83-L86) pins that.
- **Defaults come from `ev.py`.** The options default to `None` so that the code can tell "not
  given" from "given". The real defaults are `DEFAULT_POT`, `DEFAULT_BET_SIZE` and
  `DEFAULT_FOLD_EQUITY` ([ev.py:15-18](../backend/src/ev.py#L15-L18)), the same constants the API
  uses (lesson 07), so the two front doors cannot drift apart.
- **Three kinds of failure, two exit codes.** A `DatabaseError` (missing or invalid file) prints
  `Cannot load the win-rate database: …` and exits with 1. A `ModelError` (the solver's own model
  is missing or inconsistent, for example a calling-range model whose classes don't cover the
  deck: a bug or a bad setup, not your typing) prints `Internal model error: …` and also exits
  with 1. Any other `LiengError` (bad cards, bad numbers) or `ValueError` prints `Invalid input: …`
  and exits with 2. The order of the `except` clauses matters: `DatabaseError` and `ModelError` are
  themselves `LiengError`s, so they have to be caught first. All three messages go to **stderr**,
  and none is a traceback.
- **Interactive mode returns its code.** `main` calls `sys.exit(code)` only when the code is not 0.
- **The first line of `main` switches stdout to UTF-8.** That used to happen when the module was
  imported. Now importing `src.cli` (as every test does) changes nothing:

📍 [`backend/src/cli.py:70-77`](../backend/src/cli.py#L70-L77)
```python
def _use_utf8_stdout() -> None:
    """Ask the terminal stream for UTF-8 so Vietnamese text prints on Windows consoles."""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        try:
            reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass  # a stream that can't be reconfigured (e.g. already detached) keeps its encoding
```

Windows consoles often default to a code page that cannot print "Liêng". The `getattr` covers
stream objects that have no `reconfigure` method (anything that is not a real text stream), and
the `except` names the two errors a stream can raise here, with a comment saying why it is safe to
ignore them.

### 3. Exit codes, verified

| Command (from `backend/`) | Printed | Exit |
|---------------------------|---------|------|
| `python -m src.cli --pot 100000 --hand "As Kh Qd"` | the report (57 lines) | 0 |
| `python -m src.cli --pot -5` | `Invalid input: Pot must be strictly positive, got -5.0.` | 2 |
| `python -m src.cli --fold-equity 1.5` | `Invalid input: Fold equity must be between 0.0 and 1.0, got 1.5.` | 2 |
| `python -m src.cli --hand "As Xh Kd"` | `Invalid input: Invalid card 'Xh': Invalid rank 'X'. …`, and **nothing** on stdout | 2 |
| `python -m src.cli --pot abc` | argparse usage + `error: argument --pot: invalid float value: 'abc'` | 2 |
| `python -m src.cli --opponent-model psychic` | usage + `invalid choice: 'psychic' (choose from 'random', 'range')` | 2 |
| `python -m src.cli --pot 1 --db nowhere.json` | `Cannot load the win-rate database: Database file 'nowhere.json' does not exist.` | **1** |
| interactive, hand `Xx Kh Qd` | `Exiting session: Invalid card 'Xx': Invalid rank 'X'. …` | 2 |
| interactive, pot `abc` | `Exiting session: could not convert string to float: 'abc'` | 2 |
| interactive, stdin closed (`printf '' \| python -m src.cli`) | `Exiting session: no more input.` | 0 |
| interactive, Ctrl+C | `Exiting session: interrupted.` | **130** |

The codes follow Unix conventions, and the module docstring
([cli.py:6-7](../backend/src/cli.py#L6-L7)) lists them. 2 means "you used the command wrongly";
argparse already uses it for its own errors, so `cli.py` matches it. 1 is a general failure that
is not your typing: here, a database that cannot be loaded, or a broken model
(`Internal model error: …`). The table has no row for the second one because no command line can
cause it; only a code change can, and a test fakes one (weak spot 10). 130 is `128 + 2`, the
shell's code for "stopped by signal 2 (SIGINT)", which is what Ctrl+C sends. Running out of input
is a normal way for a scripted session to end, so it is 0. The constants live at
[cli.py:47-49](../backend/src/cli.py#L47-L49), so no bare `sys.exit(2)` is left in the code.

### 4. `run_solver`: validate, compute, then print

`run_solver(pot, bet_size, fold_equity, hand_str=None, db_path=DEFAULT_DB_PATH,
opponent_model=RANDOM)` ([cli.py:236-252](../backend/src/cli.py#L236-L252)) is the whole pipeline:

📍 [`backend/src/cli.py:253-271`](../backend/src/cli.py#L253-L271)
```python
    hand = Hand.from_str(hand_str) if hand_str else None
    if not (0.0 <= fold_equity <= 1.0):
        raise InvalidGameParamsError(f"Fold equity must be between 0.0 and 1.0, got {fold_equity}.")
    be_bluff = calculate_break_even_fold_equity(pot, bet_size, win_rate_when_called=0.0)

    db = WinRateDB(db_path)
    # Build the calling-range tables (~50 ms) only when the range model is requested
    calling_model = CallingRangeModel() if opponent_model is OpponentModel.RANGE else None
    finder = RangeFinder(db, calling_model)
    records = finder.solve_range(pot, bet_size, fold_equity, opponent_model)
    profitable = [r for r in records if r.is_raise_profitable]
    coverage = finder.calculate_range_coverage(profitable)

    render_banner(pot, bet_size, fold_equity, be_bluff, opponent_model)
    render_solver_overview(records, coverage)
    render_categorized_heatmap(records)

    if hand is not None:
        render_single_hand_decision(hand, db, pot, bet_size, fold_equity, calling_model)
```

Read it as three blocks:

1. **Validate.** The hand text is parsed first. The fold rate is checked by hand because the next
   call does not take one, and `calculate_break_even_fold_equity` checks the pot and the bet (both
   raise `InvalidGameParamsError`, lesson 07). Nothing has been printed yet, so a typo in `--hand`
   leaves stdout empty. [test_cli.py:59-64](../backend/tests/test_cli.py#L59-L64) pins exactly that.
2. **Compute.** `WinRateDB(db_path)` loads the file in its constructor; a missing file raises
   `DatabaseError` here, still before any output. `RangeFinder` gets a loaded database, which it
   now requires (lesson 08).
3. **Print.** Four renderers, your hand last. `render_single_hand_decision` receives the parsed
   `Hand`, so the text is parsed once.

Unlike `app.py`, the CLI builds its objects *inside a function* and passes them along. Nothing is
created at import time. Every run loads the 455 records and, under the range model, builds the
card-removal tables of lesson 06. Measured on the machine this course was written on (your numbers
will differ): building `CallingRangeModel()` took 53–55 ms, loading and validating the database
5–6 ms, and one `solve_range` about 2 ms.

`be_bluff` is the pure-bluff break-even of lesson 07, `B / (P + B)`: 33.3% for a half-pot bet,
50.0% for a pot-sized one.

### 5. Your hand: the same choice as the API

📍 [`backend/src/cli.py:162-172`](../backend/src/cli.py#L162-L172)
```python
    canonical_id = to_canonical(hand.cards).canonical_id
    stats = db.get(canonical_id)
    equity = calling_model.equity(canonical_id, fold_equity) if calling_model else stats.equity
    ev_result = evaluate_action(pot, bet_size, fold_equity, equity)
    # Under the range model EV is not monotonic in fold equity, so no single break-even exists
    break_even_text = (
        f"{ev_result.break_even_fold_equity * 100:.2f}%" if calling_model is None else "n/a (range model)"
    )

    status_color = "green" if ev_result.is_profitable else "red"
    action_text = "BET +EV" if ev_result.is_profitable else "NO BET (+EV NOT ESTABLISHED)"
```

Line 164 is the CLI's version of `app.py`'s `_equity_function`
([app.py:302-308](../backend/app.py#L302-L308)): the calling-range equity if a model exists,
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

And the overview panel above it, titled **SOLVER OVERVIEW** (`render_solver_overview`,
[cli.py:116-146](../backend/src/cli.py#L116-L146)):

| Line | random | range |
|------|--------|-------|
| Pure Bluff Break-Even Fold Equity | 50.0% | 50.0% |
| Profitable Classes | 387 / 455 | 250 / 455 |
| Combos in Range | 18,708 / 22,100 | 12,060 / 22,100 |
| Total Range Coverage | 84.65% | 54.57% |
| Highest EV Hand | A-A-A (EV: +165,000) | A-A-A (EV: +165,000) |
| Threshold Hand (EV > 0) | K-8-3 (EV: +361.50) | K-Q-4 (EV: +420) |

Two details of `format_currency` ([cli.py:80-82](../backend/src/cli.py#L80-L82)) show up here:
`+361.50` has decimals because the EV is not a whole number, while `+420` has none. The 22,100 is
`TOTAL_COMBINATIONS` from `hands.py` (lesson 08), not a literal.

### 6. `rich` if available, `print` if not

📍 [`backend/src/cli.py:51-67`](../backend/src/cli.py#L51-L67)
```python
if TYPE_CHECKING:
    from rich.console import Console

try:
    from rich import box
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    HAS_RICH = True
except ImportError:  # rich is a development dependency; fall back to plain text without it
    HAS_RICH = False


@cache
def _console() -> Console:
    """The shared rich console, created on first use rather than at import time."""
    return Console(legacy_windows=False)
```

`rich` draws the boxes and colours. It is a development dependency
([requirements-dev.txt](../backend/requirements-dev.txt)), not a runtime one: the production API
never prints a table, so it does not ship. The CLI still works without it: every renderer starts
with `if HAS_RICH:` and has an `else:` branch of plain `print` calls (for example
[cli.py:103-113](../backend/src/cli.py#L103-L113)). The console itself is made by `_console()` the
first time a renderer needs it (see the concept box below). You can see the fallback without
uninstalling anything, by hiding the package before the import (see 🧪 Try it). The plain version
of the range run above:

```
--- SOLVER OVERVIEW ---
 Profitable Classes:   250 / 455
 Combos in Range:      12,060 / 22,100 combinations
 Range Coverage:       54.57%
 Highest EV Hand:      A-A-A (EV: +165,000)
 Threshold Hand:       K-Q-4 (EV: +420)
-----------------------


--- CATEGORY BREAKDOWN ---
 SAP  :  13 /  13 classes, 52 / 52 combos profitable
 LIENG:  12 /  12 classes, 768 / 768 combos profitable
 DI   :   6 /   6 classes, 144 / 144 combos profitable
 DIEM : 219 / 424 classes, 11,096 / 21,136 combos profitable
--------------------------
```

The two branches show the same totals, but they are still not the same report: the plain category
table has no coverage column and no sample hands. The hand panels do agree now. The plain one used
to print `Expected Value:     40,200` without the `+`; it now uses the same expression as the `rich`
branch and prints `+40,200` ([cli.py:189](../backend/src/cli.py#L189), weak spot 7).

`rich` is also the slowest import the CLI has: 50–80 ms on the course machine. AGENTS.md §6 now
budgets 300 ms for one cold-start command (the old 50 ms target could not be met by a fresh Python
process with these imports), and whole commands measured 0.14 s for the random model and
0.19–0.22 s for the range model.

### 7. The category table, from shared code

📍 [`backend/src/cli.py:195-197`](../backend/src/cli.py#L195-L197)
```python
def render_categorized_heatmap(records: list[HandEVRecord]) -> None:
    """Render categorized summary tables showing distribution and top hands."""
    breakdown = category_breakdown(records)
```

`category_breakdown` is the function lesson 08 showed: one `CategorySummary` per category, with
`classes`, `combos` and `profitable_combos` summed from the records. The API's
`category_breakdown` field is built by the same call, so the CLI table and the web UI cannot
disagree about how many Đĩ combos exist. The CLI adds only presentation: a label from
`CATEGORY_LABELS` ([cli.py:40-45](../backend/src/cli.py#L40-L45)), the number of profitable
classes, a coverage percentage, and up to five sample hands
([cli.py:207-222](../backend/src/cli.py#L207-L222)). An older version kept the four totals (52,
768, 144, 21,136) as literals in this function; see weak spot 3.

### 8. Interactive mode, and how the test types for you

`interactive_mode(db_path, default_model)` ([cli.py:274-278](../backend/src/cli.py#L274-L278))
asks for the pot, the bet and the fold rate first, each with a default from `ev.py` when you just
press Enter. Then:

📍 [`backend/src/cli.py:290-312`](../backend/src/cli.py#L290-L312)
```python
        model_str = input(
            f"Opponent folds 'random' or 'range' (weakest hands first)? [{default_model.value}]: "
        ).strip()
        opponent_model = OpponentModel(model_str.lower()) if model_str else default_model

        hand_str = input("Enter your hand (e.g. 'As Kh Qd' or press Enter to skip): ").strip()
        run_solver(pot, bet, fold_equity, hand_str=hand_str or None, db_path=db_path, opponent_model=opponent_model)
    except DatabaseError as err:
        print(f"Cannot load the win-rate database: {err}", file=sys.stderr)
        return EXIT_DATABASE_ERROR
    except ModelError as err:
        print(f"Internal model error: {err}", file=sys.stderr)
        return EXIT_DATABASE_ERROR
    except (ValueError, LiengError) as err:
        print(f"\nExiting session: {err}")
        return EXIT_INVALID_INPUT
    except EOFError:
        print("\nExiting session: no more input.")
        return 0
    except KeyboardInterrupt:
        print("\nExiting session: interrupted.")
        return EXIT_INTERRUPTED
    return 0
```

- The model question shows `default_model` in brackets and uses it for an empty answer.
- Every expected failure becomes one line and an exit code. A bad number gives
  `Exiting session: could not convert string to float: 'abc'`, a bad model
  `Exiting session: 'psychic' is not a valid OpponentModel`, both with 2. A database problem and a
  broken model get the same messages and code 1 as in `main`. `EOFError` (stdin closed, for example
  `printf '' | python -m src.cli`) is a normal end, 0. Ctrl+C is 130.
- The function *returns* the code instead of calling `sys.exit`, so a test can call it and look at
  the number, and `main` stays the only place that ends the process.

How do you test something that reads the keyboard? You replace `input`:

📍 [`backend/tests/test_cli.py:39-56`](../backend/tests/test_cli.py#L39-L56)
```python
def _answer_prompts(monkeypatch, answers):
    """Feed interactive-mode prompts from a list instead of the keyboard."""
    replies = iter(answers)
    monkeypatch.setattr("builtins.input", lambda _prompt: next(replies))


def test_interactive_mode_asks_for_opponent_model(monkeypatch, capsys):
    _answer_prompts(monkeypatch, ["100000", "100000", "0.35", "range", "Ks Qh 3d"])
    main([])
    assert "ACTION: NO BET (+EV NOT ESTABLISHED)" in capsys.readouterr().out


def test_interactive_mode_reports_invalid_hand(monkeypatch, capsys):
    _answer_prompts(monkeypatch, ["100000", "100000", "0.35", "", "Xx Kh Qd"])
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2
    assert "Exiting session: Invalid card 'Xx': Invalid rank 'X'" in capsys.readouterr().out
```

- `monkeypatch.setattr("builtins.input", …)` swaps the built-in `input` for a lambda that hands
  out the next answer. pytest puts the real one back after the test.
- `main([])` passes an empty argument list, so none of the four flags is set and `main` goes
  interactive. (Calling `main()` would read pytest's own `sys.argv`.)
- The bad hand ends the session with code 2, so `main` raises `SystemExit`, and the test catches it
  with `pytest.raises`.
- `capsys.readouterr().out` returns everything printed to stdout during the test, and `.err` returns
  stderr. The exit-code test ([test_cli.py:31-36](../backend/tests/test_cli.py#L31-L36)) checks
  `.code == 2` and `"Invalid input"` in `.err`. The end-of-input test
  ([test_cli.py:74-80](../backend/tests/test_cli.py#L74-L80)) uses a fake `input` that raises
  `EOFError` instead of returning an answer.

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
an over-broad `except BaseException:` would swallow the exit. `KeyboardInterrupt` is a
`BaseException` too, not an `Exception`, which is why `interactive_mode` names it in its own
`except` clause.

## 💡 Concept: `@functools.cache` for "create on first use"

```python
@cache
def _console() -> Console:
    return Console(legacy_windows=False)
```

`cache` remembers the result for each set of arguments. A function with no arguments therefore
runs its body once, on the first call, and returns the same object ever after. That gives one
shared console without a module-level variable and without creating it at import time. The
`if TYPE_CHECKING:` import above it is read only by type checkers such as `mypy`. At runtime the
annotation `-> Console` is never evaluated (the module starts with
`from __future__ import annotations`), so a machine without `rich` never needs the name.

---

## Design decisions

- **Presentation only.** `cli.py` calls `WinRateDB`, `CallingRangeModel`, `RangeFinder`,
  `category_breakdown` and `evaluate_action`, then prints. It never re-implements EV. If the CLI
  and the web UI disagree, the bug is in one of the two front ends, not in the engine.
- **Validate, compute, then print.** A failed command prints one line on stderr and nothing on
  stdout, so a script that reads stdout never mistakes a half-report for an answer.
- **Objects are built per run.** Unlike `app.py`, whose module-level `app = create_app()` loads
  everything at import (lesson 10), `cli.py` creates nothing until `main` runs, not even the
  console. The cost is paid on every command (0.14–0.22 s in total here), which is fine for a
  tool you run by hand.
- **Exit codes that mean something.** 0, 1, 2 and 130 are named constants and documented at the
  top of the module, so a shell script can tell "fix your input" from "fix the installation".
- **The range model is opt-in, and the default is random.** `--opponent-model` defaults to
  `random`, which keeps old commands producing old answers
  ([test_cli.py:21](../backend/tests/test_cli.py#L21) pins it). The web UI chose the opposite
  default (lesson 13).
- **`rich` is optional.** The fallback costs duplicated code in every renderer, but the tool keeps
  working on a production install, where `rich` is not present. The alternative, a hard
  dependency, would remove half the module.

---

## ⚠️ Weak spots

1. ✅ **Fixed: a bad `--hand` was reported after the whole report.** The hand used to be parsed
   last, inside the hand renderer, so `--hand "As Xh Kd"` printed 48 lines and then failed. Now
   `run_solver` parses the hand and checks every number before anything is printed
   ([cli.py:253-256](../backend/src/cli.py#L253-L256)). Pinned by
   `test_invalid_hand_is_reported_before_any_output`
   ([test_cli.py:59-64](../backend/tests/test_cli.py#L59-L64)), which asserts an empty stdout;
   exercise 4 breaks it on purpose.
2. ✅ **Fixed: interactive mode always "succeeded".** It printed `Exiting session: …` and returned,
   so the exit code was 0 after an error, and `EOFError` escaped as a traceback. Now
   `interactive_mode` returns 2, 1, 0 or 130 ([cli.py:297-312](../backend/src/cli.py#L297-L312))
   and `main` exits with it ([cli.py:352-356](../backend/src/cli.py#L352-L356)). Pinned by
   `test_interactive_mode_reports_invalid_hand` ([test_cli.py:51-56](../backend/tests/test_cli.py#L51-L56))
   and `test_interactive_mode_ends_cleanly_at_end_of_input`
   ([test_cli.py:74-80](../backend/tests/test_cli.py#L74-L80)). The Ctrl+C path has no test yet
   (exercise 5).
3. ✅ **Fixed: hard-coded totals.** The per-category combos (52, 768, 144, 21,136) and "22,100" used
   to be literals. Now the table comes from `category_breakdown`
   ([cli.py:197](../backend/src/cli.py#L197)) and the total from `TOTAL_COMBINATIONS`
   ([cli.py:133](../backend/src/cli.py#L133)). The shared function is pinned by
   `test_category_breakdown_totals` ([test_range_finder.py:125-131](../backend/tests/test_range_finder.py#L125-L131));
   no CLI test reads the table itself.
4. ✅ **Fixed: a missing database was called "Invalid input".** `DatabaseError` is a `LiengError`
   ([exceptions.py:41](../backend/src/exceptions.py#L41)), so it used to land in the exit-2 branch.
   Now it is caught first, with its own message and exit code 1
   ([cli.py:367-369](../backend/src/cli.py#L367-L369), and
   [cli.py:297-299](../backend/src/cli.py#L297-L299) in interactive mode). Pinned by
   `test_missing_database_has_its_own_message_and_exit_code`
   ([test_cli.py:67-71](../backend/tests/test_cli.py#L67-L71)).
5. ✅ **Fixed: import-time side effects, and a swallowed exception.** Importing the module used to
   reconfigure `sys.stdout` inside `except Exception: pass`, and create a module-level console.
   Now `main` calls `_use_utf8_stdout()` ([cli.py:317](../backend/src/cli.py#L317)), which catches
   only `OSError` and `ValueError` and says why ([cli.py:70-77](../backend/src/cli.py#L70-L77)),
   and the console is created on first use by `_console()`
   ([cli.py:64-67](../backend/src/cli.py#L64-L67)). No test pins this directly.
6. ✅ **Fixed: defaults written three times.** 100,000 / 50,000 / 0.35 were typed in `main`, in
   `interactive_mode` and in `app.py`. Now all three read `DEFAULT_POT`, `DEFAULT_BET_SIZE` and
   `DEFAULT_FOLD_EQUITY` from [ev.py:15-18](../backend/src/ev.py#L15-L18) (here at
   [cli.py:281-288](../backend/src/cli.py#L281-L288) and [:360-362](../backend/src/cli.py#L360-L362)).
   `test_solve_default_ui_request_numbers` ([test_api.py:88-92](../backend/tests/test_api.py#L88-L92))
   pins the API side.
7. **Two different reports (half fixed).** The totals match, and the plain hand panel now shows
   the `+` on a positive EV like the `rich` one ([cli.py:189](../backend/src/cli.py#L189)), pinned
   by `test_plain_text_report_shows_the_sign_of_a_positive_ev`
   ([test_cli.py:89-94](../backend/tests/test_cli.py#L89-L94)), the first test that runs the
   fallback. The plain category table is still smaller
   ([cli.py:225-233](../backend/src/cli.py#L225-L233): no coverage column, no sample hands), and no
   test looks at it. *Fix:* build the lines once and let `rich` only decorate them (exercise 6
   starts with the test).
8. **Duplicated logic with the API.** The category table is shared now, but the equity choice still
   exists twice ([cli.py:164](../backend/src/cli.py#L164) vs
   [app.py:302-308](../backend/app.py#L302-L308)). The CLI has no profitable fold zones, so for
   K-Q-3 it says "n/a" where the web UI shows two zones (exercise 7).
9. ✅ **Fixed: "Game-Theoretic Solver".** The `--help` description used to promise game theory. It
   now reads "Expected-Value Solver & Heatmap Viewer" ([cli.py:318](../backend/src/cli.py#L318)),
   which matches README's Limitations section: an EV calculation against an assumed fold rate, not
   an equilibrium. No test pins the wording.
10. ✅ **Fixed: a broken model was called "Invalid input".** `CallingRangeModel` checks its own
    classes when it is built, and it used to raise a plain `LiengError` when they were wrong, so
    the CLI reported a bug in the solver as `Invalid input: …` with exit 2. Now the checks raise
    `ModelError` ([calling_range.py:65-68](../backend/src/calling_range.py#L65-L68)), and `main`
    and `interactive_mode` catch it before the exit-2 clause: `Internal model error: …` on stderr,
    exit 1 ([cli.py:370-372](../backend/src/cli.py#L370-L372) and
    [cli.py:300-302](../backend/src/cli.py#L300-L302)). Pinned by
    `test_a_broken_model_is_an_internal_error_not_invalid_input`
    ([test_cli.py:97-108](../backend/tests/test_cli.py#L97-L108)), which swaps `CallingRangeModel`
    for a function that raises.

---

## 🧪 Try it

Run from `backend/` with the virtual environment active (see [COURSE.md](COURSE.md#setup)).

```bash
python -m pytest tests/test_cli.py -q
```

```
............                                                             [100%]
12 passed in 0.45s
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

Check the fix for weak spot 1: a bad hand, no report, exit code 2:

```bash
python -m src.cli --pot 100000 --bet 50000 --fold-equity 0.35 --hand "As Xh Kd" | wc -l; echo "exit=${PIPESTATUS[0]}"
```

```
Invalid input: Invalid card 'Xh': Invalid rank 'X'. Must be 2-10, T, J, Q, K, or A.
0
exit=2
```

And the two other codes:

```bash
python -m src.cli --db nowhere.json --pot 1; echo "exit=$?"
printf '' | python -m src.cli | tail -1; echo "exit=${PIPESTATUS[1]}"
```

```
Cannot load the win-rate database: Database file 'nowhere.json' does not exist.
exit=1
Exiting session: no more input.
exit=0
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

Time a whole command (machine-dependent; on the course machine it was 0.14 s for the random model
and 0.19–0.22 s for the range model):

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
rate to 0.35 (`DEFAULT_POT`, `DEFAULT_FOLD_EQUITY`), with the random model. That is the
pot-sized-bet case from section 5: `Profitable Classes: 387 / 455`, coverage 84.65%, threshold hand
K-8-3. No hand panel is printed.
</details>

**🟢 2. Predict.** `python -m src.cli --hand "As As Qd"`. What appears on stderr, how many lines
appear on stdout, and what is the exit code?

<details><summary>Solution</summary>

`Invalid input: A Liêng hand cannot have duplicate cards.` on stderr, nothing on stdout
(`… 2>/dev/null | wc -l` prints 0), exit code 2. The duplicate check lives in `Hand.__post_init__`
([evaluator.py:409-413](../backend/src/evaluator.py#L409-L413)) and raises `DuplicateCardError`, a
kind of `InvalidHandSizeError` and so a `LiengError`, which `main` turns into exit code 2. It
happens on the first line of `run_solver`, before anything is printed.
</details>

**🟢 3. Predict.** In interactive mode you press Enter three times, type `range`, then press Enter
again. What runs, and what is the exit code? Then: what changes if you start it as
`python -m src.cli --opponent-model range` and press Enter five times?

<details><summary>Solution</summary>

The defaults (100,000 / 50,000 / 0.35), the range model, and no hand. The report shows
`Opponent Model: folds weakest hands first (range)` and `Profitable Classes: 455 / 455`, since a
half-pot bet at 35% folds is above the 33.3% bluff break-even, so every hand is +EV. No hand panel,
exit code 0. Check with `printf '\n\n\nrange\n\n' | python -m src.cli`. With the flag, nothing
changes in the result: the model prompt shows `[range]`, and the empty answer takes it.
</details>

**🟡 4. Break the fix for weak spot 1.** In `run_solver`, move the line
`hand = Hand.from_str(hand_str) if hand_str else None` from the top
([cli.py:253](../backend/src/cli.py#L253)) to just above `if hand is not None:`. Before you run
`python -m pytest tests/test_cli.py -q`, predict which of the twelve tests fail. Two other tests also
use a bad hand: why do they still pass?

<details><summary>Solution</summary>

```
FAILED tests/test_cli.py::test_invalid_hand_is_reported_before_any_output - A...
1 failed, 11 passed in 0.39s
```

The assertion shows the banner panel that is now printed before the error. The other two
bad-hand tests check only the exit code and the message (`test_invalid_input_exits_with_message`
with `Xx Kh Qd`, and the interactive one), and both are still right: the command still exits with
2 and says why. Only a test that looks at *what else* was printed can catch the order. That is why
the fix came with a new test instead of relying on the old ones. Undo it with
`git checkout -- backend/src/cli.py`.
</details>

**🟡 5. Pin Ctrl+C.** Weak spot 2 left exit code 130 without a test. Write one: a fake `input`
that raises `KeyboardInterrupt`, then check the exit code and the message. Then delete the
`except KeyboardInterrupt:` clause ([cli.py:309-311](../backend/src/cli.py#L309-L311)) and run the
tests again. What does pytest print, and what is its own exit code?

<details><summary>Solution</summary>

```python
def test_interactive_mode_exits_130_on_ctrl_c(monkeypatch, capsys):
    def ctrl_c(_prompt):
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", ctrl_c)
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 130
    assert "Exiting session: interrupted." in capsys.readouterr().out
```

With the clause in place: `13 passed`. Without it, the `KeyboardInterrupt` escapes from the test,
and pytest treats it as *you* pressing Ctrl+C: it stops the whole run.

```
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! KeyboardInterrupt !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
…/tests/test_cli.py:113: KeyboardInterrupt
(to show a full traceback on KeyboardInterrupt use --full-trace)
12 passed in 0.52s
```

The summary line says "12 passed" and nothing failed, but pytest's exit code is 2 (interrupted),
and the new test never got a result. Read exit codes in CI, not only the summary line. Undo it with
`git checkout -- backend/src/cli.py backend/tests/test_cli.py`.
</details>

**🔴 6. One report, two looks.** Weak spot 7 is half fixed: the plain hand panel signs a positive
EV, and `test_plain_text_report_shows_the_sign_of_a_positive_ev`
([test_cli.py:89-94](../backend/tests/test_cli.py#L89-L94)) pins it by forcing the plain branch.
Do the same for the other half. Write a test that forces the plain branch, runs the range model
with a pot-sized bet (`--pot 100000 --bet 100000 --fold-equity 0.35 --opponent-model range`), and
asserts that the Điểm row shows its coverage, 52.5%, as the `rich` table's "Category Coverage"
column does. Watch it fail, then make it pass in the plain branch of `render_categorized_heatmap`
([cli.py:225-233](../backend/src/cli.py#L225-L233)). For the full fix, make both branches print the
same lines.

<details><summary>Solution sketch</summary>

```python
def test_plain_category_table_shows_the_coverage(monkeypatch, capsys):
    monkeypatch.setattr("src.cli.HAS_RICH", False)
    main(["--pot", "100000", "--bet", "100000", "--fold-equity", "0.35", "--opponent-model", "range"])
    assert "11,096 / 21,136 combos profitable (52.5%)" in capsys.readouterr().out
```

Before the fix: `1 failed, 12 passed`. The fix is the percentage the `rich` branch already computes,
added to the plain line:

```python
                f"{row.profitable_combos:,} / {row.combos:,} combos profitable "
                f"({row.profitable_combos / row.combos * 100.0:.1f}%)"
```

Then `13 passed`, and the plain table ends with
`DIEM : 219 / 424 classes, 11,096 / 21,136 combos profitable (52.5%)`. `monkeypatch` works here
because every renderer reads the module-level `HAS_RICH` when it is *called*, not when it is
defined. For the full fix, give each renderer one list of `(label, value)` pairs (sample hands
included), and let the two branches differ only in how they draw it. A single test can then
compare the plain output with the labels.
</details>

**🔴 7. Show the profit zones in the CLI.** Add a line `Profitable when folds are: 0%–8% ·
51%–100%` to the hand panel, using `profitable_fold_zones` from `ev.py`. Check with the K-Q-3
range command: the web UI shows the same zones for that hand.

<details><summary>Hints</summary>

Build `equity_at` exactly like line 164 does, but as a function:
`equity_at = (lambda f: calling_model.equity(canonical_id, f)) if calling_model else (lambda f: stats.equity)`.
Then `zones = profitable_fold_zones(pot, bet_size, equity_at)` and format each `(start, end)` as
percentages (the frontend's `formatZones` in [format.js:8-11](../frontend/src/format.js#L8-L11)
is a model). Add a test that asserts `"51%–100%"` appears in `capsys.readouterr().out`. If you want
to close weak spot 8 too, move `_equity_function` out of `app.py` into a module both front ends
import.
</details>

---

## ❓ Quiz

1. Why does `python src/cli.py` fail while `python -m src.cli` works?
2. `python -m src.cli --opponent-model range`: does it run the solver straight away?
3. Which exceptions does `main` turn into exit code 2, which into exit code 1, and why does the
   order of the `except` clauses matter?
4. How does `test_cli.py` answer the interactive prompts without a keyboard?
5. Under the range model the hand panel says "Break-Even Fold Equity: n/a (range model)". Why
   not print the number `EVResult` already contains?

<details><summary>Answers</summary>

1. The file imports `src.…`. With `-m` from `backend/`, the current directory is on the import
   path and `src` is found. Run as a script, Python puts `backend/src/` on the path, where there is
   no `src` package.
2. No. Only `--pot`, `--bet`, `--fold-equity` and `--hand` count as "flags given". With none of
   them, `main` opens interactive mode. The flag is still used: it becomes the default answer of
   the model question.
3. Exit 2: `LiengError` (bad cards from `evaluator.py`, bad numbers as `InvalidGameParamsError`
   from `ev.py` and `run_solver`) and `ValueError` (`InvalidGameParamsError` is one too). Exit 1:
   `DatabaseError`, a missing or invalid database file, and `ModelError`, a missing or inconsistent
   model (a bug, not your input). Both are themselves `LiengError`s, so if the exit-2 clause came
   first it would catch them too and blame your input, which is exactly the old bug.
4. `monkeypatch.setattr("builtins.input", …)` replaces `input` with a lambda that returns the next
   item of a list, and `main([])` forces interactive mode.
5. That number assumes a constant equity. Under the range model the equity changes with the fold
   rate, so EV can rise, fall and rise again (lesson 07): a single break-even would be wrong.
</details>

---

## Recap

- Run it as `python -m src.cli` from `backend/`. With none of the four game flags it asks five
  questions instead, and `--opponent-model` becomes the default answer.
- `run_solver` validates the hand and the numbers, loads the database, builds the calling-range
  model only for `range`, solves all 455 hands, and only then prints a banner, the solver
  overview, a category table and, last, your hand.
- Equity comes from the calling-range model or the database, exactly as in the API. The category
  totals come from the shared `category_breakdown`, the defaults from `ev.py`. The CLI shows no
  fold zones.
- `rich` is an optional, development-only dependency: every renderer has a plain branch. The hand
  panels now agree (both sign a positive EV), but the plain category table is still smaller.
- Exit codes: 0 success (or end of input), 1 database or broken model, 2 invalid input, 130
  Ctrl+C. Nothing is printed on stdout before a failure, and nothing happens at import time.
- The tests call `main(argv)` directly, capture output with `capsys`, and type for you with
  `monkeypatch`.

**Next:** [10 — The Flask API](10-flask-api.md)
