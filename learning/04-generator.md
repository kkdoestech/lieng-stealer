# Lesson 04 — The generator and `winrates.json`

> **Goal:** understand how `generator.py` plays every one of the 455 hand classes against every
> possible opponent hand, why that takes a minute and not a week, and what each field of the
> resulting `winrates.json` means.
> **Files:** [`backend/src/generator.py`](../backend/src/generator.py),
> [`backend/data/winrates.json`](../backend/data/winrates.json),
> [`backend/tests/test_generator.py`](../backend/tests/test_generator.py).
> **Time:** ~60 min. **Before this:** [03 — Canonical hands: 22,100 → 455](03-canonical-hands.md).

---

## Where this fits

```
 OFFLINE (you run this once, by hand)
 ────────────────────────────────────
 evaluator.py ──► hands.py ──► ┌────────────────────────────┐ ──► data/winrates.json
 who beats whom   455 classes  │ generator.py (this lesson) │     455 records, 82,694 bytes
                               └────────────────────────────┘           │
                                                                         ▼
 ONLINE (every request)                                   db.py (lesson 05) reads it
                                                          calling_range.py (lesson 06) checks itself against it
```

`generator.py` is the only module that does heavy work, and nothing in the running app imports it.
Only its test file does. You run it from the command line when the rules or the evaluator change.
It writes `data/winrates.json`, and from then on the app just reads that file. The file is
committed to git, so a fresh clone works without running the generator at all.

---

## Reading order

