"""Unit tests for the Simulation Engine & Offline Winrates Generator.

Verifies:
- Exact equity calculations (A-A-A is unbeatable, 2-2-2 beats Q-K-A, Q-K-A beats A-2-3)
- Rate sum invariants: win_rate + tie_rate + loss_rate == 1.0
- Equity formula invariant: equity == win_rate + 0.5 * tie_rate
- Monte Carlo convergence against exact values
- File output integrity & JSON schema conformance for data/winrates.json
"""

import json
from pathlib import Path

import pytest

from src.generator import (
    build_parser,
    compute_hand_equity,
)
from src.hands import (
    generate_all_canonical_hands,
)


@pytest.fixture(scope="module")
def canonical_map() -> dict:
    hands = generate_all_canonical_hands()
    return {h.canonical_id: h for h in hands}


class TestGeneratorEngine:
    """Test suite for simulation engine and equity calculations."""

    def test_aaa_exact_equity(self, canonical_map: dict) -> None:
        """A-A-A is the maximum hand in Liêng and can never tie or lose heads-up."""
        aaa = canonical_map["A-A-A"]
        res = compute_hand_equity(aaa, exact=True)
        assert res["equity"] == 1.0
        assert res["win_rate"] == 1.0
        assert res["tie_rate"] == 0.0
        assert res["loss_rate"] == 0.0
        assert res["samples"] == 18424
        assert res["category"] == "SAP"

    def test_equity_hierarchy_monotonicity(self, canonical_map: dict) -> None:
        """Verify strict hierarchical equity relationships:
        A-A-A > 2-2-2 > Q-K-A > A-2-3 > Đĩ > 0 points (Bù).
        """
        aaa = compute_hand_equity(canonical_map["A-A-A"], exact=True)
        two22 = compute_hand_equity(canonical_map["2-2-2"], exact=True)
        qka = compute_hand_equity(canonical_map["Q-K-A"], exact=True)
        a23 = compute_hand_equity(canonical_map["A-2-3"], exact=True)
        qkk = compute_hand_equity(canonical_map["K-K-Q"], exact=True)  # Đĩ

        # Sáp A beats Sáp 2
        assert aaa["equity"] > two22["equity"]
        # Lowest Sáp (2-2-2) beats Highest Liêng (Q-K-A)
        assert two22["equity"] > qka["equity"]
        # Highest Liêng (Q-K-A) beats Lowest Liêng (A-2-3)
        assert qka["equity"] > a23["equity"]
        # Lowest Liêng (A-2-3) beats Đĩ
        assert a23["equity"] > qkk["equity"]

    def test_rate_invariants(self, canonical_map: dict) -> None:
        """Check mathematical consistency across multiple sample hands."""
        test_keys = ["A-A-A", "Q-K-A", "A-2-3", "9-8-7", "K-K-Q", "K-J-10"]
        for key in test_keys:
            assert key in canonical_map, f"{key} is not a canonical ID"
            res = compute_hand_equity(canonical_map[key], exact=True)
            # win_rate + tie_rate + loss_rate == 1.0 (within rounding precision)
            total_prob = res["win_rate"] + res["tie_rate"] + res["loss_rate"]
            assert abs(total_prob - 1.0) <= 0.001

            # equity == win_rate + 0.5 * tie_rate
            expected_equity = res["win_rate"] + 0.5 * res["tie_rate"]
            assert abs(res["equity"] - expected_equity) <= 0.001

    def test_monte_carlo_convergence(self, canonical_map: dict) -> None:
        """Monte Carlo with N=5000 should converge to within 1.5% of exact equity."""
        qka = canonical_map["Q-K-A"]
        exact_res = compute_hand_equity(qka, exact=True)
        mc_res = compute_hand_equity(qka, exact=False, samples=5000, seed=42)

        assert abs(exact_res["equity"] - mc_res["equity"]) < 0.015

    def test_generated_json_database_schema(self) -> None:
        """Verify the precomputed data/winrates.json conforms to the complete schema."""
        db_path = Path("data/winrates.json")
        if not db_path.exists():
            db_path = Path(__file__).resolve().parent.parent / "data" / "winrates.json"
        assert db_path.exists(), "data/winrates.json must exist"

        with open(db_path, encoding="utf-8") as f:
            data = json.load(f)

        assert len(data) == 455, f"Expected 455 canonical hands, got {len(data)}"

        required_keys = {
            "equity", "win_rate", "tie_rate", "loss_rate",
            "category", "multiplicity", "samples"
        }

        for cid, profile in data.items():
            assert required_keys.issubset(profile.keys()), f"Missing keys in {cid}"
            assert 0.0 <= profile["equity"] <= 1.0
            assert profile["samples"] == 18424
            assert profile["category"] in {"SAP", "LIENG", "DI", "DIEM"}
            assert profile["multiplicity"] in {4, 24, 64}


