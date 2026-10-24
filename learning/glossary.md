# Glossary

Every term the course uses, with the lesson that explains it properly. Back to [COURSE.md](COURSE.md).

---

## The game (Vietnamese terms)

| Term | Meaning | Lesson |
|------|---------|--------|
| **Liêng** | The Vietnamese 3-card game this project is about. Also the name of the second-best hand category (a straight). | [00](00-orientation.md) |
| **Sáp** | Three of a kind (e.g. 7-7-7). The best category; A-A-A is the best hand of all. | [02](02-hand-evaluation.md) |
| **Liêng** (category) | Three consecutive ranks, any suits. A-2-3 is the lowest, Q-K-A the highest; K-A-2 does not count. | [02](02-hand-evaluation.md) |
| **Đĩ** | Three face cards (J, Q, K) that are neither Sáp nor Liêng, e.g. J-Q-Q. Beats every points hand. | [02](02-hand-evaluation.md) |
| **Điểm** | A points hand: the sum of card values modulo 10 (A = 1, 2–9 at face value, 10/J/Q/K = 0). 9 is best, 0 is worst. | [02](02-hand-evaluation.md) |
| **Bù / Tịt** | A points hand worth 0. | [02](02-hand-evaluation.md) |
| **Tố** | Raise. | [00](00-orientation.md) |
| **Tất tay** | Go all-in. | [00](00-orientation.md) |

## The decision (poker and game-theory terms)

| Term | Meaning | Lesson |
|------|---------|--------|
| **Pot (P)** | The money already in the middle before you bet ("dead money"). | [07](07-expected-value.md) |
| **Bet size (B)** | How much you add when you raise. The code assumes the opponent calls exactly `B`. | [07](07-expected-value.md) |
| **Final pot** | `P + 2B`: the pot after you bet and the opponent calls. | [07](07-expected-value.md) |
| **Fold equity (f)** | How often the opponent folds to your raise. A number you choose (guess); the app never measures it. | [07](07-expected-value.md) |
| **Equity / showdown equity (w)** | How often you win when the cards are shown, counting a tie as half a win. | [04](04-generator.md) |
| **Equity vs a random hand** | Equity against all 18,424 hands the opponent could hold. Precomputed in `winrates.json`. | [04](04-generator.md) |
| **Expected value (EV)** | The average profit of a decision if repeated many times: `f·P + (1 − f)·[w·(P + 2B) − B]`, compared with giving up. | [07](07-expected-value.md) |
| **+EV / −EV** | Profitable / losing on average. The app recommends a raise only when EV > 0. | [07](07-expected-value.md) |
| **Break-even fold equity** | The fold rate at which EV is exactly 0. A pure bluff needs `B / (P + B)`. | [07](07-expected-value.md) |
| **Pot odds** | With no folds, the equity a raise needs to break even: `B / (P + 2B)`. | [07](07-expected-value.md) |
| **Bluff / pure bluff** | Raising a hand that rarely wins at showdown, hoping the opponent folds. A pure bluff has `w = 0`. | [07](07-expected-value.md) |
| **Profitable fold zones** | The ranges of fold rates where raising is +EV. Under the range model there can be two. | [07](07-expected-value.md) |
| **Opponent model** | How the opponent decides to fold: `random` (folds regardless of their cards) or `range` (folds their weakest hands). | [06](06-calling-range.md) |
| **Calling range** | The hands the opponent continues with. Under the range model, the strongest `(1 − f)` share of all hands. | [06](06-calling-range.md) |
| **Card removal** | The opponent can't hold the cards you hold, so your hand changes which opponent hands are possible. | [06](06-calling-range.md) |
| **Range coverage** | The share of all 22,100 hands (counted in combinations, not classes) that are profitable to raise. | [08](08-range-finder.md) |
| **Calling station** | An opponent who never folds (`f = 0`). | [08](08-range-finder.md) |
| **GTO** | "Game-theory optimal". The project's UI uses the word, but it computes EV for a given opponent, not a game-theoretic equilibrium. | [00](00-orientation.md) |
| **Heads-up** | Two players. The only situation the app models. | [00](00-orientation.md) |
| **House rule** | A rule this project chose where the game's rules are silent, e.g. how two Đĩ or two 9-point hands are tie-broken. | [02](02-hand-evaluation.md) |

## Counting and algorithms

