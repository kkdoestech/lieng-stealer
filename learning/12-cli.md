# 12 — The Command-Line Interface

> **Goal:** give the engine a usable face in the terminal: options like `--pot 100000 --hand "As Kh Qd"`,
> a choice of opponent model, nicely formatted panels and tables, an interactive question-and-answer mode,
> and clean error messages.
> **You will build:** `backend/src/cli.py` and `backend/tests/test_cli.py` (6 tests).
> **Time:** ~1.5 hours.
> **Prerequisites:** [11](11-range-finder.md).

---

## The big picture

The engine is finished. This chapter adds no new maths: it's **presentation**. Keeping presentation in its
own module (Separation of Concerns, `AGENTS.md` §1) means the same engine can later be used by a web API
(chapter 13) without touching any calculation code.

```
  terminal ──► argparse (main) ──► run_solver ──► WinRateDB + RangeFinder + ev.py   (engine)
                                         │
                                         ├─► render_banner                 ┐
                                         ├─► render_tactical_overview      │ presentation
                                         ├─► render_categorized_heatmap    │ (rich or plain print)
                                         └─► render_single_hand_decision   ┘
```

The CLI uses the **`rich`** library for coloured boxes and tables, and falls back to plain `print` if
`rich` isn't installed.

---

## Concepts you need

### `rich` in 10 lines

```python
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()
console.print(Panel("[bold cyan]Pot:[/] 100,000", title="GAME STATE"))   # a box with a title
table = Table(title="Demo")
table.add_column("Hand"); table.add_column("EV", justify="right")
table.add_row("A-A-A", "[green]+132,500[/]")
console.print(table)
```

`[bold cyan]…[/]` is rich's **markup**: a style in square brackets, closed by `[/]`.

### Optional dependencies

```python
try:
    import rich
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
```

If the import fails, the program still works, just without colours. That's a graceful **fallback**.

### `input()` for interactive programs

`input("Enter pot: ")` prints the prompt, waits for the user to press Enter, and returns the text typed
(always a `str`, so convert with `float(...)`).

---

## Step 12.1 — Imports, UTF-8 output, and optional `rich`

📄 **File:** `backend/src/cli.py` — *create this file*

```python
"""Liêng Stealer - Interactive CLI Decision Support & Range Heatmap Engine.

Provides rich visual displays of game states, tactical summaries, categorized
range matrices, and single-hand decision recommendations.
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

# Ensure UTF-8 output encoding for Windows terminals
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.calling_range import CallingRangeModel, OpponentModel
from src.db import WinRateDB
from src.evaluator import Hand, HandCategory
from src.ev import calculate_break_even_fold_equity, calculate_ev, evaluate_action
from src.exceptions import LiengError
from src.hands import to_canonical
from src.range_finder import HandEVRecord, RangeFinder

MODEL_DESCRIPTIONS = {
    OpponentModel.RANDOM: "folds at random (random)",
    OpponentModel.RANGE: "folds weakest hands first (range)",
}

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

**How it works**

- **UTF-8:** Vietnamese letters (ê, ĩ, ể) and box-drawing characters need UTF-8. Older Windows
  terminals default to another encoding and would crash with `UnicodeEncodeError`.
  `sys.stdout.reconfigure(encoding="utf-8")` switches the output stream to UTF-8. `hasattr` checks that
  the method exists (it doesn't on some replaced streams).
- **Optional rich:** if any rich import fails, `HAS_RICH = False` and every render function uses its
  plain-text branch instead.
- `Console(legacy_windows=False)` tells rich to use modern terminal features even on Windows.
- The engine imports now include the **opponent models** (chapter 9) and `LiengError` (chapter 4), used to
  report bad input cleanly. `MODEL_DESCRIPTIONS` maps each `OpponentModel` to the text the banner shows.

> ⚠️ **Pitfall: import-time side effects and a swallowed error.** Two things happen merely because
> someone *imports* this module: stdout is reconfigured, and a global `_console` object is created.
> `AGENTS.md` says "no global mutable state", and importing a module should not change the process.
> Also, `except Exception: pass` silently swallows any error, against the project's "never silently
> swallow exceptions" rule. **Better:** move both into `main()` (run only when the CLI actually starts),
> and catch the specific error, e.g. `except (AttributeError, ValueError, OSError)`, with a comment
> explaining why it's safe to ignore. (`calculate_ev` and `Text` are also imported but never used.)

---

## Step 12.2 — Formatting money

📄 **File:** `backend/src/cli.py` — *add to the end*

```python


