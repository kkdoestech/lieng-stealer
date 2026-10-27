"""Unit tests for the In-Memory Database Layer (WinRateDB).

Verifies:
- Complete loading of all 455 canonical records from data/winrates.json
- High-speed O(1) hash table lookup latency (< 5 microseconds)
- Error handling on nonexistent files, malformed data, and queries before load
- Accurate mapping from concrete Card sequences via get_by_cards()
"""

import json
import time
from pathlib import Path

import pytest

from src.db import HandStats, WinRateDB
from src.evaluator import Card, HandCategory
from src.exceptions import DatabaseError, DatabaseNotLoadedError, UnknownHandError
from src.paths import DEFAULT_DB_PATH
from tests.perf import budget


class TestWinRateDB:
    """Test suite for WinRateDB repository."""

    @pytest.fixture
    def loaded_db(self) -> WinRateDB:
        db = WinRateDB()
        db.load("data/winrates.json")
        return db

    def test_load_all_records(self, loaded_db: WinRateDB) -> None:
        """Ensure all 455 canonical hands are present and properly parsed."""
        assert len(loaded_db) == 455
        assert loaded_db.is_loaded is True

        # Test Sáp A
        aaa_stats = loaded_db.get("A-A-A")
        assert isinstance(aaa_stats, HandStats)
        assert aaa_stats.equity == 1.0
        assert aaa_stats.category == HandCategory.SAP
        assert aaa_stats.multiplicity == 4

        # Test Liêng Q-K-A
        qka_stats = loaded_db.get("Q-K-A")
        assert qka_stats.equity == pytest.approx(0.9969, abs=0.00005)
        assert qka_stats.category == HandCategory.LIENG
        assert qka_stats.multiplicity == 64

    def test_lookup_latency_budget(self, loaded_db: WinRateDB) -> None:
        """Verify O(1) hash table query latency is strictly < 5.0 microseconds per lookup."""
        n_queries = 50000
        key = "Q-K-A"

        start_time = time.perf_counter()
        for _ in range(n_queries):
            _ = loaded_db.get(key)
        elapsed = time.perf_counter() - start_time

        avg_latency_us = (elapsed / n_queries) * 1e6
        # Assert well within the 5 microsecond budget
        assert avg_latency_us < budget(5.0), f"Lookup latency too high: {avg_latency_us:.3f} us"

    def test_get_by_cards(self, loaded_db: WinRateDB) -> None:
        """Ensure concrete Card sequences correctly resolve to canonical stats."""
        cards = [Card.from_str("Qs"), Card.from_str("Kh"), Card.from_str("Ad")]
        stats = loaded_db.get_by_cards(cards)

        assert stats.category == HandCategory.LIENG
        assert stats.equity == pytest.approx(0.9969, abs=0.00005)

    def test_unloaded_query_raises(self) -> None:
        """Querying an unloaded DB instance must raise DatabaseNotLoadedError."""
        empty_db = WinRateDB()
        assert empty_db.is_loaded is False

        with pytest.raises(DatabaseNotLoadedError):
            empty_db.get("A-A-A")

        with pytest.raises(DatabaseNotLoadedError):
            empty_db.all_items()

    def test_nonexistent_file_raises(self) -> None:
        """Attempting to load a nonexistent file raises DatabaseError."""
        db = WinRateDB()
        with pytest.raises(DatabaseError):
            db.load("data/nonexistent_file.json")

    def test_key_error_on_invalid_id(self, loaded_db: WinRateDB) -> None:
        """Querying an unknown canonical ID raises KeyError."""
        with pytest.raises(KeyError):
            loaded_db.get("INVALID_KEY")


def _write(tmp_path: Path, records: object) -> Path:
    path = tmp_path / "winrates.json"
    path.write_text(json.dumps(records), encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def real_records() -> dict:
    return json.loads(DEFAULT_DB_PATH.read_text(encoding="utf-8"))


class TestDatabaseValidation:
    """The loader rejects files that parse but don't describe the 455 hands (weak spot M11)."""

    def test_malformed_json(self, tmp_path: Path) -> None:
        path = tmp_path / "winrates.json"
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(DatabaseError, match="Malformed JSON"):
            WinRateDB(path)

    def test_missing_class(self, tmp_path: Path, real_records: dict) -> None:
        records = dict(real_records)
        del records["Q-K-A"]
        with pytest.raises(DatabaseError, match="1 missing"):
            WinRateDB(_write(tmp_path, records))

    def test_rate_above_one(self, tmp_path: Path, real_records: dict) -> None:
        records = {cid: dict(stats) for cid, stats in real_records.items()}
        records["A-A-A"]["equity"] = 1.5
        with pytest.raises(DatabaseError, match="outside"):
            WinRateDB(_write(tmp_path, records))

    def test_wrong_multiplicity(self, tmp_path: Path, real_records: dict) -> None:
        records = {cid: dict(stats) for cid, stats in real_records.items()}
        records["A-A-A"]["multiplicity"] = 64
        with pytest.raises(DatabaseError, match="expected SAP x4"):
            WinRateDB(_write(tmp_path, records))

    def test_failed_reload_keeps_previous_data(self, tmp_path: Path) -> None:
        db = WinRateDB(DEFAULT_DB_PATH)
        before = db.get("Q-K-A")
        with pytest.raises(DatabaseError):
            db.load(_write(tmp_path, {"A-A-A": {}}))
        assert db.is_loaded and db.get("Q-K-A") == before

    def test_default_path_works_from_any_directory(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        db = WinRateDB()
        db.load()
        assert len(db) == 455

    def test_unknown_id_is_a_project_error_and_a_key_error(self) -> None:
        db = WinRateDB(DEFAULT_DB_PATH)
        with pytest.raises(UnknownHandError):
            db.get("J-Q-K")
        with pytest.raises(KeyError):
            db.get("J-Q-K")
