# 03 — Python Toolkit

> **Goal:** learn the Python features the project uses, with tiny examples, so the real code in later
> chapters is easy to read.
> **You will build:** nothing in the project. Try every example in the Python REPL.
> **Time:** ~1.5 hours.
> **Prerequisites:** [02](02-setup-and-project-skeleton.md). Basic Python (variables, `if`, `for`, functions, lists, dicts).

---

## The big picture

The project's code looks "advanced" at first glance: lots of `@`, `->`, `cls`, `__lt__`… In fact it only
uses about ten language features again and again. Learn them here once, and every later chapter will
read like plain English.

Start the REPL from `backend/` (with your venv active) and type along:

```bash
python
```

```
>>>
```

Exit with `exit()` or Ctrl-D (Ctrl-Z then Enter on Windows).

| # | Feature | Where it's used |
|---|---------|-----------------|
| 1 | Type hints | everywhere |
| 2 | f-strings | everywhere |
| 3 | `Enum` and `IntEnum` | `Suit`, `Rank`, `HandCategory` |
| 4 | Classes, `@property`, `@classmethod`, `@staticmethod` | `Card.from_str`, `Rank.point_value`, `Deck.standard_52` |
| 5 | `@dataclass(frozen=True)` | `Card`, `Hand`, `HandScore`, `EVResult`, … |
| 6 | Dunder methods & comparisons | `HandScore.__lt__`, `WinRateDB.__len__` |
| 7 | Tuple comparison | how we rank hands |
| 8 | Exceptions | `LiengError` family |
| 9 | Comprehensions, `sorted`, `key=` | everywhere |
| 10 | `itertools` | counting hands |
| 11 | Docstrings (Google style) | everywhere |

---

## 1. Type hints

A **type hint** says what type a variable, argument or return value should have:

```python
def add(a: int, b: int) -> int:
    return a + b

price: float = 9.5
names: list[str] = ["An", "Binh"]
scores: dict[str, float] = {"A-A-A": 1.0}
pair: tuple[int, int] = (3, 4)
maybe_name: str | None = None      # "a str, or None"
```

Python **does not check** hints when the program runs. `add("x", "y")` still works and returns `"xy"`.
Hints are for **humans** and for **tools** (VS Code autocomplete, and `mypy`, a program that reads hints
and reports mistakes before you run the code).

You will see this line at the top of most project files:

```python
from __future__ import annotations
```

It tells Python to store hints as plain text and not evaluate them right away. Practical effect: a
class can mention **its own name** in a hint before the class is finished, e.g. a method of `Card`
returning `-> Card`.

`typing.Final` marks a "constant that must not be reassigned":

```python
from typing import Final
TOTAL_COMBINATIONS: Final[int] = 22100
```

## 2. f-strings

An **f-string** puts values inside text:

```python
>>> pot = 132097.0
>>> f"EV is {pot}"
'EV is 132097.0'
>>> f"{pot:,.0f}"          # thousands separator, 0 decimals
'132,097'
>>> f"{0.3333:.1%}"        # as a percentage
'33.3%'
>>> f"{0.35 * 100:.1f}%"
'35.0%'
>>> f"{5:+}"               # always show the sign
'+5'
```

## 3. `Enum` and `IntEnum`

An **enum** is a fixed list of named constants. It prevents typos: `Suit.SPADSE` is an error,
while the string `"spadse"` would be silently wrong.

```python
from enum import Enum, IntEnum

class Suit(Enum):
    SPADES = "s"
    HEARTS = "h"

>>> Suit.SPADES
<Suit.SPADES: 's'>
>>> Suit.SPADES.value
's'
>>> Suit.SPADES.name
'SPADES'
>>> Suit("h")              # look up a member by value
<Suit.HEARTS: 'h'>
>>> list(Suit)             # iterate over all members, in definition order
[<Suit.SPADES: 's'>, <Suit.HEARTS: 'h'>]
```

An **`IntEnum`** member **is also an integer**, so you can compare and do maths with it:

```python
class Rank(IntEnum):
    TWO = 2
    KING = 13
    ACE = 14

>>> Rank.ACE > Rank.KING
True
>>> Rank.ACE.value
14
>>> Rank(13)               # look up by value
<Rank.KING: 13>
>>> Rank["KING"]           # look up by name
<Rank.KING: 13>
>>> sorted([Rank.ACE, Rank.TWO, Rank.KING])
[<Rank.TWO: 2>, <Rank.KING: 13>, <Rank.ACE: 14>]
```

We use `IntEnum` for ranks because "is this card higher?" is just `>`.

## 4. Classes, `@property`, `@classmethod`, `@staticmethod`

```python
class Temperature:
    def __init__(self, celsius: float) -> None:
        self.celsius = celsius

    @property
    def fahrenheit(self) -> float:
        """Computed every time you read it. No parentheses needed."""
        return self.celsius * 9 / 5 + 32

    @classmethod
    def from_str(cls, text: str) -> "Temperature":
        """An alternative constructor: build an instance from text."""
        return cls(float(text.rstrip("C")))

    @staticmethod
    def freezing() -> float:
        """Belongs to the class but needs neither the class nor an instance."""
        return 0.0

>>> t = Temperature.from_str("100C")
>>> t.fahrenheit          # property: no ()
212.0
>>> Temperature.freezing()
0.0
```