| Term | Meaning | Lesson |
|------|---------|--------|
| **Combination, C(n, k)** | The number of ways to choose `k` items from `n`, ignoring order. C(52, 3) = 22,100 hands; C(49, 3) = 18,424 opponent hands. | [03](03-canonical-hands.md) |
| **Combinations with replacement** | Choosing `k` items where repeats are allowed. Rank multisets: C(13 + 3 − 1, 3) = 455. | [03](03-canonical-hands.md) |
| **Canonical hand / class** | A hand with its suits forgotten, written as ranks (e.g. "K-Q-3"). All hands in a class have the same strength and the same equity. | [03](03-canonical-hands.md) |
| **Canonical ID** | The string name of a class. Mostly ranks in descending order ("K-Q-J"), except "A-2-3" and "Q-K-A". | [03](03-canonical-hands.md) |
| **Multiplicity** | How many real hands a class stands for: 4 (three of a kind), 24 (a pair) or 64 (three different ranks). | [03](03-canonical-hands.md) |
| **Exact enumeration** | Checking every possible opponent hand. What the generator does by default (18,424 per class). | [04](04-generator.md) |
| **Monte Carlo** | Estimating a probability from random samples. Available with `--monte-carlo`; no longer the default. | [04](04-generator.md) |
| **Score tuple** | The tuple `(category, primary, secondary, score, tie_breaker)` that `HandScore` compares. Python compares tuples element by element. | [02](02-hand-evaluation.md) |
| **Sorting network** | A fixed sequence of compare-and-swap steps that sorts a fixed number of items (here 3) without a loop. | [02](02-hand-evaluation.md) |
| **Prefix sum** | A running total: `prefix[j]` is the sum of the first `j` items, so any range sum is one subtraction. | [06](06-calling-range.md) |
| **Binary search / `bisect`** | Finding a position in a sorted list by halving it; O(log n). `bisect_right` finds the calling boundary. | [06](06-calling-range.md) |
| **Hash table / O(1) lookup** | A dictionary: finding a key takes about the same time however many keys there are. | [05](05-win-rate-db.md) |
| **Offline / online computation** | Do the slow work once ahead of time (offline), so each request only looks answers up (online). | [00](00-orientation.md) |
| **Stars and bars** | The counting trick behind combinations with replacement: 3 cards from 13 ranks gives C(15, 3) = 455 multisets. | [03](03-canonical-hands.md) |
| **Representative hand** | One real hand chosen to stand for a whole class (suits ♠♥♦). Its equity is the class's equity, by suit symmetry. | [03](03-canonical-hands.md) |
| **Standard error** | How far a Monte Carlo estimate typically is from the true value; it shrinks with the square root of the sample count. | [04](04-generator.md) |
| **Boundary class** | Under the range model, the one class that is only partly in the calling range: a fraction of it calls, the rest folds. | [06](06-calling-range.md) |
| **NaN** | "Not a number", a float value (`float('nan')`) that isn't valid JSON. The API currently lets it through. | [10](10-flask-api.md) |

## Python

