# 08 — The Database Layer

> **Goal:** load `winrates.json` once into memory and answer "what is the equity of this hand?" in
> well under a microsecond.
> **You will build:** `backend/src/db.py` and `backend/tests/test_db.py` (6 tests).
> **Time:** ~1 hour.
> **Prerequisites:** [07](07-generator-simulation.md) (you need `data/winrates.json`).

---

## The big picture

This is where the **online** half of the architecture begins. The program starts, loads the 455 records
from disk **once**, and from then on every question is a dictionary lookup.

```
 data/winrates.json ──(json.load, once at start-up)──► WinRateDB._cache : dict[str, HandStats]
                                                              │
     "As Kh Qd" ──► Hand ──► get_canonical_id ──► "Q-K-A" ──► _cache["Q-K-A"] ──► HandStats(equity=0.9969, …)
```

We call it a "database" even though it's a Python dictionary. For 455 small records, a `dict` beats any
real database server: there is no network, no SQL, and nothing to install.

---

## Concepts you need

### Hash tables and O(1) lookup

Python's `dict` is a **hash table**. When you store `d["Q-K-A"] = stats`:

1. Python computes `hash("Q-K-A")`, a big integer derived from the string's characters.
2. It uses that number to pick a **slot** in an internal array, and stores the key and value there.

To look up `d["Q-K-A"]`, Python computes the same hash, jumps straight to the same slot, and checks the
key. It doesn't matter if the dict has 10 or 10 million entries: the work is about the same. We call that
**O(1)**, "constant time". Compare with searching a list, which checks items one by one: **O(n)**.

```python
>>> stats_list = [("2-2-2", 0.9974), ("3-2-2", 0.6661), ...]   # find "Q-K-A": scan up to 455 items
>>> stats_dict = {"2-2-2": 0.9974, "3-2-2": 0.6661, ...}        # find "Q-K-A": one hash, one jump
```

That's why chapter 4 cared so much about **immutability**: a key's hash must never change, or the dict
would look in the wrong slot.

### Dependency injection (DI)

There are two ways for code to get the database it needs:

```python
# ❌ Global variable: every module reaches for the same hidden object
DB = load("data/winrates.json")          # runs on import!
def solve():
    return DB.get("Q-K-A")

# ✅ Dependency injection: the object is *passed in*
class RangeFinder:
    def __init__(self, db: WinRateDB) -> None:
        self._db = db
```

With DI, a test can pass in a small fake database, two databases can coexist, and nothing happens
just because a file was imported. `AGENTS.md` requires DI ("state must be injected via constructors").
`WinRateDB` is designed to be injected: it holds its state **inside the object**.

### Convert data at the boundary

JSON gives us plain dicts of strings and floats. As soon as data enters our program we convert it into
our own **typed** objects (`HandStats`, with a real `HandCategory` enum). The rest of the code then never
has to wonder "is `category` a string here or an enum?" Validate and convert **once, at the edge**.

---

## Step 8.1 — Docstring and imports

📄 **File:** `backend/src/db.py` — *create this file*

```python
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
```

(`InvalidHandSizeError` is imported only because it's mentioned in a docstring; it's never used in code.)

---

## Step 8.2 — `HandStats`: one typed record

📄 **File:** `backend/src/db.py` — *add to the end*

```python


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
```

**How it works**

- The fields are exactly the keys of one JSON record from chapter 7.
- `from_dict` is the "convert at the boundary" step:
  - `float(...)` / `int(...)` make sure the types are right (JSON writes `1.0` as `1.0`, but a
    hand-edited file might contain `1`).
  - `HandCategory["LIENG"]` looks up an enum member **by name**, turning the string back into
    `HandCategory.LIENG`.
- If a key is missing, `data["equity"]` raises `KeyError`. If a value is garbage, `float("abc")`
  raises `ValueError`. `load()` (next steps) catches both and re-raises a clear `DatabaseError`.

---

## Step 8.3 — `WinRateDB`: construction

📄 **File:** `backend/src/db.py` — *add to the end*

```python


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
```

**How it works**

- Two ways to use it: `WinRateDB("data/winrates.json")` loads immediately; `WinRateDB()` creates an
  empty one you `load()` later.
- `_cache` and `_is_loaded` start with an underscore: **private** by convention. Outside code reads
  `is_loaded` through a read-only **property**, so it can't accidentally set it to `True`.
- `str | Path | None`: we accept either a plain string or a `Path` object.

---

## Step 8.4 — `load`, part 1: find and read the file

