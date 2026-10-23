# 00 — Glossary

Come back to this page whenever you meet a word you do not know. Terms are grouped by topic and sorted
alphabetically inside each group.

---

## 1. Card game terms (Vietnamese → English)

| Term | Meaning |
|------|---------|
| **Bù** / **Tịt** | A hand worth **0 points** (the worst kind of Điểm hand). Example: 10-J-K → 0+0+0 = 0. |
| **Đĩ** (also called *Liên đồng hoa* in some places) | A hand of **three face cards** (J, Q, K) that is **not** a Sáp and **not** a Liêng. Example: J-Q-Q. Category 2. Beats every Điểm hand. |
| **Điểm** | "Points". Any hand that is not Sáp, Liêng or Đĩ. Its score is the sum of the card values, keeping only the last digit (0–9). Category 1. |
| **Liêng** | (1) The name of the game. (2) A hand of **three consecutive ranks**, e.g. 7-8-9 (a "straight"). Category 3. |
| **Sáp** | **Three of a kind**, e.g. 7-7-7. Category 4, the strongest. |
| **Tố** | To **raise** (put more money in and force the opponent to match it or give up). |
| **Tất tay** | To go **all-in** (bet everything you have). |
| **Bỏ bài** | To **fold** (give up the hand and lose what you already put in). |
| **Theo** | To **call** (match the opponent's bet). |

## 2. General card terms

| Term | Meaning |
|------|---------|
| **Card** | One playing card = a **rank** + a **suit**. |
| **Deck** | The 52 cards: 13 ranks × 4 suits. |
| **Face card** | Jack (J), Queen (Q) or King (K). The Ace is **not** a face card. |
| **Hand** | The 3 cards a player holds. |
| **Rank** | 2, 3, 4, 5, 6, 7, 8, 9, 10, J, Q, K, A. |
| **Showdown** | When nobody folds and both players show their cards to see who wins. |
| **Suit** | ♠ spades (s), ♣ clubs (c), ♦ diamonds (d), ♥ hearts (h). In Liêng, suits never change who wins. |

## 3. Poker / game-theory terms

| Term | Meaning |
|------|---------|
| **Bet size (B)** | How much money you add when you raise. |
| **Bluff** | Betting with a weak hand, hoping the opponent folds. |
| **Boundary class** | In the calling-range model, the one hand type that calls only **partly** because the calling range ends inside it (e.g. 57 of `K-9-4`'s 64 combos). |
| **Break-even fold equity** | The smallest fold probability that makes a bet's EV equal to zero. Above it, the bet makes money on average. |
| **Calling range** | The hands an opponent calls with. If they fold their weakest hands 35% of the time, their calling range is their strongest 65%. |
| **Calling station** | A player who almost never folds (fold equity ≈ 0%). |
| **Canonical hand / equivalence class** | A "hand type" that ignores suits. A♠ K♥ Q♦ and A♣ K♣ Q♥ are both the canonical hand **Q-K-A**. There are **455** canonical hands. |
| **Card removal** | The cards in your hand can't be in the opponent's hand, which changes how many combos of each hand type they can hold. |
| **Coverage** | The percentage of all 22,100 real hands for which raising is profitable. |
| **Dead money** | Money already in the pot. Nobody owns it any more; whoever wins the hand takes it. |
| **Equity** | Your share of the pot on average at showdown: `(wins + ½ × ties) / games`. 0.0 = never wins, 1.0 = always wins. |
| **Expected Value (EV)** | The average profit of a decision if you could repeat it many times. EV > 0 means "profitable in the long run". |
| **Final pot** | The size of the pot after both players have bet: `P + 2B`. |
| **Fold equity (P(Fold))** | The probability that the opponent folds when you bet. |
| **GTO (Game Theory Optimal)** | A strategy that cannot be exploited by an opponent. This project borrows the name; it actually computes simple EV, not a full GTO solution. |
| **Multiplicity** | How many real 3-card hands belong to one canonical hand (4, 24 or 64). |
| **Opponent model** | How the program assumes the opponent folds: `random` (regardless of their cards) or `range` (weakest hands first). |
| **Pot (P)** | The money in the middle of the table before your bet. |
| **Profit zone** | An interval of fold frequencies (e.g. 51%–100%) for which raising has EV > 0. A hand can have several. |
| **Range** | A set of hands. "My raising range" = all hands I would raise with. |
| **Win rate** | Fraction of showdowns you win (ties not counted). |

## 4. Maths terms

| Term | Meaning |
|------|---------|
| **Binary search** | Finding a position in a **sorted** list by repeatedly halving the search range: ~9 steps for 456 items. Python: `bisect.bisect_right`. |
| **C(n, k)** ("n choose k") | Number of ways to pick k items from n when order does not matter. `C(52,3) = 22,100`. |
| **Combinations with replacement** | Picking k items from n where the same item can be picked again and order does not matter. Used to count rank multisets: `C(13+3−1, 3) = 455`. |
| **Law of large numbers** | The more random samples you take, the closer their average gets to the true value. |
| **Modulo (mod, %)** | The remainder after division. `19 % 10 = 9`. |
| **Monotonic** | Always moving in one direction. "EV is monotonic in equity" = more equity never gives less EV. |
| **Monte Carlo** | Estimating a number by running many random experiments. |
| **Multiset** | A set that can contain the same item more than once, e.g. {7, 7, 9}. |
| **Prefix sum** | A running total: `prefix[j]` = sum of the first `j` items. The sum of any block of items is then one subtraction. |
| **Probability** | A number from 0 (impossible) to 1 (certain). |

## 5. Python & software terms

| Term | Meaning |
|------|---------|
| **Annotation / type hint** | Text such as `x: int` or `-> str` that says what type something should be. Python does not enforce it, but tools like `mypy` check it. |
| **argparse** | Python's standard library for reading command-line options like `--pot 100000`. |
| **`array` (module)** | Compact arrays of plain numbers, e.g. `array("i", [0, 4, 8])`: 4 bytes per integer instead of a full Python object. |
| **`Callable`** | Type hint for "a function": `Callable[[float], float]` takes one float and returns a float. |
| **Class / instance** | A class is a blueprint (`Card`), an instance is one object built from it (`Card(ACE, SPADES)`). |
| **`@classmethod`** | A method that receives the class (`cls`) instead of an instance. Often used as an alternative constructor, e.g. `Card.from_str("Ah")`. |
| **Closure** | A function that remembers variables from where it was created, e.g. `lambda f: model.equity(cid, f)` remembers `model` and `cid`. |
| **`@dataclass`** | A decorator that writes `__init__`, `__repr__` and `__eq__` for you from the list of fields. `frozen=True` makes instances read-only. |
| **Decorator** | A line starting with `@` above a function or class that changes how it behaves. |
| **Dependency Injection (DI)** | Passing the objects a class needs into its constructor, instead of the class creating or finding them itself (e.g. global variables). |
| **Deterministic** | Gives the same output every time for the same input. |
| **Docstring** | The string in triple quotes right under a `def` or `class`. It documents the code. |
| **Dunder method** | A "double underscore" method such as `__init__`, `__eq__`, `__lt__`, `__len__`. Python calls them for you (e.g. `a < b` calls `a.__lt__(b)`). |
| **Enum / IntEnum** | A class whose members are a fixed set of named constants, e.g. `Suit.SPADES`. `IntEnum` members also behave like integers. |
| **`str` + `Enum`** | `class OpponentModel(str, Enum)`: enum members that are also strings, so `OpponentModel.RANGE == "range"` and they convert to JSON naturally. |
| **Exception** | An error object that is "raised" and can be "caught" with `try/except`. |
| **Fixture (pytest)** | A function that prepares something (e.g. a loaded database) and passes it into tests. |
| **Hash / hashable** | A hash is a number computed from an object so it can be found quickly in a `dict` or `set`. Hashable objects must not change. |
| **Hash table** | The data structure behind Python's `dict`: finds a value by key in (on average) constant time, O(1). |
| **Immutable** | Cannot be changed after creation (like a `tuple` or a frozen dataclass). |
| **Module / package** | A module is one `.py` file. A package is a folder of modules with an `__init__.py`. |
| **O(1), O(n)** | "Big-O" notation. O(1) = takes the same time no matter how much data; O(n) = time grows with the amount of data. |
| **Parameter object** | A small class that bundles values which always travel together, e.g. `GameParams(pot, bet_size, fold_equity, opponent_model)`. |
| **Process / multiprocessing** | Running several copies of Python at once so you can use several CPU cores. |
| **Pure function** | A function whose result depends only on its inputs and that changes nothing outside itself. |
| **pytest** | The testing tool we use. It finds functions named `test_...` and runs them. |
| **REPL** | "Read–Eval–Print Loop": the interactive `>>>` Python prompt. Start it with `python3`. |
| **Virtual environment (venv)** | A private folder of installed packages for one project. |

## 6. Web terms

| Term | Meaning |
|------|---------|
| **API** | "Application Programming Interface". Here: a set of URLs that other programs can call to get data. |
| **`aria-*` attributes** | HTML attributes for screen readers: `aria-label` names a control, `aria-pressed` says whether a toggle is on. |
| **Component (React)** | A JavaScript function that returns a piece of UI. |
| **CORS** | "Cross-Origin Resource Sharing". A browser safety rule: a page from `localhost:5173` may only call an API on `localhost:5000` if the API says that is allowed. |
| **CSS variable** | A named value like `--accent-green: #22C55E;` you can reuse with `var(--accent-green)`. |
| **Endpoint / route** | One URL + method of an API, e.g. `POST /api/solve`. |
| **Environment variable** | A setting given to a program by the operating system, e.g. `OPENROUTER_API_KEY`. Good for secrets. |
| **Error handler (Flask)** | A function registered with `@app.errorhandler(SomeError)` that turns that exception into an HTTP response (e.g. 400) for every route. |
| **fetch** | The browser's built-in function to make HTTP requests from JavaScript. |
| **Flask** | A small Python library for building web servers and APIs. |
| **gunicorn** | A production-quality server that runs Flask apps. |
| **Hook (React)** | A function whose name starts with `use` (e.g. `useState`, `useEffect`) that adds features to a component. |
| **HTTP method** | `GET` (read something), `POST` (send data to be processed), etc. |
| **HTTP status code** | `200` OK, `400` bad request (client's fault), `500`/`502` server/gateway error. |
| **i18n (internationalisation)** | Making an app work in several languages: all texts in one dictionary per language (`STRINGS.en`, `STRINGS.vi`). |
| **Inline style (React)** | CSS set directly on an element from JavaScript: `style={{ left: "40%" }}`. Used for values computed at run time. |
| **JSON** | A text format for data: `{"pot": 100000, "hand": "As Kh Qd"}`. |
| **JSX** | HTML-like syntax inside JavaScript, used by React: `<h1>{title}</h1>`. |
| **LLM** | Large Language Model (an AI that writes text). The project optionally asks one for commentary. |
| **`localStorage`** | A small key/value store in the browser that survives page reloads; used to remember the chosen language. |
| **npm** | Node's package manager (like `pip` for JavaScript). |
| **React** | A JavaScript library for building user interfaces from components. |
| **REST** | A style of API design where URLs name resources and HTTP methods name actions. |
| **State (React)** | Data a component remembers between renders. Changing it re-draws the UI. |
| **Vite** | A fast development server and build tool for frontend projects. |
