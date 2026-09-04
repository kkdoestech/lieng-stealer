"""Liêng Stealer - In-Memory Database Layer & Fast O(1) Cache.

Loads the precomputed canonical equity database (data/winrates.json) into a
typed, immutable in-memory Hash Table for high-performance O(1) decision queries.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from src.evaluator import Card, HandCategory
from src.exceptions import DatabaseError, DatabaseNotLoadedError, InvalidHandSizeError
from src.hands import get_canonical_id


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
    def from_dict(cls, data: dict[str, Any]) -> "HandStats":
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

    def load(self, filepath: str | Path = "data/winrates.json") -> None:
        """Load and parse the win rates JSON into memory.

        Args:
            filepath: Path to precomputed winrates.json.

        Raises:
            DatabaseError: If file is missing, cannot be read, or is malformed.
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
            with open(path, "r", encoding="utf-8") as f:
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
            KeyError: If canonical_id is not present in database.
        """
        if not self._is_loaded:
            raise DatabaseNotLoadedError("WinRateDB is not loaded. Call load() first.")

        if canonical_id not in self._cache:
            raise KeyError(f"Canonical hand '{canonical_id}' not found in database.")

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

