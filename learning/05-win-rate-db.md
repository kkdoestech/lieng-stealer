# Lesson 05 — The win-rate database

> **Goal:** understand how `db.py` turns `winrates.json` into typed records you can look up in
> constant time, and how it fails loudly and safely when the file is missing or broken.
> **Files:** [`backend/src/db.py`](../backend/src/db.py), [`backend/tests/test_db.py`](../backend/tests/test_db.py),
> and the three places that create it: [`app.py`](../backend/app.py#L30-L36),
> [`cli.py`](../backend/src/cli.py#L232) and [`range_finder.py`](../backend/src/range_finder.py#L42-L43).
> **Time:** ~40 min. **Before this:** [04 — The generator and `winrates.json`](04-generator.md).

---

## Where this fits

```
 data/winrates.json  (lesson 04, 455 records of plain JSON)
          │  read once, at start-up
          ▼
 ┌─────────────────────────────┐
 │ db.py  WinRateDB (this one) │   dict[str, HandStats]: canonical ID → typed record
 └─────────────────────────────┘
          │  get("Q-K-A") / get_by_cards([Q♠, K♥, A♦])
          ▼
 range_finder.py (lesson 08)   app.py (lesson 10)   cli.py (lesson 09)   test_calling_range.py (lesson 06)
```

`db.py` is the smallest module in the backend and the one every request touches. Its job is
narrow: find the file, read it, convert every record into a `HandStats`, and answer lookups. It
holds the "equity against a **random** hand" side of the app. The other side, equity against the
hands that call, is computed by `calling_range.py` in lesson 06.

---

## Reading order

| # | Location | What to look for |
|---|----------|------------------|
| 1 | [db.py:1-5](../backend/src/db.py#L1-L5) | The promise: an immutable, in-memory hash table with O(1) queries. |
| 2 | [db.py:19-41](../backend/src/db.py#L19-L41) | `HandStats` and `from_dict`: JSON in, typed record out. |
| 3 | [db.py:51-61](../backend/src/db.py#L51-L61) | The constructor: state lives inside the object. |
| 4 | [db.py:63-100](../backend/src/db.py#L63-L100) | `load`: find the file, read it, parse every record, then swap in. |
| 5 | [db.py:102-137](../backend/src/db.py#L102-L137) | `get` and `get_by_cards`. |
| 6 | [db.py:139-149](../backend/src/db.py#L139-L149) | `all_items`, `len()` and `in`. |
| 7 | [app.py:30-36](../backend/app.py#L30-L36) | Who creates the instance in the web app. |
| 8 | [test_db.py](../backend/tests/test_db.py) | 6 tests, including a latency budget. |

---

## Walkthrough

### 1. `HandStats`: one typed record

📍 [`backend/src/db.py:19-41`](../backend/src/db.py#L19-L41)
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

The seven fields mirror the seven JSON fields of lesson 04, one to one. Two things happen on the
way in:

- **Numbers get their real types.** JSON writes `1.0` for A-A-A's equity, but a hand-edited file
  might have `1`. `float(...)` and `int(...)` make the types predictable for the rest of the code.
- **The category becomes an enum.** `HandCategory["LIENG"]` looks a member up **by name** and
  returns `HandCategory.LIENG`. The generator wrote `canonical_hand.category.name`
  ([generator.py:94](../backend/src/generator.py#L94)), so this is the exact reverse.

This is "convert at the boundary": the JSON is untyped text, and from here on nobody has to ask
"is `category` a string or an enum here?". `from_dict` is a `@classmethod`, which is the usual
Python way to write a second constructor.

### 2. The constructor: state inside the object

📍 [`backend/src/db.py:51-61`](../backend/src/db.py#L51-L61)
```python
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

You can build an empty database and load it later (`WinRateDB()` then `.load(...)`), or do both
at once (`WinRateDB("data/winrates.json")`). Either way, the data lives in `self._cache`, not in a
module-level variable, and whoever needs a database gets one passed in. That is the **dependency
injection** AGENTS.md §2.2 asks for.

`is_loaded` is a read-only `@property`: callers can ask `db.is_loaded` but cannot assign it. The
underscore on `_cache` and `_is_loaded` is the Python convention for "private, don't touch".

### 3. `load`, part 1: finding the file

📍 [`backend/src/db.py:72-79`](../backend/src/db.py#L72-L79)
```python
        path = Path(filepath)
        if not path.is_file():
            # Fallback check relative to backend root directory
            backend_path = Path(__file__).resolve().parent.parent / filepath
            if backend_path.is_file():
                path = backend_path
            else:
                raise DatabaseError(f"Database file '{filepath}' does not exist.")
```

Two tries:

1. **The path as given**, which for a relative path means "relative to the current directory".
2. **Relative to `backend/`.** `Path(__file__)` is `backend/src/db.py`. `.resolve()` makes it
   absolute, `.parent` is `backend/src/`, and `.parent` again is `backend/`. So
   `"data/winrates.json"` becomes `backend/data/winrates.json` wherever you run from.

That fallback is why the tests and the CLI can say `"data/winrates.json"` and still work when you
start them from the repository root. I checked: from the repo root,
`WinRateDB("data/winrates.json")` loads all 455 records and Q-K-A is 0.9969.

The order matters, though. The current directory wins. In a directory that has its own
`data/winrates.json` (I made one with a 20-sample Monte Carlo run, lesson 04), the same line
silently loads **that** file: 455 records, Q-K-A equity 1.0, `samples` 20. See weak spot 4.

### 4. `load`, part 2: read, parse, then swap in

📍 [`backend/src/db.py:81-100`](../backend/src/db.py#L81-L100)
```python
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
```

**Every failure becomes a `DatabaseError`.** Callers catch one type (or `LiengError`, its base)
instead of five. `raise … from err` keeps the original exception attached as `__cause__`, so a
traceback still shows the real reason (see the concept box). Here is what I got for five bad files:

| File content | Result | `__cause__` |
|--------------|--------|-------------|
| `{"A-A-A": ` (cut off) | `DatabaseError: Malformed JSON …` | `JSONDecodeError` |
| `[1, 2]` | `DatabaseError: … is empty or invalid.` | none |
| `{}` | `DatabaseError: … is empty or invalid.` | none |
| one record with `"category": "SAPP"` | `DatabaseError: Invalid record schema …: 'SAPP'` | `KeyError` |
| one record `"hello"` with equity 7.5, multiplicity 999 | **loads fine**, 1 record | — |

The last row is weak spot 1: the checks are about *shape*, not *meaning*.

**All or nothing.** Records go into a local `parsed_cache` first. Only after the last one parses
do lines 99-100 replace `self._cache` and set `_is_loaded`. So a failed `load` never leaves a
half-filled database. And if you reload a working database from a broken file, the old data
survives: I loaded the real file, then tried the cut-off file. `load` raised `DatabaseError`, and
afterwards `is_loaded` was still `True`, `len` 455, Q-K-A 0.9969.

### 5. Queries: `get` and `get_by_cards`

📍 [`backend/src/db.py:115-121`](../backend/src/db.py#L115-L121)
```python
        if not self._is_loaded:
            raise DatabaseNotLoadedError("WinRateDB is not loaded. Call load() first.")

        if canonical_id not in self._cache:
            raise KeyError(f"Canonical hand '{canonical_id}' not found in database.")

        return self._cache[canonical_id]
```

A lookup is two checks and one dict access. A Python `dict` is a hash table, so the cost does not
grow with the number of records: **O(1)** (concept box below). On the machine this course was
written on, one `get("Q-K-A")` took about 0.09 µs. AGENTS.md §6 budgets 5 µs, and
[test_db.py:45-57](../backend/tests/test_db.py#L45-L57) enforces that with 50,000 lookups.

The key must be the exact canonical ID from lesson 03. `"K-Q-J"` is a key (the J-Q-K straight,
written descending). `"J-Q-K"` is not, so `get("J-Q-K")` raises
`KeyError: "Canonical hand 'J-Q-K' not found in database."`. Notice the extra quotes: `KeyError`
prints its message with `repr`.

When you hold real cards, use `get_by_cards` instead:

📍 [`backend/src/db.py:136-137`](../backend/src/db.py#L136-L137)
```python
        cid = get_canonical_id(cards)
        return self.get(cid)
```

`get_canonical_id` (lesson 03) sorts the ranks and builds the key, so any order and any suits work.
`J♠ Q♥ K♦` maps to `"K-Q-J"` and returns equity 0.995. This costs about 0.92 µs, ten times a
plain `get`, because building the key dominates. Still far inside the budget.

### 6. Whole-table access and the container protocol

📍 [`backend/src/db.py:139-149`](../backend/src/db.py#L139-L149)
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

- `all_items` returns a **copy**. The range finder iterates it 455 times per request (lesson 08),
  and if a caller clears or edits the copy, the database is untouched. I checked: after
  `db.all_items().clear()`, `len(db)` is still 455. The records themselves are frozen, so they are
  safe to share.
- `__len__` makes `len(db)` work, and `__contains__` makes `"Q-K-A" in db` work. Python calls
  these "dunder" methods for you.
- A side effect of `__len__`: `bool(db)` uses it. An empty, unloaded `WinRateDB()` is falsy, a
  loaded one is truthy.

Notice that these two methods do not check `_is_loaded`, while `get` and `all_items` do
(weak spot 2).

### 7. Who creates the database

📍 [`backend/app.py:30-36`](../backend/app.py#L30-L36)
```python
# Initialize WinRateDB and the calling-range model at startup
DB_PATH = Path(__file__).resolve().parent / "data" / "winrates.json"
win_rate_db = WinRateDB()
if DB_PATH.is_file():
    win_rate_db.load(DB_PATH)
calling_model = CallingRangeModel()
range_finder = RangeFinder(win_rate_db, calling_model)
```

The web app builds one instance when `app.py` is imported, with an **absolute** path, so the
fallback never matters there. Loading the 82,694-byte file took 1.8 ms here. The CLI builds its own
with the relative default ([cli.py:232](../backend/src/cli.py#L232)), which relies on the fallback.
And `RangeFinder` loads the default path itself if it receives an unloaded database
([range_finder.py:42-43](../backend/src/range_finder.py#L42-L43)), which lesson 08 lists as a
hidden side effect. Lesson 10 explains why the `if DB_PATH.is_file()` guard cannot do what it
seems to.

---

## 💡 Concept: hash tables and O(1)

`d["Q-K-A"]` does not search the dict. Python computes `hash("Q-K-A")`, a big integer, uses it to
pick a slot in an internal array, and checks the key stored there. The work is the same for 10
keys or 10 million, so it is called **O(1)**, constant time. Searching a list of 455 pairs would be
**O(n)**: up to 455 comparisons.

Two requirements follow. A key must be **hashable**, and its hash must never change while it is in
the dict. Strings are immutable, so canonical IDs are perfect keys. That is also why lesson 01 made
`Card` a frozen dataclass.

## 💡 Concept: `raise NewError(...) from err`

Inside an `except` block, `raise DatabaseError("…") from err` raises the new error and stores the
old one in `__cause__`. The traceback then shows both, joined by "The above exception was the direct
cause of the following exception". You translate a low-level error (`JSONDecodeError`) into your
module's vocabulary (`DatabaseError`) without losing the details. Without `from err` Python still
chains them, but labels it "During handling of the above exception, another exception occurred",
which reads like a second bug.

---

## Design decisions

- **A class with explicit state, not a module global.** Tests can build as many databases as they
  like, and each caller decides which file to load. The web app still keeps one at module level
  (lesson 10), but that choice is made in `app.py`, not forced by `db.py`.
- **Parse everything up front.** Converting 455 records costs about 2 ms once, so every later
  lookup is a plain dict access returning a typed record.
- **All-or-nothing loading.** A database is either fully loaded or unchanged. A half-parsed table
  would give wrong answers silently, which is worse than an error.
- **The path fallback.** It makes `"data/winrates.json"` work from the repo root and from
  `backend/`. The alternative, always resolving relative to `backend/`, would be stricter, but
  then a relative path could not point anywhere else.
- **`KeyError` for unknown IDs.** It matches what a dict does, so `get` behaves like `db[...]`.
  The cost is that it escapes `except LiengError` (weak spot 3).

---

## ⚠️ Weak spots

1. **No semantic validation.** [db.py:89-97](../backend/src/db.py#L89-L97) checks the shape of
   each record, never its meaning. A one-record file with the made-up ID `"hello"`, equity 7.5 and
   multiplicity 999 loads without complaint. So does a 20-sample Monte Carlo file. *Fix:* after
   parsing, require 455 keys, multiplicities summing to 22,100, and rates in [0, 1] (exercise 4).
   [test_generator.py:90](../backend/tests/test_generator.py#L90) checks the committed file, but
   nothing checks a file at load time.
2. **`len()` and `in` ignore the load state.**
   [db.py:145-149](../backend/src/db.py#L145-L149): on an unloaded database `len(db)` is 0 and
   `"A-A-A" in db` is `False`, while `db.get("A-A-A")` raises `DatabaseNotLoadedError`. Code that
   checks `if cid in db:` first gets "not found" instead of "not loaded". *Fix:* raise in both, or
   document that 0 / `False` means "not loaded".
3. **`KeyError` leaks past `LiengError`.** [db.py:119](../backend/src/db.py#L119) raises a
   built-in. A caller that catches `LiengError` to handle "bad input" misses it. The API never
   reaches it, because cards always produce a valid ID, but any code that takes an ID from a user
   would. *Fix:* a `HandNotFoundError(DatabaseError, KeyError)` that is both (exercise 5).
4. **The current directory beats `backend/`.** [db.py:72-77](../backend/src/db.py#L72-L77) tries
   the cwd first. A stray `data/winrates.json` in the directory you run the CLI from silently
   replaces the real data. Combined with the generator's cwd-relative output (lesson 04, weak
   spot 4), a regeneration run from the wrong place produces a file that only *some* commands read.
   *Fix:* resolve relative paths against `backend/` only, or log which file was loaded.
5. **No duplicate-card check in `get_by_cards`.** It inherits `get_canonical_id`'s leniency
   (lesson 03): `[A♠, A♠, K♦]` returns the stats for `"A-A-K"` (equity 0.2806) instead of an
   error. Going through `Hand` first, as the API does, prevents it.
6. **Small things.** `InvalidHandSizeError` is imported only for a docstring
   ([db.py:15](../backend/src/db.py#L15)). Error messages print the path you passed, not the
   resolved one, so "does not exist" does not tell you where it looked
   ([db.py:79](../backend/src/db.py#L79)). There is no test for malformed JSON or a bad record,
   although the module docstring of `test_db.py` promises "malformed data".

---

## 🧪 Try it

Run from `backend/` with the virtual environment active (see [COURSE.md](COURSE.md#setup)).

```bash
python -m pytest tests/test_db.py -q
```

Expected output (the timing varies):

```
......                                                                   [100%]
6 passed in 0.03s
```

Look things up:

```bash
python -c '
from src.db import WinRateDB
from src.evaluator import Hand
db = WinRateDB("data/winrates.json")
print(len(db), db.is_loaded, "K-Q-J" in db, "J-Q-K" in db)
print(db.get("Q-K-A"))
print(db.get_by_cards(Hand.from_str("Js Qh Kd").cards).equity)
'
```

Expected output:

```
455 True True False
HandStats(equity=0.9969, win_rate=0.9962, tie_rate=0.0015, loss_rate=0.0023, category=<HandCategory.LIENG: 3>, multiplicity=64, samples=18424)
0.995
```

Break a reload on purpose and watch the old data survive:

```bash
python -c '
import tempfile
from src.db import WinRateDB
from src.exceptions import DatabaseError
db = WinRateDB("data/winrates.json")
with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
    f.write("{\"A-A-A\": ")
try:
    db.load(f.name)
except DatabaseError as err:
    print(type(err).__name__, "caused by", type(err.__cause__).__name__)
print(db.is_loaded, len(db), db.get("Q-K-A").equity)
'
```

Expected output:

```
DatabaseError caused by JSONDecodeError
True 455 0.9969
```

Time the lookups (your numbers will differ):

```bash
python -c '
import timeit
from src.db import WinRateDB
from src.evaluator import Hand
db = WinRateDB("data/winrates.json")
cards = Hand.from_str("Qs Kh Ad").cards
n = 1_000_000
t1 = timeit.timeit(lambda: db.get("Q-K-A"), number=n) / n * 1e6
t2 = timeit.timeit(lambda: db.get_by_cards(cards), number=n) / n * 1e6
print(f"get {t1:.2f} us, get_by_cards {t2:.2f} us")
'
```

Output on the machine this course was written on:

```
get 0.09 us, get_by_cards 0.92 us
```

---

## 🏋️ Exercises

Exercises marked 🟡 or 🔴 change code. Undo them afterwards with `git checkout -- <file>`.

**🟢 1. Predict.** For `db = WinRateDB()` (never loaded), what do `len(db)`, `bool(db)`,
`"A-A-A" in db` and `db.get("A-A-A")` give?

<details><summary>Solution</summary>

`0`, `False`, `False`, and `DatabaseNotLoadedError: WinRateDB is not loaded. Call load() first.`
The first three come from `__len__` and `__contains__`, which don't look at `_is_loaded`. Only `get`
does. Check with `python -c 'from src.db import WinRateDB; db = WinRateDB(); print(len(db), bool(db), "A-A-A" in db); db.get("A-A-A")'`.
</details>

**🟢 2. Predict.** A file has 454 good records and, at the end, one whose `"samples"` field is
missing. You call `db.load(that_file)` on a database that already holds the real data. What does
`load` raise, and what is `len(db)` afterwards?

<details><summary>Solution</summary>

`HandStats.from_dict` raises `KeyError: 'samples'` on the last record, which becomes
`DatabaseError: Invalid record schema … 'samples'` with the `KeyError` as `__cause__`. Because the
swap at [db.py:99-100](../backend/src/db.py#L99-L100) never runs, `len(db)` is still 455 and the
old records are untouched.
</details>

**🟢 3. Predict.** You `cd` to the repository root and run
`python -c 'import sys; sys.path.insert(0, "backend"); from src.db import WinRateDB; print(len(WinRateDB("data/winrates.json")))'`.
There is no `data/` folder at the root. What happens?

<details><summary>Solution</summary>

It prints `455`. `Path("data/winrates.json").is_file()` is false at the root, so the fallback at
[db.py:75](../backend/src/db.py#L75) tries `backend/data/winrates.json`, which exists.
</details>

**🟡 4. Validate the meaning, not just the shape.** At the end of `load`, before the swap, reject
a file that does not have 455 records whose multiplicities sum to 22,100, or that has an equity
outside [0, 1]. Add a test that a one-record file raises `DatabaseError`. Check with
`python -m pytest -q`.

<details><summary>Solution</summary>

```python
        if len(parsed_cache) != 455 or sum(st.multiplicity for st in parsed_cache.values()) != 22100:
            raise DatabaseError(f"Database file '{filepath}' does not cover all 455 classes / 22,100 hands.")
        if any(not 0.0 <= st.equity <= 1.0 for st in parsed_cache.values()):
            raise DatabaseError(f"Database file '{filepath}' has an equity outside [0, 1].")
```

```python
    def test_incomplete_file_is_rejected(self, tmp_path) -> None:
        bad = tmp_path / "one.json"
        bad.write_text('{"A-A-A": {"equity": 1, "win_rate": 1, "tie_rate": 0, "loss_rate": 0, '
                       '"category": "SAP", "multiplicity": 4, "samples": 18424}}')
        with pytest.raises(DatabaseError):
            WinRateDB(bad)
```

With this and exercise 5 together, the whole suite gave 95 passed. The real file passes the new
checks, so nothing else changes.
</details>

**🟡 5. An error that is both.** Add `class HandNotFoundError(DatabaseError, KeyError)` to
[exceptions.py](../backend/src/exceptions.py) and raise it at
[db.py:119](../backend/src/db.py#L119). Will
[test_key_error_on_invalid_id](../backend/tests/test_db.py#L84-L87) still pass? Add a test that
`pytest.raises(LiengError)` catches `get("J-Q-K")`. Check with `python -m pytest tests/test_db.py -q`.

<details><summary>Solution</summary>

Yes. With two base classes, the new error *is a* `KeyError` and *is a* `LiengError`, so both
`pytest.raises(KeyError)` and `pytest.raises(LiengError)` catch it. Old callers keep working and
new callers can catch the project's hierarchy. Remember to replace the unused
`InvalidHandSizeError` import with `HandNotFoundError`.
</details>

**🔴 6. Inject a fake database.** Add a `WinRateDB.from_mapping(raw: dict)` classmethod that builds
a loaded database from records in memory, sharing the parsing code with `load` (move the loop into
a `_parse` static method). Then write a test that gives `RangeFinder` a two-record fake database.
Check with `python -m pytest -q`.

<details><summary>Solution</summary>

```python
    @staticmethod
    def _parse(raw_data: dict[str, Any], source: str) -> dict[str, HandStats]:
        parsed_cache: dict[str, HandStats] = {}
        try:
            for cid, stats_dict in raw_data.items():
                parsed_cache[cid] = HandStats.from_dict(stats_dict)
        except (KeyError, ValueError, TypeError) as err:
            raise DatabaseError(f"Invalid record schema in '{source}': {err}") from err
        return parsed_cache

    @classmethod
    def from_mapping(cls, raw_data: dict[str, Any]) -> "WinRateDB":
        db = cls()
        db._cache = cls._parse(raw_data, "<mapping>")
        db._is_loaded = True
        return db
```

`load` then ends with `self._cache = self._parse(raw_data, str(filepath))` and
`self._is_loaded = True`.

```python
def test_range_finder_with_an_injected_fake_db() -> None:
    rec = {"win_rate": 0, "tie_rate": 0, "loss_rate": 0, "category": "DIEM", "multiplicity": 64, "samples": 1}
    db = WinRateDB.from_mapping({"A-A-A": {**rec, "equity": 0.9}, "4-3-3": {**rec, "equity": 0.1}})
    records = RangeFinder(db).solve_range(100000.0, 50000.0, 0.0)
    assert [r.canonical_id for r in records] == ["A-A-A", "4-3-3"]
    assert [r.is_raise_profitable for r in records] == [True, False]
```

94 passed. One surprise: with made-up IDs like `"STRONG"` the test fails with `KeyError` at
[range_finder.py:100](../backend/src/range_finder.py#L100), because the range finder's tie-break
table only knows the 455 real IDs. Dependency injection only goes as far as the code lets it
(lesson 08).
</details>

---

## ❓ Quiz

1. Why does `HandStats.from_dict` call `HandCategory[...]` instead of storing the string?
2. A reload from a broken file raises `DatabaseError`. Is the database now empty?
3. Why is `get` O(1), and what would make it O(n)?
4. `"J-Q-K" in db` is `False` but `get_by_cards` of `J♠ Q♥ K♦` works. Why?
5. What does `raise DatabaseError(...) from err` add compared with a plain `raise DatabaseError(...)`?

<details><summary>Answers</summary>

1. To convert at the boundary: the rest of the code works with a real enum (comparisons,
   `display_name`) and never has to handle strings. A bad name fails at load time, not later.
2. No. Records are parsed into a local dict first, and `self._cache` is replaced only after every
   record parsed. A failed reload keeps the previous data.
3. A dict is a hash table: Python hashes the key and jumps to its slot, whatever the size. Storing
   the records in a list and scanning it would be O(n).
4. Canonical IDs are written descending, so J-Q-K's key is `"K-Q-J"`. `get_by_cards` builds the
   key with `get_canonical_id`, so it always produces the right form.
5. It stores the original exception as `__cause__`. The traceback shows the root cause as the
   *direct cause*, instead of making it look like a second error during handling.
</details>

---

## Recap

- `WinRateDB` reads `winrates.json` once and keeps `dict[str, HandStats]`: one frozen, typed
  record per canonical ID.
- `load` tries the path as given, then relative to `backend/`. The current directory wins, which can
  load the wrong file.
- Every failure becomes a `DatabaseError` with the original as `__cause__`. Parsing is all or
  nothing, so a failed reload keeps the old data.
- `get` is an O(1) dict lookup (about 0.09 µs here). `get_by_cards` adds the canonical-ID step.
- Weak spots: no semantic validation, `len()`/`in` ignore the load state, `KeyError` escapes
  `LiengError`, cwd shadowing, no duplicate check.

**Next:** [06 — The calling range](06-calling-range.md)
