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

from src.db import WinRateDB
from src.evaluator import Hand, HandCategory
from src.ev import calculate_break_even_fold_equity, calculate_ev, evaluate_action
from src.hands import to_canonical
from src.range_finder import HandEVRecord, RangeFinder

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


def format_currency(val: float) -> str:
    """Format numerical value with thousand separators."""
    return f"{val:,.0f}" if val == int(val) else f"{val:,.2f}"


def render_banner(
    pot: float,
    bet_size: float,
    fold_equity: float,
    be_bluff_fe: float,
) -> None:
    """Render the game state banner."""
    if HAS_RICH:
        console = _console or Console(legacy_windows=False)
        content = (
            f"[bold cyan]Pot Size (Dead Money):[/] {format_currency(pot)}\n"
            f"[bold cyan]Bet / Raise Sizing:[/] {format_currency(bet_size)}\n"
            f"[bold cyan]Opponent Fold Equity:[/] {fold_equity * 100:.1f}%\n"
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
        print(f" Pure Bluff Break-Even FE:    {be_bluff_fe * 100:.1f}%")
        print(f" Final Pot (if called):       {format_currency(pot + 2.0 * bet_size)}")
        print("=" * 60)


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


def render_single_hand_decision(
    hand_str: str,
    db: WinRateDB,
    pot: float,
    bet_size: float,
    fold_equity: float,
) -> None:
    """Evaluate and render recommendation for a specific player hand."""
    hand = Hand.from_str(hand_str)
    stats = db.get_by_cards(hand.cards)
    ev_result = evaluate_action(pot, bet_size, fold_equity, stats.equity)

    status_color = "green" if ev_result.is_profitable else "red"
    action_text = "BET +EV" if ev_result.is_profitable else "NO BET (+EV NOT ESTABLISHED)"

    if HAS_RICH:
        console = _console or Console(legacy_windows=False)
        content = (
            f"[bold]Hand Evaluated:[/] {hand} ([italic]{hand.score}[/])\n"
            f"[bold]Canonical Class:[/] {to_canonical(hand.cards).canonical_id} ([cyan]{stats.category.display_name}[/])\n"
            f"[bold]Showdown Equity:[/] {stats.equity * 100:.2f}%\n"
            f"[bold]Expected Value (EV):[/] [{status_color}]{'+' if ev_result.ev > 0 else ''}{format_currency(ev_result.ev)}[/]\n"
            f"[bold]Break-Even Fold Equity:[/] {ev_result.break_even_fold_equity * 100:.2f}%\n\n"
            f"[bold {status_color} reverse] >>> ACTION: {action_text} <<< [/]"
        )
        console.print(Panel(content, title="[bold magenta]HAND EVALUATION & ACTION[/]", border_style=status_color))
    else:
        print("\n================ HAND EVALUATION ================")
        print(f" Hand:               {hand} ({hand.score})")
        print(f" Canonical Class:    {to_canonical(hand.cards).canonical_id} ({stats.category.display_name})")
        print(f" Showdown Equity:    {stats.equity * 100:.2f}%")
        print(f" Expected Value:     {format_currency(ev_result.ev)}")
        print(f" Break-Even FE:      {ev_result.break_even_fold_equity * 100:.2f}%")
        print(f" >>> ACTION: {action_text} <<<")
        print("=================================================\n")


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


def run_solver(
    pot: float,
    bet_size: float,
    fold_equity: float,
    hand_str: str | None = None,
    db_path: str = "data/winrates.json",
) -> None:
    """Execute the range solver pipeline and render visual reports."""
    db = WinRateDB(db_path)
    finder = RangeFinder(db)

    be_bluff = calculate_break_even_fold_equity(pot, bet_size, win_rate_when_called=0.0)
    records = finder.solve_range(pot, bet_size, fold_equity)
    profitable = [r for r in records if r.is_raise_profitable]
    coverage = finder.calculate_range_coverage(profitable)

    render_banner(pot, bet_size, fold_equity, be_bluff)
    render_tactical_overview(records, coverage)
    render_categorized_heatmap(records)

    if hand_str:
        render_single_hand_decision(hand_str, db, pot, bet_size, fold_equity)


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

        hand_str = input("Enter your hand (e.g. 'As Kh Qd' or press Enter to skip): ").strip()
        run_solver(pot, bet, fold_equity, hand_str=hand_str or None, db_path=db_path)
    except (ValueError, KeyboardInterrupt) as err:
        print(f"\nExiting session: {err}")


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

    args = parser.parse_args(argv)

    if args.pot is None and args.bet is None and args.fold_equity is None and args.hand is None:
        interactive_mode(args.db)
    else:
        pot = args.pot if args.pot is not None else 100000.0
        bet = args.bet if args.bet is not None else 50000.0
        fold_equity = args.fold_equity if args.fold_equity is not None else 0.35
        run_solver(pot=pot, bet_size=bet, fold_equity=fold_equity, hand_str=args.hand, db_path=args.db)


if __name__ == "__main__":
    main()
