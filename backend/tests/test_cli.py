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
    assert "Exiting session: Invalid card 'Xx': Invalid rank 'X'" in capsys.readouterr().out