def format_currency(val: float) -> str:
    """Format numerical value with thousand separators."""
    return f"{val:,.0f}" if val == int(val) else f"{val:,.2f}"
```

`132097.0` → `"132,097"`; `2812.5` → `"2,812.50"`. Whole numbers show no decimals; others show two.

---

## Step 12.3 — The game-state banner

📄 **File:** `backend/src/cli.py` — *add to the end*

```python


def render_banner(
    pot: float,
    bet_size: float,
    fold_equity: float,
    be_bluff_fe: float,
    opponent_model: OpponentModel = OpponentModel.RANDOM,
) -> None:
    """Render the game state banner."""
    if HAS_RICH:
        console = _console or Console(legacy_windows=False)
        content = (
            f"[bold cyan]Pot Size (Dead Money):[/] {format_currency(pot)}\n"
            f"[bold cyan]Bet / Raise Sizing:[/] {format_currency(bet_size)}\n"
            f"[bold cyan]Opponent Fold Equity:[/] {fold_equity * 100:.1f}%\n"
            f"[bold cyan]Opponent Model:[/] {MODEL_DESCRIPTIONS[opponent_model]}\n"
            f"[bold yellow]Pure Bluff Break-Even Fold Equity:[/] {be_bluff_fe * 100:.1f}%\n"
            f"[bold cyan]Final Pot (if called):[/] {format_currency(pot + 2.0 * bet_size)}"
        )
        console.print(Panel(content, title="[bold green]LIÊNG STEALER - GAME STATE BANNER[/]", border_style="green"))
    else:
        print("=" * 60)
        print(" LIÊNG STEALER - GAME STATE BANNER")
        print("=" * 60)
        print(f" Pot Size (Dead Money):       {format_currency(pot)}")
        print(f" Bet / Raise Sizing:          {format_currency(bet_size)}")
        print(f" Opponent Fold Equity:        {fold_equity * 100:.1f}%")
        print(f" Opponent Model:              {MODEL_DESCRIPTIONS[opponent_model]}")
        print(f" Pure Bluff Break-Even FE:    {be_bluff_fe * 100:.1f}%")
        print(f" Final Pot (if called):       {format_currency(pot + 2.0 * bet_size)}")
        print("=" * 60)
```

**How it works**

- Every render function has the same shape: `if HAS_RICH:` build a rich `Panel`/`Table`; `else:` print
  plain lines. Same information, two looks.
- Adjacent string literals inside parentheses are **joined automatically** by Python:
  `("a" "b")` is `"ab"`. That's how the multi-line `content` is built.
- `"=" * 60` repeats a string: a line of 60 `=` signs.
- The new `opponent_model` parameter has a default (`RANDOM`), so older calls keep working; the banner
  prints `MODEL_DESCRIPTIONS[opponent_model]`, so the reader always knows which model the numbers assume.

---

## Step 12.4 — The tactical overview

📄 **File:** `backend/src/cli.py` — *add to the end*

```python


def render_tactical_overview(
    records: list[HandEVRecord],
    coverage: float,
) -> None:
    """Render overview of profitable combinations and boundaries."""
    profitable = [r for r in records if r.is_raise_profitable]
    total_combos = sum(r.multiplicity for r in profitable)

    highest_ev_hand = records[0] if records else None
    lowest_profit_hand = profitable[-1] if profitable else None

    highest_desc = f"{highest_ev_hand.canonical_id} (EV: +{format_currency(highest_ev_hand.ev)})" if highest_ev_hand else "None"
    lowest_desc = f"{lowest_profit_hand.canonical_id} (EV: +{format_currency(lowest_profit_hand.ev)})" if lowest_profit_hand else "None"

    if HAS_RICH:
        console = _console or Console(legacy_windows=False)
        content = (
            f"[bold]Profitable Classes:[/] {len(profitable)} / {len(records)} canonical classes\n"
            f"[bold]Combos in Range:[/] [green]{total_combos:,}[/] / 22,100 total combinations\n"
            f"[bold]Total Range Coverage:[/] [bold green]{coverage:.2f}%[/]\n"
            f"[bold]Highest EV Hand:[/] [green]{highest_desc}[/]\n"
            f"[bold]Threshold Hand (EV > 0):[/] [yellow]{lowest_desc}[/]"
        )
        console.print(Panel(content, title="[bold blue]TACTICAL SOLVER OVERVIEW[/]", border_style="blue"))
    else:
        print("\n--- TACTICAL SOLVER OVERVIEW ---")
        print(f" Profitable Classes:   {len(profitable)} / {len(records)}")
        print(f" Combos in Range:      {total_combos:,} / 22,100 combinations")
        print(f" Range Coverage:       {coverage:.2f}%")
        print(f" Highest EV Hand:      {highest_desc}")
        print(f" Threshold Hand:       {lowest_desc}")
        print("--------------------------------\n")