class TestGeneratorCommandLine:
    """The command line must produce the exact database by default (the tests above require it)."""

    def test_defaults_to_exact_enumeration(self) -> None:
        assert build_parser().parse_args([]).exact is True

    def test_monte_carlo_is_opt_in(self) -> None:
        args = build_parser().parse_args(["--monte-carlo", "--samples", "500"])
        assert args.exact is False
        assert args.samples == 500


class TestGeneratorSafety:
    def test_exact_and_monte_carlo_are_mutually_exclusive(self) -> None:
        with pytest.raises(SystemExit):
            build_parser().parse_args(["--exact", "--monte-carlo"])

    def test_samples_must_be_positive(self) -> None:
        with pytest.raises(SystemExit):
            build_parser().parse_args(["--monte-carlo", "--samples", "0"])

    def test_default_output_does_not_depend_on_the_current_directory(self) -> None:
        from src.paths import DEFAULT_DB_PATH

        assert build_parser().parse_args([]).output == DEFAULT_DB_PATH
        assert DEFAULT_DB_PATH.is_absolute()

    def test_seeded_monte_carlo_leaves_global_random_untouched(self, canonical_map: dict) -> None:
        import random

        random.seed(123)
        expected = random.random()
        random.seed(123)
        compute_hand_equity(canonical_map["Q-K-A"], exact=False, samples=50, seed=1)
        assert random.random() == expected

    def test_write_is_complete_and_leaves_no_temp_file(self, tmp_path: Path) -> None:
        from src.generator import generate_winrates_database

        out = tmp_path / "nested" / "winrates.json"
        generate_winrates_database(exact=False, samples=5, output_path=out, workers=1)
        assert len(json.loads(out.read_text(encoding="utf-8"))) == 455
        assert [p.name for p in out.parent.iterdir()] == ["winrates.json"]


class TestGeneratorFileHandling:
    def test_new_file_gets_normal_permissions(self, tmp_path: Path) -> None:
        import os

        from src.generator import generate_winrates_database

        umask = os.umask(0)
        os.umask(umask)
        out = tmp_path / "winrates.json"
        generate_winrates_database(exact=False, samples=2, output_path=out, workers=1)
        assert out.stat().st_mode & 0o777 == 0o644 & ~umask

    def test_existing_file_keeps_its_permissions(self, tmp_path: Path) -> None:
        from src.generator import generate_winrates_database

        out = tmp_path / "winrates.json"
        out.write_text("{}", encoding="utf-8")
        out.chmod(0o640)
        generate_winrates_database(exact=False, samples=2, output_path=out, workers=1)
        assert out.stat().st_mode & 0o777 == 0o640

    def test_failed_write_leaves_the_old_file_and_no_temp_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from src import generator

        out = tmp_path / "winrates.json"
        out.write_text('{"old": true}', encoding="utf-8")

        def broken_dump(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(generator.json, "dump", broken_dump)
        with pytest.raises(OSError):
            generator.generate_winrates_database(exact=False, samples=2, output_path=out, workers=1)
        assert out.read_text(encoding="utf-8") == '{"old": true}'
        assert [p.name for p in tmp_path.iterdir()] == ["winrates.json"]
