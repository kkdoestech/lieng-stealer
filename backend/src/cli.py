"""Liêng Stealer - Interactive CLI Decision Support & Range Heatmap Engine.

Provides rich visual displays of game states, solver summaries, categorized
range matrices, and single-hand decision recommendations.

Exit codes: 0 success, 1 the win-rate database could not be loaded, 2 invalid input,
130 interrupted with Ctrl-C.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

from src.calling_range import CallingRangeModel, OpponentModel
from src.db import WinRateDB
from src.ev import (
    DEFAULT_BET_SIZE,
    DEFAULT_FOLD_EQUITY,
    DEFAULT_POT,
    calculate_break_even_fold_equity,
    evaluate_action,
    final_pot,
)
from src.evaluator import Hand, HandCategory
from src.exceptions import DatabaseError, InvalidGameParamsError, LiengError
from src.hands import TOTAL_COMBINATIONS, to_canonical
from src.paths import DEFAULT_DB_PATH
from src.range_finder import HandEVRecord, RangeFinder, category_breakdown

MODEL_DESCRIPTIONS = {
    OpponentModel.RANDOM: "folds at random (random)",
    OpponentModel.RANGE: "folds weakest hands first (range)",
}

CATEGORY_LABELS = {
    HandCategory.SAP: "Sáp (Triples)",
    HandCategory.LIENG: "Liêng (Straights)",
    HandCategory.DI: "Đĩ (Face Cards)",
    HandCategory.DIEM: "Điểm (Points)",
}

EXIT_DATABASE_ERROR = 1
EXIT_INVALID_INPUT = 2
EXIT_INTERRUPTED = 130

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


def _use_utf8_stdout() -> None:
    """Ask the terminal stream for UTF-8 so Vietnamese text prints on Windows consoles."""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        try:
            reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass  # a stream that can't be reconfigured (e.g. already detached) keeps its encoding


def format_currency(val: float) -> str:
    """Format numerical value with thousand separators."""
    return f"{val:,.0f}" if val == int(val) else f"{val:,.2f}"


def render_banner(
    pot: float,
    bet_size: float,
    fold_equity: float,
    be_bluff_fe: float,
    opponent_model: OpponentModel = OpponentModel.RANDOM,
) -> None:
    """Render the game state banner."""
    if HAS_RICH:
        content = (
            f"[bold cyan]Pot Size (Dead Money):[/] {format_currency(pot)}\n"
            f"[bold cyan]Bet / Raise Sizing:[/] {format_currency(bet_size)}\n"
            f"[bold cyan]Opponent Fold Equity:[/] {fold_equity * 100:.1f}%\n"
            f"[bold cyan]Opponent Model:[/] {MODEL_DESCRIPTIONS[opponent_model]}\n"
            f"[bold yellow]Pure Bluff Break-Even Fold Equity:[/] {be_bluff_fe * 100:.1f}%\n"
            f"[bold cyan]Final Pot (if called):[/] {format_currency(final_pot(pot, bet_size))}"
        )
        _console().print(Panel(content, title="[bold green]LIÊNG STEALER - GAME STATE BANNER[/]", border_style="green"))
    else:
        print("=" * 60)
        print(" LIÊNG STEALER - GAME STATE BANNER")
        print("=" * 60)
        print(f" Pot Size (Dead Money):       {format_currency(pot)}")
        print(f" Bet / Raise Sizing:          {format_currency(bet_size)}")
        print(f" Opponent Fold Equity:        {fold_equity * 100:.1f}%")
        print(f" Opponent Model:              {MODEL_DESCRIPTIONS[opponent_model]}")
        print(f" Pure Bluff Break-Even FE:    {be_bluff_fe * 100:.1f}%")
        print(f" Final Pot (if called):       {format_currency(final_pot(pot, bet_size))}")
        print("=" * 60)


def render_solver_overview(
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
        content = (
            f"[bold]Profitable Classes:[/] {len(profitable)} / {len(records)} canonical classes\n"
            f"[bold]Combos in Range:[/] [green]{total_combos:,}[/] / {TOTAL_COMBINATIONS:,} total combinations\n"
            f"[bold]Total Range Coverage:[/] [bold green]{coverage:.2f}%[/]\n"
            f"[bold]Highest EV Hand:[/] [green]{highest_desc}[/]\n"
            f"[bold]Threshold Hand (EV > 0):[/] [yellow]{lowest_desc}[/]"
        )
        _console().print(Panel(content, title="[bold blue]SOLVER OVERVIEW[/]", border_style="blue"))
    else:
        print("\n--- SOLVER OVERVIEW ---")
        print(f" Profitable Classes:   {len(profitable)} / {len(records)}")
        print(f" Combos in Range:      {total_combos:,} / {TOTAL_COMBINATIONS:,} combinations")
        print(f" Range Coverage:       {coverage:.2f}%")
        print(f" Highest EV Hand:      {highest_desc}")
        print(f" Threshold Hand:       {lowest_desc}")
        print("-----------------------\n")


def render_single_hand_decision(
    hand: Hand,
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
    canonical_id = to_canonical(hand.cards).canonical_id
    stats = db.get(canonical_id)
    equity = calling_model.equity(canonical_id, fold_equity) if calling_model else stats.equity
    ev_result = evaluate_action(pot, bet_size, fold_equity, equity)
    # Under the range model EV is not monotonic in fold equity, so no single break-even exists
    break_even_text = (
        f"{ev_result.break_even_fold_equity * 100:.2f}%" if calling_model is None else "n/a (range model)"
    )

    status_color = "green" if ev_result.is_profitable else "red"
    action_text = "RAISE / ALL-IN RECOMMENDED" if ev_result.is_profitable else "CHECK / FOLD RECOMMENDED"

    if HAS_RICH:
        content = (
            f"[bold]Hand Evaluated:[/] {hand} ([italic]{hand.score}[/])\n"
            f"[bold]Canonical Class:[/] {canonical_id} ([cyan]{stats.category.display_name}[/])\n"
            f"[bold]Showdown Equity:[/] {equity * 100:.2f}%\n"
            f"[bold]Expected Value (EV):[/] [{status_color}]{'+' if ev_result.ev > 0 else ''}{format_currency(ev_result.ev)}[/]\n"
            f"[bold]Break-Even Fold Equity:[/] {break_even_text}\n\n"
            f"[bold {status_color} reverse] >>> ACTION: {action_text} <<< [/]"
        )
        _console().print(Panel(content, title="[bold magenta]HAND EVALUATION & ACTION[/]", border_style=status_color))
    else:
        print("\n================ HAND EVALUATION ================")
        print(f" Hand:               {hand} ({hand.score})")
        print(f" Canonical Class:    {canonical_id} ({stats.category.display_name})")
        print(f" Showdown Equity:    {equity * 100:.2f}%")
        print(f" Expected Value:     {format_currency(ev_result.ev)}")
        print(f" Break-Even FE:      {break_even_text}")
        print(f" >>> ACTION: {action_text} <<<")
        print("=================================================\n")


def render_categorized_heatmap(records: list[HandEVRecord]) -> None:
    """Render categorized summary tables showing distribution and top hands."""
    breakdown = category_breakdown(records)
    if HAS_RICH:
        table = Table(title="[bold]Range Matrix Breakdown by Category[/]", box=box.ROUNDED)
        table.add_column("Category", style="cyan", justify="left")
        table.add_column("Total Classes", justify="right")
        table.add_column("Profitable Classes", justify="right")
        table.add_column("Combos (EV > 0)", justify="right")
        table.add_column("Category Coverage", justify="right")
        table.add_column("Sample Profitable Hands", justify="left")

        for row in breakdown:
            profitable = [r for r in records if r.category is row.category and r.is_raise_profitable]
            sample_hands = ", ".join(r.canonical_id for r in profitable[:5])
            if len(profitable) > 5:
                sample_hands += f" ... (+{len(profitable) - 5} more)"
            elif not sample_hands:
                sample_hands = "[dim]None[/]"

            table.add_row(
                CATEGORY_LABELS[row.category],
                str(row.classes),
                f"[green]{len(profitable)}[/]",
                f"{row.profitable_combos:,} / {row.combos:,}",
                f"{row.profitable_combos / row.combos * 100.0:.1f}%",
                sample_hands,
            )

        _console().print(table)
    else:
        print("\n--- CATEGORY BREAKDOWN ---")
        for row in breakdown:
            profitable_classes = sum(1 for r in records if r.category is row.category and r.is_raise_profitable)
            print(
                f" {row.category.name:5s}: {profitable_classes:3d} / {row.classes:3d} classes, "
                f"{row.profitable_combos:,} / {row.combos:,} combos profitable"
            )
        print("--------------------------\n")


def run_solver(
    pot: float,
    bet_size: float,
    fold_equity: float,
    hand_str: str | None = None,
    db_path: str | Path = DEFAULT_DB_PATH,
    opponent_model: OpponentModel = OpponentModel.RANDOM,
) -> None:
    """Execute the range solver pipeline and render visual reports.

    Every input is validated before anything is printed, so a bad value never leaves a
    half-printed report behind.

    Raises:
        LiengError: If the hand or a number is invalid (InvalidGameParamsError is also a ValueError).
        DatabaseError: If the win-rate database cannot be loaded.
    """
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


def interactive_mode(
    db_path: str | Path = DEFAULT_DB_PATH,
    default_model: OpponentModel = OpponentModel.RANDOM,
) -> int:
    """Run interactive CLI prompt session and return the process exit code."""
    print("\n--- LIÊNG STEALER: INTERACTIVE SOLVER ---")
    try:
        pot_str = input(f"Enter Pot Size (e.g. {DEFAULT_POT:.0f}): ").strip()
        pot = float(pot_str) if pot_str else DEFAULT_POT

        bet_str = input(f"Enter Bet/Raise Size (e.g. {DEFAULT_BET_SIZE:.0f}): ").strip()
        bet = float(bet_str) if bet_str else DEFAULT_BET_SIZE

        fe_str = input(f"Enter Opponent Fold Probability [0.0 - 1.0] (e.g. {DEFAULT_FOLD_EQUITY}): ").strip()
        fold_equity = float(fe_str) if fe_str else DEFAULT_FOLD_EQUITY

        model_str = input(
            f"Opponent folds 'random' or 'range' (weakest hands first)? [{default_model.value}]: "
        ).strip()
        opponent_model = OpponentModel(model_str.lower()) if model_str else default_model

        hand_str = input("Enter your hand (e.g. 'As Kh Qd' or press Enter to skip): ").strip()
        run_solver(pot, bet, fold_equity, hand_str=hand_str or None, db_path=db_path, opponent_model=opponent_model)
    except DatabaseError as err:
        print(f"Cannot load the win-rate database: {err}", file=sys.stderr)
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


def main(argv: Sequence[str] | None = None) -> None:
    """CLI argument entry point."""
    _use_utf8_stdout()
    parser = argparse.ArgumentParser(description="Liêng Stealer - Expected-Value Solver & Heatmap Viewer")
    parser.add_argument("--pot", type=float, default=None, help=f"Current pot size (e.g. {DEFAULT_POT:.0f})")
    parser.add_argument("--bet", type=float, default=None, help=f"Bet / Raise size (e.g. {DEFAULT_BET_SIZE:.0f})")
    parser.add_argument(
        "--fold-equity",
        "--p-fold",
        dest="fold_equity",
        type=float,
        default=None,
        help=f"Opponent fold probability between 0.0 and 1.0 (e.g. {DEFAULT_FOLD_EQUITY})",
    )
    parser.add_argument(
        "--hand",
        type=str,
        default=None,
        help="Player hand to evaluate (e.g. 'As Kh Qd' or 'As,Kh,Qd')",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Path to winrates database (default: backend/data/winrates.json, wherever you run from)",
    )
    parser.add_argument(
        "--opponent-model",
        choices=[m.value for m in OpponentModel],
        default=OpponentModel.RANDOM.value,
        help="How the opponent folds: 'random' or 'range' (weakest hands first). Default: random. "
             "In interactive mode it becomes the default answer.",
    )

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
    except (LiengError, ValueError) as err:
        # Bad hand text or out-of-range numbers: a clear message and the usage-error exit code
        print(f"Invalid input: {err}", file=sys.stderr)
        sys.exit(EXIT_INVALID_INPUT)


if __name__ == "__main__":
    main()
