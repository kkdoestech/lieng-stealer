"""Liêng Stealer - In-Memory Database Layer & Fast O(1) Cache.

Loads the precomputed canonical equity database (data/winrates.json) into a
typed, immutable in-memory Hash Table for high-performance O(1) decision queries.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.evaluator import Card, HandCategory
from src.exceptions import DatabaseError, DatabaseNotLoadedError, UnknownHandError
from src.hands import generate_all_canonical_hands, get_canonical_id
from src.paths import DEFAULT_DB_PATH

# Rates are rounded to 4 decimals one by one, so win + tie + loss can be off by up to 1e-4.
_RATE_TOLERANCE = 2e-4


@dataclass(frozen=True)
class HandStats:
    """Immutable equity statistics for a canonical hand class."""
    equity: float
    win_rate: float
    tie_rate: float
    loss_rate: float
    category: HandCategory
    multiplicity: int
    samples: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HandStats:
        """Construct a HandStats instance from a dictionary record."""
        return cls(
            equity=float(data["equity"]),
            win_rate=float(data["win_rate"]),
            tie_rate=float(data["tie_rate"]),
            loss_rate=float(data["loss_rate"]),
            category=HandCategory[data["category"]],
            multiplicity=int(data["multiplicity"]),
            samples=int(data["samples"]),
        )


class WinRateDB:
    """In-memory Hash Table repository for canonical win rates.

    Encapsulates loaded state without global variables, allowing clean
    dependency injection across the system.
    """

    def __init__(self, filepath: str | Path | None = None) -> None:
        """Initialize the database, optionally loading from filepath."""
        self._cache: dict[str, HandStats] = {}
        self._is_loaded: bool = False
        if filepath is not None:
            self.load(filepath)

    @property
    def is_loaded(self) -> bool:
        """Check whether the database has been loaded into memory."""
        return self._is_loaded

    def load(self, filepath: str | Path = DEFAULT_DB_PATH) -> None:
        """Load, parse and validate the win rates JSON into memory.

        The new data replaces the old only after every record has parsed and passed validation,
        so a failed load leaves a previously loaded database untouched.

        Args:
            filepath: Path to a winrates.json file (default: backend/data/winrates.json). A relative
                path is tried as given, then relative to the backend folder.

        Raises:
            DatabaseError: If the file is missing, cannot be read, is malformed, or does not
                describe exactly the 455 canonical hands with plausible rates.
        """
        path = Path(filepath)
        if not path.is_file():
            # Fallback check relative to backend root directory
            backend_path = Path(__file__).resolve().parent.parent / filepath
            if backend_path.is_file():
                path = backend_path
            else:
                raise DatabaseError(f"Database file '{filepath}' does not exist.")

        try:
            with open(path, encoding="utf-8") as f:
                raw_data = json.load(f)
        except json.JSONDecodeError as err:
            raise DatabaseError(f"Malformed JSON in database file '{filepath}': {err}") from err
        except OSError as err:
            raise DatabaseError(f"Failed to read database file '{filepath}': {err}") from err

        if not isinstance(raw_data, dict) or len(raw_data) == 0:
            raise DatabaseError(f"Database file '{filepath}' is empty or invalid.")

        parsed_cache: dict[str, HandStats] = {}
        try:
            for cid, stats_dict in raw_data.items():
                parsed_cache[cid] = HandStats.from_dict(stats_dict)
        except (KeyError, ValueError, TypeError) as err:
            raise DatabaseError(f"Invalid record schema in '{filepath}': {err}") from err

        _validate_records(parsed_cache, str(path))
        self._cache = parsed_cache
        self._is_loaded = True

    def get(self, canonical_id: str) -> HandStats:
        """Query statistics for a canonical hand ID in O(1) time.

        Args:
            canonical_id: Normalized key, e.g. 'A-A-A', 'Q-K-A', '9-8-7'.

        Returns:
            The associated HandStats object.

        Raises:
            DatabaseNotLoadedError: If queried before loading.
            UnknownHandError: If canonical_id is not present (also a KeyError).
        """
        if not self._is_loaded:
            raise DatabaseNotLoadedError("WinRateDB is not loaded. Call load() first.")

        if canonical_id not in self._cache:
            raise UnknownHandError(f"Canonical hand '{canonical_id}' not found in database.")

        return self._cache[canonical_id]

    def get_by_cards(self, cards: Sequence[Card]) -> HandStats:
        """Query statistics for any concrete 3-card hand in O(1) time.

        Args:
            cards: Sequence of 3 Card instances.

        Returns:
            HandStats for the matching canonical equivalence class.

        Raises:
            InvalidHandSizeError: If len(cards) != 3.
            DatabaseNotLoadedError: If queried before loading.
        """
        cid = get_canonical_id(cards)
        return self.get(cid)

    def all_items(self) -> dict[str, HandStats]:
        """Return all canonical hand stats as a dictionary copy."""
        if not self._is_loaded:
            raise DatabaseNotLoadedError("WinRateDB is not loaded. Call load() first.")
        return dict(self._cache)

    def __len__(self) -> int:
        return len(self._cache)

    def __contains__(self, canonical_id: str) -> bool:
        return canonical_id in self._cache


def _validate_records(records: dict[str, HandStats], source: str) -> None:
    """Check that parsed records describe exactly the 455 canonical hands with plausible rates.

    Raises:
        DatabaseError: Naming the first problem found.
    """
    expected = {hand.canonical_id: hand for hand in generate_all_canonical_hands()}
    missing = sorted(expected.keys() - records.keys())
    unknown = sorted(records.keys() - expected.keys())
    if missing or unknown:
        raise DatabaseError(
            f"'{source}' must contain exactly the {len(expected)} canonical hands: "
            f"{len(missing)} missing (e.g. {missing[:3]}), {len(unknown)} unknown (e.g. {unknown[:3]})."
        )

    for cid, stats in records.items():
        canonical = expected[cid]
        if stats.category is not canonical.category or stats.multiplicity != canonical.multiplicity:
            raise DatabaseError(
                f"'{source}': {cid} is recorded as {stats.category.name} x{stats.multiplicity}, "
                f"expected {canonical.category.name} x{canonical.multiplicity}."
            )
        rates = (stats.equity, stats.win_rate, stats.tie_rate, stats.loss_rate)
        if not all(0.0 <= rate <= 1.0 for rate in rates):
            raise DatabaseError(f"'{source}': {cid} has a rate outside [0, 1]: {rates}.")
        if abs(stats.win_rate + stats.tie_rate + stats.loss_rate - 1.0) > _RATE_TOLERANCE:
            raise DatabaseError(f"'{source}': {cid} win + tie + loss rates do not sum to 1.")
        if abs(stats.equity - (stats.win_rate + 0.5 * stats.tie_rate)) > _RATE_TOLERANCE:
            raise DatabaseError(f"'{source}': {cid} equity does not equal win rate + half the tie rate.")
        if stats.samples < 1:
            raise DatabaseError(f"'{source}': {cid} has {stats.samples} samples.")