```

**How it works**

- Because `records` is sorted best-first (chapter 11), `records[0]` is the best hand and
  `profitable[-1]` (last profitable) is the **threshold hand**: the weakest hand still worth raising.
- `x if condition else "None"` protects against empty lists (`records[0]` on an empty list would crash).
- `{total_combos:,}` adds thousands separators to an integer.

---

## Step 12.5 — The single-hand decision

📄 **File:** `backend/src/cli.py` — *add to the end*

```python


def render_single_hand_decision(
    hand_str: str,
    db: WinRateDB,
    pot: float,
    bet_size: float,
    fold_equity: float,
    calling_model: CallingRangeModel | None = None,
) -> None:
    """Evaluate and render recommendation for a specific player hand.

    With a calling_model, equity is measured against the opponent's calling range;
    otherwise against a random hand.
    """
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

    if HAS_RICH:
        console = _console or Console(legacy_windows=False)
        content = (
            f"[bold]Hand Evaluated:[/] {hand} ([italic]{hand.score}[/])\n"
            f"[bold]Canonical Class:[/] {canonical_id} ([cyan]{stats.category.display_name}[/])\n"
            f"[bold]Showdown Equity:[/] {equity * 100:.2f}%\n"
            f"[bold]Expected Value (EV):[/] [{status_color}]{'+' if ev_result.ev > 0 else ''}{format_currency(ev_result.ev)}[/]\n"
            f"[bold]Break-Even Fold Equity:[/] {break_even_text}\n\n"
            f"[bold {status_color} reverse] >>> ACTION: {action_text} <<< [/]"
        )
        console.print(Panel(content, title="[bold magenta]HAND EVALUATION & ACTION[/]", border_style=status_color))
    else:
        print("\n================ HAND EVALUATION ================")
        print(f" Hand:               {hand} ({hand.score})")
        print(f" Canonical Class:    {canonical_id} ({stats.category.display_name})")
        print(f" Showdown Equity:    {equity * 100:.2f}%")
        print(f" Expected Value:     {format_currency(ev_result.ev)}")
        print(f" Break-Even FE:      {break_even_text}")
        print(f" >>> ACTION: {action_text} <<<")
        print("=================================================\n")
```

**How it works**: this is the complete pipeline for one hand in a few lines:
**text → `Hand` → `HandStats` (O(1) lookup) → equity for the chosen model → `EVResult`**. The rest is
formatting.

- **Which equity?** With a `calling_model`, `calling_model.equity(canonical_id, fold_equity)` (chapter 9);
  without one, the random-hand `stats.equity`. The optional parameter defaults to `None`, so the random
  model needs no model object at all.
- **Break-even under the range model:** a single break-even fold equity only makes sense when equity stays
  the same as folds change (random model). Under the range model EV isn't monotonic (chapter 10), so the
  panel says `n/a (range model)` instead of printing a misleading number. This matches the API's
  `break_even_fold_equity: null` (chapter 13).
- The colour (green or red) and the action text are chosen once and reused, so they can't disagree.

---

## Step 12.6 — The category breakdown table

This function is long, so it comes in two slices. The first builds the table's columns and constants.

📄 **File:** `backend/src/cli.py` — *add to the end*

```python


def render_categorized_heatmap(records: list[HandEVRecord]) -> None:
    """Render categorized summary tables showing distribution and top hands."""
    if HAS_RICH:
        console = _console or Console(legacy_windows=False)
        table = Table(title="[bold]Range Matrix Breakdown by Category[/]", box=box.ROUNDED)
        table.add_column("Category", style="cyan", justify="left")
        table.add_column("Total Classes", justify="right")
        table.add_column("Profitable Classes", justify="right")
        table.add_column("Combos (EV > 0)", justify="right")
        table.add_column("Category Coverage", justify="right")
        table.add_column("Sample Profitable Hands", justify="left")

        categories = [
            (HandCategory.SAP, "Sáp (Triples)"),
            (HandCategory.LIENG, "Liêng (Straights)"),
            (HandCategory.DI, "Đĩ (Face Cards)"),
            (HandCategory.DIEM, "Điểm (Points)"),
        ]

        total_cat_combos = {
            HandCategory.SAP: 52,
            HandCategory.LIENG: 768,
            HandCategory.DI: 144,
            HandCategory.DIEM: 21136,
        }