| Term | Meaning | Lesson |
|------|---------|--------|
| **Exception hierarchy** | Custom errors that inherit from one base (`LiengError`), so `except LiengError` catches all of them. | [01](01-errors-and-cards.md) |
| **`Enum` / `IntEnum`** | A fixed set of named values. `IntEnum` values are also integers, so ranks can be compared and added. | [01](01-errors-and-cards.md) |
| **Frozen dataclass** | `@dataclass(frozen=True)`: Python writes `__init__`, `__repr__` and `__eq__`, and fields can't change after creation. | [01](01-errors-and-cards.md) |
| **`__eq__` / `__hash__` contract** | Objects that compare equal must have equal hashes, or sets and dicts misbehave. `Hand` breaks this. | [02](02-hand-evaluation.md) |
| **`@property`** | A method you read like an attribute (`card.point_value`). | [01](01-errors-and-cards.md) |
| **`@classmethod` / `@staticmethod`** | Methods called on the class (`Card.from_str("As")`) rather than on an instance. | [01](01-errors-and-cards.md) |
| **`Callable[[float], float]`** | The type of "a function that takes a float and returns a float", e.g. `equity_at`. | [07](07-expected-value.md) |
| **`ProcessPoolExecutor`** | Runs work in several processes at once. Functions passed to it must be importable (picklable). | [04](04-generator.md) |
| **Virtual environment (venv)** | A private folder of installed packages for one project. Activate it before running the backend. | [COURSE.md](COURSE.md#setup) |
| **pytest fixture** | A function that prepares something a test needs (e.g. a Flask test client); `scope` controls how often it's rebuilt. | [15](15-tests-and-performance.md) |
| **`monkeypatch` / `capsys`** | pytest helpers: temporarily replace an attribute or environment variable / capture printed output. | [15](15-tests-and-performance.md) |
| **argparse** | The standard library's command-line argument parser. | [09](09-cli.md) |
| **Exit code** | The number a program returns to the shell: 0 means success; the CLI uses 2 for invalid input. | [09](09-cli.md) |
| **`NotImplemented`** | What a comparison method returns for a type it doesn't understand, so Python can try the other operand. | [02](02-hand-evaluation.md) |
| **`functools.total_ordering`** | A decorator that fills in `<=`, `>`, `>=` from `==` and `<`. `CanonicalHand` doesn't use it, so `<=` is missing. | [02](02-hand-evaluation.md) |
| **Pickling** | Turning a Python object into bytes, which is how work is sent to other processes. Worker functions must be defined at module level. | [04](04-generator.md) |
| **GIL** | CPython's global interpreter lock: only one thread runs Python code at a time, so CPU-heavy work uses processes, not threads. | [04](04-generator.md) |
| **Atomic write** | Write to a temporary file, then rename it over the target, so readers never see a half-written file. The generator doesn't do this yet. | [04](04-generator.md) |
| **Exception chaining** | `raise DatabaseError(...) from err` keeps the original error attached, so the traceback shows both. | [05](05-win-rate-db.md) |
| **Dependency injection** | Passing a component what it needs (e.g. the database) instead of letting it create or import it. | [05](05-win-rate-db.md) |
| **Optional import** | `try: import rich except ImportError: ...`, so the program still runs without the package. | [09](09-cli.md) |
| **`SystemExit`** | The exception `sys.exit()` raises; tests catch it to check a CLI's exit code. | [09](09-cli.md) |
| **Fixture scope / `tmp_path` / `xfail`** | How often pytest rebuilds a fixture; a fresh temporary folder per test; marking a test as expected to fail. | [15](15-tests-and-performance.md) |
| **`time.perf_counter`** | The clock to use for measuring short durations. | [15](15-tests-and-performance.md) |
| **ruff / mypy (strict)** | The Python linter and type checker. `backend/pyproject.toml` configures both; CI runs them on every push. | [15](15-tests-and-performance.md) |
| **`functools.cached_property`** | A property computed on first access and stored on the instance; `Hand.score` uses it. | [02](02-hand-evaluation.md) |
| **Lookup table** | Precomputed answers keyed by the input: `evaluate_hand` looks up 455 scores by sorted ranks instead of recomputing them. | [02](02-hand-evaluation.md) |

## Web and frontend

| Term | Meaning | Lesson |
|------|---------|--------|
| **Flask** | A small Python web framework. Each `@app.route` maps a URL to a function. | [10](10-flask-api.md) |
| **JSON API** | An HTTP interface that takes and returns JSON instead of web pages. | [10](10-flask-api.md) |
| **Status code** | The number that says how a request went: 200 OK, 400 bad input, 404 not found, 500 server error, 502 upstream failed. | [10](10-flask-api.md) |
| **CORS** | Browser rules for which other sites may call an API. The backend allows every origin (`*`). | [10](10-flask-api.md) |
| **Test client** | Flask's in-process fake browser: `app.test_client().post(...)` calls a route without starting a server. | [10](10-flask-api.md) |
| **App factory** | A `create_app()` function that builds the app and its dependencies, instead of module-level globals. `app.py` uses one; tests pass in their own database. | [10](10-flask-api.md) |
| **LLM / OpenRouter** | A large language model, reached through the OpenRouter service. Used only by `/api/analyze`, which falls back to a rule-based answer without a key. | [10](10-flask-api.md) |
| **gunicorn / WSGI** | The production server that runs the Flask app with several worker processes. | [16](16-deployment.md) |
| **Procfile** | A one-line file telling a hosting platform how to start the web process. | [16](16-deployment.md) |
| **Environment variable** | A setting passed from outside the program, e.g. `PORT`, `OPENROUTER_API_KEY`, `VITE_API_URL`. | [16](16-deployment.md) |
| **Node / npm** | The JavaScript runtime and its package manager. | [12](12-frontend-tooling.md) |
| **Vite** | The frontend dev server and build tool. `VITE_*` variables are baked into the build. | [12](12-frontend-tooling.md) |
| **Dev proxy** | A Vite setting that forwards `/api` requests to the backend during development. Configured here but unused. | [12](12-frontend-tooling.md) |
| **oxlint** | The JavaScript linter the project uses. | [12](12-frontend-tooling.md) |
| **React / JSX** | A UI library where components are functions returning HTML-like JSX. | [13](13-frontend-app.md) |
| **State (`useState`)** | Values a component remembers between renders; changing them re-renders. | [13](13-frontend-app.md) |
| **Effect (`useEffect`)** | Code that runs after a render, e.g. the first solve on page load. | [13](13-frontend-app.md) |
| **StrictMode** | A React development mode that runs effects twice to expose bugs. | [12](12-frontend-tooling.md) |
| **Controlled input** | An `<input>` whose value comes from state and changes only through `onChange`. | [13](13-frontend-app.md) |
| **`fetch` / `async` / `await`** | The browser's HTTP call, and the syntax for waiting on it. | [13](13-frontend-app.md) |
| **i18n** | Internationalisation: keeping UI text in per-language dictionaries (`i18n.js`). | [13](13-frontend-app.md) |
| **`localStorage`** | Per-browser storage; the UI remembers the chosen language there. | [13](13-frontend-app.md) |
| **Design token / CSS variable** | A named value such as `--accent: #E6B450`, defined once in `index.css` and used everywhere. | [14](14-styling.md) |
| **Ayu Dark** | The colour palette the UI uses (from the VS Code theme of the same name). | [14](14-styling.md) |
| **`:focus-visible`** | The CSS state for keyboard focus; the UI draws a 2px accent ring there. | [14](14-styling.md) |
| **Route / `jsonify`** | A URL handled by a Flask function / the helper that turns a dict into a JSON response. | [10](10-flask-api.md) |
| **Origin / CORS preflight** | Scheme + host + port of a web page / the `OPTIONS` request a browser sends to ask whether a cross-origin call is allowed. | [10](10-flask-api.md) |
| **Prompt injection** | Text a user supplies that changes what an LLM is told to do. `/api/analyze` pastes client text into its prompt. | [10](10-flask-api.md) |
| **Worker process / `--preload`** | gunicorn runs several copies of the app; `--preload` builds it once before forking so the copies share memory. | [16](16-deployment.md) |
| **Bundle / build-time configuration** | The JavaScript files Vite produces for production. `VITE_*` values are copied into them at build time and are public. | [16](16-deployment.md) |
| **ES module / `import.meta.env`** | JavaScript's `import`/`export` file system / where Vite exposes environment variables to the code. | [12](12-frontend-tooling.md) |
| **Fast Refresh** | Vite + React updating the page as you edit, without losing state. | [12](12-frontend-tooling.md) |
| **Derived value** | Something computed from state during render (e.g. `isRaise`) instead of being stored as state. | [13](13-frontend-app.md) |
| **Updater form / lazy initial state** | `setPot(v => v + 10000)` computes from the latest value / `useState(loadSavedLang)` runs the function only on the first render. | [13](13-frontend-app.md) |
| **Promise** | A value that arrives later; `await` waits for it. `fetch` returns one. | [13](13-frontend-app.md) |
| **`Intl.NumberFormat`** | The browser's locale-aware number formatter: 131,876 in English, 131.876 in Vietnamese. | [13](13-frontend-app.md) |
| **`aria-label` / `aria-pressed`** | Attributes that tell screen readers what a control is / whether a toggle button is on. | [13](13-frontend-app.md) |
| **`rem`** | A CSS length relative to the root font size (15px here), so 0.87rem ≈ 13px. | [14](14-styling.md) |
| **CSS grid / media query** | The two-column layout (`340px 1fr`) / rules that apply only below a width (1024, 640, 480px). | [14](14-styling.md) |
| **`tabular-nums`** | A font setting that gives every digit the same width, so numbers line up in tables. | [14](14-styling.md) |
| **Error code** | The stable `code` in every API error (`invalid_hand`, `rate_limited`, …), so clients react to the kind of error, not to its English text. | [10](10-flask-api.md) |
| **Rate limit / Flask-Limiter** | A cap on how often one client may call an endpoint; `/api/analyze` allows 10 per minute by default. | [10](10-flask-api.md) |
| **Blueprint** | A group of Flask routes that an app registers; `app.py` has `api` and `analysis` (the rate-limited one). | [10](10-flask-api.md) |
| **`AbortController`** | A browser object that cancels a `fetch`; the page gives every solve run one, so a newer run cancels an older one. | [13](13-frontend-app.md) |
| **`useEffectEvent`** | A React 19 hook for effect code that reads the latest props/state without becoming an effect dependency. | [13](13-frontend-app.md) |
| **Vitest / Testing Library** | The frontend test runner, and helpers that render components and find elements the way a user would. | [15](15-tests-and-performance.md) |
| **`color-mix()`** | CSS that blends two colours; the profit-map tokens are `--good` / `--bad` mixed with transparency. | [14](14-styling.md) |
| **CI (GitHub Actions)** | Checks that run on every push: backend lint/types/tests, frontend lint/tests/build, the course checker. | [16](16-deployment.md) |

