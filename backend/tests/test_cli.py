"""Unit tests for the command-line interface (src/cli.py).

Verifies:
- The default opponent model stays random (backward compatible)
- --opponent-model range re-prices the ladder of a medium hand
- The report shows the advice action, its kind, the why line, and the three rungs
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


@pytest.fixture
def plain(monkeypatch):
    """The plain-text report, which does not wrap at the console width."""
    import src.cli as cli

    monkeypatch.setattr(cli, "HAS_RICH", False)


def test_default_model_is_random(capsys):
    main(MEDIUM_HAND)
    output = capsys.readouterr().out
    assert ">>> ACTION: SMALL BET (33,000) — BLUFF <<<" in output
    assert "Why: Small bluff: EV is +52,393.18" in output


def test_range_model_reprices_the_ladder(plain, capsys):
    """Both models say 'small bluff', but the calling range kills the bigger rungs."""
    main(MEDIUM_HAND + ["--opponent-model", "range"])
    output = capsys.readouterr().out
    assert ">>> ACTION: SMALL BET (33,000) — BLUFF <<<" in output
    assert "Why: Small bluff: EV is +14,715.32 but the win rate is low (1.08%)" in output
    assert "EV      -11,995  worst -12.00% of pot  blocked: EV_BELOW_FLOOR" in output
    assert "EV      -27,894  worst -27.89% of pot  blocked: EV_BELOW_FLOOR" in output


def test_the_report_shows_the_whole_ladder_with_markers(plain, capsys):
    main(MEDIUM_HAND)
    output = capsys.readouterr().out
    assert "Ladder:" in output
    assert "  ✓ SMALL BET     33,000  EV +   52,393.18  worst +45.07% of pot  <- recommended" in output
    assert "  ✗ LARGE BET     75,000  EV +   44,748.76  worst +36.25% of pot  blocked: BLUFF_TOO_SMALL_ONLY" in output
    assert "  ✗ ALL IN       100,000  EV +   40,198.52  worst +31.00% of pot  blocked: BLUFF_TOO_SMALL_ONLY" in output


def test_a_monster_shoves_and_every_rung_clears(plain, capsys):
    main(["--hand", "As Kh Qd", "--opponent-model", "range"])
    output = capsys.readouterr().out
    assert ">>> ACTION: ALL IN (100,000) — VALUE <<<" in output
    assert "Why: All in: you win about 99.52% at showdown, so +164,064 is worth risking the pot" in output
    assert "  ✓ ALL IN       100,000  EV +     164,064  worst +154.08% of pot  <- recommended" in output


def test_an_edge_under_the_floor_checks_and_quotes_the_best_rung(plain, capsys):
    """A-K-10 at a 5% fold rate: the best size earns 2.36% of the pot, under the 5% floor."""
    main(["--hand", "As Kh 10d", "--pot", "100000", "--bet", "50000", "--fold-equity", "0.05"])
    output = capsys.readouterr().out
    assert ">>> ACTION: CHECK (0) — BLUFF <<<" in output
    assert "Why: Check: betting earns only 2.36% of the pot, under the 5% we need." in output


def test_every_size_losing_checks_and_shows_each_rung_refused(plain, capsys):
    main(["--hand", "2s 3h 5d", "--pot", "100000", "--bet", "50000", "--fold-equity", "0.05"])
    output = capsys.readouterr().out
    assert ">>> ACTION: CHECK (0) — BLUFF <<<" in output
    assert "Why: Check: every size loses money at your fold assumption (best case -25.98% of pot)." in output
    assert "  ✗ SMALL BET     33,000  EV   -25,977.66  worst -32.61% of pot  blocked: EV_BELOW_FLOOR" in output


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
    assert ">>> ACTION: SMALL BET (33,000) — BLUFF <<<" in capsys.readouterr().out


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
    output = capsys.readouterr().out
    assert ">>> ACTION: SMALL BET (33,000) — BLUFF <<<" in output
    assert "Why: Small bluff: EV is +14,715.32" in output


def test_plain_text_report_shows_the_sign_of_a_positive_ev(monkeypatch, capsys):
    import src.cli as cli

    monkeypatch.setattr(cli, "HAS_RICH", False)
    main(["--hand", "As Kh Qd"])
    output = capsys.readouterr().out
    assert "Expected Value:     +132,101.34" in output
    assert ">>> ACTION: ALL IN (100,000) — VALUE <<<" in output


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