| # | Location | What to look for |
|---|----------|------------------|
| 1 | [generator.py:1-7](../backend/src/generator.py#L1-L7) | The docstring: exact enumeration and Monte Carlo, both supported. |
| 2 | [generator.py:28-97](../backend/src/generator.py#L28-L97) | `compute_hand_equity`: one hand class against its opponents. |
| 3 | [generator.py:100-104](../backend/src/generator.py#L100-L104) | `_worker_task`: a tiny wrapper that exists for the process pool. |
| 4 | [generator.py:107-149](../backend/src/generator.py#L107-L149) | `generate_winrates_database`: 455 tasks, in parallel, then one JSON file. |
| 5 | [generator.py:152-207](../backend/src/generator.py#L152-L207) | The command line: `--monte-carlo`, `--samples`, `--output`, `--workers`. |
| 6 | [winrates.json](../backend/data/winrates.json) | Open it and read the first two records. Don't edit it by hand. |
| 7 | [test_generator.py](../backend/tests/test_generator.py) | 7 tests: exact values, invariants, the schema, the CLI defaults. |

---

## Walkthrough

### 1. What "equity" means here

Put your hand against `n` opponent hands and count the results:

```
win_rate  = wins   / n          tie_rate = ties / n          loss_rate = losses / n
equity    = (wins + 0.5 × ties) / n
```

A tie splits the pot, so it counts as half a win. **Equity** is the number the EV formula needs as
"how often do I win when called" (lesson 07). Here the opponent holds a *random* hand: any 3 of the
49 cards you don't hold, all equally likely. Lesson 06 replaces "random" with "the hands that would
actually call".

How many opponent hands are there? You hold 3 of the 52 cards, so the opponent picks 3 of the other
49: C(49, 3) = **18,424** hands. That number appears everywhere in this lesson and the next two.

### 2. One hand against every opponent: exact enumeration

📍 [`backend/src/generator.py:48-70`](../backend/src/generator.py#L48-L70)
```python
    hero_cards = get_representative_cards(canonical_hand.canonical_id)
    hero_score = canonical_hand.score

    # Construct the remaining 49-card deck
    hero_set = set(hero_cards)
    remaining_deck = [c for c in Deck.standard_52() if c not in hero_set]

    wins = 0
    ties = 0
    losses = 0

    if exact:
        # Full combinatorial enumeration: C(49, 3) = 18,424 opponent hands
        opponent_combinations = itertools.combinations(remaining_deck, 3)
        total_showdowns = 18424
        for opp_cards in opponent_combinations:
            opp_score = evaluate_hand(opp_cards)
            if hero_score > opp_score:
                wins += 1
            elif hero_score == opp_score:
                ties += 1
            else:
                losses += 1
```

Read it in three steps:

1. **Pick concrete cards for the class.** `get_representative_cards("Q-K-A")` returns `Q♠ K♥ A♦`
   ([hands.py:119](../backend/src/hands.py#L119), lesson 03). `canonical_hand.score` is the
   `HandScore` computed once when the class was built.
2. **Build the 49-card deck the opponent draws from.** Cards are frozen dataclasses (lesson 01), so
   they hash and `c not in hero_set` is a fast set lookup.
3. **Walk every opponent hand.** `itertools.combinations(remaining_deck, 3)` yields each unordered
   3-card hand exactly once. `HandScore` defines `>` and `==` on its `score_tuple`
   ([evaluator.py:256-279](../backend/src/evaluator.py#L256-L279), lesson 02), so one comparison
   decides each showdown.

**Worked example: Q-K-A.** Counting by hand, without rounding:

| Result | Count | Why |
|--------|-------|-----|
| wins | 18,354 | everything that is not a Sáp and not another Q-K-A |
| ties | 27 | other Q-K-A hands: 3 queens × 3 kings × 3 aces left |
| losses | 43 | every Sáp: 10 untouched ranks × 4 combos + Q, K, A × 1 combo each |
| total | 18,424 | C(49, 3) |

`equity = (18,354 + 0.5 × 27) / 18,424 = 0.99693`, stored as **0.9969**. That is the number you
saw in lesson 07's worked example.

For the whole file the generator does 455 × 18,424 = **8,382,920** evaluations. One class takes
about 0.1 s on the machine this course was written on (4 cores). A full run with one worker took
57 s. Your timings will differ.

### 3. Why one representative per class is enough

The generator plays `Q♠ K♥ A♦` and writes the answer for all 64 Q-K-A hands. Why may it?

Take any other Q-K-A, say `Q♣ K♣ A♣`. Both hands take one queen, one king and one ace out of the
deck. So both leftover decks hold exactly the same number of cards of each rank: four of every
rank from 2 to J, and three each of Q, K and A. Pair the leftover cards up rank by rank (`Q♠` in one
deck with `Q♣` in the other, and so on). That pairing turns every opponent hand of one deck into an
opponent hand of the other with the **same ranks**. In Liêng, strength depends only on ranks
(AGENTS.md §3.1), so each pair of opponent hands has the same score. Same opponents, same scores,
same counts.

You don't have to trust the argument. I ran the same count for `Q♣ K♣ A♣`, all one suit:
`(18354, 27, 43)`, identical to `Q♠ K♥ A♦`. This is what makes the 22,100 → 455 reduction of
lesson 03 pay off here: 455 runs instead of 22,100, about 49 times less work.

### 4. The other branch: Monte Carlo

📍 [`backend/src/generator.py:71-82`](../backend/src/generator.py#L71-L82)
```python
    else:
        # Monte Carlo random sampling
        total_showdowns = samples
        for _ in range(samples):
            opp_cards = random.sample(remaining_deck, 3)
            opp_score = evaluate_hand(opp_cards)
            if hero_score > opp_score:
                wins += 1
            elif hero_score == opp_score:
                ties += 1
            else:
                losses += 1
```

Instead of visiting all 18,424 opponents, Monte Carlo draws `samples` random ones and hopes they
are representative. `random.sample(remaining_deck, 3)` picks 3 distinct cards. The same opponent can
come up twice across iterations, which is fine for an estimate.

How good is the estimate? Here is K-Q-3 (true equity 0.36) with `seed=7`:

| Samples | Estimate | Actual error | Predicted error √(p(1−p)/N) |
|---------|----------|--------------|-----------------------------|
| 100 | 0.405 | 0.045 | 0.048 |
| 1,000 | 0.3495 | 0.0105 | 0.0152 |
| 10,000 | 0.3598 | 0.0002 | 0.0048 |
| 18,424 exact | **0.36** | 0 | — |

The 10,000 row was lucky. The predicted error says a typical run is off by about 0.005. Note that
10,000 samples cost more than half of the exact count (18,424), and they give you only an estimate.
For Liêng the exact method is simply better. Monte Carlo stays in the code because it is the
technique you need when the full space is too big (5-card poker against several players, say).

The test pins a sanity bound instead of a value: Q-K-A with 5,000 samples and `seed=42` gives
0.9973, within 0.015 of the exact 0.9969
([test_generator.py:82-88](../backend/tests/test_generator.py#L82-L88)).

The seed is set at the top of the function:
[generator.py:45-46](../backend/src/generator.py#L45-L46) calls `random.seed(seed)`. That reseeds
Python's **global** random generator, which is a weak spot (see below).

### 5. The record: seven fields

📍 [`backend/src/generator.py:84-97`](../backend/src/generator.py#L84-L97)
```python
    win_rate = wins / total_showdowns
    tie_rate = ties / total_showdowns
    loss_rate = losses / total_showdowns
    equity = (wins + 0.5 * ties) / total_showdowns

    return {
        "equity": round(equity, 4),
        "win_rate": round(win_rate, 4),
        "tie_rate": round(tie_rate, 4),
        "loss_rate": round(loss_rate, 4),
        "category": canonical_hand.category.name,
        "multiplicity": canonical_hand.multiplicity,
        "samples": total_showdowns,
    }
```

| Field | Q-K-A | Meaning |
|-------|-------|---------|
| `equity` | 0.9969 | win + half the ties. The number the rest of the app uses. |
| `win_rate`, `tie_rate`, `loss_rate` | 0.9962, 0.0015, 0.0023 | the three counts divided by 18,424 |
| `category` | `"LIENG"` | the `HandCategory` **name** (`SAP`, `LIENG`, `DI`, `DIEM`), so `db.py` can turn it back into the enum |
| `multiplicity` | 64 | how many of the 22,100 real hands belong to the class (lesson 03) |
| `samples` | 18424 | how many showdowns were counted. 18,424 means "exact". |

**Tie rates come in exactly three sizes.** You can only tie a hand with the same rank multiset
(lesson 02: the score tuple holds all three ranks). So a tie needs the opponent to hold your three
ranks, drawn from what you left in the deck:

| Your class | Example | Opponent ways to copy your ranks | `tie_rate` |
|------------|---------|----------------------------------|------------|
| three distinct ranks | Q-K-A, K-Q-3 | 3 × 3 × 3 = **27** | 27 / 18,424 = 0.0015 |
| a pair | 5-2-2, K-K-Q | C(2,2) × 3 = **3** | 3 / 18,424 = 0.0002 |
| Sáp | A-A-A | C(1,3) = **0** | 0.0 |

Every one of the 455 records has one of those three tie rates.

**Rounding has a cost.** Each rate is rounded on its own, so the three do not always add up to 1.
In the real file, 151 of the 455 records sum to 1.0001. And `equity` is rounded from the raw counts,
so in 314 records it differs from `win_rate + 0.5 × tie_rate` by up to 0.0001. The tests allow
0.001 for both ([test_generator.py:74-80](../backend/tests/test_generator.py#L74-L80)).

### 6. All 455 classes, in parallel

📍 [`backend/src/generator.py:124-140`](../backend/src/generator.py#L124-L140)
```python
    canonical_hands = generate_all_canonical_hands()
    num_workers = workers or os.cpu_count() or 1

    tasks = [
        (ch, exact, samples, i if not exact else None)
        for i, ch in enumerate(canonical_hands)
    ]

    results: dict[str, Any] = {}
    if num_workers > 1:
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            for cid, data in executor.map(_worker_task, tasks):
                results[cid] = data
    else:
        for task in tasks:
            cid, data = _worker_task(task)
            results[cid] = data
```

- **One task per class.** Each is a tuple `(hand, exact, samples, seed)`. In Monte Carlo mode the
  seed is the class's index, so a rerun gives the same numbers. In exact mode there is nothing
  random, so the seed is `None`.
- **Processes, not threads.** The work is pure Python arithmetic. Python threads take turns on one
  core (the GIL), so only separate processes run it truly in parallel. `ProcessPoolExecutor` starts
  `num_workers` copies of Python and hands each one tasks.
- **`executor.map` keeps the input order**, even when tasks finish out of order. So the dict, and
  the file, always list the classes in the same order.
- **One worker means no pool.** The `else` branch runs the same tasks in this process, which is
  easier to debug and is what you get with `--workers 1`.

Why does `_worker_task` exist at all, instead of passing `compute_hand_equity` with a `lambda`?

📍 [`backend/src/generator.py:100-104`](../backend/src/generator.py#L100-L104)
```python
def _worker_task(args: tuple[CanonicalHand, bool, int, int | None]) -> tuple[str, dict[str, Any]]:
    """Worker task wrapper for ProcessPoolExecutor."""
    canonical_hand, exact, samples, seed = args
    result = compute_hand_equity(canonical_hand, exact=exact, samples=samples, seed=seed)
    return canonical_hand.canonical_id, result
```

`executor.map` calls the function with **one** argument per task, so the wrapper unpacks the
tuple. And the function has to travel to another process, which means it has to be **pickled**
(see the concept box). A module-level function pickles as just its name, `src.generator._worker_task`
(45 bytes). A `lambda` fails with `PicklingError: Can't pickle <function <lambda> …>`. The wrapper
also returns the canonical ID next to the result, so the parent knows which record it got.

### 7. Writing the file

📍 [`backend/src/generator.py:142-149`](../backend/src/generator.py#L142-L149)
```python
    # Ensure destination directory exists
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    return results
```

`indent=2` makes the file readable and diff-friendly: 455 records, 82,694 bytes. The order is the
order of `generate_all_canonical_hands`, which is **multiset order, not strength order**. It starts
`"2-2-2", "3-2-2", "4-2-2", "5-2-2", "6-2-2"`. So `"5-2-2"` (9 points, equity 0.8591) sits right
next to `"6-2-2"` (0 points, 0.0038). The file ends with `"Q-K-A", "A-A-Q", "K-K-K", "A-K-K",
"A-A-K", "A-A-A"`. Never assume a position in this file means anything. Lesson 06 builds its own
strength order.

The exact run is deterministic. I regenerated it into a scratch path and compared it with the
committed file: `cmp` reported them **byte-for-byte identical**. That one check proves the
evaluator, the canonical classes and the generator still agree with the data the app serves.

### 8. The command line

📍 [`backend/src/generator.py:163-175`](../backend/src/generator.py#L163-L175)
```python
    parser.add_argument(
        "--exact",
        dest="exact",
        action="store_true",
        default=True,
        help="Run exact combinatorial enumeration over all C(49, 3) = 18,424 hands (default).",
    )
    parser.add_argument(
        "--monte-carlo",
        dest="exact",
        action="store_false",
        help="Estimate equities from --samples random opponent hands instead of exact enumeration.",
    )
```

Both flags write to the same `dest="exact"`. Exact is the default, and `--monte-carlo` flips it to
`False`. Earlier versions defaulted to Monte Carlo and quietly produced a file that failed the
tests, so the safe choice became the default
([test_generator.py:118-124](../backend/tests/test_generator.py#L118-L124) pins that). The price is
a flag that does nothing (weak spot 1). Run it as `python -m src.generator` from `backend/`: the
`-m` form puts `backend/` on the import path, so `from src.evaluator import …` works.

### 9. What the tests pin

| Test | Pins |
|------|------|
| [test_aaa_exact_equity :37](../backend/tests/test_generator.py#L37) | A-A-A: equity 1.0, no ties, `samples == 18424`, `"SAP"` |
| [test_equity_hierarchy_monotonicity :48](../backend/tests/test_generator.py#L48) | A-A-A > 2-2-2 > Q-K-A > A-2-3 > K-K-Q (Đĩ) |
| [test_rate_invariants :67](../backend/tests/test_generator.py#L67) | rates sum to 1 and equity = win + ½ tie, within 0.001 |
| [test_monte_carlo_convergence :82](../backend/tests/test_generator.py#L82) | 5,000 samples land within 0.015 of exact |
| [test_generated_json_database_schema :90](../backend/tests/test_generator.py#L90) | the committed file: 455 keys, 7 fields, `samples == 18424` everywhere |
| [:118](../backend/tests/test_generator.py#L118), [:121](../backend/tests/test_generator.py#L121) | exact by default, Monte Carlo only on request |

The schema test reads the real file, so it fails if someone commits a Monte Carlo file by mistake.

---

## 💡 Concept: pickling and process pools

A worker process has its own memory. To send it a task, Python **pickles** the function and its
arguments into bytes, ships them through a pipe, and unpickles them on the other side.

- Data (tuples, frozen dataclasses, enums) pickles by value.
- Functions pickle **by name**: "module `src.generator`, attribute `_worker_task`". The worker
  imports that module and looks the name up. A `lambda` or a nested function has no importable
  name, so it cannot be sent.
- On Linux the default start method is `fork` (the worker starts as a copy of the parent). On
  Windows and macOS it is `spawn` (a fresh Python that re-imports your module). That is why
  [generator.py:206](../backend/src/generator.py#L206) has an `if __name__ == "__main__":` guard:
  without it, every spawned worker would start the generator again.

## 💡 Concept: how wrong is a Monte Carlo estimate?

Each sample is a coin flip that comes up "win" with probability `p`. After `N` flips, the typical
error of the average is the **standard error** `√(p(1 − p) / N)`. Two consequences:

- Quadrupling `N` only halves the error.
- Hands near 0 or 1 (A-A-A, 4-3-3) are estimated well, hands near 0.5 worst.

For K-Q-3 that is 0.048 at 100 samples and 0.0048 at 10,000, as in the table in section 4.

---

## Design decisions

- **Exact by default.** The space is small (18,424 opponents), so the true value costs about a
  minute of CPU, once. An estimate would add noise to every downstream number and break the
  exact cross-check in lesson 06.
- **One representative per class.** Suit symmetry makes it exact, not an approximation, and it
  cuts the work by about 49 times.
- **Precompute offline, commit the result.** Requests never wait for this. The cost is that the
  file can drift from the code if the rules change and nobody reruns the generator. The schema test
  and the `cmp` check are the guards.
- **JSON, not a binary format.** 83 KB, readable, diff-able, and loads in a few milliseconds.
- **Processes over threads.** It is CPU-bound Python, so only processes help. Tasks are big
  (18,424 evaluations each), so the cost of pickling them is negligible.

---

## ⚠️ Weak spots

1. **`--exact` does nothing.** [generator.py:163-169](../backend/src/generator.py#L163-L169):
   `store_true` with `default=True` can never change the value. Worse, the last flag wins:
   `--monte-carlo --exact` gives exact, `--exact --monte-carlo` gives Monte Carlo. *Fix:* drop
   `--exact`, or put both flags in `parser.add_mutually_exclusive_group()`.
2. **Hard-coded 18,424.** [generator.py:62](../backend/src/generator.py#L62) states the count
   instead of computing it. It is correct today, but if the deck or hand size ever changed, every
   rate would be silently wrong. *Fix:* `math.comb(len(remaining_deck), 3)`, or divide by
   `wins + ties + losses` (exercise 4).
3. **Global random state.** [generator.py:45-46](../backend/src/generator.py#L45-L46) calls
   `random.seed(seed)`, which reseeds the generator every other module shares. AGENTS.md §2.2
   forbids global mutable state. I checked: after one Monte Carlo call with `seed=1`, a caller's
   own `random.seed(123); random.random()` sequence no longer continues where it was.
   *Fix:* `rng = random.Random(seed)` and `rng.sample(...)` (exercise 5).
4. **Output relative to the current directory.** The default `output_path="data/winrates.json"`
   ([generator.py:110](../backend/src/generator.py#L110)) is resolved from wherever you run the
   command. `db.py` has a fallback to `backend/` (lesson 05), the generator doesn't. Run it from
   another directory (with `PYTHONPATH=backend`) and you get a second `data/winrates.json` there,
   while the app keeps reading the old one. *Fix:* default to
   `Path(__file__).resolve().parent.parent / "data" / "winrates.json"`.
5. **Non-atomic write.** [generator.py:146-147](../backend/src/generator.py#L146-L147) opens the
   real file for writing, which empties it first. If the process dies during `json.dump`, the file
   is truncated, and an app starting at that moment fails to load it. *Fix:* write to a `.tmp`
   file next to it, then `os.replace` it into place (exercise 6).
6. **A test that silently skips a hand.**
   [test_generator.py:69-72](../backend/tests/test_generator.py#L69-L72) lists `"10-J-K"`, but the
   canonical ID is `"K-J-10"` (descending, lesson 03), so `continue` skips it without a word. The
   test checks 5 hands while claiming 6. *Fix:* use `"K-J-10"` and replace the `continue` with an
   `assert` (exercise 3).
7. **Rounded rates don't add up.** 151 records sum to 1.0001 (section 5). Harmless for the app,
   which only reads `equity`, but surprising if you validate the file. *Fix:* store the raw counts
   too, or round only `equity`.
8. **Small things.** `Card` is imported but unused ([generator.py:20](../backend/src/generator.py#L20)).
   `Any` appears in three signatures and one variable although AGENTS.md §2.1 asks for a justification. A `TypedDict`
   for the record would document the 7 fields in one place.

---

## 🧪 Try it

Run from `backend/` with the virtual environment active (see [COURSE.md](COURSE.md#setup)).

```bash
python -m pytest tests/test_generator.py -q
```

Expected output (the timing varies):

```
.......                                                                  [100%]
7 passed in 1.03s
```

Peek at the file without dumping it:

```bash
python -c '
import json
d = json.load(open("data/winrates.json"))
print(len(d), list(d)[:5])
print(d["Q-K-A"])
'
```

Expected output:

```
455 ['2-2-2', '3-2-2', '4-2-2', '5-2-2', '6-2-2']
{'equity': 0.9969, 'win_rate': 0.9962, 'tie_rate': 0.0015, 'loss_rate': 0.0023, 'category': 'LIENG', 'multiplicity': 64, 'samples': 18424}
```

Watch Monte Carlo converge on K-Q-3:

```bash
python -c '
from src.hands import generate_all_canonical_hands
from src.generator import compute_hand_equity
kq3 = next(h for h in generate_all_canonical_hands() if h.canonical_id == "K-Q-3")
print("exact", compute_hand_equity(kq3)["equity"])
for n in (100, 1000, 10000):
    print(n, compute_hand_equity(kq3, exact=False, samples=n, seed=7)["equity"])
'
```

Expected output:

```
exact 0.36
100 0.405
1000 0.3495
10000 0.3598
```

Regenerate the whole database **into a scratch file** (never over `data/winrates.json`) and
compare it with the committed one. With one worker this took 57 s here; drop `--workers 1` to use
every core.

```bash
python -m src.generator --workers 1 --output /tmp/winrates_check.json && cmp /tmp/winrates_check.json data/winrates.json && echo IDENTICAL
```

Expected output:

```
Starting equity generation in Exact Combinatorial Enumeration across 1 workers...
Successfully generated database for 455 canonical hands -> /tmp/winrates_check.json
IDENTICAL
```

---

## 🏋️ Exercises

Exercises marked 🟡 or 🔴 change code. Undo them afterwards with `git checkout -- <file>`.

**🟢 1. Predict.** How many of the 18,424 opponent hands beat 2-2-2, the weakest Sáp? What are its
`win_rate` and `loss_rate`?

<details><summary>Solution</summary>

Only a bigger Sáp beats it: 12 ranks (3 to A) × C(4,3) = 4 combos = **48**. Nothing ties (you hold
three of the four 2s). `win_rate = 18,376 / 18,424 = 0.9974`, `loss_rate = 48 / 18,424 = 0.0026`.
Check with `python -c 'import json; print(json.load(open("data/winrates.json"))["2-2-2"])'`.
</details>

**🟢 2. Predict.** What `tie_rate` does 9-9-4 get, and what does
`build_parser().parse_args(["--monte-carlo", "--exact"]).exact` return?

<details><summary>Solution</summary>

9-9-4 is a pair: the opponent needs both remaining 9s and one of three 4s, C(2,2) × 3 = 3 ties,
so `3 / 18,424 = 0.0002`. The parse returns `True`: both flags share `dest="exact"`, and the last
one wins. Check the second with
`python -c 'from src.generator import build_parser; print(build_parser().parse_args(["--monte-carlo", "--exact"]).exact)'`.
</details>

**🟡 3. Make the skipped hand count.** In
[test_generator.py:69-72](../backend/tests/test_generator.py#L69-L72), change `"10-J-K"` to
`"K-J-10"` and replace the two `if … continue` lines with `assert key in canonical_map, key`.
Check with `python -m pytest tests/test_generator.py -q`.

<details><summary>Solution</summary>

```python
        test_keys = ["A-A-A", "Q-K-A", "A-2-3", "9-8-7", "K-K-Q", "K-J-10"]
        for key in test_keys:
            assert key in canonical_map, key
```

All 7 tests still pass, and now a typo in the list fails loudly instead of shrinking the test.
Try `"10-J-K"` again with the assert to see the failure.
</details>

**🟡 4. Remove the magic number.** Replace `total_showdowns = 18424` at
[generator.py:62](../backend/src/generator.py#L62) with a computed value. Check with
`python -m pytest tests/test_generator.py -q`, then regenerate into `/tmp` and `cmp` as in 🧪.

<details><summary>Solution</summary>

Add `import math` and write `total_showdowns = math.comb(len(remaining_deck), 3)`. The tests still
pass (7 passed), and since the value is still 18,424 the regenerated file is identical. An
alternative that cannot disagree with the loop is to compute
`total_showdowns = wins + ties + losses` after it.
</details>

**🟡 5. A private random generator.** Replace the global `random.seed(seed)` at
[generator.py:45-46](../backend/src/generator.py#L45-L46) with an `rng` that belongs to the call.
Check: `python -m pytest tests/test_generator.py -q` still passes, and this prints `True`:

```bash
python -c '
import random
from src.hands import generate_all_canonical_hands
from src.generator import compute_hand_equity
qka = next(h for h in generate_all_canonical_hands() if h.canonical_id == "Q-K-A")
random.seed(123); a = random.random()
random.seed(123); compute_hand_equity(qka, exact=False, samples=10, seed=1); b = random.random()
print(a == b)
'
```

<details><summary>Solution</summary>

```python
    rng = random.Random(seed)
    ...
            opp_cards = rng.sample(remaining_deck, 3)
```

Before the change the command prints `False`; after, `True`. `random.Random(42)` produces the same
sequence as `random.seed(42)`, so the convergence test still gets 0.9973.
</details>

**🔴 6. Atomic write, with a test.** Make `generate_winrates_database` write to a temporary file
next to the target and move it into place. Add a test that runs a tiny Monte Carlo database into
pytest's `tmp_path` and checks that only the final file is left. Check with
`python -m pytest tests/test_generator.py -q`.

<details><summary>Solution</summary>

```python
    tmp_file = out_file.with_name(out_file.name + ".tmp")
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    os.replace(tmp_file, out_file)
```

```python
def test_atomic_write_leaves_no_temp_file(tmp_path: Path) -> None:
    out = tmp_path / "w.json"
    generate_winrates_database(exact=False, samples=10, output_path=out, workers=1)
    assert len(json.loads(out.read_text())) == 455
    assert list(tmp_path.iterdir()) == [out]
```

8 passed. `workers=1` keeps the test fast and avoids starting processes. `os.replace` is atomic
on the same file system: a reader sees either the old file or the new one, never half of one.
</details>

---

## ❓ Quiz

1. Why is the number of opponent hands 18,424 and not 22,100?
2. Why is it enough to evaluate `Q♠ K♥ A♦` to know the equity of all 64 Q-K-A hands?
3. Why does the parallel version need `_worker_task` defined at module level?
4. A record has `tie_rate: 0.0002`. What kind of hand is it?
5. Why does the file list `"5-2-2"` right before `"6-2-2"`, and why must no code rely on file order?

<details><summary>Answers</summary>

1. You hold 3 of the 52 cards, so the opponent chooses 3 of the remaining 49: C(49, 3) = 18,424.
   22,100 = C(52, 3) counts all hands before anyone is dealt.
2. Strength depends only on ranks. Renaming suits maps one Q-K-A to any other and maps the leftover
   deck one-to-one onto the other leftover deck, so the win, tie and loss counts are identical.
3. The function must be pickled to reach the worker process, and functions pickle by importable
   name. A `lambda` or a nested function has no such name.
4. A pair (5-2-2, K-K-Q …): 3 ties / 18,424. Three distinct ranks give 0.0015, a Sáp 0.0.
5. The order comes from `combinations_with_replacement` over ranks (multiset order), not from hand
   strength. 5-2-2 is 9 points and 6-2-2 is 0 points, so position says nothing about strength.
</details>

---

## Recap

- The generator plays one representative of each of the 455 classes against all 18,424 opponent
  hands: 8,382,920 evaluations, about a minute on one core, run once, offline.
- Suit symmetry makes one representative exact, not an approximation.
- `equity = (wins + ½ ties) / 18,424`. Tie rates are 27, 3 or 0 out of 18,424, depending on the
  class shape.
- Monte Carlo is supported but worse here: 10,000 samples cost more than half the exact work and
  are still only accurate to about ±0.005.
- `ProcessPoolExecutor.map` runs tasks in parallel and keeps their order. Its function must be
  module-level, because it is pickled by name.
- `winrates.json` has 455 records with 7 fields, in multiset order. An exact rerun is byte-identical.
- Weak spots: a no-op `--exact`, a hard-coded 18,424, a global RNG seed, a cwd-relative output, a
  non-atomic write, a test that skips `"10-J-K"`.

**Next:** [05 — The win-rate database](05-win-rate-db.md)