📄 **File:** `backend/src/db.py` — *add to the end*

```python

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
```

**How it works**

- **Relative paths** like `"data/winrates.json"` are relative to the **current working directory** (the
  folder your terminal is in). If you start Python from the project root instead of `backend/`, that
  path doesn't exist. So the code tries a second location: relative to the `backend/` folder, computed
  from this file's own location (`Path(__file__)` is `.../backend/src/db.py`; `.parent.parent` is
  `.../backend`).
- **Translate low-level errors into our errors.** Three things can go wrong, and each becomes a
  `DatabaseError` with a clear message:
  - the file isn't there,
  - the file isn't valid JSON (`json.JSONDecodeError`),
  - the operating system can't read it (`OSError`: no permission, it's a folder, …).
- `raise ... from err` keeps the original error attached (Python prints "The above exception was the
  direct cause of…"), so no debugging information is lost. **Never silently swallow exceptions.**
- Finally a sanity check: the top level must be a non-empty JSON object (a Python `dict`).

> ⚠️ **Pitfall: a "helpful" hidden fallback.** If `data/winrates.json` isn't found where you asked,
> `load` silently uses `backend/data/winrates.json` instead. Try it: run Python from `/tmp` and
> `WinRateDB("data/winrates.json")` still loads 455 hands, from a file you never pointed to. This hides
> mistakes (you think you're loading a test file but you get the real one). **Better:** let the
> **caller** build an absolute path (as `app.py` does in chapter 12 with
> `Path(__file__).resolve().parent / "data" / "winrates.json"`) and make `load` fail if that exact
> file is missing. Explicit beats implicit.

---

## Step 8.5 — `load`, part 2: convert every record, then commit

📄 **File:** `backend/src/db.py` — *add to the end*

```python

        parsed_cache: dict[str, HandStats] = {}
        try:
            for cid, stats_dict in raw_data.items():
                parsed_cache[cid] = HandStats.from_dict(stats_dict)
        except (KeyError, ValueError, TypeError) as err:
            raise DatabaseError(f"Invalid record schema in '{filepath}': {err}") from err

        self._cache = parsed_cache
        self._is_loaded = True
```

**How it works**

- Convert every record into a `HandStats`. Any broken record (missing key → `KeyError`, bad number or
  unknown category name → `ValueError`/`KeyError`, wrong shape → `TypeError`) stops the load with a
  `DatabaseError`.
- **All or nothing:** records are collected in a *local* dict, `parsed_cache`. Only when **all 455**
  converted successfully do we replace `self._cache` and set `_is_loaded`. If record #300 is broken,
  the object keeps its old, consistent state instead of being half-loaded. This "build, then swap" trick
  is worth remembering.

---

## Step 8.6 — Queries: `get` and `get_by_cards`

📄 **File:** `backend/src/db.py` — *add to the end*

```python

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
```

**How it works**

- `get` guards against two mistakes, each with its own error: asking before loading
  (`DatabaseNotLoadedError`) and asking for a key that doesn't exist (`KeyError` with a clear message).
- `get_by_cards` is the method the rest of the app actually uses: real cards → canonical ID (chapter 6)
  → lookup. **That one line is where hand isomorphism pays off**: any of the 22,100 real hands finds its
  answer among only 455 records.

> 💡 **Design question.** Unknown IDs raise a built-in `KeyError`, not a `LiengError`. The web API
> (chapter 12) only catches `LiengError` to return "400 Bad Request". In practice `get_by_cards` always
> produces a valid key, so this can't happen through the API. But `get("J-Q-K")` (a spelling a human
> might type) raises a `KeyError`. A `HandNotFoundError(LiengError, KeyError)` would fit the project's
> own error hierarchy better while staying compatible.

---

## Step 8.7 — Whole-table access and Python protocols

📄 **File:** `backend/src/db.py` — *add to the end*

```python

    def all_items(self) -> dict[str, HandStats]:
        """Return all canonical hand stats as a dictionary copy."""
        if not self._is_loaded:
            raise DatabaseNotLoadedError("WinRateDB is not loaded. Call load() first.")
        return dict(self._cache)

    def __len__(self) -> int:
        return len(self._cache)

    def __contains__(self, canonical_id: str) -> bool:
        return canonical_id in self._cache
```

**How it works**

- `all_items` returns a **copy** (`dict(self._cache)`), so a caller who modifies the result can't damage
  the database. Copying 455 references takes microseconds. The range finder (chapter 10) loops over it.
- `__len__` makes `len(db)` work; `__contains__` makes `"Q-K-A" in db` work. Implementing these
  "protocol" methods makes your class feel like a built-in container.

🧪 **Mini-check**

```bash
python -c "
from src.db import WinRateDB
from src.evaluator import Hand
db = WinRateDB('data/winrates.json')
print(len(db), db.is_loaded, 'Q-K-A' in db, 'J-Q-K' in db)
print(db.get('Q-K-A'))
print(db.get_by_cards(Hand.from_str('Js Qh Kd').cards).equity)
"
```

Expected output:

```
455 True True False
HandStats(equity=0.9969, win_rate=0.9962, tie_rate=0.0015, loss_rate=0.0023, category=<HandCategory.LIENG: 3>, multiplicity=64, samples=18424)
0.995
```

Notice `'J-Q-K' in db` is `False` (the key is `K-Q-J`), but `get_by_cards` finds J♠ Q♥ K♦ anyway,
because it computes the canonical ID itself.

---

## Step 8.8 — The tests

📄 **File:** `backend/tests/test_db.py` — *create this file*

```python
"""Unit tests for the In-Memory Database Layer (WinRateDB).

Verifies:
- Complete loading of all 455 canonical records from data/winrates.json
- High-speed O(1) hash table lookup latency (< 5 microseconds)
- Error handling on nonexistent files, malformed data, and queries before load
- Accurate mapping from concrete Card sequences via get_by_cards()
"""

import time
import pytest

from src.db import HandStats, WinRateDB
from src.evaluator import Card, HandCategory
from src.exceptions import DatabaseError, DatabaseNotLoadedError


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
        assert qka_stats.equity == 0.9969
        assert qka_stats.category == HandCategory.LIENG
        assert qka_stats.multiplicity == 64
```

A fixture can also live **inside a test class** (here without `scope=`, so it runs again for every test
that uses it. Loading the file takes a few milliseconds, so that's fine).

📄 **File:** `backend/tests/test_db.py` — *add to the end*

```python

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
        assert avg_latency_us < 5.0, f"Lookup latency too high: {avg_latency_us:.3f} us"

    def test_get_by_cards(self, loaded_db: WinRateDB) -> None:
        """Ensure concrete Card sequences correctly resolve to canonical stats."""
        cards = [Card.from_str("Qs"), Card.from_str("Kh"), Card.from_str("Ad")]
        stats = loaded_db.get_by_cards(cards)

        assert stats.category == HandCategory.LIENG
        assert stats.equity == 0.9969
```

**Performance tests.** `time.perf_counter()` is a high-resolution clock for measuring short durations.
We time **50,000** lookups and divide, because a single lookup (~0.1 µs) is too short to measure
reliably. The `AGENTS.md` budget is 5 µs; a typical laptop does about **0.13 µs**, roughly 40× faster
than required.

> 💡 Timing tests can be **flaky**: on a very busy or slow CI machine they might fail for reasons
> unrelated to your code. A generous budget (like 5 µs for a 0.13 µs operation) keeps them reliable.

📄 **File:** `backend/tests/test_db.py` — *add to the end*

```python

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
```

These are **negative tests**: they check that bad situations fail *in the right way*. Testing only the
happy path leaves half the behaviour unchecked.

> 💡 **Missing test:** the "malformed JSON" and "invalid record schema" branches of `load` have no test.
> pytest's built-in `tmp_path` fixture gives each test a fresh temporary folder, ideal for this:
>
> ```python
> def test_malformed_json_raises(tmp_path) -> None:
>     bad = tmp_path / "bad.json"
>     bad.write_text("{not json", encoding="utf-8")
>     with pytest.raises(DatabaseError):
>         WinRateDB(bad)
> ```

---

## ✅ Checkpoint

```bash
python -m pytest -q
```

Expected output:

```
..................................                                       [100%]
34 passed in 3.60s
```

Commit:

```bash
git add . && git commit -m "feat: in-memory WinRateDB with O(1) lookup"
```

## Recap

- `WinRateDB` loads `winrates.json` once into a `dict[str, HandStats]`. Lookups are **O(1)** (≈ 0.13 µs).
- `HandStats.from_dict` converts raw JSON into typed objects **at the boundary**.
- `load` turns every low-level failure into a `DatabaseError` (with `from err`), and commits only if
  **all** records parse ("build, then swap").
- The object holds its own state, so it can be **injected** into other classes instead of living in a global.
- Pitfalls: the silent path fallback; `get` raises a plain `KeyError` outside the `LiengError` family.

**Next:** [09 — Expected Value](10-expected-value.md)
