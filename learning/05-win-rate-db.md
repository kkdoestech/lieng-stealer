# Lesson 05 — The win-rate database

> **Goal:** understand how `db.py` turns `winrates.json` into typed records you can look up in
> constant time, and how it fails loudly and safely when the file is missing, broken or simply
> wrong.
> **Files:** [`backend/src/db.py`](../backend/src/db.py), [`backend/src/paths.py`](../backend/src/paths.py),
> [`backend/tests/test_db.py`](../backend/tests/test_db.py), and the two places that create it:
> [`app.py`](../backend/app.py#L135-L136) and [`cli.py`](../backend/src/cli.py#L258)
> ([`range_finder.py`](../backend/src/range_finder.py#L46-L47) only checks that it is loaded).
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
| 2 | [db.py:24-46](../backend/src/db.py#L24-L46) | `HandStats` and `from_dict`: JSON in, typed record out. |
| 3 | [db.py:56-66](../backend/src/db.py#L56-L66) | The constructor: state lives inside the object. |
| 4 | [db.py:68-111](../backend/src/db.py#L68-L111) | `load`: find the file, read it, parse every record, validate, then swap in. |
| 5 | [db.py:163-193](../backend/src/db.py#L163-L193) | `_validate_records`: exactly the 455 hands, the right category and multiplicity, plausible rates. |
| 6 | [db.py:113-148](../backend/src/db.py#L113-L148) | `get` and `get_by_cards`. |
| 7 | [db.py:150-160](../backend/src/db.py#L150-L160) | `all_items`, `len()` and `in`. |
| 8 | [paths.py](../backend/src/paths.py), [app.py:135-136](../backend/app.py#L135-L136) | The default path, and who creates the instance in the web app. |
| 9 | [test_db.py](../backend/tests/test_db.py) | 13 tests, including a latency budget and seven for validation. |

---

## Walkthrough

### 1. `HandStats`: one typed record

📍 [`backend/src/db.py:24-46`](../backend/src/db.py#L24-L46)
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
```

(The return annotation is a plain `HandStats`, not the string `"HandStats"`, because the module
starts with `from __future__ import annotations`: annotations are no longer evaluated when the
class is defined, so a class can name itself.)

The seven fields mirror the seven JSON fields of lesson 04, one to one. Two things happen on the
way in:

- **Numbers get their real types.** JSON writes `1.0` for A-A-A's equity, but a hand-edited file
  might have `1`. `float(...)` and `int(...)` make the types predictable for the rest of the code.
- **The category becomes an enum.** `HandCategory["LIENG"]` looks a member up **by name** and
  returns `HandCategory.LIENG`. The generator wrote `canonical_hand.category.name`
  ([generator.py:103](../backend/src/generator.py#L103)), so this is the exact reverse.

This is "convert at the boundary": the JSON is untyped text, and from here on nobody has to ask
"is `category` a string or an enum here?". `from_dict` is a `@classmethod`, which is the usual
Python way to write a second constructor.

### 2. The constructor: state inside the object

📍 [`backend/src/db.py:56-66`](../backend/src/db.py#L56-L66)
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

📍 [`backend/src/db.py:82-89`](../backend/src/db.py#L82-L89)
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

That fallback is why the tests can say `"data/winrates.json"` and still work when you start them
from the repository root. I checked: from the repo root, `WinRateDB("data/winrates.json")` loads
all 455 records and Q-K-A is 0.9969.

The order matters, though. The current directory wins. In a directory that has its own
`data/winrates.json` (I made one with a 20-sample Monte Carlo run, lesson 04), the same line
silently loads **that** file: 455 records, Q-K-A equity 1.0, `samples` 20. It even passes the new
validation (section 5), because a Monte Carlo file is well-formed. See weak spot 4.

Since October 2026 you rarely pass a relative path at all. `load()` without an argument, the CLI's
`--db` and the web app all default to `DEFAULT_DB_PATH`:

📍 [`backend/src/paths.py:8-9`](../backend/src/paths.py#L8-L9)
```python
BACKEND_DIR: Final[Path] = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH: Final[Path] = BACKEND_DIR / "data" / "winrates.json"
```

The same `.resolve().parent.parent` trick, done once: an absolute path, so neither try depends on
where you are. From the shadowing directory above, `WinRateDB().load()` loads the real file
(Q-K-A 0.9969, `samples` 18424).

### 4. `load`, part 2: read, parse, validate, then swap in

📍 [`backend/src/db.py:91-111`](../backend/src/db.py#L91-L111)
```python
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
| one record `"hello"` with equity 7.5, multiplicity 999 | `DatabaseError: … must contain exactly the 455 canonical hands: 455 missing (e.g. ['10-10-10', '10-10-2', '10-10-3']), 1 unknown (e.g. ['hello']).` | none |

The first four checks are about *shape*. The last row is new: until October 2026 that file
**loaded fine**, one record, because nothing checked *meaning* (weak spot 1). The next section
shows the check that rejects it.

**All or nothing.** Records go into a local `parsed_cache` first. Only after the last one parses
*and* the whole table passes validation do lines 110-111 replace `self._cache` and set
`_is_loaded`. So a failed `load` never leaves a half-filled database. And if you reload a working
database from a broken file, the old data survives: I loaded the real file, then tried the cut-off
file. `load` raised `DatabaseError`, and afterwards `is_loaded` was still `True`, `len` 455, Q-K-A
0.9969.

### 5. `_validate_records`: does the file mean the right thing?

📍 [`backend/src/db.py:169-176`](../backend/src/db.py#L169-L176)
```python
    expected = {hand.canonical_id: hand for hand in generate_all_canonical_hands()}
    missing = sorted(expected.keys() - records.keys())
    unknown = sorted(records.keys() - expected.keys())
    if missing or unknown:
        raise DatabaseError(
            f"'{source}' must contain exactly the {len(expected)} canonical hands: "
            f"{len(missing)} missing (e.g. {missing[:3]}), {len(unknown)} unknown (e.g. {unknown[:3]})."
        )
```

The reference is not a list typed into `db.py`: it is `generate_all_canonical_hands()` from lesson
03, so the database must match the code that defines the classes. Set difference on the dict keys
(`expected.keys() - records.keys()`) gives the missing and unknown ids in one step each. Then every
record is checked against its class ([db.py:178-193](../backend/src/db.py#L178-L193)):

- its `category` and `multiplicity` must equal the class's (`Q-K-A is recorded as DIEM x64,
  expected LIENG x64.`);
- every rate must be in [0, 1];
- `win + tie + loss` must be 1, and `equity` must be `win + tie / 2`, both within 0.0002
  ([db.py:20-21](../backend/src/db.py#L20-L21)): the generator rounds each rate on its own, so 151
  real records sum to 1.0001 (lesson 04);
- `samples` must be at least 1.

Each failure names the first bad class. Real messages, each from the real file with one field
changed:

| Change | Message |
|--------|---------|
| delete `A-A-A` | `… 1 missing (e.g. ['A-A-A']), 0 unknown (e.g. []).` |
| Q-K-A `category` → `"DIEM"` | `…: Q-K-A is recorded as DIEM x64, expected LIENG x64.` |
| Q-K-A `equity` → 0.5 | `…: Q-K-A equity does not equal win rate + half the tie rate.` |
| Q-K-A `loss_rate` → 0.5 | `…: Q-K-A win + tie + loss rates do not sum to 1.` |
| Q-K-A `samples` → 0 | `…: Q-K-A has 0 samples.` |

What it can't catch is a file that is *consistent but wrong*: a 20-sample Monte Carlo file passes
every check (weak spot 4).

### 6. Queries: `get` and `get_by_cards`

📍 [`backend/src/db.py:126-132`](../backend/src/db.py#L126-L132)
```python
        if not self._is_loaded:
            raise DatabaseNotLoadedError("WinRateDB is not loaded. Call load() first.")

        if canonical_id not in self._cache:
            raise UnknownHandError(f"Canonical hand '{canonical_id}' not found in database.")

        return self._cache[canonical_id]
```

A lookup is two checks and one dict access. A Python `dict` is a hash table, so the cost does not
grow with the number of records: **O(1)** (concept box below). On the machine this lesson was
re-run on, one `get("Q-K-A")` took about 0.10 µs. AGENTS.md §6 budgets 5 µs, and
[test_db.py:50-62](../backend/tests/test_db.py#L50-L62) enforces that with 50,000 lookups.

The key must be the exact canonical ID from lesson 03. `"K-Q-J"` is a key (the J-Q-K straight,
written descending). `"J-Q-K"` is not, so `get("J-Q-K")` raises
`UnknownHandError: Canonical hand 'J-Q-K' not found in database.` That class is both a
`LiengError` and a `KeyError` (lesson 01), so `except KeyError` code written for the old plain
`KeyError` still works. It also prints its message without the extra quotes a `KeyError` adds.

When you hold real cards, use `get_by_cards` instead:

📍 [`backend/src/db.py:147-148`](../backend/src/db.py#L147-L148)
```python
        cid = get_canonical_id(cards)
        return self.get(cid)
```

`get_canonical_id` (lesson 03) rejects duplicate cards, orders the ranks and builds the key, so any
order and any suits work. `J♠ Q♥ K♦` maps to `"K-Q-J"` and returns equity 0.995, and
`[A♠, A♠, K♦]` raises `DuplicateCardError`. This costs about 2.6 µs, much more than a plain `get`,
because building the key dominates. The duplicate check made that step dearer: on the same machine
`get_canonical_id` takes about 2.2 µs now against 0.8 µs before the fixes (0.7 µs of it is the
`len(set(cards))`). Still inside the budget.

### 7. Whole-table access and the container protocol

📍 [`backend/src/db.py:150-160`](../backend/src/db.py#L150-L160)
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

### 8. Who creates the database

📍 [`backend/app.py:148-154`](../backend/app.py#L148-L154)
```python
    if db is None:
        db = WinRateDB(DEFAULT_DB_PATH)
    if calling_model is None:
        calling_model = CallingRangeModel()
    if thresholds is None:
        thresholds = _thresholds_from_config(app.config)
    app.extensions["lieng"] = Services(db, calling_model, RangeFinder(db, calling_model), thresholds)
```

The web app builds its database inside `create_app()` (lesson 10), with the **absolute**
`DEFAULT_DB_PATH`, unless the caller passes one in: `create_app(db=my_db)` is how a test injects a
different database. A missing or invalid file raises `DatabaseError` right there, so the app fails
at start-up instead of answering requests with no data. Loading and validating the 82,694-byte
file took 5.5 ms here (most of it is building the 455 reference classes for the validation). The
CLI builds its own from `--db`, which also defaults to `DEFAULT_DB_PATH`
([cli.py:258](../backend/src/cli.py#L258)). `RangeFinder` no longer loads anything itself: given
an unloaded database it raises `DatabaseNotLoadedError`
([range_finder.py:46-47](../backend/src/range_finder.py#L46-L47)). Until October 2026 it quietly
loaded the default path behind your back, and `app.py` had an `if DB_PATH.is_file()` guard that
could never do what it seemed to (lessons 08 and 10).

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
  like, and each caller decides which file to load. The web app keeps one per app object, built by
  `create_app()` (lesson 10).
- **Parse and validate everything up front.** Converting and checking 455 records costs a few
  milliseconds once, so every later lookup is a plain dict access returning a typed record that is
  known to be sane.
- **All-or-nothing loading.** A database is either fully loaded or unchanged. A half-parsed table
  would give wrong answers silently, which is worse than an error.
- **The path fallback.** It makes `"data/winrates.json"` work from the repo root and from
  `backend/`. The alternative, always resolving relative to `backend/`, would be stricter, but
  then a relative path could not point anywhere else.
- **An unknown ID is a `KeyError` *and* a `LiengError`.** `UnknownHandError` matches what a dict
  does, so `get` behaves like `db[...]`, and it is still caught by the project's `except LiengError`.
- **Validate against the code, not against a copy of it.** The expected 455 classes come from
  `generate_all_canonical_hands()`, so the rule "the file must match the classes" can't drift from
  the classes themselves.

---

## ⚠️ Weak spots

Six weak spots were listed here when the course was written. Commit `bba5e63` ("fix(core)", October
2026) fixed three and narrowed a fourth; two are still open.

1. ✅ **Fixed: no semantic validation.** `load` checked the shape of each record, never its meaning:
   a one-record file with the made-up ID `"hello"`, equity 7.5 and multiplicity 999 loaded without
   complaint. Now `_validate_records` ([db.py:163-193](../backend/src/db.py#L163-L193)) requires
   exactly the 455 canonical ids, the right category and multiplicity for each, rates in [0, 1]
   that add up, and at least one sample, before the swap. Pinned by `TestDatabaseValidation`
   ([test_db.py:106-138](../backend/tests/test_db.py#L106-L138)): malformed JSON, a missing class, a
   rate above 1, a wrong multiplicity, and a failed reload that keeps the old data.
2. **`len()` and `in` ignore the load state.**
   [db.py:156-160](../backend/src/db.py#L156-L160): on an unloaded database `len(db)` is 0 and
   `"A-A-A" in db` is `False`, while `db.get("A-A-A")` raises `DatabaseNotLoadedError`. Code that
   checks `if cid in db:` first gets "not found" instead of "not loaded". *Fix:* raise in
   `__contains__`, or document that 0 / `False` means "not loaded" (exercise 5).
3. ✅ **Fixed: `KeyError` leaked past `LiengError`.** `get` raised a built-in `KeyError`, which
   `except LiengError` missed. Now it raises `UnknownHandError`
   ([db.py:130](../backend/src/db.py#L130)), which is both. Pinned by
   `test_unknown_id_is_a_project_error_and_a_key_error`
   ([test_db.py:146-151](../backend/tests/test_db.py#L146-L151)), and the old
   `test_key_error_on_invalid_id` ([test_db.py:89-92](../backend/tests/test_db.py#L89-L92)) still
   passes.
4. **Narrowed: the current directory beats `backend/` for a relative path.**
   [db.py:82-87](../backend/src/db.py#L82-L87) still tries the cwd first, so
   `WinRateDB("data/winrates.json")` run next to a stray `data/winrates.json` silently loads it, and
   validation can't tell a well-formed Monte Carlo file from the real one. What changed is that
   nothing in the app passes a relative path any more: the defaults of `load()`, the CLI's `--db`,
   `create_app()` and the generator's `--output` are all the absolute `DEFAULT_DB_PATH`
   ([paths.py:8-9](../backend/src/paths.py#L8-L9)), pinned by
   `test_default_path_works_from_any_directory` ([test_db.py:140-144](../backend/tests/test_db.py#L140-L144)).
   *Fix for the rest:* resolve relative paths against `backend/` only, or log which file was
   loaded.
5. ✅ **Fixed: no duplicate-card check in `get_by_cards`.** It inherited `get_canonical_id`'s
   leniency, so `[A♠, A♠, K♦]` returned A-A-K's stats (equity 0.2806). `get_canonical_id` now raises
   `DuplicateCardError` (lesson 03), and so does `get_by_cards`.
6. **Small things.** The unused `InvalidHandSizeError` import is gone. Error messages from the
   first checks print the path you passed, not the resolved one, so "does not exist" does not tell
   you where it looked ([db.py:89](../backend/src/db.py#L89)), while the validation messages print
   the resolved path ([db.py:109](../backend/src/db.py#L109)): one file, two conventions. And
   `get_by_cards` is about 2.6 µs, three times what it was, because of the duplicate check and the
   key building (section 6); fine against the 5 µs budget, but nothing times it.

---

## 🧪 Try it

Run from `backend/` with the virtual environment active (see [COURSE.md](COURSE.md#setup)).

```bash
python -m pytest tests/test_db.py -q
```

Expected output (the timing varies):

```
.............                                                            [100%]
13 passed in 0.09s
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

Output on the machine this lesson was re-run on:

```
get 0.10 us, get_by_cards 2.59 us
```

Feed the loader a file that parses but means the wrong thing (weak spot 1, now fixed):

```bash
python -c '
import json, tempfile
from src.db import WinRateDB
from src.exceptions import DatabaseError
records = json.load(open("data/winrates.json"))
records["Q-K-A"]["category"] = "DIEM"
with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
    json.dump(records, f)
try:
    WinRateDB(f.name)
except DatabaseError as err:
    print(str(err).replace(f.name, "<tmp>"))
'
```

Expected output:

```
'<tmp>': Q-K-A is recorded as DIEM x64, expected LIENG x64.
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
swap at [db.py:110-111](../backend/src/db.py#L110-L111) never runs, `len(db)` is still 455 and the
old records are untouched.
</details>

**🟢 3. Predict.** You `cd` to the repository root and run
`python -c 'import sys; sys.path.insert(0, "backend"); from src.db import WinRateDB; print(len(WinRateDB("data/winrates.json")))'`.
There is no `data/` folder at the root. What happens?

<details><summary>Solution</summary>

It prints `455`. `Path("data/winrates.json").is_file()` is false at the root, so the fallback at
[db.py:85](../backend/src/db.py#L85) tries `backend/data/winrates.json`, which exists.
</details>

**🟡 4. Which check fires?** Copy the real file, make one change, and load the copy. For each
change, predict the message before you run it: (a) Q-K-A's `multiplicity` → 24; (b) rename the key
`"K-Q-J"` to `"J-Q-K"`; (c) A-A-A's `win_rate` → 0.9 and `loss_rate` → 0.1; (d) the same as (c), and
`equity` → 0.9 too. Use the last probe in 🧪 Try it as a template.

<details><summary>Solution</summary>

```
(a) '<tmp>': Q-K-A is recorded as LIENG x24, expected LIENG x64.
(b) '<tmp>' must contain exactly the 455 canonical hands: 1 missing (e.g. ['K-Q-J']), 1 unknown (e.g. ['J-Q-K']).
(c) '<tmp>': A-A-A equity does not equal win rate + half the tie rate.
(d) loads
```

(b) is the inconsistent id format of lesson 03 meeting the validator: `J-Q-K` is a perfectly
reasonable spelling, but not the stored one. (c) is caught because the rates no longer explain the
equity. (d) is consistent and wrong: A-A-A can never lose, yet the file says it loses 10% of the
time, and nothing in `_validate_records` knows that. Validation can check that the file describes
the right hands in a self-consistent way; only regenerating and comparing (`cmp`, lesson 04)
checks that the numbers are *true*.
</details>

**🟡 5. Make `in` honest (weak spot 2).** Change `__contains__`
([db.py:159-160](../backend/src/db.py#L159-L160)) to raise `DatabaseNotLoadedError` on an unloaded
database, and add a test for it. Predict how many existing tests break. Why would you *not* do the
same to `__len__`?

<details><summary>Solution</summary>

```python
    def __contains__(self, canonical_id: str) -> bool:
        if not self._is_loaded:
            raise DatabaseNotLoadedError("WinRateDB is not loaded. Call load() first.")
        return canonical_id in self._cache
```

```python
    def test_membership_on_unloaded_db_raises(self) -> None:
        with pytest.raises(DatabaseNotLoadedError):
            _ = "A-A-A" in WinRateDB()
```

None break: `172 passed` before you add the test and `173 passed` with it, because no code asks
`in` of an unloaded database. `__len__` is different: `bool(db)` falls back to it, and `/health` reports
`classes_loaded: len(db)` (lesson 10), where 0 is a meaningful answer. A `len()` that raises would
turn "not loaded" into a 500. Undo with `git checkout -- backend/src/db.py backend/tests/test_db.py`.
</details>

**🔴 6. Inject a fake database.** Add a `WinRateDB.from_mapping(raw: dict)` classmethod that builds
a loaded database from records in memory, sharing the parsing **and validation** code with `load`
(move the end of `load` into an `_install(raw_data, source)` method). Then write a test that gives
`RangeFinder` a fake database: the real records, with 4-3-3 made unbeatable. Check with
`python -m pytest -q`, `python -m mypy` and `ruff check src tests`.

<details><summary>Solution</summary>

```python
        self._install(raw_data, str(path))   # the new end of load()

    @classmethod
    def from_mapping(cls, raw_data: dict[str, Any]) -> WinRateDB:
        """Build a loaded database from records already in memory (validated like a file)."""
        db = cls()
        db._install(raw_data, "<mapping>")
        return db

    def _install(self, raw_data: dict[str, Any], source: str) -> None:
        """Parse and validate the records, then swap them in (all or nothing)."""
        parsed_cache: dict[str, HandStats] = {}
        try:
            for cid, stats_dict in raw_data.items():
                parsed_cache[cid] = HandStats.from_dict(stats_dict)
        except (KeyError, ValueError, TypeError) as err:
            raise DatabaseError(f"Invalid record schema in '{source}': {err}") from err

        _validate_records(parsed_cache, source)
        self._cache = parsed_cache
        self._is_loaded = True
```

```python
def test_range_finder_with_an_injected_fake_db(real_records: dict) -> None:
    from src.range_finder import RangeFinder

    records = {cid: dict(stats) for cid, stats in real_records.items()}
    records["4-3-3"].update(equity=1.0, win_rate=1.0, tie_rate=0.0, loss_rate=0.0)
    ranked = RangeFinder(WinRateDB.from_mapping(records)).solve_range(100000.0, 50000.0, 0.0)
    assert [r.canonical_id for r in ranked[:2]] == ["A-A-A", "4-3-3"]
    with pytest.raises(DatabaseError, match="453 missing"):
        WinRateDB.from_mapping({cid: records[cid] for cid in ("A-A-A", "4-3-3")})
```

`173 passed`, mypy and ruff clean. The fake 4-3-3 ties A-A-A on EV (150,000) and equity (1.0), and
the range finder's last tie-break, real hand strength (lesson 08), puts A-A-A first. The last two
lines show the price of validation: a two-record fake, which the course's first version of this
exercise used, is now rejected. Validation and easy test doubles pull in opposite directions; here
the fake is built from the real file, so it passes. Undo with
`git checkout -- backend/src/db.py backend/tests/test_db.py`.
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
   record parsed and the whole table passed `_validate_records`. A failed reload keeps the previous
   data.
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
- `load` tries the path as given, then relative to `backend/`. The current directory wins for a
  relative path, but every default is now the absolute `DEFAULT_DB_PATH` from `paths.py`.
- Every failure becomes a `DatabaseError` with the original as `__cause__`. After parsing,
  `_validate_records` checks the 455 ids, categories, multiplicities and rates against
  `generate_all_canonical_hands()`. Loading is all or nothing, so a failed reload keeps the old data.
- `get` is an O(1) dict lookup (about 0.1 µs here) and raises `UnknownHandError` (a `KeyError` and
  a `LiengError`) for an unknown id. `get_by_cards` adds the canonical-ID step, duplicate check
  included.
- Fixed: validation, the escaping `KeyError`, the missing duplicate check, relative defaults. Still
  open: `len()`/`in` ignore the load state, a relative path can still be shadowed by the cwd, and
  two conventions for paths in error messages.

**Next:** [06 — The calling range](06-calling-range.md)