```

These are the per-category totals from chapter 6 (52 / 768 / **144** / **21,136**). They're **correct**
here. (The first version of the frontend typed them in wrongly; the current API computes them from the
data instead, chapter 13.)

> 💡 **Hard-coded facts.** These totals can be *computed* from the data:
> `sum(s.multiplicity for s in db.all_items().values() if s.category == cat)`. Computed numbers can't
> drift out of sync with the data; typed ones can, as the first version of the frontend proved.

The second slice fills one row per category:

📄 **File:** `backend/src/cli.py` — *add to the end*

```python

        for cat, label in categories:
            cat_records = [r for r in records if r.category == cat]
            profitable = [r for r in cat_records if r.is_raise_profitable]
            prof_combos = sum(r.multiplicity for r in profitable)
            total_combos = total_cat_combos[cat]
            cov = (prof_combos / total_combos) * 100.0 if total_combos > 0 else 0.0

            sample_hands = ", ".join(r.canonical_id for r in profitable[:5])
            if len(profitable) > 5:
                sample_hands += f" ... (+{len(profitable) - 5} more)"
            elif not sample_hands:
                sample_hands = "[dim]None[/]"

            table.add_row(
                label,
                str(len(cat_records)),
                f"[green]{len(profitable)}[/]",
                f"{prof_combos:,} / {total_combos:,}",
                f"{cov:.1f}%",
                sample_hands,
            )

        console.print(table)
    else:
        print("\n--- CATEGORY BREAKDOWN ---")
        for cat in (HandCategory.SAP, HandCategory.LIENG, HandCategory.DI, HandCategory.DIEM):
            cat_records = [r for r in records if r.category == cat]
            profitable = [r for r in cat_records if r.is_raise_profitable]
            print(f" {cat.name:5s}: {len(profitable):3d} / {len(cat_records):3d} classes profitable")
        print("--------------------------\n")
```

**How it works**

- For each category: filter its records, keep the profitable ones, sum their multiplicities, divide by
  the category total.
- Sample hands: the first five profitable IDs (already sorted best-first), plus "(+N more)".
- Format specs: `{cat.name:5s}` pads a string to width 5; `{len(...):3d}` pads an integer to width 3.

---

## Step 12.7 — The pipeline and the interactive mode

📄 **File:** `backend/src/cli.py` — *add to the end*

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

**How it works**

- `run_solver` is the **composition root**: the one place that creates the objects (`WinRateDB`, the
  optional `CallingRangeModel`, then `RangeFinder(db, calling_model)`, injected) and wires the pipeline
  together. Look how short it is: all the real work lives in the engine modules.
- **Build only what you need:** the calling-range tables cost ~50 ms (chapter 9), so they're built only
  when the range model is requested (`… if opponent_model is OpponentModel.RANGE else None`). The default
  random-model run stays as fast as before.
- The **pure-bluff break-even** is just `calculate_break_even_fold_equity` with `win_rate_when_called=0.0`.
- `interactive_mode` asks five questions. Pressing Enter accepts a default (`if pot_str else 100000.0`;
  for the model, `random`). `OpponentModel(model_str.lower())` turns the text into the enum, or raises
  `ValueError` for anything else. `hand_str or None` turns an empty string into `None` ("no hand").
- `KeyboardInterrupt` is what Ctrl-C raises; catching it exits politely instead of printing a traceback.

> ✅ **How the code fixed this (before → after).** The first version caught only `ValueError` here and
> nowhere else: typing `Xx Kh Qd` (interactively or with `--hand`) crashed with a full traceback ending in
> `src.exceptions.InvalidCardError: Invalid rank 'X'…`. Now interactive mode also catches `LiengError` (the
> custom family from chapter 4, built exactly for this), and `main` turns bad input into one clear line
> (Step 12.8). The first version also offered **only the random model**; `--opponent-model` and the
> interactive question fix that.

---

## Step 12.8 — Command-line arguments

📄 **File:** `backend/src/cli.py` — *add to the end*

```python


