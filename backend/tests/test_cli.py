"""Unit tests for the command-line interface (src/cli.py).

Verifies:
- The default opponent model stays random (backward compatible)
- --opponent-model range flips a medium hand from raise to fold
- Invalid input exits with status 2 and a readable message instead of a traceback,
  before any part of the report is printed
- A missing database exits with status 1 and its own message
- Interactive mode: exit 2 after bad input, clean exit on end of input,
  --opponent-model as the default answer
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
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2
    assert "Exiting session: Invalid card 'Xx': Invalid rank 'X'" in capsys.readouterr().out


def test_invalid_hand_is_reported_before_any_output(capsys):
    with pytest.raises(SystemExit):
        main(["--hand", "As Xh Kd"])
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("Invalid input: Invalid card 'Xh'")


def test_missing_database_has_its_own_message_and_exit_code(capsys, tmp_path):
    with pytest.raises(SystemExit) as exc:
        main(["--hand", "As Kh Qd", "--db", str(tmp_path / "missing.json")])
    assert exc.value.code == 1
    assert "Cannot load the win-rate database" in capsys.readouterr().err


def test_interactive_mode_ends_cleanly_at_end_of_input(monkeypatch, capsys):
    def no_more_input(_prompt):
        raise EOFError

    monkeypatch.setattr("builtins.input", no_more_input)
    main([])  # returns normally: exit code 0
    assert "Exiting session: no more input." in capsys.readouterr().out


def test_interactive_mode_uses_the_opponent_model_flag_as_default(monkeypatch, capsys):
    _answer_prompts(monkeypatch, ["100000", "100000", "0.35", "", "Ks Qh 3d"])
    main(["--opponent-model", "range"])
    assert "CHECK / FOLD RECOMMENDED" in capsys.readouterr().out


def test_plain_text_report_shows_the_sign_of_a_positive_ev(monkeypatch, capsys):
    import src.cli as cli

    monkeypatch.setattr(cli, "HAS_RICH", False)
    main(["--hand", "As Kh Qd"])
    assert "Expected Value:     +132,097" in capsys.readouterr().out


def test_a_broken_model_is_an_internal_error_not_invalid_input(monkeypatch, capsys):
    import src.cli as cli
    from src.exceptions import ModelError

    def broken_model(*args, **kwargs):
        raise ModelError("classes are not distinct")

    monkeypatch.setattr(cli, "CallingRangeModel", broken_model)
    with pytest.raises(SystemExit) as exc:
        main(["--hand", "As Kh Qd", "--opponent-model", "range"])
    assert exc.value.code == 1
    assert "Internal model error: classes are not distinct" in capsys.readouterr().err
