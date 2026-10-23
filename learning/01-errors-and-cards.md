# Lesson 01 — Errors and cards

> **Goal:** understand the project's exception family and the four small types everything else is
> built on (`Suit`, `Rank`, `Card`, `Deck`), including exactly how the text `"10h"` becomes a card
> and what happens when the text is wrong.
> **Files:** [`backend/src/exceptions.py`](../backend/src/exceptions.py),
> [`backend/src/evaluator.py:18-171`](../backend/src/evaluator.py#L18-L171),
> [`backend/tests/test_evaluator.py:28-83`](../backend/tests/test_evaluator.py#L28-L83).
> **Time:** ~45 min. **Before this:** [00 — Orientation](00-orientation.md).

---

## Where this fits

```
  "As Kh Qd"  (text from the CLI, the API or a test)
       │  Hand.from_str splits it into tokens (lesson 02)
       ▼
  ┌─────────────────────────────────────────────┐
  │  Card.from_str ─► Rank.from_str, Suit.from_str│  this lesson
  │  Card(rank, suit)      Deck.standard_52()     │
  └─────────────────────────────────────────────┘
       │                         │
       ▼                         ▼
  evaluate_hand (lesson 02)   generator.py (lesson 04): the 49 cards left
       │
  every bad input on the way raises a LiengError ──► app.py: 400 JSON / cli.py: exit 2
```

Every other module stands on these types. They are small, but three decisions made here travel
all the way up: a card is an **immutable, hashable value**, ranks are **integers** you can compare,
and bad input **raises** an exception from one family instead of returning `None`.

---

## Reading order

| # | Location | What to look for |
|---|----------|------------------|
| 1 | [exceptions.py:4-31](../backend/src/exceptions.py#L4-L31) | Six classes, one root. Note which one has a parent other than `LiengError`. |
| 2 | [evaluator.py:18-48](../backend/src/evaluator.py#L18-L48) | `Suit`: an `Enum` with a symbol and a parser. |
| 3 | [evaluator.py:51-107](../backend/src/evaluator.py#L51-L107) | `Rank`: an `IntEnum`, its point value, face cards, parser. |
| 4 | [evaluator.py:110-158](../backend/src/evaluator.py#L110-L158) | `Card`: a frozen dataclass and `from_str`, with the `"10"` special case. |
| 5 | [evaluator.py:161-171](../backend/src/evaluator.py#L161-L171) | `Deck.standard_52`: all 52 cards as a tuple. |
| 6 | [test_evaluator.py:28-83](../backend/tests/test_evaluator.py#L28-L83) | The six tests that pin parsing and validation. |

---

## Walkthrough

### 1. The exception family

📍 [`backend/src/exceptions.py:4-31`](../backend/src/exceptions.py#L4-L31)
```python
class LiengError(Exception):
    """Base exception class for all Liêng engine errors."""
    pass


class InvalidCardError(LiengError):
    """Raised when card string or parameters are invalid."""
    pass


class InvalidHandSizeError(LiengError):
    """Raised when hand does not contain exactly 3 unique cards."""
    pass


class InvalidGameParamsError(LiengError):
    """Raised when pot, bet size, fold equity, or opponent model are invalid."""
    pass


class DatabaseError(LiengError):
    """Base error for precomputed database operations."""
    pass


class DatabaseNotLoadedError(DatabaseError):
    """Raised when querying a database that has not been loaded."""
    pass
```

The whole file is a tree with one root:

```
LiengError
├── InvalidCardError         bad rank or suit text           evaluator.py:48, :107, :141
├── InvalidHandSizeError     not 3 cards, OR a duplicate     evaluator.py:311-409, hands.py:88-154
├── InvalidGameParamsError   bad pot / bet / fold / model     app.py only (:59, :62, :64, :70, :325, :330)
└── DatabaseError            winrates.json missing or broken db.py:79-97
    └── DatabaseNotLoadedError  query before load()           db.py:116, :142
```

The point of a family is the `except` at the edges. The CLI catches the root once
([cli.py:321](../backend/src/cli.py#L321)) and turns any of them into `Invalid input: …` with exit
code 2. The API turns a bad hand into a 400 response in the same way
([app.py:176](../backend/app.py#L176)) and has one error handler for `InvalidGameParamsError`
([app.py:75](../backend/app.py#L75)). Any *other* exception, such as a `TypeError` from a real bug,
still crashes loudly, which is what you want.

Each class has a docstring *and* `pass`. The `pass` is redundant (a docstring is already a valid
class body), but harmless.

### 2. `Suit`: four constants and a forgiving parser

`Suit` is a plain `Enum` whose values are the one-letter codes `"s"`, `"c"`, `"d"`, `"h"`
([evaluator.py:18-23](../backend/src/evaluator.py#L18-L23)). Its parser accepts the letter in any
case or the Unicode symbol:

📍 [`backend/src/evaluator.py:36-48`](../backend/src/evaluator.py#L36-L48)
```python
    @classmethod
    def from_str(cls, suit_str: str) -> "Suit":
        """Parse suit from single-character representation or unicode symbol."""
        cleaned = suit_str.strip().lower()
        mapping = {
            "s": cls.SPADES, "♠": cls.SPADES,
            "c": cls.CLUBS, "♣": cls.CLUBS,
            "d": cls.DIAMONDS, "♦": cls.DIAMONDS,
            "h": cls.HEARTS, "♥": cls.HEARTS,
        }
        if cleaned in mapping:
            return mapping[cleaned]
        raise InvalidCardError(f"Invalid suit '{suit_str}'. Must be one of s, c, d, h or ♠, ♣, ♦, ♥.")
```

Two things to notice. Suits have **no order**: `Suit` is an `Enum`, not an `IntEnum`, so
`Suit.SPADES < Suit.HEARTS` is a `TypeError`. That matches the rule "suits never decide a
showdown". And the `symbol` property ([evaluator.py:26](../backend/src/evaluator.py#L26)) is never
called anywhere in the backend: every card prints with its letter (`str(card)` is `"Ah"`, not
`"A♥"`).

### 3. `Rank`: integers with names

`Rank` is an `IntEnum` from `TWO = 2` to `ACE = 14`
([evaluator.py:51-65](../backend/src/evaluator.py#L51-L65)). Because each member *is* an `int`,
`Rank.ACE > Rank.KING` is `True`, and later code can sort ranks and use them as numbers. Two
properties encode game rules:

📍 [`backend/src/evaluator.py:81-93`](../backend/src/evaluator.py#L81-L93)
```python
    @property
    def point_value(self) -> int:
        """Card point value for Điểm calculation: Ace=1, 2-9=Face, 10/J/Q/K=0."""
        if self == Rank.ACE:
            return 1
        if self.value >= 10:
            return 0
        return self.value

    @property
    def is_face_card(self) -> bool:
        """Return True if the rank is a face card (Jack, Queen, King)."""
        return self in (Rank.JACK, Rank.QUEEN, Rank.KING)
```

The order of the checks in `point_value` matters: the Ace is 14, so testing `>= 10` first would
give it 0 points. Running `" ".join(f"{r.short_name}:{r.point_value}" for r in Rank)` prints:

```
2:2 3:3 4:4 5:5 6:6 7:7 8:8 9:9 10:0 J:0 Q:0 K:0 A:1
```

So the Ace plays two roles: **14** when ranks are compared (high card, Q-K-A) and **1** when
points are added (A-3-5 is 9 points). Lesson 02 shows the one place where it is also treated as
**1** for ordering (A-2-3).

`short_name` ([evaluator.py:67-79](../backend/src/evaluator.py#L67-L79)) exists because an
`IntEnum` prints as its number in Python 3.11+: `str(Rank.TEN)` is `"10"` but `f"{Rank.JACK}"` is
`"11"`. `short_name` gives `"J"`. Note that ten is always written `"10"`, never `"T"`, even though
the parser accepts both ([evaluator.py:102](../backend/src/evaluator.py#L102)).

### 4. `Card`: a value, not an object with identity

📍 [`backend/src/evaluator.py:110-114`](../backend/src/evaluator.py#L110-L114)
```python
@dataclass(frozen=True)
class Card:
    """Immutable representation of a playing card."""
    rank: Rank
    suit: Suit
```

`frozen=True` gives you three things for free: `__eq__` that compares fields, a `__hash__` from
those same fields, and an error if anyone tries to change a card. On a real run:

| Expression | Result |
|-----------|--------|
| `Card.from_str("As") == Card(Rank.ACE, Suit.SPADES)` | `True` (same fields) |
| `... is ...` | `False` (two objects, still equal) |
| `len({Card.from_str("As"), Card(Rank.ACE, Suit.SPADES)})` | `1` |
| `card.rank = Rank.KING` | `FrozenInstanceError: cannot assign to field 'rank'` |
| `Card.from_str("Kh") < Card.from_str("2s")` | `TypeError` (no ordering defined) |

Hashability is what later code relies on. `Hand.__post_init__` detects duplicates with
`len(set(self.cards)) != 3` ([evaluator.py:385](../backend/src/evaluator.py#L385)), and the
generator removes the hero's cards with `c not in hero_set`
([generator.py:53](../backend/src/generator.py#L53)). Both need cards that hash by value.

### 5. `Card.from_str`: the one tricky parse

📍 [`backend/src/evaluator.py:139-152`](../backend/src/evaluator.py#L139-L152)
```python
        cleaned = card_str.strip()
        if len(cleaned) < 2:
            raise InvalidCardError(f"Card string '{card_str}' is too short.")

        if cleaned.upper().startswith("10"):
            rank_part = cleaned[:2]
            suit_part = cleaned[2:]
        else:
            rank_part = cleaned[0]
            suit_part = cleaned[1:]

        rank = Rank.from_str(rank_part)
        suit = Suit.from_str(suit_part)
        return cls(rank=rank, suit=suit)
```

Every rank is one character except `"10"`. So the parser checks for that prefix first
([evaluator.py:143](../backend/src/evaluator.py#L143)) and otherwise splits after the first
character. Then it delegates to the two enum parsers, which raise `InvalidCardError` for anything
they don't know. Here is what it does with a range of inputs (real output):

| Input | Result |
|-------|--------|
| `"Ah"`, `"AS"`, `"kd"` | `Ah`, `As`, `Kd` (case doesn't matter) |
| `"10s"`, `"Td"`, `"T♥"`, `"10♣"` | `10s`, `10d`, `10h`, `10c` |
| `" 10H "` | `10h` (surrounding spaces stripped) |
| `"10 s"` | `10s` (the space *inside* is stripped too, by `Suit.from_str`) |
| `"X"`, `"Q"` | `Card string 'X' is too short.` |
| `"1s"` | `Invalid rank '1'. Must be 2-10, T, J, Q, K, or A.` |
| `"11h"` | `Invalid rank '1'. …` (the message names the fragment, not your input) |
| `"Ax"` | `Invalid suit 'x'. Must be one of s, c, d, h or ♠, ♣, ♦, ♥.` |
| `"100s"` | `Invalid suit '0s'. …` |
| `"10"` | `Invalid suit ''. …` |

The last three rows are correct rejections with confusing messages. See weak spot 4.

`__str__` and `__repr__` ([evaluator.py:154-158](../backend/src/evaluator.py#L154-L158)) print
`10h` and `Card('10h')`, so `Card.from_str(str(card)) == card` always holds.

### 6. `Deck`: all 52 cards, once

📍 [`backend/src/evaluator.py:161-171`](../backend/src/evaluator.py#L161-L171)
```python
class Deck:
    """Factory for standard 52-card French decks."""

    @staticmethod
    def standard_52() -> tuple[Card, ...]:
        """Generate a complete immutable standard 52-card deck."""
        return tuple(
            Card(rank=r, suit=s)
            for r in Rank
            for s in Suit
        )
```

The outer loop is the rank, so the deck starts `2s 2c 2d 2h 3s …` and ends `Ah`. It returns a
**tuple** (52 items, 52 distinct), so nobody can shuffle or pop the shared deck by accident. The
only production caller is the generator ([generator.py:53](../backend/src/generator.py#L53)), which
removes the hero's three cards to get the 49 the opponent can hold. `Deck` is a class with no
state; it is really a namespace for one function.

### 7. What the tests pin

Six tests cover this lesson ([test_evaluator.py:28-83](../backend/tests/test_evaluator.py#L28-L83)):
`"Ah"`, `"10s"` and `"Td"` parse with the right point values; lower case and `"9♠"` work; `"X"`,
`"11h"` and `"Ax"` raise `InvalidCardError`; and a `Hand` rejects duplicates and wrong counts with
`InvalidHandSizeError`. Nothing tests `Deck`, `Suit.symbol`, the error messages' wording (except one
CLI test, exercise 7), or the shape of the exception tree (exercise 4).

---

## 💡 Concept: `Enum` vs `IntEnum`

An `Enum` is a fixed set of named constants: `Suit.HEARTS`, with `.name == "HEARTS"` and
`.value == "h"`. You can look one up by value (`Suit("h")`) and iterate over all of them
(`list(Suit)`), but members are not strings and can't be compared with `<`.

An `IntEnum` member **is also an `int`**. `Rank.ACE > Rank.KING` is `True`, `sorted()` works, and
arithmetic works too, returning a plain `int`: `Rank.ACE + Rank.KING` is `27`. Use `Enum` when the
constants have no order (suits) and `IntEnum` when they do (ranks).

## 💡 Concept: `@property` and `@classmethod`

A `@property` is a method you read like an attribute: `Rank.ACE.point_value`, no parentheses. Use
it for values computed from other data. A `@classmethod` receives the class (`cls`) instead of an
instance, which makes it the standard way to write an **alternative constructor**:
`Card.from_str("Ah")` parses text and then calls `cls(rank=…, suit=…)`. A `@staticmethod`, like
`Deck.standard_52`, receives neither; it is a function that lives in the class for organisation.

## 💡 Concept: frozen dataclasses and hashing

`@dataclass` writes `__init__`, `__repr__` and `__eq__` from the field list. With `frozen=True` it
also blocks assignment and writes `__hash__` from the same fields. That pairing is the rule every
hashable type must follow: **if `a == b`, then `hash(a) == hash(b)`**. Sets and dict keys depend on
it. `Card` follows it. Lesson 02 shows a class in this file that breaks it.

## 💡 Concept: exception families and `raise … from err`

`except LiengError:` catches every subclass, so one line at the edge of the program handles all
"your input is wrong" cases while real bugs still crash. When you translate a low-level error into
your own, write `raise DatabaseError("…") from err` (as [db.py:85](../backend/src/db.py#L85) does):
the original error stays attached and shows up in the traceback as "The above exception was the
direct cause of …".

---

## Design decisions

- **Fail loudly, at the boundary.** Parsers raise; they never return `None`. A `None` card would
  crash much later, far from the typo that caused it. AGENTS.md says "never silently swallow
  exceptions", and this file follows it.
- **One root class.** Callers can choose how precise to be: `except InvalidCardError` for one
  case, `except LiengError` for all of them.
- **No order on suits, integer ranks.** The types encode the game: suits never decide a showdown,
  ranks always can.
- **Parsing lives next to the type.** `Rank.from_str`, `Suit.from_str` and `Card.from_str` are
  class methods, so the knowledge of how to write a rank is in one place.
- **Values, not objects.** Frozen, hashable cards can be dict keys and set members, and nobody can
  change a card that another part of the program is holding.
- **Lenient input, canonical output.** Upper or lower case, `T` or `10`, letters or symbols all
  parse; printing always uses one form (`10h`).

---

## ⚠️ Weak spots

1. **`InvalidHandSizeError` also means "duplicate card".**
   [evaluator.py:315](../backend/src/evaluator.py#L315) and
   [:386](../backend/src/evaluator.py#L386) raise it for `As As Qd`, which has the right size. The
   docstring ([exceptions.py:15](../backend/src/exceptions.py#L15)) admits the double meaning. A
   caller who wants to say "you typed a card twice" can't tell the two cases apart. *Fix:* add
   `DuplicateCardError(InvalidHandSizeError)`. Making it a subclass keeps every existing
   `except InvalidHandSizeError` and test working (exercise 5).
2. **Built-in errors leak past `LiengError`.** `WinRateDB.get` raises `KeyError`
   ([db.py:119](../backend/src/db.py#L119)); `CallingRangeModel.equity` raises `KeyError` and
   `ValueError` ([calling_range.py:112](../backend/src/calling_range.py#L112),
   [:134](../backend/src/calling_range.py#L134)); `ev.py` raises `ValueError` for a bad pot or bet
   ([ev.py:51-58](../backend/src/ev.py#L51-L58)). `except LiengError` does not catch any of them.
   The CLI compensates by catching `(LiengError, ValueError)` ([cli.py:321](../backend/src/cli.py#L321)),
   and the API is safe only because it always computes the canonical id itself. *Fix:*
   `UnknownHandError(LiengError, KeyError)`: one class that both kinds of `except` catch
   (exercise 6).
3. **Nothing pins the hierarchy.** There is no `test_exceptions.py`. If `DatabaseError` stopped
   inheriting from `LiengError`, all 93 tests would still pass, but the CLI would answer a missing
   file with a traceback and exit 1 instead of `Invalid input: …` and exit 2 (exercise 4). *Fix:* a
   three-line test of `issubclass`.
4. **Error messages quote the fragment, not the input.** `"11h"` reports `Invalid rank '1'`,
   `"10"` reports `Invalid suit ''` ([evaluator.py:150-151](../backend/src/evaluator.py#L150-L151)).
   For a user typing a hand into a web form, "which card?" is the first question. *Fix:* wrap both
   calls and re-raise `Invalid card '11h': …` (exercise 7). Relatedly, `"10 s"` is accepted
   because `Suit.from_str` strips spaces again.
5. **Two definitions of "face card", and dead helpers.** `Rank.is_face_card`
   ([evaluator.py:91](../backend/src/evaluator.py#L91)) is used only by a test. The evaluator decides
   Đĩ with its own numeric check, `r1 >= 11 and r3 <= 13`
   ([evaluator.py:354](../backend/src/evaluator.py#L354)). The two agree today; if one changes, they
   won't. `Suit.symbol` ([evaluator.py:26](../backend/src/evaluator.py#L26)) is used nowhere.
   *Fix:* use the property in the evaluator (if speed allows), or delete it.
6. **Lookup tables rebuilt on every call.** `Suit.from_str`, `Rank.from_str`, `short_name` and
   `symbol` each build a dict literal inside the method
   ([evaluator.py:40-45](../backend/src/evaluator.py#L40-L45),
   [:99-104](../backend/src/evaluator.py#L99-L104)). `Suit.from_str("h")` took 520 ns; the same
   lookup with the dict built once at module level took 124 ns. Parsing is not on a hot path, so
   this is tidiness more than speed.

---

## 🧪 Try it

Run from `backend/` with the virtual environment active.

```bash
python -m pytest tests/test_evaluator.py -q -k "TestCardAndRank or TestHandCreation"
```

Expected output (the timing varies):

```
......                                                                   [100%]
6 passed, 12 deselected in 0.01s
```

Print the exception tree:

```bash
python -c '
import src.exceptions as e
def tree(c, d=0):
    print("    " * d + c.__name__)
    for s in c.__subclasses__():
        tree(s, d + 1)
tree(e.LiengError)
'
```

Expected output:

```
LiengError
    InvalidCardError
    InvalidHandSizeError
    InvalidGameParamsError
    DatabaseError
        DatabaseNotLoadedError
```

See which errors `except LiengError` catches and which escape (weak spot 2):

```bash
python -c '
from src.exceptions import LiengError
from src.db import WinRateDB
from src.calling_range import CallingRangeModel
from src.evaluator import Hand
db = WinRateDB("data/winrates.json"); m = CallingRangeModel()
for label, fn in [("duplicate", lambda: Hand.from_str("As As Qd")),
                  ("db.get J-Q-K", lambda: db.get("J-Q-K")),
                  ("equity f=1.5", lambda: m.equity("K-Q-3", 1.5))]:
    try:
        fn()
    except LiengError as err:
        print(f"{label:13} caught: {type(err).__name__}")
    except Exception as err:
        print(f"{label:13} ESCAPED: {type(err).__name__}: {err}")
'
```

Expected output:

```
duplicate     caught: InvalidHandSizeError
db.get J-Q-K  ESCAPED: KeyError: "Canonical hand 'J-Q-K' not found in database."
equity f=1.5  ESCAPED: ValueError: Fold equity must be between 0.0 and 1.0, got 1.5.
```

(The `KeyError` message is in double quotes because `str()` of a `KeyError` shows its argument's
`repr`. And `"J-Q-K"` really is unknown: its id is `"K-Q-J"`, lesson 03.)

---

## 🏋️ Exercises

Exercises marked 🟡 or 🔴 change code. Undo them afterwards with `git checkout -- <file>`.

**🟢 1. Predict the parse.** What does `Card.from_str` return or raise for `"td"`, `"10♣"`, `"1Os"`
(a letter O), `"Q"` and `"♠A"`? Check each in `python -c`.

<details><summary>Solution</summary>

`"td"` → `10d`; `"10♣"` → `10c`; `"1Os"` → `Invalid rank '1'` (it doesn't start with `"10"`, so the
rank is the single character `"1"`); `"Q"` → `Card string 'Q' is too short.`; `"♠A"` →
`Invalid rank '♠'`: the parser expects rank first.
</details>

**🟢 2. Predict the enum behaviour.** What do these print: `Rank.ACE + Rank.KING`, `str(Rank.TEN)`,
`f"{Rank.JACK}"`, `Rank.JACK.short_name`, and
`sorted({Card.from_str("Kh"), Card.from_str("2s")})`?

<details><summary>Solution</summary>

`27`, `10`, `11`, `J`, and `TypeError: '<' not supported between instances of 'Card' and 'Card'`.
`IntEnum` arithmetic returns plain ints and prints as numbers, which is why `short_name` exists.
`Card` has no ordering; sort with a key, e.g. `sorted(cards, key=lambda c: c.rank)`.
</details>

**🟢 3. Predict what `except LiengError` catches.** For each, caught or escapes?
(a) `Hand.from_str("As Kh Qd Jc")`; (b) `Card.from_str("Zz")`; (c) `WinRateDB().get("Q-K-A")`
(never loaded); (d) a loaded `db.get("A-K-Q")`.

<details><summary>Solution</summary>

(a) caught, `InvalidHandSizeError`. (b) caught, `InvalidCardError` (`Invalid rank 'Z'`).
(c) caught, `DatabaseNotLoadedError` ([db.py:116](../backend/src/db.py#L116)). (d) escapes as
`KeyError`: Q-K-A is stored as `"Q-K-A"`, not `"A-K-Q"` (lesson 03).
</details>

**🟡 4. Show that nothing pins the hierarchy.** In
[exceptions.py:24](../backend/src/exceptions.py#L24) change `DatabaseError(LiengError)` to
`DatabaseError(Exception)`. Predict, then run `python -m pytest -q` and
`python -m src.cli --db nope.json --pot 1 --bet 1; echo $?`. Then write the test that would have
caught it.

<details><summary>Solution</summary>

`93 passed`. The CLI now ends in a traceback,
`src.exceptions.DatabaseError: Database file 'nope.json' does not exist.`, with exit code 1. Before
the change it printed `Invalid input: Database file 'nope.json' does not exist.` and exited 2. A
pinning test:

```python
def test_every_project_error_is_a_lieng_error() -> None:
    for cls in (InvalidCardError, InvalidHandSizeError, InvalidGameParamsError,
                DatabaseError, DatabaseNotLoadedError):
        assert issubclass(cls, LiengError)
```

Undo with `git checkout -- backend/src/exceptions.py`.
</details>

**🟡 5. Give duplicates their own error.** Add `DuplicateCardError(InvalidHandSizeError)` to
`exceptions.py` and raise it at [evaluator.py:315](../backend/src/evaluator.py#L315) and
[:386](../backend/src/evaluator.py#L386). Check: `python -m pytest -q`, then
`Hand.from_str("As As Qd")` inside `try/except InvalidHandSizeError`.

<details><summary>Solution</summary>

All 93 tests still pass, because the new class is a subclass: `test_duplicate_cards_raises`
expects `InvalidHandSizeError` and still gets one. The `try` prints
`DuplicateCardError … A Liêng hand cannot have duplicate cards.` Undo with
`git checkout -- backend/src/exceptions.py backend/src/evaluator.py`.
</details>

**🔴 6. Stop the `KeyError` leak without breaking anyone.** Add
`class UnknownHandError(LiengError, KeyError)` and raise it at [db.py:119](../backend/src/db.py#L119)
(and, if you like, [calling_range.py:112](../backend/src/calling_range.py#L112)). Check with
`python -m pytest -q`, and add a test that `except LiengError` catches `db.get("J-Q-K")`.

<details><summary>Solution</summary>

93 tests pass, including `test_key_error_on_invalid_id`
([test_db.py:84](../backend/tests/test_db.py#L84)), which still expects `KeyError`: with two bases
the new error *is* both. In a probe, `db.get("J-Q-K")` is now caught by `except LiengError`, and
`isinstance(err, KeyError)` is `True`. Undo with
`git checkout -- backend/src/exceptions.py backend/src/db.py backend/src/calling_range.py`.
</details>

**🔴 7. Name the card in the message.** Wrap the two parser calls at
[evaluator.py:150-151](../backend/src/evaluator.py#L150-L151) in `try/except InvalidCardError` and
re-raise `InvalidCardError(f"Invalid card '{card_str}': {err}") from err`. Run `python -m pytest -q`.
Which test fails, and what does that tell you?

<details><summary>Solution</summary>

`1 failed, 92 passed`: `test_interactive_mode_reports_invalid_hand`
([test_cli.py:47-50](../backend/tests/test_cli.py#L47-L50)) asserts the exact text
`Exiting session: Invalid rank 'X'`, and the message is now
`Invalid card 'Xx': Invalid rank 'X'. …`. Error wording is part of the CLI's contract; update the
assertion deliberately. The UI shows these messages too (lesson 13). Undo with
`git checkout -- backend/src/evaluator.py`.
</details>

---

## ❓ Quiz

1. Why does `Rank` inherit from `IntEnum` but `Suit` only from `Enum`?
2. Why must `point_value` test for the Ace *before* testing `self.value >= 10`?
3. Why does `Card.from_str` check for the prefix `"10"` before anything else?
4. Which property of `Card` makes `len(set(cards)) != 3` a valid duplicate check, and which
   decorator argument provides it?
5. Name one exception that a caller of `WinRateDB.get` can receive that is *not* a `LiengError`,
   and one place in the code that works around this.

<details><summary>Answers</summary>

1. Ranks have an order and are used as numbers (comparisons, sorting, the Liêng table). Suits have
   no order in Liêng, so making them incomparable prevents mistakes.
2. `Rank.ACE` is 14, so `>= 10` would match it first and give it 0 points instead of 1.
3. It is the only two-character rank. Without the check, `"10s"` would be split into rank `"1"`
   and suit `"0s"`, both invalid.
4. Equal cards have equal hashes, because `@dataclass(frozen=True)` generates `__eq__` and
   `__hash__` from the same fields.
5. `KeyError` for an unknown canonical id ([db.py:119](../backend/src/db.py#L119)). The CLI catches
   `(LiengError, ValueError)` ([cli.py:321](../backend/src/cli.py#L321)); the API avoids it by always
   computing the id from real cards.
</details>

---

## Recap

- `exceptions.py` is one tree rooted at `LiengError`. Edges of the program (`cli.py`, `app.py`)
  catch it once and turn it into exit code 2 or a 400 response.
- `Suit` is an unordered `Enum`; `Rank` is an `IntEnum` from 2 to 14 with `point_value` (Ace 1,
  10–K 0) and `short_name` (because `IntEnum`s print as numbers).
- `Card` is a frozen dataclass: equal by value, hashable, immutable, not ordered.
- `Card.from_str` handles `"10"` first, then one character of rank and the rest as suit; it accepts
  case, `T` and symbols, and raises `InvalidCardError` for anything else.
- `Deck.standard_52()` returns all 52 cards as a tuple; the generator is its only caller.
- Weak spots: one error name for two problems, `KeyError`/`ValueError` escaping the family, an
  untested hierarchy, and messages that don't name the bad card.

**Next:** [02 — Hand evaluation](02-hand-evaluation.md)