def main(argv: Sequence[str] | None = None) -> None:
    """CLI argument entry point."""
    parser = argparse.ArgumentParser(description="Liêng Stealer - Game-Theoretic Solver & Heatmap Viewer")
    parser.add_argument("--pot", type=float, default=None, help="Current pot size (e.g. 100000)")
    parser.add_argument("--bet", type=float, default=None, help="Bet / Raise size (e.g. 50000)")
    parser.add_argument(
        "--fold-equity",
        "--p-fold",
        dest="fold_equity",
        type=float,
        default=None,
        help="Opponent fold probability between 0.0 and 1.0 (e.g. 0.35)",
    )
    parser.add_argument(
        "--hand",
        type=str,
        default=None,
        help="Player hand to evaluate (e.g. 'As Kh Qd' or 'As,Kh,Qd')",
    )
    parser.add_argument(
        "--db",
        type=str,
        default="data/winrates.json",
        help="Path to winrates database (default: data/winrates.json)",
    )
    parser.add_argument(
        "--opponent-model",
        choices=[m.value for m in OpponentModel],
        default=OpponentModel.RANDOM.value,
        help="How the opponent folds: 'random' or 'range' (weakest hands first). Default: random",
    )

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


if __name__ == "__main__":
    main()
```

**How it works**

- Two spellings for one option: `"--fold-equity", "--p-fold"` with `dest="fold_equity"` (the attribute
  name in `args`).
- All defaults are `None` on purpose: that's how the code knows whether the user passed **nothing at
  all** (→ interactive mode) or at least one option (→ fill the missing ones with defaults and run).
- `x if x is not None else default` (not `x or default`): with `or`, a legitimate `--fold-equity 0`
  would be treated as "missing", because `0.0` is falsy. That's a classic bug to avoid.
- `--opponent-model` uses `choices=[m.value for m in OpponentModel]`: argparse itself rejects anything
  else (with a usage message and exit code 2), and the list comes from the enum, so it can't go stale.
- **Errors become a message and an exit code.** `run_solver` is wrapped in `try/except (LiengError,
  ValueError)`: a bad hand (`LiengError`) or an impossible number such as a negative pot (`ValueError` from
  `ev.py`) prints `Invalid input: …` on **standard error** (`file=sys.stderr`, the channel for error
  messages) and exits with status **2**, the conventional "you used the command wrongly" code (argparse
  uses it too). Scripts that call the CLI can check `$?` instead of parsing a traceback.

---

## ✅ Checkpoint

From `backend/`:

```bash
python -m src.cli --pot 100000 --bet 50000 --fold-equity 0.35 --hand "As Kh Qd"
```

Expected output (colours not shown; the category table between the panels is omitted here):

```
╭───────────────────── LIÊNG STEALER - GAME STATE BANNER ──────────────────────╮
│ Pot Size (Dead Money): 100,000                                               │
│ Bet / Raise Sizing: 50,000                                                   │
│ Opponent Fold Equity: 35.0%                                                  │
│ Opponent Model: folds at random (random)                                     │
│ Pure Bluff Break-Even Fold Equity: 33.3%                                     │
│ Final Pot (if called): 200,000                                               │
╰──────────────────────────────────────────────────────────────────────────────╯
╭────────────────────────── TACTICAL SOLVER OVERVIEW ──────────────────────────╮
│ Profitable Classes: 455 / 455 canonical classes                              │
│ Combos in Range: 22,100 / 22,100 total combinations                          │
│ Total Range Coverage: 100.00%                                                │
│ Highest EV Hand: A-A-A (EV: +132,500)                                        │
│ Threshold Hand (EV > 0): 4-3-3 (EV: +2,513)                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
                       Range Matrix Breakdown by Category
 ... (table: Sáp 52/52, Liêng 768/768, Đĩ 144/144, Điểm 21,136/21,136) ...
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

Now the junk hand against a calling station:

```bash
python -m src.cli --pot 100000 --bet 50000 --fold-equity 0.05 --hand "2s 3h 5d"
```

The overview should say **354 / 455** classes, **77.81%** coverage, threshold hand **J-8-4**, and the
decision panel:

```
│ Hand Evaluated: 2s 3h 5d (0 điểm (Bù))                                       │
│ Canonical Class: 5-3-2 (Điểm)                                                │
│ Showdown Equity: 0.24%                                                       │
│ Expected Value (EV): -42,044                                                 │
│ Break-Even Fold Equity: 33.12%                                               │
│                                                                              │
│  >>> ACTION: CHECK / FOLD RECOMMENDED <<<                                    │
```

Now the **same medium hand under both opponent models** (pot-sized bet, 35% folds):

```bash
python -m src.cli --pot 100000 --bet 100000 --fold-equity 0.35 --hand "Ks Qh 3d"
python -m src.cli --pot 100000 --bet 100000 --fold-equity 0.35 --hand "Ks Qh 3d" --opponent-model range
```