- **`@property`**: a method that looks like an attribute. Use it for values computed from other data.
- **`@classmethod`**: receives the **class** as `cls`. The classic use is a "named constructor"
  like `Card.from_str("Ah")`. Writing `cls(...)` instead of `Temperature(...)` also works for subclasses.
- **`@staticmethod`**: a plain function that lives inside a class for organisation.

Properties work on enums too. This is exactly how `Rank.point_value` works later:

```python
class Rank(IntEnum):
    NINE = 9
    TEN = 10
    ACE = 14

    @property
    def point_value(self) -> int:
        if self == Rank.ACE:
            return 1
        if self.value >= 10:
            return 0
        return self.value

>>> Rank.NINE.point_value, Rank.TEN.point_value, Rank.ACE.point_value
(9, 0, 1)
```

## 5. `@dataclass(frozen=True)`

Writing `__init__`, `__repr__` and `__eq__` by hand for every small class is boring. A **dataclass**
generates them from the list of fields:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Point:
    x: int
    y: int

>>> p = Point(1, 2)          # __init__ generated
>>> p
Point(x=1, y=2)              # __repr__ generated
>>> p == Point(1, 2)         # __eq__ generated: compares fields
True
>>> p.x = 5                  # frozen=True → read-only
dataclasses.FrozenInstanceError: cannot assign to field 'x'
>>> {p, Point(1, 2)}         # frozen + eq → also hashable → usable in sets/dict keys
{Point(x=1, y=2)}
```

Why **frozen** (immutable)?

1. **Safety:** nobody can change a card from A♠ into K♥ by accident.
2. **Hashing:** only immutable objects should be dictionary keys or set members. (If a key changed after
   being stored, the dictionary could never find it again.)

The project's spec (`AGENTS.md`) requires all domain objects (`Card`, `Hand`, `HandScore`, `EVResult`) to
be frozen dataclasses.

## 6. Dunder methods and comparison operators

Python turns operators into method calls:

| You write | Python calls |
|-----------|--------------|
| `a < b` | `a.__lt__(b)` |
| `a <= b` | `a.__le__(b)` |
| `a > b` | `a.__gt__(b)` |
| `a >= b` | `a.__ge__(b)` |
| `a == b` | `a.__eq__(b)` |
| `len(x)` | `x.__len__()` |
| `k in x` | `x.__contains__(k)` |
| `str(x)` | `x.__str__()` |
| `repr(x)` (and the REPL) | `x.__repr__()` |

So to make hands comparable with `<`, we write `__lt__` and friends. A common pattern:

```python
class Box:
    def __init__(self, size: int) -> None:
        self.size = size

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Box):
            return NotImplemented      # "I don't know how to compare with that"
        return self.size < other.size

>>> Box(1) < Box(2)
True
>>> Box(1) < 5
TypeError: '<' not supported between instances of 'Box' and 'int'
```

Returning the special value **`NotImplemented`** (not raising an error) lets Python try the other
object's method, and if that also fails, Python raises a clear `TypeError` for you.

> ⚠️ **The hash/eq contract.** If you write your own `__eq__`, then for any two objects with
> `a == b`, `hash(a)` **must** equal `hash(b)`. Otherwise sets and dicts behave strangely. Keep this in
> mind; it comes back as a Pitfall in chapter 5.

## 7. Tuple comparison: the trick behind hand ranking

Python compares tuples **element by element, left to right**, and stops at the first difference,
just like comparing words in a dictionary:

```python
>>> (4, 2) > (3, 14)       # 4 > 3, decided immediately
True
>>> (1, 9, 13) > (1, 9, 12)   # first two equal, 13 > 12
True
>>> (1, 9) == (1, 9)
True
```

This is the **key design idea** of the hand evaluator: we turn each hand into a tuple like
`(category, primary_rank, secondary_rank, score, tie_breaker)`. The category comes first, so a
Sáp (4, …) beats every Liêng (3, …) automatically. Only if the categories are equal does Python look at
the next element. One `>` decides any showdown.

## 8. Exceptions and custom exception classes

```python
class BankError(Exception):              # our own family of errors
    """Base class for bank errors."""

class InsufficientFunds(BankError):      # a more specific error
    """Not enough money."""

def withdraw(balance: float, amount: float) -> float:
    if amount > balance:
        raise InsufficientFunds(f"Cannot take {amount}, only {balance} left.")
    return balance - amount

try:
    withdraw(10, 50)
except BankError as err:                 # catches InsufficientFunds too (it's a subclass)
    print("Problem:", err)
# Problem: Cannot take 50, only 10 left.
```

Why make our own classes instead of using `ValueError` everywhere?

- Code that calls us can catch **all** our errors with one `except LiengError:` and still let real bugs
  (like `TypeError`) crash loudly.
- The error's **name** explains the problem (`InvalidHandSizeError` is clearer than `ValueError`).

Two more forms you'll see:

```python
try:
    data = json.load(f)
