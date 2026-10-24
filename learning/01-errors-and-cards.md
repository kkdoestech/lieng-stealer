# Lesson 01 — Errors and cards

> **Goal:** understand the project's exception family and the four small types everything else is
> built on (`Suit`, `Rank`, `Card`, `Deck`), including exactly how the text `"10h"` becomes a card
> and what happens when the text is wrong.
> **Files:** [`backend/src/exceptions.py`](../backend/src/exceptions.py),
> [`backend/src/evaluator.py:21-176`](../backend/src/evaluator.py#L21-L176),
> [`backend/tests/test_evaluator.py:31-86`](../backend/tests/test_evaluator.py#L31-L86),
> [`backend/tests/test_exceptions.py`](../backend/tests/test_exceptions.py).
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
| 1 | [exceptions.py:9-42](../backend/src/exceptions.py#L9-L42) | Eight classes, one root. Note the two that have a second parent, a built-in. |
| 2 | [evaluator.py:21-39](../backend/src/evaluator.py#L21-L39) | `Suit`: an `Enum` with a symbol and a parser. |
| 3 | [evaluator.py:42-83](../backend/src/evaluator.py#L42-L83) | `Rank`: an `IntEnum`, its point value, face cards, parser. |
| 4 | [evaluator.py:86-108](../backend/src/evaluator.py#L86-L108) | The four lookup tables both enums use, built once at import. |
| 5 | [evaluator.py:111-163](../backend/src/evaluator.py#L111-L163) | `Card`: a frozen dataclass and `from_str`, with the `"10"` special case. |
| 6 | [evaluator.py:166-176](../backend/src/evaluator.py#L166-L176) | `Deck.standard_52`: all 52 cards as a tuple. |
| 7 | [test_evaluator.py:31-86](../backend/tests/test_evaluator.py#L31-L86), [:287-296](../backend/tests/test_evaluator.py#L287-L296), [test_exceptions.py](../backend/tests/test_exceptions.py) | The tests that pin parsing, validation, the message wording and the exception tree. |

---

## Walkthrough

### 1. The exception family

📍 [`backend/src/exceptions.py:9-42`](../backend/src/exceptions.py#L9-L42)
```python
class LiengError(Exception):
    """Base exception class for all Liêng engine errors."""


class InvalidCardError(LiengError):
    """Raised when card string or parameters are invalid."""


class InvalidHandSizeError(LiengError):
    """Raised when hand does not contain exactly 3 unique cards."""


class DuplicateCardError(InvalidHandSizeError):
    """Raised when the same card appears more than once in a hand."""


class InvalidGameParamsError(LiengError, ValueError):
    """Raised when pot, bet size, fold equity, or opponent model are invalid."""


class UnknownHandError(LiengError, KeyError):
    """Raised when a canonical hand ID is not one of the 455 known classes."""

    def __str__(self) -> str:
        # KeyError.__str__ quotes its argument; report the message as written instead.
        return str(self.args[0]) if self.args else ""


class DatabaseError(LiengError):
    """Base error for precomputed database operations."""


class DatabaseNotLoadedError(DatabaseError):
    """Raised when querying a database that has not been loaded."""
```

The whole file is a tree with one root:

```
LiengError
├── InvalidCardError           bad rank or suit text            evaluator.py:38, :82, :142, :156
├── InvalidHandSizeError       not 3 cards                      evaluator.py:326, :411, :436, hands.py:115
│   └── DuplicateCardError     the same card twice              evaluator.py:332, :413, hands.py:117
├── InvalidGameParamsError     bad pot / bet / fold / model     ev.py:65-71, calling_range.py:145,
│   (also a ValueError)                                         cli.py:255, app.py:214-275
├── UnknownHandError           id is not one of the 455         db.py:130, calling_range.py:123
│   (also a KeyError)
└── DatabaseError              winrates.json missing or broken  db.py:89-107, :173-193
    └── DatabaseNotLoadedError   query before load()            db.py:127, :153, range_finder.py:47
```

The point of a family is the `except` at the edges. The CLI catches `DatabaseError` first and
reports `Cannot load the win-rate database: …` with exit code 1
([cli.py:364](../backend/src/cli.py#L364)), then catches the rest of the family once and turns it
into `Invalid input: …` with exit code 2 ([cli.py:367](../backend/src/cli.py#L367)). The API has one
handler that turns `InvalidGameParamsError` into a 400 with `"code": "invalid_params"`
([app.py:184](../backend/app.py#L184)) and one that turns a bad card or hand, duplicates included,
into a 400 with `"code": "invalid_hand"` ([app.py:188-191](../backend/app.py#L188-L191)). Any
*other* exception, such as a `TypeError` from a real bug, is still not mistaken for bad input: the
CLI crashes with a traceback, and the API logs it and answers a generic 500
([app.py:198](../backend/app.py#L198)).

Three classes are more than a plain child of `LiengError`, each for a reason:

- `DuplicateCardError` is a kind of `InvalidHandSizeError`, so every `except InvalidHandSizeError`
  written before it existed (the API handler, the tests) still catches a duplicate.
- `InvalidGameParamsError` is also a `ValueError`, and `UnknownHandError` is also a `KeyError`.
  Code written against the built-ins (`except KeyError` around a dictionary-style lookup) keeps
  working, and `except LiengError` now catches these too.
- `UnknownHandError` overrides `__str__` because `str(KeyError("msg"))` is `"'msg'"`, with quotes.
  The override prints the message as written.

### 2. `Suit`: four constants and a forgiving parser

`Suit` is a plain `Enum` whose values are the one-letter codes `"s"`, `"c"`, `"d"`, `"h"`
([evaluator.py:21-26](../backend/src/evaluator.py#L21-L26)). Its parser accepts the letter in any
case or the Unicode symbol, by looking the cleaned text up in a table:

📍 [`backend/src/evaluator.py:33-39`](../backend/src/evaluator.py#L33-L39)
```python
    @classmethod
    def from_str(cls, suit_str: str) -> Suit:
        """Parse suit from single-character representation or unicode symbol."""
        suit = _SUIT_BY_TEXT.get(suit_str.strip().lower())
        if suit is None:
            raise InvalidCardError(f"Invalid suit '{suit_str}'. Must be one of s, c, d, h or ♠, ♣, ♦, ♥.")
        return suit
```

The table is built once, at import, from the enum itself:

📍 [`backend/src/evaluator.py:86-97`](../backend/src/evaluator.py#L86-L97)
```python
# Lookup tables used by the enums above. They live at module level because a dict assigned inside
# an Enum class body would become an enum member, and building them once avoids per-call work.
_SUIT_SYMBOLS: Final[dict[Suit, str]] = {
    Suit.SPADES: "♠",
    Suit.CLUBS: "♣",
    Suit.DIAMONDS: "♦",
    Suit.HEARTS: "♥",
}
_SUIT_BY_TEXT: Final[dict[str, Suit]] = {
    **{suit.value: suit for suit in Suit},
    **{symbol: suit for suit, symbol in _SUIT_SYMBOLS.items()},
}
```

`_SUIT_BY_TEXT` has eight keys: `"s"`, `"c"`, `"d"`, `"h"` and the four symbols. The comment
explains a real trap: inside `class Suit(Enum):`, any plain assignment such as
`_TABLE = {...}` would become a fifth *member* of the enum, not a helper. So the tables live below
both classes, and `Suit.from_str` can still use them because the name is only looked up when the
method runs. Until October 2026 each method built its dict literal on every call (weak spot 6).

Two things to notice. Suits have **no order**: `Suit` is an `Enum`, not an `IntEnum`, so
`Suit.SPADES < Suit.HEARTS` is a `TypeError`. That matches the rule "suits never decide a
showdown". And the `symbol` property ([evaluator.py:28-31](../backend/src/evaluator.py#L28-L31)) is
never called anywhere in the backend: every card prints with its letter (`str(card)` is `"Ah"`, not
`"A♥"`).

### 3. `Rank`: integers with names

`Rank` is an `IntEnum` from `TWO = 2` to `ACE = 14`
([evaluator.py:42-56](../backend/src/evaluator.py#L42-L56)). Because each member *is* an `int`,
`Rank.ACE > Rank.KING` is `True`, and later code can sort ranks and use them as numbers. Two
properties encode game rules:

📍 [`backend/src/evaluator.py:63-75`](../backend/src/evaluator.py#L63-L75)
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

`short_name` ([evaluator.py:58-61](../backend/src/evaluator.py#L58-L61)) exists because an
`IntEnum` prints as its number in Python 3.11+: `str(Rank.TEN)` is `"10"` but `f"{Rank.JACK}"` is
`"11"`. `short_name` gives `"J"`, read from `_RANK_NAMES`
([evaluator.py:98-104](../backend/src/evaluator.py#L98-L104)). `Rank.from_str` looks the
upper-cased text up in `_RANK_BY_TEXT`, which is the same names plus one extra key, `"T"`
([evaluator.py:105-108](../backend/src/evaluator.py#L105-L108)). So ten is always *written* `"10"`,
never `"T"`, but the parser accepts both.

### 4. `Card`: a value, not an object with identity

📍 [`backend/src/evaluator.py:111-115`](../backend/src/evaluator.py#L111-L115)
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
`len(set(self.cards)) != 3` ([evaluator.py:412](../backend/src/evaluator.py#L412)), and the
generator removes the hero's cards with `c not in hero_set`
([generator.py:62](../backend/src/generator.py#L62)). Both need cards that hash by value.

### 5. `Card.from_str`: the one tricky parse

📍 [`backend/src/evaluator.py:140-157`](../backend/src/evaluator.py#L140-L157)
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

        try:
            rank = Rank.from_str(rank_part)
            suit = Suit.from_str(suit_part)
        except InvalidCardError as err:
            # Name the whole card: "11h" alone would otherwise be reported as "Invalid rank '1'".
            raise InvalidCardError(f"Invalid card '{cleaned}': {err}") from err
        return cls(rank=rank, suit=suit)
```

Every rank is one character except `"10"`. So the parser checks for that prefix first
([evaluator.py:144](../backend/src/evaluator.py#L144)) and otherwise splits after the first
character. Then it delegates to the two enum parsers, which raise `InvalidCardError` for anything
they don't know. The enum parsers only ever see a fragment (`"1"`, `"0s"`), so `from_str` catches
their error and raises a new one that starts with the whole card, keeping the original attached
with `from err`. Here is what it does with a range of inputs (real output):

| Input | Result |
|-------|--------|
| `"Ah"`, `"AS"`, `"kd"` | `Ah`, `As`, `Kd` (case doesn't matter) |
| `"10s"`, `"Td"`, `"T♥"`, `"10♣"` | `10s`, `10d`, `10h`, `10c` |
| `" 10H "` | `10h` (surrounding spaces stripped) |
| `"10 s"` | `10s` (the space *inside* is stripped too, by `Suit.from_str`) |
| `"X"`, `"Q"` | `Card string 'X' is too short.` |
| `"1s"` | `Invalid card '1s': Invalid rank '1'. Must be 2-10, T, J, Q, K, or A.` |
| `"11h"` | `Invalid card '11h': Invalid rank '1'. …` |
| `"Ax"` | `Invalid card 'Ax': Invalid suit 'x'. Must be one of s, c, d, h or ♠, ♣, ♦, ♥.` |
| `"100s"` | `Invalid card '100s': Invalid suit '0s'. …` |
| `"10"` | `Invalid card '10': Invalid suit ''. …` |

The last three rows used to be correct rejections with confusing messages, because they named only
the fragment (`Invalid rank '1'` for `"11h"`). Weak spot 4 tells how that was fixed. The `"10 s"`
row is still lenient (weak spot 7).

`__str__` and `__repr__` ([evaluator.py:159-163](../backend/src/evaluator.py#L159-L163)) print
`10h` and `Card('10h')`, so `Card.from_str(str(card)) == card` always holds.

### 6. `Deck`: all 52 cards, once

📍 [`backend/src/evaluator.py:166-176`](../backend/src/evaluator.py#L166-L176)
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
only production caller is the generator ([generator.py:62](../backend/src/generator.py#L62)), which
removes the hero's three cards to get the 49 the opponent can hold. `Deck` is a class with no
state; it is really a namespace for one function.

### 7. What the tests pin

Six tests in two classes cover parsing and validation
([test_evaluator.py:31-86](../backend/tests/test_evaluator.py#L31-L86)): `"Ah"`, `"10s"` and `"Td"`
parse with the right point values; lower case and `"9♠"` work; `"X"`, `"11h"` and `"Ax"` raise
`InvalidCardError`; and a `Hand` rejects duplicates and wrong counts with `InvalidHandSizeError`.
Two more pin the fixes from this lesson's weak spots
([test_evaluator.py:287-296](../backend/tests/test_evaluator.py#L287-L296)): a duplicate raises the
specific `DuplicateCardError`, and the message for `"11h"` starts with `Invalid card '11h'`.

[test_exceptions.py](../backend/tests/test_exceptions.py) pins the tree itself: one parametrized
test checks every class's parents with `issubclass` (seven cases), and one checks that
`UnknownHandError` prints its message without quotes. The exact wording of a card error is also
asserted by two CLI tests ([test_cli.py:56](../backend/tests/test_cli.py#L56),
[:64](../backend/tests/test_cli.py#L64)) and one API test
([test_api.py:110](../backend/tests/test_api.py#L110)). Nothing tests `Deck` directly or
`Suit.symbol`.

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
it. `Card` follows it. Lesson 02 shows a class in this file that used to break it, and how it was
fixed.

## 💡 Concept: exception families and `raise … from err`

`except LiengError:` catches every subclass, so one line at the edge of the program handles all
"your input is wrong" cases while real bugs still crash. When you translate a low-level error into
your own, write `raise DatabaseError("…") from err` (as [db.py:95](../backend/src/db.py#L95) does):
the original error stays attached and shows up in the traceback as "The above exception was the
direct cause of …".

---

## Design decisions

- **Fail loudly, at the boundary.** Parsers raise; they never return `None`. A `None` card would
  crash much later, far from the typo that caused it. AGENTS.md says "never silently swallow
  exceptions", and this file follows it.
- **One root class.** Callers can choose how precise to be: `except InvalidCardError` for one
  case, `except LiengError` for all of them.
- **New errors fit under old ones.** `DuplicateCardError` subclasses `InvalidHandSizeError`, and
  `UnknownHandError` / `InvalidGameParamsError` also subclass `KeyError` / `ValueError`. Adding a
  more precise error then breaks no existing `except`. The cost is a tree that is a little less
  tidy, which `test_exceptions.py` now pins.
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

Six weak spots were listed here when the course was written. The October 2026 fixes (commit
`bba5e63`, "fix(core)") closed four of them; two small ones, and a new one, are still open.

1. ✅ **Fixed: `InvalidHandSizeError` also meant "duplicate card".** `As As Qd` has the right size,
   yet it raised the same error as a two-card hand, so a caller couldn't say "you typed a card
   twice". Now both duplicate checks raise `DuplicateCardError`
   ([evaluator.py:332](../backend/src/evaluator.py#L332),
   [:413](../backend/src/evaluator.py#L413)), and so does `get_canonical_id`
   ([hands.py:117](../backend/src/hands.py#L117), lesson 03). Because it subclasses
   `InvalidHandSizeError`, the old test `test_duplicate_cards_raises` and the API's `invalid_hand`
   handler still catch it. Pinned by `test_duplicate_cards_raise_duplicate_card_error`
   ([test_evaluator.py:288-292](../backend/tests/test_evaluator.py#L288-L292)) and
   [test_hands.py:115-119](../backend/tests/test_hands.py#L115-L119).
2. ✅ **Fixed: built-in errors leaked past `LiengError`.** `WinRateDB.get` and
   `CallingRangeModel.equity` used to raise a plain `KeyError` for an unknown id, and `ev.py` and
   the calling-range model a plain `ValueError` for bad numbers, so `except LiengError` missed all
   of them. Now they raise `UnknownHandError` ([db.py:130](../backend/src/db.py#L130),
   [calling_range.py:123](../backend/src/calling_range.py#L123)) and `InvalidGameParamsError`
   ([ev.py:65-71](../backend/src/ev.py#L65-L71),
   [calling_range.py:145](../backend/src/calling_range.py#L145)), each of which is *both* a
   `LiengError` and the built-in it replaced. Pinned by
   `test_unknown_id_is_a_project_error_and_a_key_error`
   ([test_db.py:146-151](../backend/tests/test_db.py#L146-L151)) and the parents test. *Still open,
   and minor:* three plain `ValueError`s remain for programming mistakes rather than user input
   (`steps < 1` at [ev.py:178](../backend/src/ev.py#L178), a missing calling model at
   [range_finder.py:81](../backend/src/range_finder.py#L81), `samples < 1` at
   [generator.py:54](../backend/src/generator.py#L54)), which is why the CLI still catches
   `(LiengError, ValueError)` ([cli.py:367](../backend/src/cli.py#L367)).
3. ✅ **Fixed: nothing pinned the hierarchy.** If `DatabaseError` stopped inheriting from
   `LiengError`, all 93 tests at the time still passed. Now
   [test_exceptions.py:22-36](../backend/tests/test_exceptions.py#L22-L36) checks every class's
   parents, and that change fails two of its cases (exercise 4).
4. ✅ **Fixed: error messages quoted the fragment, not the input.** `"11h"` used to report
   `Invalid rank '1'`, and `"10"` reported `Invalid suit ''`. Now `Card.from_str` wraps both
   parser calls and re-raises with the whole card first
   ([evaluator.py:151-156](../backend/src/evaluator.py#L151-L156)):
   `Invalid card '11h': Invalid rank '1'. …`. Pinned by `test_card_error_names_the_whole_card`
   ([test_evaluator.py:294-296](../backend/tests/test_evaluator.py#L294-L296)) and the CLI/API tests
   that assert the full text.
5. **Two definitions of "face card", and dead helpers.** `Rank.is_face_card`
   ([evaluator.py:72-75](../backend/src/evaluator.py#L72-L75)) is used only by `Card.is_face_card`,
   which only a test calls. The evaluator decides Đĩ with its own numeric check,
   `r1 >= 11 and r3 <= 13` ([evaluator.py:374](../backend/src/evaluator.py#L374)). The two agree
   today; if one changes, they won't. `Suit.symbol`
   ([evaluator.py:28-31](../backend/src/evaluator.py#L28-L31)) is used nowhere. `ruff` (added in the
   fixes) removes unused *imports*, not unused properties. *Fix:* use the property in the evaluator's
   table builder (it runs only 455 times, at import, so speed no longer matters), or delete it.
6. ✅ **Fixed: lookup tables were rebuilt on every call.** `Suit.from_str`, `Rank.from_str`,
   `short_name` and `symbol` each built a dict literal inside the method; `Suit.from_str("h")` took
   520 ns. The four tables now live at module level
   ([evaluator.py:86-108](../backend/src/evaluator.py#L86-L108)), and the same call takes about
   180 ns on the same machine. Parsing is not on a hot path, so this was tidiness more than speed;
   no test pins it.
7. **Spaces inside a card are accepted.** `"10 s"` and `"A h"` parse as `10s` and `Ah`, because
   `Suit.from_str` strips its fragment again ([evaluator.py:36](../backend/src/evaluator.py#L36)).
   Harmless in a hand like `"As Kh Qd"` (it is split on spaces first), but a card that the user
   wrote as two tokens should be an error, not a guess. *Fix:* reject whitespace inside `cleaned`
   (exercise 7).

---

## 🧪 Try it

Run from `backend/` with the virtual environment active.

```bash
python -m pytest tests/test_evaluator.py -q -k "TestCardAndRank or TestHandCreation"
```

Expected output (the timing varies):

```
......                                                                   [100%]
6 passed, 21 deselected in 0.02s
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
        DuplicateCardError
    InvalidGameParamsError
    UnknownHandError
    DatabaseError
        DatabaseNotLoadedError
```

(`__subclasses__()` lists only classes that name the parent directly, so the built-in second
parents don't show up here. The next command shows them.)

See that `except LiengError` now catches the three errors that used to escape it (weak spots 1
and 2), and that each is still the built-in it replaced:

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
        print(f"{label:13} {type(err).__name__:22} KeyError={isinstance(err, KeyError)!s:5} "
              f"ValueError={isinstance(err, ValueError)}")
        print(" " * 13, err)
'
```

Expected output:

```
duplicate     DuplicateCardError     KeyError=False ValueError=False
              A Liêng hand cannot have duplicate cards.
db.get J-Q-K  UnknownHandError       KeyError=True  ValueError=False
              Canonical hand 'J-Q-K' not found in database.
equity f=1.5  InvalidGameParamsError KeyError=False ValueError=True
              Fold equity must be between 0.0 and 1.0, got 1.5.
```

Before the fixes the last two lines escaped as a plain `KeyError` (printed in quotes,
`"Canonical hand 'J-Q-K' …"`) and a plain `ValueError`. `"J-Q-K"` really is unknown: its id is
`"K-Q-J"` (lesson 03).

---

## 🏋️ Exercises

Exercises marked 🟡 or 🔴 change code. Undo them afterwards with `git checkout -- <file>`.

**🟢 1. Predict the parse.** What does `Card.from_str` return or raise for `"td"`, `"10♣"`, `"1Os"`
(a letter O), `"Q"` and `"♠A"`? Check each in `python -c`.

<details><summary>Solution</summary>

`"td"` → `10d`; `"10♣"` → `10c`; `"1Os"` → `Invalid card '1Os': Invalid rank '1'. …` (it doesn't
start with `"10"`, so the rank is the single character `"1"`); `"Q"` →
`Card string 'Q' is too short.` (raised before the `try`, so it has no `Invalid card` prefix);
`"♠A"` → `Invalid card '♠A': Invalid rank '♠'. …`: the parser expects rank first.
</details>

**🟢 2. Predict the enum behaviour.** What do these print: `Rank.ACE + Rank.KING`, `str(Rank.TEN)`,
`f"{Rank.JACK}"`, `Rank.JACK.short_name`, and
`sorted({Card.from_str("Kh"), Card.from_str("2s")})`?

<details><summary>Solution</summary>

`27`, `10`, `11`, `J`, and `TypeError: '<' not supported between instances of 'Card' and 'Card'`.
`IntEnum` arithmetic returns plain ints and prints as numbers, which is why `short_name` exists.
`Card` has no ordering; sort with a key, e.g. `sorted(cards, key=lambda c: c.rank)`.
</details>

**🟢 3. Predict what `except LiengError` catches.** For each, caught or escapes, and as which
class? (a) `Hand.from_str("As Kh Qd Jc")`; (b) `Card.from_str("Zz")`; (c) `WinRateDB().get("Q-K-A")`
(never loaded); (d) a loaded `db.get("A-K-Q")`.

<details><summary>Solution</summary>

All four are caught. (a) `InvalidHandSizeError`. (b) `InvalidCardError`
(`Invalid card 'Zz': Invalid rank 'Z'. …`). (c) `DatabaseNotLoadedError`
([db.py:127](../backend/src/db.py#L127)). (d) `UnknownHandError`: Q-K-A is stored as `"Q-K-A"`, not
`"A-K-Q"` (lesson 03). Before the fixes, (d) escaped as a plain `KeyError`.
</details>

**🟡 4. Break the hierarchy on purpose.** In [exceptions.py:37](../backend/src/exceptions.py#L37)
change `DatabaseError(LiengError)` to `DatabaseError(Exception)`. Predict which tests fail, then run
`python -m pytest -q`. Also predict, then run,
`python -m src.cli --db nope.json --pot 1 --bet 1; echo $?`.

<details><summary>Solution</summary>

`2 failed, 157 passed`: the `DatabaseError` and `DatabaseNotLoadedError` cases of
`test_exception_parents` ([test_exceptions.py:22-36](../backend/tests/test_exceptions.py#L22-L36)).
Nothing else notices. The CLI still prints
`Cannot load the win-rate database: Database file 'nope.json' does not exist.` and exits 1,
because it catches `DatabaseError` by name before the catch-all
([cli.py:364](../backend/src/cli.py#L364)). Before the fixes, the same change made every test pass
while the CLI crashed with a traceback; the parents test is now the only safety net, which is
exactly its job. Undo with `git checkout -- backend/src/exceptions.py`.
</details>

**🟡 5. Why is `DuplicateCardError` a subclass?** In
[exceptions.py:21](../backend/src/exceptions.py#L21) change `DuplicateCardError(InvalidHandSizeError)`
to `DuplicateCardError(LiengError)`. Predict how many tests fail and what this request returns, then
check:

```bash
python -c '
from app import create_app
c = create_app(config={"TESTING": True}).test_client()
r = c.post("/api/evaluate", json={"hand": "As As Qd"}); print(r.status_code, r.get_json())
'
```

<details><summary>Solution</summary>

Before the change it prints
`400 {'code': 'invalid_hand', 'error': 'A Liêng hand cannot have duplicate cards.'}`. After it,
`3 failed, 156 passed`: `test_duplicate_cards_raises` (it expects `InvalidHandSizeError`), the
`DuplicateCardError` case of the parents test, and `test_analyze_rejects_an_invalid_hand`
([test_api.py:297-300](../backend/tests/test_api.py#L297-L300)), which now gets a 500. The probe
logs a traceback and prints `500 {'code': 'internal_error', 'error': 'Internal server error.'}`: the
API's `invalid_hand` handler is registered for `InvalidHandSizeError`
([app.py:188-191](../backend/app.py#L188-L191)), so a duplicate that is no longer one falls through
to the catch-all. Subclassing is what let the new error be added without touching any caller. Undo
with `git checkout -- backend/src/exceptions.py`.
</details>

**🟡 6. Why does `UnknownHandError` override `__str__`?** Delete
[exceptions.py:32-34](../backend/src/exceptions.py#L32-L34). Predict what
`str(err)` is for `db.get("J-Q-K")`, then run `python -m pytest -q`.

<details><summary>Solution</summary>

`"Canonical hand 'J-Q-K' not found in database."`, with the double quotes: `KeyError.__str__`
returns the `repr` of its argument, and `UnknownHandError` inherits it. `1 failed, 158 passed`:
`test_unknown_hand_error_message_is_not_quoted`
([test_exceptions.py:39-41](../backend/tests/test_exceptions.py#L39-L41)). The quotes would reach any
user who sees the message, such as a CLI error line. Undo with
`git checkout -- backend/src/exceptions.py`.
</details>

**🔴 7. Reject a space inside a card (weak spot 7).** Make `Card.from_str("10 s")` and
`Card.from_str("A h")` raise `InvalidCardError`, while `" 10h "` (spaces *around* the card) still
parses. Add a test, then run `python -m pytest -q`.

<details><summary>Solution</summary>

After the length check ([evaluator.py:141-142](../backend/src/evaluator.py#L141-L142)) add:

```python
        if any(ch.isspace() for ch in cleaned):
            raise InvalidCardError(f"Card string '{cleaned}' contains a space.")
```

and a test in `tests/test_evaluator.py`:

```python
def test_space_inside_a_card_is_rejected() -> None:
    for text in ("10 s", "A h"):
        with pytest.raises(InvalidCardError, match="contains a space"):
            Card.from_str(text)
    assert str(Card.from_str(" 10h ")) == "10h"
```

`160 passed`. Nothing else breaks, because `Hand.from_str` splits on whitespace before it calls
`Card.from_str`, so no token it passes contains a space: `Hand.from_str("As  Kh,Qd")` still gives
`As Kh Qd`. Undo with `git checkout -- backend/src/evaluator.py backend/tests/test_evaluator.py`.
</details>

---

## ❓ Quiz

1. Why does `Rank` inherit from `IntEnum` but `Suit` only from `Enum`?
2. Why must `point_value` test for the Ace *before* testing `self.value >= 10`?
3. Why does `Card.from_str` check for the prefix `"10"` before anything else?
4. Which property of `Card` makes `len(set(cards)) != 3` a valid duplicate check, and which
   decorator argument provides it?
5. `WinRateDB.get("J-Q-K")` raises `UnknownHandError`. Name two different `except` clauses that
   catch it, and say why the class was given two parents.

<details><summary>Answers</summary>

1. Ranks have an order and are used as numbers (comparisons, sorting, the Liêng table). Suits have
   no order in Liêng, so making them incomparable prevents mistakes.
2. `Rank.ACE` is 14, so `>= 10` would match it first and give it 0 points instead of 1.
3. It is the only two-character rank. Without the check, `"10s"` would be split into rank `"1"`
   and suit `"0s"`, both invalid.
4. Equal cards have equal hashes, because `@dataclass(frozen=True)` generates `__eq__` and
   `__hash__` from the same fields.
5. `except LiengError` and `except KeyError` (also `except UnknownHandError`). It subclasses
   `LiengError` so the project's catch-alls handle it ([cli.py:367](../backend/src/cli.py#L367)),
   and `KeyError` so code written when `WinRateDB.get` raised a plain `KeyError`
   ([db.py:130](../backend/src/db.py#L130)) keeps working.
</details>

---

## Recap

- `exceptions.py` is one tree of eight classes rooted at `LiengError`. Edges of the program
  (`cli.py`, `app.py`) catch it and turn it into exit code 2 (1 for a database problem) or a 400
  JSON response with a `code`.
- `DuplicateCardError` subclasses `InvalidHandSizeError`; `InvalidGameParamsError` and
  `UnknownHandError` are also a `ValueError` and a `KeyError`. New errors fit under old `except`s,
  and `test_exceptions.py` pins every parent.
- `Suit` is an unordered `Enum`; `Rank` is an `IntEnum` from 2 to 14 with `point_value` (Ace 1,
  10–K 0) and `short_name` (because `IntEnum`s print as numbers).
- `Card` is a frozen dataclass: equal by value, hashable, immutable, not ordered.
- `Card.from_str` handles `"10"` first, then one character of rank and the rest as suit; it accepts
  case, `T` and symbols, and raises `InvalidCardError` naming the whole card for anything else.
  The enums' lookup tables are built once, at module level.
- `Deck.standard_52()` returns all 52 cards as a tuple; the generator is its only caller.
- Fixed: a separate duplicate error, no built-in errors escaping the family, a pinned hierarchy,
  messages that name the card, tables built once. Still open: dead face-card/symbol helpers, a few
  plain `ValueError`s for programming mistakes, and spaces accepted inside a card.

**Next:** [02 — Hand evaluation](02-hand-evaluation.md)