The first panel shows `Showdown Equity: 36.00%`, `+40,200` and **RAISE / ALL-IN RECOMMENDED**. The second
shows `Opponent Model: folds weakest hands first (range)` in the banner, then `Showdown Equity: 1.08%`,
`-27,894`, `Break-Even Fold Equity: n/a (range model)` and **CHECK / FOLD RECOMMENDED**.

And a typo:

```bash
python -m src.cli --hand "Xx Kh Qd"; echo "exit code: $?"
```

After the report, the last lines are:

```
Invalid input: Invalid rank 'X'. Must be 2-10, T, J, Q, K, or A.
exit code: 2
```

Try interactive mode too (`python -m src.cli` with no options) and press Enter five times to accept the
defaults.

---

## Step 12.9 — Tests for the CLI

A command-line program is still code with behaviour worth protecting. pytest's built-in **`capsys`**
fixture captures everything printed to standard output and standard error, so a test can call `main([...])`
and inspect the text.

📄 **File:** `backend/tests/test_cli.py` — *create this file*

```python
"""Unit tests for the command-line interface (src/cli.py).

Verifies:
- The default opponent model stays random (backward compatible)
- --opponent-model range flips a medium hand from raise to fold
- Invalid input exits with status 2 and a readable message instead of a traceback
"""

import pytest

from src.cli import main

# K-Q-3 with a pot-sized bet at 35% folds: equity 0.36 vs a random hand, 0.0108 vs a calling range
MEDIUM_HAND = ["--pot", "100000", "--bet", "100000", "--fold-equity", "0.35", "--hand", "Ks Qh 3d"]


def test_default_model_is_random(capsys):
    main(MEDIUM_HAND)
    assert "RAISE / ALL-IN RECOMMENDED" in capsys.readouterr().out


def test_range_model_recommends_fold(capsys):
    main(MEDIUM_HAND + ["--opponent-model", "range"])
    assert "CHECK / FOLD RECOMMENDED" in capsys.readouterr().out


@pytest.mark.parametrize("argv", [["--hand", "Xx Kh Qd"], ["--pot", "-5"]])
def test_invalid_input_exits_with_message(capsys, argv):
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code == 2
    assert "Invalid input" in capsys.readouterr().err
```

**How it works**

- `main(MEDIUM_HAND)` runs the real CLI in-process: no subprocess, no mocks. `capsys.readouterr()` returns
  what was printed, split into `.out` and `.err`.
- The expected decisions come from earlier chapters (36% random equity → raise; 1.08% against the calling
  range → fold), not from the CLI itself.
- `pytest.raises(SystemExit)` catches the `sys.exit(2)`; `exc.value.code` is the exit status. The test
  checks both the status **and** that the message went to `.err` (standard error).
- `@pytest.mark.parametrize` runs one test function with several inputs: here a bad hand and a negative pot.

📄 **File:** `backend/tests/test_cli.py` — *add to the end*

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

- `monkeypatch.setattr("builtins.input", …)` replaces the built-in `input()` for the duration of one test
  only, with a function that returns prepared answers from an **iterator** (`next(replies)`). This is a
  small, honest test double: it replaces the keyboard, the only part that can't run in a test, while
  everything else stays real.
- The second test answers `""` to the model question (the default, random) and then types a bad hand: it
  passes only because interactive mode catches `LiengError`. Remove `LiengError` from that `except` and
  this test fails. That's how you know a test protects the fix.

✅ **Checkpoint**

```bash
python -m pytest tests/test_cli.py -v
```

Expected: **6 passed** (the parametrized test counts twice). The whole suite now has 70 tests. Commit:

```bash
git add . && git commit -m "feat: CLI with opponent models, clean errors and tests"
```

## Recap

- The CLI is pure presentation: `main` (argparse) → `run_solver` (wires DB + finder) → four render functions.
- Each renderer has a **rich** branch and a **plain** fallback, chosen by `HAS_RICH`.
- Defaults of `None` distinguish "no options given" (interactive mode) from "some options given".
- `--opponent-model {random,range}` and an interactive question choose the opponent model; the calling-range
  tables are built only when needed.
- Bad input prints `Invalid input: …` on stderr and exits with status 2; interactive mode catches `LiengError`.
- `capsys` and `monkeypatch` make a CLI testable in-process.
- Pitfalls: import-time side effects and a swallowed exception; hard-coded category totals.

**Next:** [13 — The Flask web API](13-flask-api.md)