except json.JSONDecodeError as err:
    raise DatabaseError("Bad file") from err   # "from err" keeps the original error attached
```

```python
try:
    something()
except (KeyError, ValueError, TypeError) as err:   # catch several types at once
    ...
```

## 9. Comprehensions, `sorted` and `key=`

```python
>>> [n * n for n in range(5)]                        # list comprehension
[0, 1, 4, 9, 16]
>>> [n for n in range(10) if n % 3 == 0]             # with a filter
[0, 3, 6, 9]
>>> {w: len(w) for w in ["sap", "lieng"]}            # dict comprehension
{'sap': 3, 'lieng': 5}
>>> sorted({c for c in "banana"})                    # set comprehension (sets have no order, so we sort)
['a', 'b', 'n']
>>> sum(n for n in range(4))                         # generator expression (no list built)
6
```

Sorting by a custom rule with `key=`:

```python
>>> people = [("An", 20), ("Binh", 18), ("Chi", 20)]
>>> sorted(people, key=lambda p: p[1])                   # by age
[('Binh', 18), ('An', 20), ('Chi', 20)]
>>> sorted(people, key=lambda p: (p[1], p[0]), reverse=True)  # by age, then name, descending
[('Chi', 20), ('An', 20), ('Binh', 18)]
```

`lambda p: p[1]` is a tiny unnamed function: "given `p`, return `p[1]`". `list.sort(key=...)` does the
same thing but sorts the list in place.

Unpacking:

```python
>>> r1, r2, r3 = [2, 3, 14]
>>> r1, r2 = r2, r1          # swap two variables
>>> (r1, r2, r3)
(3, 2, 14)
```

## 10. `itertools`: counting hands without writing nested loops

```python
>>> import itertools
>>> list(itertools.combinations("ABCD", 2))                # choose 2, order doesn't matter, no repeats
[('A', 'B'), ('A', 'C'), ('A', 'D'), ('B', 'C'), ('B', 'D'), ('C', 'D')]
>>> list(itertools.combinations_with_replacement("AB", 2))  # repeats allowed
[('A', 'A'), ('A', 'B'), ('B', 'B')]
>>> import math
>>> math.comb(52, 3)                                       # "52 choose 3"
22100
>>> sum(1 for _ in itertools.combinations(range(52), 3))   # count them the hard way
22100
```

- `combinations(deck, 3)` gives every possible **3-card hand** (no card twice).
- `combinations_with_replacement(ranks, 3)` gives every possible **multiset of 3 ranks** (the same
  rank may repeat, like 7-7-9). That's how we'll list the 455 hand types.

## 11. Docstrings (Google style)

The project documents every public function in **Google style**:

```python
def calculate_points(cards: list[int]) -> int:
    """Compute the sum of card values modulo 10.

    Args:
        cards: The card point values.

    Returns:
        The score between 0 and 9.

    Raises:
        ValueError: If the list is empty.
    """
```

- First line: a one-sentence summary.
- `Args:` one line per parameter.
- `Returns:` what comes back.
- `Raises:` which exceptions can happen and when.

Run `help(calculate_points)` in the REPL to see it. Editors also show it when you hover.

---

## ✅ Checkpoint

Paste this whole block into the REPL. It uses almost every feature from this chapter.

```python
from __future__ import annotations
from dataclasses import dataclass
from enum import IntEnum
import itertools

class R(IntEnum):
    TWO = 2
    ACE = 14

@dataclass(frozen=True)
class Score:
    category: int
    rank: int

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Score):
            return NotImplemented
        return (self.category, self.rank) < (other.category, other.rank)

print(R.ACE > R.TWO, R.ACE.name, R(2))
print(Score(4, 2) > Score(3, 14))
print(len(list(itertools.combinations_with_replacement(range(13), 3))))
print(f"{132097.0:,.0f}")
```

Expected output:

```
True ACE 2
True
455
132,097
```

(`print(R(2))` shows `2` because, since Python 3.11, printing an `IntEnum` member prints its number.
The REPL's `repr` would show `<R.TWO: 2>`. Also notice that `Score(4, 2) > Score(3, 14)` works even
though we only wrote `__lt__`: Python flips it into `Score(3, 14) < Score(4, 2)` for you.)

The `455` is a preview of chapter 6: it's the number of ways to choose 3 ranks out of 13 when repeats
are allowed.

## Recap

- **Type hints** document types; `from __future__ import annotations` lets a class refer to itself.
- **`IntEnum`** gives named constants that compare like numbers; **`@property`** makes computed attributes.
- **`@dataclass(frozen=True)`** builds small, immutable, hashable value objects.
- **Dunder methods** (`__lt__`, `__eq__`, `__len__`…) make operators work on your classes.
- **Tuples compare left to right**, which is how one `>` can rank any two hands.
- **`itertools.combinations`** lists every hand; **`combinations_with_replacement`** lists every rank multiset.

**Next:** [04 — Exceptions and cards](04-exceptions-and-cards.md)